import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from agent_smith.agent import deadline as deadline_module
from agent_smith.sandbox import manager as manager_module


@pytest.mark.parametrize("module", ["agent_mbpp", "agent_swebench"])
def test_cli_reports_malformed_task_without_traceback(
    module: str, tmp_path: Path
) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text("{not-json", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", module, "--task-file", str(task_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("Error: invalid task data")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("module", ["agent_mbpp", "agent_swebench"])
def test_cli_reports_invalid_sandbox_config_without_traceback(
    module: str, tmp_path: Path
) -> None:
    task_path = tmp_path / "task.json"
    if module == "agent_mbpp":
        task_json = (
            '{"task_id": 1, "task_definition": "Return one", '
            '"function_definition": "def one():"}'
        )
    else:
        task_json = (
            '{"instance_id": "project__repo-1", '
            '"problem_statement": "Fix it", "docker_image": "image", '
            '"eval_script": "true"}'
        )
    task_path.write_text(task_json, encoding="utf-8")
    config_path = tmp_path / "sandbox.json"
    config_path.write_text("{not-json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
            "--task-file",
            str(task_path),
            "--sandbox-config",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("Error: Invalid sandbox configuration")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("module", ["agent_mbpp", "agent_swebench"])
@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_cli_reports_keyboard_interrupt_without_traceback(
    module: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_path = tmp_path / "task.json"
    if module == "agent_mbpp":
        task = {
            "task_id": 1,
            "task_definition": "Return one",
            "function_definition": "def one():",
        }
    else:
        task = {
            "instance_id": "project__repo-1",
            "problem_statement": "Fix it",
            "docker_image": "image",
            "eval_script": "true",
        }
    task_path.write_text(json.dumps(task), encoding="utf-8")
    stopped = []

    class InterruptingManager:
        """Simulate a terminal interrupt during MCP startup."""

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def list_tools(self):
            """Interrupt while the CLI waits for MCP discovery."""

            raise KeyboardInterrupt

        def stop(self) -> None:
            """Record that the CLI reached its cleanup block."""

            stopped.append(True)

    monkeypatch.setattr(manager_module, "SandboxManager", InterruptingManager)
    monkeypatch.setattr(
        sys,
        "argv",
        [module, "--task-file", str(task_path)],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module(module, run_name="__main__")

    captured = capsys.readouterr()
    assert exit_info.value.code == 130
    assert captured.err == "Interrupted.\n"
    assert "Traceback" not in captured.err
    assert stopped == [True]


@pytest.mark.parametrize("module", ["agent_mbpp", "agent_swebench"])
@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_cli_reports_task_deadline_without_traceback(
    module: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_path = tmp_path / "task.json"
    if module == "agent_mbpp":
        task = {
            "task_id": 1,
            "task_definition": "Return one",
            "function_definition": "def one():",
        }
    else:
        task = {
            "instance_id": "project__repo-1",
            "problem_statement": "Fix it",
            "docker_image": "image",
            "eval_script": "true",
        }
    task_path.write_text(json.dumps(task), encoding="utf-8")
    stopped = []

    class ExpiringManager:
        """Simulate expiration while the CLI waits for MCP discovery."""

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def list_tools(self):
            """Expire after the manager has been created."""

            raise deadline_module.TaskDeadlineExceeded("task deadline expired")

        def stop(self) -> None:
            """Record that the CLI reached its cleanup block."""

            stopped.append(True)

    monkeypatch.setattr(manager_module, "SandboxManager", ExpiringManager)
    monkeypatch.setattr(
        sys,
        "argv",
        [module, "--task-file", str(task_path)],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module(module, run_name="__main__")

    captured = capsys.readouterr()
    assert exit_info.value.code == 124
    assert captured.err == "Error: task deadline expired\n"
    assert "Traceback" not in captured.err
    assert stopped == [True]
