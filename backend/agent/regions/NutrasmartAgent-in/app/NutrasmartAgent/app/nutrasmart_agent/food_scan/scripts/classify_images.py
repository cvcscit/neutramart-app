#!/usr/bin/env python
"""Classify local images with the configured cuisine-model ensemble (no Bedrock, no agent).

Loads every checkpoint in ``FOOD_CLASSIFIER_MODELS`` through the production code path
(``recognition.build_classifier`` + ``analysis.decode_image``) and prints, per image,
which model won, its top-k predictions, and whether the result clears
``FOOD_CLASSIFIER_THRESHOLD`` (otherwise the agent would fall back to the vision LLM).

Example::

    FOOD_CLASSIFIER_MODELS="chinese=/models/chinese.pt,indian=/models/indian.pt,thai=/models/thai.pt" \\
        python app/nutrasmart_agent/food_scan/scripts/classify_images.py photo1.jpg photo2.png
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

# Allow running as a plain script from backend/agent without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.nutrasmart_agent.food_scan.analysis import decode_image  # noqa: E402
from app.nutrasmart_agent.food_scan.recognition import build_classifier  # noqa: E402
from app.nutrasmart_agent.food_scan.settings import load_settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("images", nargs="+", type=Path, help="Image files to classify.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = replace(load_settings().classifier, enabled=True)
    if not settings.models:
        print("Set FOOD_CLASSIFIER_MODELS (name=uri,name=uri,...) first.", file=sys.stderr)
        return 2

    s3 = None
    if any(model.uri.startswith("s3://") for model in settings.models):
        from app.nutrasmart_agent.food_scan.services import build_services

        s3 = build_services(load_settings()).model_s3
    classifier = build_classifier(settings, s3)

    for path in args.images:
        result = classifier.classify(decode_image(path.read_bytes()))
        route = "classifier" if result.top.confidence >= settings.threshold else "vision LLM fallback"
        print(f"{path.name}: model={result.model} -> {route} (threshold {settings.threshold:.2f})")
        for prediction in result.predictions:
            print(f"    {prediction.confidence:6.1%}  {prediction.display_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
