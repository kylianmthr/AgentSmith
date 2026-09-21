from typing import Any, Callable

from anyio.from_thread import BlockingPortal
from mcp import ClientSession


class MCPContentHandle:
    """Expose MCP resources and prompts through synchronous wrappers."""

    def __init__(
        self,
        portal: BlockingPortal,
        session: ClientSession,
        supports_resources: bool,
        supports_prompts: bool,
    ) -> None:
        """Store the MCP session and its advertised capabilities."""

        self.portal = portal
        self.session = session
        self.supports_resources = supports_resources
        self.supports_prompts = supports_prompts

    @staticmethod
    def _render_content(content: Any) -> str:
        """Convert an MCP content item to readable text."""

        text = getattr(content, "text", None)
        if text is not None:
            return text
        blob = getattr(content, "blob", None)
        if blob is not None:
            return blob
        resource = getattr(content, "resource", None)
        if resource is not None:
            return MCPContentHandle._render_content(resource)
        if hasattr(content, "model_dump_json"):
            return content.model_dump_json()
        return str(content)

    def list_resources(self, mode: str = "uri") -> list[Any]:
        """List advertised resources as URIs, documentation, or models."""

        if not self.supports_resources:
            return []
        resources = self.portal.call(self.session.list_resources).resources
        if mode == "uri":
            return [str(resource.uri) for resource in resources]
        if mode == "prompt":
            documentation = []
            for resource in resources:
                lines = [f"MCP Resource {resource.uri}:\n"]
                if resource.name:
                    lines.append(f"Name: {resource.name}\n")
                if resource.description:
                    lines.append(f"Description: {resource.description}\n")
                lines.append(
                    "Read: mcp_read_resource(uri: string) -> str\n"
                )
                documentation.append("".join(lines))
            return documentation
        if mode == "full":
            return list(resources)
        raise ValueError(f"Unknown list_resources mode: {mode}")

    def list_prompts(self, mode: str = "name") -> list[Any]:
        """List advertised prompts as names, documentation, or models."""

        if not self.supports_prompts:
            return []
        prompts = self.portal.call(self.session.list_prompts).prompts
        if mode == "name":
            return [prompt.name for prompt in prompts]
        if mode == "prompt":
            documentation = []
            for prompt in prompts:
                lines = [f"MCP Prompt {prompt.name}:\n"]
                if prompt.description:
                    lines.append(f"Description: {prompt.description}\n")
                lines.append(
                    "Call: mcp_get_prompt(name: string, "
                    "arguments: dict | None = None) -> str\n"
                )
                if prompt.arguments:
                    lines.append("Prompt arguments:\n")
                    for argument in prompt.arguments:
                        required = "required" if argument.required else "optional"
                        description = (
                            f": {argument.description}"
                            if argument.description
                            else ""
                        )
                        lines.append(
                            f"- {argument.name} ({required}){description}\n"
                        )
                documentation.append("".join(lines))
            return documentation
        if mode == "full":
            return list(prompts)
        raise ValueError(f"Unknown list_prompts mode: {mode}")

    def read_resource(self, uri: str) -> str:
        """Read one MCP resource and return its textual contents."""

        if not self.supports_resources:
            raise RuntimeError("The MCP server does not expose resources")
        result = self.portal.call(self.session.read_resource, uri)
        return "\n".join(self._render_content(item) for item in result.contents)

    def get_prompt(
        self,
        name: str,
        arguments: dict[str, str] | None = None,
    ) -> str:
        """Render one MCP prompt as role-prefixed messages."""

        if not self.supports_prompts:
            raise RuntimeError("The MCP server does not expose prompts")
        result = self.portal.call(self.session.get_prompt, name, arguments)
        messages = []
        if result.description:
            messages.append(result.description)
        for message in result.messages:
            role = getattr(message.role, "value", message.role)
            messages.append(
                f"{role}:\n{self._render_content(message.content)}"
            )
        return "\n\n".join(messages)

    def create_wrappers(self) -> dict[str, Callable[..., str]]:
        """Create wrappers only for capabilities declared by the server."""

        wrappers: dict[str, Callable[..., str]] = {}
        if self.supports_resources:
            wrappers["mcp_read_resource"] = self.read_resource
        if self.supports_prompts:
            wrappers["mcp_get_prompt"] = self.get_prompt
        return wrappers

    def documentation(self) -> list[str]:
        """Return resource and prompt documentation for the agent manual."""

        return self.list_resources("prompt") + self.list_prompts("prompt")
