import argparse
import sys
from pathlib import Path

from agent_smith.agent.loop import Agent
from agent_smith.models.task_input import MBPPTaskInput
from agent_smith.sandbox.manager import SandboxManager

# Official MBPP limits (subject VI.1.1), cumulative over the whole task.
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
        default="openai/gpt-oss-120b",
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
        sandbox_config_path = (
            Path(args.sandbox_config) if args.sandbox_config else None
        )
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
            manager = SandboxManager(
                sandbox_config_path, mcp_config=mcp_config
            )
            tools = manager.list_tools()
            parsed_tools = "\n".join(tools)
            print(parsed_tools)
            task_str = f"{task.task_definition}\nYour function must be declared like this: {task.function_definition}"
            sys_prompt = (
                "You are a Python coding agent using code-based tool calling. You solve one MBPP task by iterating:\n"
                "METHOD\n"
                "1. Write the function using the EXACT name and signature given in the task, plus any helper you need.\n"
                "2. Verify it with run_tests before submitting.\n"
                "3. If the tests don't validate your solution, display the return of your function\n"
                "4. Compare it with the expected result\n"
                "5. Fix your code accordingly\n"
                "6. Submit with final_answer(solution)\n"
                "You always must test your code with the tools that you can use.\n"
                "Any other function than the present one in tools section are strictly forbidden\n"
                "TOOLS\n"
                f"{parsed_tools}\n"
                "final_answer(code) to submit your code if it's valid\n"
                "CONSTRAINTS\n"
                "- Budget is tight (10 iterations max, small token budget). Aim to finish in 2-3 steps.\n"
                "- Solution must be self-contained: include the imports it needs, no test code, no input().\n"
                "- Do not re-explain the problem or restate code you already wrote.\n"
                "EXAMPLE\n"
                "- First example\n"
                "Task: write a function `add(a, b)` that returns the sum.\n"
                "Thought: Simple, I write it and test it right away.\n"
                "Code:\n"
                "```python\n"
                "solution = '''def add(a, b):\n"
                "    return a + b\n"
                "'''\n"
                "print(run_tests(solution))\n"
                "```\n"
                "Observation: 3/3 tests passed\n"
                "Thought: I can validate my solution\n"
                "Code:\n"
                "```python\n"
                "final_answer(solution)\n"
                "```\n"
                "- Second example\n"
                "Task: write a function `repocc(string, char, new_char)` that replaces all occurences of a character.\n"
                "Thought: I will use `str.replace`.\n"
                "Code:\n"
                "```python\n"
                "solution = '''def repocc(string, char, new_char):\n"
                "    return string.replace(char, new_char, 1)\n"
                "'''\n"
                "print(run_tests(solution))\n"
                "```\n"
                "Observation: 1/3 tests passed\n"
                "Thought: I need to see what my function returns\n"
                "Code:\n"
                "```python\n"
                "exec(solution)\n"
                "print(repocc('hello', 'l', 't'))\n"
                "```\n"
                "Observation: hetlo\n"
                "Thought: The second occurrence of 'l' was not replaced\n"
                "Code:\n"
                "```python\n"
                "solution = '''def repocc(string, char, new_char):\n"
                "    return string.replace(char, new_char)\n"
                "'''\n"
                "print(run_tests(solution))\n"
                "```\n"
                "Observation: 3/3 tests passed\n"
                "Thought: I can validate my solution\n"
                "Code:\n"
                "```python\n"
                "final_answer(solution)\n"
                "```\n"
                "- Third example\n"
                "Task: write a function `add(a, b)` that multiply a, b and returns the result.\n"
                "Thought: I will use `*` operator.\n"
                "```python\n"
                "solution = '''def mul(a, b):\n"
                "   return a * b\n"
                "'''"
                "```\n"
                "Observation: Stderr: No tests were run. Please use the `run_tests` tool to validate your solution before submitting.\n"
                "Thought: I need to test my function with the `run_tests` tool\n"
                "```python\n"
                "print(run_tests(solution))\n"
                "```"
                "Observation: 3/3 tests passed\n"
                "Thought: I can validate my solution\n"
                "```python\n"
                "final_answer(solution)\n"
                "```"
                "You need to terminate your responses by <end_code>\n"
                "You need to provide one python code block at a time, and you need to wait for the observation before providing the next code block.\n"
                "If all of your tests pass, you must submit your solution with final_answer\n"
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
