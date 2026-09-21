# SWE-bench model benchmark

## Status

This report contains a complete five-model by three-task matrix, an external
validation result for every run, provider-reliability measurements, intermediary
agent metrics, and a three-task prompt ablation. All values come from the linked
`solution.json`, `run_meta.txt`, and validation logs; no missing result was
estimated.

Only the five models with a complete three-task cohort are retained here. Short
compatibility or availability probes for other models were excluded because
they did not produce comparable results on all three tasks. Nemotron uses
NVIDIA NIM because its OpenRouter route sometimes omitted usage metadata.

## Setup

The original Groq and OpenRouter runs were captured on 2026-09-19 from Git
revision `bc738df`. The direct-NVIDIA completion was captured on 2026-09-20
from revision `2eddca0`. The local OpenRouter usage-tracking change does not
affect the direct NVIDIA endpoint or the stdio SWE-bench agent loop.

All models received the same task JSON, focused system prompt, dynamically
generated MCP manual, tool implementation, and limits:

- 30 agent iterations;
- 300,000 cumulative input tokens;
- 10,000 cumulative output tokens;
- 1,000 output tokens per request;
- a 900-second external deadline per agent run.

The fixed task cohort uses three tasks explicitly suggested by the project
subject for initial SWE-bench evaluation. It spans two SymPy subsystems and one
xarray merge bug. The model set covers two Groq-served general models (Qwen and
GPT-OSS), two coding-oriented OpenRouter models (DeepSeek and Laguna), and
Nemotron through a second independent provider, NVIDIA NIM. This gives useful
variation in model family, provider, tool-call behavior, and reliability while
keeping the tasks and agent implementation constant.

| Code | Task | Primary changed area | Input |
|---|---|---|---|
| S1 | `sympy__sympy-13480` | Hyperbolic functions | [task JSON](benchmark_traces/tasks/sympy__sympy-13480.json) |
| S2 | `sympy__sympy-14711` | SymPy core/printing behavior | [task JSON](benchmark_traces/tasks/sympy__sympy-14711.json) |
| X | `pydata__xarray-4629` | `xarray/core/merge.py` | [task JSON](benchmark_traces/tasks/pydata__xarray-4629.json) |

Groq and OpenRouter used the keys supplied for those runs. The Nemotron rerun
used a separate NVIDIA API Catalog key and the OpenAI-compatible endpoint
`https://integrate.api.nvidia.com/v1`.

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
| Nemotron 3 Ultra 550B / NVIDIA NIM | S1 | No | 30 | 30 | 73,336 | 2,937 | 432.21 s | [JSON](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-13480/validation.log) |
| Nemotron 3 Ultra 550B / NVIDIA NIM | S2 | No | 30 | 30 | 88,232 | 2,506 | 616.47 s | [JSON](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-14711/validation.log) |
| Nemotron 3 Ultra 550B / NVIDIA NIM | X | Yes | 14 | 14 | 47,249 | 1,793 | 197.47 s | [JSON](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/pydata__xarray-4629/validation.log) |
| DeepSeek V4 Flash / OpenRouter | S1 | No | 27 | 27 | 68,834 | 10,000 | 338.39 s | [JSON](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-13480/validation.log) |
| DeepSeek V4 Flash / OpenRouter | S2 | No | 30 | 30 | 95,822 | 7,273 | 236.30 s | [JSON](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-14711/validation.log) |
| DeepSeek V4 Flash / OpenRouter | X | Yes | 7 | 7 | 23,992 | 1,035 | 41.82 s | [JSON](benchmark_traces/runs/deepseek-v4-flash-0731-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/pydata__xarray-4629/validation.log) |
| Laguna S 2.1 / OpenRouter | S1 | Yes | 11 | 19 | 25,305 | 611 | 138.57 s | [JSON](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-13480/validation.log) |
| Laguna S 2.1 / OpenRouter | S2 | No | 30 | 56 | 93,025 | 4,011 | 395.96 s | [JSON](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-14711/validation.log) |
| Laguna S 2.1 / OpenRouter | X | Yes | 24 | 35 | 71,416 | 3,208 | 281.15 s | [JSON](benchmark_traces/runs/poolside-laguna-s-2.1-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/pydata__xarray-4629/validation.log) |

Qwen and Laguna meet the examination solve threshold on this cohort with 2/3
externally valid patches. GPT-OSS, Nemotron, and DeepSeek each solved 1/3.

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
| Nemotron 3 Ultra / NVIDIA NIM | 74 / 74 | 0 | None | 15.23 s | 100% |
| DeepSeek V4 Flash / OpenRouter | 64 / 64 | 0 | None | 9.35 s | 100% |
| Laguna S 2.1 / OpenRouter | 65 / 110 | 45 | None | 10.82 s | 59.1% |

GPT-OSS failed when Groq rejected model-generated native tool calls with
`Tool choice is none, but model called a tool`. Direct NVIDIA NIM returned
usage metrics on every Nemotron response and needed no retry. Laguna eventually
completed all three runs, but 45 of 110 HTTP attempts were retries after
OpenRouter or its upstream provider returned rate-limit errors. DeepSeek had no
provider error; its S1 run stopped on the agent's output-token budget.

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
| Focused / Nemotron | X | 1 | 3 | 12 | 14 | 2 |
| Focused / Laguna | S1 | 3 | 6 | 7 | 11 | 4 |
| Focused / Laguna | X | 5 | 15 | 21 | 24 | 3 |
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

Qwen 3.8-27B on Groq remains the selected default for the final pipeline. It
reached the required 2/3 solve threshold with far fewer iterations and HTTP
retries than Laguna, and its focused prompt was materially better than the
generic ablation.

DeepSeek V4 Flash is the strongest fallback from a provider perspective: it had
100% observed API availability and the lowest mean response time, but solved
only 1/3 and exhausted the output-token budget on S1. GPT-OSS 120B also solved
1/3, but its native-tool-call incompatibility makes it less reliable with the
current client protocol.

Laguna S 2.1 also reached 2/3, but its native tool-call formatting caused many
invalid responses and its OpenRouter route required 45 retries. Nemotron's
direct NVIDIA endpoint was fully available and solved 1/3; on both SymPy tasks
it found useful changes but exhausted all 30 iterations without submitting a
patch. Nemotron is therefore technically usable through NVIDIA NIM, but it is
not a reliable default for this agent protocol.
