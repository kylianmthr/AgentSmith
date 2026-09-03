*This project has been created as part of the 42 curriculum by qrios, kmathuri.*

# Agent Smith

Agent Smith is a small agentic framework that autonomously solves Python coding tasks. It asks an LLM to reason about a task, extracts executable Python from the response, runs that code inside a restricted sandbox, returns the observation to the model, and repeats until the model calls `final_answer`.

The project targets two benchmarks:

- **MBPP** for short algorithmic Python problems;
- **SWE-bench** for real bug fixes in existing repositories.

The framework and orchestration loop are implemented in this repository. It does not use an external agent-orchestration framework.

## Description

The goal is to move beyond one-shot code generation and implement a complete **Thought -> Code -> Observation** workflow. The LLM writes Python that calls tools, the sandbox executes it, and the resulting output becomes context for the next iteration.

The same agent core is used by two dedicated command-line applications:

- `agent_mbpp` produces a Python solution and validates it with MBPP tests;
- `agent_swebench` explores a repository, edits files, runs the evaluation script, and returns a unified Git patch.

Each run produces a JSON `SolutionOutput` containing the final answer, per-step token usage, timings, retries, raw LLM output, sandbox input, sandbox output, and the complete system prompt.

## Architecture

```text
Task JSON
   |
   v
MBPP or SWE-bench CLI
   |
   v
Agent loop <-----------------------------+
   |                                     |
   +--> OpenAI-compatible LLM            |
   |        |                            |
   |        v                            |
   +--> Code extractor                   |
   |    Python / XML / Hermes /          |
   |    ReAct / Qwen tool-call formats   |
   |        |                            |
   |        v                            |
   +--> Sandbox manager                  |
            |                            |
            v                            |
       Isolated worker process           |
            |                            |
            +--> final_answer            |
            |                            |
            +--> dynamic MCP wrappers    |
                       |                 |
                       v                 |
              stdio or HTTP MCP client   |
                       |                 |
                       v                 |
             MBPP / SWE-bench server ----+
                   observation
```

Main packages and entry points:

```text
agent_smith/
  agent/          Agent loop, environment loading, response extraction
  llm/            OpenAI-compatible client and response model
  mcp_client/     stdio/HTTP transports and dynamic tool wrappers
  models/         Pydantic task, configuration, metrics and result models
  sandbox/        REPL, manager, worker and validation layers
agent_mbpp/       MBPP command-line agent
agent_swebench/   SWE-bench command-line agent
mcp_tools_mbpp.py
mcp_tools_swebench.py
```

## Agent Loop

The agent starts with a benchmark-specific system prompt, the task, and a manual generated from the connected MCP server's tool schemas. Every iteration performs the following sequence:

1. send the current conversation to the selected LLM;
2. record latency, token counts, retry count, endpoint and raw output;
3. extract Python or translate a supported tool-call format into Python;
4. execute the extracted code in the persistent sandbox namespace;
5. capture stdout, stderr, errors and a possible `final_answer`;
6. append the observation to the conversation and continue.

The loop stops when the model calls `final_answer`, reaches the iteration or token budget, or encounters an unrecoverable sandbox error. Conversation history and large observations are truncated to control cumulative token usage, with an explicit message telling the model what was removed.

For MBPP, the final answer is the complete Python solution. For SWE-bench, it must be a unified Git diff returned by `get_patch()`.

## Sandbox Design

LLM-generated code executes in a dedicated worker process managed through multiprocessing queues. The namespace persists across iterations so the model can define a value in one step and reuse it later.

The sandbox applies several controls:

- an allowlist for Python imports;
- a restricted builtin namespace;
- AST checks for unsafe attributes and exception handling;
- filesystem path checks on MCP tool arguments;
- execution timeout using process-local signals;
- memory limits using operating-system resource limits;
- no direct network modules in the allowed imports;
- propagation and cleanup for `KeyboardInterrupt` and `SystemExit`.

`final_answer` is injected directly by the sandbox. It is deliberately separate from MCP and remains available with any connected server.

The `sandbox` command provides both an interactive REPL and a stdin mode used by the examination scripts.

## MCP Client and Tools

The sandbox can connect to an MCP server over stdio or streamable HTTP. It discovers tool schemas dynamically, creates Python wrappers, and generates the manual included in the LLM system prompt. This allows the sandbox to work with an unknown compatible server without hardcoding its tools.

The MBPP server exposes:

- `run_tests(code)` — execute the task tests against a proposed solution.

The SWE-bench server exposes all mandatory tools:

| Tool | Purpose |
|---|---|
| `read_file` | Read a line range with numbered output |
| `edit_file` | Perform one exact string replacement |
| `list_files` | List files matching a pattern |
| `search_code` | Search repository text with file and line information |
| `search_function_or_class_definition_in_code` | Locate a definition |
| `find_references` | Locate symbol references with Jedi |
| `run_command` | Run a command in the testbed |
| `run_tests` | Execute the supplied evaluation script |
| `get_patch` | Return the current unified Git diff |

SWE-bench tools run outside the untrusted Python namespace and operate on the task's Docker container or configured testbed.

