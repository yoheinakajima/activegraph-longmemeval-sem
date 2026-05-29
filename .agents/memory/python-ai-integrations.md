---
name: Python LLM via Replit AI integrations
description: Use Replit-managed OpenAI/Anthropic from Python despite JS-only skills.
---
The ai-integrations-openai / ai-integrations-anthropic skills are written for the TS
monorepo, but a standalone Python project can use the same proxy.

**How to apply:**
- Provision once in the JS sandbox: `setupReplitAIIntegrations({providerSlug, providerUrlEnvVarName, providerApiKeyEnvVarName})` for `openai` and `anthropic`. This sets env vars `AI_INTEGRATIONS_OPENAI_BASE_URL/API_KEY` and `AI_INTEGRATIONS_ANTHROPIC_BASE_URL/API_KEY`.
- In Python: `OpenAI(base_url=os.environ["AI_INTEGRATIONS_OPENAI_BASE_URL"], api_key=os.environ["AI_INTEGRATIONS_OPENAI_API_KEY"])`; same shape for `Anthropic`. The api_key is a dummy string — works only when BASE_URL is also set.
- Model quirks: gpt-5/o-series reject explicit `temperature` and require `max_completion_tokens` (not `max_tokens`); gpt-4o accepts both and temperature. Anthropic claude-opus-4-7 deprecates `temperature`. gpt-4o judge resolves to a pinned snapshot (e.g. gpt-4o-2024-11-20) returned in `response.model`.
- Never ask the user for keys; never write the key to files.
