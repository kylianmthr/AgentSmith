import argparse
import asyncio
from enum import Enum
import docker
import jedi
import io
import os
import tarfile
import tempfile
import subprocess
import re
import logging
import sys
from fastmcp import FastMCP

from agent_smith.models.task_input import SWEBenchTaskInput
from mcp_tools_mbpp import TASK_DEFINITION

DOCKER_IMAGE = "swebench/sweb.eval.x86_64.sympy_1776_sympy-23534:latest"
TESTBED_PATH = os.environ.get("TESTBED_PATH")
CLIENT = None
CONTAINER = None
EVAL_SCRIPT = "#!/bin/bash\nset -uxo pipefail\nsource /opt/miniconda3/bin/activate\nconda activate testbed\ncd /testbed\ngit config --global --add safe.directory /testbed\ncd /testbed\ngit status\ngit show\ngit -c core.fileMode=false diff f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0\nsource /opt/miniconda3/bin/activate\nconda activate testbed\npython -m pip install -e .\ngit checkout f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0 sympy/functions/elementary/tests/test_hyperbolic.py\ngit apply -v - <<'EOF_114329324912'\ndiff --git a/sympy/functions/elementary/tests/test_hyperbolic.py b/sympy/functions/elementary/tests/test_hyperbolic.py\n--- a/sympy/functions/elementary/tests/test_hyperbolic.py\n+++ b/sympy/functions/elementary/tests/test_hyperbolic.py\n@@ -272,6 +272,8 @@ def test_coth():\n \n     assert coth(k*pi*I) == -cot(k*pi)*I\n \n+    assert coth(log(tan(2))) == coth(log(-tan(2)))\n+    assert coth(1 + I*pi/2) == tanh(1)\n \n def test_coth_series():\n     x = Symbol('x')\n\nEOF_114329324912\n: '>>>>> Start Test Output'\nPYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' bin/test -C --verbose sympy/functions/elementary/tests/test_hyperbolic.py\n: '>>>>> End Test Output'\ngit checkout f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0 sympy/functions/elementary/tests/test_hyperbolic.py\n"
START, END = ">>>>> Start Test Output", ">>>>> End Test Output"
HINTS_TEXT = ""
INSTANCE_ID = ""

mcp = FastMCP("swebench-tools")
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("swebench-tools")


def load_task_file(path: str) -> bool:
    global DOCKER_IMAGE
    global CLIENT
    global CONTAINER
    global EVAL_SCRIPT
    global HINTS_TEXT
    global INSTANCE_ID
    try:
        with open(path, "r") as f:
            json_data = f.read()
            task = SWEBenchTaskInput.model_validate_json(json_data)
            DOCKER_IMAGE = task.docker_image
            CLIENT = docker.from_env()
            CONTAINER = CLIENT.containers.run(
                DOCKER_IMAGE, command="sleep infinity", detach=True, tty=True
            )
            EVAL_SCRIPT = task.eval_script
            HINTS_TEXT = task.hints_text
            INSTANCE_ID = task.instance_id
            return True
    except Exception as e:
        logger.error(f"ERROR: {e}")
        return False

def start_testbed_container() -> bool:
    global CLIENT
    global CONTAINER

    if TESTBED_PATH is None:
        return False
    if not os.path.isdir(TESTBED_PATH):
        logger.error(f"TESTBED_PATH does not exist: {TESTBED_PATH}")
        return False
    try:
        CLIENT = docker.from_env()
        CONTAINER = CLIENT.containers.run(
            "python:3.11-slim",
            command="sleep infinity",
            detach=True,
            tty=True,
            working_dir="/testbed",
            volumes={
                os.path.abspath(TESTBED_PATH): {
                    "bind": "/testbed",
                    "mode": "rw",
                }
            },
        )
        return True
    except Exception as e:
        logger.error(f"Could not start TESTBED_PATH container: {e}")
        return False

def _format_line(content: str, start_line: int) -> str:
    new_content = ""
    i = 0
    for line in content.splitlines():
        new_line = f"{start_line + i}: {line}"
        new_content += new_line + "\n"
        i += 1
    return new_content


@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read a file from the container and return the specified lines.

    Args:
        filepath: The path to the file inside the container.
        start_line: The starting line number (1-based).
        end_line: The ending line number (inclusive, 1-based).

    Returns:
        The content of the specified lines, with line numbers prefixed.
    """
    if CONTAINER is None:
        return (
            "read_file unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    res = CONTAINER.exec_run(
        cmd=["sed", "-n", f"{start_line},{end_line}p", filepath],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"{filepath}: {(err or b'').decode('utf-8', errors='replace')}"
        )
    return _format_line(
        (out or b"").decode("utf-8", errors="replace"), start_line
    )


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Edit a file in the container by replacing occurrences of a string.

    Args:
        old_str: The string to be replaced.
        new_str: The string to replace with.

    Returns:
        None

    Raises:
        FileNotFoundError if the file does not exist or cannot be edited.
    """
    if CONTAINER is None:
        return (
            "edit_file unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    res = CONTAINER.exec_run(
        cmd=["sed", "-i", f"s/{old_str}/{new_str}/g", filepath],
        workdir="/testbed",
    )
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"{filepath}: {(res.output or b'').decode('utf-8', errors='replace')}"
        )
    return "Edit applied."


