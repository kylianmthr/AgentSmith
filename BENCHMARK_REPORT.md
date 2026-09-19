# SWE-bench model benchmark

## Status

This report contains a complete five-model by three-task matrix, an external
validation result for every run, provider-reliability measurements, intermediary
agent metrics, and a three-task prompt ablation. All values come from the linked
`solution.json`, `run_meta.txt`, and validation logs; no missing result was
estimated.

Two OpenRouter models were unavailable because the supplied free-tier key had
already exhausted its daily free-model quota. Their real retry and failure
traces are retained because provider availability is part of the required
benchmark, but those rows do not measure the underlying models' coding ability.

## Setup

The benchmark was run on 2026-09-19 from the current working tree based on Git
revision `bc738df`. The HTTP startup fix and an unrelated REPL import cleanup
were locally modified; neither changes the stdio SWE-bench agent loop used here.

All models received the same task JSON, focused system prompt, dynamically
generated MCP manual, tool implementation, and limits:

- 30 agent iterations;
- 300,000 cumulative input tokens;
- 10,000 cumulative output tokens;
- 1,000 output tokens per request;
- a 900-second external deadline per agent run.

The fixed task cohort uses three tasks explicitly suggested by the project
subject for initial SWE-bench evaluation. It spans two SymPy subsystems and one
xarray merge bug.

| Code | Task | Primary changed area | Input |
|---|---|---|---|
| S1 | `sympy__sympy-13480` | Hyperbolic functions | [task JSON](benchmark_traces/tasks/sympy__sympy-13480.json) |
| S2 | `sympy__sympy-14711` | SymPy core/printing behavior | [task JSON](benchmark_traces/tasks/sympy__sympy-14711.json) |
| X | `pydata__xarray-4629` | `xarray/core/merge.py` | [task JSON](benchmark_traces/tasks/pydata__xarray-4629.json) |

Groq used the active comma-separated keys from the supplied `.env`. OpenRouter
used the commented key from that file and `https://openrouter.ai/api/v1`.

## Results

`Pass` is the external `moulinette_eval validate swebench` verdict, not the
agent's self-reported success. Wall time is the agent's recorded end-to-end
time and excludes the subsequent external validation.

| Model / provider | Task | Pass | Iterations | Requests | Input tokens | Output tokens | Wall time | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Qwen 3.8-27B / Groq | S1 | Yes | 4 | 4 | 7,948 | 138 | 10.79 s | [JSON](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-13480/validation.log) |
| Qwen 3.8-27B / Groq | S2 | No | 30 | 30 | 91,876 | 2,359 | 761.37 s | [JSON](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-14711/validation.log) |
| Qwen 3.8-27B / Groq | X | Yes | 7 | 8 | 22,710 | 400 | 124.26 s | [JSON](benchmark_traces/runs/qwen-qwen3.8-27b/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/pydata__xarray-4629/validation.log) |
| GPT-OSS 120B / Groq | S1 | No | 1 | 1 | 0 | 0 | 1.82 s | [JSON](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-13480/validation.log) |
| GPT-OSS 120B / Groq | S2 | No | 3 | 3 | 3,179 | 2,000 | 6.66 s | [JSON](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-14711/validation.log) |
| GPT-OSS 120B / Groq | X | Yes | 10 | 10 | 24,923 | 4,427 | 183.32 s | [JSON](benchmark_traces/runs/openai-gpt-oss-120b/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/pydata__xarray-4629/validation.log) |
| Nemotron 3 Ultra 550B / OpenRouter | S1 | No | 1 | 6 | 0 | 0 | 44.41 s | [JSON](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-free/sympy__sympy-13480/validation.log) |
| Nemotron 3 Ultra 550B / OpenRouter | S2 | No | 1 | 6 | 0 | 0 | 42.74 s | [JSON](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-free/sympy__sympy-14711/validation.log) |
| Nemotron 3 Ultra 550B / OpenRouter | X | No | 1 | 6 | 0 | 0 | 43.69 s | [JSON](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-free/pydata__xarray-4629/validation.log) |
| DeepSeek V4 Flash / OpenRouter | S1 | No | 27 | 27 | 68,834 | 10,000 | 338.39 s | [JSON](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-13480/validation.log) |
| DeepSeek V4 Flash / OpenRouter | S2 | No | 30 | 30 | 95,822 | 7,273 | 236.30 s | [JSON](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-14711/validation.log) |
| DeepSeek V4 Flash / OpenRouter | X | Yes | 7 | 7 | 23,992 | 1,035 | 41.82 s | [JSON](benchmark_traces/runs/deepseek-v4-flash-0731-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/pydata__xarray-4629/validation.log) |
| Laguna S 2.1 / OpenRouter | S1 | No | 1 | 6 | 0 | 0 | 43.31 s | [JSON](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-13480/validation.log) |
| Laguna S 2.1 / OpenRouter | S2 | No | 1 | 6 | 0 | 0 | 42.65 s | [JSON](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-14711/validation.log) |
| Laguna S 2.1 / OpenRouter | X | No | 1 | 6 | 0 | 0 | 43.00 s | [JSON](benchmark_traces/runs/poolside-laguna-s-2.1-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/pydata__xarray-4629/validation.log) |

