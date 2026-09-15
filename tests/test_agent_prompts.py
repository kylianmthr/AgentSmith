from agent_mbpp.__main__ import build_system_prompt as build_mbpp_prompt
from agent_swebench.__main__ import build_system_prompt as build_swebench_prompt


def test_mbpp_prompt_requires_early_testing_and_evidence_driven_retries() -> None:
    prompt = build_mbpp_prompt("run_tests(solution: str)")

    assert "run_tests(solution: str)" in prompt
    assert "first response" in prompt
    assert "calculate your actual result" in prompt
    assert "never resubmit equivalent logic" in prompt
    assert "final_answer(solution)" in prompt


def test_swebench_prompt_does_not_trust_wrapper_status_alone() -> None:
    prompt = build_swebench_prompt("run_tests()")

    assert "run_tests()" in prompt
    assert "complete test summary" in prompt
    assert "exit code alone are not proof" in prompt
    assert "After verified passing tests" in prompt
    assert "final_answer(get_patch())" in prompt
