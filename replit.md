# activegraph-memory

An ActiveGraph-native memory lifecycle pack. Treats memory as state evolution — not just retrieval — tracking what was observed, extracted, supported, contradicted, retrieved, used, and evaluated, all as graph state backed by an event-sourced log.

---

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

For the Python package (`activegraph_memory`):
- `pip install -e .` — install package in editable mode (run from `activegraph-memory/`)
- `pytest` — run all tests (must pass offline, no API keys, no network)

---

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)
- Python package: `activegraph_memory` (ActiveGraph pack)

---

## Where things live

- `docs/brief/` — all reference documents broken out from the original developer brief
- `todo.md` — full task checklist from start to completion
- `activegraph-memory/` — the Python repository to be created (see brief docs)
- `attached_assets/` — original source brief (do not edit)

---

## Reference Documents

Read these when working on specific aspects of the implementation. Each document is self-contained.

| Document | When to read |
|---|---|
| [`docs/brief/overview.md`](docs/brief/overview.md) | Start here — mission, architecture, naming, design philosophy, non-goals, determinism rules, coding style |
| [`docs/brief/repository_structure.md`](docs/brief/repository_structure.md) | When scaffolding the repo — full directory tree for `activegraph-memory/` |
| [`docs/brief/object_types.md`](docs/brief/object_types.md) | When implementing `types.py` — all 13 object types with complete Pydantic schemas and rules |
| [`docs/brief/relation_types.md`](docs/brief/relation_types.md) | When implementing `relations.py` — all 14 relation types with examples |
| [`docs/brief/behaviors.md`](docs/brief/behaviors.md) | When implementing any behavior — all 11 behaviors with triggers, logic, and rules |
| [`docs/brief/prompts.md`](docs/brief/prompts.md) | When writing prompt files — all 8 prompts with required rules and output fields |
| [`docs/brief/tools_and_settings.md`](docs/brief/tools_and_settings.md) | When implementing tools or settings — all 5 tools, full MemorySettings schema, fixture file list |
| [`docs/brief/examples.md`](docs/brief/examples.md) | When writing examples — all 8 example scenarios with expected graph state |
| [`docs/brief/tests.md`](docs/brief/tests.md) | When writing tests — all 17 test files with specific assertions |
| [`docs/brief/development_phases.md`](docs/brief/development_phases.md) | When planning or executing a phase — all 15 phases (0–14) plus benchmark harness (Phase 15) with per-phase requirements |
| [`docs/brief/acceptance_criteria.md`](docs/brief/acceptance_criteria.md) | When verifying completion — full checklist across packaging, integration, lifecycle, advanced memory, fork/diff, tests, docs, quality |
| [`docs/brief/readme_requirements.md`](docs/brief/readme_requirements.md) | When writing the README — required sections, lifecycle diagram, usage example |

---

## Todo

See [`todo.md`](todo.md) for the complete task checklist organized by phase.

---

## Architecture decisions

- The Python package (`activegraph_memory`) is an ActiveGraph-native pack — graph objects and behaviors are the core, not a MemoryEngine wrapper
- All behavior bodies must be deterministic: no `datetime.now()`, `uuid.uuid4()`, `random.random()`, or direct LLM/network calls
- Tests must pass fully offline with no API keys and no external services
- Memory is never stored as an isolated string — every memory object carries lineage back to its source observation
- GitHub connection is handled separately — do not implement it here

---

## Product

An installable Python pack (`memory`) for the ActiveGraph framework that makes memory a first-class lifecycle capability: observation ingestion, semantic/episodic/procedural extraction, evidence linkage, retrieval planning, answer generation, contradiction detection, temporal grounding, numeric attribution, consolidation, forgetting/archival, usage evaluation, and fork/diff policy comparison.

---

## User preferences

- GitHub connection is the user's responsibility — skip any GitHub-related tasks
- Complete implementation with minimal stopping

---

## Gotchas

- Before finalizing `pyproject.toml`, confirm the exact entry point group name from ActiveGraph source code (it may differ from `"activegraph.packs"`)
- If docs and ActiveGraph code disagree, prefer code
- Do not build convenience APIs (`observe_memory`, `query_memory`) until the pack itself is working
- Do not claim benchmark performance until benchmarks are actually run
- `occurred_at` ≠ `observed_at` — never conflate them
- Vector search is optional; keyword search is required for Phase 4

---

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
- Original brief: `attached_assets/Pasted-Developer-Brief-Build-activegraph-memory-as-an-ActiveGr_1779857295549.txt`
