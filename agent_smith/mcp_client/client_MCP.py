from typing import Any
from pydantic import ValidationError
from anyio.from_thread import start_blocking_portal
from mcp import ClientSession


from agent_smith.models.mcp_config import SandboxMCPConfig
from agent_smith.mcp_client.content import MCPContentHandle
from agent_smith.mcp_client.tools import ToolsHandle
from agent_smith.mcp_client.stdio_handle import StdioHandle
from agent_smith.mcp_client.http_handle import HttpHandle, HttpHandleErr


class SandboxMCPClientError(Exception):
    """Report an MCP client lifecycle or transport failure."""

    pass

class SandboxMCPClient:
    """Manage a synchronous facade over an asynchronous MCP session."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate transport configuration and initialize lifecycle state."""

        if not config:
            raise SandboxMCPClientError("MCP config cannot be empty")
        try:
            self.config = SandboxMCPConfig.model_validate(config).model_dump()
        except ValidationError as error:
            raise SandboxMCPClientError(error) from error
        self.portal_context = None
        self.portal = None
        self.stdio_handle = None
        self.http_handle = None
        self.session_context = None
        self.session: ClientSession | None = None
        self.tools: ToolsHandle | None = None
        self.content: MCPContentHandle | None = None

    def start(self, allowed_directories: list[str]) -> None:
        """Start the configured transport and initialize the MCP session."""

        if self.session is not None:
            return
        try:
            self.portal_context = start_blocking_portal()
            self.portal = self.portal_context.__enter__()
            read_stream, write_stream = self.get_streams_from_transport()
            self.session_context = self.portal.wrap_async_context_manager(
                ClientSession(read_stream, write_stream)
            )
            self.session = self.session_context.__enter__()
            initialization = self.portal.call(self.session.initialize)
            if self.portal is None or self.session is None:
                raise RuntimeError("MCP client is not started")
            self.tools = ToolsHandle(self.portal, self.session, allowed_directories)
            capabilities = initialization.capabilities
            self.content = MCPContentHandle(
                self.portal,
                self.session,
                supports_resources=capabilities.resources is not None,
                supports_prompts=capabilities.prompts is not None,
            )
        except Exception as e:
            self.stop()
            raise SandboxMCPClientError(f"Error Setting up the MCP Client: {e}")


    def get_streams_from_transport(self) -> tuple[Any, Any]:
        """Open streams for the configured MCP transport."""

        transport = self.config["transport"]
        if self.portal is None:
            raise SandboxMCPClientError("Portal is not started")
        if transport == "stdio":
            self.stdio_handle = StdioHandle(self.portal, self.config)
            return self.stdio_handle.handle_stdio()
        if transport == "http":
            try:
                self.http_handle = HttpHandle(self.portal, self.config)
                return self.http_handle.handle_http()
            except HttpHandleErr as e:
                raise SandboxMCPClientError(f"Error in Transport: {e}")

        raise SandboxMCPClientError(f"Unsupported MCP transport: {transport}")


    def stop(self) -> None:
        """Close the MCP session, transport, and blocking portal."""

        if self.session_context is not None:
            self.session_context.__exit__(None, None, None)

        if self.stdio_handle is not None:
            self.stdio_handle.stop()

        if self.http_handle is not None:
            self.http_handle.stop()

        if self.portal_context is not None:
            self.portal_context.__exit__(None, None, None)

        self.session = None
        self.session_context = None
        self.tools = None
        self.content = None
        self.portal = None
        self.portal_context = None
