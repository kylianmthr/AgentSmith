import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from agent_smith.agent.loop import Agent
from agent_smith.models.task_input import MBPPTaskInput
from agent_smith.sandbox.manager import SandboxManager

MAX_INPUT_TOKENS = 5_000
MAX_OUTPUT_TOKENS = 1_200


def _error_summary(error: Exception) -> str:
    """Return one concise line for a command-line error."""

    if isinstance(error, ValidationError):
        issue = error.errors(include_url=False)[0]
        location = ".".join(str(part) for part in issue["loc"])
        prefix = f"{location}: " if location else ""
        return f"invalid task data ({prefix}{issue['msg']})"
    return str(error).strip().splitlines()[0] or type(error).__name__


def build_system_prompt(parsed_tools: str) -> str:
    """Build the MBPP system prompt and tool manual."""

    return (
        "You are a precise MBPP Python solver. Return the smallest general "
        "solution and finish quickly.\n"
        "TOOLS\n"
        f"{parsed_tools}\n"
        "RESPONSE CONTRACT\n"
        "- Every response must contain exactly one complete ```python ... ``` "
        "block followed by <end_code>, with no text before or after it.\n"
        "- Your first response must assign complete, runnable source to "
        "`solution` and immediately call print(run_tests(solution)). Never "
        "spend an iteration on analysis, comments, docstrings, or debug code.\n"
        "- Put all source and imports inside `solution`. Outside it, the only "
        "testing statement allowed is exactly print(run_tests(solution)).\n"
        "- Call run_tests once with exactly one positional argument. Never pass "
        "its optional test_list argument, add custom assertions, call candidate "
        "functions directly, use input(), or redefine tools.\n"
        "- After all tests pass, the very next response must be exactly:\n"
        "```python\n"
        "final_answer(solution)\n"
        "```<end_code>\n"
        "SOLVING RULES - APPLY SILENTLY\n"
        "- Infer the canonical operation from the task name, required signature, "
        "wording, and every example together. Do not fit isolated examples.\n"
        "- Before testing, dry-run every public assertion. Check the exact return "
        "type, ordering, multiplicity, inclusive or exclusive bounds, equality, "
        "empty inputs, and one-item inputs when relevant.\n"
        "- On failure, re-read the failing assertion, calculate your actual result "
        "and compare it with the expected value. Change the assumption this disproves; "
        "never resubmit equivalent logic or guess unexplained constants.\n"
        "- Prefer a direct formula, loop, comprehension, standard-library call, "
        "or small recurrence. Keep code compact enough to finish the response.\n"
        "- One discriminating test is hidden. Preserve general behavior beyond "
        "the public examples, including ordering and duplicate handling.\n"
        "TEMPLATE\n"
        "```python\n"
        "solution = '''def add(a, b):\n"
        "    return a + b\n"
        "'''\n"
        "print(run_tests(solution))\n"
        "```<end_code>"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI for mbpp agent")
    parser.add_argument(
        "--task-file",
        type=str,
        default="cache/mbpp_task.json",
        help="Path to the task.json file",
    )
    parser.add_argument(
        "--output-file",
        "--output",
        dest="output_file",
        type=str,
        default="cache/mbpp_solution.json",
        help="Path to the output file",
    )
    parser.add_argument(
        "--sandbox-config",
        type=str,
        default=None,
        help="Optional path to a sandbox configuration file",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="qwen/qwen3.8-27b",
        help="Name of the model to use",
    )
    parser.add_argument(
        "--provider-url",
        type=str,
        default="https://api.groq.com/openai/v1",
        help="URL of the LLM provider",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of agent loop iterations (limit: 10)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=420,
        help="Maximum output tokens per LLM request",
    )
    args = parser.parse_args()
    manager = None
    try:
        task_path = Path(args.task_file)
        sandbox_config_path = Path(args.sandbox_config) if args.sandbox_config else None
        with open(task_path, "r") as f:
            json_data = f.read()
            task = MBPPTaskInput.model_validate_json(json_data)
            mcp_config = {
                "command": sys.executable,
                "args": [
                    "mcp_tools_mbpp.py",
                    "--task",
                    str(task_path),
                ],
                "cwd": str(Path.cwd()),
                "transport": "stdio",
            }
            manager = SandboxManager(sandbox_config_path, mcp_config=mcp_config)
            tools = manager.list_tools()
            parsed_tools = "\n".join(tools)
            visible_tests = "\n".join(task.test_list)
            task_str = (
                "TASK\n"
                f"{task.task_definition}\n\n"
                "REQUIRED SIGNATURE\n"
                f"{task.function_definition}\n\n"
                "PUBLIC TESTS (all must pass; hidden tests also exist)\n"
                f"{visible_tests}\n\n"
                "Solve the general problem, not only these examples."
            )
            sys_prompt = build_system_prompt(parsed_tools)
            agent = Agent(
                sandbox=manager,
                sys_prompt=sys_prompt,
                task=task_str,
                task_id=str(task.task_id),
                benchmark_name="MBPP",
                provider=args.provider_url,
                model_name=args.model_name,
                max_tokens=args.max_tokens,
                max_iterations=args.max_iterations,
                max_input_tokens=MAX_INPUT_TOKENS,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                max_observation_chars=1500,
                history_window=4,
            )
            res = agent.execute()
            path = Path(args.output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(res.model_dump_json(indent=4))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"Error: {_error_summary(error)}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        if manager is not None:
            manager.stop()
