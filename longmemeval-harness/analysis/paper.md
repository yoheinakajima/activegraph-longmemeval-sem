# From Recall to Reasoning: A 500-Question Evaluation of LLM Memory Extraction on LongMemEval-S

*Draft — May 2026. Generated from the `longmemeval-harness` run artifacts (`runs/full-s-sonnet`, `runs/task18-flat-500`, `runs/task18-agentic-500`). All numbers in this draft are reproducible from `analysis/significance.py` and `analysis/failures.py`.*

## Abstract

We evaluate the ActiveGraph **semantic-memory pack** on the full cleaned LongMemEval-S
benchmark (n = 500), the system the original ActiveGraph LongMemEval study explicitly
deferred ("this run does not answer it"). We measure three configurations end-to-end
with a frozen Claude Sonnet 4.5 reader and a `gpt-4o-2024-08-06` judge: (i) a
deterministic-extraction baseline, (ii) LLM memory extraction with flat retrieval, and
(iii) LLM extraction with agentic retrieval. LLM extraction lifts overall accuracy from
**0.606 to 0.834** (flat) — a large, highly significant gain (paired McNemar, net +114
of 500, p < 1e-15). Agentic retrieval does **not** beat flat at scale (0.840 vs 0.834,
net +3, p = 0.72); the earlier 50-question finding that "flat > agentic" was sampling
noise. Most importantly, the bottleneck **flips**: the deterministic system is
retrieval-limited (36% of answerable questions fail because the evidence is never
retrieved), whereas under LLM extraction ~72% of remaining errors occur *with the gold
evidence present in context* — i.e., they are reader/reasoning failures, not retrieval
failures. We characterize four reasoning failure modes (temporal arithmetic,
cross-session aggregation, knowledge supersession, preference grounding) and one
systematic extraction regression: LLM extraction discards assistant-authored facts,
which significantly degrades the `single-session-assistant` question type (0.964 →
0.750, p = 0.0018). We argue the next lever is reader-side reasoning and
assistant-content retention, not retrieval breadth.

## 1. Background

LongMemEval-S is a long-term-memory QA benchmark: each instance is a multi-session chat
history (hundreds of turns, including distractor sessions) plus a question whose answer
depends on one or more "gold" evidence turns. The cleaned `s` split has 500 instances
spanning six question types.

The original ActiveGraph LongMemEval-S analysis measured the *deterministic substrate*
(a turn-node graph with no LLM at ingest, retrieval by dense or lexical similarity) and
reported 85.6% QA accuracy at a ~2.5k-token context budget. That study explicitly
deferred the semantic-memory question: *"That would be the real ActiveGraph
semantic-memory test. This run does not answer it."* This paper evaluates exactly that
deferred system — the `activegraph-memory` semantic pack, which performs LLM-based
memory extraction, consolidation, contradiction detection, temporal resolution, and a
keyword+vector retrieval blend — and is therefore a follow-up experiment, not a
reproduction of the 85.6% substrate number.

## 2. Experimental setup

**Harness.** Each question is run end-to-end through the pack: ingest the full session
history into a fresh memory store, retrieve for the question, assemble reader context,
generate an answer with the reader model, and score it with an LLM judge. Per-question
records (retrieval, context, hypothesis, judgment, latencies, token counts) are
persisted to a SQLite store, enabling the paired analysis below.

**Fixed across all runs.**
- Reader: `claude-sonnet-4-5` (resolved `claude-sonnet-4-5-20250929`), temperature 0,
  tool-free, `max_tokens = 1024`, with the byte-identical reader prompt template used by
  the original study (a deliberately frozen control for substrate↔pack comparability).
- Judge: `gpt-4o-2024-08-06`, temperature 0.
- Retrieval limit 40; keyword + vector retrieval enabled; no reranking; no HyDE / query
  expansion.
- Dataset: cleaned LongMemEval-S, 500 instances, sha256 `d6f21ea9…`, seed 42.

