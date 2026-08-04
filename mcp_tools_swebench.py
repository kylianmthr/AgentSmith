import docker
import jedi
import io
import os
import tarfile
import tempfile
import re

DOCKER_IMAGE = "swebench/sweb.eval.x86_64.sympy_1776_sympy-23534:latest"
CLIENT = docker.from_env()
CONTAINER = CLIENT.containers.run(
    DOCKER_IMAGE, command="sleep infinity", detach=True, tty=True
)
EVAL_SCRIPT = "#!/bin/bash\nset -uxo pipefail\nsource /opt/miniconda3/bin/activate\nconda activate testbed\ncd /testbed\ngit config --global --add safe.directory /testbed\ncd /testbed\ngit status\ngit show\ngit -c core.fileMode=false diff f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0\nsource /opt/miniconda3/bin/activate\nconda activate testbed\npython -m pip install -e .\ngit checkout f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0 sympy/functions/elementary/tests/test_hyperbolic.py\ngit apply -v - <<'EOF_114329324912'\ndiff --git a/sympy/functions/elementary/tests/test_hyperbolic.py b/sympy/functions/elementary/tests/test_hyperbolic.py\n--- a/sympy/functions/elementary/tests/test_hyperbolic.py\n+++ b/sympy/functions/elementary/tests/test_hyperbolic.py\n@@ -272,6 +272,8 @@ def test_coth():\n \n     assert coth(k*pi*I) == -cot(k*pi)*I\n \n+    assert coth(log(tan(2))) == coth(log(-tan(2)))\n+    assert coth(1 + I*pi/2) == tanh(1)\n \n def test_coth_series():\n     x = Symbol('x')\n\nEOF_114329324912\n: '>>>>> Start Test Output'\nPYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' bin/test -C --verbose sympy/functions/elementary/tests/test_hyperbolic.py\n: '>>>>> End Test Output'\ngit checkout f57fe3f4b3f2cab225749e1b3b38ae1bf80b62f0 sympy/functions/elementary/tests/test_hyperbolic.py\n"
START, END = ">>>>> Start Test Output", ">>>>> End Test Output"


def _format_line(content: str, start_line: int) -> str:
    new_content = ""
    i = 0
    for line in content.splitlines():
        new_line = f"{start_line + i}: {line}"
        new_content += new_line + "\n"
        i += 1
    return new_content


def read_file(filepath: str, start_line: int, end_line: int) -> str:
    res = CONTAINER.exec_run(
        cmd=["sed", "-n", f"{start_line},{end_line}p", filepath],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"{filepath}: {(err or b'').decode('utf-8', errors='replace')}"
        )
    return _format_line(
        (out or b"").decode("utf-8", errors="replace"), start_line
    )


def edit_file(filepath: str, old_str: str, new_str: str) -> None:
    res = CONTAINER.exec_run(
        cmd=["sed", "-i", f"s/{old_str}/{new_str}/g", filepath],
        workdir="/testbed",
    )
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"{filepath}: {(res.output or b'').decode('utf-8', errors='replace')}"
        )


def list_files(directory: str, pattern: str = "*") -> str:
    res = CONTAINER.exec_run(
        cmd=["find", directory, "-name", pattern],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"{directory}: {(err or b'').decode('utf-8', errors='replace')}"
        )
    return (out or b"").decode("utf-8", errors="replace")


