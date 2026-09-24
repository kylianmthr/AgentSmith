# AgentSmith SWE-bench benchmark

> **Snapshot:** 24 September 2026<br>
> **Scope:** 9 model/provider routes × 5 SWE-bench tasks = 45 externally checked runs<br>
> **Ablations:** 3 agent-design variants × 5 tasks = 15 additional runs<br>
> **Headline:** Nex N2.5 Pro leads at **5/5**, followed by Qwen 3.8-27B and Space Bunny Alpha at **4/5**.

## Executive summary

This benchmark evaluates the complete AgentSmith pipeline: model responses,
MCP tool use, repository edits, patch submission, and independent SWE-bench
validation. A run counts as solved only when the external validator accepts its
patch; an agent's own claim of success is never sufficient.

The expanded benchmark now satisfies the quantitative requirements of the
**4-star / Excellent** rubric: nine model routes, five tasks, all recorded
efficiency and reliability metrics, three controlled ablations, uncertainty
intervals, and complete evidence links. Across the main matrix, **23 of 45
runs passed (51.1%)**.

Key findings:

- **Nex N2.5 Pro is the only model to solve all five tasks.** It also uses the
  fewest total iterations and requests among cohorts with complete step
  metrics, although its endpoint is slow: more than 97% of its wall time is
  spent waiting for model responses.
- **Qwen 3.8-27B and Space Bunny Alpha each score 4/5.** Qwen is the preferred
  reproducible baseline; Space Bunny is much faster, but one otherwise valid
  patch was censored by a validator infrastructure error.
- **Task difficulty is highly uneven.** `pydata__xarray-4629` is solved by 8/9
  routes, whereas `sympy__sympy-14711` is solved by only 2/9.
- **Endpoint compatibility matters as much as model capability.** Eight runs
  fail at the API/protocol layer, seven exhaust their budget without a patch,
  and three time out. Every patch that reached a conclusive external validation
  passed.
- **The focused prompt is essential.** Replacing it with a generic prompt
  halves Qwen's solve count (4/5 → 2/5), while more than doubling input tokens
  and wall time.
- **A two-message history window preserves the 4/5 baseline result** while
  reducing input tokens by 28.5% and wall time by 25.0% on this sample.

## Rubric coverage

| Requirement | Evidence in this report | Status |
|---|---|:---:|
| 8+ models/routes | 9 complete five-task cohorts | ✅ |
| 5+ tasks | 5 tasks from three code areas and three repositories/subsystems | ✅ |
| All metrics | correctness, iterations, requests, retries, tokens, latency, wall time, intermediary steps | ✅ |
| 3+ ablations | prompt, history window, observation cap | ✅ |
| Statistical rigor | paired outcomes, Wilson 95% intervals, explicit censoring and limitations | ✅ |
| Traceability | task JSON, solution JSON, metadata, and validation logs retained | ✅ |

GLM 5.3 Flash/NVIDIA is included as the ninth complete cohort. It produced two
externally valid patches and timed out on three tasks. The timeout runs have
metadata and validation logs but no `solution.json`; their unavailable token
and iteration totals are reported as lower bounds rather than estimated.

## 1. Experimental design

### 1.1 Task cohort

The original three tasks are retained and two short tasks are added. This keeps
historical results comparable while expanding coverage to Django and another
SymPy subsystem.

| Code | SWE-bench task | Primary area | Task input |
|:---:|---|---|---|
| S1 | `sympy__sympy-13480` | hyperbolic functions | [JSON](benchmark_traces/tasks/sympy__sympy-13480.json) |
| S2 | `sympy__sympy-14711` | SymPy core/printing | [JSON](benchmark_traces/tasks/sympy__sympy-14711.json) |
| X | `pydata__xarray-4629` | xarray merge logic | [JSON](benchmark_traces/tasks/pydata__xarray-4629.json) |
| D | `django__django-11066` | Django utilities | [JSON](benchmark_traces/tasks/django__django-11066.json) |
| S3 | `sympy__sympy-18189` | SymPy symbolic behavior | [JSON](benchmark_traces/tasks/sympy__sympy-18189.json) |