## Contributors

- **Quentin Rios (`qrios`)** focused primarily on the sandbox and MCP client: process isolation, restricted execution, resource limits, REPL behavior, MCP transports, dynamic wrappers, path validation and lifecycle handling.
- **Kylian Mathurin (`kmathuri`)** focused primarily on the MCP servers and tools, the agent loop, MBPP and SWE-bench agents, prompts, code extraction, LLM handling, metrics and benchmark integration.

Both contributors participated in integration, testing, debugging and review across component boundaries.

## Instructions

### Requirements

- Python 3.10 or newer;
- [uv](https://docs.astral.sh/uv/);
- Docker with a running daemon for SWE-bench;
- access to a free OpenAI-compatible LLM endpoint;
- one or more API keys for that endpoint.

Install the locked dependencies from the repository root:

```bash
uv sync
cp .env.example .env
```

Edit `.env` and set `API_KEY`. Multiple keys can be supplied as a comma-separated list and are rotated when the provider returns a permission or rate-limit error.

### Sandbox

```bash
# Interactive sandbox
uv run sandbox

# Custom restrictions
uv run sandbox sandbox_template.json

# MCP over stdio
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json

# Connect to an existing HTTP MCP server
uv run sandbox --mcp-server http://127.0.0.1:8000/mcp sandbox_template.json

# Start an HTTP server and connect to it
uv run python mcp_tools_mbpp.py --transport http --host 127.0.0.1 --port 8000 --path /mcp
```

Enter `exit` or press Ctrl+D to leave the interactive sandbox.

### MBPP agent

```bash
uv run python -m agent_mbpp \
  --task-file cache/mbpp_task.json \
  --output cache/mbpp_solution.json \
  --model-name "provider/model" \
  --provider-url "https://provider.example/v1"
```

### SWE-bench agent

Docker must be available before starting a SWE-bench task.

```bash
docker info

uv run python -m agent_swebench \
  --task-file cache/swebench_task.json \
  --output cache/swebench_solution.json \
  --model-name "provider/model" \
  --provider-url "https://provider.example/v1"
```

### Local tests

```bash
# Complete repository test suite
uv run pytest -q

# Exclude marked slow and integration tests during development
uv run pytest -q -m "not slow and not integration"
```

### Examination scripts

The official scripts require three sibling workspaces: this repository, the supplied `moulinette`, and the supplied `exams`. Install both Python environments and create `.env` before running them.

In the current local checkout, the exam archive is nested under `exams/exams/` and the moulinette should be extracted next to this repository as `../moulinette`:

```bash
uv sync
uv --directory ../moulinette sync
docker info

./exams/exams/exam_sandbox.sh \
  --student-path . \
  --moulinette-path ../moulinette \
  --env-file .env

./exams/exams/exam_mbpp.sh \
  --student-path . \
  --moulinette-path ../moulinette \
  --env-file .env

./exams/exams/exam_swebench.sh \
  --student-path . \
  --moulinette-path ../moulinette \
  --env-file .env

./exams/exams/exam_anticheat.sh --student-path .
```

The sandbox exam requires every non-bonus test to pass. MBPP requires at least 4 of 5 tasks; SWE-bench requires at least 2 of 3 tasks and successful Docker cleanup.

## Models and Evaluation Output

Task files are validated as `MBPPTaskInput` or `SWEBenchTaskInput`. Every agent run writes a `SolutionOutput` JSON containing:

- task and benchmark identifiers;
- success state and submitted solution;
- iteration, request, token and wall-time totals;
- the full system prompt;
- one `StepMetrics` entry per iteration;
- raw LLM output and sandbox input/output for traceability;
- endpoint, model and retry metadata.

API secrets must stay in `.env`, which is ignored by Git. Never commit real keys or place them in prompts, logs or result files.

## Benchmark Results and Analysis

The canonical model comparison belongs in [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md), backed by committed `solution.json` traces. The required experiment compares at least five models on the same three or more SWE-bench tasks and records pass/fail, iterations, input/output tokens, wall time, provider reliability, at least two intermediary exploration metrics, and an ablation study.

Measured benchmark data has not yet been added to this repository. This section and `BENCHMARK_REPORT.md` must be updated from real runs before project submission; results must not be estimated or fabricated.

## Resources

- [Python `ast` documentation](https://docs.python.org/3/library/ast.html)
- [Python multiprocessing documentation](https://docs.python.org/3/library/multiprocessing.html)
- [Python resource limits](https://docs.python.org/3/library/resource.html)
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification/latest)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/)
- [SWE-bench repository](https://github.com/SWE-bench/SWE-bench)
- [SWE-bench paper](https://arxiv.org/abs/2310.06770)
- [Google Research MBPP dataset](https://github.com/google-research/google-research/tree/master/mbpp)

### Use of AI

AI assistants were used to help review code paths, identify edge cases, debug test failures, and draft project documentation. Suggestions and generated text were inspected and adapted by the contributors. Architectural decisions, security trade-offs, implementation, benchmark execution and final validation remain the responsibility of the project authors.