def search_code(pattern: str, file_pattern: str = "*") -> str:
    res = CONTAINER.exec_run(
        cmd=["grep", "-rnw", ".", "-e", pattern, "--include", file_pattern],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        raise FileNotFoundError(
            f"Pattern '{pattern}' not found in files matching '{file_pattern}': {(err or b'').decode('utf-8')}"
        )
    return (out or b"").decode("utf-8", errors="replace")


def search_function_or_class_definition_in_code(name: str) -> str:
    res = CONTAINER.exec_run(
        cmd=["grep", "-rnw", ".", "-e", f"def {name}(", "--include", "*.py"],
        workdir="/testbed",
        demux=True,
    )
    out, err = res.output
    if res.exit_code != 0:
        res_class = CONTAINER.exec_run(
            cmd=[
                "grep",
                "-rnw",
                ".",
                "-e",
                f"class {name}(",
                "--include",
                "*.py",
            ],
            workdir="/testbed",
            demux=True,
        )
        out_class, err_class = res_class.output
        if res_class.exit_code != 0:
            raise FileNotFoundError(
                f"Function or class '{name}' not found in code"
            )
        return out_class.decode("utf-8", errors="replace")
    return (out or b"").decode("utf-8", errors="replace")


def _copy_testbed_to_host(dst: str) -> str:
    bits, _stat = CONTAINER.get_archive("/testbed")
    buf = io.BytesIO()
    for chunk in bits:
        buf.write(chunk)
    buf.seek(0)
    with tarfile.open(fileobj=buf) as tar:
        tar.extractall(dst, filter="data")
    return os.path.join(dst, "testbed")


def find_references(name: str, filepath: str, line: int) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = _copy_testbed_to_host(tmp)
        if os.path.isabs(filepath):
            container_path = os.path.normpath(filepath)
        else:
            container_path = os.path.normpath(
                os.path.join("/testbed", filepath)
            )

        if container_path != "/testbed" and not container_path.startswith(
            "/testbed/"
        ):
            raise ValueError(f"filepath hors de /testbed: {filepath!r}")
        rel = os.path.relpath(container_path, "/testbed")
        host_path = os.path.join(root, rel)
        with open(host_path, encoding="utf-8") as f:
            code_line = f.readlines()[line - 1]
        col = code_line.find(name)
        if col < 0:
            raise ValueError(f"'{name}' not found {filepath}:{line}")

        project = jedi.Project(root)
        script = jedi.Script(path=host_path, project=project)
        refs = script.get_references(
            line=line, column=col, include_builtins=False
        )
        lines = []
        for r in refs:
            abs_path = "/testbed" + str(r.module_path)[len(root) :]
            lines.append(f"{abs_path}:{r.line} {r.get_line_code().strip()}")
        return "\n".join(lines)


def run_command(command: str, workdir: str = "/testbed") -> str:
    res = CONTAINER.exec_run(
        cmd=["sh", "-c", command],
        workdir=workdir,
        demux=True,
    )
    out, err = res.output
    return f"stdout:\n{(out or b'').decode('utf-8', errors='replace')}\nstderr:\n{(err or b'').decode('utf-8', errors='replace')}\nexit_code: {res.exit_code}"


def test_section(text: str) -> tuple[str, bool]:
    i = text.find(START)
    j = text.find(END, i + 1) if i != -1 else -1
    if i != -1 and j != -1:
        index = i + len(START)
        return text[index:j].strip(), True
    return text, False


_TB = re.compile(r"^Traceback \(most recent call last\):", re.M)
_EXC = re.compile(r"^\w[\w.]*(Error|Exception|Warning|Assertion)\b")


def summarize(output: str, budget: int = 6000, max_blocks: int = 5) -> str:
    lines = output.splitlines()
    tail = lines[-40:]

    blocks, seen = [], set()
    starts = [i for i, l in enumerate(lines) if _TB.match(l)]
    for s in starts:
        block = [lines[s]]
        for l in lines[s + 1 : s + 41]:
            block.append(l)
            if _EXC.match(l):
                break
        sig = block[-1]
        if sig not in seen:
            seen.add(sig)
            blocks.append("\n".join(block))
        if len(blocks) >= max_blocks:
            break
    header = f"[{len(starts)} traceback(s), {len(blocks)} show]"
    body = (
        "\n\n".join(blocks) + "\n\n--- END OF OUTPUT ---\n" + "\n".join(tail)
    )
    out = header + "\n" + body
    return out if len(out) <= budget else out[:budget] + "\n[cuted (too long)]"


def run_tests():
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tarinfo = tarfile.TarInfo(name="run_tests.sh")
        tarinfo.size = len(EVAL_SCRIPT.encode("utf-8"))
        tar.addfile(tarinfo, io.BytesIO(EVAL_SCRIPT.encode("utf-8")))
    tar_stream.seek(0)
    CONTAINER.put_archive("/testbed", tar_stream.read())
    CONTAINER.exec_run(cmd=["chmod", "+x", "run_tests.sh"], workdir="/testbed")
    res = CONTAINER.exec_run(cmd=["./run_tests.sh"], workdir="/testbed")
    combined = (res.output or b"").decode("utf-8", errors="replace")
    section, found = test_section(combined)
    verdict = "OK" if found else f"FAIL (exit code: {res.exit_code})"
    note = "" if found else "\n[NO TEST FOUND, return raw output]"
    body = summarize(section, budget=6000)
    return f"Exit code: {res.exit_code}\nVerdict: {verdict}{note}\n\n{body}"


def get_patch():
    res = CONTAINER.exec_run(
        "git -c core.fileMode=false diff", demux=True, workdir="/testbed"
    )
    out, err = res.output
    if res.exit_code != 0:
        raise RuntimeError(
            f"git diff failed: {(err or b'').decode('utf-8', errors='replace')}"
        )
    return (out or b"").decode("utf-8", errors="replace")


if __name__ == "__main__":
    try:
        print(CONTAINER.exec_run("ls -l /testbed").output.decode())
        # print(read_file("README.md", 1, 5))
        edit_file("README.md", "# SymPy", "test")
        # print(read_file("README.md", 1, 5))
        # print(list_files(".", "*.md"))
        # print("=====")
        # print(search_code("SymPy", "*.md"))
        # print(read_file("isympy.py", 176, 600))
        # print(search_function_or_class_definition_in_code("main"))
        # print(find_references("main", "isympy.py", 176))
        # print(run_command("mkdir test"))
        print(get_patch())
    finally:
        CONTAINER.stop()
        CONTAINER.remove()
