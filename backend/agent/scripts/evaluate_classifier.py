#!/usr/bin/env python
"""Evaluate the food classifier on a folder-per-class image directory.

Runs every image under ``DATA_DIR/<label>/*`` through the same code path the agent
uses in production (``analysis.decode_image`` + ``recognition.build_classifier``) and
reports, per split:

- top-1 / top-k accuracy against the folder label;
- the share of images that would take the classifier route (top-1 >= threshold);
- the accuracy of that route (how often a confident label is actually right), which is
  what matters in production because below-threshold images go to the vision LLM;
- a threshold sweep, to help choose ``FOOD_CLASSIFIER_THRESHOLD``.

If ``--manifest`` (the training ``path,label,sha256,split`` CSV) is given, images are
matched by SHA-256 to their training split. Only images the model never trained on
(``test``, or ``unseen`` when absent from the manifest) give an honest estimate.

Example::

    python scripts/evaluate_classifier.py "/data/Indian Food Images" --device cuda \\
        --model /path/to/nutrasmart_efficientnetv2s_best.pt \\
        --manifest /path/to/nutrasmart_manifest.csv --output results.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Allow running as a plain script from backend/agent without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.nutrasmart_agent.analysis import decode_image  # noqa: E402
from app.nutrasmart_agent.recognition import ClassifierError, build_classifier  # noqa: E402
from app.nutrasmart_agent.settings import CLASSIFIER_DEVICES, ClassifierSettings, load_settings  # noqa: E402

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
UNSEEN_SPLIT = "unseen"
ALL_SPLITS = "all"
SWEEP_THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
WORST_CLASSES_SHOWN = 10


@dataclass(frozen=True)
class ImageResult:
    """Outcome of classifying one image."""

    path: Path
    label: str
    split: str
    predicted: str = ""
    confidence: float = 0.0
    top_k: tuple[str, ...] = ()
    error: str = ""

    @property
    def correct(self) -> bool:
        return not self.error and self.predicted == self.label

    @property
    def in_top_k(self) -> bool:
        return not self.error and self.label in self.top_k


@dataclass
class SplitStats:
    """Aggregates for one split (or all images)."""

    results: list[ImageResult] = field(default_factory=list)

    @property
    def scored(self) -> list[ImageResult]:
        return [r for r in self.results if not r.error]

    def routed(self, threshold: float) -> list[ImageResult]:
        return [r for r in self.scored if r.confidence >= threshold]


def parse_args(defaults: ClassifierSettings) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("data_dir", type=Path, help="Directory with one sub-folder per label.")
    parser.add_argument(
        "--model",
        default=defaults.model_uri or None,
        required=not defaults.model_uri,
        help="Checkpoint path or s3:// URI (default: FOOD_CLASSIFIER_MODEL_URI).",
    )
    parser.add_argument("--backend", default=defaults.backend, help="Classifier backend name.")
    parser.add_argument(
        "--threshold", type=float, default=defaults.threshold,
        help="Confidence threshold for the classifier route (default: FOOD_CLASSIFIER_THRESHOLD).",
    )
    parser.add_argument("--top-k", type=int, default=defaults.top_k, help="k for top-k accuracy.")
    parser.add_argument("--threads", type=int, default=defaults.num_threads, help="Torch CPU threads.")
    parser.add_argument(
        "--device", choices=CLASSIFIER_DEVICES, default=defaults.device,
        help="Inference device (default: FOOD_CLASSIFIER_DEVICE). 'cuda' needs requirements-gpu.txt.",
    )
    parser.add_argument("--manifest", type=Path, help="Training manifest CSV (path,label,sha256,split).")
    parser.add_argument("--output", type=Path, help="Write per-image results to this CSV.")
    parser.add_argument("--limit", type=int, help="Only evaluate the first N images (quick check).")
    args = parser.parse_args()
    if not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be within [0, 1]")
    return args


def find_images(data_dir: Path) -> list[tuple[Path, str]]:
    """Return ``(path, label)`` for every image file, label = parent folder name."""
    if not data_dir.is_dir():
        raise SystemExit(f"Not a directory: {data_dir}")
    images = sorted(
        (path, path.parent.name)
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and path.parent != data_dir
    )
    if not images:
        raise SystemExit(f"No images found under {data_dir}")
    return images


def load_manifest_splits(manifest: Path | None) -> dict[str, str]:
    """Map SHA-256 -> training split (empty if no manifest)."""
    if manifest is None:
        return {}
    with manifest.open(newline="") as fh:
        return {row["sha256"]: row["split"] for row in csv.DictReader(fh)}


def classify_image(classifier, path: Path, label: str, split: str, raw: bytes) -> ImageResult:
    try:
        result = classifier.classify(decode_image(raw))
    except (ValueError, ClassifierError) as exc:
        return ImageResult(path=path, label=label, split=split, error=str(exc))
    return ImageResult(
        path=path,
        label=label,
        split=split,
        predicted=result.top.food_id,
        confidence=result.top.confidence,
        top_k=tuple(p.food_id for p in result.predictions),
    )


def evaluate(classifier, images, splits_by_sha: dict[str, str]) -> list[ImageResult]:
    results = []
    started = time.perf_counter()
    for index, (path, label) in enumerate(images, start=1):
        raw = path.read_bytes()
        split = splits_by_sha.get(hashlib.sha256(raw).hexdigest(), UNSEEN_SPLIT)
        results.append(classify_image(classifier, path, label, split, raw))
        if index % 100 == 0 or index == len(images):
            rate = index / (time.perf_counter() - started)
            print(f"\r  {index}/{len(images)} images ({rate:.1f}/s)", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return results


def _pct(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:6.1%}" if denominator else "     –"


def print_split_table(stats_by_split: dict[str, SplitStats], threshold: float, top_k: int) -> None:
    header = (
        f"{'split':<10}{'images':>8}{'errors':>8}{'top-1':>8}{f'top-{top_k}':>8}"
        f"{'routed':>9}{'routed acc':>12}{'confident+wrong':>17}"
    )
    print(f"\nResults at threshold {threshold:.2f} (routed = would skip the vision LLM)")
    print(header)
    print("-" * len(header))
    for name, stats in stats_by_split.items():
        scored, routed = stats.scored, stats.routed(threshold)
        wrong_routed = sum(not r.correct for r in routed)
        print(
            f"{name:<10}{len(stats.results):>8}{len(stats.results) - len(scored):>8}"
            f"{_pct(sum(r.correct for r in scored), len(scored)):>8}"
            f"{_pct(sum(r.in_top_k for r in scored), len(scored)):>8}"
            f"{_pct(len(routed), len(scored)):>9}"
            f"{_pct(sum(r.correct for r in routed), len(routed)):>12}"
            f"{wrong_routed:>17}"
        )


def print_threshold_sweep(name: str, stats: SplitStats, current: float) -> None:
    thresholds = sorted(set(SWEEP_THRESHOLDS) | {current})
    scored = stats.scored
    print(f"\nThreshold sweep on '{name}' ({len(scored)} images)")
    print(f"{'threshold':>10}{'routed':>9}{'routed acc':>12}{'confident+wrong':>17}")
    for threshold in thresholds:
        routed = stats.routed(threshold)
        marker = "  <- current" if threshold == current else ""
        print(
            f"{threshold:>10.2f}{_pct(len(routed), len(scored)):>9}"
            f"{_pct(sum(r.correct for r in routed), len(routed)):>12}"
            f"{sum(not r.correct for r in routed):>17}{marker}"
        )


def print_worst_classes(name: str, stats: SplitStats) -> None:
    per_class: dict[str, list[ImageResult]] = defaultdict(list)
    for result in stats.scored:
        per_class[result.label].append(result)
    ranked = sorted(per_class.items(), key=lambda item: sum(r.correct for r in item[1]) / len(item[1]))
    print(f"\nWorst {WORST_CLASSES_SHOWN} classes on '{name}' (top-1, most common wrong prediction)")
    for label, results in ranked[:WORST_CLASSES_SHOWN]:
        confusions = Counter(r.predicted for r in results if not r.correct).most_common(1)
        confused = f"-> {confusions[0][0]} ({confusions[0][1]})" if confusions else ""
        print(f"  {label:<28}{_pct(sum(r.correct for r in results), len(results))}  n={len(results):<4}{confused}")


def write_csv(path: Path, results: list[ImageResult], threshold: float) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["path", "label", "split", "predicted", "confidence", "correct", "routed", "top_k", "error"])
        for r in results:
            writer.writerow([
                str(r.path), r.label, r.split, r.predicted, f"{r.confidence:.6f}", int(r.correct),
                int(not r.error and r.confidence >= threshold), "|".join(r.top_k), r.error,
            ])
    print(f"\nPer-image results written to {path}")


def honest_split(stats_by_split: dict[str, SplitStats]) -> str:
    """The split the model never trained on, for the sweep and worst-class report."""
    for name in ("test", UNSEEN_SPLIT):
        if name in stats_by_split:
            return name
    return ALL_SPLITS


def main() -> int:
    defaults = load_settings().classifier
    args = parse_args(defaults)

    images = find_images(args.data_dir)
    if args.limit:
        images = images[: args.limit]
    labels = {label for _, label in images}
    print(f"Found {len(images)} images in {len(labels)} label folders", file=sys.stderr)

    settings = ClassifierSettings(
        enabled=True,
        backend=args.backend,
        model_uri=str(args.model),
        threshold=args.threshold,
        top_k=args.top_k,
        cache_dir=defaults.cache_dir,
        num_threads=args.threads,
        device=args.device,
    )
    # boto3 is only needed for s3:// model URIs; build the client lazily for that case.
    s3 = None
    if settings.model_uri.startswith("s3://"):
        from app.nutrasmart_agent.services import build_services

        s3 = build_services(load_settings()).s3
    classifier = build_classifier(settings, s3)

    splits_by_sha = load_manifest_splits(args.manifest)
    results = evaluate(classifier, images, splits_by_sha)

    stats_by_split: dict[str, SplitStats] = defaultdict(SplitStats)
    for result in results:
        stats_by_split[result.split].results.append(result)
        stats_by_split[ALL_SPLITS].results.append(result)
    ordered = {name: stats_by_split[name] for name in ("train", "val", "test", UNSEEN_SPLIT, ALL_SPLITS)
               if name in stats_by_split}

    print_split_table(ordered, args.threshold, args.top_k)
    focus = honest_split(ordered)
    if args.manifest and focus != ALL_SPLITS:
        print(f"\nNote: train/val images were seen during training; '{focus}' is the honest estimate.")
    print_threshold_sweep(focus, ordered[focus], args.threshold)
    print_worst_classes(focus, ordered[focus])

    errors = [r for r in results if r.error]
    for r in errors[:10]:
        print(f"  ERROR {r.path}: {r.error}", file=sys.stderr)

    if args.output:
        write_csv(args.output, results, args.threshold)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
