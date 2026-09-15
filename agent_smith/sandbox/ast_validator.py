import ast


class AstValidatorErr(Exception):
    """Report rejected syntax or AST constructs."""

    pass


class AstValidator:
    """Reject dangerous syntax before sandbox execution."""

    FORBIDDEN_IMPORTS = {
        "socket",
        "ssl",
        "http",
        "urllib",
        "requests",
        "subprocess",
        "os",
        "sys",
        "pathlib",
        "shutil",
        "ftplib",
        "smtplib",
        "telnetlib",
        "importlib",
        "builtins",
        "webbrowser",
        "pickle",
        "marshal",
        "shelve",
    }

    FORBIDDEN_ATTRIBUTES = {
        "sys",
        "modules",
        "builtins",
        "os",
        "subprocess",
        "pathlib",
        "shutil",
        "open",
        "popen",
        "system",
        "attrgetter",
        "methodcaller",
        "Formatter",
        "get_field",
    }

    def validate(self, python_code: str) -> None:
        """Parse code and validate its relevant AST nodes."""

        try:
            tree = ast.parse(python_code)
        except SyntaxError as error:
            raise AstValidatorErr(f"Invalid Python syntax: {error}") from error

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.validate_attribute(node)
            elif isinstance(node, ast.ExceptHandler):
                self.validate_except_handler(node)

    def validate_attribute(self, node: ast.Attribute) -> None:
        """Reject private and explicitly forbidden attributes."""

        if (node.attr.startswith("_") or node.attr in self.FORBIDDEN_ATTRIBUTES):
            raise AstValidatorErr(f"Forbidden attribute access: {node.attr}")

    def validate_except_handler(self, node: ast.ExceptHandler) -> None:
        """Reject bare exception handlers that can swallow interrupts."""

        if node.type is None:
            raise AstValidatorErr("Forbidden empty except")

    @classmethod
    def is_authorized_import(cls, module_name: str, authorized_imports: list[str]) -> bool:
        """Return whether a module matches the configured allowlist."""

        if cls.is_forbidden_import(module_name):
            return False
        for authorized in authorized_imports:
            if authorized.endswith(".*"):
                prefix = authorized[:-2]
                if module_name == prefix or module_name.startswith(prefix + "."):
                    return True
            elif module_name == authorized:
                return True
        return False

    @classmethod
    def is_forbidden_import(cls, module_name: str) -> bool:
        """Return whether a module belongs to the hard denylist."""

        for forbidden in cls.FORBIDDEN_IMPORTS:
            if module_name == forbidden or module_name.startswith(forbidden + "."):
                return True
        return False
