"""Small CLI wrapper around the same analysis service used by the API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import AnalysisService


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect image provenance metadata.")
    parser.add_argument("image", type=Path, help="Path to an image file")
    args = parser.parse_args()
    result = AnalysisService().analyze(args.image.read_bytes())
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
