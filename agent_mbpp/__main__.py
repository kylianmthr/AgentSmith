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
        help="Maximum output tokens per LLM request",
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
            task_str = f"{task.task_definition}\nYour function must be declared like this: {task.function_definition}"
            sys_prompt = (
                "You are a Python coding agent solving one MBPP task.\n"
                "TOOLS\n"
                f"{parsed_tools}\n"
                "WORKFLOW\n"
                "1. Write a self-contained solution using the exact required name and signature.\n"
                "2. Store the complete source in `solution` and immediately call `print(run_tests(solution))`.\n"
                "3. If a test fails, fix `solution` and run the tests again.\n"
                "4. As soon as all tests pass, call `final_answer(solution)` on the next step.\n"
                "RULES\n"
                "- Aim to finish in 2-3 steps; input tokens are limited to 6000.\n"
                "- Never submit untested code. Do not include tests or input() in the solution.\n"
                "- Keep reasoning to one short sentence and do not repeat the task.\n"
                "- Return exactly one ```python code block per response, followed by <end_code>.\n"
                "EXAMPLE\n"
                "```python\n"
                "solution = '''def add(a, b):\n    return a + b\n'''\n"
                "print(run_tests(solution))\n"
                "```<end_code>\n"
                "After the observation says all tests passed:\n"
                "```python\nfinal_answer(solution)\n```<end_code>\n"
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