**The two manipulated variables.**
1. *Extraction*: `deterministic` (one memory per observation, no LLM at ingest) vs `llm`
   (a cached `gpt-4o-mini` extractor, temperature 0, JSON output, confidence threshold
   0.65).
2. *Retrieval strategy*: `flat` vs `agentic` (concept-mediated retrieval with a
   confidence-gated iterative loop), evaluated only under LLM extraction.

This yields three runs: `full-s-sonnet` (deterministic + flat), `task18-flat-500`
(llm + flat), `task18-agentic-500` (llm + agentic). All three completed 500/500 with
zero harness errors and zero pack errors.

**Caching / reproducibility.** Extraction and embedding calls are cached to disk keyed
by content hash, so re-runs are deterministic and free; the s split heavily reuses
distractor sessions, so cache hit rates are high.

**Parity caveats.** (a) The deterministic baseline was judged with
`gpt-4o-2024-11-20`; the two LLM-extraction runs used the parity snapshot
`gpt-4o-2024-08-06`. The original study estimates judge-snapshot contribution at ~±1
point, well below the effect sizes we report for extraction. (b) The pack uses its own
keyword+vector retrieval rather than the study's dense embeddings — but that retrieval
*is* the system under test, not a tunable knob. (c) Mean reader context is ~7.5–8k
tokens, not the substrate study's ~2.5k budget; these are different systems and the
budgets are not comparable.

## 3. Results

### 3.1 Overall accuracy

| Configuration | Extraction | Retrieval | Accuracy (n=500) | Wilson 95% CI |
|---|---|---|---|---|
| `full-s-sonnet` | deterministic | flat | 0.606 | [0.563, 0.648] |
| `task18-flat-500` | **llm** | flat | **0.834** | [0.799, 0.864] |
| `task18-agentic-500` | **llm** | agentic | **0.840** | [0.805, 0.870] |

LLM extraction is the dominant lever: +0.228 absolute over the deterministic baseline.
The two LLM-extraction configurations are statistically indistinguishable.

### 3.2 Paired significance (McNemar)

Because all runs share the same 500 questions, we use the paired McNemar test on
per-question correct/incorrect outcomes. `b` = first-config-only correct, `c` =
second-config-only correct; `net` = `c − b`; `p_exact` is the two-sided exact binomial
on discordant pairs.

| Comparison | b | c | net | p_exact | verdict |
|---|---|---|---|---|---|
| deterministic vs **flat-llm** | 27 | 141 | **+114** | < 1e-15 | flat-llm far better |
| deterministic vs **agentic-llm** | 31 | 148 | **+117** | < 1e-15 | agentic-llm far better |
| **flat-llm vs agentic-llm** | 14 | 17 | +3 | **0.72** | **no difference** |

The deterministic→LLM gain is significant for *every* question type. The
flat-vs-agentic difference is not significant overall, and no per-type delta reaches
significance (closest: temporal-reasoning +4, p = 0.34). **The 50-question result that
"flat 0.94 > agentic 0.90" does not replicate at scale — it was sampling noise.**
Agentic does use slightly less reader context (mean 7,651 vs 8,042 tokens) for equal
accuracy, so it is plausibly a marginal *precision* improvement, but the accuracy
difference itself is a wash and does not justify the extra retrieval-loop LLM calls.

### 3.3 Per-question-type breakdown

| Type (n) | deterministic | flat-llm | agentic-llm |
|---|---|---|---|
| knowledge-update (78) | 0.756 | 0.846 | 0.808 |
| multi-session (133) | 0.346 | 0.827 | 0.827 |
| single-session-assistant (56) | **0.964** | **0.750** | **0.750** |
| single-session-preference (30) | 0.367 | 0.867 | 0.933 |
| single-session-user (70) | 0.829 | 0.943 | 0.943 |
| temporal-reasoning (133) | 0.564 | 0.805 | 0.835 |

