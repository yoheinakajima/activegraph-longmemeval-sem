---
name: agentic concept-graph retrieval experiment
description: Outcome of the entity-graph + agentic retrieval experiment on the activegraph-memory pack vs the flat baseline; why flat is still the default.
---

# Agentic concept-graph retrieval vs flat baseline

Two flag-gated layers were added to the `activegraph-memory` pack:
1. concept graph — entities/topics extracted per memory, deduped into
   `memory_concept` nodes, linked via `about_entity` (`enable_concept_graph`).
2. agentic retrieval — concept vector-search → linked facts → confidence
   self-assessment → fallback to direct fact search → iterate
   (`retrieval_strategy="agentic"`, `DefaultAgenticController`).

Both default OFF (flat behavior). The agentic path implies concept-graph on.

## Result (50-q LongMemEval-S, llm extraction, sonnet reader)
- **Agentic 0.90 vs flat baseline 0.94 — agentic did NOT beat baseline.**
- Agentic FIXED: single-session-preference (0.67→1.0), +1 single-session-user,
  +1 temporal. REGRESSED: 2 temporal, 1 single-session-user, 1 multi-session,
  1 knowledge-update. Net −2 questions.

**Why:** concept-mediated retrieval helps narrow single-fact preference questions
but injects recall noise on multi-hop / temporal / knowledge-update questions
where the flat keyword+vector blend already lands the gold turns precisely.

**How to apply:** The overfit-heuristic removal was GATED on agentic beating
baseline, so it was NOT done — the heuristics stay. Flat stays the default.
Before revisiting: the agentic loop needs better fact ranking / iteration
stopping on multi-hop questions, not just concept recall, to clear 0.94. The
layers are A/B-comparable behind flags, so future tuning can re-run the same
50-q LongMemEval-S slice (`--retrieval-strategy agentic`) against the flat
baseline run.

**Controller boundary is untrusted:** `retrieve_memories._agentic_retrieve`
filters controller output through `RetrievalTools.is_fact` — a buggy/LLM
controller returning concept ids, excluded ids, or non-existent ids would
otherwise cause `PackSchemaViolation` on `retrieved_for`/`used_in_answer` and
leak concept nodes into results. Any new controller path must keep that filter.
