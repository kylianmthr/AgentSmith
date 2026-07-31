from typing import Any


from agent_smith.models.mcp_config import SandboxMCPConfig
from pydantic import ValidationError
from anyio.from_thread import start_blocking_portal
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

class SandboxMCPClientError(Exception):
    pass

class SandboxMCPClient:
    def __init__(self, config: dict[str, Any]) -> None:
        if not config:
            raise SandboxMCPClientError("MCP config cannot be empty")
        try:
            self.config = SandboxMCPConfig.model_validate(config).model_dump()
        except ValidationError as error:
            raise SandboxMCPClientError(error) from error
        self.portal_context = None
        self.portal = None
        self.stdio_context = None
        self.http_context = None
        self.session_context = None
        self.session: ClientSession | None = None

    def start(self) -> None:
        if self.session is not None:
            return
        try:
            # Démarre un portal pour appeler du code async depuis ce code sync.
            self.portal_context = start_blocking_portal()
            self.portal = self.portal_context.__enter__()
            read_stream, write_stream = self.get_streams_from_transport()

            # Crée une session MCP au-dessus des flux read/write.
            self.session_context = self.portal.wrap_async_context_manager(
                ClientSession(read_stream, write_stream)
            )
            self.session = self.session_context.__enter__()

            # on initialise tout ça
            self.portal.call(self.session.initialize)

            # en gros:
            # portal_context = permet d'appeler du code async depuis notre code normal
            # stdio_context = lance le serveur MCP et ouvre la communication avec lui
            # session_context = utilise cette communication pour envoyer des requêtes MCP
        except Exception as e:
            self.stop()
            raise SandboxMCPClientError(f"Error Setting up the MCP Client: {e}")


    def get_streams_from_transport(self) -> tuple[Any, Any]:
        if self.portal is None:
            raise SandboxMCPClientError("Portal is not started")
        transport = self.config["transport"]
        if transport == "stdio":
            server = StdioServerParameters(
                command=self.config["command"],
                args=self.config.get("args", []),
                cwd=self.config.get("cwd"),
            )
            self.stdio_context = self.portal.wrap_async_context_manager(
                stdio_client(server)
            )
            read_stream, write_stream = self.stdio_context.__enter__()
            return (read_stream, write_stream)

        if transport == "http":
            url = self.config.get("url")
            if not url:
                raise SandboxMCPClientError("HTTP MCP transport requires a url")
            self.http_context = self.portal.wrap_async_context_manager(
                streamable_http_client(url)
            )

            streams = self.http_context.__enter__()
            read_stream, write_stream = streams[:2]
            return read_stream, write_stream

        raise SandboxMCPClientError(f"Unsupported MCP transport: {transport}")


    def stop(self) -> None:
        if self.session_context is not None:
            self.session_context.__exit__(None, None, None)

        if self.stdio_context is not None:
            self.stdio_context.__exit__(None, None, None)

        if self.http_context is not None:
            self.http_context.__exit__(None, None, None)

        if self.portal_context is not None:
            self.portal_context.__exit__(None, None, None)

        self.session = None
        self.session_context = None
        self.stdio_context = None
        self.http_context = None
        self.portal = None
        self.portal_context = None

    # Fonction test pour lister les tools, je l'ai pas suppr ça peut peut être servir pour SWE BENCH
    def list_tools(self) -> list[str]:
        if self.portal is None or self.session is None:
            raise RuntimeError("MCP client is not started")

        result = self.portal.call(self.session.list_tools)
        return [tool.name for tool in result.tools]

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call one MCP tool."""
        if self.portal is None or self.session is None:
            raise RuntimeError("MCP client is not started")
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
        return {"run_tests": self.run_tests_wrapper}
        
    def run_tests_wrapper(self, code):
        return self.call_tool("run_tests", {"code": code})
