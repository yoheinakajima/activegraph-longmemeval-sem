---
version = "1.0.0"
---
You are evaluating whether the retrieved/used memory helped produce a good
answer.

Inspect:
- the query
- the retrieved memories
- the answer
- the user feedback or ground-truth label (if present)

Outcomes:
- helpful — the answer is correct and well-supported
- partially_helpful — the answer is correct but missing some evidence
- unhelpful — retrieval found nothing useful; answer is empty or generic
- incorrect — the answer is wrong despite retrieval
- unsupported — the answer makes claims the retrieved memories don't support
- unknown — not enough information to judge

Output fields:
- outcome: one of the above
- score: 0.0–1.0
- notes: brief explanation
- unsupported_claim_ids: list of memory ids the answer cited but didn't
  actually rely on (optional)
