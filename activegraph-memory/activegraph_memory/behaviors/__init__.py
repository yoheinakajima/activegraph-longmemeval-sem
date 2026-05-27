"""All memory pack behaviors, aggregated.

Some behaviors are split across multiple object-type filters (because the
``where=`` filter doesn't support ``in [...]`` semantics). Those modules export
a list of ``Behavior`` objects; we flatten them here.
"""

from __future__ import annotations

from activegraph_memory.behaviors.answer_with_evidence import answer_with_evidence
from activegraph_memory.behaviors.attach_numeric_scope import attach_numeric_scope
from activegraph_memory.behaviors.consolidate_memories import consolidate_memories
from activegraph_memory.behaviors.detect_contradictions import detect_contradictions
from activegraph_memory.behaviors.evaluate_memory_usage import evaluate_memory_usage
from activegraph_memory.behaviors.extract_candidate_memories import extract_candidate_memories
from activegraph_memory.behaviors.fallback_retrieve import fallback_retrieve
from activegraph_memory.behaviors.forget_or_archive_memory import (
    archive_memory,
    forget_memory,
)
from activegraph_memory.behaviors.plan_memory_retrieval import plan_memory_retrieval
from activegraph_memory.behaviors.resolve_temporal_refs import resolve_temporal_refs
from activegraph_memory.behaviors.retrieve_memories import retrieve_memories


def _flatten(items):
    out = []
    for it in items:
        if isinstance(it, list):
            out.extend(it)
        else:
            out.append(it)
    return out


BEHAVIORS = _flatten([
    extract_candidate_memories,
    detect_contradictions,
    plan_memory_retrieval,
    retrieve_memories,
    fallback_retrieve,
    answer_with_evidence,
    resolve_temporal_refs,
    attach_numeric_scope,
    consolidate_memories,
    forget_memory,
    archive_memory,
    evaluate_memory_usage,
])

__all__ = ["BEHAVIORS"]
