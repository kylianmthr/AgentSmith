from anyio.from_thread import BlockingPortal
from mcp import ClientSession
from typing import Callable

class ToolsHandle:
    def __init__(self, portal: BlockingPortal, session: ClientSession) -> None:
        self.portal = portal
        self.session = session

    def list_tools(self) -> list[str]:
        result = self.portal.call(self.session.list_tools)
        return [tool.name for tool in result.tools]

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call one MCP tool."""
        result = self.portal.call(
            self.session.call_tool,
            name,
            arguments,
        )
        return "\n".join(
            content.text
            for content in result.content
            if content.type == "text"
        )


    def create_tool_wrappers(self) -> dict[str, object]:
        """Return Python callables to inject into worker namespace."""
        tools = self.list_tools()
        wrappers = {}
        for tool in tools:
            wrappers[tool] = self.create_single_wrapper(tool)
        print(wrappers)
        return wrappers

    def create_single_wrapper(self, tool: str) -> Callable:
        def wrapper(**kwargs):
            return self.call_tool(tool, kwargs)
        return wrapper

