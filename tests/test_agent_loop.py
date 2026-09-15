import pytest

from agent_smith.agent import loop as loop_module
from agent_smith.agent.loop import Agent
from agent_smith.llm.response import LLMResponse
from agent_smith.models.result import SandboxResult


class FakeSandbox:
    def __init__(self, result: SandboxResult) -> None:
        self.result = result
        self.broken = False
        self.stopped = False

    def run(self, _python_code: str) -> SandboxResult:
        return self.result

    def stop(self) -> None:
        self.stopped = True


class FakeDotEnvLoader:
    def __init__(self) -> None:
        self.api_key = None

    def load(self) -> None:
        self.api_key = ["test-key"]


class FakeClient:
    response = LLMResponse(
        input_tokens=11,
        output_tokens=7,
        request_time_ms=2.5,
        retries=2,
        llm_output="```python\nfinal_answer('done')\n```",
    )

    def __init__(self, **_kwargs) -> None:
        self.total_requests = 0

    def generate(self, conversation) -> LLMResponse:
        self.total_requests += 1 + self.response.retries
        return self.response


class FakeFailingClient:
    def __init__(self, **_kwargs) -> None:
        self.total_requests = 0

    def generate(self, conversation) -> LLMResponse:
        self.total_requests += 4
        raise RuntimeError("provider unavailable")


def make_agent(sandbox: FakeSandbox) -> Agent:
    return Agent(
        sandbox=sandbox,
        sys_prompt="system",
        task="task",
        task_id="42",
        benchmark_name="MBPP",
        provider="https://example.test/v1",
        model_name="test-model",
        max_tokens=100,
        max_iterations=1,
        max_input_tokens=1000,
        max_output_tokens=1000,
    )


def test_execute_counts_initial_request_and_retries_and_records_full_log(
    monkeypatch,
) -> None:
    sandbox = FakeSandbox(
        SandboxResult(
            stdout="candidate output\n",
            stderr="candidate warning\n",
            error=None,
            final_answer="done",
            success=True,
        )
    )
    monkeypatch.setattr(loop_module, "DotEnvLoader", FakeDotEnvLoader)
    monkeypatch.setattr(loop_module, "Client", FakeClient)

    result = make_agent(sandbox).execute()

    assert result.success is True
    assert result.total_requests == 3
    assert result.steps[0].retries == 2
    assert result.steps[0].sandbox_output == (
        "[STDOUT]\n"
        "candidate output\n\n"
        "[STDERR]\n"
        "candidate warning\n\n"
        "[ERROR]\n"
        "None\n"
        "[FINAL_ANSWER]\n"
        "'done'\n"
        "[SUCCESS]\n"
        "True"
    )
    assert sandbox.stopped is True


def test_execute_stops_sandbox_when_control_flow_propagates(monkeypatch) -> None:
    sandbox = FakeSandbox(SandboxResult())

    def interrupt(_self, _python_code: str) -> SandboxResult:
        raise KeyboardInterrupt

    monkeypatch.setattr(loop_module, "DotEnvLoader", FakeDotEnvLoader)
    monkeypatch.setattr(loop_module, "Client", FakeClient)
    monkeypatch.setattr(FakeSandbox, "run", interrupt)

    with pytest.raises(KeyboardInterrupt):
        make_agent(sandbox).execute()

    assert sandbox.stopped is True


def test_execute_counts_attempts_when_all_retries_fail(monkeypatch) -> None:
    sandbox = FakeSandbox(SandboxResult())
    monkeypatch.setattr(loop_module, "DotEnvLoader", FakeDotEnvLoader)
    monkeypatch.setattr(loop_module, "Client", FakeFailingClient)

    result = make_agent(sandbox).execute()

    assert result.success is False
    assert result.error == "provider unavailable"
    assert result.total_requests == 4
    assert sandbox.stopped is True
