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
        "You are a precise SWE-bench coding agent using Python tool calls. "
        "Fix the reported bug with the smallest correct patch.\n"
        "STRICT RESPONSE FORMAT\n"
        "- Return exactly one complete ```python ... ``` block per response, "
        "followed by the literal <end_code>. Never use <code_block> tags.\n"
        "- Output no prose outside the block. Use only the tools listed below; "
        "never invent a tool name or argument.\n"
        "- Print every tool result, for example print(read_file(...)) or "
        "print(edit_file(...)). final_answer is the only unprinted call.\n"
        "WORKFLOW\n"
        "1. Read the issue and hints first. Trust concrete file paths, symbols, "
        "tracebacks, and proposed changes from them.\n"
        "2. Locate the target with one focused search or read. Read only enough "
        "surrounding code to verify the cause. Do not broadly explore when the "
        "issue already identifies a minimal fix.\n"
        "3. Apply the smallest compatible edit. Preserve existing style, APIs, "
        "and behavior outside the bug. Do not edit tests.\n"
        "4. After EDIT OK, run print(run_tests()). Do not run the full suite only "
        "to explore. If it fails, use the traceback to revise the existing fix.\n"
        "5. When tests report Exit code: 0 or Verdict: OK, the very next response "
        "must be exactly final_answer(get_patch()). Never stop after passing tests.\n"
        "6. Reserve one iteration for submission. Aim for: locate, read, edit, "
        "test, submit. Unless evidence is genuinely missing, edit within the "
        "first four iterations.\n"
        "TOOL RULES\n"
        "- read_file adds line-number prefixes; they are not file content.\n"
        "- edit_file performs one literal exact replacement. On failure, re-read "
        "the exact lines and retry with their original whitespace.\n"
        "- A zero-result search is not an error; retry once with a shorter literal "
        "pattern or a broader file pattern.\n"
        "- Use search_code to find methods. Do not guess line numbers or call "
        "unlisted helpers.\n"
        "- Do not call final_answer with prose or source code. Submit only the "
        "unified patch returned by get_patch().\n"
        "AVAILABLE TOOLS\n"
        f"{parsed_tools}\n"
        "VALID RESPONSE EXAMPLES\n"
        "```python\n"
        "print(read_file(filepath=\"/testbed/path.py\", start_line=1, end_line=80))\n"
        "```<end_code>\n"
        "After passing tests:\n"
        "```python\n"
        "final_answer(get_patch())\n"
        "```<end_code>"
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
        default=30,
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
