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

## Enhancement experiment: multi-strategy + rerank/trim (50-q LongMemEval-S)

Tried to push agentic past 0.94 by (1) matching question entities to concept
names, (2) direct fact fallback, (3) trying multiple strategies + merging,
(4) reranking + trimming context to fix "too much info". Sweep of configs:

| config (agentic)                                  | overall | turn_rec | turn_hit |
|---------------------------------------------------|---------|----------|----------|
| flat baseline                                     | 0.94    | 0.933    | 0.920    |
| prior agentic / all extras OFF (= shipped default)| 0.90    | 0.938    | 0.880    |
| fixed trim=15                                     | 0.80    | 0.830    | 0.720    |
| adaptive trim keep_ratio=0.5                      | 0.76    | 0.800    | 0.680    |
| no-trim + question-entity match + reranking       | 0.84    | 0.948    | 0.900    |
| reranking only (entity-match off, trim off)       | 0.88    | 0.938    | 0.880    |

**The decisive learning: recall is NOT the bottleneck — precision is.** Every
agentic variant matches or exceeds flat's turn recall; the no-trim+entity-match
config hit the *highest recall of all runs* (0.948 > flat 0.933) yet scored only
0.84. The right facts are almost always retrieved; the reader still answers
wrong because of distractors.

Three concrete failure modes, each from a different "improvement":
- **Trimming with the offline scorer backfires.** Cosine+keyword mis-ranks, so
  any trim (fixed OR adaptive) pushes true facts out → turn recall collapses
  (0.938→0.80), multi-hop dies (multi-session 0.92→0.54). You cannot fix a
  precision problem with a weak ranker.
- **More retrieval strategies = more distractors.** Question-entity match adds
  facts that share a surface entity but aren't the answer; with a strong reader
  this *lowers* accuracy. The marginal fact a new strategy adds is, by
  construction, one the simpler strategy ranked lower — i.e. likelier a
  distractor.
- **Reranking reorders into the reader's position bias.** Even with no trim and
  no entity-match, entity-overlap/recency reranking alone made the reader
  hedge/abstain on preference questions despite having the facts
  (single-session-preference 1.0→0.33): the reader named the gold preference,
  then said "I don't have enough information" instead of committing.

**Why flat (0.94) still wins:** its targeted heuristics (supersession cues,
query_mode, owner/property guessing) do *precision* work — suppressing the
specific distractors (stale knowledge-updates, same-entity siblings) that a
generic recall-maximizing retriever cannot. This is why removing those
heuristics stays GATED and was never done; they are load-bearing.

**Shipped state:** all four capabilities are built and flag-gated but **OFF by
default** (`agentic_match_question_entities=False`,
`agentic_entity_overlap_weight=0.0`, `agentic_rerank_keep_ratio=0.0`,
`agentic_rerank_limit=40` as a cap; direct fallback stays on). Default agentic
path = 0.90 (confirmed). Flat stays the product default.

**If revisiting:** the lever to beat 0.94 is precision, not recall or
reordering. Promising directions not yet tried — a *learned/stronger* reranker
(cross-encoder) good enough to trim safely; distractor-suppression at ingest
(supersession/entity-disambiguation written into the graph) rather than at read
time; or telling the reader to commit rather than hedge. Adding more retrieval
breadth is a dead end here.
