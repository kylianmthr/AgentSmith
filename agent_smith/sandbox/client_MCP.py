from typing import Any

from anyio.from_thread import start_blocking_portal
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

class SandboxMCPClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.portal_context = None
        self.portal = None
        self.stdio_context = None
        self.session_context = None
        self.session: ClientSession | None = None

    def start(self) -> None:
        # Démarre un portal pour appeler du code async depuis ce code sync.
        self.portal_context = start_blocking_portal()
        self.portal = self.portal_context.__enter__()

        # Décrit la commande qui lancera le serveur MCP en mode stdio.
        server = StdioServerParameters(
            command=self.config["command"], # python3
            args=self.config.get("args", []), # mcp_tools_mbpp.py --task task.json par ex
            cwd=self.config.get("cwd"), # le path de lancement genre /home/user/AgentSmith
        )

        # Lance le serveur MCP et ouvre les flux read/write avec lui.
        self.stdio_context = self.portal.wrap_async_context_manager(
            stdio_client(server)
        )
        read_stream, write_stream = self.stdio_context.__enter__()

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

    def stop(self) -> None:
        """Close connection / process."""

    def list_tools(self) -> list[str]:
        """Return available tool names."""

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call one MCP tool."""

    def create_tool_wrappers(self) -> dict[str, object]:
        """Return Python callables to inject into worker namespace."""
        