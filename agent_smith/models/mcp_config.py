from pydantic import BaseModel, Field, model_validator
from pathlib import Path
from typing import Literal


class SandboxMCPConfig(BaseModel):
    """Validated configuration for an MCP transport."""

    command: str = Field(default="python3", min_length=1)
    args: list[str] = Field(default_factory=list)
    cwd: Path = Field(default_factory=Path.cwd)
    transport: Literal["stdio", "http"] = "stdio"
    url: str | None = None

    @model_validator(mode="after")
    def validate_transport(self):
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("Command is required when using stdio")
        elif self.transport == "http":
            if not self.url:
                raise ValueError("URL is required when using http")
        return self
