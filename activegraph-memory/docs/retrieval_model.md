# retrieval model

Retrieval is a two-stage pipeline driven by two behaviors:
`plan_memory_retrieval` and `retrieve_memories`.

## Plan

A `memory_query` triggers `plan_memory_retrieval`, which produces a
`retrieval_plan` with:

- `keywords` — normalized tokens extracted from the question.
- `vector_queries` — optional embedding queries (empty when the
  vector backend is disabled via `enable_vector_retrieval=False`).
- `memory_types` — which of `semantic` / `episodic` / `procedural` to
  search (defaults to all three).
- `mode` — `standard` or `deep`. `deep` widens type scope and
  includes `superseded` memories.
- `required_data` — list of additional signals the caller needs to
  consider the result satisfactory (`numeric_value`, `temporal_value`,
  etc.). Used downstream by `fallback_retrieve` and by the answer
  behavior when deciding `missing_data`.

## Retrieve

`retrieve_memories` scans `ctx.view.objects()`, ranks hits, and writes
a `memory_retrieval_result`. The ranker:

1. Filters by memory type (per the plan).
2. Filters out `deleted`, `archived`, and (by default) `superseded`
   statuses.
3. Runs the keyword search tool against `content`.
4. Optionally runs the vector search tool with a lower blend weight
   (configurable via `vector_blend_weight`).
5. Sorts by composite score descending, ties broken by id ascending
   for determinism.
6. Truncates to `retrieval_limit`.

Each hit gets two `retrieved_for` edges: one to the
`memory_retrieval_result`, one to the original `memory_query`.

## Fallback

If `retrieval_plan.required_data` contained `numeric_value` or
`temporal_value` and the corresponding edge does not show up on any
hit, `fallback_retrieve` fires. It expands the keyword set with
domain-specific seeds (`amount`, `number`, `target`, `size`,
`reserves`, `date`, `when`, `year`) and re-runs the keyword search
against the full memory store. The combined hit set replaces the
original result, with `metadata.is_fallback=True` recorded.

## Answer

`answer_with_evidence` reads the retrieval result, assembles the
answer from the `content` fields of the hits, applies procedural
memories as style constraints, and records `used_in_answer` edges.
If the retrieval was empty, the answer says so explicitly and does
not invent memories.
