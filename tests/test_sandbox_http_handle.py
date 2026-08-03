from pathlib import Path

import pytest

from agent_smith.mcp_client.http_handle import HttpHandle, HttpHandleErr
from agent_smith.mcp_client import http_handle as http_handle_module


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.wait_calls = []

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None) -> None:
        self.wait_calls.append(timeout)


def test_start_http_server_adds_transport_host_port_and_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict = {}
    fake_process = FakeProcess()

    def fake_popen(command, cwd=None, start_new_session=False):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["start_new_session"] = start_new_session
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
    assert captured["start_new_session"] is True
    assert handle.http_server_process is fake_process


def test_start_http_server_defaults_to_mcp_path_when_url_has_no_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict = {}

    def fake_popen(command, cwd=None, start_new_session=False):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["start_new_session"] = start_new_session
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
    assert captured["start_new_session"] is True


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
    calls = {"connect": 0}

    def fake_connect_http():
        calls["connect"] += 1
        return "read_stream", "write_stream"

    monkeypatch.setattr(handle, "is_server_reachable", lambda: False)
    monkeypatch.setattr(handle, "connect_http", fake_connect_http)

    with pytest.raises(HttpHandleErr, match="missing args"):
        handle.handle_http()

    assert calls["connect"] == 0


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
    calls = {"connect": 0, "start": 0, "wait": 0}

    def fake_connect_http():
        calls["connect"] += 1
        return "read_stream", "write_stream"

    def fake_start_http_server():
        calls["start"] += 1

    def fake_wait_for_server():
        calls["wait"] += 1

    monkeypatch.setattr(handle, "is_server_reachable", lambda: False)
    monkeypatch.setattr(handle, "connect_http", fake_connect_http)
    monkeypatch.setattr(handle, "start_http_server", fake_start_http_server)
    monkeypatch.setattr(handle, "wait_for_server", fake_wait_for_server)

    assert handle.handle_http() == ("read_stream", "write_stream")
    assert calls == {"connect": 1, "start": 1, "wait": 1}
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
    assert process.wait_calls == [2]
    assert process.killed is False
    assert handle.http_server_process is None
    assert handle.http_launched is False
