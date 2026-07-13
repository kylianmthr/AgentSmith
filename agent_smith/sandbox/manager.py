from pathlib import Path
from agent_smith.sandbox.config_validator import SandboxConfigValidator
from agent_smith.sandbox.result import SandboxResult
from agent_smith.sandbox.code_validator import SandboxCodeValidator


class SandboxManager:
    def __init__(self, config_path: Path | None) -> None:
        self.config = SandboxConfigValidator.load(config_path)


    def run(self, python_code: str) -> SandboxResult:
        result = SandboxResult()
        valid = SandboxCodeValidator.validate(python_code, self.config.authorized_imports)
        if not valid:
            result.stderr = "Invalid python code"
        return result
        
