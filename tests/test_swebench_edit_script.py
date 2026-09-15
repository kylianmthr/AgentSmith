import base64
import json
import os
from pathlib import Path
import subprocess
import sys

from mcp_tools_swebench import EDIT_SCRIPT


def run_edit_script(
    path: Path,
    old: str,
    new: str,
) -> subprocess.CompletedProcess[str]:
    payload = base64.b64encode(
        json.dumps({"path": str(path), "old": old, "new": new}).encode()
    ).decode()
    env = {**os.environ, "PATH": ""}
    return subprocess.run(
        [sys.executable, "-c", EDIT_SCRIPT, payload],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_edit_script_reports_no_new_lint_violations(tmp_path: Path) -> None:
    target = tmp_path / "module.py"
    target.write_text("value = 1\n", encoding="utf-8")

    result = run_edit_script(target, "value = 1", "value = 2")

    assert result.returncode == 0
    assert "EDIT OK" in result.stdout
    assert "No new lint violations (basic)" in result.stdout
    assert target.read_text(encoding="utf-8") == "value = 2\n"


def test_edit_script_reports_introduced_lint_violation(tmp_path: Path) -> None:
    target = tmp_path / "module.py"
    target.write_text(
        "try:\n    value = 1\nexcept Exception:\n    value = 2\n",
        encoding="utf-8",
    )

    result = run_edit_script(target, "except Exception:", "except:")

    assert result.returncode == 3
    assert "INTRODUCED LINT VIOLATIONS" in result.stdout
    assert "E722 Do not use bare except" in result.stdout
    assert "except:" in target.read_text(encoding="utf-8")
