import ast

class AstValidatorErr(Exception):
    pass

class AstValidator:
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

    def __init__(self, authorized_imports: list[str]) -> None:
        self.auth_imp = authorized_imports
        self.forbidden_func = {
            "eval",
            "exec",
            "open",
            "compile",
            "input",
            "__import__",
            "globals",
            "locals",
            "vars",
            "getattr",
            "setattr",
            "delattr",
            "breakpoint",
        }

    def validate(self, python_code: str) -> None:
        try:
            tree = ast.parse(python_code)
        except SyntaxError as error:
            raise AstValidatorErr(f"Invalid Python syntax: {error}") from error

        for node in ast.walk(tree):
            # if isinstance(node, ast.Import):
            #     self.validate_import(node)

            # elif isinstance(node, ast.ImportFrom):
            #     self.validate_import_from(node)

            # if isinstance(node, ast.Call):
            #     self.validate_call(node)

            if isinstance(node, ast.Attribute):
                self.validate_attribute(node)

            elif isinstance(node, ast.ExceptHandler):
                self.validate_except_handler(node)

    def validate_import(self, node: ast.Import) -> None:
        for alias in node.names:
            module_name = alias.name
            if not self.is_authorized_import(module_name, self.auth_imp):
                raise AstValidatorErr(f"Unauthorized import: {module_name}")

    def validate_import_from(self, node: ast.ImportFrom) -> None:
        module_name = node.module or ""
        if not self.is_authorized_import(module_name, self.auth_imp):
            raise AstValidatorErr(f"Unauthorized import: {module_name}")
        for importfrom in node.names:
            if (importfrom.name.startswith("_") or importfrom.name in self.FORBIDDEN_ATTRIBUTES):
                raise AstValidatorErr(f"Forbidden imported attribute: {importfrom.name}")

    def validate_call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
            if function_name in self.forbidden_func:
                raise AstValidatorErr(f"Forbidden function call: {function_name}")

    def validate_attribute(self, node: ast.Attribute) -> None:
        if (node.attr.startswith("_") or node.attr in self.FORBIDDEN_ATTRIBUTES):
            raise AstValidatorErr(f"Forbidden attribute access: {node.attr}")

    def validate_except_handler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            raise AstValidatorErr("Forbidden empty except")

    @classmethod
    def is_authorized_import(cls, module_name: str, authorized_imports: list[str]) -> bool:
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
        for forbidden in cls.FORBIDDEN_IMPORTS:
            if module_name == forbidden or module_name.startswith(forbidden + "."):
                return True
        return False