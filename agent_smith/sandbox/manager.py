from multiprocessing import Process, Queue
from queue import Empty
from pathlib import Path
from typing import Any

from agent_smith.sandbox.config_validator import (
    SandboxConfigValidator,
    SandboxConfigError,
)
from agent_smith.models.result import SandboxResult
from agent_smith.sandbox.worker import worker_entrypoint


class SandboxManagerError(Exception):
    pass


class SandboxManager:
    """
    Usage:

    NO MCP:
    uv run sandbox

    NO MCP + custom sandbox config:
    uv run sandbox sandbox_config.json

    STDIO MCP:
    uv run sandbox --mcp-stdio "python3 mcp_tools_mbpp.py --task task.json"

    STDIO MCP + custom sandbox config:
    uv run sandbox --mcp-stdio "python3 mcp_tools_mbpp.py --task task.json" sandbox_config.json

    HTTP MCP, server already running:
    uv run sandbox --mcp-server http://127.0.0.1:9000/mcp

    HTTP MCP, server already running + custom sandbox config:
    uv run sandbox --mcp-server http://127.0.0.1:9000/mcp sandbox_config.json

    HTTP MCP with autostart:
    uv run sandbox --mcp-server http://127.0.0.1:9000/mcp --autostart "python3 mcp_tools_mbpp.py --task task.json"

    HTTP MCP with autostart + custom sandbox config:
    uv run sandbox --mcp-server http://127.0.0.1:9000/mcp --autostart "python3 mcp_tools_mbpp.py --task task.json" sandbox_config.json
    
    To run HTTP server independently:
    uv run python mcp_tools_mbpp.py \
    --transport http \
    --task task.json \
    --host 127.0.0.1 \
    --port 9000 \
    --path /mcp
    then in another terminal:
    uv run sandbox --mcp-server http://127.0.0.1:9000/mcp
    """

    def __init__(
        self,
        config_path: Path | None,
        mcp_config: dict[str, Any] | None = None,
    ) -> None:
        self.start_timeout = 120
        try:
            self.config = SandboxConfigValidator.load(config_path)
            if mcp_config is None:
                self.mcp_config = None
            else:
                self.mcp_config = mcp_config
            self.input_queue = Queue()
            self.output_queue = Queue()
            self.process: Process | None = None
            self.history: list[SandboxResult] = []
        except (SandboxConfigError, TypeError) as e:
            raise SandboxManagerError(e)

    def list_tools(self) -> list[str]:
        self.start()
        self.input_queue.put({"type": "list_tools"})
        return self.output_queue.get(timeout=self.config.max_execution_time_seconds)

    def start(self) -> None:
        if self.process is not None and self.process.is_alive():
            return
        self.process = Process(
            target=worker_entrypoint,
            args=(
                self.input_queue,
                self.output_queue,
                self.config.authorized_imports,
                self.config.allowed_directories,
                self.config.max_memory_mb,
                self.mcp_config,
            ),
        )
        self.process.start()
        try:
            message = self.output_queue.get(timeout=self.start_timeout)
        except Empty as error:
            self.stop(force=True)
            raise SandboxManagerError(
                "Sandbox worker startup timed out"
            ) from error

        if message.get("type") != "ready":
            self.stop(force=True)
            raise SandboxManagerError(
                message.get("error", "Sandbox worker startup failed")
            )

    def run(self, python_code: str) -> SandboxResult:
        self.start()
        self.input_queue.put(
            {
                "type": "run",
                "code": python_code,
            }
        )
        try:
            raw_result = self.output_queue.get(
                timeout=self.config.max_execution_time_seconds,
            )
            result = SandboxResult(**raw_result)
        except Empty:
            self.stop(force=True)
            result = SandboxResult(
                stderr=f"Sandbox execution timed out after {self.config.max_execution_time_seconds} seconds",
                error="TimeoutError",
                success=False,
            )
        self.history.append(result)
        return result

    def stop(self, force: bool = False) -> None:
        if self.process is None:
            return
        try:
            if force:
                self.process.terminate()
            elif self.process.is_alive():
                self.input_queue.put({"type": "stop"})
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=2)
        finally:
            self.process = None
