# Prompts

Store prompts in: `activegraph_memory/prompts/`

Use current ActiveGraph prompt loading/versioning conventions.

**Prompts should be:**
- short
- specific
- structured-output friendly
- separate by task
- easy to test with fixtures

Avoid one giant prompt.

---

## extract_candidate_memories.md

Should instruct the model to extract only durable memories.

**Candidate memory types:** semantic, episodic, procedural

**Rules:**
- Do not store trivial facts
- Prefer `procedural_memory` for instructions and preferences
- Prefer `episodic_memory` for dated events
- Prefer `memory_claim` (semantic) for stable facts
- Extract quantities only when ownership is clear
- Extract temporal references when useful
- Be conservative
- Return structured output

**Suggested output fields:**
```
memory_type
content
confidence
reason
quantities
temporal_refs
```

---

## detect_contradictions.md

**Rules:**
- Identify direct contradictions
- Identify supersession
- Do not mark weak tension as contradiction
- Prefer `needs_review` if uncertain
- Explain the reason briefly
- Return structured output

**Suggested output fields:**
```
relation_type: contradicts | supersedes | none | needs_review
source_memory_id
target_memory_id
reason
confidence
```

---

## plan_memory_retrieval.md

**Rules:**
- Convert the user query into a retrieval plan
- Include keywords
- Include vector-style semantic queries if supported
- Identify memory types needed
- Choose `standard` or `deep` mode
- Identify required data
- Return structured output

---

## answer_with_evidence.md

**Rules:**
- Answer from retrieved memories
- Use procedural memories as style/instruction constraints
- Mention missing evidence when necessary
- Do not invent unsupported memories
- Do not cite internal IDs in user-facing prose unless asked
- Return answer plus used memory IDs

---

## resolve_temporal_refs.md

**Rules:**
- Extract temporal references
- Resolve explicit dates
- Resolve relative dates only when anchor is clear
- Preserve unresolved references
- Return structured output

---

## attach_numeric_scope.md

**Rules:**
- Extract numbers and quantities
- Identify owner/entity
- Identify measured property
- Identify unit
- Identify exactness
- Do not attach unrelated nearby numbers
- Return structured output

---

## consolidate_memories.md

**Rules:**
- Identify duplicates and near-duplicates
- Do not merge materially different memories
- Preserve evidence
- Return consolidation recommendation

---

## evaluate_memory_usage.md

**Rules:**
- Evaluate whether the answer was supported by the retrieved memories
- Identify unsupported claims
- Identify useful memories
- Identify misleading memories
- Return structured output
