from multiprocessing import Process, Queue
from queue import Empty
from pathlib import Path

from agent_smith.sandbox.config_validator import SandboxConfigValidator
from agent_smith.sandbox.result import SandboxResult
from agent_smith.sandbox.worker import worker_entrypoint

class SandboxManager:
    def __init__(
        self,
        config_path: Path | None,
        mcp_config: dict | None = None,
    ) -> None:
        self.config = SandboxConfigValidator.load(config_path)
        self.mcp_config = mcp_config
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.process: Process | None = None
        self.history: list[SandboxResult] = []

    def start(self) -> None:
        if self.process is not None and self.process.is_alive():
            return
        self.process = Process(
            target=worker_entrypoint,
            args=(
                self.input_queue,
                self.output_queue,
                self.config.authorized_imports,
                self.mcp_config,
            ),
        )
        self.process.start()

    def run(self, python_code: str) -> SandboxResult:
        self.start()
        self.input_queue.put({
            "type": "run",
            "code": python_code,
        })

        try:
            raw_result = self.output_queue.get(
                timeout=self.config.max_execution_time_seconds,
            )
            result = SandboxResult(**raw_result)
        except Empty:
            self.stop(force=True)
            result = SandboxResult(
                stderr="Sandbox execution timed out",
                error="TimeoutError",
                success=False,
            )
        self.history.append(result)
        return result

    def stop(self, force: bool = False) -> None:
        if self.process is None:
            return
        if force:
            self.process.terminate()
            self.process.join()
            self.process = None
            return
        if self.process.is_alive():
            self.input_queue.put({"type": "stop"})
            self.process.join()

        self.process = None