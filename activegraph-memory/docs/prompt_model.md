# prompt model

Eight prompts ship under `activegraph_memory/prompts/`:

- `extract_candidate_memories.md`
- `plan_memory_retrieval.md`
- `retrieve_memories.md`
- `answer_with_evidence.md`
- `detect_contradictions.md`
- `consolidate_memories.md`
- `resolve_temporal_refs.md`
- `attach_numeric_scope.md`
- `evaluate_memory_usage.md`

Each prompt declares its expected input variables and the JSON shape
of the expected output, so it can be plugged into ActiveGraph's
`@llm_behavior` decorator without further translation.

## Why are prompts here when the behaviors are deterministic?

The behaviors shipped in version `0.1.0` are deterministic so the
pack runs offline in CI with no API key. The prompts represent the
intent of each behavior in natural language, so the next maintainer
can swap any behavior from `@behavior` to `@llm_behavior` by:

1. Loading the prompt via the pack manifest.
2. Wrapping the body of the behavior in an `llm` call that uses the
   loaded prompt as the system message.
3. Updating the behavior decorator to `@llm_behavior(...)`.

The deterministic implementation is the floor, not the ceiling.
