import json
from pathlib import Path
from queue import Queue

import pytest

from agent_smith.models.sandbox_config import SandboxConfig
from agent_smith.sandbox import manager as manager_module
from agent_smith.sandbox.manager import SandboxManager, SandboxManagerError
from agent_smith.sandbox import worker as worker_module
from agent_smith.sandbox.worker import SandboxWorker
from agent_smith.sandbox.config_validator import (
    SandboxConfigError,
    SandboxConfigValidator,
)


class FakeProcess:
    def __init__(self) -> None:
        self.started = False
        self.alive = False
        self.terminated = False

    def start(self) -> None:
        self.started = True
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def kill(self) -> None:
        self.alive = False

    def join(self, timeout: float | None = None) -> None:
        pass


def install_fake_process(
    monkeypatch: pytest.MonkeyPatch,
    manager: SandboxManager,
) -> FakeProcess:
    process = FakeProcess()
    monkeypatch.setattr(manager_module, "Process", lambda *args, **kwargs: process)
    manager.input_queue = Queue()
    manager.output_queue = Queue()
    return process


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


def test_manager_consumes_ready_before_first_run_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SandboxManager(None)
    process = install_fake_process(monkeypatch, manager)
    manager.output_queue.put({"type": "ready"})
    manager.output_queue.put({"stdout": "ok\n", "success": True})

    result = manager.run("print('ok')")

    assert process.started is True
    assert result.success is True
    assert result.stdout == "ok\n"
    assert manager.input_queue.get_nowait() == {
        "type": "run",
        "code": "print('ok')",
    }


def test_real_worker_completes_ready_handshake() -> None:
    manager = SandboxManager(None)

    try:
        manager.start()
        result = manager.run("print('ready')")
    finally:
        manager.stop()

    assert result.success is True
    assert result.stdout == "ready\n"


def test_manager_rejects_worker_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SandboxManager(None)
    process = install_fake_process(monkeypatch, manager)
    manager.output_queue.put(
        {
            "type": "startup_error",
            "error": "MCP initialization failed",
        }
    )

    with pytest.raises(SandboxManagerError, match="MCP initialization failed"):
        manager.start()

    assert process.terminated is True
    assert manager.process is None


def test_manager_times_out_while_waiting_for_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SandboxManager(None)
    process = install_fake_process(monkeypatch, manager)
    manager.start_timeout = 0.01

    with pytest.raises(SandboxManagerError, match="worker startup timed out"):
        manager.start()

    assert process.terminated is True
    assert manager.process is None


def test_worker_applies_configured_memory_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []
    monkeypatch.setattr(
        worker_module.resource,
        "setrlimit",
        lambda resource_id, limits: calls.append((resource_id, limits)),
    )
    worker = SandboxWorker(
        input_queue=Queue(),
        output_queue=Queue(),
        authorized_imports=["math"],
        allowed_directories=["/testbed"],
        max_memory_mb=64,
        max_execution_time_seconds=2,
    )

    worker.apply_memory_limit()

    limit_bytes = 64 * 1024 * 1024
    assert calls == [
        (worker_module.resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    ]
