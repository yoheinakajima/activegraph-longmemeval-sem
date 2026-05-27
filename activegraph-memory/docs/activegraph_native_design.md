# activegraph-native design notes

This document records exactly which ActiveGraph APIs the `memory` pack uses,
and the few places we made pragmatic choices because the brief allowed
"the closest idiomatic version" when a feature would otherwise force live
network or live model calls.

ActiveGraph version targeted: **1.0.5.post2** (PyPI).

---

## Pack API

```python
from activegraph.packs import Pack, load_prompts_from_dir, ObjectType, RelationType

pack = Pack(
    name="memory",
    version="0.1.0",
    object_types=(...),
    relation_types=(...),
    behaviors=(...),
    tools=(...),
    prompts=load_prompts_from_dir(PROMPTS_DIR),
    settings_schema=MemorySettings,
)
```

`Pack` is a frozen dataclass with equality by `(name, version)`. All
collections are stored as tuples (the constructor coerces). The pack is
exposed via the entry point group `activegraph.packs`:

```toml
[project.entry-points."activegraph.packs"]
memory = "activegraph_memory:pack"
```

This is the exact group name ActiveGraph 1.0.5.post2 scans in
`activegraph.packs.loader`. It is confirmed by inspecting
`activegraph.packs.discover()` and matches the scaffold template shipped
with the framework (`activegraph.packs.scaffold`).

## Object and Relation Types

```python
ObjectType(name=..., schema=PydanticModel, description=...)
RelationType(name=..., source_types=(...), target_types=(...), description=...)
```

`source_types` and `target_types` are tuples of object-type names. The pack
loader validates that every relation a behavior creates respects the
declared source/target lists, so it pays to enumerate honestly. We do that
for all 12 relations in `relations.py`.

The brief mentions two additional relations (`about_entity`,
`same_entity_as`) — both depend on a generic entity object type that
ActiveGraph 1.0.5 does not provide. Per the brief's "defer if entity model
is not available" note, these are not registered. A future version of the
pack can add them once an entity object type is introduced (either upstream
or as a sibling pack).

## Behavior API

