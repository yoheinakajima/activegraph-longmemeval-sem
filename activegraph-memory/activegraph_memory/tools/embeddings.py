"""Embedding providers.

``DeterministicEmbeddingProvider`` produces a stable hash-based embedding so
vector search works offline in tests without numpy or an API key. It is NOT
semantically meaningful — equal text in, equal vector out; different text in,
different vector out. That is enough to exercise the lifecycle.

``OpenAIEmbeddingProvider`` is a real, batched, in-memory-cached provider that
calls an OpenAI-compatible embeddings endpoint (e.g. ``text-embedding-3-small``).
A caller swaps it in at runtime via :func:`set_active_provider`.

The pack itself never reads a provider API key from the environment — the key
must be passed in explicitly by the caller (the harness does this).
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable, Optional, Protocol

from activegraph_memory.tools.text_normalize import tokenize

EMBED_DIM = 64
OPENAI_EMBED_DIM = 1536  # text-embedding-3-small


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]: ...


class DeterministicEmbeddingProvider:
    """Token-hash bag-of-words embedding. Deterministic and offline."""

    dim: int = EMBED_DIM

    def __init__(self, dim: int = EMBED_DIM) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in tokenize(text):
            h = int.from_bytes(
                hashlib.blake2b(tok.encode("utf-8"), digest_size=4).digest(),
                "big",
            )
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


_DEFAULT = DeterministicEmbeddingProvider()

# Process-wide active provider. The pack's vector search uses this when no
# explicit provider is passed, so a caller can inject a real embeddings
# backend without threading it through every behavior signature.
_ACTIVE: "EmbeddingProvider" = _DEFAULT


def set_active_provider(provider: Optional["EmbeddingProvider"]) -> None:
    """Install the process-wide embedding provider (None resets to default)."""
    global _ACTIVE
    _ACTIVE = provider or _DEFAULT


def get_active_provider() -> "EmbeddingProvider":
    return _ACTIVE


def embed(text: str, provider: EmbeddingProvider | None = None) -> list[float]:
    """Convenience wrapper using the active provider by default."""
    return (provider or _ACTIVE).embed(text)


class OpenAIEmbeddingProvider:
    """Real OpenAI-compatible embeddings provider.

    Batches uncached inputs into chunked requests and caches every embedding
    by exact text for the lifetime of the instance, so repeated turn text (and
    repeated queries during fallback retrieval) are embedded at most once.

    The API key must be supplied explicitly — the pack never reads it from the
    environment. ``base_url`` is optional (omit for api.openai.com; the Replit
    AI proxy does not currently expose an embeddings endpoint).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        api_key: str,
        base_url: str | None = None,
        batch_size: int = 256,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "OpenAIEmbeddingProvider requires `pip install openai`."
            ) from e
        if not api_key:
            raise RuntimeError(
                "OpenAIEmbeddingProvider requires an explicit api_key. "
                "The pack will never read a provider key from the environment."
            )
        self.model = model
        self.batch_size = max(1, batch_size)
        self._client = (
            OpenAI(api_key=api_key, base_url=base_url)
            if base_url
            else OpenAI(api_key=api_key)
        )
        self._cache: dict[str, list[float]] = {}

    def _zero(self) -> list[float]:
        return [0.0] * OPENAI_EMBED_DIM

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        # Unique, non-empty, not-yet-cached inputs preserve insertion order.
        missing: list[str] = []
        seen: set[str] = set()
        for t in items:
            if t and t.strip() and t not in self._cache and t not in seen:
                seen.add(t)
                missing.append(t)
        for i in range(0, len(missing), self.batch_size):
            chunk = missing[i : i + self.batch_size]
            resp = self._client.embeddings.create(model=self.model, input=chunk)
            for t, d in zip(chunk, resp.data):
                self._cache[t] = list(d.embedding)
        return [self._cache.get(t, self._zero()) for t in items]


class OptionalOpenAIEmbeddingProvider(OpenAIEmbeddingProvider):
    """Backwards-compatible alias for :class:`OpenAIEmbeddingProvider`."""
