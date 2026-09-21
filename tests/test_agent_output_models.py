import pytest
from pydantic import ValidationError

from agent_smith.models.agent_output import SolutionOutput, StepMetrics


def test_step_metrics_uses_subject_defaults_for_trace_fields() -> None:
    step = StepMetrics(
        step=1,
        input_tokens=12,
        output_tokens=4,
        request_time_ms=25.0,
    )

    assert step.api_url == ""
    assert step.model_name == ""
    assert step.llm_output == ""
    assert step.sandbox_input == ""
    assert step.sandbox_output == ""
    assert step.retries == 0
    assert step.timestamp


def test_step_metrics_keeps_core_metrics_required() -> None:
    with pytest.raises(ValidationError):
        StepMetrics(step=1, input_tokens=12, output_tokens=4)


def test_solution_output_uses_subject_defaults() -> None:
    solution = SolutionOutput(
        task_id="42",
        benchmark="mbpp",
        success=False,
        solution="",
        iterations=0,
        total_requests=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_time_seconds=0.0,
    )

    assert solution.steps == []
    assert solution.system_prompt == ""
    assert solution.error is None
    assert solution.timestamp
