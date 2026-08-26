from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app import cli

REPOSITORY_ROOT = Path(__file__).parents[1]
FIXTURE_PATH = REPOSITORY_ROOT / "fixtures" / "official-c2pa" / "C.jpg"


def _cli_environment() -> dict[str, str]:
    environment = os.environ.copy()
    executable_directory = str(Path(sys.executable).parent)
    environment["PATH"] = os.pathsep.join([executable_directory, environment.get("PATH", "")])
    return environment


def _run_installed_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["image-provenance-inspector", *arguments],
        cwd=REPOSITORY_ROOT,
        env=_cli_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed


def test_installed_cli_help_smoke() -> None:
    completed = _run_installed_cli("--help")

    assert "usage: image-provenance-inspector" in completed.stdout
    assert "Path to an image file" in completed.stdout


def test_installed_cli_analyzes_fixture() -> None:
    completed = _run_installed_cli(str(FIXTURE_PATH))
    payload = json.loads(completed.stdout)

    assert payload["file"]["format"] == "JPEG"
    assert payload["c2pa"]["present"] is True
    assert payload["assessment"]["origin"]["type"] == "UNKNOWN"
    assert payload["assessment"]["editing"]["type"] == "UNKNOWN"


def test_cli_main_serializes_result(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["image-provenance-inspector", str(FIXTURE_PATH)])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["file"]["sha256"]
    assert payload["c2pa"]["actions"] == ["c2pa.created"]
