from types import SimpleNamespace
from pathlib import Path

from agent_smith.mcp_client import client_MCP as client_module
from agent_smith.mcp_client.client_MCP import SandboxMCPClient


def test_mcp_client_initializes_session_and_lists_tools(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.initialized = False

        def initialize(self) -> None:
            self.initialized = True

        def list_tools(self):
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="run_tests",
                        description="Run tests",
                        inputSchema={"properties": {}},
                    )
                ]
            )

    session = FakeSession()

    class FakeSessionContext:
        def __enter__(self):
            return session

        def __exit__(self, *_args):
            return None

    class FakePortal:
        def wrap_async_context_manager(self, _context):
            return FakeSessionContext()

        def call(self, function, *args):
            return function(*args)

    class FakePortalContext:
        def __enter__(self):
            return FakePortal()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        client_module,
        "start_blocking_portal",
        lambda: FakePortalContext(),
    )
    monkeypatch.setattr(
        client_module,
        "ClientSession",
        lambda _read, _write: object(),
    )

    client = SandboxMCPClient(
        {
            "command": "python",
            "args": ["mcp_tools_mbpp.py"],
            "cwd": str(Path(__file__).resolve().parents[1]),
        }
    )
    monkeypatch.setattr(
        client,
        "get_streams_from_transport",
        lambda: (object(), object()),
    )

    try:
        client.start(allowed_directories=["/testbed", "/tmp/agent"])

        assert session.initialized is True
        assert "run_tests" in client.tools.list_tools()

    finally:
        client.stop()
