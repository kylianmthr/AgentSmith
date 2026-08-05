import argparse
from pathlib import Path

from agent_smith.agent.loop import Agent
from agent_smith.models.task_input import SWEBenchTaskInput
from agent_smith.sandbox.manager import SandboxManager

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI for mbpp agent")
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
        "--model-name",
        type=str,
        default="llama-3.1-8b-instant",
        help="Name of the model to use",
    )
    parser.add_argument(
        "--provider-url",
        type=str,
        default="https://api.groq.com/openai/v1",
        help="URL of the LLM provider",
    )
    args = parser.parse_args()
    try:
        with open(args.task_file, "r") as f:
            json_data = f.read()
            task = SWEBenchTaskInput.model_validate_json(json_data)
            mcp_config = {
                "command": "python3",
                "args": [
                    "mcp_tools_swebench.py",
                    "--task",
                    args.task_file,
                ],
                "cwd": Path.cwd(),
                "transport": "stdio",
            }
            manager = SandboxManager(
                Path(args.task_file), mcp_config=mcp_config
            )
            tools = manager.list_tools()
            parsed_tools = "\n".join(tools)
            task_str = f"{task.problem_statement}\nYou have some hints to resolve this task: {task.hints_text}"
            sys_prompt = (
                "You are a Python coding agent using code-based tool calling. You solve SWE benchmark problem:\n"
                "METHOD\n"
                "1. Read the probem statement and the hints given in the task\n"
                "2. Explore the codebase using the tools given in TOOLS section\n"
                "3. Find the reference of the class or function which is reponsible for the bug\n"
                "4. Fix it with the given tools\n"
                "5. Launch the tests to verify that your solution fix the problem\n"
                "6. If your solution doesn't work, read the output of the tests and modify your code accordly\n"
                "7. If your code passed all tests, submit your solution with final_answer(solution), solution must be the git patch of your modification. You can retrieve it with your given tools\n"
                "You always must test your code with the tools that you can use.\n"
                "Any other function than the present one in tools section are strictly forbidden\n"
                "TOOLS\n"
                "This functions return values, if you want to be able to see it you probably need to use print() function\n"
                f"{parsed_tools}\n"
                "final_answer(code) to submit your code if it's valid\n"
                "EXAMPLE\n"
                "[ASSISTANT]\n"
                "Thought: The issue says `Mul.flatten` mishandles zero coefficients.\n"
                "I locate the definition before reading its context.\n"
                "```python\n"
                'loc = search_function_or_class_definition_in_code(name="flatten")\n'
                "print(loc)\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "/testbed/sympy/core/mul.py:120 def flatten(cls, seq):\n"
                "[ASSISTANT]\n"
                "Thought: I read the relevant range to understand the current logic.\n"
                "```python\n"
                'src = read_file(filepath="/testbed/sympy/core/mul.py", start_line=120, end_line=160)\n'
                "print(src)\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "121: def flatten(cls, seq):\n"
                "121:     coeff = S.One\n"
                "...\n"
                "148:     if coeff is S.Zero:\n"
                "149:         return [coeff], [], None\n"
                "...  (truncated)\n"
                "[ASSISTANT]\n"
                "Thought: The coeff==0 branch returns too early and drops the non-commutative factors.\n"
                "I fix it, then run the tests in the same turn.\n"
                "```python\n"
                "edit_file(\n"
                '    filepath="/testbed/sympy/core/mul.py",\n'
                '    old_str="    if coeff is S.Zero:\\n        return [coeff], [], None",\n'
                '    new_str="    if coeff is S.Zero:\\n        return [coeff], nc_part, None",\n'
                ")\n"
                "result = run_tests()\n"
                "print(result)\n"
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
                'files = list_files(directory="/testbed/sympy/parsing", pattern="*.py")\n'
                "print(files)\n"
                'hits = search_code(pattern="unexpected token", file_pattern="*.py")\n'
                "print(hits)\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "/testbed/sympy/parsing/sympy_parser.py\n"
                "/testbed/sympy/parsing/mathematica.py\n"
                '/testbed/sympy/parsing/sympy_parser.py:512     raise SyntaxError("unexpected token")\n'
                "[ASSISTANT]\n"
                "Thought: Before touching the function that raises the error, I check who calls it\n"
                "to gauge the blast radius of a signature change.\n"
                "```python\n"
                'refs = find_references(name="eval_expr", filepath="/testbed/sympy/parsing/sympy_parser.py", line=498)\n'
                "print(refs)\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "/testbed/sympy/parsing/sympy_parser.py:1043     return eval_expr(code, local_dict, global_dict)\n"
                '/testbed/sympy/parsing/tests/test_sympy_parser.py:88     eval_expr("2 + 2")\n'
                "[ASSISTANT]\n"
                "Thought: Only one internal caller, so adding an optional parameter is safe. I edit and test.\n"
                "```python\n"
                "edit_file(\n"
                '    filepath="/testbed/sympy/parsing/sympy_parser.py",\n'
                '    old_str="def eval_expr(code, local_dict, global_dict):",\n'
                '    new_str="def eval_expr(code, local_dict, global_dict, strict=False):",\n'
                ")\n"
                "print(run_tests())\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "... 15 passed, 0 failed ...\n"
                "[ASSISTANT]\n"
                "```python\n"
                "final_answer(get_patch())\n"
                "```<end_code>\n"
                "EXAMPLE 3 (recovery: the first fix fails, the hypothesis is reformulated)\n"
                "[ASSISTANT]\n"
                "Thought: The issue reports a TypeError in `concat`. I fix what looks like the cause and test.\n"
                "```python\n"
                "edit_file(\n"
                '    filepath="/testbed/xarray/core/concat.py",\n'
                '    old_str="dims = set(v.dims)",\n'
                '    new_str="dims = list(v.dims)",\n'
                ")\n"
                "print(run_tests())\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "... 3 passed, 2 failed ...\n"
                "FAILED test_concat.py::test_concat_dim_order - AssertionError: order not preserved\n"
                "[ASSISTANT]\n"
                "Thought: My change doesn't address the root cause: the problem is dim ordering, not type.\n"
                "I re-read the full function to form a better hypothesis before editing again.\n"
                "```python\n"
                'src = read_file(filepath="/testbed/xarray/core/concat.py", start_line=200, end_line=240)\n'
                "print(src)\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "200: def _calc_concat_dim(...):\n"
                "...\n"
                "221:     dims = list(v.dims)\n"
                "222:     dims = sorted(dims)   # <-- sort that breaks original order\n"
                "...\n"
                "[ASSISTANT]\n"
                "Thought: Line 222 sorts the dimensions and destroys their order. That is the real cause.\n"
                "I replace the sort with order-preserving dedup, then re-test.\n"
                "```python\n"
                "edit_file(\n"
                '    filepath="/testbed/xarray/core/concat.py",\n'
                '    old_str="    dims = sorted(dims)",\n'
                '    new_str="    dims = list(dict.fromkeys(dims))",\n'
                ")\n"
                "print(run_tests())\n"
                "```<end_code>\n"
                "[OBSERVATION]\n"
                "... 5 passed, 0 failed ...\n"
                "[ASSISTANT]\n"
                "```python\n"
                "final_answer(get_patch())\n"
                "```<end_code>\n"
                "CONSTRAINTS\n"
                "- Budget is tight (30 iterations max, small token budget). Aim to finish in minimal steps.\n"
                "- Solution must be self-contained: include the imports it needs, no test code, no input().\n"
                "- Do not re-explain the problem or restate code you already wrote.\n"
                "You need to terminate your responses by <end_code>\n"
                "You need to provide one python code block at a time, and you need to wait for the observation before providing the next code block.\n"
                "If all of your tests pass, you must submit your solution with final_answer\n"
            )
            agent = Agent(
                sandbox=manager,
                sys_prompt=sys_prompt,
                task=task_str,
                task_id=task.instance_id,
                limits=350,
                benchmark_name="SWEBench",
                provider=args.provider_url,
                model_name=args.model_name,
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
