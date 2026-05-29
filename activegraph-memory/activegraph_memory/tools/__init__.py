"""Memory-pack tools.

Plain helper functions (used inside behaviors) and ``@tool``-decorated
wrappers (registered with the pack so callers can invoke them through
the ActiveGraph tool interface).
"""

from __future__ import annotations

from activegraph_memory.tools.keyword_search import (
    KeywordSearchInput,
    KeywordSearchOutput,
    SearchHit,
    keyword_search,
    keyword_search_fn,
)
from activegraph_memory.tools.vector_search import (
    VectorSearchInput,
    VectorSearchOutput,
    vector_search,
    vector_search_fn,
)
from activegraph_memory.tools.embeddings import (
    DeterministicEmbeddingProvider,
    embed,
)
from activegraph_memory.tools.text_normalize import (
    normalize,
    tokenize,
    extract_keywords,
)
from activegraph_memory.tools.scoring import (
    keyword_score,
    cosine_similarity,
)
from activegraph_memory.tools.concepts import (
    ConceptExtractor,
    concepts_for_memory,
    deterministic_concepts,
    get_active_concept_extractor,
    normalize_concept,
    set_active_concept_extractor,
)
from activegraph_memory.tools.retrieval import (
    ConceptHit,
    DefaultAgenticController,
    FactHit,
    RetrievalController,
    RetrievalDecision,
    RetrievalTools,
    get_active_retrieval_controller,
    set_active_retrieval_controller,
)

TOOLS = [keyword_search, vector_search]

__all__ = [
    "TOOLS",
    "KeywordSearchInput",
    "KeywordSearchOutput",
    "SearchHit",
    "keyword_search",
    "keyword_search_fn",
    "VectorSearchInput",
    "VectorSearchOutput",
    "vector_search",
    "vector_search_fn",
    "DeterministicEmbeddingProvider",
    "embed",
    "normalize",
    "tokenize",
    "extract_keywords",
    "keyword_score",
    "cosine_similarity",
    "ConceptExtractor",
    "concepts_for_memory",
    "deterministic_concepts",
    "normalize_concept",
    "set_active_concept_extractor",
    "get_active_concept_extractor",
    "ConceptHit",
    "FactHit",
    "RetrievalDecision",
    "RetrievalTools",
    "RetrievalController",
    "DefaultAgenticController",
    "set_active_retrieval_controller",
    "get_active_retrieval_controller",
]
