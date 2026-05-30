# vNext: hybrid claim + raw-span retrieval

This is a forward-looking design note, not a measured result. It proposes the
next experiment suggested by the triage in `analysis/cleanup_tables.py` and the
figure `analysis/figures/09_proposed_hybrid_retrieval.png`.

## The problem the data points at

On the matched-hit subset (questions where retrieval succeeded for both the
deterministic and flat readers), answer accuracy is essentially equal — the
gap between modes is dominated by **retrieval**, not reader quality
(`01_accuracy_ladder.png`, `05_matched_hit_subset.png`).

But among answerable questions where the gold turn *was* retrieved yet the answer
was still wrong (`turn_hit=1 & wrong`), the LLM triage attributes the large
majority to label **A** (reasoning / evidence-use) and a smaller but real slice
to label **B** (span-loss): the exact value needed to answer was paraphrased or
compressed away during claim extraction, so the reader literally cannot read it
off. `turn_hit=1` proves provenance coverage — that a memory derived from the
gold turn reached the context — **not** that the answer span survived
extraction.

Label B is structurally unfixable at read time: no reranking or trimming can
recover a value that extraction already dropped. It must be fixed where the loss
happens — at ingest / retrieval.

## Proposal

Keep the semantic pack's compressed claims (they carry recall, update semantics,
and dedupe), but **attach the verbatim source span** to each claim and make it
retrievable:

1. **Dual index.** Alongside claim embeddings, index the raw turn text
   (verbatim span) keyed by the same `derived_from` provenance the pack already
   tracks.
2. **Retrieve claims first** (recall), then **back-fill verbatim spans** for the
   top claims into the assembled context (fidelity).
3. **Merge + rerank** the claim + span candidates before handing them to the
   reader, budgeting context so spans are added only for the highest-value
   claims.

The reader then sees both the consolidated claim ("user changed deploy region")
and the verbatim span ("switched to `us-east-1` on Mar 3"), so span-loss (B)
failures become readable while the recall and update benefits of claims remain.

## What to measure

- Does the B slice of the `turn_hit=1 & wrong` triage shrink without inflating
  context cost (`04_context_cost.png`) past an acceptable budget?
- Net accuracy on the full `s` split vs the current flat/retain baselines.
- No regression on abstention accuracy (verbatim spans must not coax the reader
  into answering unanswerable questions).

## Why not just keep everything verbatim

That is the **substrate-only** cell of the 2×2 in
`docs/prior-substrate-comparison.md`: high fidelity, but it forgoes the
compression, update, and dedupe properties that make a semantic memory cheap and
maintainable at scale. The hybrid aims for the top-right cell — claims for
recall/update, spans for fidelity — rather than abandoning either.
