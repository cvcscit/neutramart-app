"""EfficientNetV2-S food classifier backed by a NutraSmart training checkpoint.

Ported from the wellness360 ``predict_food.py`` reference script. Production runs on
CPU (AgentCore has no GPU); ``device="cuda"`` is supported for local evaluation. Both
run in float32 (no autocast) so GPU scores match production CPU scores. The checkpoint is a plain dict:
``model_state_dict``, ``class_names``, ``class_to_index`` and optional preprocessing
fields (``image_size``, ``imagenet_mean``, ``imagenet_std``, ``architecture``). It is
loaded with ``weights_only=True`` so no arbitrary pickled code can run.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image, ImageOps
from torchvision import transforms
from torchvision.models import efficientnet_v2_s

from .base import ClassificationResult, ClassifierError, FoodPrediction

logger = logging.getLogger(__name__)

ARCHITECTURE = "efficientnet_v2_s"
_REQUIRED_KEYS = ("model_state_dict", "class_names", "class_to_index")
_RESIZE_SIZE = 256  # eval-time resize before center crop, as in training
_DEFAULT_IMAGE_SIZE = 224
_DEFAULT_MEAN = (0.485, 0.456, 0.406)
_DEFAULT_STD = (0.229, 0.224, 0.225)


def _display_name(food_id: str) -> str:
    return food_id.replace("_", " ").title()


def _resolve_device(device: str) -> torch.device:
    if device == "cuda" and not torch.cuda.is_available():
        raise ClassifierError("FOOD_CLASSIFIER_DEVICE=cuda but CUDA is not available in this torch build.")
    if device == "cuda":
        # TF32 convolutions shift confidences by ~1e-4 and can reorder near-ties; keep full
        # float32 so GPU evaluations reproduce production (CPU) scores exactly.
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
    return torch.device(device)


def _load_checkpoint(path: Path, device: torch.device) -> dict:
    try:
        checkpoint = torch.load(path, map_location=device, weights_only=True)
    except Exception as exc:
        raise ClassifierError(f"Could not load checkpoint {path}: {exc}") from exc

    if not isinstance(checkpoint, dict):
        raise ClassifierError("Checkpoint is not a dict.")
    missing = [key for key in _REQUIRED_KEYS if key not in checkpoint]
    if missing:
        raise ClassifierError(f"Checkpoint is missing required fields: {missing}")
    architecture = checkpoint.get("architecture", ARCHITECTURE)
    if architecture != ARCHITECTURE:
        raise ClassifierError(
            f"Checkpoint architecture {architecture!r} does not match backend {ARCHITECTURE!r}."
        )
    return checkpoint


def _index_to_class(checkpoint: dict) -> dict[int, str]:
    class_names = checkpoint["class_names"]
    if not isinstance(class_names, list) or not class_names:
        raise ClassifierError("Invalid or empty class_names in checkpoint.")
    mapping = {int(index): name for name, index in checkpoint["class_to_index"].items()}
    if set(mapping) != set(range(len(class_names))):
        raise ClassifierError(f"Invalid class mapping: expected indices 0..{len(class_names) - 1}.")
    return mapping


def _build_model(checkpoint: dict, num_classes: int, device: torch.device) -> nn.Module:
    model = efficientnet_v2_s(weights=None)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    try:
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    except RuntimeError as exc:
        raise ClassifierError(f"Checkpoint does not match EfficientNetV2-S: {exc}") from exc
    model.to(device)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad = False
    return model


def _build_transform(checkpoint: dict) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(_RESIZE_SIZE),
            transforms.CenterCrop(checkpoint.get("image_size", _DEFAULT_IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(
                checkpoint.get("imagenet_mean", _DEFAULT_MEAN),
                checkpoint.get("imagenet_std", _DEFAULT_STD),
            ),
        ]
    )


class EfficientNetV2SClassifier:
    """``FoodClassifier`` implementation using original + mirrored test-time augmentation."""

    def __init__(
        self,
        model: nn.Module,
        transform: transforms.Compose,
        index_to_class: dict[int, str],
        top_k: int,
        device: torch.device,
    ) -> None:
        self._device = device
        self._model = model
        self._transform = transform
        self._index_to_class = index_to_class
        self._top_k = min(top_k, len(index_to_class))

    @classmethod
    def from_checkpoint(
        cls, path: Path, top_k: int, num_threads: int, device: str = "cpu"
    ) -> "EfficientNetV2SClassifier":
        """Load and validate a checkpoint file and build a ready-to-use classifier."""
        torch.set_num_threads(num_threads)
        torch_device = _resolve_device(device)
        checkpoint = _load_checkpoint(path, torch_device)
        index_to_class = _index_to_class(checkpoint)
        model = _build_model(checkpoint, len(index_to_class), torch_device)
        logger.info("food_classifier_loaded %s", json.dumps({
            "architecture": ARCHITECTURE,
            "device": str(torch_device),
            "path": str(path),
            "classes": len(index_to_class),
            "epoch": checkpoint.get("epoch"),
            "validation_macro_f1": checkpoint.get("validation_macro_f1"),
        }))
        return cls(model, _build_transform(checkpoint), index_to_class, top_k, torch_device)

    def classify(self, image: Image.Image) -> ClassificationResult:
        """Average softmax over the image and its mirror; return the top-k predictions."""
        try:
            batch = torch.stack(
                [self._transform(image), self._transform(ImageOps.mirror(image))]
            ).to(self._device)
            with torch.inference_mode():
                probabilities = torch.softmax(self._model(batch), dim=1).mean(dim=0).cpu()
            values, indices = torch.topk(probabilities, k=self._top_k)
        except Exception as exc:
            raise ClassifierError(f"Food classifier inference failed: {exc}") from exc

        predictions = tuple(
            FoodPrediction(
                food_id=self._index_to_class[int(index)],
                display_name=_display_name(self._index_to_class[int(index)]),
                confidence=float(value),
            )
            for value, index in zip(values.tolist(), indices.tolist())
        )
        return ClassificationResult(predictions=predictions)
