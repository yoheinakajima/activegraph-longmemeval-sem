# Memory is Hard: What Semantic Memory Adds (and Breaks) on LongMemEval-S

*Technical benchmark note: LLM semantic extraction lifts the ActiveGraph memory pack from 60.6% to 83.4% QA accuracy on cleaned LongMemEval-S (n=500), a large and statistically established gain (paired McNemar, +114 of 500, p < 1e-15). But the gain is not free. The bottleneck flips from retrieval to reader reconciliation: with extraction on, ~72% of remaining errors happen with the gold evidence already in context. Agentic retrieval adds nothing at scale (84.0% vs 83.4%, p = 0.72). And the extractor silently drops assistant-authored facts, which significantly regresses one question type (96.4% → 75.0%, p = 0.0018).*

- research
- benchmark

---

In the [previous post](https://activegraph.ai/blog/evidence-compilation-before-semantic-memory-longmemeval) I tested a narrow prerequisite for ActiveGraph: whether the deterministic runtime substrate could compile useful evidence from long conversations *before* semantic memory was added. The answer was yes — the event-sourced substrate was not a retrieval tax, landing 85.6% QA at a ~2.4k-token budget, statistically tied with dense turn-RAG and the gold-session oracle. That post ended with an explicit promise:

> Semantic writes, update semantics, provenance-aware memory evolution, and agent-experience memory remain follow-up hypotheses... That would be the real ActiveGraph semantic-memory test. This run does not answer it.

This post answers it. I turned on the semantic-memory layer — LLM-based fact extraction at ingest — and ran the full cleaned `s` split again. The headline is that semantic memory is a large, real win. The more useful finding is the title of this post: **memory is hard**, because the obvious win comes bundled with new and subtler failure modes that retrieval-side metrics had been hiding.

## What this run is, and is not

This is **not** a re-run of the 85.6% substrate. The earlier post measured a tuned deterministic *retrieval* pipeline (`activegraph-det-embedding`): embedding-scored turns, temporal expansion, deterministic packing, and crucially **no LLM at ingest**. This post measures the **semantic-memory pack** — the deferred system — which performs LLM fact extraction, consolidation, contradiction detection, and temporal resolution at ingest, then retrieves over the extracted memories with a keyword+vector blend.

So the comparison of interest here is *internal to the pack*: extraction **off** (deterministic, one memory per observation) vs extraction **on** (an LLM extractor). The deterministic-extraction mode of the pack (60.6%) is a weaker retrieval configuration than the earlier substrate, so do not read "60.6 → 83.4" as a regression-then-recovery from 85.6. It is a clean A/B on whether generative memory writing helps, holding the reader, judge, prompt, and benchmark fixed.

The claim hierarchy for this post:

> **Established (paired, significant):** LLM semantic extraction is a large QA win over deterministic extraction within this pack, and it works by converting retrieval misses into evidence-present questions.
>
> **Established (paired, significant):** flat and agentic retrieval are tied at scale; the earlier 50-question "flat beats agentic" was sampling noise.
>
> **Established (paired, significant):** the extractor drops assistant-authored facts, regressing the `single-session-assistant` type.
>
> **Observed, not yet causal:** the remaining ceiling is reader reconciliation (temporal arithmetic, cross-session aggregation, knowledge supersession, preference grounding), not retrieval breadth.

## What was tested

Unlike the substrate post, this run **does** use LLM-generated memory at ingest. The pack:

- ingests every session/turn and extracts durable memories with a cached `gpt-4o-mini` extractor (temperature 0, JSON, confidence threshold 0.65);
- consolidates, dedupes, detects contradictions, and resolves temporal references over those memories;
- retrieves the top-40 memories per question with a keyword+vector blend (no rerank, no HyDE, no query expansion);
- assembles a chronological evidence bundle and hands it to the reader.

Everything downstream is frozen and shared across runs: the reader is `claude-sonnet-4-5` (temperature 0, `max_tokens=1024`) with the same prompt template used in the substrate post — a deliberate control so accuracy differences reflect *what was written to memory and retrieved*, not reader choice. The judge is `gpt-4o-2024-08-06`. Dataset is cleaned LongMemEval-S, 500 instances, seed 42. Three runs, all 500/500 with zero errors:

| Run | Extraction | Retrieval | QA accuracy (n=500) | Wilson 95% CI |
|---|---|---|---|---|
| deterministic | off | flat | 0.606 | [0.563, 0.648] |
| **semantic (flat)** | **llm** | flat | **0.834** | [0.799, 0.864] |
| **semantic (agentic)** | **llm** | agentic | **0.840** | [0.805, 0.870] |

## Main result: semantic memory is a large, established win

Because all three systems are scored on the same 500 questions, the right test is paired. I use exact McNemar on per-question correctness. `b10` = semantic correct and deterministic wrong; `b01` = deterministic correct and semantic wrong.

| Comparison | b10 | b01 | net | McNemar p | reading |
|---|---|---|---|---|---|
| semantic-flat vs deterministic | 141 | 27 | **+114** | < 1e-15 | large, established win |
| semantic-agentic vs deterministic | 148 | 31 | **+117** | < 1e-15 | large, established win |
| semantic-agentic vs semantic-flat | 17 | 14 | +3 | **0.72** | **tied in this run** |

This is the opposite shape from the substrate post's main comparison. There, the headline edge (ActiveGraph vs dense turn-RAG) was a +2-point *tie* (p = 0.132). Here, turning on extraction is a +22.8-point win whose discordance is overwhelmingly one-directional — 141 questions flip from wrong to right, only 27 the other way. There is no statistical ambiguity: semantic extraction helps, and it helps a lot.

The agentic loop, by contrast, is a genuine null. The +0.6-point nominal edge comes from 31 discordant questions split 17/14, with p = 0.72 and no per-type delta reaching significance (the closest is temporal-reasoning, +4, p = 0.34). The earlier 50-question result that ranked flat (0.94) above agentic (0.90) does not survive at scale; it was noise. Agentic does retrieve a slightly tighter context (mean 7,651 vs 8,042 reader tokens for equal accuracy), so it is plausibly a marginal precision improvement, but the accuracy difference is zero and it does not justify the extra retrieval-loop LLM calls. **Flat retrieval stays the default.**

## What is significant and what is not

The substrate post's discipline applies here too: separate "the number moved" from "the number moved for a reason we can defend."

**Established.** The extraction win (both retrieval strategies), the flat/agentic tie, and the assistant-extraction regression (below) are all paired-significant.

**Per-type, mixed.** Extraction is significant on the cross-session and synthesis types but the picture is not uniform:

| Type (n) | deterministic | semantic-flat | semantic-agentic |
|---|---|---|---|
| knowledge-update (78) | 0.756 | 0.846 | 0.808 |
| multi-session (133) | 0.346 | 0.827 | 0.827 |
| single-session-assistant (56) | **0.964** | **0.750** | **0.750** |
| single-session-preference (30) | 0.367 | 0.867 | 0.933 |
| single-session-user (70) | 0.829 | 0.943 | 0.943 |
| temporal-reasoning (133) | 0.564 | 0.805 | 0.835 |

The wins are concentrated where deterministic extraction was starving the reader: multi-session (0.346 → 0.827), preference (0.367 → 0.867/0.933), temporal (0.564 → 0.805/0.835). The one category that goes the wrong way — `single-session-assistant`, 0.964 → 0.750 — is not noise (more below).

## Retrieval-side result: the bottleneck flips

End-to-end QA mixes two things: whether retrieval surfaced the evidence, and whether the reader used it. The substrate post separated them with an answer-in-context sidecar; I do the same here, reusing the same definitions and the same 30-abstention exclusion (n = 470):

- **turn-AIC**: fraction of questions where all labeled gold turn IDs reached the reader.
- **session-AIC**: the same at session granularity.
- **rfwe**: reader-failed-with-evidence — judged wrong *despite* the labeled evidence being retrieved.

| Run | turn-AIC | session-AIC | acc \| turn-AIC hit | acc \| turn-AIC miss | rfwe (of 470) | retrieval-miss errors |
|---|---|---|---|---|---|---|
| deterministic | 0.502 | 0.774 | 0.907 | 0.274 | 22 | 170 |
| semantic-flat | 0.906 | 0.983 | 0.864 | 0.477 | **58** | 23 |
| semantic-agentic | 0.887 | 0.979 | 0.880 | 0.472 | **50** | 28 |

This is the heart of the post. In the deterministic pack, retrieval is the binding constraint: it places the gold turn only half the time (turn-AIC 0.502), and **170 of 192 answerable errors are pure retrieval misses**. Semantic extraction nearly eliminates that — turn-AIC jumps to 0.906, session-AIC to 0.983 — and the failure mode **inverts**. For semantic-flat, **58 of 81 answerable errors (72%) are rfwe**: the gold evidence is already in context and the reader still gets it wrong. Retrieval is no longer the problem. The reader is.

This is exactly the regime the substrate post anticipated for knowledge-update but could not test, because deterministic retrieval was already near ceiling there. Now the whole benchmark is in that regime.

One subtlety, because it looks alarming and is not: `acc | turn-AIC hit` is *lower* for semantic (0.864) than deterministic (0.907). That is a selection effect, not a reader regression. Deterministic extraction only surfaces evidence for the easy half of questions, so its "evidence-present" subset is easy by construction. Semantic extraction surfaces evidence for the hard questions too — and those are harder to reason over even with the evidence in hand. The reader did not get worse; it is now being asked the hard questions it never used to see.

## The assistant-extraction regression

The `single-session-assistant` regression is the clearest defect the semantic layer introduces, and it is mechanistic, not statistical noise. Every one of the 14 semantic-flat failures on this type has **turn-AIC = 0**: the gold turn was never retrieved. Turn-AIC for the type collapses from 0.911 (deterministic) to 0.696 (both semantic runs), and accuracy tracks it almost exactly (0.750). The paired test is unambiguous (deterministic vs semantic-flat: b = 13 won by deterministic, 1 the other way, p = 0.0018).

The cause is structural. `single-session-assistant` questions ask what the **assistant** previously said:

> *"What move did you make after 27. Kg2 Bd5+?"* — gold: 28. Kg3
> *"How many mummies will the party face in the temple?"* — gold: 4
> *"What was the 27th parameter on that list you gave me?"* — gold: 'Sound effects...'

The extractor is built to distill durable facts *about the user*, so it discards assistant-authored content. Those turns never become memories, so retrieval cannot find them, so the reader correctly abstains: *"I don't have any record of providing that…"* The deterministic mode, which keeps one memory per observation regardless of speaker, retained them. This is a write-time policy bug, not a retrieval or reader bug, and it is the cheapest fix on the board: retain assistant-authored facts at ingest and most of the lost 21 points come back with no downside elsewhere.

There is a nice irony here, and it is why the post is titled the way it is. The substrate had near-perfect recall on these questions *because it was dumb* — it stored everything. The "smarter" semantic layer is the thing that decided assistant turns were not worth remembering.

## rfwe, by type: four reasoning failures

The 58 semantic-flat rfwe cases cluster into four reconciliation failures — the reader has the evidence and still misfires:

- **Temporal arithmetic (22).** Dates are present; the interval is miscomputed. *"How many weeks since I recovered from the flu when I went on my 10th jog?"* — both dates in context (Jan 19 → Apr 10), reader says 12 weeks, gold 15. Another reads two timestamps on one record as start=end and concludes a 21-day read took "0 days."
- **Cross-session aggregation (16).** Counting/summing across sessions fails. *"How many art events did I attend last month?"* — reader lists 3, gold 4. *"Page count of the two novels I finished in January and March?"* — reader cannot bind the months and abstains.
- **Knowledge supersession (12).** Both old and updated facts are retrieved and the reader picks the stale one. *"Where do I currently keep my old sneakers?"* — answers "under your bed" (superseded) over the current "shoe rack." This **confirms the substrate post's prediction verbatim**: it argued a semantic layer should help knowledge-update "by marking facts as superseded before assembly... not by improving retrieval recall." Retrieval recall on knowledge-update is ~ceiling (turn-AIC 0.96); the remaining failures are reconciliation, exactly as predicted. The typed-supersession lever is still untested, and this run says it is the right lever.
- **Preference grounding (4).** The implicit preference is in context but the reader gives generic advice. *"Any tips for my phone battery?"* — the user earlier bought a power bank (in context); the reader returns boilerplate instead of building on it.

None of these are retrieval problems. They are the reader reconciling evidence it already has.

## What I take from this

Three conclusions, in decreasing order of confidence:

1. **Semantic extraction is the headline win and should stay on.** It is the only change that moves QA at scale, by ~23 points, and it does so by converting retrieval misses into evidence-present questions. The substrate post's deferred hypothesis — that semantic memory would help — is supported.
2. **Agentic retrieval is not worth enabling.** It is statistically tied with flat retrieval; its only measurable edge is a small context-size reduction. On this benchmark, retrieval breadth and read-time reordering are exhausted levers.
3. **The remaining ceiling is reader reconciliation, plus one write-time fix.** With 72% of errors landing on evidence the system already retrieved, the high-value work is reader-side reasoning (temporal arithmetic, cross-session aggregation, supersession selection, preference grounding) and stopping the extractor from discarding assistant-authored facts. Because the reader prompt is a frozen parity control, reader-side changes belong on an explicitly non-parity track, measured on a 50-question slice first and confirmed on the full 500.

The broader lesson is the one the substrate post hinted at and this run makes concrete: a memory system's hard problems do not disappear when retrieval gets good — they move. Better memory turned a retrieval benchmark into a reasoning benchmark, and surfaced a write-time policy question (what is worth remembering?) that a dumber store never had to answer. Memory is hard because the bottleneck is a moving target.

## Limitations

- **Single reader, single judge.** All numbers use one reader (Sonnet 4.5) and the `gpt-4o-2024-08-06` judge; reader-side conclusions may not transfer.
- **Judge non-parity on the baseline.** The deterministic baseline used `gpt-4o-2024-11-20`; the two semantic runs used the parity snapshot. Estimated ≤1-point effect, immaterial to a 23-point result.
- **One extractor.** Extraction used `gpt-4o-mini`; a stronger extractor might raise recall further and might not drop assistant content.
- **turn-AIC is a labeled-evidence proxy.** As in the substrate post, rfwe can be overcounted when a question is answerable from unlabeled context, and assistant-content questions are exactly where label coverage matters most.
- **Not graph-causal.** Extraction, consolidation, contradiction detection, and retrieval move together; this run validates the semantic pipeline as a bundle, not any single component.

## Reproduction

All figures regenerate from the run stores under `runs/`:

```
cd longmemeval-harness
../.pythonlibs/bin/python -m analysis.significance   # accuracy, McNemar, AIC tables
../.pythonlibs/bin/python -m analysis.failures       # the rfwe examples quoted above
```

Runs: `runs/full-s-sonnet` (deterministic, 0.606), `runs/task18-flat-500` (semantic-flat, 0.834), `runs/task18-agentic-500` (semantic-agentic, 0.840). Each `store.sqlite` holds one row per question with the retrieval result, assembled context, reader hypothesis, gold answer, judge decision, turn/session AIC, token counts, and latencies.
