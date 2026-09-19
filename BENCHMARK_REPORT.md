# SWE-bench benchmark report

**Status: preliminary, not yet compliant with the five-model requirement.**
The correction requires at least five models on at least three common tasks.
This report contains new runs for three accessible models on the same three
tasks, plus a controlled prompt ablation. Two further models remain to be run;
no missing result is estimated or presented as complete.

## Experimental setup

The runs were made on 2026-09-18 from agent code at Git revision `6c93fbe`.
Only the report and unrelated local files were dirty; the tracked agent code
was unchanged during the experiment. Each model received the same task JSON,
the same tool implementations, and the same SWE-bench agent settings: 30
iterations maximum, 1,000 output tokens per request, 10,000 output tokens in
total, and a 600-second sandbox-manager limit. A separate 900-second shell
timeout guarded each invocation. All models used the Groq OpenAI-compatible
endpoint. The model names below are the exact API identifiers, not inferred
model families.

The three tasks were selected before comparing models. They cover a
scikit-learn public API change and two different SymPy subsystems. They are a
small fixed cohort, not a representative sample of SWE-bench. The input files
are preserved at [SK](benchmark_traces/tasks/scikit-learn__scikit-learn-13439.json),
[S1](benchmark_traces/tasks/sympy__sympy-13480.json), and
[S2](benchmark_traces/tasks/sympy__sympy-18189.json).

| Code | Task | Changed area |
| --- | --- | --- |
| SK | `scikit-learn__scikit-learn-13439` | `sklearn/pipeline.py` |
| S1 | `sympy__sympy-13480` | `sympy/functions/elementary/hyperbolic.py` |
| S2 | `sympy__sympy-18189` | `sympy/solvers/diophantine.py` |

`qwen/qwen3.8-27b` was the project's configured model. The two other
accessible general-purpose models, `openai/gpt-oss-20b` and
`openai/gpt-oss-120b`, offer a useful size contrast at the same endpoint.
This is a comparison of the **current agent plus provider interface**, not
an isolated measure of raw model coding ability. The GPT-OSS failures below
are primarily protocol incompatibilities.

## Model comparison

`Pass` is the external `moulinette_eval validate swebench` verdict for a
submitted patch. A dash means that no patch was submitted, so external patch
validation was not possible. Agent wall time excludes external validation.
The linked files are the unmodified `solution.json` outputs. Failed API calls
can have zero recorded tokens because the provider returned no usage record.

| Model | Task | Pass | Iterations | Requests | Input tokens | Output tokens | Wall time | Trace |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen 3.8-27B | SK | Yes | 12 | 12 | 35,232 | 930 | 245.66 s | [JSON](benchmark_traces/runs/qwen-qwen3.8-27b/scikit-learn__scikit-learn-13439/solution.json) |
| Qwen 3.8-27B | S1 | Yes | 4 | 4 | 7,694 | 191 | 57.25 s | [JSON](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-13480/solution.json) |
| Qwen 3.8-27B | S2 | Yes | 4 | 4 | 11,379 | 161 | 187.41 s | [JSON](benchmark_traces/runs/qwen-qwen3.8-27b/sympy__sympy-18189/solution.json) |
| GPT-OSS 20B | SK | No patch | 1 | 1 | 0 | 0 | 2.73 s | [JSON](benchmark_traces/runs/gpt-oss-20b/scikit-learn__scikit-learn-13439/solution.json) |
| GPT-OSS 20B | S1 | No patch | 1 | 1 | 0 | 0 | 2.50 s | [JSON](benchmark_traces/runs/gpt-oss-20b/sympy__sympy-13480/solution.json) |
| GPT-OSS 20B | S2 | No patch | 1 | 1 | 0 | 0 | 2.46 s | [JSON](benchmark_traces/runs/gpt-oss-20b/sympy__sympy-18189/solution.json) |
| GPT-OSS 120B | SK | No patch | 25 | 26 | 76,495 | 10,000 | 530.37 s | [JSON](benchmark_traces/runs/gpt-oss-120b/scikit-learn__scikit-learn-13439/solution.json) |
| GPT-OSS 120B | S1 | No patch | 3 | 3 | 3,029 | 173 | 4.65 s | [JSON](benchmark_traces/runs/gpt-oss-120b/sympy__sympy-13480/solution.json) |
| GPT-OSS 120B | S2 | No patch | 1 | 1 | 0 | 0 | 2.20 s | [JSON](benchmark_traces/runs/gpt-oss-120b/sympy__sympy-18189/solution.json) |

Qwen submitted three patches, and all three passed the external validator
(`Overall: PASSED`, `Metrics: VALID`). It averaged 6.67 iterations and 163.44
seconds per task. GPT-OSS 20B failed on the first request of every task with
HTTP 400, `Tool choice is none, but model called a tool`. GPT-OSS 120B hit
that same error on both SymPy tasks. On SK it obtained responses but reached
the 10,000-output-token budget without submitting a patch. These outcomes
rule out those two models **with this provider and prompt/agent protocol**;
they do not establish that the underlying models cannot solve the tasks.