@mcp.tool()
def list_files(directory: str, pattern: str = "*") -> str:
    """List files in a directory inside the container that match a given pattern.

    Args:
        directory: The directory to search in.
        pattern: The filename pattern to match (default is "*", which matches all files).

    Returns:
        The list of matching files, one per line.
    """
    if CONTAINER is None:
        return (
            "list_files unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    res = CONTAINER.exec_run(
        cmd=["find", directory, "-name", pattern],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"{directory}: {(err or b'').decode('utf-8', errors='replace')}"
        )
    return (out or b"").decode("utf-8", errors="replace")


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*") -> str:
    """Search for a pattern in code files inside the container.

    Args:
        pattern: The regex pattern to search for.
        file_pattern: The filename pattern to include in the search (default is "*", which includes all files).

    Returns:
        The matching lines with file paths and line numbers.
    """
    if CONTAINER is None:
        return (
            "search_code unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    res = CONTAINER.exec_run(
        cmd=["grep", "-rnw", ".", "-e", pattern, "--include", file_pattern],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"Pattern '{pattern}' not found in files matching '{file_pattern}': {(err or b'').decode('utf-8')}"
        )
    return (out or b"").decode("utf-8", errors="replace")


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Search for a function or class definition in code files inside the container.

    Args:
        name: The name of the function or class to search for.

    Returns:
        The matching lines with file paths and line numbers.
    """
    if CONTAINER is None:
        return (
            "search_function_or_class_definition_in_code unavailable: "
            "SWE-bench container is not initialized. Start with --task <task.json> "
            "or set TESTBED_PATH before launching the sandbox."
        )
    res = CONTAINER.exec_run(
        cmd=["grep", "-rn", ".", "-e", f"def {name}(", "--include", "*.py"],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        res_class = CONTAINER.exec_run(
            cmd=[
                "grep",
                "-rnE",
                ".",
                "-e",
                f"class {name}[:(]",
                "--include",
                "*.py",
            ],
            workdir="/testbed",
            demux=True,
        )
        out_class, err_class = res_class.output
        if res_class.exit_code != 0:
            raise FileNotFoundError(
                f"Function or class '{name}' not found in code"
            )
        return out_class.decode("utf-8", errors="replace")
    return (out or b"").decode("utf-8", errors="replace")


def _copy_testbed_to_host(dst: str) -> str:
    if CONTAINER is None:
        raise RuntimeError(
            "find_references unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    bits, _stat = CONTAINER.get_archive("/testbed")
    buf = io.BytesIO()
    for chunk in bits:
        buf.write(chunk)
    buf.seek(0)
    with tarfile.open(fileobj=buf) as tar:
        tar.extractall(dst, filter="data")
    return os.path.join(dst, "testbed")


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find references to a function or class in code files inside the container using Jedi.

    Args:
        name: The name of the function or class to find references for.
        filepath: The path to the file inside the container where the function or class is defined.
        line: The line number (1-based) in the file where the function or class is

    Returns:
        References to the function or class, with file paths and line numbers.
    """
    if CONTAINER is None:
        return (
            "find_references unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    with tempfile.TemporaryDirectory() as tmp:
        root = _copy_testbed_to_host(tmp)
        if os.path.isabs(filepath):
            container_path = os.path.normpath(filepath)
        else:
            container_path = os.path.normpath(
                os.path.join("/testbed", filepath)
            )

        if container_path != "/testbed" and not container_path.startswith(
            "/testbed/"
        ):
            raise ValueError(f"filepath hors de /testbed: {filepath!r}")
        rel = os.path.relpath(container_path, "/testbed")
        host_path = os.path.join(root, rel)
        with open(host_path, encoding="utf-8") as f:
            code_line = f.readlines()[line - 1]
        col = code_line.find(name)
        if col < 0:
            raise ValueError(f"'{name}' not found {filepath}:{line}")

        project = jedi.Project(root)
        script = jedi.Script(path=host_path, project=project)
        refs = script.get_references(
            line=line, column=col, include_builtins=False
        )
        lines = []
        for r in refs:
            abs_path = "/testbed" + str(r.module_path)[len(root) :]
            lines.append(f"{abs_path}:{r.line} {r.get_line_code().strip()}")
        return "\n".join(lines)


@mcp.tool()
def run_command(command: str, workdir: str = "/testbed") -> str:
    """Run a shell command inside the container and return its output.

    Args:
        command: The shell command to run.
        workdir: The working directory inside the container (default is "/testbed").

    Returns:
        The standard output and standard error of the command, along with the exit code.
    """
    if CONTAINER is None:
        return (
            "run_command unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    res = CONTAINER.exec_run(
        cmd=["sh", "-c", command],
        workdir=workdir,
        demux=True,
    )
    out, err = res.output
    return f"stdout:\n{(out or b'').decode('utf-8', errors='replace')}\nstderr:\n{(err or b'').decode('utf-8', errors='replace')}\nexit_code: {res.exit_code}"


def _test_section(text: str) -> tuple[str, bool]:
    i = text.find(START)
    j = text.find(END, i + 1) if i != -1 else -1
    if i != -1 and j != -1:
        index = i + len(START)
        return text[index:j].strip(), True
    return text, False


_TB = re.compile(r"^Traceback \(most recent call last\):", re.M)
_EXC = re.compile(r"^\w[\w.]*(Error|Exception|Warning|Assertion)\b")


def _summarize(output: str, budget: int = 6000, max_blocks: int = 5) -> str:
    lines = output.splitlines()
    tail = lines[-40:]

    blocks, seen = [], set()
    starts = [i for i, l in enumerate(lines) if _TB.match(l)]
    for s in starts:
        block = [lines[s]]
        for l in lines[s + 1 : s + 41]:
            block.append(l)
            if _EXC.match(l):
                break
        sig = block[-1]
        if sig not in seen:
            seen.add(sig)
            blocks.append("\n".join(block))
        if len(blocks) >= max_blocks:
            break
    header = f"[{len(starts)} traceback(s), {len(blocks)} show]"
    body = (
        "\n\n".join(blocks) + "\n\n--- END OF OUTPUT ---\n" + "\n".join(tail)
    )
    out = header + "\n" + body
    return out if len(out) <= budget else out[:budget] + "\n[cuted (too long)]"


@mcp.tool()
def run_tests() -> str:
    """Run the evaluation script inside the container and return the results.

    Returns:
        The exit code, verdict, and summarized output of the evaluation script.
    """
    if CONTAINER is None:
        return (
            "run_tests unavailable: SWE-bench container is not initialized. "
            "Start with --task <task.json> or set TESTBED_PATH before launching the sandbox."
        )
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tarinfo = tarfile.TarInfo(name="run_tests.sh")
        tarinfo.size = len(EVAL_SCRIPT.encode("utf-8"))
        tar.addfile(tarinfo, io.BytesIO(EVAL_SCRIPT.encode("utf-8")))
    tar_stream.seek(0)
    CONTAINER.put_archive("/testbed", tar_stream.read())
    CONTAINER.exec_run(cmd=["chmod", "+x", "run_tests.sh"], workdir="/testbed")
    res = CONTAINER.exec_run(cmd=["./run_tests.sh"], workdir="/testbed")
    combined = (res.output or b"").decode("utf-8", errors="replace")
    section, found = _test_section(combined)
    verdict = "OK" if found else f"FAIL (exit code: {res.exit_code})"
    note = "" if found else "\n[NO TEST FOUND, return raw output]"
    body = _summarize(section, budget=6000)
    return f"Exit code: {res.exit_code}\nVerdict: {verdict}{note}\n\n{body}"


@mcp.tool()
def get_patch():

    if TESTBED_PATH:
        res = subprocess.run(
            ["git", "-C", TESTBED_PATH, "-c", "core.fileMode=false", "diff"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return "No changes"
        return res.stdout or "No changes"
    if CONTAINER is None:
        return "No changes (SWE-bench container is not initialized)"
    res = CONTAINER.exec_run(
        "git -c core.fileMode=false diff", demux=True, workdir="/testbed"
    )
    out, err = res.output
    if res.exit_code != 0:
        raise RuntimeError(
            f"git diff failed: {(err or b'').decode('utf-8', errors='replace')}"
        )
    return (out or b"").decode("utf-8", errors="replace")


@mcp.resource("mbpp://task")
def get_task() -> str:
    """Get the informations of the current task."""
    return (
        "INSTANCE ID\n"
        f"{INSTANCE_ID}\n"
        "HINTS\n"
        f"{HINTS_TEXT}\n"
        "DOCKER IMAGE\n"
        f"{DOCKER_IMAGE}\n"
        "EVAL SCRIPT\n"
        f"{EVAL_SCRIPT}"
    )


@mcp.prompt()
def get_prompt() -> str:
    return "TODO"


class TransportType(str, Enum):
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
    elif TESTBED_PATH:
        if not start_testbed_container():
            sys.exit(1)
    try:
        if args.transport == TransportType.STDIO:
            mcp.run(
                transport="stdio",
                show_banner=True,
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
            )

    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        if CONTAINER is not None:
            CONTAINER.stop()
            CONTAINER.remove()
