from pydantic import BaseModel, Field, model_validator
from pathlib import Path
from typing import Literal


class SandboxMCPConfig(BaseModel):
    command: str = Field(default="python3", min_length=1, max_length=50)
    args: list[str] = Field(default_factory=list)
    cwd: Path = Field(default_factory=Path.cwd)
    transport: Literal["stdio", "http"] = "stdio"
    url: str | None = None

    @model_validator(mode="after")
    def validate_transport(self):
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("Command is required when using stdio")
            if not self.args:
                raise ValueError("Args are required when using stdio")
        if self.transport == "http" and not self.url:
            if not self.url:
                raise ValueError("URL is required when using http")
        return self
