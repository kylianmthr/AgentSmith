import argparse
import sys
from pathlib import Path

from agent_smith.agent.loop import Agent
from agent_smith.models.task_input import MBPPTaskInput
from agent_smith.sandbox.manager import SandboxManager

MAX_INPUT_TOKENS = 5_000
MAX_OUTPUT_TOKENS = 1_200

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
                "You are a Python coding agent using code-based tool calling. "
                "You solve one MBPP task by iterating.\n"
                "METHOD\n"
                "1. Write the function with the EXACT name and signature given in the task, implementing "
                "the general behaviour the description states, not just the visible tests.\n"
                "2. Check it with print(run_tests(solution)). Never submit untested code.\n"
                "3. If tests fail, define the function directly in the code block and print what it "
                "returns, compare with the expected result, then fix it.\n"
                "4. Submit with final_answer(solution).\n"
                "TOOLS (any other function is forbidden)\n"
                f"{parsed_tools}\n"
                "final_answer(solution): submit your validated code, one positional argument\n"
                "RULES\n"
                "- One ```python block per reply, terminated by <end_code>, then wait for the observation.\n"
                "- Keep the Thought to one short line and the code compact: a reply that runs past the "
                "output limit is cut off mid-block and wastes an iteration.\n"
                "- Call run_tests(solution) with the solution only: the task tests are already loaded.\n"
                "- run_tests shows only part of the tests, hidden ones run too. So BEFORE your first "
                "run_tests, re-read the description and honour every word of it and the edge cases it "
                "implies (empty input, single element, duplicate or swapped values).\n"
                "- As soon as run_tests answers 'N/N tests passed', your next reply must be exactly "
                "final_answer(solution) and nothing else. Never re-test a solution that passed.\n"
                "- Budget is tight (10 iterations max, small token budget): aim for 2-3 steps, stay brief, "
                "never restate the problem or code you already wrote.\n"
                "- The solution is self-contained: imports included, no test code, no input().\n"
                "EXAMPLE\n"
                "Task: write a function `repocc(s, c, n)` that replaces all occurrences of a character.\n"
                "[ASSISTANT]\n"
                "Thought: I will use `str.replace`.\n"
                "```python\n"
                "solution = '''def repocc(s, c, n):\n"
                "    return s.replace(c, n, 1)\n"
                "'''\n"
                "print(run_tests(solution))\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "1/3 tests passed\n"
                "[ASSISTANT]\n"
                "Thought: I print what my function actually returns.\n"
                "```python\n"
                "def repocc(s, c, n):\n"
                "    return s.replace(c, n, 1)\n"
                "print(repocc('hello', 'l', 't'))\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "hetlo\n"
                "[ASSISTANT]\n"
                "Thought: only the first occurrence was replaced, the count argument is wrong.\n"
                "```python\n"
                "solution = '''def repocc(s, c, n):\n"
                "    return s.replace(c, n)\n"
                "'''\n"
                "print(run_tests(solution))\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "3/3 tests passed\n"
                "[ASSISTANT]\n"
                "Thought: tests pass, I submit.\n"
                "```python\n"
                "final_answer(solution)\n"
                "```<end_code>\n"
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
                history_window=4,
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
