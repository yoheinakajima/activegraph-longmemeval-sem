# roadmap

## v0.1 — shipped

- Fifteen object types, twelve relation types, twenty registered
  behaviors covering extraction, contradiction, consolidation,
  temporal scope, numeric scope, retrieval planning, retrieval,
  fallback retrieval, answering, evaluation, archival, and forgetting.
- Deterministic implementation: tests pass offline with no API key.
- Eight prompts shipped so any behavior can be swapped to
  `@llm_behavior` without redesigning the cascade.
- Settings schema, fixtures, examples, full docs.
- Two-graph policy comparison.

## v0.2 — soon

- Entity model. `about_entity` and `same_entity_as` relations need a
  first-class `entity` object type. We deliberately did not invent
  one inside the memory pack so a host application can plug in an
  existing entity store.
- Multi-type `where=` filters. Once ActiveGraph supports
  `where={"object.type": {"in": [...]}}`, the per-type behavior
  duplicates collapse from twenty registered behaviors to eleven.
- First-class fork/diff API. When ActiveGraph supports forking a
  graph and diffing two forks, `examples/fork_memory_policy.py`
  collapses from two graphs to one fork.

## v0.3 — later

- Optional LLM mode. Each behavior gets a `@llm_behavior` variant
  loaded from the existing prompt files. Settings flag selects
  deterministic vs LLM per behavior.
- Optional vector backend. `OptionalOpenAIEmbeddingProvider` swaps
  in for the deterministic embedding provider when an API key is
  configured. Vector queries land in the `vector_queries` slot on
  the retrieval plan.
- Benchmark harness (`benchmark_plan.md`).

## Out of scope

- A chat UI. Hosts plug the pack into their own UI.
- A storage layer. ActiveGraph already provides the store.
- A scheduler. ActiveGraph already provides the runtime.
