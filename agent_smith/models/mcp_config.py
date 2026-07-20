from pydantic import BaseModel, Field
from pathlib import Path

class SandboxMCPConfig(BaseModel):
    command: str = Field(default="python3", min_length=1, max_length=50)
    args: list[str] = Field(default_factory=lambda: ["mcp_tools_mbpp.py"])
    cwd: Path = Field(default_factory=Path.cwd)