import sys
from pathlib import Path

from agent_smith.mcp_client.client_MCP import SandboxMCPClient


def test_mcp_client_connects_to_stdio_server_and_lists_tools() -> None:
    client = SandboxMCPClient(
        {
            "command": sys.executable,
            "args": ["mcp_tools_mbpp.py"],
            "cwd": str(Path(__file__).resolve().parents[1]),
        }
    )

    try:
        client.start()

        assert "run_tests" in client.tools.list_tools()

    finally:
        client.stop()
