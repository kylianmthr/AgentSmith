from agent_smith.sandbox.manager import SandboxManager
from pathlib import Path

def test_codes(param: int = 1) -> str:
    if param == 1:
        return """
x = 10
y = x + 5

print("x =", x)
print("y =", y)
final_answer(str(y))
"""

    if param == 2:
        return """
solution = "def add(a, b): return a - b"
print(run_tests(solution))
"""

    if param == 3:
        return """
solution = solution.replace("a - b", "a + b")
print(run_tests(solution))
final_answer(solution)
"""

    return ""

if __name__ == "__main__":
    # LAUNCH WITH uv run python3 -m agent_smith.sandbox.fake_main

    task_path = "/home/nitwee/42/AgentSmith/agent_smith/sandbox/fake_task.json"

    mcp_config = {
        "command": "python3",
        "args": ["mcp_tools_mbpp.py", "--task", task_path],
        "cwd": "/home/nitwee/42/AgentSmith",
    }

    # BASIC check
    code = test_codes()
    # REPL Persistence check
    code1 = test_codes(2)
    code2 = test_codes(3)
    config_path = Path(__file__).with_name("fake_config.json")
    sandbox = SandboxManager(config_path, mcp_config)
    try:
        result = sandbox.run(code)
        print(f"BASIC CHECK RES: {result}\n")
        result = sandbox.run(code1)
        print(f"PERSISTENCE CHECK RES 1: {result}\n")
        result = sandbox.run(code2)
        print(f"PERSISTENCE CHECK RES 2: {result}\n")
    finally:
        sandbox.stop()

    