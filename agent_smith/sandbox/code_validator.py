from agent_smith.sandbox.ast_validator import AstValidator, AstValidatorErr

class SandboxCodeValidatorErr(Exception):
    pass

class SandboxCodeValidator:
    @classmethod
    def validate(cls, python_code: str, authorized_imports: list[str]) -> None:
        ast_validator = AstValidator()
        try:
            ast_validator.validate(python_code)
        except AstValidatorErr as e:
            raise SandboxCodeValidatorErr(f"Sandbox Code Validation Error: {e}")