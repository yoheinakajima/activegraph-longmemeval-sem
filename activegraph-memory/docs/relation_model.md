# relation model

Twelve relation types live in `activegraph_memory/relations.py`. Each
declares `source_types` and `target_types` so the runtime can refuse
out-of-spec edges at write time.

| relation             | source                                              | target                              | meaning                                                       |
|----------------------|-----------------------------------------------------|-------------------------------------|---------------------------------------------------------------|
| `derived_from`       | memory_claim / episodic_memory / procedural_memory  | memory_observation                  | "this memory was extracted from that observation"             |
| `supports`           | memory_observation                                  | memory_claim / episodic / procedural| reverse of `derived_from`, eases retrieval                    |
| `contradicts`        | memory                                              | memory (same type)                  | new memory disagrees with the older one                        |
| `supersedes`         | memory                                              | memory (same type)                  | new memory replaces the older one                              |
| `retrieved_for`      | memory                                              | memory_query / memory_retrieval_result | "this memory was returned for this query"                  |
| `used_in_answer`     | memory                                              | memory_answer                       | "the answer actually used this memory"                         |
| `has_quantity`       | memory_claim / episodic_memory / memory_observation | quantity_claim                      | scoped numeric fact attached to a memory                       |
| `has_temporal_ref`   | memory_claim / episodic_memory / memory_observation | temporal_ref                        | resolved or unresolved time reference                          |
| `validated_by`       | memory_answer                                       | memory_evaluation                   | the answer was confirmed by an evaluation                      |
| `invalidated_by`     | memory_answer                                       | memory_evaluation                   | the answer was rejected by an evaluation                       |
| `consolidated_into`  | memory                                              | memory_consolidation                | older memory was rolled into a consolidation marker            |
| `governed_by_policy` | any                                                 | memory_policy                       | operation was governed by a named policy                       |

`about_entity` and `same_entity_as` are described in
`docs/roadmap.md`; they require a first-class `entity` object type
that lives outside the memory pack.
