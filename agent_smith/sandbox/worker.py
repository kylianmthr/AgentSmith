# agent_smith/sandbox/worker.py

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from multiprocessing import Queue

from agent_smith.sandbox.code_validator import (
    SandboxCodeValidator,
    SandboxCodeValidatorErr,
)
from agent_smith.sandbox.client_MCP import SandboxMCPClient
from agent_smith.sandbox.ast_validator import AstValidator


class SandboxWorker:
    def __init__(
        self,
        input_queue: Queue,
        output_queue: Queue,
        authorized_imports: list[str],
        mcp_config: dict | None = None,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.authorized_imports = authorized_imports
        self.final_answer_value: str | None = None
        self.mcp_client = None
        if mcp_config is not None:
            self.mcp_client = SandboxMCPClient(mcp_config)
            self.mcp_client.start()
        self.namespace = self.create_namespace()

    def list_tools(self) -> list[str]:
        if self.mcp_client is None:
            return []
        return self.mcp_client.list_tools()

    def create_namespace(self) -> dict:
        allowed_builtins = {
            "print": print,
            "len": len,
            "range": range,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "enumerate": enumerate,
            "zip": zip,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "sorted": sorted,
            "__import__": self.safe_import,
        }
        namespace = {
            "__builtins__": allowed_builtins,
            "final_answer": self.final_answer,
        }
        if self.mcp_client is not None:
            namespace.update(self.mcp_client.create_tool_wrappers())
        return namespace

    def final_answer(self, value: str) -> None:
        self.final_answer_value = value

    def loop(self) -> None:
        while True:
            message = self.input_queue.get()
            if message["type"] == "stop":
                if self.mcp_client is not None:
                    self.mcp_client.stop()
                break
            if message["type"] == "run":
                self.handle_run(message["code"])
            if message["type"] == "list_tools":
                self.output_queue.put(self.list_tools())

    def handle_run(self, python_code: str) -> None:
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        if "run_tests" not in python_code:
            stderr_buffer.write(
                "No tests were run. Please use the `run_tests` tool to validate your solution before submitting.\n"
            )
        self.final_answer_value = None
        try:
            SandboxCodeValidator.validate(
                python_code,
                self.authorized_imports,
            )
            with (
                redirect_stdout(stdout_buffer),
                redirect_stderr(stderr_buffer),
            ):
                exec(python_code, self.namespace, self.namespace)

            self.output_queue.put(
                {
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": None,
                    "final_answer": self.final_answer_value,
                    "success": True,
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

    def safe_import(
        self, name, globals=None, locals=None, fromlist=(), level=0
    ):
        if not AstValidator.is_authorized_import(
            name, self.authorized_imports
        ):
            raise ImportError(f"Unauthorized import: {name}")
        return __import__(name, globals, locals, fromlist, level)


def worker_entrypoint(
    input_queue: Queue,
    output_queue: Queue,
    authorized_imports: list[str],
    mcp_config: dict | None = None,
) -> None:
    try:
        worker = SandboxWorker(
            input_queue=input_queue,
            output_queue=output_queue,
            authorized_imports=authorized_imports,
            mcp_config=mcp_config,
        )
        worker.loop()
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