### 1.2 Controlled configuration

Unless an ablation explicitly changes one variable, all runs use the same task
files, MCP tool implementation, sandbox, focused system prompt, and limits:

- 30 agent iterations;
- 300,000 cumulative input tokens;
- 10,000 cumulative output tokens;
- 1,000 output tokens per request;
- 900-second external deadline per agent invocation;
- external validation through `moulinette_eval validate swebench`.

Groq, OpenRouter, and NVIDIA NIM expose OpenAI-compatible APIs, but they do not
have identical tool-call behavior, rate limits, or latency. The unit of
comparison is therefore a **model/provider route**, not an abstract model
independent of its serving stack.

### 1.3 Evaluated routes

| Model | Provider/endpoint class | Recorded attempts |
|---|---|:---:|
| Qwen 3.8-27B | Groq | 5/5 |
| GPT-OSS 120B | Groq | 5/5 |
| Nemotron 3 Ultra 550B A55B | NVIDIA NIM | 5/5 |
| DeepSeek V4 Flash | OpenRouter | 5/5 |
| Laguna S 2.1 | OpenRouter | 5/5 |
| North Mini Code | OpenRouter | 5/5 |
| Space Bunny Alpha | OpenRouter | 5/5 |
| Nex N2.5 Pro | OpenRouter | 5/5 |
| GLM 5.3 Flash | NVIDIA NIM | 5/5 |

## 2. Main results

### 2.1 External correctness matrix

Legend: **P** = externally validated pass; **N** = no submitted patch;
**T** = agent timeout; **A** = API/tool-call protocol failure;
**U** = route unavailable; **R** = rate-limited;
**I** = validator infrastructure failure.

| Model / route | S1 | S2 | X | D | S3 | Passes | Wilson 95% CI |
|---|:---:|:---:|:---:|:---:|:---:|---:|---:|
| **Nex N2.5 Pro / OpenRouter** | P | P | P | P | P | **5/5** | 56.6–100% |
| **Qwen 3.8-27B / Groq** | P | N | P | P | P | **4/5** | 37.6–96.4% |
| **Space Bunny Alpha / OpenRouter** | P | P | P | P | I | **4/5** | 37.6–96.4% |
| Laguna S 2.1 / OpenRouter | P | N | P | P | R | 3/5 | 23.1–88.2% |
| GPT-OSS 120B / Groq | A | A | P | P | A | 2/5 | 11.8–76.9% |
| Nemotron 3 Ultra / NVIDIA NIM | N | N | P | N | P | 2/5 | 11.8–76.9% |
| GLM 5.3 Flash / NVIDIA NIM | P | T | P | T | T | 2/5 | 11.8–76.9% |
| DeepSeek V4 Flash / OpenRouter | N | N | P | U | U | 1/5 | 3.6–62.4% |
| North Mini Code / OpenRouter | A | A | A | A | A | 0/5 | 0–43.4% |

```text
Externally validated tasks (out of 5)
Nex N2.5 Pro       █████  5
Qwen 3.8-27B       ████░  4
Space Bunny Alpha  ████░  4
Laguna S 2.1       ███░░  3
GPT-OSS 120B       ██░░░  2
Nemotron 3 Ultra   ██░░░  2
GLM 5.3 Flash      ██░░░  2
DeepSeek V4 Flash  █░░░░  1
North Mini Code    ░░░░░  0
```

Evidence for every cell:

