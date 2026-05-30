# Prior substrate result vs this work: a 2×2

A common point of confusion: an earlier public result reported LongMemEval
numbers for the same underlying memory **substrate**. That result is **not**
comparable to the numbers here, because it varied a different axis. This note
makes the distinction explicit.

## The 2×2

|                          | **Substrate only** (raw event log / store) | **Semantic pack** (extract → embed → consolidate → retrieve) |
| ------------------------ | ------------------------------------------ | ------------------------------------------------------------ |
| **Prior public result**  | ✅ what it measured                         | —                                                            |
| **This work**            | —                                          | ✅ what we measure                                            |

- The **prior result** stress-tested the *substrate*: it fed retrieved raw
  material to a reader and measured QA accuracy. It did **not** run the semantic
  pack (the claim-extraction + consolidation + semantic-retrieval pipeline).
- **This work** measures the *semantic pack* end-to-end on LongMemEval-S, across
  reader/memory modes (deterministic, flat, agentic, retain).

Because the two occupy different cells of the 2×2, their accuracy numbers are
**not** apples-to-apples. A higher or lower number in one cell says nothing
direct about the other: the substrate result isolates retrieval+reader over raw
spans; this work additionally pays (and measures) the extraction/consolidation
compression step, which is exactly where the span-loss (label B) failures in the
triage come from.

## Why keep both

The substrate and the semantic pack answer different product questions:

- **Substrate**: "if I keep everything verbatim and retrieve well, how far does
  that get me?" — an upper bound on recall-bound reading.
- **Semantic pack**: "if I compress turns into consolidated claims (cheaper,
  updatable, dedup'd), what does that cost me in answerability?"

The proposed hybrid (see `docs/vnext-hybrid-raw-span.md`) is precisely an attempt
to occupy the **top-right** cell — keep the compressed claims for recall and
update semantics, but attach verbatim spans to recover the span-loss failures.

See the methodology section of the README for the exact runs, splits, and judge
configuration behind the numbers in this repo.
