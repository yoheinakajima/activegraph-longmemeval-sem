---
name: activegraph-memory pack driver
description: Driving the frozen memory pack and tracing provenance.
---
Drive pattern: `g=Graph(); rt=Runtime(g); rt.load_pack(pack, settings=MemorySettings())`,
`g.add_object("memory_observation", {..., "metadata": {...}})`, `rt.run_until_idle()`,
then `g.add_object("memory_query", {"question":..., "mode":"standard"})`, `rt.run_until_idle()`.
Check `rt.errors == []`.

**Provenance for evidence mapping:**
- `memory_answer.data` has `used_memory_ids` (claims) and `evidence_ids` (observations); `memory_retrieval_result.data["retrieved_object_ids"]`.
- Relation `derived_from` points claim -> observation (source_id=claim, target_id=observation). Relation objects expose `source_id`/`target_id` (fall back to `source`/`target`).
- To map a retrieved memory back to source turns: if it's a `memory_observation` use it directly; else follow `derived_from` to its observations, then read `observation.data["metadata"]` for whatever you stamped (e.g. session_id/turn_index).
- Object ids look like `memory_observation#7`; the numeric suffix == insertion order == chronological if you ingest in order.
- Ingestion is deterministic/LLM-free; ingest in chronological order so supersession/recency works.
