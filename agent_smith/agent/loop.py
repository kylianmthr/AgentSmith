from openai.types.chat import ChatCompletionMessageParam
from agent_smith.agent.env_loader import DotEnvLoader
from agent_smith.sandbox.manager import SandboxManager
from agent_smith.llm.client import Client
from agent_smith.agent.code_extractor import CodeExtractor
from agent_smith.models.agent_output import SolutionOutput, StepMetrics
import time
import ast
import re

# What the moulinette checks before it even runs the evaluation.
PATCH_MARKERS = ("diff --git", "--- a/", "+++ b/", "@@")


class Agent:
    def __init__(
        self,
        sandbox: SandboxManager,
        sys_prompt: str,
        task: str,
        task_id: str,
        benchmark_name: str,
        provider: str,
        model_name: str,
        max_tokens: int,
        max_iterations: int,
        max_input_tokens: int,
        max_output_tokens: int,
        max_observation_chars: int = 4000,
        history_window: int = 8,
    ) -> None:
        self.sandbox = sandbox
        self.sys_prompt = sys_prompt
        self.task = task
        self.benchmark_name = benchmark_name
        self.provider = provider
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_observation_chars = max_observation_chars
        self.history_window = history_window
        self.result: SolutionOutput = SolutionOutput(
            task_id=task_id,
            benchmark=self.benchmark_name,
            success=False,
            solution="",
            system_prompt=sys_prompt,
            iterations=0,
            steps=[],
            total_requests=0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_time_seconds=0.0,
        )

    def truncate_observation(self, text: str) -> str:
        if len(text) <= self.max_observation_chars:
            return text
        dropped = len(text) - self.max_observation_chars
        return (
            f"{text[: self.max_observation_chars]}\n"
            f"[OBSERVATION TRUNCATED: {dropped} characters dropped. Narrow "
            "your next call to see the rest.]"
        )

    def build_observation(self, sandbox_res, warning: str | None) -> str:
        parts = []
        if warning:
            parts.append(f"warning: {warning}")
        parts.append(f"stdout: {self.truncate_observation(sandbox_res.stdout)}")
        if sandbox_res.stderr:
            parts.append(
                f"stderr: {self.truncate_observation(sandbox_res.stderr)}"
            )
        if sandbox_res.error:
            parts.append(f"code error: {sandbox_res.error}")
        if not sandbox_res.stdout.strip() and not sandbox_res.error:
            parts.append(
                "note: the observation is empty because your code printed "
                "nothing. Wrap every tool call in print()."
            )
        return "\n".join(parts)

    def trim_history(
        self, history: list[ChatCompletionMessageParam]
    ) -> list[ChatCompletionMessageParam]:
        """Keep the system prompt, the task, and the last exchanges.

        The cumulative input token budget is spent on every request, so an
        ever-growing history blows it long before the iteration limit.
        """
        head, tail = history[:2], history[2:]
        if len(tail) <= self.history_window:
            return history
        dropped = len(tail) - self.history_window
        note: ChatCompletionMessageParam = {
            "role": "user",
            "content": (
                f"[{dropped} earlier messages were dropped to stay within the "
                "input token budget. Work from the current state of the "
                "repository, re-read what you need instead of relying on "
                "those messages.]"
            ),
        }
        return head + [note] + tail[-self.history_window :]

    def rejected_final_answer(self, answer: str) -> str | None:
        """Reject invalid or unverified benchmark submissions."""
        if self.benchmark_name == "MBPP":
            return (
                "final_answer() was REJECTED because this candidate was not "
                "validated. Define it in `solution` and call exactly "
                "print(run_tests(solution)). Submission happens automatically "
                "when all official public tests pass."
            )
        if self.benchmark_name != "SWEBench":
            return None
        if any(marker in answer for marker in PATCH_MARKERS):
            return None
        return (
            "final_answer() was REJECTED: what you submitted is not a git "
            "patch. The solution must be the unified diff of your changes. "
            "Apply the fix with edit_file, check it with run_tests, then call "
            "final_answer(get_patch()). Never describe the fix in prose."
        )

    def budget_exceeded(self) -> str | None:
        if self.result.total_input_tokens >= self.max_input_tokens:
            return (
                f"Input token budget exhausted "
                f"({self.result.total_input_tokens}/{self.max_input_tokens})"
            )
        if self.result.total_output_tokens >= self.max_output_tokens:
            return (
                f"Output token budget exhausted "
                f"({self.result.total_output_tokens}/{self.max_output_tokens})"
            )
        return None

    @staticmethod
    def shadowed_sandbox_names(python_code: str) -> set[str]:
        """Detect attempts to overwrite the sandbox API."""
        reserved = {"final_answer", "run_tests"}
        try:
            tree = ast.parse(python_code)
        except SyntaxError:
            return set()
        shadowed = set()
        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                if node.name in reserved:
                    shadowed.add(node.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    if node.id in reserved:
                        shadowed.add(node.id)
            elif isinstance(node, ast.alias):
                assigned_name = node.asname or node.name.split(".")[0]
                if assigned_name in reserved:
                    shadowed.add(assigned_name)
        return shadowed

    @staticmethod
    def official_mbpp_tests_passed(
        python_code: str,
        stdout: str,
    ) -> bool:
        """Accept only one exact run_tests(solution) call."""
        try:
            tree = ast.parse(python_code)
        except SyntaxError:
            return False
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_tests"
        ]
        if len(calls) != 1:
            return False
        call = calls[0]
        if call.keywords or len(call.args) != 1:
            return False
        argument = call.args[0]
        if not isinstance(argument, ast.Name) or argument.id != "solution":
            return False
        match = re.fullmatch(
            r"\s*(\d+)/(\d+) tests passed\s*",
            stdout,
        )
        if match is None:
            return False
        passed = int(match.group(1))
        total = int(match.group(2))
        return total > 0 and passed == total

    @staticmethod
    def format_sandbox_log(sandbox_res) -> str:
        return (
            "[STDOUT]\n"
            f"{sandbox_res.stdout}\n"
            "[STDERR]\n"
            f"{sandbox_res.stderr}\n"
            "[ERROR]\n"
            f"{sandbox_res.error!r}\n"
            "[FINAL_ANSWER]\n"
            f"{sandbox_res.final_answer!r}\n"
            "[SUCCESS]\n"
            f"{sandbox_res.success}"
        )

    def execute(self):
        history: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.sys_prompt},
            {"role": "user", "content": self.task},
        ]
        dotenv = DotEnvLoader()
        dotenv.load()
        start_time = time.time()
        try:
            if not dotenv.api_key:
                raise ValueError("API Key not defined.")
            client = Client(
                api_url=self.provider,
                model_name=self.model_name,
                max_tokens=self.max_tokens,
                api_keys=dotenv.api_key,
            )
            extractor = CodeExtractor()
            i = 0
            while i < self.max_iterations:
                exhausted = self.budget_exceeded()
                if exhausted:
                    self.result.error = exhausted
                    break
                history = self.trim_history(history)
                self.result.iterations += 1
                res = client.generate(conversation=history)
                self.result.total_requests += 1
                self.result.total_input_tokens += res.input_tokens
                self.result.total_output_tokens += res.output_tokens
                print(f"=== LLM output (step {i + 1}) ===")
                print(res.llm_output)
                history.append(
                    {"role": "assistant", "content": res.llm_output}
                )
                extracted = extractor.extract(res.llm_output)
                if extracted.code is None:
                    print(f"=== No code extracted: {extracted.warning}")
                    history.append(
                        {"role": "user", "content": extracted.warning or ""}
                    )
                    self.result.steps.append(
                        StepMetrics(
                            step=i + 1,
                            input_tokens=res.input_tokens,
                            output_tokens=res.output_tokens,
                            request_time_ms=res.request_time_ms,
                            api_url=self.provider,
                            model_name=self.model_name,
                            llm_output=res.llm_output,
                            sandbox_input="",
                            sandbox_output=extracted.warning or "",
                            retries=res.retries,
                        )
                    )
                    i += 1
                    continue

                shadowed = self.shadowed_sandbox_names(extracted.code)
                if shadowed:
                    warning = (
                        "Do not define, assign, import, delete, or overwrite "
                        "these preloaded sandbox functions: "
                        + ", ".join(sorted(shadowed))
                        + ". Use them directly."
                    )
                    print(f"=== Code rejected: {warning}")
                    history.append(
                        {"role": "user", "content": warning}
                    )
                    self.result.steps.append(
                        StepMetrics(
                            step=i + 1,
                            input_tokens=res.input_tokens,
                            output_tokens=res.output_tokens,
                            request_time_ms=res.request_time_ms,
                            api_url=self.provider,
                            model_name=self.model_name,
                            llm_output=res.llm_output,
                            sandbox_input="",
                            sandbox_output=warning,
                            retries=res.retries,
                        )
                    )
                    i += 1
                    continue

                print("=== Code sent to sandbox ===")
                print(extracted.code)
                sandbox_res = self.sandbox.run(extracted.code)
                observation = self.build_observation(
                    sandbox_res, extracted.warning
                )
                self.result.steps.append(
                    StepMetrics(
                        step=i + 1,
                        input_tokens=res.input_tokens,
                        output_tokens=res.output_tokens,
                        request_time_ms=res.request_time_ms,
                        api_url=self.provider,
                        model_name=self.model_name,
                        llm_output=res.llm_output,
                        sandbox_input=extracted.code,
                        sandbox_output=self.format_sandbox_log(sandbox_res),
                        retries=res.retries,
                    )
                )
                if sandbox_res.final_answer is not None:
                    rejection = self.rejected_final_answer(
                        sandbox_res.final_answer
                    )
                    if rejection is None:
                        self.result.success = True
                        self.result.solution = sandbox_res.final_answer
                        break
                    observation = rejection
                    self.result.steps[-1].sandbox_output += (
                        "\n\n[AGENT DECISION]\n"
                        + rejection
                    )

                if (
                    self.benchmark_name == "MBPP"
                    and not sandbox_res.error
                    and self.official_mbpp_tests_passed(
                        extracted.code,
                        sandbox_res.stdout,
                    )
                ):
                    print(
                        "=== Official MBPP tests passed: "
                        "submitting automatically ==="
                    )
                    submission_code = "final_answer(solution)"
                    submission_res = self.sandbox.run(submission_code)

                    current_step = self.result.steps[-1]
                    current_step.sandbox_input += (
                        "\n\n[AUTOMATIC SUBMISSION]\n"
                        + submission_code
                    )
                    current_step.sandbox_output += (
                        "\n\n[AUTOMATIC SUBMISSION RESULT]\n"
                        + self.format_sandbox_log(submission_res)
                    )
                    if submission_res.final_answer is not None:
                        self.result.success = True
                        self.result.solution = submission_res.final_answer
                        break
                if self.sandbox.broken:
                    self.result.error = (
                        "Sandbox is unrecoverable: "
                        f"{sandbox_res.error or 'unknown'}"
                    )
                    break
                history.append({"role": "user", "content": observation})
                i += 1
                print("=== Observation ===")
                print(observation)
        except Exception as e:
            self.result.error = str(e)
        self.result.total_time_seconds = time.time() - start_time
        self.sandbox.stop()
        return self.result
