import argparse
import sys
from pathlib import Path

from agent_smith.agent.loop import Agent
from agent_smith.models.task_input import SWEBenchTaskInput
from agent_smith.sandbox.manager import SandboxManager

# Official SWE-bench limits (subject VI.1.2), cumulative over the whole task.
MAX_INPUT_TOKENS = 300_000
MAX_OUTPUT_TOKENS = 10_000


def build_system_prompt(parsed_tools: str) -> str:
    return (
        "You are a Python coding agent using code-based tool calling. You solve SWE benchmark problem:\n"
        "METHOD\n"
        "1. Read the problem statement and the hints given in the task\n"
        "2. Explore the codebase using the tools given in TOOLS section\n"
        "3. Find the reference of the class or function which is responsible for the bug\n"
        "4. Fix it with the given tools\n"
        "5. Launch the tests to verify that your solution fix the problem\n"
        "6. If your solution doesn't work, read the output of the tests and modify your code accordly\n"
        "7. If your code passed all tests, submit your solution with final_answer(solution), solution must be the git patch of your modification. You can retrieve it with your given tools\n"
        "You always must test your code with the tools that you can use.\n"
        "Any other function than the present one in tools section are strictly forbidden\n"
        "OBSERVATIONS\n"
        "The observation you receive is the stdout of your code block, nothing else.\n"
        "A tool call whose return value is not printed produces NO observation.\n"
        "Therefore every tool call must be wrapped in print(). The only exception is\n"
        "final_answer(), which terminates the run.\n"
        "    print(edit_file(...))    correct\n"
        "    edit_file(...)           wrong: you will see an empty observation\n"
        "If an observation is empty, the cause is your own code, not a broken tool or a\n"
        "missing file. Re-issue the same call wrapped in print() before forming any other\n"
        "hypothesis.\n"
        "TOOL BEHAVIOUR YOU MUST KNOW\n"
        "- read_file prefixes every line with 'NNN: '. That prefix is NOT part of the\n"
        "  file. Strip it before reusing the text in edit_file.\n"
        "- edit_file replaces old_str LITERALLY (never as a regex). old_str may span\n"
        "  several lines and must match EXACTLY ONCE, whitespace and indentation\n"
        "  included. It answers 'EDIT OK: 1 occurrence replaced' or 'EDIT FAILED: ...'\n"
        "  and on failure the file is left untouched: re-read the lines and copy them\n"
        "  verbatim instead of guessing.\n"
        "- search_code, search_function_or_class_definition_in_code and find_references\n"
        "  answer '/absolute/path.py:<line> <content>'. 'No match ... (0 result)' is a\n"
        "  normal answer, not a crash: retry with a shorter pattern.\n"
        "- run_tests runs the whole evaluation script and is SLOW (tens of seconds to\n"
        "  minutes). Call it only after an EDIT OK, never to explore.\n"
        "TOOLS\n"
        f"{parsed_tools}\n"
        "final_answer(code) to submit your code if it's valid\n"
        "EXAMPLE\n"
        "[ASSISTANT]\n"
        "Thought: The issue says `Mul.flatten` mishandles zero coefficients.\n"
        "I locate the definition before reading its context.\n"
        "```python\n"
        'print(search_function_or_class_definition_in_code(name="flatten"))\n'
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "/testbed/sympy/core/mul.py:120 def flatten(cls, seq):\n"
        "[ASSISTANT]\n"
        "Thought: I read the relevant range to understand the current logic.\n"
        "```python\n"
        'print(read_file(filepath="/testbed/sympy/core/mul.py", start_line=120, end_line=160))\n'
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "121: def flatten(cls, seq):\n"
        "121:     coeff = S.One\n"
        "...\n"
        "148:     if coeff is S.Zero:\n"
        "149:         return [coeff], [], None\n"
        "...  (truncated)\n"
        "[ASSISTANT]\n"
        "Thought: The coeff==0 branch returns too early and drops the non-commutative\n"
        "factors. I copy lines 148-149 verbatim, without their 'NNN: ' prefix.\n"
        "```python\n"
        "print(edit_file(\n"
        '    filepath="/testbed/sympy/core/mul.py",\n'
        '    old_str="    if coeff is S.Zero:\\n        return [coeff], [], None",\n'
        '    new_str="    if coeff is S.Zero:\\n        return [coeff], nc_part, None",\n'
        "))\n"
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "EDIT OK: 1 occurrence replaced in /testbed/sympy/core/mul.py.\n"
        "[ASSISTANT]\n"
        "Thought: The edit landed. Now I run the tests.\n"
        "```python\n"
        "print(run_tests())\n"
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "... 42 passed, 0 failed ...\n"
        "[ASSISTANT]\n"
        "Thought: All tests pass. I submit the patch.\n"
        "```python\n"
        "final_answer(get_patch())\n"
        "```<end_code>\n"
        "EXAMPLE 2 (broad exploration: list_files + search_code + find_references before editing)\n"
        "[ASSISTANT]\n"
        "Thought: I don't know the parsing module layout yet. I list the files, then search\n"
        "for the error string mentioned in the issue.\n"
        "```python\n"
        'print(list_files(directory="/testbed/sympy/parsing", pattern="*.py"))\n'
        'print(search_code(pattern="unexpected token", file_pattern="*.py"))\n'
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "/testbed/sympy/parsing/sympy_parser.py\n"
        "/testbed/sympy/parsing/mathematica.py\n"
        '/testbed/sympy/parsing/sympy_parser.py:512     raise SyntaxError("unexpected token")\n'
        "[ASSISTANT]\n"
        "Thought: Before touching the function that raises the error, I check who calls it\n"
        "to gauge the blast radius of a signature change.\n"
        "```python\n"
        'print(find_references(name="eval_expr", filepath="/testbed/sympy/parsing/sympy_parser.py", line=498))\n'
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "/testbed/sympy/parsing/sympy_parser.py:1043     return eval_expr(code, local_dict, global_dict)\n"
        '/testbed/sympy/parsing/tests/test_sympy_parser.py:88     eval_expr("2 + 2")\n'
        "[ASSISTANT]\n"
        "Thought: Only one internal caller, so adding an optional parameter is safe. I edit and test.\n"
        "```python\n"
        "print(edit_file(\n"
        '    filepath="/testbed/sympy/parsing/sympy_parser.py",\n'
        '    old_str="def eval_expr(code, local_dict, global_dict):",\n'
        '    new_str="def eval_expr(code, local_dict, global_dict, strict=False):",\n'
        "))\n"
        "print(run_tests())\n"
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "EDIT OK: 1 occurrence replaced in /testbed/sympy/parsing/sympy_parser.py.\n"
        "... 15 passed, 0 failed ...\n"
        "[ASSISTANT]\n"
        "```python\n"
        "final_answer(get_patch())\n"
        "```<end_code>\n"
        "EXAMPLE 3 (recovery: a failed edit, then a failed hypothesis)\n"
        "[ASSISTANT]\n"
        "Thought: The issue reports a TypeError in `concat`. I fix what looks like the cause.\n"
        "```python\n"
        "print(edit_file(\n"
        '    filepath="/testbed/xarray/core/concat.py",\n'
        '    old_str="dims = set(v.dims)",\n'
        '    new_str="dims = list(v.dims)",\n'
        "))\n"
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "EDIT FAILED: old_str not found in /testbed/xarray/core/concat.py (0 occurrence),\n"
        "the file is unchanged. Re-read the exact lines with read_file and copy them\n"
        "verbatim, indentation included and WITHOUT the 'NNN: ' line-number prefix that\n"
        "read_file adds.\n"
        "[ASSISTANT]\n"
        "Thought: I guessed the text instead of copying it. I read the real lines.\n"
        "```python\n"
        'print(read_file(filepath="/testbed/xarray/core/concat.py", start_line=200, end_line=240))\n'
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "200: def _calc_concat_dim(...):\n"
        "...\n"
        "221:     dims = list(v.dims)\n"
        "222:     dims = sorted(dims)   # <-- sort that breaks original order\n"
        "...\n"
        "[ASSISTANT]\n"
        "Thought: Line 222 sorts the dimensions and destroys their order. That is the real\n"
        "cause. I copy line 222 exactly, with its four spaces of indentation.\n"
        "```python\n"
        "print(edit_file(\n"
        '    filepath="/testbed/xarray/core/concat.py",\n'
        '    old_str="    dims = sorted(dims)",\n'
        '    new_str="    dims = list(dict.fromkeys(dims))",\n'
        "))\n"
        "print(run_tests())\n"
        "```<end_code>\n"
        "[OBSERVATION]\n"
        "EDIT OK: 1 occurrence replaced in /testbed/xarray/core/concat.py.\n"
        "... 5 passed, 0 failed ...\n"
        "[ASSISTANT]\n"
        "```python\n"
        "final_answer(get_patch())\n"
        "```<end_code>\n"
        "CONSTRAINTS\n"
        "- Budget is tight. Aim to finish in minimal steps: explore, one edit, one test run.\n"
        "- Keep every Thought to two lines at most. A response cut off mid-code-block is\n"
        "  wasted: it executes nothing.\n"
        "- Solution must be self-contained: include the imports it needs, no test code, no input().\n"
        "- Do not re-explain the problem or restate code you already wrote.\n"
        "- Do not switch to run_command to work around a tool that seems to fail. Fix the call.\n"
        "You need to terminate your responses by <end_code>\n"
        "You need to provide one python code block at a time, and you need to wait for the observation before providing the next code block.\n"
        "If all of your tests pass, you must submit your solution with final_answer\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI for swebench agent")
    parser.add_argument(
        "--task-file",
        type=str,
        default="cache/swebench_task.json",
        help="Path to the task.json file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="cache/swebench_solution.json",
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
        help="Maximum number of agent loop iterations (limit: 30)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1000,
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
            task = SWEBenchTaskInput.model_validate_json(json_data)
            mcp_config = {
                "command": sys.executable,
                "args": [
                    "mcp_tools_swebench.py",
                    "--task",
                    str(task_path),
                ],
                "cwd": str(Path.cwd()),
                "transport": "stdio",
            }
            manager = SandboxManager(
                sandbox_config_path,
                mcp_config=mcp_config,
                run_timeout=600,
            )
            tools = manager.list_tools()
            parsed_tools = "\n".join(tools)
            task_str = f"{task.problem_statement}\nYou have some hints to resolve this task: {task.hints_text}"
            agent = Agent(
                sandbox=manager,
                sys_prompt=build_system_prompt(parsed_tools),
                task=task_str,
                task_id=task.instance_id,
                benchmark_name="SWEBench",
                provider=args.provider_url,
                model_name=args.model_name,
                max_tokens=args.max_tokens,
                max_iterations=args.max_iterations,
                max_input_tokens=MAX_INPUT_TOKENS,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                max_observation_chars=4000,
                history_window=8,
            )
            res = agent.execute()
            try:
                path = Path(args.output)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(res.model_dump_json(indent=4))
            except (FileNotFoundError, PermissionError) as e:
                print(f"Error writing output file: {e}")
    except (FileNotFoundError, PermissionError) as e:
        print(f"Error reading task file: {e}")
