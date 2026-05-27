# evaluation

`evaluate_memory_usage` runs after every `memory_answer` and produces
a `memory_evaluation` linked back to the answer via either
`validated_by` (positive) or `invalidated_by` (negative).

## Outcomes

The `outcome` field uses one of:

- `helpful` — the answer used at least one memory and the user did
  not contradict it.
- `unhelpful` — the answer ran but did not actually use any memory.
- `incorrect` — the answer disagreed with a known evaluation source
  (benchmark or user correction).
- `unsupported` — the answer cited a memory but the memory itself
  was missing required data (e.g. numeric_value).
- `partially_helpful` — partial coverage; some required_data was
  missing.
- `unknown` — the behavior could not decide (default).

The deterministic implementation picks `helpful` /
`partially_helpful` / `unhelpful` / `unknown` based on the retrieval
result's `confidence` and `missing_data`. `incorrect` and
`unsupported` arrive through future benchmark and user-correction
events; the behavior dispatches on `event.type` rather than on a
fixed schedule.

## Why not auto-mutate memories

A failing answer is a signal, not a verdict on the underlying memory.
The same memory might have been retrieved for the wrong query, or
the retrieval ranking might have been off. The pack writes an
evaluation and stops; downstream tooling (a periodic batch job, an
operator dashboard) decides whether to archive, supersede, or
revisit the source memory. This is what
`benchmark_plan.md` hooks into.

## Benchmark and correction events

`memory_evaluation` is also created from non-answer events:

- `benchmark.answered` — emitted by a benchmark harness that knows
  the ground-truth answer.
- `user.corrected` — emitted by the host application when the user
  pushes back on a previously emitted answer.

Both flow through the same `evaluate_memory_usage` behavior, so the
audit trail is uniform.
