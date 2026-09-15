import os
import sys
from pathlib import Path

import pytest

from agent_smith.mcp_client.client_MCP import SandboxMCPClient


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_MCP_INTEGRATION") != "1",
    reason="set RUN_MCP_INTEGRATION=1 to start a real stdio MCP server",
)
def test_mcp_client_connects_to_stdio_server_and_discovers_capabilities() -> None:
    client = SandboxMCPClient(
        {
            "command": sys.executable,
            "args": [
                "mcp_tools_mbpp.py",
                "--task",
                "agent_smith/sandbox/fake_task.json",
            ],
            "cwd": str(Path(__file__).resolve().parents[1]),
        }
    )

    try:
        client.start(allowed_directories=["/testbed", "/tmp/agent"])

        assert "run_tests" in client.tools.list_tools()
        assert "mbpp://task" in client.content.list_resources()
        assert "get_prompt" in client.content.list_prompts()

        wrappers = client.content.create_wrappers()
        assert "TASK DEFINITION" in wrappers["mcp_read_resource"]("mbpp://task")
        assert "MBPP task" in wrappers["mcp_get_prompt"]("get_prompt")

    finally:
        client.stop()
