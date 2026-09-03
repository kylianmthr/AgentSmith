import pytest
from queue import Queue

from agent_smith.sandbox.code_validator import (
    SandboxCodeValidator,
    SandboxCodeValidatorErr,
)
from agent_smith.sandbox.worker import SandboxWorker


AUTHORIZED_IMPORTS = [
    "math",
    "json",
    "collections",
    "collections.*",
]


def validate(python_code: str) -> None:
    SandboxCodeValidator.validate(python_code, AUTHORIZED_IMPORTS)


def execute_in_worker(
    python_code: str,
    authorized_imports: list[str] | None = None,
) -> dict:
    """Exercise runtime restrictions without spawning a child process."""
    output_queue = Queue()
    worker = SandboxWorker(
        input_queue=Queue(),
        output_queue=output_queue,
        authorized_imports=authorized_imports or AUTHORIZED_IMPORTS,
        allowed_directories=["/testbed"],
        max_memory_mb=512,
        max_execution_time_seconds=5,
    )
    worker.handle_run(python_code)
    return output_queue.get_nowait()


def test_validate_accepts_valid_python_code_without_imports() -> None:
    validate("result = 1 + 2\nprint(result)")


def test_validate_rejects_invalid_python_syntax() -> None:
    with pytest.raises(SandboxCodeValidatorErr, match="Invalid Python syntax"):
        validate("def broken(:\n    pass")


@pytest.mark.parametrize(
    "python_code",
    [
        "import math\nresult = math.sqrt(9)",
        "from math import sqrt\nresult = sqrt(9)",
        "import json\nresult = json.dumps({'ok': True})",
        "import collections.abc\nresult = collections.abc.Sequence",
    ],
)
def test_validate_accepts_authorized_imports(python_code: str) -> None:
    validate(python_code)


@pytest.mark.parametrize(
    "python_code",
    [
        "import os\nresult = os.getcwd()",
        "from pathlib import Path\nresult = Path('.')",
        "import subprocess\nresult = subprocess.run(['ls'])",
    ],
)
def test_worker_rejects_unauthorized_imports(python_code: str) -> None:
    result = execute_in_worker(python_code)

    assert result["success"] is False
    assert "Unauthorized import" in result["error"]


@pytest.mark.parametrize(
    "python_code, authorized_imports",
    [
        ("import socket", ["socket"]),
        ("import urllib.request", ["urllib.*"]),
        ("import http.server", ["http.*"]),
        ("import os.path", ["os.*"]),
        ("import pathlib", ["pathlib"]),
        ("import sys", ["sys"]),
    ],
)
def test_worker_rejects_forbidden_imports_even_when_authorized(
    python_code: str,
    authorized_imports: list[str],
) -> None:
    result = execute_in_worker(python_code, authorized_imports)

    assert result["success"] is False
    assert "Unauthorized import" in result["error"]


@pytest.mark.parametrize(
    "python_code",
    [
        "eval('1 + 1')",
        "exec('print(1)')",
        "open('/tmp/file.txt')",
        "__import__('os')",
    ],
)
def test_worker_rejects_forbidden_builtin_calls(python_code: str) -> None:
    result = execute_in_worker(python_code)

    assert result["success"] is False
    assert result["error"]
