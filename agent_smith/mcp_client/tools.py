from anyio.from_thread import BlockingPortal
from mcp import ClientSession
from typing import Callable, Any

class ToolsHandle:
    def __init__(self, portal: BlockingPortal, session: ClientSession) -> None:
        self.portal = portal
        self.session = session

    def list_tools(self, mode: str = "name") -> list[Any]:
        result = self.portal.call(self.session.list_tools)
        if mode == "name":
            return [tool.name for tool in result.tools]
        elif mode == "prompt":
            res = []
            for tool in result.tools:
                properties = tool.inputSchema.get("properties", {})
                func_def = []
                func_def.append(f"Func {tool.name}:\n")
                func_def.append(f"def {tool.name}(")
                for i, (arg_name, arg_schema) in enumerate(properties.items()):
                    arg_type = arg_schema.get("type", "")
                    func_def.append(f"{arg_name}: {arg_type}")
                    if i < len(properties) - 1:
                        func_def.append(", ")
                return_type = None
                if tool.outputSchema:
                    return_data = tool.outputSchema.get("result")
                    if return_data:
                        return_type = return_data.get("type")
                if return_type:
                    func_def.append(f") -> {return_type}:")
                else:
                    func_def.append("):")
                res.append("".join(func_def))
            return res
        elif mode == "full":
            return [tool for tool in result.tools]
        return [tool for tool in result.tools]


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
        tools = self.list_tools("full")
        wrappers = {}
        for tool in tools:
            wrappers[tool.name] = self.create_single_wrapper(tool)
        return wrappers

    def create_single_wrapper(self, tool: Any) -> Callable:
        def wrapper(*args, **kwargs):
            properties = tool.inputSchema.get("properties", {})
            names = [name for name in properties]
            named_args = {}
            if len(args) > len(names):
                raise TypeError(f"Too many args in tool {tool.name}: {args}")
            for i, arg in enumerate(args):
                named_args[names[i]] = arg
            if kwargs:
                for k, v in kwargs.items():
                    if k in named_args:
                        raise TypeError(
                            f"{tool.name} has multiple values for arg {k}"
                        )
                    named_args[k] = v
            return self.call_tool(tool.name, named_args)
        return wrapper
