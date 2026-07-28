from pathlib import Path

from agent_smith.sandbox.manager import SandboxManager, SandboxManagerError
from agent_smith.llm.client import Client
from agent_smith.extractor.manager import ExtractorManager
from agent_smith.models.result import SandboxResult


class OrchestratorError(Exception):
    pass

class Orchestrator:
    def __init__(
        self,
        config_path: Path | None,
        max_iterations: int,
        api_url: str,
        model_name: str,
        max_tokens: int,
        api_key: str,
        stop: str = "<end_code>",
        mcp_config: dict | None = None,
    ) -> None:
        self.llm = None
        self.sandbox = None
        self.extractor = None
        self.conversation = []
        self.max_iterations = max_iterations #valider config plus tard
        try:
            self.extractor = ExtractorManager()
            self.llm = Client(
                api_url,
                model_name,
                max_tokens,
                api_key,
                stop
                )
            self.sandbox = SandboxManager(config_path, mcp_config)
        except SandboxManagerError as e:
            raise OrchestratorError(e)
        except Exception as e:
            raise OrchestratorError(e)

    def run_loop(self) -> None | str:
        if not self.llm or not self.sandbox or not self.extractor:
            return
        try:
            for _ in range(self.max_iterations):
                response = self.llm.generate(self.conversation)
                extracted_code = self.extractor.extract(response.llm_output)
                if extracted_code == "":
                    break
                result = self.sandbox.run(extracted_code)
                if self.check_is_done(result):
                    return result.final_answer
        finally:
            self.sandbox.stop()

    def check_is_done(self, result: SandboxResult) -> bool:
        if not self.sandbox:
            return False
        if not result.success:
            return False

        if result.final_answer is None:
            return False

        test_code = f"print(run_tests({result.final_answer!r}))"
        test_result = self.sandbox.run(test_code)

        if not test_result.success:
            return False

        return "tests passed" in test_result.stdout