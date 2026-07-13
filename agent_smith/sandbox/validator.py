from pydantic import ValidationError
from agent_smith.models.sandbox_config import SandboxConfig
from pathlib import Path


class SandboxConfigValidator:
    @staticmethod
    def load(config_path: Path | None) -> SandboxConfig:
        if config_path is None:
            return SandboxConfig()

        try:
            config_json = config_path.read_text(encoding="utf-8")
            return SandboxConfig.model_validate_json(config_json)

        except FileNotFoundError as error:
            raise ValueError(
                f"Sandbox configuration not found: {config_path}"
            ) from error

        except OSError as error:
            raise ValueError(
                f"Cannot read sandbox configuration: {config_path}"
            ) from error

        except ValidationError as error:
            raise ValueError(
                f"Invalid sandbox configuration: {error}"
            ) from error
