import subprocess
import sys
from mcp.server.fastmcp import FastMCP

TEST_LIST = [
    'assert remove_Occ("hello","l") == "heo"',
    'assert remove_Occ("abcda","a") == "bcd"',
    'assert remove_Occ("PHP","P") == "H"',
]

mcp = FastMCP("mbpp-tools")


def last_line(stderr: str) -> str:
    lines = [line for line in stderr.strip().split("\n") if line.strip()]
    return lines[-1] if lines else ""


@mcp.tool()
def run_tests(code: str) -> str:
    """Execute the MBPP test suite against a candidate solution.

    Args:
        code: The complete Python source of your solution (function definition included).

    Returns:
        A summary like "2/3 tests passed" followed by details of failing assertions.
    """
    failures = []
    for test in TEST_LIST:
        test_code = code + "\n" + test
        try:
            res = subprocess.run(
                [sys.executable, "-"],
                input=test_code,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                failures.append(f"FAILED: {test}\n{last_line(res.stderr)}")
        except subprocess.TimeoutExpired:
            failures.append(f"TIMEOUT: {test}")
    res = f"{len(TEST_LIST) - len(failures)}/{len(TEST_LIST)} tests passed"
    if failures:
        res += "\n" + "\n".join(
            failures[:3]
        )  # on a que 600 tokens/iteration donc on limite les logs de failures
    return res


if __name__ == "__main__":
    mcp.run(transport="stdio")
