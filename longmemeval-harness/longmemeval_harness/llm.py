"""LLM client wrappers over the Replit-managed AI integrations.

Both providers are reached through the integration proxy using env vars
that are provisioned by the platform (never asked from the user):

    AI_INTEGRATIONS_OPENAI_BASE_URL / AI_INTEGRATIONS_OPENAI_API_KEY
    AI_INTEGRATIONS_ANTHROPIC_BASE_URL / AI_INTEGRATIONS_ANTHROPIC_API_KEY

The client is lazy (SDKs and env vars are only touched on first use) so
the deterministic parts of the harness can run/import with no keys.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResult:
    text: str
    provider: str
    requested_model: str
    resolved_model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: Optional[str]


class LLMError(RuntimeError):
    pass


def _missing(*names: str) -> list[str]:
    return [n for n in names if not os.environ.get(n)]


class LLMClient:
    """Thin retrying wrapper around the OpenAI and Anthropic SDKs."""

    def __init__(self, retries: int = 5, base_delay: float = 2.0):
        self.retries = retries
        self.base_delay = base_delay
        self._openai = None
        self._anthropic = None

    def _openai_client(self):
        if self._openai is None:
            miss = _missing(
                "AI_INTEGRATIONS_OPENAI_BASE_URL",
                "AI_INTEGRATIONS_OPENAI_API_KEY",
            )
            if miss:
                raise LLMError(f"OpenAI integration env vars missing: {miss}")
            from openai import OpenAI

            self._openai = OpenAI(
                base_url=os.environ["AI_INTEGRATIONS_OPENAI_BASE_URL"],
                api_key=os.environ["AI_INTEGRATIONS_OPENAI_API_KEY"],
            )
        return self._openai

    def _anthropic_client(self):
        if self._anthropic is None:
            miss = _missing(
                "AI_INTEGRATIONS_ANTHROPIC_BASE_URL",
                "AI_INTEGRATIONS_ANTHROPIC_API_KEY",
            )
            if miss:
                raise LLMError(f"Anthropic integration env vars missing: {miss}")
            from anthropic import Anthropic

            self._anthropic = Anthropic(
                base_url=os.environ["AI_INTEGRATIONS_ANTHROPIC_BASE_URL"],
                api_key=os.environ["AI_INTEGRATIONS_ANTHROPIC_API_KEY"],
            )
        return self._anthropic

    def complete(
        self,
        provider: str,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResult:
        last: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                if provider == "openai":
                    return self._openai_complete(
                        model, system, user, temperature, max_tokens
                    )
                if provider == "anthropic":
                    return self._anthropic_complete(
                        model, system, user, temperature, max_tokens
                    )
                raise LLMError(f"unknown provider {provider!r}")
            except LLMError:
                raise
            except Exception as exc:  # noqa: BLE001 - transient API errors
                last = exc
                if attempt < self.retries - 1:
                    time.sleep(self.base_delay * (2**attempt))
        raise LLMError(f"LLM call failed after {self.retries} attempts: {last}")

    def _openai_complete(self, model, system, user, temperature, max_tokens):
        kwargs = dict(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=max_tokens,
        )
        # gpt-5 / o-series do not accept an explicit temperature.
        if not (model.startswith("gpt-5") or model.startswith("o")):
            kwargs["temperature"] = temperature
        r = self._openai_client().chat.completions.create(**kwargs)
        u = r.usage
        return LLMResult(
            text=(r.choices[0].message.content or ""),
            provider="openai",
            requested_model=model,
            resolved_model=getattr(r, "model", model) or model,
            prompt_tokens=getattr(u, "prompt_tokens", 0),
            completion_tokens=getattr(u, "completion_tokens", 0),
            total_tokens=getattr(u, "total_tokens", 0),
            finish_reason=r.choices[0].finish_reason,
        )

    def _anthropic_complete(self, model, system, user, temperature, max_tokens):
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # temperature is deprecated on claude-opus-4-7.
        if not model.startswith("claude-opus-4-7"):
            kwargs["temperature"] = temperature
        m = self._anthropic_client().messages.create(**kwargs)
        text = "".join(
            b.text for b in m.content if getattr(b, "type", None) == "text"
        )
        u = m.usage
        in_tok = getattr(u, "input_tokens", 0)
        out_tok = getattr(u, "output_tokens", 0)
        return LLMResult(
            text=text,
            provider="anthropic",
            requested_model=model,
            resolved_model=getattr(m, "model", model) or model,
            prompt_tokens=in_tok,
            completion_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            finish_reason=getattr(m, "stop_reason", None),
        )
