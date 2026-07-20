from pydantic import BaseModel, Field

class SandboxResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    final_answer: str | None = None
    success: bool = False