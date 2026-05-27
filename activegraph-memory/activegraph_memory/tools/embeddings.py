"""Embedding providers.

``DeterministicEmbeddingProvider`` produces a stable hash-based embedding so
vector search works offline in tests without numpy or an API key. It is NOT
semantically meaningful — equal text in, equal vector out; different text in,
different vector out. That is enough to exercise the lifecycle.

A production user swaps in a real embeddings provider (OpenAI, local model,
etc.) at the call site.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from activegraph_memory.tools.text_normalize import tokenize

EMBED_DIM = 64


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


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


_DEFAULT = DeterministicEmbeddingProvider()


def embed(text: str, provider: EmbeddingProvider | None = None) -> list[float]:
    """Convenience wrapper using the deterministic provider by default."""
    return (provider or _DEFAULT).embed(text)


class OptionalOpenAIEmbeddingProvider:
    """Placeholder for a real OpenAI embeddings provider.

    Construction without ``openai`` installed or without an API key raises
    ``RuntimeError`` — by design, deterministic tests must not depend on this.
    """

    def __init__(self, model: str = "text-embedding-3-small", *, api_key: str | None = None) -> None:
        try:
            import openai  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "OptionalOpenAIEmbeddingProvider requires `pip install openai`."
            ) from e
        if not api_key:
            raise RuntimeError(
                "OptionalOpenAIEmbeddingProvider requires an explicit api_key. "
                "The pack will never read OPENAI_API_KEY from the environment."
            )
        self.model = model
        self._api_key = api_key

    def embed(self, text: str) -> list[float]:  # pragma: no cover — live call
        from openai import OpenAI
        client = OpenAI(api_key=self._api_key)
        resp = client.embeddings.create(model=self.model, input=text)
        return list(resp.data[0].embedding)
