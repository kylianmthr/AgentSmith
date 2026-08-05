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
            sys_prompt = "todo"
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
                path = Path(args.output_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(res.model_dump_json(indent=4))
            except (FileNotFoundError, PermissionError) as e:
                print(f"Error writing output file: {e}")
    except (FileNotFoundError, PermissionError) as e:
        print(f"Error reading task file: {e}")
