from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from multiprocessing import Queue
import resource
import signal
import os
from typing import Any

from agent_smith.sandbox.code_validator import (
    SandboxCodeValidator,
    SandboxCodeValidatorErr,
)
from agent_smith.mcp_client.client_MCP import SandboxMCPClient
from agent_smith.sandbox.ast_validator import AstValidator

class SandboxExecutionTimeout(BaseException):
    pass

def _timeout_handler(_signum, _frame):
    raise SandboxExecutionTimeout()

class SandboxWorker:
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
        if self.mcp_config is not None:
            self.mcp_client = SandboxMCPClient(self.mcp_config)
            self.mcp_client.start(self.allowed_directories)
            self.namespace = self.create_namespace()
        self.apply_memory_limit()
        self.output_queue.put({"type": "ready"})

    def create_namespace(self) -> dict:
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
        }
        namespace = {
            "__builtins__": allowed_builtins,
            "final_answer": self.final_answer,
        }
        if self.mcp_client is not None:
            wrappers = self.mcp_client.tools.create_tool_wrappers()
            namespace.update({
                name: self.pause_timeout_around(wrapper)
                for name, wrapper in wrappers.items()
            })
        return namespace

    def pause_timeout_around(self, func):
        def wrapped(*args, **kwargs):
            remaining = signal.setitimer(signal.ITIMER_REAL, 0)[0]
            try:
                return func(*args, **kwargs)
            finally:
                if remaining > 0:
                    signal.setitimer(signal.ITIMER_REAL, remaining)
        return wrapped

    def final_answer(self, value: str) -> None:
        self.final_answer_value = value

    def list_tools(self) -> list[str]:
        if self.mcp_client is None:
            return []
        return self.mcp_client.tools.list_tools("prompt")

    def loop(self) -> None:
        while True:
            message = self.input_queue.get()
            if message["type"] == "stop":
                self.cleanup()
                break
            if message["type"] == "run":
                self.handle_run(message["code"])
            if message["type"] == "list_tools":
                self.output_queue.put(self.list_tools())

    def apply_memory_limit(self) -> None:
        limit_bytes = self.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))

    def exec_with_timeout(
        self,
        python_code: str,
        ) -> None:
        previous_handler = signal.getsignal(signal.SIGALRM)

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, self.max_execution_time_seconds)
        try:
            exec(python_code, self.namespace, self.namespace)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)



    def handle_run(self, python_code: str) -> None:
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
            self.output_queue.put({
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue() + "\nSandbox execution timed out...",
                "error": "TimeoutError",
                "final_answer": self.final_answer_value,
                "success": False,
            })

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
            self.cleanup()
            self.output_queue.put(
                {
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": type(error).__name__,
                    "final_answer": self.final_answer_value,
                    "success": False,
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

    def safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if not AstValidator.is_authorized_import(name, self.authorized_imports):
            raise ImportError(f"Unauthorized import: {name}")
        return __import__(name, globals, locals, fromlist, level)

    def cleanup(self) -> None:
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
    worker = None
    def handle_sigterm(_signum: int, _frame: Any) -> None:
        try:
            if worker is not None:
                worker.cleanup()
        finally:
            os._exit(0)
    signal.signal(signal.SIGTERM, handle_sigterm)
    try:
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
