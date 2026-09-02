from abc import ABC, abstractmethod
from dataclasses import dataclass
import re
import html
import ast
import json


class JSONMalformed(ValueError):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


@dataclass
class ExtractedCode:
    """What the loop should run, plus what the model must be told about it.

    code is None when nothing runnable was found: the loop then feeds the
    warning back as the observation instead of executing anything.
    """

    code: str | None
    warning: str | None = None


NO_CODE_BLOCK = (
    "No valid Python code block was found in your response, so nothing was "
    "executed. Answer with exactly one ```python ... ``` block terminated by "
    "<end_code>."
)

TRUNCATED_UNPARSABLE = (
    "Your code block was cut off before its closing ``` and does not parse, so "
    "nothing was executed. Your response hit the output token limit: write a "
    "much shorter Thought and a smaller code block."
)

TRUNCATED_INTERPRETED = (
    "Your code block was never closed by ``` (your response was cut off). It "
    "was interpreted anyway, up to the end of your output. Keep your next "
    "response shorter."
)

BARE_CODE_INTERPRETED = (
    "Your response contained no ```python fence. The whole answer parsed as "
    "Python and was interpreted as code. Use a fenced block next time."
)


class CodeExtractor:
    def __init__(self) -> None:
        self.extractors: list[Extractor] = [
            PythonExtractor(),
            XMLExtractor(),
            HermesExctractor(),
            ReActExtractor(),
        ]
        self.salvagers: list[tuple[Extractor, str]] = [
            (TruncatedPythonExtractor(), TRUNCATED_INTERPRETED),
            (BareCodeExtractor(), BARE_CODE_INTERPRETED),
        ]

    def extract(self, llm_output: str) -> ExtractedCode:
        for extractor in self.extractors:
            try:
                return ExtractedCode(code=extractor.extract(llm_output))
            except ValueError:
                continue
        for salvager, warning in self.salvagers:
            try:
                code = salvager.extract(llm_output)
            except ValueError:
                continue
            if not self.is_parsable(code):
                return ExtractedCode(code=None, warning=TRUNCATED_UNPARSABLE)
            return ExtractedCode(code=code, warning=warning)
        return ExtractedCode(code=None, warning=NO_CODE_BLOCK)

    @staticmethod
    def is_parsable(code: str) -> bool:
        try:
            ast.parse(code)
        except (SyntaxError, ValueError):
            return False
        return True


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


class TruncatedPythonExtractor(Extractor):
    """Salvage a fenced block whose closing ``` never arrived."""

    OPEN_RE = re.compile(r"```(?:python)?\n(?P<code>.*)\Z", re.DOTALL)

    def extract(self, prompt: str) -> str:
        match = self.OPEN_RE.search(prompt)
        if not match:
            raise ValueError("No unterminated python code block was found")
        code = match.group("code")
        if not code.strip():
            raise ValueError("Unterminated python code block is empty")
        return code


class BareCodeExtractor(Extractor):
    """Last resort: the whole answer is Python with no fence at all."""

    def extract(self, prompt: str) -> str:
        code = prompt.strip()
        if not code:
            raise ValueError("Empty response")
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError) as error:
            raise ValueError("Response is not bare Python code") from error
        if not any(isinstance(node, ast.Call) for node in ast.walk(tree)):
            raise ValueError("Bare code calls nothing, it is prose")
        return code
