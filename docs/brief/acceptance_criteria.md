# Full Acceptance Criteria

The repo is acceptable when **all** of the following are true.

---

## Packaging

- [ ] `pip install -e .` works
- [ ] Package imports as `activegraph_memory`
- [ ] Package exports `pack`
- [ ] Pack is discoverable through ActiveGraph entry points

---

## ActiveGraph Integration

- [ ] Pack loads in ActiveGraph runtime
- [ ] Object types register
- [ ] Relation types register
- [ ] Behaviors register
- [ ] Settings schema works
- [ ] Prompts load
- [ ] Tools load if implemented

---

## Memory Lifecycle

- [ ] `memory_observation` can create memory objects
- [ ] Memory objects link to observations
- [ ] `memory_query` creates `retrieval_plan`
- [ ] `retrieval_plan` creates `memory_retrieval_result`
- [ ] Retrieved memories link to result
- [ ] `memory_retrieval_result` creates `memory_answer`
- [ ] Used memories link to answer

---

## Advanced Memory

- [ ] Contradictions can be detected
- [ ] Supersession can be represented
- [ ] Temporal references can be extracted/resolved
- [ ] Numeric claims can be scoped
- [ ] Fallback retrieval can run
- [ ] Memories can be consolidated
- [ ] Memories can be archived/forgotten
- [ ] Memory usage can be evaluated

---

## Fork/Diff

- [ ] Different memory policies can be compared over the same or similar event history
- [ ] Example demonstrates why event-sourced memory matters

---

## Tests

- [ ] Tests pass offline
- [ ] Tests require no API keys
- [ ] Tests require no network
- [ ] Tests cover all major object types
- [ ] Tests cover all major relation types
- [ ] Tests cover all major behaviors

---

## Docs

- [ ] README is clear
- [ ] Architecture docs exist
- [ ] Memory lifecycle docs exist
- [ ] Object/relation/behavior docs exist
- [ ] Examples are documented
- [ ] Roadmap is documented
- [ ] Benchmark plan is documented

---

## Quality

- [ ] Simple readable Python
- [ ] Typed models
- [ ] Small modules
- [ ] Deterministic tests
- [ ] No hidden side effects
- [ ] No unsupported performance claims
