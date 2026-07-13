import ast

class SandboxCodeValidator:
    @classmethod
    def validate(cls, python_code: str, authorized_imports: list[str]) -> bool:
        return True