Qwen is the only model meeting the examination solve threshold on this cohort:
2/3 externally valid patches. GPT-OSS and DeepSeek each solved 1/3. Nemotron
and Laguna could not produce a response because of the shared OpenRouter quota.

## Provider reliability

Availability is successful LLM responses divided by all HTTP attempts. Mean
response time is calculated from successful responses recorded in
`StepMetrics`. Failed OpenRouter requests did not return usage or latency data,
so their per-request mean cannot be reconstructed; their complete retry wall
time remains visible in each `solution.json`.

| Model / provider | Successful responses / attempts | API retries | Terminal error | Mean successful response | Observed availability |
|---|---:|---:|---|---:|---:|
| Qwen 3.8-27B / Groq | 41 / 42 | 1 | None | 21.51 s | 97.6% |
| GPT-OSS 120B / Groq | 12 / 14 | 0 | 2 HTTP 400 protocol errors | 15.73 s | 85.7% |
| Nemotron 3 Ultra / OpenRouter | 0 / 18 | 15 | 3 HTTP 429 quota errors | Not measurable | 0% |
| DeepSeek V4 Flash / OpenRouter | 64 / 64 | 0 | None | 9.35 s | 100% |
| Laguna S 2.1 / OpenRouter | 0 / 18 | 15 | 3 HTTP 429 quota errors | Not measurable | 0% |

GPT-OSS failed when Groq rejected model-generated native tool calls with
`Tool choice is none, but model called a tool`. Nemotron and Laguna exhausted
all five configured retries on every task. OpenRouter reported a free-tier
daily limit of 50 requests and zero remaining requests, with reset scheduled
for 2026-09-20 02:00 CEST. DeepSeek remained available through the same key,
which indicates model-route-specific availability rather than a total endpoint
outage.

## Intermediary agent metrics

Steps are one-based. Metrics are reported for externally valid patches. “First
read” is the first successful display of the final patch file, “first edit” is
the first `EDIT OK`, and the submission gap is final-answer step minus the first
observed passing test step.

| Condition / model | Task | First read | First edit | Tests first pass | Final answer | Pass-to-submit gap |
|---|---|---:|---:|---:|---:|---:|
| Focused / Qwen | S1 | 1 | 2 | 3 | 4 | 1 |
| Focused / Qwen | X | 1 | 2 | 6 | 7 | 1 |
| Focused / GPT-OSS | X | 8 | 9 | Not run | 10 | N/A |
| Focused / DeepSeek | X | 2 | 3 | 4 | 7 | 3 |
| Generic / Qwen | S1 | 1 | 11 | 19 | 22 | 3 |

The GPT-OSS patch passed external validation without the agent running tests.
This is a submission-discipline risk even though the patch itself was correct.
The focused Qwen prompt consistently submitted one iteration after observing
passing tests, while DeepSeek spent three additional iterations.

## Prompt ablation

The ablation reused Qwen, Groq, all three task files, tools, limits, and
validation procedure. Only the system prompt changed. The generic condition
instructed the model to inspect, edit, test, and submit with
`final_answer(get_patch())`, without the focused workflow and error-recovery
guidance. Each trace preserves the full actual prompt in `system_prompt`.

| Task | Focused result / iterations / time | Generic result / iterations / time | Generic evidence |
|---|---|---|---|
| S1 | Pass / 4 / 10.79 s | Pass / 22 / 348.55 s | [JSON](benchmark_traces/ablation/generic/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/ablation/generic/sympy__sympy-13480/validation.log) |
| S2 | Fail / 30 / 761.37 s | Fail / 30 / 716.50 s | [JSON](benchmark_traces/ablation/generic/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/ablation/generic/sympy__sympy-14711/validation.log) |
| X | Pass / 7 / 124.26 s | Fail / 30 / 597.34 s | [JSON](benchmark_traces/ablation/generic/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/ablation/generic/pydata__xarray-4629/validation.log) |

Across the three tasks, the focused prompt passed 2/3 versus 1/3 for the generic
prompt. Focused Qwen used 41 iterations, 122,534 input tokens, 2,897 output
tokens, and 896.42 seconds. Generic Qwen used 82 iterations, 219,964 input
tokens, 6,110 output tokens, and 1,662.39 seconds. On S1, the generic prompt
did not make its first successful edit until step 11, compared with step 2 for
the focused prompt. The focused methodology therefore improved both solve rate
and exploration efficiency on this cohort.

## Conclusions

Qwen 3.8-27B on Groq is the selected default for the final pipeline. It is the
only tested configuration that reached the required 2/3 solve threshold, and
its focused prompt was materially better than the generic ablation.

DeepSeek V4 Flash is the strongest fallback from a provider perspective: it had
100% observed API availability and the lowest mean response time, but solved
only 1/3 and exhausted the output-token budget on S1. GPT-OSS 120B also solved
1/3, but its native-tool-call incompatibility makes it less reliable with the
current client protocol.

Nemotron 3 Ultra and Laguna S 2.1 should be excluded operationally with the
currently supplied OpenRouter free-tier key because they were completely
unavailable during the benchmark. This result is not evidence about their
underlying coding quality; a fair model-quality comparison requires rerunning
their three saved tasks after the quota reset.
