# Examples

Implement all examples using current ActiveGraph APIs.

If an API is unavailable, document the limitation in the example file and keep the example as close as possible.

Store examples in: `examples/`

---

## Example 1: basic_memory_run.py

**Scenario:**
- Observation: `"Yohei prefers lowercase X posts and dislikes em dashes."`
- Query: `"How should I write Yohei's X posts?"`

**Expected:**
- Procedural memory is created
- Query retrieves procedural memory
- Answer says to use lowercase and avoid em dashes

---

## Example 2: contradiction_demo.py

**Scenario:**
- Observation 1: `"The project is called PythonFunc."`
- Observation 2: `"The project is now called BabyAGI."`

**Expected graph state:**
- Memory A: project called PythonFunc
- Memory B: project now called BabyAGI
- B supersedes A
- A is not deleted

---

## Example 3: procedural_memory_demo.py

**Scenario:**
- Observation: `"For future X posts, use lowercase and keep it casual."`
- Query: `"Draft an X post style reminder."`

**Expected:**
- Procedural memory is retrieved and used

---

## Example 4: temporal_memory_demo.py

**Scenario:**
- Observation date: `2026-05-26`
- Observation: `"Yesterday I met the founder."`

**Expected:**
- `temporal_ref` is created
- "Yesterday" is resolved relative to observation date if anchor exists

---

## Example 5: numeric_memory_demo.py

**Scenario:**
- Observation: `"Fund III target is $20–25M with around 36 investments and 25% reserves."`

**Expected:**
- `quantity_claim` objects are created
- Numbers are attached to correct owners/properties:
  - `$20–25M` → Fund III target size
  - `36` → fund construction (investments)
  - `25%` → reserves policy

---

## Example 6: fallback_retrieval_demo.py

**Scenario:**
- Query asks for a specific number
- First retrieval misses the relevant memory
- Fallback retrieval targets missing data

**Expected:**
- Fallback retrieval result links to original query
- Missing data is reduced or preserved explicitly

---

## Example 7: fork_memory_policy.py

**Purpose:** Show why ActiveGraph matters for memory.

**Scenario:**
- Same observation history
- Fork A: conservative extraction threshold
- Fork B: aggressive extraction threshold

**Expected:**
- Fork B extracts more memories
- Fork A extracts fewer
- Diff shows policy-driven difference in memory state

**Note:** This is one of the most important examples. It demonstrates the core ActiveGraph advantage — event-sourced state that can be replayed under different policies.

If exact fork/diff APIs are unavailable:
- Document the limitation
- Simulate comparison with two graph instances
- Keep interface close to future fork/diff API

---

## Example 8: memory_evaluation_demo.py

**Scenario:**
- A query retrieves memory
- An answer uses memory
- A user correction or benchmark label marks the answer partially incorrect

**Expected:**
- `memory_evaluation` object is created
- Answer is linked to evaluation
- Used memories can later be inspected

---

## Suggested README Usage Example

Use actual APIs after checking ActiveGraph docs. Conceptual shape:

```python
from activegraph import Graph, Runtime
from activegraph.packs import load_by_name
from activegraph_memory import MemorySettings

graph = Graph()
runtime = Runtime(graph)
runtime.load_pack(
    load_by_name("memory"),
    settings=MemorySettings(
        enable_semantic_memory=True,
        enable_episodic_memory=True,
        enable_procedural_memory=True,
    ),
)
graph.add_object(
    "memory_observation",
    {
        "actor": "user",
        "content": "Yohei prefers lowercase X posts and dislikes em dashes.",
        "source": "chat",
    },
)
runtime.run_until_idle()
graph.add_object(
    "memory_query",
    {
        "question": "How should I write Yohei's X posts?",
        "mode": "standard",
    },
)
runtime.run_until_idle()
answers = graph.objects(type="memory_answer")
print(answers[-1].answer)
```

**Note:** Do not commit this exact code if ActiveGraph APIs differ — update it to match real APIs.