LLM extraction massively improves the cross-session and synthesis types
(multi-session 0.346→0.827, preference 0.367→0.867/0.933, temporal 0.564→0.805/0.835)
but **regresses `single-session-assistant`** from 0.964 to 0.750. This regression is
statistically significant (deterministic vs flat: b=13, c=1, p = 0.0018) and is
mechanistically explained in §4.1.

### 3.4 The bottleneck flips from recall to reasoning

We decompose each answerable question (n = 470; the 30 abstention questions have no
gold turns) by whether retrieval surfaced all gold turns (`turn_hit = 1`) and whether
the final answer was correct.

| Run | hit-rate | acc \| hit=1 | acc \| hit=0 | reasoning-error share | retrieval-miss share |
|---|---|---|---|---|---|
| deterministic | 0.502 | 0.907 | 0.274 | 0.047 | **0.362** |
| flat-llm | 0.906 | 0.864 | 0.477 | **0.123** | 0.049 |
| agentic-llm | 0.887 | 0.880 | 0.472 | **0.106** | 0.060 |

- *reasoning-error share* = fraction of answerable questions where the gold evidence
  **was** retrieved yet the answer was wrong (`turn_hit=1 & wrong`).
- *retrieval-miss share* = fraction where the evidence was **not** retrieved
  (`turn_hit=0 & wrong`).

The deterministic system is **retrieval-limited**: it retrieves the gold turn only half
the time (hit-rate 0.502), and 36% of all answerable questions fail for lack of
evidence; when evidence *is* present it answers correctly 91% of the time. LLM
extraction nearly eliminates the retrieval miss (hit-rate jumps to 0.906; retrieval-miss
share falls to ~5%), and the bottleneck **inverts**: for flat-llm, 58 of 81 answerable
errors (**72%**) occur with the gold evidence already in context. Retrieval is no longer
the binding constraint — the reader is.

A subtle point: `acc | hit=1` is *lower* for LLM extraction (0.864) than for
deterministic (0.907). This is a selection effect, not a reader regression — the
deterministic system only surfaces evidence for the easy half of questions, so its
"evidence-present" subset is easier; LLM extraction surfaces evidence for the hard
questions too, and those are harder to reason over even with the evidence in hand.

## 4. Failure analysis

### 4.1 The assistant-extraction regression (systematic, significant)

