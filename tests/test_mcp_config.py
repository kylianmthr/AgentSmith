from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_smith.models.mcp_config import SandboxMCPConfig


def test_stdio_config_requires_args() -> None:
    with pytest.raises(ValidationError, match="Args are required"):
        SandboxMCPConfig(transport="stdio", command="python3", args=[])


def test_stdio_config_accepts_command_args_and_cwd(tmp_path: Path) -> None:
    config = SandboxMCPConfig(
        transport="stdio",
        command="python3",
        args=["mcp_tools_mbpp.py", "--task", "task.json"],
        cwd=tmp_path,
    )

    assert config.transport == "stdio"
    assert config.command == "python3"
    assert config.args == ["mcp_tools_mbpp.py", "--task", "task.json"]
    assert config.cwd == tmp_path


def test_http_config_requires_url() -> None:
    with pytest.raises(ValidationError, match="URL is required"):
        SandboxMCPConfig(transport="http", url=None)


def test_http_config_accepts_url_without_args_for_existing_server() -> None:
    config = SandboxMCPConfig(
        transport="http",
        url="http://127.0.0.1:9000/mcp",
    )

    assert config.transport == "http"
    assert config.url == "http://127.0.0.1:9000/mcp"
    assert config.args == []


def test_http_config_accepts_url_with_command_args_for_autostart(
    tmp_path: Path,
) -> None:
    config = SandboxMCPConfig(
        transport="http",
        url="http://127.0.0.1:9000/mcp",
        command="python3",
        args=["mcp_tools_mbpp.py", "--task", "task.json"],
        cwd=tmp_path,
    )

    assert config.transport == "http"
    assert config.url == "http://127.0.0.1:9000/mcp"
    assert config.command == "python3"
    assert config.args == ["mcp_tools_mbpp.py", "--task", "task.json"]
    assert config.cwd == tmp_path


def test_rejects_unknown_transport() -> None:
    with pytest.raises(ValidationError):
        SandboxMCPConfig(transport="websocket")
