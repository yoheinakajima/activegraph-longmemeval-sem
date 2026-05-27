# contradiction handling

`detect_contradictions` runs on every `object.created` event for
`memory_claim`, `episodic_memory`, and `procedural_memory` (registered
three times because `where=` does not accept lists yet).

## Decision

For the new memory `N` and each existing active memory `O` of the
same type:

1. Skip when `subject_key(N.content) != subject_key(O.content)`. The
   subject key is the first ~2 normalized content tokens, with common
   conversational markers (`update`, `actually`, `correction`,
   `now`, `today`, …) stripped first.
2. Skip when keyword overlap (`|N ∩ O| / min(|N|, |O|)`) is below
   `0.4`. This is the floor for "actually about the same thing."
3. If `text_signals_supersession(N.content)` is true ("now",
   "actually", "renamed", "updated to", …) and confidence is above
   `contradiction_confidence_threshold`, write a `supersedes` edge
   and patch `O.status = "superseded"`.
4. Otherwise write a `contradicts` edge and patch
   `O.status = "needs_review"`.

The new memory is never the loser; the order in the event log
determines priority.

## Old memories are never deleted

A superseded memory stays in the graph with its full provenance and
its `supersedes` / `contradicts` edges. The event log is the source
of truth. Standard retrieval hides `superseded` and `needs_review`
by default; deep retrieval includes them.

## When the heuristic is not enough

The deterministic implementation handles obvious supersession
("Yohei lives in Tokyo." → "Update: Yohei now lives in SF.") and is
deliberately conservative everywhere else, since false positives are
expensive. For semantic contradiction ("Yohei is on the East Coast."
vs "Yohei is on the West Coast.") swap the behavior to
`@llm_behavior` and load `prompts/detect_contradictions.md`.
