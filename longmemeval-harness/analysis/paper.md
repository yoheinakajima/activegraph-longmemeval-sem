# From Recall to Reasoning: A 500-Question Evaluation of LLM Memory Extraction on LongMemEval-S

*Draft — May 2026. Generated from the `longmemeval-harness` run artifacts (`runs/full-s-sonnet`, `runs/task18-flat-500`, `runs/task18-agentic-500`, `runs/task19-retain-500`). All numbers in this draft are reproducible from `analysis/significance.py` and `analysis/failures.py`.*

## Abstract

We evaluate the ActiveGraph **semantic-memory pack** on the full cleaned LongMemEval-S
benchmark (n = 500), the system the original ActiveGraph LongMemEval study explicitly
deferred ("this run does not answer it"). We measure four configurations end-to-end
with a frozen Claude Sonnet 4.5 reader and a `gpt-4o-2024-08-06` judge: (i) a
deterministic-extraction baseline, (ii) LLM memory extraction with flat retrieval,
(iii) LLM extraction with agentic retrieval, and (iv) LLM extraction with an ingest fix
that retains assistant-authored facts. LLM extraction lifts overall accuracy from
**0.606 to 0.834** (flat) — a large, highly significant gain (paired McNemar, net +114
of 500, p < 1e-15). Agentic retrieval does **not** beat flat at scale (0.840 vs 0.834,
net +3, p = 0.72); the earlier 50-question finding that "flat > agentic" was sampling
noise. Most importantly, the bottleneck **flips**: the deterministic system is
retrieval-limited (36% of answerable questions fail because the evidence is never
retrieved), whereas under LLM extraction ~72% of remaining errors occur *with the gold
evidence present in context* — i.e., they are reader/reasoning failures, not retrieval
failures. We then diagnose the one systematic regression LLM extraction introduces — it
discards assistant-authored facts, collapsing `single-session-assistant` from 0.964 to
0.750 — and show it is a pure *ingest* defect: flat and agentic retrieval fail on the
**identical 14 questions**, every one a retrieval miss. A targeted, flag-gated ingest fix
that retains assistant facts recovers **all 14** coverage failures and lifts the type to
**0.982** (net +13, p = 0.0010) with no significant regression on any other type,
raising overall accuracy to **0.848**. The single residual failure is a *fidelity* (not
coverage) case: a verbatim literary quote the extractor paraphrases away. Finally, we
report a **negative result** for the other predicted lever — a non-parity reasoning
scaffold on the reader regressed a 50-question slice (0.940 → 0.880; fixed 1, broke 4)
and was not shipped.
We conclude that on this benchmark the actionable headroom is at **ingest precision and
fidelity**, not at read-time scaffolding or retrieval breadth.

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

**The three manipulated variables.**
1. *Extraction*: `deterministic` (one memory per observation, no LLM at ingest) vs `llm`
   (a cached `gpt-4o-mini` extractor, temperature 0, JSON output, confidence threshold
   0.65).
2. *Retrieval strategy*: `flat` vs `agentic` (concept-mediated retrieval with a
   confidence-gated iterative loop), evaluated only under LLM extraction.
3. *Assistant retention*: whether the LLM extractor also distills facts from
   **assistant** turns (default in the fix; off in the original baselines).

This yields four runs: `full-s-sonnet` (deterministic + flat), `task18-flat-500`
(llm + flat, retention **off**), `task18-agentic-500` (llm + agentic, retention **off**),
and `task19-retain-500` (llm + flat + retention **on**). All four completed 500/500 with
zero harness errors and zero pack errors.

**Clean A/B for the retention fix.** The extractor is role-aware: the **user-turn**
extraction path is byte-identical between `task18-flat-500` and `task19-retain-500` (same
cache key and prompt → cache hits → identical user memories); only **assistant** turns
are additionally extracted when retention is on. So the retain-vs-flat comparison
isolates exactly one variable — assistant-fact retention — with everything else held
fixed, including the frozen parity reader and the `gpt-4o-2024-08-06` judge.

**Caching / reproducibility.** Extraction and embedding calls are cached to disk keyed
by content hash, so re-runs are deterministic and free; the s split heavily reuses
distractor sessions, so cache hit rates are high.