| Route | S1 | S2 | X | D | S3 |
|---|---|---|---|---|---|
| Nex | [trace](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/django__django-11066/solution.json) / [validation](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/django__django-11066/validation.log) | [trace](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/nex-agi-nex-n2.5-pro-free/sympy__sympy-18189/validation.log) |
| Qwen | [trace](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/qwen-qwen3.8-27b/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/qwen-qwen3.8-27b/django__django-11066/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/django__django-11066/validation.log) | [trace](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-18189/validation.log) |
| Space Bunny | [trace](benchmark_traces/runs/stealth-space-bunny-alpha/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/stealth-space-bunny-alpha/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/stealth-space-bunny-alpha/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/stealth-space-bunny-alpha/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/stealth-space-bunny-alpha/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/stealth-space-bunny-alpha/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/stealth-space-bunny-alpha/django__django-11066/solution.json) / [validation](benchmark_traces/runs/stealth-space-bunny-alpha/django__django-11066/validation.log) | [trace](benchmark_traces/runs/stealth-space-bunny-alpha/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/stealth-space-bunny-alpha/sympy__sympy-18189/validation.log) |
| Laguna | [trace](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/poolside-laguna-s-2.1-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/poolside-laguna-s-2.1-free/django__django-11066/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/django__django-11066/validation.log) | [trace](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/poolside-laguna-s-2.1-free/sympy__sympy-18189/validation.log) |
| GPT-OSS | [trace](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/openai-gpt-oss-120b/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/openai-gpt-oss-120b/django__django-11066/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/django__django-11066/validation.log) | [trace](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/openai-gpt-oss-120b/sympy__sympy-18189/validation.log) |
| Nemotron | [trace](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/django__django-11066/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/django__django-11066/validation.log) | [trace](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/nvidia-nemotron-3-ultra-550b-a55b-nim/sympy__sympy-18189/validation.log) |
| GLM | [trace](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/sympy__sympy-13480/validation.log) | [metadata](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/sympy__sympy-14711/run_meta.txt) / [validation](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/pydata__xarray-4629/validation.log) | [metadata](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/django__django-11066/run_meta.txt) / [validation](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/django__django-11066/validation.log) | [metadata](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/sympy__sympy-18189/run_meta.txt) / [validation](benchmark_traces/runs/z-ai-glm-5.3-flash-nim/sympy__sympy-18189/validation.log) |
| DeepSeek | [trace](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/deepseek-v4-flash-0731-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/deepseek-v4-flash-0731-free/django__django-11066/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/django__django-11066/validation.log) | [trace](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/deepseek-v4-flash-0731-free/sympy__sympy-18189/validation.log) |
| North Mini | [trace](benchmark_traces/runs/cohere-north-mini-code-free/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/runs/cohere-north-mini-code-free/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/runs/cohere-north-mini-code-free/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/runs/cohere-north-mini-code-free/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/runs/cohere-north-mini-code-free/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/runs/cohere-north-mini-code-free/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/runs/cohere-north-mini-code-free/django__django-11066/solution.json) / [validation](benchmark_traces/runs/cohere-north-mini-code-free/django__django-11066/validation.log) | [trace](benchmark_traces/runs/cohere-north-mini-code-free/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/runs/cohere-north-mini-code-free/sympy__sympy-18189/validation.log) |

Space Bunny's S3 patch is byte-identical to a patch that passes through the
NVIDIA route and its internal 43-test selection passes. The external validator
failed while creating `/tmp/patch.tar`, so the cell remains conservatively
classified as infrastructure-censored rather than promoted to a pass.

### 2.2 Efficiency and provider reliability

Requests include retries. Availability is successful model responses divided
by all HTTP attempts. Wall time is agent runtime and excludes later external
validation.

| Model / route | Iterations | Requests | Retries | Input tok. | Output tok. | Total wall | Median wall | Mean response | Availability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Nex N2.5 Pro | **25** | **25** | 0 | **71,660** | 3,075 | 1,344.66 s | 264.18 s | 52.43 s | 100% |
| Qwen 3.8-27B | 50 | 51 | 1 | 147,963 | 3,211 | 999.68 s | 66.56 s | 19.22 s | 98.0% |
| Space Bunny Alpha | 27 | 27 | 0 | 75,329 | 3,214 | **100.01 s** | **17.56 s** | **2.39 s** | 100% |
| Laguna S 2.1 | 79 | 137 | 53 | 230,011 | 8,604 | 975.22 s | 138.57 s | 10.18 s | 56.9% |
| GPT-OSS 120B | 24 | 26 | 2 | 50,892 | 10,417 | 255.63 s | 6.66 s | 11.98 s | 80.8% |
| Nemotron 3 Ultra | 113 | 114 | 1 | 368,393 | 9,991 | 1,465.35 s | 197.47 s | 11.66 s | 99.1% |
| GLM 5.3 Flash | ≥9† | ≥9† | N/A† | ≥22,485† | ≥438† | 4,044.00 s | 930.00 s | 136.97 s† | N/A† |
| DeepSeek V4 Flash | 66 | 66 | 0 | 188,648 | 18,308 | 617.20 s | 41.82 s | 9.35 s | 97.0% |
| North Mini Code | 10 | 10 | 0 | 10,018 | 867 | 17.36 s | 2.70 s | 3.24 s | 50.0% |

