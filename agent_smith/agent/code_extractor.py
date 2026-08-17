from abc import ABC, abstractmethod
import re
import html
import ast
import json


class JSONMalformed(ValueError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class CodeExtractor:
    def __init__(self) -> None:
        self.extractors: list[Extractor] = [
            PythonExtractor(),
            XMLExtractor(),
            HermesExctractor(),
            ReActExtractor(),
        ]

    def extract(self, llm_output: str) -> str:
        i = 0
        while i < len(self.extractors):
            try:
                res = self.extractors[i].extract(llm_output)
                return res
            except ValueError:
                i += 1
        return llm_output


class Extractor(ABC):
    @abstractmethod
    def extract(self, prompt: str) -> str:
        pass

    def transform(self, raw: str):
        raw = html.unescape(raw).strip()
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return raw


class PythonExtractor(Extractor):
    def extract(self, prompt: str) -> str:
        pattern = r"```(?:python)?\n?(.*?)\n?```"
        match = re.search(pattern, prompt, re.DOTALL)

        if match:
            code = match.group(1)
            return code
        else:
            raise ValueError("No python code block was found")


class XMLExtractor(Extractor):
    INVOKE_RE = re.compile(
        r'<invoke name="(?P<name>[^"]+)">(?P<content>.*?)</invoke>', re.DOTALL
    )
    PARAM_RE = re.compile(
        r'<parameter name="(?P<name>[^"]+)">(?P<value>.*?)</parameter>',
        re.DOTALL,
    )

    def extract(self, prompt: str) -> str:
        match = self.INVOKE_RE.search(prompt)
        if not match:
            raise ValueError("No XML code block was found")

        func_name = match.group("name")
        parameters = [
            f"{p.group('name')}={self.transform(p.group('value'))!r}"  # !r = repr
            for p in self.PARAM_RE.finditer(match.group("content"))
        ]
        return f"result = {func_name}({', '.join(parameters)})"


class JSONExtractor:
    def extract(self, prompt: str) -> dict:
        try:
            call = json.loads(prompt)
            return call
        except json.JSONDecodeError as e:
            raise JSONMalformed(f"Malformed JSON tool call: {e}")


class HermesExctractor(Extractor):
    TOOL_CALL_RE = re.compile(
        r"<tool_call>\s*(?P<json>\{.*?\})\s*</tool_call>", re.DOTALL
    )

    def extract(self, prompt: str) -> str:
        match = self.TOOL_CALL_RE.search(prompt)
        if not match:
            raise ValueError("No JSON tool call was found")
        call = JSONExtractor().extract(match.group("json"))
        func_name = call["name"]
        arguments = call.get("arguments", {})
        parameters = [f"{key}={value!r}" for key, value in arguments.items()]
        return f"result = {func_name}({', '.join(parameters)})"


class ReActExtractor(Extractor):
    def extract(self, prompt: str) -> str:
        pattern = (
            r"Action:\s*(?P<name>\S+)(?:\s*Action Input:\s*(?P<input>.*))?"
        )
        match = re.search(pattern, prompt, re.DOTALL)
        if not match:
            raise ValueError("No ReAct code block was found")
        func_name = match.group("name")
        raw_input = match.group("input")
        if not raw_input or not raw_input.strip():
            return f"result = {func_name}()"
        try:
            parameters_json = JSONExtractor().extract(raw_input.strip())
            parameters = [
                f"{key}={value!r}" for key, value in parameters_json.items()
            ]
            return f"result = {func_name}({', '.join(parameters)})"
        except Exception:
            return f"result = {func_name}({raw_input!r})"