**Parity caveats.** (a) The deterministic baseline was judged with
`gpt-4o-2024-11-20`; the three LLM-extraction runs used the parity snapshot
`gpt-4o-2024-08-06`. The original study estimates judge-snapshot contribution at ~±1
point, well below the effect sizes we report for extraction. (b) The pack uses its own
keyword+vector retrieval rather than the study's dense embeddings — but that retrieval
*is* the system under test, not a tunable knob. (c) Mean reader context is ~8–9.5k
tokens, not the substrate study's ~2.5k budget; these are different systems and the
budgets are not comparable.

## 3. Results

### 3.1 Overall accuracy

| Configuration | Extraction | Retrieval | Retention | Accuracy (n=500) | Wilson 95% CI |
|---|---|---|---|---|---|
| `full-s-sonnet` | deterministic | flat | — | 0.606 | [0.563, 0.648] |
| `task18-flat-500` | **llm** | flat | off | 0.834 | [0.799, 0.864] |
| `task18-agentic-500` | **llm** | agentic | off | 0.840 | [0.805, 0.870] |
| `task19-retain-500` | **llm** | flat | **on** | **0.848** | [0.814, 0.877] |

LLM extraction is the dominant lever: +0.228 absolute over the deterministic baseline.
The two retrieval strategies are statistically indistinguishable. The assistant-retention
fix adds a further +0.014 overall on top of the flat baseline — small in aggregate
because the type it targets is only 56 of 500 questions, but, as §4 shows, it is a
targeted and side-effect-free gain.

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
| **flat-llm vs retain** (overall) | 29 | 36 | +7 | 0.457 | overall tie… |
| **flat-llm vs retain** (single-session-assistant only) | 1 | 14 | **+13** | **0.0010** | **retain far better** |

Two things matter here. First, the flat-vs-agentic difference is not significant overall,
and no per-type delta reaches significance — **the 50-question result that "flat 0.94 >
agentic 0.90" does not replicate at scale; it was sampling noise.** Second, the overall
flat-vs-retain delta (+7) is itself *not* significant — but that is the wrong unit of
analysis. The retention fix is a scalpel: restricted to the `single-session-assistant`
type it is net +13 of 56 (p = 0.0010), and **no other type shows a significant change**
(all per-type p ≥ 0.63; see §3.3). The aggregate looks modest only because a significant
+13 on one type is diluted across 500 questions.

A paired bootstrap (20k resamples over the 500 per-question outcomes) confirms the
distinction directly on the *delta*, not just each run's accuracy: the overall retain−flat
delta is **+0.014, 95% CI [−0.018, +0.046]** (straddles zero), whereas the
`single-session-assistant` delta is **+0.232, 95% CI [+0.107, +0.357]** (excludes zero).
The per-type gain also survives multiple-comparison correction across the six question
types: Holm-adjusted **p = 0.0059**, and the raw p = 0.0010 clears the Bonferroni
threshold 0.05/6 = 0.0083, while every other type has Holm-adjusted p = 1.0. So "no
collateral damage" is the corrected reading, not a descriptive hand-wave: exactly one
type moves.

### 3.3 Per-question-type breakdown

| Type (n) | deterministic | flat-llm | agentic-llm | retain | retain−flat (McNemar b/c, p) |
|---|---|---|---|---|---|
| knowledge-update (78) | 0.756 | 0.846 | 0.808 | 0.859 | +0.013 (3/4, p=1.0) |
| multi-session (133) | 0.346 | 0.827 | 0.827 | 0.805 | −0.023 (11/8, p=0.65) |
| single-session-assistant (56) | 0.964 | **0.750** | **0.750** | **0.982** | **+0.232 (1/14, p=0.0010)** |
| single-session-preference (30) | 0.367 | 0.867 | 0.933 | 0.833 | −0.033 (3/2, p=1.0) |
| single-session-user (70) | 0.829 | 0.943 | 0.943 | 0.943 | +0.000 (1/1) |
| temporal-reasoning (133) | 0.564 | 0.805 | 0.835 | 0.782 | −0.023 (10/7, p=0.63) |

LLM extraction massively improves the cross-session and synthesis types
(multi-session 0.346→0.827, preference 0.367→0.867/0.933, temporal 0.564→0.805/0.835)
but **regresses `single-session-assistant`** from 0.964 to 0.750 (§4.1). The retention
fix recovers that type to **0.982** — *above* even the deterministic substrate — while
every other type moves only within noise (the −0.02/−0.03 wobbles on multi-session,
temporal, and preference are all non-significant at p ≥ 0.63, the expected cost of adding
more candidate facts to the retrieved set; note turn-recall actually *rises* everywhere,
§3.4). This is the defining property of the fix: large where it should be, invisible
everywhere else.

