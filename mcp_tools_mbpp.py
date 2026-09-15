from enum import Enum
import subprocess
import sys
import argparse
import logging
import json
from fastmcp import FastMCP
import asyncio

from agent_smith.models.task_input import MBPPTaskInput

# j'ai pas vu d'interdictions dans le sujet par rapport au variable globales, ici ca m'arrange
TEST_LIST = []
TEST_IMPORT = []
TASK_DEFINITION = ""
FUNCTION_DEFINITION = ""
TASK_ID = ""

mcp = FastMCP("mbpp-tools")
logging.basicConfig(
    level=logging.INFO, stream=sys.stderr
)  # je suis oblige de config les logs sur stderr pour eviter que ca ne perturbe le serveur mcp
logger = logging.getLogger("mbpp-tools")


def load_task_file(path: str) -> bool:
    """Load an MBPP task into the server state."""

    global TEST_LIST
    global TEST_IMPORT
    global TASK_DEFINITION
    global FUNCTION_DEFINITION
    global TASK_ID
    try:
        with open(path, "r") as f:
            json_data = f.read()
            task = MBPPTaskInput.model_validate_json(json_data)
            TEST_LIST = task.test_list
            TEST_IMPORT = task.test_imports
            TASK_DEFINITION = task.task_definition
            FUNCTION_DEFINITION = task.function_definition
            TASK_ID = task.task_id
            return True
    except Exception as e:
        logger.error(f"ERROR: {e}")
        return False


def last_line(stderr: str) -> str:
    """Return the last non-empty stderr line."""

    lines = [line for line in stderr.strip().split("\n") if line.strip()]
    return lines[-1] if lines else ""


@mcp.tool()
def run_tests(code: str, test_list: list[str] | None = None) -> str:
    """Execute the MBPP test suite against a candidate solution.

    Args:
        code: The complete Python source of your solution (function definition included).

    Returns:
        A summary like "2/3 tests passed" followed by details of failing assertions.
    """
    tests = test_list if test_list is not None else TEST_LIST
    if not tests:
        return "ERROR: No tests provided"
    failures = []
    for test in tests:
        test_code = "\n".join(TEST_IMPORT) + "\n" + code + "\n" + test
        try:
            res = subprocess.run(
                [
                    sys.executable,
                    "-",
                ],  # ca c'est pour lancer dynamiquement du code sans cree de fichier, le - dis a python de lire la stdin
                input=test_code,
                capture_output=True,
                text=True,
                timeout=10,
            )  # c'est comme le exec dont je t'avais parle mais c'est pas bloquant
            if res.returncode != 0:
                failure = f"FAILED: {test}\n{last_line(res.stderr)}"
                if not len(last_line(res.stderr)):
                    failure += "No stderr"
                failures.append(failure)
        except subprocess.TimeoutExpired:
            failures.append(f"TIMEOUT: {test} (10s)")
        except Exception as e:
            failures.append(f"CRASH: {e}")
    res = f"{len(tests) - len(failures)}/{len(tests)} tests passed"
    if failures:
        res += "\n" + "\n".join(
            failures[:3]
        )  # on a que 600 tokens/iteration donc on limite les logs de failures
        if len(failures) > 3:
            res += f"\n{len(failures) - 3} additional failures not displayed"
    if test_list is not None:
        return json.dumps({"success": not failures, "output": res})
    return res


@mcp.resource("mbpp://task")
def get_task() -> str:
    """Get the informations of the current task."""
    formated_test_list = "\n".join(TEST_LIST)
    return (
        "TASK DEFINITION\n"
        f"{TASK_DEFINITION}\n\n"
        "FUNCTION DEFINITION\n"
        f"{FUNCTION_DEFINITION}\n\n"
        "TESTS\n"
        f"{formated_test_list}"
    )


@mcp.prompt()
def get_prompt() -> str:
    """Return the MBPP agent methodology prompt."""

    return (
        "Solve one MBPP task with a short evidence-driven loop:\n"
        "METHOD\n"
        "1. Infer the standard operation from the wording, signature, and all "
        "examples.\n"
        "2. Write the complete function and immediately verify it with run_tests.\n"
        "3. On failure, re-read the assertion, calculate the actual result, and "
        "revise the assumption that caused the mismatch; never repeat equivalent "
        "code.\n"
        "4. Submit immediately after every test passes.\n"
        "CONSTRAINTS\n"
        "- The budget is tight: test on the first turn and finish in 2-3 turns.\n"
        "- Keep the solution self-contained and preserve exact return types, ordering, "
        "multiplicity, and boundary behavior.\n"
        "- Account for hidden edge cases without overfitting the public examples."
    )


class TransportType(str, Enum):
    """Supported MCP server transports."""

    STDIO = "stdio"
    HTTP = "http"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP server for mbpp agent")
    parser.add_argument(
        "--task", type=str, default=None, help="Path to the task.json file"
    )
    parser.add_argument(
        "--transport",
        type=TransportType,
        choices=list(TransportType),
        default=TransportType.STDIO,
        help="The transport type of the mcp server, could be stdio or http",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for HTTP MCP server",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP MCP server",
    )

    parser.add_argument(
        "--path",
        type=str,
        default="/mcp",
        help="Path for HTTP MCP server",
    )

    args = parser.parse_args()
    if args.task:
        if not load_task_file(args.task):
            sys.exit(1)

    try:
        if args.transport == TransportType.STDIO:
            mcp.run(
                transport="stdio",
                show_banner=False,
                log_level="ERROR",
            )
        else:
            if not args.host.strip():
                parser.error("--host cannot be empty")
            if args.port <= 0 or args.port > 65535:
                parser.error("--port must be between 1 and 65535")
            if not args.path.strip():
                parser.error("--path cannot be empty")
            if not args.path.startswith("/"):
                args.path = "/" + args.path

            mcp.run(
                transport="http",
                host=args.host,
                port=args.port,
                path=args.path,
                show_banner=False,
                log_level="ERROR",
            )

    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