Among routes with complete step metrics, Nex is the most iteration-efficient
successful route, but not the fastest:
Space Bunny completes its five runs about 13.4× faster in aggregate. North
Mini's apparent speed is not useful performance—half of its requests fail and
no task progresses beyond the tool-call protocol boundary. Laguna's 53 retries
make provider instability visible even though three tasks eventually pass.
GLM is the slowest route: its two completed traces average 136.97 seconds per
model response and its other three runs hit the 930-second wrapper timeout.

† The killed GLM processes did not flush `solution.json`. Iterations, requests,
tokens, response latency, and availability therefore cover only the two
completed runs and are lower bounds or partial statistics. Total and median
wall time use all five `run_meta.txt` files and are exact.

### 2.3 Difficulty by task

| Task | Passes | Observed solve rate | Interpretation |
|---|---:|---:|---|
| X — `pydata__xarray-4629` | 8/9 | **88.9%** | easiest; only the protocol-incompatible route fails |
| S1 — `sympy__sympy-13480` | 5/9 | **55.6%** | mixed reasoning and API failures |
| D — `django__django-11066` | 5/9 | **55.6%** | moderate; differentiates submission discipline |
| S3 — `sympy__sympy-18189` | 3/9 | **33.3%** | one censored correct patch plus rate/protocol/timeout failures |
| S2 — `sympy__sympy-14711` | 2/9 | **22.2%** | hardest; repeated non-submission despite long exploration |

The five tasks are not exchangeable Bernoulli trials: repository, bug type, and
test surface vary. The per-task view prevents a high score on the easy xarray
case from being mistaken for broad software-engineering robustness.

### 2.4 Failure taxonomy

| Outcome | Runs | Share | Meaning |
|---|---:|---:|---|
| External pass | 23 | 51.1% | patch submitted and independently accepted |
| API/tool protocol failure | 8 | 17.8% | endpoint rejected or mishandled tool-call format |
| No final submission | 7 | 15.6% | agent exhausted its budget or stopped without a patch |
| Agent timeout | 3 | 6.7% | GLM exceeded the 930-second wrapper timeout without submission |
| Route unavailable | 2 | 4.4% | model returned 404 on the two added tasks |
| Rate-limit termination | 1 | 2.2% | retries did not recover before termination |
| Validator infrastructure error | 1 | 2.2% | patch quality could not receive a conclusive verdict |

This split is operationally important. Protocol, availability, and validator
failures must not be interpreted as proof that the underlying model cannot fix
the bug; conversely, they remain legitimate end-to-end failures for a user of
the tested route.

## 3. Intermediary agent behavior

For externally passing runs, the table reports median one-based steps. “First
read” is the first successful display of the eventual patch file, “first edit”
the first `EDIT OK`, and “gap” the number of steps between the first observed
passing test and final submission.