### 3.4 The bottleneck flips from recall to reasoning

We decompose each answerable question (n = 470; the 30 abstention questions have no
gold turns) by whether retrieval surfaced all gold turns (`turn_hit = 1`) and whether
the final answer was correct.

| Run | hit-rate | acc \| hit=1 | acc \| hit=0 | reasoning-error share | retrieval-miss share |
|---|---|---|---|---|---|
| deterministic | 0.502 | 0.907 | 0.274 | 0.047 | **0.362** |
| flat-llm | 0.906 | 0.864 | 0.477 | **0.123** | 0.049 |
| agentic-llm | 0.887 | 0.880 | 0.472 | **0.106** | 0.060 |
| retain | **0.949** | 0.863 | 0.500 | 0.130 | **0.026** |

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
the binding constraint — the reader is. The retention fix pushes hit-rate to **0.949**
and halves the residual retrieval-miss share to **0.026** (turn-recall 0.940 → 0.975,
session-hit 0.983 → 0.994), confirming that the assistant-turn failures were missing
*evidence*, not missing *reasoning*.

A subtle point: `acc | hit=1` is *lower* for LLM extraction (~0.86) than for
deterministic (0.907). This is a selection effect, not a reader regression — the
deterministic system only surfaces evidence for the easy half of questions, so its
"evidence-present" subset is easier; LLM extraction surfaces evidence for the hard
questions too, and those are harder to reason over even with the evidence in hand.

### 3.5 Operational cost of retention

Retention changes ingest extraction, not retrieval breadth. The retrieval primary limit
is 40 (median 40, p95 40 in both runs); a fallback occasionally adds a few items (flat
max 56, retain max 52; 14/500 and 11/500 questions exceed 40), but the retrieved-set size
distribution is effectively identical across the two runs — so retrieval *breadth* is not
what retention changes; assistant memories compete within the same retrieved set rather
than enlarging it. What
grows is per-item length: mean reader context rises from **8,042 to 9,569 tokens** (+19%;
median 7,896 → 9,174, p95 10,923 → 14,027) and total reader tokens from 4.53M to 5.38M,
because retained assistant memories preserve verbatim lists and numbers. Counter-
intuitively, total extracted memories *fall* (mean **779.9 → 718.5** per question): with
retention off, assistant turns are still extracted, but under the liberal user-centric
prompt, which emits many mis-attributed, non-recallable memories; retention routes them
to a targeted assistant prompt that emits fewer but answer-bearing memories. User-turn
extraction is byte-identical between the two runs — the extraction cache key omits role on
the user path, so user turns are cache hits with identical results, verified by
`test_user_path_identical_regardless_of_retain_flag` — so the entire claim-count and
context-size delta is the assistant-path change alone. We deliberately do *not* report
wall-clock as a cost: both runs are served from a content-addressed extraction/embedding
cache, so runtime is dominated by cache warmth and is not a clean measure.

## 4. Failure analysis

### 4.1 The assistant-extraction defect: diagnosis

LLM extraction introduces exactly one systematic regression — `single-session-assistant`
falls from 0.964 to 0.750 — and the failure leaves an unmistakable fingerprint. The
accuracy is `42/56` in **both** the flat and agentic runs, and not approximately: the two
runs fail on the **identical 14 questions** (overlap 14, flat-only 0, agentic-only 0).
Every one of those 14 has `turn_hit = 0` — the gold turn was *never retrieved*. Turn-level
hit-rate for this type drops from 0.911 (deterministic) to 0.696 under both LLM runs, and
accuracy tracks it almost exactly.