Every one of the 14 `single-session-assistant` failures under flat-llm has
`turn_hit = 0`: the gold turn was *never retrieved*. Turn-level hit-rate for this type
drops from 0.911 (deterministic) to 0.696 (both LLM runs), and accuracy tracks it
almost exactly (0.750). The cause is structural: `single-session-assistant` questions
ask what the **assistant** previously said ("what move did you make after 27. Kg2
Bd5+?", "how many mummies will the party face?", "what was the 27th parameter on that
list?"). The LLM extractor is designed to distill durable facts *about the user* and
therefore drops assistant-authored content, so those turns never become memories. The
reader then correctly abstains ("I don't have any record of providing that…") because
the fact genuinely is not in the store. The deterministic extractor, which keeps one
memory per observation regardless of speaker, retains them.

This is the clearest actionable defect surfaced by the study: the gain on the other five
types is large enough to absorb it, but recovering assistant-authored facts at ingest
would recover most of the lost 21 points on this type with no downside elsewhere.

### 4.2 Reasoning-on-evidence failures (the new majority)

The 58 flat-llm errors with evidence present cluster into four modes:

- **Temporal arithmetic (22 cases).** The dates are in context but the reader
  miscomputes the interval. E.g. *"How many weeks had passed since I recovered from the
  flu when I went on my 10th jog?"* — both dates present (Jan 19 → Apr 10), reader
  answers "12 weeks", gold is 15. Another reads two timestamps on the same record as
  start=end and concludes a 21-day read took "0 days."
- **Cross-session aggregation (16 cases).** Counting or summing across sessions fails.
  *"How many art events did I attend in the past month?"* — reader lists 3, gold is 4;
  *"page count of the two novels I finished in January and March"* — reader cannot bind
  the months and abstains.
- **Knowledge supersession (12 cases).** Both the old and the updated fact are
  retrieved, and the reader picks the stale one. *"Where do I currently keep my old
  sneakers?"* — reader answers "under your bed" (the superseded location) instead of the
  current "shoe rack"; *"most recently purchased lens"* — reader names the older 50mm
  prime over the more recent 70-200mm zoom.
- **Preference grounding (4 cases).** The implicit preference is in context but the
  reader gives generic advice or claims no history. *"Any tips for my phone battery?"* —
  the user previously bought a power bank (in context), but the reader returns boilerplate
  battery tips instead of building on it.

These are reader-reasoning failures, not retrieval failures, and they are now the
dominant error class.

## 5. Discussion: the next lever

Three conclusions follow directly from the data:

1. **LLM extraction is the headline win and should stay on.** It is the only change that
   moves overall accuracy at scale, and it does so by ~23 points.
2. **Agentic retrieval is not worth enabling as a default.** It is statistically tied
   with flat retrieval; its only measurable edge is a small context-size reduction.
   Retrieval breadth and read-time reordering are exhausted levers on this benchmark.
3. **The remaining headroom is in the reader, plus one extraction fix.** With ~72% of
   errors occurring on evidence the system already retrieved, the highest-value work is
   (a) reader-side reasoning for temporal arithmetic, cross-session aggregation, and
   supersession/recency selection, and (b) retaining assistant-authored facts at ingest
   to recover the `single-session-assistant` regression. Neither is a retrieval problem.

Because the reader prompt is currently a frozen parity control, reader-side improvements
should be reported as an explicitly non-parity track (e.g. a reasoning-scaffold or
date-normalization prompt, or a self-correction pass), measured first on a 50-question
slice and confirmed on the full 500.

## 6. Limitations

- **Single reader / single judge.** All numbers are for one reader (Sonnet 4.5) and one
  judge snapshot; reader-side conclusions may not transfer to other readers.
- **Judge non-parity on the baseline.** The deterministic baseline used a different
  judge snapshot (`gpt-4o-2024-11-20`); estimated ≤1-point effect, immaterial to the
  extraction result but worth noting.
- **One extractor.** LLM extraction used `gpt-4o-mini`; a stronger extractor might both
  raise recall further and avoid the assistant-content drop.
- **S split only.** Results are for cleaned LongMemEval-S (500); the larger / oracle
  splits are untested here.
- **Turn-hit is a proxy.** The recall/reasoning decomposition relies on gold-turn
  matching as the definition of "evidence present"; a retrieved-but-unhelpful gold turn
  would be miscounted as evidence-present.

## 7. Conclusion

On the full LongMemEval-S benchmark, LLM-based memory extraction lifts the ActiveGraph
semantic pack from 0.606 to 0.834 and, in doing so, converts the task from a retrieval
problem into a reasoning problem: most remaining errors happen with the right evidence
already in front of the reader. Agentic retrieval adds nothing at scale. The path
forward is reader-side reasoning (temporal, aggregation, supersession, preference) and a
targeted ingest fix to stop discarding assistant-authored facts.

## Appendix A: Reproduction

All figures are regenerated from the run stores under `runs/`:

```
cd longmemeval-harness
../.pythonlibs/bin/python -m analysis.significance   # tables in §3.1–3.4
../.pythonlibs/bin/python -m analysis.failures       # examples in §4
```

Run artifacts:
- `runs/full-s-sonnet/` — deterministic + flat (overall 0.606)
- `runs/task18-flat-500/` — llm + flat (overall 0.834)
- `runs/task18-agentic-500/` — llm + agentic (overall 0.840)

Each `store.sqlite` holds one row per question with the retrieval result, assembled
context, reader hypothesis, gold answer, judge decision, turn/session recall and hit,
token counts, and latencies.