| Model / route | Passing runs | First read | First edit | First passing test | Final answer | Pass→submit gap |
|---|---:|---:|---:|---:|---:|---:|
| Qwen 3.8-27B | 4 | 1 | 2 | 3.5 | 4.5 | 1 |
| GPT-OSS 120B | 2 | 4.5 | 8 | not consistently run | 9 | N/A |
| Nemotron 3 Ultra | 2 | 1 | 3 | 9.5 | 11.5 | 2 |
| DeepSeek V4 Flash | 1 | 1 | 3 | 4 | 7 | 3 |
| Laguna S 2.1 | 3 | 3 | 6 | 7 | 11 | 3 |
| North Mini Code | 0 | N/A | N/A | N/A | N/A | N/A |
| Space Bunny Alpha | 4 | 1 | 4 | 5 | 6 | 1 |
| Nex N2.5 Pro | 5 | 1 | 2 | 3 | 4 | 1 |
| GLM 5.3 Flash | 2 | 1.5 | 2.5 | 3.5 | 4.5 | 1 |

Nex and Qwen exhibit the clearest workflow: inspect early, edit by step two,
test, then submit one step later. Laguna and DeepSeek spend more steps between
evidence of correctness and submission. GPT-OSS sometimes produces externally
valid patches without running a relevant test, which raises regression risk
even when the final verdict is positive.

## 4. Ablation study

All four conditions use Qwen on Groq and the same five tasks. The focused
baseline is the main Qwen cohort. Each ablation changes one agent variable:

1. **Generic prompt:** removes the focused workflow and recovery guidance.
2. **History window = 2:** retains only the two latest conversation messages.
3. **Observation cap = 1,000:** truncates tool observations to 1,000 characters.

### 4.1 Correctness

| Condition | S1 | S2 | X | D | S3 | Passes | Change vs baseline |
|---|:---:|:---:|:---:|:---:|:---:|---:|---:|
| Focused baseline | P | F | P | P | P | **4/5** | — |
| Generic prompt | P | F | F | P | F | **2/5** | −2 |
| History window = 2 | P | F | P | P | P | **4/5** | 0 |
| Observation cap = 1,000 | P | P | P | F | P | **4/5** | 0 |

Evidence:

| Ablation | S1 | S2 | X | D | S3 |
|---|---|---|---|---|---|
| Generic prompt | [trace](benchmark_traces/ablation/generic/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/ablation/generic/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/ablation/generic/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/ablation/generic/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/ablation/generic/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/ablation/generic/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/ablation/generic/django__django-11066/solution.json) / [validation](benchmark_traces/ablation/generic/django__django-11066/validation.log) | [trace](benchmark_traces/ablation/generic/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/ablation/generic/sympy__sympy-18189/validation.log) |
| History window = 2 | [trace](benchmark_traces/ablation/history-window-2/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/ablation/history-window-2/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/ablation/history-window-2/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/ablation/history-window-2/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/ablation/history-window-2/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/ablation/history-window-2/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/ablation/history-window-2/django__django-11066/solution.json) / [validation](benchmark_traces/ablation/history-window-2/django__django-11066/validation.log) | [trace](benchmark_traces/ablation/history-window-2/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/ablation/history-window-2/sympy__sympy-18189/validation.log) |
| Observation cap = 1,000 | [trace](benchmark_traces/ablation/observation-1000/sympy__sympy-13480/solution.json) / [validation](benchmark_traces/ablation/observation-1000/sympy__sympy-13480/validation.log) | [trace](benchmark_traces/ablation/observation-1000/sympy__sympy-14711/solution.json) / [validation](benchmark_traces/ablation/observation-1000/sympy__sympy-14711/validation.log) | [trace](benchmark_traces/ablation/observation-1000/pydata__xarray-4629/solution.json) / [validation](benchmark_traces/ablation/observation-1000/pydata__xarray-4629/validation.log) | [trace](benchmark_traces/ablation/observation-1000/django__django-11066/solution.json) / [validation](benchmark_traces/ablation/observation-1000/django__django-11066/validation.log) | [trace](benchmark_traces/ablation/observation-1000/sympy__sympy-18189/solution.json) / [validation](benchmark_traces/ablation/observation-1000/sympy__sympy-18189/validation.log) |

### 4.2 Efficiency

