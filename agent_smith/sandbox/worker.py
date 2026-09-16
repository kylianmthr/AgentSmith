from contextlib import redirect_stderr, redirect_stdout
import ctypes
from io import StringIO
from multiprocessing import Queue
import resource
import signal
import os
import sys
from typing import Any

from agent_smith.sandbox.code_validator import (
    SandboxCodeValidator,
    SandboxCodeValidatorErr,
)
from agent_smith.mcp_client.client_MCP import SandboxMCPClient
from agent_smith.sandbox.ast_validator import AstValidator


class SandboxExecutionTimeout(BaseException):
    """Interrupt generated code when its execution budget expires."""

    pass


def _timeout_handler(_signum, _frame):
    """Raise the sandbox timeout from the alarm signal."""

    raise SandboxExecutionTimeout()


class SandboxWorker:
    """Execute generated code in a persistent restricted process."""

    def __init__(
        self,
        input_queue: Queue,
        output_queue: Queue,
        authorized_imports: list[str],
        allowed_directories: list[str],
        max_memory_mb: int,
        max_execution_time_seconds: int,
        mcp_config: dict | None = None,
    ) -> None:
        """Configure execution limits, queues, and optional MCP access."""

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.authorized_imports = authorized_imports
        self.allowed_directories = allowed_directories
        self.max_memory_mb = max_memory_mb
        self.max_execution_time_seconds = max_execution_time_seconds
        self.final_answer_value: str | None = None
        self.mcp_config = mcp_config
        self.mcp_client = None
        self.namespace = self.create_namespace()

    def start(self) -> None:
        """Initialize MCP tools, resource limits, and readiness."""

        if self.mcp_config is not None:
            self.mcp_client = SandboxMCPClient(self.mcp_config)
            self.mcp_client.start(self.allowed_directories)
            self.namespace = self.create_namespace()
        self.apply_memory_limit()
        self.output_queue.put({"type": "ready"})

    def create_namespace(self) -> dict:
        """Create the restricted persistent execution namespace."""

        allowed_builtins = {
            "print": print,
            "len": len,
            "dir": dir,
            "range": range,
            "type": type,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "bytearray": bytearray,
            "bytes": bytes,
            "set": set,
            "tuple": tuple,
            "enumerate": enumerate,
            "zip": zip,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "all": all,
            "any": any,
            "isinstance": isinstance,
            "repr": repr,
            "round": round,
            "sorted": sorted,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "RuntimeError": RuntimeError,
            "ImportError": ImportError,
            "NameError": NameError,
            "MemoryError": MemoryError,
            "TimeoutError": TimeoutError,
            "ZeroDivisionError": ZeroDivisionError,
            "KeyError": KeyError,
            "__import__": self.safe_import,
            "open": self.safe_open,
        }
        namespace = {
            "__builtins__": allowed_builtins,
            "final_answer": self.final_answer,
        }
        if self.mcp_client is not None:
            wrappers = self.mcp_client.tools.create_tool_wrappers()
            if self.mcp_client.content is not None:
                wrappers.update(self.mcp_client.content.create_wrappers())
            namespace.update(
                {
                    name: self.pause_timeout_around(wrapper)
                    for name, wrapper in wrappers.items()
                }
            )
        return namespace

    def pause_timeout_around(self, func):
        """Pause the code timer while a trusted MCP tool is running."""

        def wrapped(*args, **kwargs):
            """Invoke an MCP tool outside the generated-code timer."""

            remaining = signal.setitimer(signal.ITIMER_REAL, 0)[0]
            try:
                return func(*args, **kwargs)
            finally:
                if remaining > 0:
                    signal.setitimer(signal.ITIMER_REAL, remaining)

        return wrapped

    def final_answer(self, value: str | None = None, **kwargs) -> None:
        """Record the answer submitted by generated code."""

        if value is None and kwargs:
            value = next(iter(kwargs.values()))
        self.final_answer_value = value

    def list_tools(self) -> list[str]:
        """Return documentation for tools exposed by the MCP server."""

        if self.mcp_client is None:
            return []
        documentation = self.mcp_client.tools.list_tools("prompt")
        if self.mcp_client.content is not None:
            documentation.extend(self.mcp_client.content.documentation())
        return documentation

    def loop(self) -> None:
        """Process manager commands until a stop request arrives."""

        while True:
            message = self.input_queue.get()
            if message["type"] == "stop":
                self.cleanup()
                break
            if message["type"] == "run":
                self.handle_run(message["code"])
            if message["type"] == "list_tools":
                self.output_queue.put(self.list_tools())

    MEMORY_LIMIT_NAMES = ("RLIMIT_AS", "RLIMIT_DATA")

    def apply_memory_limit(self) -> None:
        """Cap the worker's address space.

        Linux honours RLIMIT_AS, which is what the security tests check.
        Darwin refuses to lower RLIMIT_AS and RLIMIT_DATA altogether, so the
        limit is unenforceable there: warn loudly and keep going rather than
        making the sandbox unusable on the development machine.
        """
        limit_bytes = self.max_memory_mb * 1024 * 1024
        for limit_name in self.MEMORY_LIMIT_NAMES:
            limit = getattr(resource, limit_name, None)
            if limit is None:
                continue
            try:
                resource.setrlimit(limit, (limit_bytes, limit_bytes))
                return
            except (ValueError, OSError):
                continue
        if sys.platform.startswith("linux"):
            raise RuntimeError(
                "Cannot apply the sandbox memory limit "
                f"({self.max_memory_mb} MB): setrlimit was refused."
            )
        print(
            f"WARNING: the {sys.platform} kernel refuses to lower RLIMIT_AS "
            f"and RLIMIT_DATA, so the {self.max_memory_mb} MB sandbox memory "
            "limit is NOT enforced here. It is enforced on Linux, where the "
            "evaluation runs.",
            file=sys.stderr,
        )

    def exec_with_timeout(
        self,
        python_code: str,
    ) -> None:
        """Execute code under the configured alarm timeout."""

        previous_handler = signal.getsignal(signal.SIGALRM)

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, self.max_execution_time_seconds)
        try:
            exec(python_code, self.namespace, self.namespace)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)

    def handle_run(self, python_code: str) -> None:
        """Validate and execute one code request with captured output."""

        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        self.final_answer_value = None
        try:
            SandboxCodeValidator.validate(
                python_code,
                self.authorized_imports,
            )
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                self.exec_with_timeout(python_code)

            self.output_queue.put(
                {
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": None,
                    "final_answer": self.final_answer_value,
                    "success": True,
                }
            )

        except SandboxExecutionTimeout:
            self.output_queue.put(
                {
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue()
                    + "\nSandbox execution timed out...",
                    "error": "TimeoutError",
                    "final_answer": self.final_answer_value,
                    "success": False,
                }
            )

        except SandboxCodeValidatorErr as error:
            self.output_queue.put(
                {
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": str(error),
                    "final_answer": self.final_answer_value,
                    "success": False,
                }
            )

        except (KeyboardInterrupt, SystemExit) as error:
            self.output_queue.put(
                {
                    "type": "control_flow",
                    "exception": type(error).__name__,
                    "code": getattr(error, "code", None),
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "final_answer": self.final_answer_value,
                }
            )
            raise

        except Exception as error:
            self.output_queue.put(
                {
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": str(error),
                    "final_answer": self.final_answer_value,
                    "success": False,
                }
            )

    def safe_open(
        self,
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        """Open a file only when its resolved path is allowed."""

        if opener is not None:
            raise PermissionError("Custom openers are not allowed")
        try:
            requested_path = os.path.realpath(os.path.abspath(os.fspath(file)))
        except (TypeError, ValueError, OSError) as error:
            raise PermissionError("Invalid file path") from error
        allowed = False
        for directory in self.allowed_directories:
            allowed_directory = os.path.realpath(os.path.abspath(directory))
            try:
                if (
                    os.path.commonpath([requested_path, allowed_directory])
                    == allowed_directory
                ):
                    allowed = True
                    break
            except ValueError:
                continue
        if not allowed:
            raise PermissionError(
                f"File access outside allowed directories: {requested_path}"
            )
        return open(
            requested_path,
            mode,
            buffering,
            encoding,
            errors,
            newline,
            closefd,
            opener,
        )

    def safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Import a module only when the sandbox allowlist permits it."""

        if not AstValidator.is_authorized_import(name, self.authorized_imports):
            raise ImportError(f"Unauthorized import: {name}")
        return __import__(name, globals, locals, fromlist, level)

    def cleanup(self) -> None:
        """Close the worker's MCP client if one is active."""

        if self.mcp_client is not None:
            self.mcp_client.stop()
            self.mcp_client = None


def worker_entrypoint(
    input_queue: Queue,
    output_queue: Queue,
    authorized_imports: list[str],
    allowed_directories: list[str],
    max_memory_mb: int,
    max_execution_time_seconds: int,
    mcp_config: dict | None = None,
) -> None:
    """Run a sandbox worker and report startup failures to its manager."""

    worker = None

    def handle_sigterm(_signum: int, _frame: Any) -> None:
        """Clean up worker resources before forced termination."""

        try:
            if worker is not None:
                worker.cleanup()
        finally:
            os._exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        if sys.platform.startswith("linux"):
            ctypes.CDLL(None).prctl(1, signal.SIGTERM)
        worker = SandboxWorker(
            input_queue=input_queue,
            output_queue=output_queue,
            authorized_imports=authorized_imports,
            allowed_directories=allowed_directories,
            max_memory_mb=max_memory_mb,
            max_execution_time_seconds=max_execution_time_seconds,
            mcp_config=mcp_config,
        )
        worker.start()
        worker.loop()

    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        output_queue.put(
            {
                "stdout": "",
                "stderr": "",
                "error": f"Worker startup failed: {e}",
                "final_answer": None,
                "success": False,
            }
        )
    finally:
        if worker is not None:
            worker.cleanup()
