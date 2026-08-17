from openai.types.chat import ChatCompletionMessageParam
from agent_smith.agent.env_loader import DotEnvLoader
from agent_smith.sandbox.manager import SandboxManager
from agent_smith.llm.client import Client
from agent_smith.agent.code_extractor import CodeExtractor
from agent_smith.models.agent_output import SolutionOutput, StepMetrics
import time


class Agent:
    def __init__(
        self,
        sandbox: SandboxManager,
        sys_prompt: str,
        task: str,
        task_id: int,
        limits: int,
        benchmark_name: str,
        provider: str,
        model_name: str,
    ) -> None:
        self.sandbox = sandbox
        self.sys_prompt = sys_prompt
        self.task = task
        self.limits = limits
        self.benchmark_name = benchmark_name
        self.provider = provider
        self.model_name = model_name
        self.result: SolutionOutput = SolutionOutput(
            task_id=str(task_id),
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

    def execute(self):
        history: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.sys_prompt},
            {"role": "user", "content": self.task},
        ]
        dotenv = DotEnvLoader()
        dotenv.load()
        start_time = time.time()
        max_retries = 10 if self.benchmark_name == "MBPP" else 30
        try:
            if not dotenv.api_key:
                raise ValueError("API Key not defined.")
            client = Client(
                api_url=self.provider,
                model_name=self.model_name,
                max_tokens=self.limits,
                api_keys=dotenv.api_key,
            )
            extractor = CodeExtractor()
            i = 0
            while i < max_retries:
                self.result.iterations += 1
                res = client.generate(conversation=history)
                self.result.total_requests += 1
                self.result.total_input_tokens += res.input_tokens
                self.result.total_output_tokens += res.output_tokens
                print("=== LLM output ===")
                print(res.llm_output)
                print("==================")
                history.append(
                    {"role": "assistant", "content": res.llm_output}
                )
                code = extractor.extract(res.llm_output)
                print(code)
                sandbox_res = self.sandbox.run(code)
                step = StepMetrics(
                    step=i + 1,
                    input_tokens=res.input_tokens,
                    output_tokens=res.output_tokens,
                    request_time_ms=res.request_time_ms,
                    api_url=self.provider,
                    model_name=self.model_name,
                    llm_output=res.llm_output,
                    sandbox_input=code,
                    sandbox_output=sandbox_res.stdout,
                    retries=res.retries,
                )
                self.result.steps.append(step)
                if sandbox_res.final_answer:
                    self.result.success = True
                    self.result.solution = sandbox_res.final_answer
                    break
                history.append(
                    {
                        "role": "user",
                        "content": f"stdout: {sandbox_res.stdout}\nstderr: {sandbox_res.stderr}\ncode error: {sandbox_res.error}",
                    }
                )
                i += 1
                print("==== Sandbox res ====")
                print(sandbox_res)
                print("====== History ======")
                print(history)
                print("=====================")
        except Exception as e:
            self.result.error = str(e)
        self.result.total_time_seconds = time.time() - start_time
        self.sandbox.stop()
        return self.result
