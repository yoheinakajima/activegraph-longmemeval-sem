"""longmemeval-harness — evaluate the activegraph-memory pack on LongMemEval.

A self-contained, resumable benchmark harness. It treats the
``activegraph-memory`` pack as a frozen, read-only dependency: it only
imports the pack's public surface (``Graph``, ``Runtime``, ``pack``,
``MemorySettings``) and never modifies it.

Pipeline under test (the semantic pack):
    observation -> claim -> retrieval -> answer

The harness adds, around that pipeline:
    dataset loader -> stratified sampler -> pack adapter ->
    LLM reader -> retrieval sidecar scorer -> LLM judge ->
    resumable SQLite store -> manifest + metrics report
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
