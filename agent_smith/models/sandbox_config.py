from typing import List

from pydantic import BaseModel, Field, field_validator


SAFE_IMPORTS = [
    "math",
    "math.*",
    "collections",
    "collections.*",
    "itertools",
    "re",
    "json",
    "typing",
    "typing.*",
    "functools",
    "operator",
    "heapq",
    "bisect",
    "copy",
    "string",
    "random",
    "datetime",
    "datetime.*",
    "array",
    "cmath",
]

class SandboxConfig(BaseModel):
    """Sandbox configuration for student solutions.

    authorized_imports is configurable, but only as a subset of SAFE_IMPORTS.
    The config can make the sandbox stricter, not more permissive.
    """
    authorized_imports: List[str] = Field(
        default_factory=lambda: SAFE_IMPORTS.copy()
    )
    allowed_directories: List[str] = Field(
        default_factory=lambda: ["/testbed", "/tmp/agent"],
        min_length=1,
    )
    max_execution_time_seconds: int = Field(
        default=30,
        ge=1,
        le=900,
    )
    max_memory_mb: int = Field(
        default=512,
        ge=64,
        le=4096,
    )

    @field_validator("authorized_imports")
    @classmethod
    def validate_authorized_imports(cls, imports: list[str]) -> list[str]:
        for module_name in imports:
            if module_name not in SAFE_IMPORTS:
                raise ValueError(
                    f"Import not allowed in sandbox config: {module_name}. "
                    f"Allowed imports are: {SAFE_IMPORTS}"
                )

        return imports