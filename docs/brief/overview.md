# Overview: activegraph-memory

## Mission

Create a repository called `activegraph-memory` that implements an installable ActiveGraph pack named `memory`.

The goal is **not** to build another standalone vector-memory library. The goal is to build an **ActiveGraph-native memory lifecycle system** where memory is represented as graph state, updated by behaviors, grounded in evidence, and backed by event-sourced lineage.

### Core Thesis

Memory is not just retrieval. Memory is **state evolution**.

A memory system should track:
- what was observed
- what was extracted
- what evidence supports it
- what changed
- what conflicted
- what was superseded
- what was retrieved
- what was used
- whether it helped

---

## Architectural Direction

Build this as an **ActiveGraph pack first**.

Primary architecture:
```
ActiveGraph graph
→ memory objects
→ typed memory relations
→ behaviors that update memory state
→ event log as source of truth
→ retrieval, answer, evaluation, and policy comparison derived from graph state
```

Avoid making the package primarily:
```
MemoryEngine
→ external memory database
→ optional ActiveGraph adapter
```

A small convenience wrapper may be added later, but it should sit on top of graph objects and behaviors — it must not become the core architecture. ActiveGraph should remain the substrate.

---

## Naming

| Item | Name |
|---|---|
| Repository | `activegraph-memory` |
| Python Package | `activegraph_memory` |
| ActiveGraph Pack | `memory` |

### Import Shape

Preferred user-facing import:
```python
from activegraph_memory import pack
```

Optional later convenience import (do not build until pack works):
```python
from activegraph_memory import observe_memory, query_memory
```

---

## Pack Entry Point

In `pyproject.toml`, include the current ActiveGraph equivalent of:
```toml
[project.entry-points."activegraph.packs"]
memory = "activegraph_memory:pack"
```

Confirm the exact entry point group from current ActiveGraph code/docs before finalizing.

---

## Design Philosophy

The package should demonstrate that memory is not a passive storage layer.

**Memory lifecycle:**
```
observed → extracted → supported → indexed → retrieved → used →
evaluated → updated → contradicted → superseded → consolidated → forgotten/archived
```

**ActiveGraph should make this lifecycle:**
- inspectable
- replayable
- forkable
- diffable
- auditable
- behavior-driven
- evidence-linked

Favor **explicit graph structure** over hidden prompt behavior. Prompts can help extract and reason, but graph objects and relations should preserve the memory state.

---

## Core Product Requirements

The pack must support:

1. Observation ingestion
2. Semantic memory extraction
3. Episodic memory extraction
4. Procedural memory extraction
5. Evidence linkage
6. Memory retrieval
7. Answer generation from retrieved memory
8. Contradiction detection
9. Supersession handling
10. Retrieval planning
11. Fallback retrieval
12. Temporal grounding
13. Numeric attribution
14. Memory consolidation
15. Explicit forgetting/archive behavior
16. Memory usage evaluation
17. Fork/diff comparison of memory policies

---

## Required Research Before Coding

Before writing implementation code, inspect the current ActiveGraph repository and docs.

Read at minimum:
- ActiveGraph README
- ActiveGraph pack docs
- ActiveGraph behavior docs
- ActiveGraph LLM behavior docs
- ActiveGraph tool docs
- ActiveGraph event log docs
- ActiveGraph object/relation schema docs
- ActiveGraph prompt docs
- ActiveGraph settings docs
- ActiveGraph fork/diff docs
- Existing first-party or example packs
- Existing tests for packs, behaviors, tools, prompts, fork/diff

Use the actual current ActiveGraph APIs. Do not invent APIs if equivalents already exist.

If docs and code disagree, prefer code. If APIs are unclear, inspect tests and examples. If a feature is unavailable or unstable, document the limitation and implement the closest idiomatic version.

Create a short implementation note at `docs/activegraph_native_design.md` summarizing:
- exact pack API used
- exact behavior API used
- exact LLM behavior API used
- exact tool API used
- exact prompt loading API used
- exact settings API used
- exact fork/diff API used, if available
- any gaps or assumptions

---

## Non-Goals

- Do not build a chat UI
- Do not build a FastAPI server unless needed for examples later
- Do not require FAISS
- Do not require LangGraph
- Do not require OpenAI API keys for tests
- Do not require live model calls for tests
- Do not require live web calls for tests
- Do not build a full production memory service
- Do not optimize retrieval before graph lifecycle is correct
- Do not claim benchmark performance before benchmarks are run
- Do not make this a generic memory DB with ActiveGraph sprinkled on top

---

## Coding Style

- Simple, readable Python
- Prefer explicit names
- Prefer small modules
- Prefer typed models
- Prefer deterministic tests
- Avoid clever abstractions
- Avoid premature optimization
- Keep behavior responsibilities narrow
- Make graph state easy to inspect
- Make examples easy to run

---

## Determinism Rules

**Forbidden inside deterministic behavior bodies:**
- `datetime.now()`
- `uuid.uuid4()`
- `random.random()`
- `requests.get(...)`
- `openai.chat.completions.create(...)`
- file writes
- database writes outside ActiveGraph APIs

**Use instead:**
- framework-provided event timestamps
- framework-provided IDs
- framework tools
- framework LLM behaviors
- fixture providers in tests

Tests must not require live network or live model calls.

---

## ActiveGraph-Native Model

The event log is the source of truth.

Graph objects represent projected memory state.

Relations represent evidence, support, contradiction, retrieval, usage, and lifecycle links.

Behaviors update the graph in response to events.

A memory should never appear as an isolated string in a store with no provenance.

Every memory should be able to answer:
- Where did this come from?
- What evidence supports it?
- What older memory did it update or supersede?
- What conflicts with it?
- When was it retrieved?
- When was it used?
- Did it affect an answer?
- Was that answer later evaluated?