That two *different* retrieval strategies converge on the exact same 42/56 is the
diagnosis: this is a pure **ingest** defect, upstream of retrieval. You cannot retrieve a
fact that was never stored, so the choice of retrieval algorithm is irrelevant. The cause
is structural: `single-session-assistant` questions ask what the **assistant** previously
said ("what move did you make after 27. Kg2 Bd5+?", "how many mummies will the party
face?", "what was the 27th parameter on that list?"). The extractor is designed to distill
durable facts *about the user* and therefore discards assistant-authored content, so those
turns never become memories. The reader then correctly abstains ("I don't have any record
of providing that…") because the fact genuinely is not in the store. The deterministic
extractor, which keeps one memory per observation regardless of speaker, retains them —
hence its 0.964 on this type. This is significant (deterministic vs flat: b=13, c=1,
p = 0.0018).

### 4.2 The fix and its result: coverage recovered, one fidelity case remains

The fix is a flag-gated, role-aware change at ingest: when `retain_assistant_facts` is on,
the extractor additionally distills `"The assistant …"` memories from assistant turns,
while the user-turn path stays byte-identical (so the A/B isolates exactly this variable).
The result is clean:

- **All 14 coverage failures recover.** `single-session-assistant` goes 42/56 → 55/56
  (0.750 → **0.982**, Wilson [0.906, 0.997]), turn-hit 0.696 → 0.964, net +13 (p = 0.0010).
  The recovered type now *exceeds* the deterministic substrate's 0.964 and is statistically
  tied with it (det 54/56 vs retain 55/56; b=1, c=2).
- **No collateral damage.** No other type moves significantly (§3.3); the fix is
  side-effect-free at the resolution of this benchmark.

The one residual failure (`58470ed2`) is instructive because it is a *different* failure
mode — **fidelity, not coverage**. The question asks for a verbatim Borges quote ("a sphere
whose exact center is any one of its hexagons and whose circumference is inaccessible").
Retention *did* store an assistant memory about *The Library of Babel* — "Borges" appears
five times in the assembled context — but the extractor **paraphrased** the turn ("the
universe is composed of an indefinite… number of hexagonal galleries") and dropped the
exact sentence the question targets; "sphere" and "circumference" appear zero times in
context, so `turn_hit = 0`. The deterministic substrate answers this one correctly because
it stores the assistant turn *verbatim*. In other words, LLM extraction trades the raw
substrate's verbatim fidelity for compression: that compression (a) used to drop assistant
facts entirely — the dominant, now-fixed *coverage* gap — and (b) still paraphrases the
rest, leaving a small residual on quote-exact questions. The narrow remaining lever would
be preserving verbatim spans for assistant turns flagged as quotes/lists, but it is a
single question on this split and a separate experiment.

### 4.3 Reasoning-on-evidence failures (the persistent majority)

With the assistant-coverage gap closed, the dominant remaining error class is unchanged:
answers that are wrong despite the gold evidence being in context. The 58 flat-llm errors
with evidence present cluster into four modes (all persist under retain):

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

### 4.4 A negative result: read-time reasoning scaffold does not pay off

§4.3 makes read-time reasoning the obvious next lever, so we tested it directly. We added
a non-parity reader mode that scaffolds the answer with *structured, visible* evidence
(identify question type → extract evidence notes → perform explicit
date/aggregation/current-state computation → emit a concise `ANSWER:` that is parsed back
out), gated behind a flag so the frozen parity reader is untouched. This is a structured
evidence compiler, not a hidden "think step by step" prompt. We validated it on a
50-question slice (seed 42 — the same instances as the parity run `pref-extract-s`, with
retention on, differing in reader mode; both runs request `claude-sonnet-4-5`, though the
scaffold manifest pins the `-20250929` snapshot while the parity manifest records the
alias, so the intended single variable is the reader mode modulo same-family resolution),
and it **regressed** accuracy from 0.940 to 0.880 (net −3 of 50). It fixed exactly one question (a knowledge-update) and broke
four — one multi-session, one temporal-reasoning, and **two single-session-preference** —
where the added reasoning steps talked the reader out of a correct grounded answer. Mean
reader output grew from 97 to 449 completion tokens while the `ANSWER:` parse stayed
reliable, so the regression reads as *overthinking*, not an answer-format mismatch or a
context-length artifact. Per the pre-registered gate (only promote interventions that
improve the slice), the scaffold was **not** shipped to default and the corresponding full
run was **not** executed; the mode ships flag-gated **off**. The lesson is narrow but
real: even a structured, visible evidence compiler is not a free win on this benchmark,
and the targeted reasoning fixes that would actually help (a deterministic
date-normalization or recency-selection pass) remain future work.

## 5. Discussion: where the headroom actually is

Four conclusions follow directly from the data:

1. **LLM extraction is the headline win and should stay on.** It is the only change that
   moves overall accuracy at scale, and it does so by ~23 points.
2. **Agentic retrieval is not worth enabling as a default.** It is statistically tied
   with flat retrieval; its only measurable edge is a small context-size reduction.
   Retrieval breadth and read-time reordering are exhausted levers on this benchmark.
3. **Assistant retention is a clean, targeted ingest fix and should be on by default.**
   It recovers the one regression LLM extraction introduced (+13 on the affected type,
   p = 0.0010), brings that type *above* the deterministic substrate, and harms nothing
   else. The one residual case reframes the remaining ingest problem from *coverage*
   (solved) to *fidelity* (verbatim spans), a much smaller target.
4. **The remaining headroom is reasoning-on-evidence — but not via generic scaffolding.**
   With ~72% of errors occurring on evidence the system already retrieved, and a generic
   reasoning scaffold failing its validation slice (§4.4), the highest-value work is
   *specific* reader-side competencies — temporal arithmetic, cross-session aggregation,
   and supersession/recency selection — not broad chain-of-thought, and not more
   retrieval.

The methodological throughline: every intervention here was flag-gated, validated on a
cheap slice before any full run, and measured paired against a frozen baseline on the same
500 questions. That discipline is what let a +13 on one type be distinguished from noise,
and what stopped a plausible-sounding reader scaffold from shipping on the strength of a
good demo.

## 6. Limitations

- **Single reader / single judge.** All numbers are for one reader (Sonnet 4.5) and one
  judge snapshot; reader-side conclusions may not transfer to other readers.
- **Judge non-parity on the baseline.** The deterministic baseline used a different
  judge snapshot (`gpt-4o-2024-11-20`); estimated ≤1-point effect, immaterial to the
  extraction result but worth noting. The flat, agentic, and retain runs all share the
  parity `gpt-4o-2024-08-06` judge, so the retain-vs-flat comparison is judge-clean.
- **One extractor.** LLM extraction used `gpt-4o-mini`; a stronger extractor might raise
  recall further and, in particular, preserve the verbatim spans that cause the one
  residual `single-session-assistant` fidelity failure.
- **S split only.** Results are for cleaned LongMemEval-S (500); the larger / oracle
  splits are untested here.
- **Turn-hit is a proxy, defined precisely** as `turn_hit = (gold_turns ⊆ ctx_turns)`,
  where `gold_turns` are the dataset's `has_answer` turn ids and `ctx_turns` are the
  source-turn ids recovered from each *retrieved memory's* provenance. It therefore
  measures whether a memory **derived from the gold turn** was retrieved — not raw-turn
  retrieval and not memory-text matching. It can (a) undercount when a memory derived from
  a non-gold turn is semantically sufficient, and (b) read 0 when the gold-turn memory was
  paraphrased so the query no longer retrieves it — exactly the residual Borges case
  (§4.2), where the source turn's "sphere/circumference" sentence was compressed away.
- **Read-time scaffold tested at 50 questions.** The negative result in §4.4 is a slice
  decision under the pre-registered gate, not a full-500 measurement; a more targeted
  reasoning intervention could still pay off and was not exhaustively explored.

## 7. Conclusion

On the full LongMemEval-S benchmark, LLM-based memory extraction lifts the ActiveGraph
semantic pack from 0.606 to 0.834 and, in doing so, converts the task from a retrieval
problem into a reasoning problem: most remaining errors happen with the right evidence
already in front of the reader. Agentic retrieval adds nothing at scale. The one
regression LLM extraction introduces — discarding assistant-authored facts — is a pure
ingest defect with a clean fingerprint (two retrieval strategies failing on the identical
14 questions), and a targeted role-aware retention fix recovers all of it, lifting
`single-session-assistant` to 0.982 and overall accuracy to 0.848 with no collateral
damage. The other predicted lever, a read-time reasoning scaffold, failed its validation
slice and was not shipped. The path forward is ingest *fidelity* (verbatim spans) and
*specific* reader competencies (temporal, aggregation, supersession) — not retrieval
breadth and not generic scaffolding.

## Appendix A: Reproduction

All figures are regenerated from the run stores under `runs/`:

```
cd longmemeval-harness
# overall / per-type / significance tables (§3) and the retain comparison:
../.pythonlibs/bin/python -m analysis.significance \
    --det full-s-sonnet --flat task18-flat-500 --agentic task19-retain-500
# failure examples (§4):
../.pythonlibs/bin/python -m analysis.failures \
    --flat task18-flat-500 --agentic task19-retain-500
```

Run artifacts:
- `runs/full-s-sonnet/` — deterministic + flat (overall 0.606)
- `runs/task18-flat-500/` — llm + flat, retention off (overall 0.834) — Track-1 baseline
- `runs/task18-agentic-500/` — llm + agentic, retention off (overall 0.840)
- `runs/task19-retain-500/` — llm + flat, retention on (overall 0.848)

Each `store.sqlite` holds one row per question with the retrieval result, assembled
context, reader hypothesis, gold answer, judge decision, turn/session recall and hit,
token counts, and latencies. Run-level configuration (extraction, retrieval, reader mode,
retention flag, judge/reader/dataset identifiers) is recorded in each run's
`manifest.json`.

## Appendix B: Assistant-retention audit (the 14 recovered questions)

The table below is the per-question audit for every `single-session-assistant` question
that was wrong under `task18-flat-500` and correct under `task19-retain-500`. In **all 14**,
`turn_hit` flips `0 → 1`: under flat the gold assistant turn produced no retrievable
memory (the reader typically abstains, "I don't have any record…"); under retain a
`"The assistant …"` memory derived from that exact turn is retrieved and carries the gold
answer. User-authored memories are unchanged across the two runs (cache-keyed user path,
§3.5). The snippet column is the highest gold-overlap assistant memory found in the
assembled context; `turn_hit = 1` is the rigorous proof that a memory derived from the
gold turn was retrieved.

| qid | gold answer | flat | retain | retained assistant memory that carried the answer |
|---|---|---|---|---|
| `1568498a` | 28. Kg3 | ✗ (hit=0) | ✓ (hit=1) | "the assistant made the move 28. Kg3 in a chess game." |
| `18dcd5a5` | 4 (mummies) | ✗ | ✓ | the assistant's *Lost Temple of the Djinn* one-shot encounter breakdown |
| `1903aded` | Transcriptionist (7th) | ✗ | ✓ | "The assistant provided a list of remote job options: 1. Virtual customer service rep… " |
| `3e321797` | 10 minutes | ✗ | ✓ | "The assistant provided a list of remedies for under-eye dark circles (cucumber…)" |
| `41275add` | 'How to Sit Properly at a Desk…' (Mayo Clinic) | ✗ | ✓ | "The assistant recommended the following YouTube videos for proper workplace posture: 1. 'How to Sit Properly…'" |
| `71a3fd6b` | +49 (0) 62 32 / 14 23 - 0 | ✗ | ✓ | "The assistant provided the contact details for the tourism board of Speyer…" |
| `7e00a6cb` | International Budget Hostel | ✗ | ✓ | "The assistant listed several budget-friendly hostels in Amsterdam…" |
| `8752c811` | 27th = 'Sound effects…' | ✗ | ✓ | "The assistant provided a list of 100 prompt parameters…" |
| `8aef76bc` | Mod Podge or another sealant | ✗ | ✓ | "The assistant provided a list of DIY home decor projects using recycled materials…" |
| `a40e080f` | Patagonia and Southwest Airlines | ✗ | ✓ | "The assistant provided examples of two companies that prioritize employee safety: Patagonia and Southwest…" |
| `b759caee` | @jessica_poole_jewellery | ✗ | ✓ | "The assistant recommended three jewelry designers… 1. Jessica Poole (@jessica_poole_jewellery)…" |
| `ceb54acb` | 'sexual fixations', … | ✗ | ✓ | "The assistant provided the following alternatives…: 1. Sexual fixations…" |
| `e3fc4d6e` | Dr. Arati Prabhakar | ✗ | ✓ | the assistant's summary of the LLNL fusion-breakthrough announcement |
| `fca762bc` | Memrise | ✗ | ✓ | "The assistant recommended the language learning apps Duolingo, Rosetta Stone, Babbel, Memrise, and Lingodeer…" |

The single non-recovered `single-session-assistant` question (`58470ed2`, the Borges
*Library of Babel* verbatim quote) is the fidelity case of §4.2: a `"The assistant …"`
memory about the Library *was* stored, but it paraphrased the source turn ("indefinite
hexagonal galleries") and dropped the exact "sphere / center / circumference" sentence, so
the gold-turn memory was not retrieved (`turn_hit = 0`). The deterministic substrate
answers it because it retrieves the raw turn verbatim — the system under test retrieves
only extracted memories (with source-turn provenance), not raw turns, which is why a
verbatim-span anchor is the natural next ingest experiment.
