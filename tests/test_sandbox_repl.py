import sys
from pathlib import Path

import pytest

from agent_smith.models.result import SandboxResult
from agent_smith.sandbox import repl as repl_module
from agent_smith.sandbox.repl import (
    REPLError,
    REPLInteractive,
    build_mcp_config_with_task,
    parse_args,
)


class FakeSandbox:
    def __init__(self) -> None:
        self.runs: list[str] = []
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def run(self, python_code: str) -> SandboxResult:
        self.runs.append(python_code)
        return SandboxResult(stdout="ok\n", success=True)

    def stop(self) -> None:
        self.stopped = True


def make_repl_with_fake_sandbox(fake_sandbox: FakeSandbox) -> REPLInteractive:
    repl = REPLInteractive.__new__(REPLInteractive)
    repl.buffer = []
    repl.sandbox = fake_sandbox
    return repl


class TestBuildMCPConfigWithTask:
    def test_rejects_empty_command(self) -> None:
        with pytest.raises(REPLError, match="cannot be empty"):
            build_mcp_config_with_task("")

    def test_rejects_unknown_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(repl_module, "which", lambda command: None)

        with pytest.raises(REPLError, match="command not found"):
            build_mcp_config_with_task("blabla.txt aligator --task")

    def test_accepts_any_existing_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(repl_module, "which", lambda command: f"/usr/bin/{command}")

        config = build_mcp_config_with_task("node server.js --stdio")

        assert config["command"] == "node"
        assert config["args"] == ["server.js", "--stdio"]
        assert config["cwd"] == Path.cwd()
        assert "transport" not in config

    def test_preserves_quoted_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(repl_module, "which", lambda command: f"/usr/bin/{command}")

        config = build_mcp_config_with_task(
            'python mcp_tools_mbpp.py --task "tasks/my task.json"'
        )

        assert config["command"] == "python"
        assert config["args"] == [
            "mcp_tools_mbpp.py",
            "--task",
            "tasks/my task.json",
        ]
        assert "transport" not in config


class TestParseArgs:
    def test_no_args_uses_default_config_and_no_mcp(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["sandbox"])

        config_path, mcp_config = parse_args()

        assert config_path is None
        assert mcp_config is None

    def test_accepts_json_config_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["sandbox", "sandbox_template.json"])

        config_path, mcp_config = parse_args()

        assert config_path == Path("sandbox_template.json")
        assert mcp_config is None

    def test_rejects_non_json_config_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["sandbox", "sandbox_template.txt"])

        with pytest.raises(REPLError, match="JSON"):
            parse_args()

    def test_builds_mcp_stdio_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(repl_module, "which", lambda command: f"/usr/bin/{command}")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "sandbox",
                "--mcp-stdio",
                "python mcp_tools_mbpp.py --task task.json",
            ],
        )

        config_path, mcp_config = parse_args()

        assert config_path is None
        assert mcp_config == {
            "command": "python",
            "args": ["mcp_tools_mbpp.py", "--task", "task.json"],
            "cwd": Path.cwd(),
            "transport": "stdio",
        }

    def test_builds_http_mcp_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["sandbox", "--mcp-server", "http://localhost"])

        config_path, mcp_config = parse_args()

        assert config_path is None
        assert mcp_config == {
            "transport": "http",
            "url": "http://localhost",
        }

    def test_builds_http_mcp_config_with_autostart(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(repl_module, "which", lambda command: f"/usr/bin/{command}")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "sandbox",
                "--mcp-server",
                "http://127.0.0.1:9000/mcp",
                "--autostart",
                "python mcp_tools_mbpp.py --task task.json",
            ],
        )

        config_path, mcp_config = parse_args()

        assert config_path is None
        assert mcp_config == {
            "transport": "http",
            "url": "http://127.0.0.1:9000/mcp",
            "command": "python",
            "args": ["mcp_tools_mbpp.py", "--task", "task.json"],
            "cwd": Path.cwd(),
        }

    def test_builds_http_autostart_config_with_custom_sandbox_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(repl_module, "which", lambda command: f"/usr/bin/{command}")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "sandbox",
                "--mcp-server",
                "http://127.0.0.1:9000/mcp",
                "--autostart",
                "python mcp_tools_mbpp.py --task task.json",
                "sandbox_config.json",
            ],
        )

        config_path, mcp_config = parse_args()

        assert config_path == Path("sandbox_config.json")
        assert mcp_config == {
            "transport": "http",
            "url": "http://127.0.0.1:9000/mcp",
            "command": "python",
            "args": ["mcp_tools_mbpp.py", "--task", "task.json"],
            "cwd": Path.cwd(),
        }

    def test_rejects_stdio_and_http_together(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "sandbox",
                "--mcp-stdio",
                "python mcp_tools_mbpp.py",
                "--mcp-server",
                "http://localhost",
            ],
        )

        with pytest.raises(REPLError, match="Use either"):
            parse_args()


class TestREPLInteractiveRun:
    def test_executes_single_complete_entry(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake_sandbox = FakeSandbox()
        repl = make_repl_with_fake_sandbox(fake_sandbox)
        lines = iter(["x = 1", "exit"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: next(lines))

        repl.run()

        assert fake_sandbox.runs == ["x = 1"]
        assert fake_sandbox.stopped is True
        assert "ok" in capsys.readouterr().out

    def test_waits_for_complete_multiline_entry(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_sandbox = FakeSandbox()
        repl = make_repl_with_fake_sandbox(fake_sandbox)
        lines = iter([
            "def add(a, b):",
            "    return a + b",
            "",
            "exit",
        ])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: next(lines))

        repl.run()

        assert fake_sandbox.runs == [
            "def add(a, b):\n    return a + b\n"
        ]
        assert fake_sandbox.stopped is True

    def test_invalid_syntax_does_not_call_sandbox(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake_sandbox = FakeSandbox()
        repl = make_repl_with_fake_sandbox(fake_sandbox)
        lines = iter(["bad )", "exit"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: next(lines))

        repl.run()

        assert fake_sandbox.runs == []
        assert fake_sandbox.stopped is True
        assert "Invalid code" in capsys.readouterr().out

    def test_eof_stops_sandbox(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_sandbox = FakeSandbox()
        repl = make_repl_with_fake_sandbox(fake_sandbox)

        def raise_eof(prompt: str) -> str:
            raise EOFError

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", raise_eof)

        repl.run()

        assert fake_sandbox.runs == []
        assert fake_sandbox.stopped is True
