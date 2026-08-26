"""Small CLI wrapper around the same analysis service used by the API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzers.sanitizer import build_sanitize_payload, sanitize_image
from .errors import AnalysisError
from .models.result import SanitizationGroup
from .service import AnalysisService


def _inspect_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect image provenance metadata.")
    parser.add_argument("image", type=Path, help="Path to an image file")
    return parser


def _sanitize_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-provenance-inspector sanitize",
        description="Remove selected privacy metadata while preserving provenance signals.",
    )
    parser.add_argument("image", type=Path, help="Path to an image file")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the sanitized image",
    )
    parser.add_argument(
        "--remove",
        dest="groups",
        action="append",
        choices=[group.value for group in SanitizationGroup],
        help="Privacy group to remove; repeat for multiple groups (default: all)",
    )
    return parser


def _run_inspect(arguments: list[str]) -> None:
    parser = _inspect_parser()
    args = parser.parse_args(arguments)
    result = AnalysisService().analyze(args.image.read_bytes())
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


def _run_sanitize(arguments: list[str]) -> None:
    parser = _sanitize_parser()
    args = parser.parse_args(arguments)
    source = args.image.resolve()
    destination = args.output.resolve()
    if source == destination:
        parser.error("--output must be different from the input image")
    try:
        input_data = args.image.read_bytes()
        groups = [SanitizationGroup(group) for group in args.groups] if args.groups else None
        output_data, report = sanitize_image(input_data, groups)
        original_info, output_info, encoded = build_sanitize_payload(input_data, output_data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(output_data)
    except AnalysisError as exc:
        parser.error(exc.message)
    payload = {
        "original": original_info.model_dump(mode="json"),
        "output": output_info.model_dump(mode="json"),
        "image": encoded.model_dump(mode="json"),
        "report": report.model_dump(mode="json"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "sanitize":
        _run_sanitize(arguments[1:])
        return
    _run_inspect(arguments)
