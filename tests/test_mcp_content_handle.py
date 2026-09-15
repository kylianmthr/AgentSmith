from types import SimpleNamespace

import pytest

from agent_smith.mcp_client.content import MCPContentHandle


class FakePortal:
    """Return predefined MCP results for synchronous handle tests."""

    def __init__(self) -> None:
        self.calls = []

    def call(self, function, *args):
        """Record a call and return data for the requested MCP method."""

        self.calls.append((function.__name__, args))
        if function.__name__ == "list_resources":
            resource = SimpleNamespace(
                uri="mbpp://task",
                name="get_task",
                description="Current MBPP task.",
            )
            return SimpleNamespace(resources=[resource])
        if function.__name__ == "list_prompts":
            argument = SimpleNamespace(
                name="style",
                required=False,
                description="Preferred response style.",
            )
            prompt = SimpleNamespace(
                name="get_prompt",
                description="Solver methodology.",
                arguments=[argument],
            )
            return SimpleNamespace(prompts=[prompt])
        if function.__name__ == "read_resource":
            return SimpleNamespace(
                contents=[SimpleNamespace(text="task contents")]
            )
        if function.__name__ == "get_prompt":
            message = SimpleNamespace(
                role=SimpleNamespace(value="user"),
                content=SimpleNamespace(text="solve carefully"),
            )
            return SimpleNamespace(
                description="Solver methodology.",
                messages=[message],
            )
        raise AssertionError(f"Unexpected call: {function.__name__}")


def make_session():
    """Return named callables matching the ClientSession API."""

    def list_resources():
        pass

    def list_prompts():
        pass

    def read_resource(_uri):
        pass

    def get_prompt(_name, _arguments=None):
        pass

    return SimpleNamespace(
        list_resources=list_resources,
        list_prompts=list_prompts,
        read_resource=read_resource,
        get_prompt=get_prompt,
    )


def test_content_documentation_describes_resources_and_prompts() -> None:
    handle = MCPContentHandle(FakePortal(), make_session(), True, True)

    documentation = handle.documentation()

    assert "MCP Resource mbpp://task" in documentation[0]
    assert "mcp_read_resource" in documentation[0]
    assert "MCP Prompt get_prompt" in documentation[1]
    assert "style (optional)" in documentation[1]


def test_content_wrappers_read_resources_and_render_prompts() -> None:
    portal = FakePortal()
    handle = MCPContentHandle(portal, make_session(), True, True)
    wrappers = handle.create_wrappers()

    resource = wrappers["mcp_read_resource"]("mbpp://task")
    prompt = wrappers["mcp_get_prompt"]("get_prompt", {"style": "short"})

    assert resource == "task contents"
    assert prompt == "Solver methodology.\n\nuser:\nsolve carefully"
    assert ("read_resource", ("mbpp://task",)) in portal.calls
    assert (
        "get_prompt",
        ("get_prompt", {"style": "short"}),
    ) in portal.calls


def test_content_handle_omits_unsupported_capabilities() -> None:
    handle = MCPContentHandle(FakePortal(), make_session(), False, False)

    assert handle.documentation() == []
    assert handle.create_wrappers() == {}
    with pytest.raises(RuntimeError, match="does not expose resources"):
        handle.read_resource("mbpp://task")
    with pytest.raises(RuntimeError, match="does not expose prompts"):
        handle.get_prompt("get_prompt")
