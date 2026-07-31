from pathlib import Path

import pytest

from agent_smith.mcp_client.http_handle import HttpHandle, HttpHandleErr
from agent_smith.mcp_client import http_handle as http_handle_module


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_start_http_server_adds_transport_host_port_and_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict = {}
    fake_process = FakeProcess()

    def fake_popen(command, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd
        return fake_process

    monkeypatch.setattr(http_handle_module.subprocess, "Popen", fake_popen)

    handle = HttpHandle(
        portal=None,  # start_http_server does not use the portal
        config={
            "transport": "http",
            "url": "http://127.0.0.1:9010/custom-mcp",
            "command": "python3",
            "args": ["mcp_tools_mbpp.py", "--task", "task.json"],
            "cwd": tmp_path,
        },
    )

    handle.start_http_server()

    assert captured["cwd"] == tmp_path
    assert captured["command"] == [
        "python3",
        "mcp_tools_mbpp.py",
        "--task",
        "task.json",
        "--transport",
        "http",
        "--host",
        "127.0.0.1",
        "--port",
        "9010",
        "--path",
        "/custom-mcp",
    ]
    assert handle.http_server_process is fake_process


def test_start_http_server_defaults_to_mcp_path_when_url_has_no_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict = {}

    def fake_popen(command, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd
        return FakeProcess()

    monkeypatch.setattr(http_handle_module.subprocess, "Popen", fake_popen)

    handle = HttpHandle(
        portal=None,
        config={
            "transport": "http",
            "url": "http://127.0.0.1:9011",
            "command": "python3",
            "args": ["mcp_tools_mbpp.py", "--task", "task.json"],
            "cwd": tmp_path,
        },
    )

    handle.start_http_server()

    assert captured["command"][-2:] == ["--path", "/mcp"]


def test_start_http_server_rejects_url_without_hostname() -> None:
    handle = HttpHandle(
        portal=None,
        config={
            "transport": "http",
            "url": "http:///mcp",
            "command": "python3",
            "args": ["mcp_tools_mbpp.py"],
        },
    )

    with pytest.raises(HttpHandleErr, match="hostname"):
        handle.start_http_server()


def test_start_http_server_rejects_url_without_port() -> None:
    handle = HttpHandle(
        portal=None,
        config={
            "transport": "http",
            "url": "http://127.0.0.1/mcp",
            "command": "python3",
            "args": ["mcp_tools_mbpp.py"],
        },
    )

    with pytest.raises(HttpHandleErr, match="port"):
        handle.start_http_server()


def test_handle_http_without_autostart_args_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = HttpHandle(
        portal=None,
        config={
            "transport": "http",
            "url": "http://127.0.0.1:9012/mcp",
            "args": [],
        },
    )

    monkeypatch.setattr(
        handle,
        "connect_http",
        lambda: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )

    with pytest.raises(HttpHandleErr, match="Need args"):
        handle.handle_http()


def test_handle_http_autostarts_then_returns_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = HttpHandle(
        portal=None,
        config={
            "transport": "http",
            "url": "http://127.0.0.1:9013/mcp",
            "command": "python3",
            "args": ["mcp_tools_mbpp.py", "--task", "task.json"],
        },
    )
    calls = {"connect": 0, "start": 0}

    def fake_connect_http():
        calls["connect"] += 1
        if calls["connect"] == 1:
            raise RuntimeError("connection refused")
        return "read_stream", "write_stream"

    def fake_start_http_server():
        calls["start"] += 1

    monkeypatch.setattr(handle, "connect_http", fake_connect_http)
    monkeypatch.setattr(handle, "start_http_server", fake_start_http_server)
    monkeypatch.setattr(http_handle_module.time, "sleep", lambda _: None)

    assert handle.handle_http() == ("read_stream", "write_stream")
    assert calls == {"connect": 2, "start": 1}
    assert handle.http_launched is True


def test_stop_terminates_only_autostarted_process() -> None:
    handle = HttpHandle(portal=None, config={})
    process = FakeProcess()
    handle.http_server_process = process

    handle.stop()
    assert process.terminated is False

    handle.http_launched = True
    handle.stop()
    assert process.terminated is True
