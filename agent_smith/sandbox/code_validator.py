from agent_smith.sandbox.ast_validator import AstValidator, AstValidatorErr

class SandboxCodeValidatorErr(Exception):
    """Report code rejected before sandbox execution."""

    pass

class SandboxCodeValidator:
    """Coordinate static validation of generated Python code."""

    @classmethod
    def validate(cls, python_code: str, authorized_imports: list[str]) -> None:
        """Validate generated code against sandbox restrictions."""

        ast_validator = AstValidator()
        try:
            ast_validator.validate(python_code)
        except AstValidatorErr as e:
            raise SandboxCodeValidatorErr(f"Sandbox Code Validation Error: {e}")
