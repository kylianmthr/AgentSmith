# agent_smith/sandbox/worker.py

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from multiprocessing import Queue

from agent_smith.sandbox.code_validator import (
    SandboxCodeValidator,
    SandboxCodeValidatorErr,
)


class SandboxWorker:
    def __init__(
        self,
        input_queue: Queue,
        output_queue: Queue,
        authorized_imports: list[str],
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.authorized_imports = authorized_imports
        self.final_answer_value: str | None = None
        self.namespace = self.create_namespace()

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
        }
        return {
            "__builtins__": allowed_builtins,
            "final_answer": self.final_answer,
        }

    def final_answer(self, value: str) -> None:
        self.final_answer_value = value

    def loop(self) -> None:
        while True:
            message = self.input_queue.get()
            if message["type"] == "stop":
                break
            if message["type"] == "run":
                self.handle_run(message["code"])

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
                exec(python_code, self.namespace, self.namespace)

            self.output_queue.put({
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
                "error": None,
                "final_answer": self.final_answer_value,
                "success": True,
            })

        except SandboxCodeValidatorErr as error:
            self.output_queue.put({
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
                "error": str(error),
                "final_answer": self.final_answer_value,
                "success": False,
            })

        except Exception as error:
            self.output_queue.put({
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
                "error": str(error),
                "final_answer": self.final_answer_value,
                "success": False,
            })


def worker_entrypoint(
    input_queue: Queue,
    output_queue: Queue,
    authorized_imports: list[str],
) -> None:
    worker = SandboxWorker(
        input_queue=input_queue,
        output_queue=output_queue,
        authorized_imports=authorized_imports,
    )
    worker.loop()