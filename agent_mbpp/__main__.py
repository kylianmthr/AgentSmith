import argparse
import sys
from pathlib import Path

from agent_smith.agent.loop import Agent
from agent_smith.models.task_input import MBPPTaskInput
from agent_smith.sandbox.manager import SandboxManager

MAX_INPUT_TOKENS = 6_000
MAX_OUTPUT_TOKENS = 1_500

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
        default=350,
        help=(
            "Maximum output tokens per LLM request"
        ),
    )
    args = parser.parse_args()
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
            sys_prompt = (
            "You are a precise MBPP Python solver. Solve the general task with the "
            "shortest reliable implementation.\n"
            "TOOLS\n"
            f"{parsed_tools}\n"
            "STRICT PROTOCOL\n"
            "- Reply with exactly one complete Python block ending with <end_code>; "
            "no prose, reasoning, comments, docstrings, JSON, or extra blocks.\n"
            "- Put all source and imports in `solution`.\n"
            "- The only statement outside `solution` must be exactly:\n"
            "print(run_tests(solution))\n"
            "- Call run_tests once with exactly one positional argument. The optional "
            "`test_list` parameter is FORBIDDEN: never pass custom tests or assertions.\n"
            "- Never call candidate functions, input(), final_answer, or redefine tools.\n"
            "REASON SILENTLY\n"
            "- One discriminating test is hidden. Do not overfit public examples.\n"
            "- Dry-run every assertion and consider empty, zero, one-item, equality, "
            "opposite branch, duplicates, negatives, missing results, and return type.\n"
            "- Use true division for averages. Preserve ordering and multiplicity. "
            "Search failures normally return None; absent numeric amounts return 0.\n"
            "- Ratio means target/non-target; proportion means target/total.\n"
            "- For multiple valid answers, prefer the first from natural increasing "
            "iteration. A count beside operation ranges usually selects that many "
            "ranges; trace indices backwards when appropriate.\n"
            "- Prefer a formula, loop, comprehension, or small recurrence. After a "
            "failure, replace the disproved logic and emit a complete corrected block.\n"
            "TEMPLATE\n"
            "```python\n"
            "solution = '''def add(a, b):\n"
            "    return a + b\n"
            "'''\n"
            "print(run_tests(solution))\n"
            "```<end_code>"
        )
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
                history_window=6,
            )
            res = agent.execute()
            try:
                path = Path(args.output_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(res.model_dump_json(indent=4))
            except (FileNotFoundError, PermissionError) as e:
                print(f"Error writing output file: {e}")
    except (FileNotFoundError, PermissionError) as e:
        print(f"Error reading task file: {e}")
