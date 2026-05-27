"""Behavior 2 — detect_contradictions.

Trigger: ``object.created`` for any memory object (claim, episodic, procedural).

Compare against existing active memories of the same type. Emit either:
  - a ``supersedes`` edge if the new text signals replacement
    ("now called X", "actually Y", "renamed to Z") and the old memory's
    status patches to ``superseded``,
  - or a ``contradicts`` edge with the older memory patched to
    ``needs_review`` when uncertain.

The behavior is registered three times — once per memory type — because the
ActiveGraph ``where=`` filter does not support ``in [...]`` semantics. The
behavior bodies are identical and dispatched through ``_compare``.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import (
    content_signature,
    subject_key,
    text_signals_supersession,
)
from activegraph_memory.constants import (
    STATUS_ACTIVE,
    STATUS_NEEDS_REVIEW,
    STATUS_SUPERSEDED,
)
from activegraph_memory.settings import MemorySettings
from activegraph_memory.tools.text_normalize import tokenize


def _compare(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_contradiction_detection:
        return
    new_obj = event.payload.get("object", {})
    new_id = new_obj.get("id")
    new_type = new_obj.get("type")
    new_data = new_obj.get("data") or {}
    new_content = (new_data.get("content") or "").strip()
    if not (new_id and new_content):
        return

    new_sig = content_signature(new_content)
    new_key = subject_key(new_content)
    new_tokens = set(tokenize(new_content))
    replaces = text_signals_supersession(new_content)

    for other in ctx.view.objects(type=new_type):
        if other.id == new_id:
            continue
        other_data = other.data or {}
        if other_data.get("status") != STATUS_ACTIVE:
            continue
        other_content = other_data.get("content") or ""
        if not other_content:
            continue
        if content_signature(other_content) == new_sig:
            continue  # exact duplicates -> consolidation, not contradiction

        other_key = subject_key(other_content)
        other_tokens = set(tokenize(other_content))
        if not other_key or other_key != new_key:
            continue
        # Need enough overlap to assert they're about the same thing
        overlap = (
            len(new_tokens & other_tokens)
            / max(1, min(len(new_tokens), len(other_tokens)))
        )
        if overlap < 0.4:
            continue
        confidence = min(1.0, 0.7 + overlap / 5)
        if confidence < settings.contradiction_confidence_threshold:
            relation = "contradicts"
            patch_status = STATUS_NEEDS_REVIEW
        elif replaces:
            relation = "supersedes"
            patch_status = STATUS_SUPERSEDED
        else:
            relation = "contradicts"
            patch_status = STATUS_NEEDS_REVIEW

        graph.add_relation(new_id, other.id, relation)
        graph.patch_object(other.id, {"status": patch_status})


@behavior(
    name="detect_contradictions_memory_claim",
    on=["object.created"],
    where={"object.type": "memory_claim"},
)
def _on_claim(event, graph, ctx, *, settings: MemorySettings):
    _compare(event, graph, ctx, settings=settings)


@behavior(
    name="detect_contradictions_episodic",
    on=["object.created"],
    where={"object.type": "episodic_memory"},
)
def _on_episodic(event, graph, ctx, *, settings: MemorySettings):
    _compare(event, graph, ctx, settings=settings)


@behavior(
    name="detect_contradictions_procedural",
    on=["object.created"],
    where={"object.type": "procedural_memory"},
)
def _on_procedural(event, graph, ctx, *, settings: MemorySettings):
    _compare(event, graph, ctx, settings=settings)


# The pack registers a single symbol; we expose the three Behavior objects as
# a list so the package-level __init__ can flatten them.
detect_contradictions = [_on_claim, _on_episodic, _on_procedural]
