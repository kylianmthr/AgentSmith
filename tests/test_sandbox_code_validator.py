import pytest

from agent_smith.sandbox.code_validator import (
    SandboxCodeValidator,
    SandboxCodeValidatorErr,
)


AUTHORIZED_IMPORTS = [
    "math",
    "json",
    "collections",
    "collections.*",
]


def validate(python_code: str) -> None:
    SandboxCodeValidator.validate(python_code, AUTHORIZED_IMPORTS)


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
def test_validate_rejects_unauthorized_imports(python_code: str) -> None:
    with pytest.raises(SandboxCodeValidatorErr, match="Unauthorized import"):
        validate(python_code)


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
def test_validate_rejects_forbidden_imports_even_when_authorized(
    python_code: str,
    authorized_imports: list[str],
) -> None:
    with pytest.raises(SandboxCodeValidatorErr, match="Unauthorized import"):
        SandboxCodeValidator.validate(python_code, authorized_imports)


@pytest.mark.parametrize(
    "python_code",
    [
        "eval('1 + 1')",
        "exec('print(1)')",
        "open('/tmp/file.txt')",
        "__import__('os')",
    ],
)
def test_validate_rejects_forbidden_builtin_calls(python_code: str) -> None:
    with pytest.raises(SandboxCodeValidatorErr, match="Forbidden function call"):
        validate(python_code)