## Provider reliability

`total_requests` includes retries. "Usable responses" counts steps with a
provider response and recorded response time. The response-time mean is
weighted by those steps and includes retry waiting; failed HTTP requests have
no measured response time in `solution.json`. "Usable / attempted" is an
observed compatibility-and-service rate, **not** provider uptime.

| Model | Usable / attempted | Retries | Terminal HTTP 400 | Mean response time | Observed availability |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen 3.8-27B | 20 / 20 | 0 | 0 | 13.83 s | 100% |
| GPT-OSS 20B | 0 / 3 | 0 | 3 | Not measurable | 0% usable |
| GPT-OSS 120B | 27 / 30 | 1 | 2 | 19.71 s | 90% usable |

GPT-OSS 120B's extra attempt was an HTTP 429 rate-limit retry on SK. Its two
terminal errors and all three GPT-OSS 20B errors were HTTP 400 protocol
rejections, not outages. None of the nine runs establishes long-term provider
availability or a statistically reliable latency distribution.

## Intermediary exploration metrics

Steps are one-based. "First read" includes a successful `read_file` or a
successful `run_command` that displayed the eventual patch file. "First edit"
requires `EDIT OK`, not an attempted call. "Tests pass" requires an actual
passing test summary with no failures; the `run_tests()` wrapper's own
`SUCCESS` flag alone is insufficient. The gap is final-answer step minus
first passing-test step. These metrics are meaningful for the Qwen baseline
and its ablation; the GPT-OSS runs have no final patch to inspect.

| Prompt | Task | First read | First edit | Tests pass | Final answer | Pass-to-submit gap |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Focused | SK | 1 | 10 | 11 | 12 | 1 |
| Focused | S1 | 1 | 2 | 3 | 4 | 1 |
| Focused | S2 | 1 | 2 | 3 | 4 | 1 |
| Generic | SK | None | None | None | None | N/A |
| Generic | S1 | 1 | 12 | 15 | 19 | 4 |
| Generic | S2 | 1 | 2 | 9 | 10 | 1 |

The focused prompt yielded the expected read, edit, test, submit sequence on
all three tasks. SK still needed two failed syntax attempts before its first
successful edit. Under the generic prompt, S1 spent eight iterations on
malformed `edit_file` calls before editing at step 12. Generic SK never made a
successful read or edit; its `run_tests()` observations at steps 14 and 22
reported **one failed test** and 40 passed, so they are not marked as passing.
There is no pre-edit test baseline in these traces, so "first decrease in test
failures" is not claimed.

## Prompt ablation

The ablation reused Qwen, the same three task JSONs, code revision, endpoint,
tool implementation, limits, and external validator. A temporary CLI copy
changed only `build_system_prompt()`. The generic condition replaced the
focused task strategy with: "Solve the issue using the available Python
tools. Return exactly one Python code block followed by `<end_code>`. Print
tool results. Test the change, then submit the unified diff with
`final_answer(get_patch())`." Both prompts included the same dynamically
generated tool manual. The full actual prompts are preserved in each trace's
`system_prompt` field.

| Task | Focused verdict / iterations / time | Generic verdict / iterations / time | Generic trace |
| --- | --- | --- | --- |
| SK | Pass / 12 / 245.66 s | No patch / 30 / 449.63 s | [JSON](benchmark_traces/ablation/generic/scikit-learn__scikit-learn-13439/solution.json) |
| S1 | Pass / 4 / 57.25 s | Pass / 19 / 321.96 s | [JSON](benchmark_traces/ablation/generic/sympy__sympy-13480/solution.json) |
| S2 | Pass / 4 / 187.41 s | Pass / 10 / 291.33 s | [JSON](benchmark_traces/ablation/generic/sympy__sympy-18189/solution.json) |

The focused condition passed 3/3 versus 2/3 for the generic condition. Its
mean was 6.67 versus 19.67 iterations and 163.44 versus 354.31 seconds per
task. Total input/output tokens were 54,305/1,282 focused versus
120,483/3,605 generic. Both submitted generic patches passed the external
validator. This single, sequential run per task is directional evidence, not
a statistically controlled estimate of prompt effect: sampling variance,
provider load, and run order remain possible confounders.

## Conclusion and remaining work

For the currently tested provider setup, Qwen is the only defensible default:
it solved all three tasks, submitted externally valid patches, and completed
without API errors. The GPT-OSS runs exposed a tool-choice incompatibility;
investigate the provider/client protocol before treating them as a fair
head-to-head coding comparison. The ablation suggests that the focused prompt
reduces wasted tool calls and speeds submission on this small cohort.

The required **five-model** comparison is still missing two models, deferred
until access to suitable model endpoints is available. Run those two on the
same three saved task JSONs, validate submitted patches, and add their raw
`solution.json` traces and reliability rows. Then revisit the model choice.
The older 2026-09-14 [Qwen pilot](benchmark_traces/qwen-qwen3.8-27b/) used a
different code/prompt revision and a 10-iteration setting; it is retained as
historical evidence and is **not pooled** with these new results.
