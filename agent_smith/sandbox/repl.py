from pathlib import Path
import codeop
from typing import Any
import argparse
from urllib.parse import urlparse
import shlex
from shutil import which

from agent_smith.sandbox.manager import SandboxManager, SandboxManagerError
from agent_smith.models.result import SandboxResult

class REPLError(Exception):
    pass

class REPLInteractive:
    def __init__(
        self,
        config_path: Path | None,
        mcp_config: dict | None = None,
    ) -> None:
        self.buffer = []
        try:
            self.sandbox = SandboxManager(config_path, mcp_config)
        except SandboxManagerError as e:
            raise REPLError(e)

    def run(self):
        prompt = "sandbox> "
        try:
            while 1:
                line = input(prompt)
                if line == "exit":
                    break
                self.buffer.append(line)
                python_code = "\n".join(self.buffer)
                try:
                    compiled = codeop.compile_command(python_code)
                except (SyntaxError, ValueError, OverflowError) as e:
                    print(f"Invalid code: {e}")
                    self.buffer.clear()
                    continue
                if compiled is None:
                    prompt = "> "
                    continue

                result = self.sandbox.run(python_code)
                self.display_result(result)
                self.buffer.clear()
                prompt = "sandbox> "        
        except EOFError:
            pass
        except SandboxManagerError as e:
            raise REPLError(e)

        finally:
            self.sandbox.stop()

    @staticmethod
    def display_result(result: SandboxResult) -> None:
        if result:
            print("************** RESULT: **************")
            if result.stdout:
                print(f"    Stdout: {result.stdout}")
            if result.stderr:
                print(f"    Stderr: {result.stderr}")
            if result.error:
                print(f"    Error: {result.error}")
            if result.final_answer:
                print(f"    Final Answer: {result.final_answer}")
            if result.success:
                print(f"    Success: Yes")
            else:
                print(f"    Success: No")
                print(f"    -> Check forbidden imports, functions, crash on code execution, infinite loops...")
            print("*************************************")

def build_mcp_config_with_task(args: str) -> dict[str, Any]:
    try:
        parts = shlex.split(args)
    except ValueError as error:
        raise REPLError(f"Invalid --mcp-stdio command: {error}") from error
    if not parts:
        raise REPLError("--mcp-stdio cannot be empty. Usage: \"python mcp_tools_mbpp.py\"")
    command = parts[0]
    if which(command) is None:
        raise REPLError(f"MCP stdio command not found: {command}")
    if not parts[1:]:
        raise REPLError(
            '--mcp-stdio must launch a server, example: "python mcp_tools_mbpp.py"'
        )
    return {
        "command": command,
        "args": parts[1:],
        "cwd": Path.cwd(),
    }


def parse_args() -> tuple[Path | None, dict[str, Any] | None]:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config_path",
        nargs="?",
        type=Path,
    )
    parser.add_argument(
        "--mcp-stdio",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--mcp-server",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--autostart",
        type=str,
        default=None,
    )
    args = parser.parse_args()

    if args.mcp_stdio and args.mcp_server:
        raise REPLError(
            "Use either --mcp-stdio or --mcp-server, not both"
        )
    mcp_config = None
    if args.mcp_stdio:
        mcp_config = build_mcp_config_with_task(args.mcp_stdio)
        mcp_config.update({"transport": "stdio"})
    if args.mcp_server:
        mcp_config = {
            "transport": "http",
            "url": args.mcp_server,
        }
        if args.autostart:
            autostart_config = build_mcp_config_with_task(args.autostart)
            mcp_config.update(autostart_config)
    if args.config_path is not None and args.config_path.suffix != ".json":
        raise REPLError("Config must be a JSON file")
    return (args.config_path, mcp_config)


def main() -> None:
    try:
        config_path, mcp_config = parse_args()
        repl = REPLInteractive(config_path, mcp_config)
        repl.run()
    except REPLError as e:
        print(e)
        return