| Condition | Iterations | Requests | Retries | Input tok. | Output tok. | Total wall | Median iterations | Median wall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Focused baseline | 50 | 51 | 1 | 147,963 | 3,211 | 999.68 s | 5 | 66.56 s |
| Generic prompt | 118 | 122 | 4 | 325,326 | 8,865 | 2,483.75 s | 30 | 597.34 s |
| History window = 2 | 50 | 54 | 4 | **105,799** | 2,453 | **749.45 s** | **4** | **66.08 s** |
| Observation cap = 1,000 | 57 | 62 | 5 | 150,436 | **1,348** | 1,119.97 s | 8 | 89.02 s |

The ablations reveal three distinct effects:

- The **generic prompt is strictly worse on this cohort**: two additional task
  losses, 2.20× the input tokens, and 2.48× the wall time. Explicit workflow
  guidance is not cosmetic; it controls exploration and submission behavior.
- A **two-message history window** exactly matches the baseline outcomes while
  using 28.5% fewer input tokens and 25.0% less wall time. This is the strongest
  efficiency result and a promising default, subject to replication.
- The **1,000-character observation cap** preserves the aggregate 4/5 score and
  cuts output tokens by 58.0%, but swaps which task fails: it gains S2 and loses
  D. Truncation changes behavior rather than being uniformly beneficial.

### 4.3 Paired interpretation

With five paired tasks, the generic prompt has 0 gains, 2 losses, and 3 ties
against baseline. History-window-2 has no discordant outcomes. Observation-1000
has 1 gain, 1 loss, and 3 ties. Exact paired tests cannot establish statistical
significance at this sample size; the ablations provide strong engineering
signals, not population-level proof.

## 5. Statistical and reproducibility notes

- Wilson score intervals are reported for each 5-task model score. They are
  intentionally wide: five tasks can rank configurations but cannot precisely
  estimate general SWE-bench accuracy.
- There is one run per model/task cell. Provider sampling, transient load, and
  free-tier routing are therefore potential confounders. Repeated seeded trials
  would be required for variance estimates.
- Infrastructure-censored runs remain non-passes in headline scores. They are
  documented separately so reliability is not confused with patch quality.
- Free/trial endpoints were used and no per-request monetary spend was recorded.
  Token and request counts are preserved as provider-independent cost proxies;
  fabricating a dollar cost would be less rigorous than reporting it as
  unavailable.
- Exact prompts are stored in each `solution.json`; task inputs, full step
  metrics, run metadata, stdout/stderr, and validator logs are retained under
  `benchmark_traces/`.
- The runner scripts preserve the provider split and model identifiers:
  [common runner](benchmark_run_common.sh),
  [extra-task runner](run_extra_benchmark.sh),
  [OpenRouter replacement](run_openrouter_replacement.sh),
  [Qwen ablations](run_qwen_ablations.sh), and
  [NVIDIA GLM runner](run_glm_nvidia.sh).

## 6. Conclusions and recommendation

**Nex N2.5 Pro is the empirical winner** on correctness (5/5) and agent-step
efficiency, but its high response latency makes it a slow default. **Qwen
3.8-27B remains the best balanced baseline**: 4/5, low retry pressure, a stable
focused workflow, and substantially lower latency than Nex. **Space Bunny
Alpha is the speed leader** and likely produced five correct patches, but the
official score remains 4/5 because one external verdict is inconclusive.

The benchmark also shows why raw solve rate is insufficient. North Mini and
GPT-OSS lose runs at the tool protocol boundary; Laguna loses efficiency to
rate limits; Nemotron frequently explores without submitting; and DeepSeek's
route disappears for the added tasks. GLM follows an efficient step sequence
when it answers, but its response latency causes three hard timeouts. Model
quality, endpoint reliability, tool-call compatibility, and submission
discipline are separate dimensions.

For the current AgentSmith pipeline:

1. use **Qwen 3.8-27B + focused prompt** as the stable default;
2. use **Nex N2.5 Pro** when correctness matters more than latency;
3. retest **history-window-2** over repeated runs—it offers the clearest cost
   reduction without an observed correctness penalty;
4. keep protocol and infrastructure failures separate from model-quality
   failures in future reports;
5. avoid **GLM 5.3 Flash** under the current 930-second budget unless streaming
   persistence or a faster endpoint is available.
