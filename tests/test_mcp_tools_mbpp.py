import json
import pytest
import mcp_tools_mbpp as srv


VALID_TASK = {
    "task_id": 42,
    "task_definition": "Write a function add(a, b) that returns the sum.",
    "function_definition": "def add(a, b):",
    "test_imports": [],
    "test_list": [
        "assert add(1, 2) == 3",
        "assert add(0, 0) == 0",
        "assert add(-1, 1) == 0",
    ],
}

GOOD_SOLUTION = "def add(a, b):\n    return a + b\n"


def write_task(tmp_path, **overrides):
    data = {**VALID_TASK, **overrides}
    path = tmp_path / "task.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture(autouse=True)
def reset_globals(monkeypatch):
    monkeypatch.setattr(srv, "TEST_LIST", [])
    monkeypatch.setattr(srv, "TEST_IMPORT", [])
    monkeypatch.setattr(srv, "TASK_DEFINITION", "")
    monkeypatch.setattr(srv, "FUNCTION_DEFINITION", "")
    monkeypatch.setattr(srv, "TASK_ID", "")


@pytest.fixture
def loaded_task(tmp_path):
    assert srv.load_task_file(write_task(tmp_path)) is True
    return VALID_TASK


class TestLoadTaskFile:
    def test_valid_file(self, tmp_path):
        assert srv.load_task_file(write_task(tmp_path)) is True

    def test_valid_file_load_global_var(self, tmp_path):
        srv.load_task_file(write_task(tmp_path))

        assert srv.TASK_ID == 42
        assert srv.TASK_DEFINITION == VALID_TASK["task_definition"]
        assert srv.FUNCTION_DEFINITION == VALID_TASK["function_definition"]
        assert srv.TEST_LIST == VALID_TASK["test_list"]
        assert srv.TEST_IMPORT == []

    def test_import_loaded(self, tmp_path):
        srv.load_task_file(write_task(tmp_path, test_imports=["import math"]))
        assert srv.TEST_IMPORT == ["import math"]

    def test_invalid_file(self, tmp_path):
        assert srv.load_task_file(str(tmp_path / "nope.json")) is False

    def test_json_malformed(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ this is not json")
        assert srv.load_task_file(str(path)) is False

    def test_other_json_object(self, tmp_path):
        path = tmp_path / "other.json"
        path.write_text(json.dumps({"hello": "world"}))
        assert srv.load_task_file(str(path)) is False

    def test_missing_fields(self, tmp_path):
        data = {k: v for k, v in VALID_TASK.items() if k != "task_definition"}
        path = tmp_path / "missing.json"
        path.write_text(json.dumps(data))
        assert srv.load_task_file(str(path)) is False

    def test_wrong_type(self, tmp_path):
        assert srv.load_task_file(write_task(tmp_path, task_id="aaaaah")) is False

    def test_error_dont_change_global_var(self, tmp_path, loaded_task):
        srv.load_task_file(str(tmp_path / "nope.json"))
        assert srv.TEST_LIST == VALID_TASK["test_list"]

    def test_pydantic_default_value(self, tmp_path):
        data = {k: v for k, v in VALID_TASK.items() if k not in ("test_imports",)}
        path = tmp_path / "no_imports.json"
        path.write_text(json.dumps(data))
        assert srv.load_task_file(str(path)) is True
        assert srv.TEST_IMPORT == []


class TestLastLine:
    @pytest.mark.parametrize(
        "stderr, expected",
        [
            ("one line", "one line"),
            ("1\n2\n3", "3"),
            ("with\nfinal newline\n", "final newline"),
            ("multiple\n\n\nnewlines\n\n\n", "newlines"),
            ("empty\n   \n line \n  \n", " line"),
            ("", ""),
            ("\n\n\n", ""),
            ("     ", ""),
        ],
    )
    def test_last_line_not_empty(self, stderr, expected):
        assert srv.last_line(stderr) == expected

    def test_traceback(self):
        tb = (
            "Traceback (most recent call last):\n"
            '  File "<stdin>", line 4, in <module>\n'
            "AssertionError\n"
        )
        assert srv.last_line(tb) == "AssertionError"


class TestRunTestsSansTache:
    def test_no_task_loaded(self):
        assert srv.run_tests(GOOD_SOLUTION) == "ERROR: No tests provided"

    def test_empty_code(self):
        assert srv.run_tests("") == "ERROR: No tests provided"


class TestRunTests:
    def test_good_solution(self, loaded_task):
        assert srv.run_tests(GOOD_SOLUTION).startswith("3/3 tests passed")

    def test_good_solution_without_failure(self, loaded_task):
        res = srv.run_tests(GOOD_SOLUTION)
        assert "FAILED" not in res
        assert res.strip() == "3/3 tests passed"

    def test_partial_solution(self, loaded_task):
        code = "def add(a, b):\n    return 3\n"
        res = srv.run_tests(code)

        assert res.startswith("1/3 tests passed")
        assert "FAILED: assert add(0, 0) == 0" in res
        assert "AssertionError" in res

    def test_wrong_solution(self, loaded_task):
        code = "def add(a, b):\n    return None\n"
        assert srv.run_tests(code).startswith("0/3 tests passed")

    def test_missing_function(self, loaded_task):
        res = srv.run_tests("x = 1\n")

        assert res.startswith("0/3 tests passed")
        assert "NameError" in res

    def test_empty_code(self, loaded_task):
        assert srv.run_tests("").startswith("0/3 tests passed")

    def test_syntax_error(self, loaded_task):
        res = srv.run_tests("def add(a, b)\n    return a + b\n")

        assert res.startswith("0/3 tests passed")
        assert "SyntaxError" in res

    def test_stderr_empty(self, loaded_task, tmp_path):
        srv.load_task_file(write_task(tmp_path, test_list=["import sys; sys.exit(1)"]))
        res = srv.run_tests(GOOD_SOLUTION)

        assert res.startswith("0/1 tests passed")
        assert "No stderr" in res


class TestRunTestsImports:
    def test_solution_with_lib(self, tmp_path):
        srv.load_task_file(
            write_task(
                tmp_path,
                function_definition="def circle_area(r):",
                test_list=["assert abs(circle_area(1) - 3.14159) < 1e-4"],
            )
        )
        code = "import math\n\ndef circle_area(r):\n    return math.pi * r ** 2\n"

        assert srv.run_tests(code).startswith("1/1 tests passed")

    def test_import_loaded_top_of_code_string(self, tmp_path):
        srv.load_task_file(
            write_task(
                tmp_path,
                test_imports=["import math"],
                function_definition="def double(x):",
                test_list=["assert double(math.pi) == 2 * math.pi"],
            )
        )
        code = "def double(x):\n    return 2 * x\n"

        assert srv.run_tests(code).startswith("1/1 tests passed")

    def test_with_missing_lib(self, tmp_path):
        srv.load_task_file(
            write_task(
                tmp_path,
                test_imports=[],
                function_definition="def double(x):",
                test_list=["assert double(math.pi) == 2 * math.pi"],
            )
        )
        res = srv.run_tests("def double(x):\n    return 2 * x\n")

        assert res.startswith("0/1 tests passed")
        assert "NameError" in res


class TestRunTestsTroncature:
    @pytest.fixture
    def five_tests(self, tmp_path):
        srv.load_task_file(
            write_task(
                tmp_path,
                test_list=[f"assert add({i}, 0) == {i}" for i in range(5)],
            )
        )

    def test_max_three_failures(self, five_tests):
        res = srv.run_tests("def add(a, b):\n    return 999\n")

        assert res.startswith("0/5 tests passed")
        assert res.count("FAILED:") == 3

    def test_tronc_message(self, five_tests):
        res = srv.run_tests("def add(a, b):\n    return 999\n")
        assert "2 additional failures not displayed" in res

    def test_no_additional_failure_if_less_than_three(self, loaded_task):
        res = srv.run_tests("def add(a, b):\n    return 999\n")

        assert res.count("FAILED:") == 3
        assert "additional failures" not in res


@pytest.mark.slow
class TestRunTestsTimeout:
    def test_infinite_loop(self, tmp_path):
        srv.load_task_file(
            write_task(
                tmp_path,
                function_definition="def loop():",
                test_list=["assert loop() is None"],
            )
        )
        code = "def loop():\n    while True:\n        pass\n"
        res = srv.run_tests(code)

        assert res.startswith("0/1 tests passed")
        assert "TIMEOUT" in res
        assert "10s" in res

    def test_timeout_and_other_test(self, tmp_path):
        srv.load_task_file(
            write_task(
                tmp_path,
                function_definition="def add(a, b):",
                test_list=[
                    "assert add(1, 2) == 3",
                    "while True: pass",
                    "assert add(0, 0) == 0",
                ],
            )
        )
        res = srv.run_tests(GOOD_SOLUTION)

        assert res.startswith("2/3 tests passed")
        assert "TIMEOUT" in res


class TestGetTask:
    def test_three_section(self, loaded_task):
        res = srv.get_task()

        assert "TASK DEFINITION" in res
        assert "FUNCTION DEFINITION" in res
        assert "TESTS" in res

    def test_task_details(self, loaded_task):
        res = srv.get_task()

        assert VALID_TASK["task_definition"] in res
        assert VALID_TASK["function_definition"] in res
        for test in VALID_TASK["test_list"]:
            assert test in res

    def test_tests_separated(self, loaded_task):
        res = srv.get_task()
        bloc_tests = res.split("TESTS\n", 1)[1]
        assert bloc_tests.strip().count("\n") == len(VALID_TASK["test_list"]) - 1

    def test_see_task_without_task(self):
        res = srv.get_task()
        assert "TASK DEFINITION" in res


class TestGetPrompt:
    def test_valid_prompt(self):
        assert len(srv.get_prompt()) > 0

    def test_same_prompt_with_task(self, tmp_path):
        avant = srv.get_prompt()
        srv.load_task_file(write_task(tmp_path))
        assert srv.get_prompt() == avant


class TestTransportType:
    def test_values(self):
        assert srv.TransportType.STDIO == "stdio"
        assert srv.TransportType.HTTP == "http"

    def test_from_string(self):
        assert srv.TransportType("stdio") is srv.TransportType.STDIO
        assert srv.TransportType("http") is srv.TransportType.HTTP

    def test_invalid_transport_type(self):
        with pytest.raises(ValueError):
            srv.TransportType("websocket")
