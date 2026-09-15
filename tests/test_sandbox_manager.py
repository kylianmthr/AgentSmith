import json
from pathlib import Path
from queue import Queue

import pytest

from agent_smith.models.sandbox_config import SandboxConfig
from agent_smith.sandbox import manager as manager_module
from agent_smith.sandbox.manager import SandboxManager, SandboxManagerError
from agent_smith.sandbox.worker import SandboxWorker, worker_entrypoint
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


@pytest.mark.parametrize(
    "message, exception_type, expected_code",
    [
        (
            {"type": "control_flow", "exception": "KeyboardInterrupt"},
            KeyboardInterrupt,
            None,
        ),
        (
            {"type": "control_flow", "exception": "SystemExit", "code": 7},
            SystemExit,
            7,
        ),
    ],
)
def test_manager_propagates_worker_control_flow(
    message: dict,
    exception_type: type[BaseException],
    expected_code: int | None,
) -> None:
    with pytest.raises(exception_type) as caught:
        SandboxManager._raise_control_flow(message)

    if exception_type is SystemExit:
        assert caught.value.code == expected_code


@pytest.mark.parametrize(
    "exception",
    [KeyboardInterrupt(), SystemExit(9)],
)
def test_worker_reports_control_flow_before_reraising(
    monkeypatch: pytest.MonkeyPatch,
    exception: BaseException,
) -> None:
    input_queue = Queue()
    output_queue = Queue()
    worker = SandboxWorker(
        input_queue=input_queue,
        output_queue=output_queue,
        authorized_imports=[],
        allowed_directories=["/tmp"],
        max_memory_mb=128,
        max_execution_time_seconds=1,
    )

    def interrupt(_python_code: str) -> None:
        raise exception

    monkeypatch.setattr(worker, "exec_with_timeout", interrupt)

    with pytest.raises(type(exception)):
        worker.handle_run("print('before interrupt')")

    message = output_queue.get(timeout=1)
    assert message["type"] == "control_flow"
    assert message["exception"] == type(exception).__name__
    assert message["code"] == getattr(exception, "code", None)


@pytest.mark.parametrize("exception", [KeyboardInterrupt(), SystemExit(4)])
def test_worker_entrypoint_stops_control_flow_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    exception: BaseException,
) -> None:
    cleanup_calls = []

    class InterruptingWorker:
        def __init__(self, **_kwargs) -> None:
            pass

        def start(self) -> None:
            pass

        def loop(self) -> None:
            raise exception

        def cleanup(self) -> None:
            cleanup_calls.append(True)

    monkeypatch.setattr(
        "agent_smith.sandbox.worker.SandboxWorker", InterruptingWorker
    )

    worker_entrypoint(
        Queue(),
        Queue(),
        authorized_imports=[],
        allowed_directories=["/tmp"],
        max_memory_mb=128,
        max_execution_time_seconds=1,
    )

    assert cleanup_calls == [True]


def test_real_worker_completes_ready_handshake() -> None:
    manager = SandboxManager(None)

    try:
        manager.start()
        result = manager.run("print('ready')")
    finally:
        manager.stop()

    assert result.success is True
    assert result.stdout == "ready\n"


def test_real_worker_allows_file_access_inside_allowed_directory(
    tmp_path: Path,
) -> None:
    allowed_directory = tmp_path / "allowed"
    allowed_directory.mkdir()
    config_path = tmp_path / "sandbox.json"
    config_path.write_text(
        json.dumps({"allowed_directories": [str(allowed_directory)]}),
        encoding="utf-8",
    )
    target = allowed_directory / "result.txt"
    manager = SandboxManager(config_path)

    try:
        result = manager.run(
            f"handle = open({str(target)!r}, 'w')\n"
            "handle.write('sandboxed')\n"
            "handle.close()\n"
            f"print(open({str(target)!r}).read())"
        )
    finally:
        manager.stop()

    assert result.success is True
    assert result.stdout == "sandboxed\n"
    assert target.read_text(encoding="utf-8") == "sandboxed"


def test_real_worker_rejects_file_access_outside_allowed_directory(
    tmp_path: Path,
) -> None:
    allowed_directory = tmp_path / "allowed"
    allowed_directory.mkdir()
    config_path = tmp_path / "sandbox.json"
    config_path.write_text(
        json.dumps({"allowed_directories": [str(allowed_directory)]}),
        encoding="utf-8",
    )
    outside_target = tmp_path / "outside.txt"
    manager = SandboxManager(config_path)

    try:
        result = manager.run(f"open({str(outside_target)!r}, 'w')")
    finally:
        manager.stop()

    assert result.success is False
    assert result.error is not None
    assert "File access outside allowed directories" in result.error
    assert not outside_target.exists()


@pytest.mark.parametrize(
    "python_code, error_text",
    [
        ("import os", "Unauthorized import: os"),
        ("eval('1 + 1')", "name 'eval' is not defined"),
        ("exec('print(1)')", "name 'exec' is not defined"),
        ("__import__('os')", "Unauthorized import: os"),
    ],
)
def test_real_worker_enforces_runtime_restrictions(
    python_code: str,
    error_text: str,
) -> None:
    manager = SandboxManager(None)

    try:
        result = manager.run(python_code)
    finally:
        manager.stop()

    assert result.success is False
    assert result.error is not None
    assert error_text in result.error


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
