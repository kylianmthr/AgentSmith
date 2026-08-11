import json
from pathlib import Path

import pytest

from agent_smith.models.sandbox_config import SandboxConfig
from agent_smith.sandbox.manager import SandboxManager
from agent_smith.sandbox.config_validator import (
    SandboxConfigError,
    SandboxConfigValidator,
)


def test_validator_uses_default_config_when_path_is_none() -> None:
    config = SandboxConfigValidator.load(None)

    assert config == SandboxConfig()


def test_validator_loads_valid_json_config(tmp_path: Path) -> None:
    config_path = tmp_path / "sandbox.json"
    config_path.write_text(
        json.dumps(
            {
                "authorized_imports": ["math", "json"],
                "allowed_directories": ["/tmp/agent"],
                "max_execution_time_seconds": 10,
                "max_memory_mb": 128,
            }
        ),
        encoding="utf-8",
    )

    config = SandboxConfigValidator.load(config_path)

    assert config.authorized_imports == ["math", "json"]
    assert config.allowed_directories == ["/tmp/agent"]
    assert config.max_execution_time_seconds == 10
    assert config.max_memory_mb == 128


def test_validator_rejects_missing_config_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(SandboxConfigError, match="Sandbox configuration not found"):
        SandboxConfigValidator.load(missing_path)


def test_validator_rejects_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.json"
    config_path.write_text("not valid JSON", encoding="utf-8")

    with pytest.raises(SandboxConfigError, match="Invalid sandbox configuration"):
        SandboxConfigValidator.load(config_path)


def test_validator_rejects_invalid_config_schema(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid-schema.json"
    config_path.write_text(
        json.dumps({"authorized_imports": "math"}),
        encoding="utf-8",
    )

    with pytest.raises(SandboxConfigError, match="Invalid sandbox configuration"):
        SandboxConfigValidator.load(config_path)


@pytest.mark.parametrize(
    "authorized_imports",
    [
        ["socket"],
        ["urllib"],
        ["urllib.request"],
        ["httpx"],
        ["os"],
        ["sys"],
        ["pathlib"],
    ],
)
def test_validator_rejects_imports_outside_safe_imports(
    tmp_path: Path,
    authorized_imports: list[str],
) -> None:
    config_path = tmp_path / "invalid-imports.json"
    config_path.write_text(
        json.dumps({"authorized_imports": authorized_imports}),
        encoding="utf-8",
    )

    with pytest.raises(SandboxConfigError, match="Invalid sandbox configuration"):
        SandboxConfigValidator.load(config_path)


@pytest.mark.parametrize(
    "invalid_config",
    [
        {"allowed_directories": []},
        {"max_execution_time_seconds": 0},
        {"max_execution_time_seconds": 901},
        {"max_memory_mb": 63},
        {"max_memory_mb": 4097},
    ],
)
def test_validator_rejects_invalid_limits(
    tmp_path: Path,
    invalid_config: dict,
) -> None:
    config_path = tmp_path / "invalid-limits.json"
    config_path.write_text(json.dumps(invalid_config), encoding="utf-8")

    with pytest.raises(SandboxConfigError, match="Invalid sandbox configuration"):
        SandboxConfigValidator.load(config_path)


def test_manager_exposes_validated_config(tmp_path: Path) -> None:
    config_path = tmp_path / "sandbox.json"
    config_path.write_text(
        json.dumps(
            {
                "max_execution_time_seconds": 5,
                "max_memory_mb": 64,
            }
        ),
        encoding="utf-8",
    )

    manager = SandboxManager(config_path)

    assert isinstance(manager.config, SandboxConfig)
    assert manager.config.max_execution_time_seconds == 5
    assert manager.config.max_memory_mb == 64


def test_manager_applies_worker_memory_limit(tmp_path: Path) -> None:
    config_path = tmp_path / "sandbox.json"
    config_path.write_text(
        json.dumps(
            {
                "max_execution_time_seconds": 2,
                "max_memory_mb": 64,
            }
        ),
        encoding="utf-8",
    )

    manager = SandboxManager(config_path)

    try:
        result = manager.run("x = 'a' * (1024 * 1024 * 512)")
    finally:
        manager.stop()

    assert result.success is False
    assert result.error is not None
