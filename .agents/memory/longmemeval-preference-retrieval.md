---
name: LongMemEval single-session-preference failure
description: Why the "recommend a show to watch" preference question fails, and why broadening the retrieval stoplist backfires.
---

# single-session-preference is an extraction-gap, not just a retrieval-gap

The recurring failing preference question on LongMemEval-S asks "recommend a
show or movie to watch tonight". Gold answer: user prefers stand-up comedy
specials on Netflix. The preference is **implied by a past user request**
("recommend some stand-up comedy specials on Netflix with strong storytelling
like John Mulaney") — never stated as a preference.

What actually happens in the pack:
- Extraction captures the *fact* "The user is an aspiring stand-up comedian"
  but does NOT mint a clean preference/interest memory from the request.
- That fact's cosine similarity to the recommendation query is ~0.14, so it
  ranks ~80–130 and never enters the top-40 retrieval window.
- The reader therefore sees comedy-adjacent noise ("attended a comedy writing
  workshop") but no usable viewing preference, and abstains.

**Why:** preferences revealed by *what a user asks for* are a different signal
than stated preferences; the conservative extraction prompt skips them, and
recommendation-style queries are lexically/semantically far from how interests
are stored.

**How to apply:** a genuine fix needs the *extraction* side to mint
interest/preference memories from user requests (entertainment/hobby/food
domains). That bumps the extraction PROMPT_VERSION → invalidates the warm
extraction cache → full re-extraction (~1.5h full) AND risks adding noise that
regresses the currently-perfect strong types. Treat as a deliberate,
user-approved experiment, not a quick fix.

# Do NOT broaden the retrieval stoplist to fix this

`keyword_score` = fraction of query keywords present, and the stoplist is
intentionally tiny, so an ultra-common word like "can" ties the top-N cutoff
and floods context with "X can be made / can help" noise. Tempting fix:
add modals/wh-words/quantifiers (can, what, how, some, all, ...) to
`tools/text_normalize._STOPWORDS`.

Measured result on the 50-q stratified s-slice (seed42, sonnet reader,
gpt-4o judge, --extraction llm): it did NOT fix the preference question and
**regressed overall 0.94 → 0.90** — broke one single-session-user and one
temporal-reasoning question.

**Why:** wh-words and quantifiers carry real retrieval signal for temporal and
user questions; stripping them changes ranking unfavorably elsewhere.
**How to apply:** keep the stoplist minimal. Validate any retrieval-scoring
change with a clean before/after per-question diff on the s-slice before
keeping it — type-level accuracy alone hides offsetting flips.
