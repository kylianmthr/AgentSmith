from pathlib import Path
from agent_smith.sandbox.validator import SandboxConfigValidator


class SandboxManager:
    def __init__(self, config_path: Path | None) -> None:
        self.config = SandboxConfigValidator.load(config_path)