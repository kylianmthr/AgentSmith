from contextlib import AsyncExitStack
from typing import Any

from anyio.from_thread import start_blocking_portal
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

class SandboxMCPClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.portal_context = None
        self.portal = None
        self.conn: AsyncExitStack | None = None
        self.session: ClientSession | None = None

    def start(self) -> None:
        """Connect to the MCP server."""
        self.portal_context = start_blocking_portal()
        self.portal = self.portal_context.__enter__()
        self.portal.call(self.connect)

    async def connect(self) -> None:
        self.conn = AsyncExitStack()

        server = StdioServerParameters(
            command=self.config["command"],
            args=self.config.get("args", []),
            cwd=self.config.get("cwd"),
        )
        read_stream, write_stream = await self.conn.enter_async_context(
            stdio_client(server)
        )
        self.session = await self.conn.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self.session.initialize()

    def stop(self) -> None:
        """Close connection / process."""

    def list_tools(self) -> list[str]:
        """Return available tool names."""

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call one MCP tool."""

    def create_tool_wrappers(self) -> dict[str, object]:
        """Return Python callables to inject into worker namespace."""
        