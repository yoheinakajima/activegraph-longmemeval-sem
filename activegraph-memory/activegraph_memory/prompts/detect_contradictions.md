---
version = "1.0.0"
---
You are deciding whether a new memory contradicts or supersedes an existing
memory in the view.

Compare only memories of the same type and the same subject. Ignore weakly
related memories.

Rules:
- "Direct contradiction" means both memories cannot be true at the same time.
- "Supersession" means the new memory explicitly updates the old one
  ("now called X", "actually Y", "renamed to Z", "we decided to change…").
- Do not flag weak tension as contradiction. Prefer `needs_review` when
  uncertain.
- Explain the reason briefly so a reviewer can audit.

Output fields:
- relation_type: "contradicts" | "supersedes" | "needs_review" | "none"
- source_memory_id: the new memory
- target_memory_id: the existing memory you are comparing against
- reason: one-sentence justification
- confidence: 0.0–1.0
