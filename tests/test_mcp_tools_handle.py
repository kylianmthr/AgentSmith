from types import SimpleNamespace

import pytest

from agent_smith.mcp_client.tools import ToolsHandle


def make_tool(
    name: str = "run_tests",
    properties: dict | None = None,
    description: str = "Run tests against a candidate solution.",
):
    if properties is None:
        properties = {
            "code": {
                "type": "string",
                "description": "The complete Python source of your solution.",
            }
        }

    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema={"properties": properties},
        outputSchema=None,
    )


def make_tools_handle_for_wrapper_tests():
    handle = ToolsHandle.__new__(ToolsHandle)
    calls = []

    def fake_call_tool(name: str, arguments: dict):
        calls.append((name, arguments))
        return "ok"

    handle.call_tool = fake_call_tool
    return handle, calls


def test_dynamic_wrapper_accepts_positional_argument() -> None:
    handle, calls = make_tools_handle_for_wrapper_tests()
    wrapper = handle.create_single_wrapper(make_tool())

    result = wrapper("def add(a, b): return a + b")

    assert result == "ok"
    assert calls == [
        ("run_tests", {"code": "def add(a, b): return a + b"})
    ]


def test_dynamic_wrapper_accepts_keyword_argument() -> None:
    handle, calls = make_tools_handle_for_wrapper_tests()
    wrapper = handle.create_single_wrapper(make_tool())

    result = wrapper(code="def add(a, b): return a + b")

    assert result == "ok"
    assert calls == [
        ("run_tests", {"code": "def add(a, b): return a + b"})
    ]


def test_dynamic_wrapper_accepts_positional_and_keyword_arguments() -> None:
    handle, calls = make_tools_handle_for_wrapper_tests()
    tool = make_tool(
        name="read_file",
        properties={
            "filepath": {"type": "string"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
        },
    )
    wrapper = handle.create_single_wrapper(tool)

    result = wrapper("/testbed/app.py", start_line=1, end_line=50)

    assert result == "ok"
    assert calls == [
        (
            "read_file",
            {
                "filepath": "/testbed/app.py",
                "start_line": 1,
                "end_line": 50,
            },
        )
    ]


def test_dynamic_wrapper_rejects_too_many_positional_arguments() -> None:
    handle, _ = make_tools_handle_for_wrapper_tests()
    wrapper = handle.create_single_wrapper(make_tool())

    with pytest.raises(TypeError, match="Too many args"):
        wrapper("first", "second")


def test_dynamic_wrapper_rejects_duplicate_argument_value() -> None:
    handle, _ = make_tools_handle_for_wrapper_tests()
    wrapper = handle.create_single_wrapper(make_tool())

    with pytest.raises(TypeError, match="multiple values"):
        wrapper("solution", code="other solution")


class FakePortal:
    def __init__(self, tools):
        self.tools = tools

    def call(self, _):
        return SimpleNamespace(tools=self.tools)


def test_list_tools_rejects_unknown_mode() -> None:
    handle = ToolsHandle(
        portal=FakePortal([]),
        session=SimpleNamespace(list_tools=lambda: None),
    )

    with pytest.raises(ValueError, match="Unknown list_tools mode"):
        handle.list_tools("banana")


def test_list_tools_prompt_formats_tool_description_signature_and_arguments() -> None:
    tool = make_tool()
    handle = ToolsHandle(
        portal=FakePortal([tool]),
        session=SimpleNamespace(list_tools=lambda: None),
    )

    prompt_tools = handle.list_tools("prompt")

    assert prompt_tools == [
        "Func run_tests:\n"
        "Description: Run tests against a candidate solution.\n"
        "Signature: def run_tests(code: string) -> str\n"
        "Arguments:\n"
        "- code (string): The complete Python source of your solution.\n"
    ]
