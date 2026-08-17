from typing import Any
from mcp.client.stdio import StdioServerParameters, stdio_client
from anyio.from_thread import BlockingPortal
import os


class StdioHandle:
    def __init__(self, portal: BlockingPortal, config: dict[str, Any]) -> None:
        self.portal = portal
        self.config = config
        self.stdio_context = None

    def handle_stdio(self) -> tuple[Any, Any]:
        server = StdioServerParameters(
            command=self.config["command"],
            args=self.config.get("args", []),
            cwd=self.config.get("cwd"),
            env=os.environ.copy()
        )
        self.stdio_context = self.portal.wrap_async_context_manager(
            stdio_client(server)
        )
        read_stream, write_stream = self.stdio_context.__enter__()
        return (read_stream, write_stream)

    def stop(self) -> None:
        if self.stdio_context is not None:
            self.stdio_context.__exit__(None, None, None)
            self.stdio_context = None
