# README Requirements

The README should be complete and developer-facing.

---

## Required Sections (16 total)

1. One-sentence description
2. Why this exists
3. ActiveGraph-native thesis
4. Installation
5. Minimal usage
6. Pack loading
7. Memory lifecycle diagram
8. Object types
9. Relation types
10. Behavior list
11. Settings
12. Examples
13. Development setup
14. Test instructions
15. Roadmap
16. Optional inspiration section (see below)

---

## Suggested Opening

```markdown
# ActiveGraph Memory
An ActiveGraph-native memory lifecycle pack.
Most agent memory systems treat memory as retrieval. ActiveGraph Memory treats memory as state evolution: what was observed, what was extracted, what changed, what conflicted, what was retrieved, and what was used.
```

Do not claim benchmark performance until benchmarks exist. Do not overstate capability. Use clear examples.

---

## Memory Lifecycle Diagram

Include in README or `docs/memory_lifecycle.md`:

```
memory_observation
  ↓ extract_candidate_memories
memory_claim / episodic_memory / procedural_memory
  ↓ derived_from / supports
evidence-linked memory graph
  ↓ resolve_temporal_refs / attach_numeric_scope
temporal_ref / quantity_claim
  ↓ detect_contradictions
contradicts / supersedes relations
  ↓ consolidate_memories
consolidated memory state
  ↓ memory_query
retrieval_plan
  ↓ retrieve_memories
memory_retrieval_result
  ↓ fallback_retrieve if needed
expanded retrieval result
  ↓ answer_with_evidence
memory_answer
  ↓ evaluate_memory_usage
memory_evaluation
```

---

## Optional Inspiration Section

If included, make it short, factual, and positive.

Suggested wording:

```markdown
## Inspiration
ActiveGraph Memory is inspired by the broader shift from simple vector recall toward memory-first agent systems: semantic, episodic, and procedural memory; disciplined retrieval; temporal grounding; numeric attribution; fallback retrieval; and background consolidation.
Recent open-source projects such as Quarq Agent explore related ideas. ActiveGraph Memory takes a graph-native approach, representing memory as event-sourced state evolution with explicit lineage, relations, and behavior-driven updates.
```

This section is optional. The repo should stand on its own as an ActiveGraph-native memory pack.