We use pack-aware decorators imported from `activegraph.packs` so behaviors
do not register on the global registry (CONTRACT v0.9 #3):

```python
from activegraph.packs import behavior

@behavior(
    name="extract_candidate_memories",
    on=["object.created"],
    where={"object.type": "memory_observation"},
    creates=["memory_claim", "episodic_memory", "procedural_memory"],
)
def extract_candidate_memories(event, graph, ctx, *, settings: MemorySettings):
    ...
```

Behavior signature is `(event, graph, ctx)` plus typed-keyword settings
injection (CONTRACT v0.9 #7 Form 1). Settings are resolved from the active
runtime's `load_pack(pack, settings=...)` call; an instance with all
defaults is used when none was passed.

`where=` supports single-value equality only. The brief specifies several
behaviors as triggering on multiple object types
(`object.type in [memory_claim, episodic_memory, procedural_memory]`). Two
options were considered:
1. Drop `where=` and filter inside the body with an early return.
2. Register the behavior once per type with the same body.

We chose option 2 (one behavior per type, same body) so the trigger
remains visible in the registered behavior list, which is friendlier to
inspection tools (`runtime.print_graph`, trace UIs, etc.).

## LLM Behavior API (deferred)

ActiveGraph exposes `@llm_behavior(...)` and ships
`RecordedLLMProvider` / `RecordingLLMProvider` for fixture-driven offline
tests. The brief is explicit that **tests must be deterministic, offline,
and require no API keys** (`docs/brief/tests.md`, "Determinism Rules" in
`docs/brief/overview.md`).

To satisfy that constraint without committing brittle prompt-hash fixtures
on day one, all v0.1 behaviors are plain `@behavior` (deterministic) with
heuristic extraction. The prompts in `prompts/*.md` describe the contract
exactly as an `@llm_behavior` would, and the I/O shapes the heuristics
produce match what an LLM-backed swap would emit — so swapping
`@behavior` for `@llm_behavior(prompt_template="…", output_schema=…)` is
mechanical, no schema changes required.

Recommended swap-in shape for a future LLM-backed behavior:

```python
from activegraph.packs import llm_behavior
from pydantic import BaseModel

class Extraction(BaseModel):
    memory_type: Literal["semantic", "episodic", "procedural"]
    content: str
    confidence: float

@llm_behavior(
    name="extract_candidate_memories",
    on=["object.created"],
    where={"object.type": "memory_observation"},
    output_schema=Extraction,
    deterministic=True,
)
def extract(event, graph, ctx, out: Extraction, *, settings: MemorySettings):
    ...
```

## Tool API

```python
from activegraph.packs import tool

@tool(
    name="keyword_search",
    input_schema=KeywordSearchInput,
    output_schema=KeywordSearchOutput,
    deterministic=True,
)
def keyword_search(args, ctx) -> KeywordSearchOutput: ...
```

Two tools are registered: `keyword_search` and `vector_search`. Both are
deterministic and offline. Internally, behaviors call the plain helper
functions (`keyword_search_fn`, `vector_search_fn`) rather than going
through the runtime's tool dispatcher — that path is reserved for
LLM-driven calls where the model is choosing tools.

The vector tool uses `DeterministicEmbeddingProvider` (a token-hash
bag-of-words) so vector retrieval works offline. A production user passes
a real `EmbeddingProvider` to `vector_search_fn(..., provider=)`.

## Prompt API

```python
from activegraph.packs import load_prompts_from_dir
prompts = load_prompts_from_dir(Path(__file__).parent / "prompts")
```

Each prompt file is a Markdown file with a TOML frontmatter `version`
field. The loader scans the directory, hashes each file's body, and returns
a tuple of `PackPrompt(name, version, body, content_hash)`. The pack
loader's prompt resolver matches a prompt to a behavior by name when an
`@llm_behavior` is registered with the same `name=`.

## Settings API

```python
class MemorySettings(BaseModel):
    enable_semantic_memory: bool = True
    ...
```

A Pydantic model with all-default fields. Behaviors access settings via
typed keyword injection: `def my_behavior(event, graph, ctx, *,
settings: MemorySettings): ...`. Two other access forms are documented in
ActiveGraph (`ctx.settings`, `ctx.pack_settings("memory")`); we did not
need them.

## Runtime API

```python
from activegraph import Graph, Runtime
from activegraph.packs import load_by_name

rt = Runtime(Graph())
rt.load_pack(load_by_name("memory"), settings=MemorySettings(...))

graph.add_object("memory_observation", {...})
rt.run_until_idle()
```

The runtime drives behaviors off the event queue until quiescent. The
event log is the source of truth — graph state is projection. Every
`add_object` / `add_relation` / `patch_object` call emits exactly one
event; replay reconstructs identical state.

## Fork / Diff API

ActiveGraph exposes `runtime.fork()` and `runtime.diff(other)` returning
`Diff(DivergentObject(...), DivergentRelation(...))`. The fork demo
(`examples/fork_memory_policy.py`) uses these directly to compare two
memory policies over the same observation prefix.

When `fork()` is unavailable (older ActiveGraph), the demo falls back to
constructing two `Runtime(Graph())` instances and ingesting the same
events into both — the comparison is by-hand object/relation diff. The
example file documents both modes.

## Gaps and Pragmatic Choices

| Area | Gap | Choice |
|---|---|---|
| LLM behaviors | Need a provider and recorded fixtures keyed by prompt SHA | All v0.1 behaviors are deterministic `@behavior`; prompts ship for the eventual swap. |
| Multi-type `where=` | No `in [...]` support | Register one behavior per type with the same body. |
| Entity objects | No generic `entity` type upstream | `about_entity` and `same_entity_as` not registered. |
| Vector embeddings | No bundled offline provider | `DeterministicEmbeddingProvider` (hash bag-of-words) for tests. |
| Answer generation | Real LLM would compose better prose | Deterministic concat of procedural + semantic/episodic content. |
