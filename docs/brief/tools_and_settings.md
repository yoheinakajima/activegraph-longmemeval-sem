# Tools and Settings

---

## Tools

Store tools in: `activegraph_memory/tools/`

Tools should be deterministic in tests. Do not require network access for tests.

---

### keyword_search

Simple text search over memory object content.

**Requirements:**
- deterministic
- no network
- works in tests
- supports memory type filtering
- supports status filtering

---

### vector_search

Optional but should be part of the full design.

**Requirements:**
- optional dependency
- deterministic mock embeddings in tests
- supports memory type filtering
- supports status filtering
- does not require external API in tests

---

### embeddings

Provide an interface.

Implement:
- `DeterministicEmbeddingProvider` — for tests (no network, no API)
- `OptionalOpenAIEmbeddingProvider` — if current tool conventions allow

Do not call OpenAI directly inside deterministic behaviors.

---

### text_normalize

Utility for tokenization, lowercasing, punctuation cleanup, keyword extraction.

Should be deterministic.

---

### scoring

Utility for retrieval scoring.

Should be deterministic.

---

## Settings

Create a settings schema using current ActiveGraph settings conventions.

```python
class MemorySettings(BaseModel):
    enable_semantic_memory: bool = True
    enable_episodic_memory: bool = True
    enable_procedural_memory: bool = True
    enable_retrieval_planning: bool = True
    enable_keyword_retrieval: bool = True
    enable_vector_retrieval: bool = False
    enable_contradiction_detection: bool = True
    enable_temporal_resolution: bool = True
    enable_numeric_scope: bool = True
    enable_consolidation: bool = True
    enable_fallback_retrieval: bool = True
    enable_answer_generation: bool = True
    enable_memory_evaluation: bool = True
    extraction_confidence_threshold: float = 0.65
    contradiction_confidence_threshold: float = 0.75
    consolidation_confidence_threshold: float = 0.85
    retrieval_mode_default: Literal["standard", "deep"] = "standard"
    retrieval_limit: int = 10
    fallback_retrieval_limit: int = 5
    include_superseded_in_standard_retrieval: bool = False
    include_archived_in_standard_retrieval: bool = False
    allow_general_knowledge_in_answers: bool = False
    default_policy_name: str = "default"
```

---

## Fixtures

Store fixture files in: `activegraph_memory/fixtures/`

Each fixture is a `.jsonl` file used for offline testing.

| File | Purpose |
|---|---|
| `simple_conversation.jsonl` | Basic observation → memory extraction flow |
| `contradiction_conversation.jsonl` | Two conflicting observations |
| `procedural_memory.jsonl` | Instructions and style preferences |
| `numeric_memory.jsonl` | Observations with numeric facts |
| `temporal_memory.jsonl` | Observations with temporal references |
| `fallback_retrieval.jsonl` | Query that requires fallback retrieval |
| `policy_comparison.jsonl` | Same events run under two different policies |
