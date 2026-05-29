"""Memory extraction providers.

The extraction behavior (``extract_candidate_memories``) decides, for each new
``memory_observation``, which durable memories to create. In v0.1 this is a
deterministic keyword heuristic (:func:`classify_observation`). This module lets
a caller swap in a smarter extractor (e.g. an LLM) at runtime without threading
it through every behavior signature — exactly mirroring the embeddings
``set_active_provider`` pattern.

The pack itself never reads an API key from the environment. A real LLM-backed
extractor is built and injected by the caller (the harness), keeping the pack
generic and offline-testable. When no extractor is installed, the behavior falls
back to the deterministic heuristic, so default behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class ExtractedMemory:
    """One durable memory proposed for an observation.

    ``memory_type`` is one of ``"procedural" | "episodic" | "semantic"``.
    """

    memory_type: str
    content: str
    confidence: float = 0.85
    reason: Optional[str] = None
    concepts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExtractionProvider(Protocol):
    def extract(
        self, content: str, metadata: dict[str, Any]
    ) -> list[ExtractedMemory]: ...


# Process-wide active extractor. ``None`` means "use the deterministic heuristic
# baked into the behavior" — the default, so the pack runs offline unchanged.
_ACTIVE: Optional[ExtractionProvider] = None


def set_active_extractor(provider: Optional[ExtractionProvider]) -> None:
    """Install the process-wide extraction provider (None resets to heuristic)."""
    global _ACTIVE
    _ACTIVE = provider


def get_active_extractor() -> Optional[ExtractionProvider]:
    return _ACTIVE
