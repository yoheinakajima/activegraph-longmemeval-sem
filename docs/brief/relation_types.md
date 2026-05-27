# Relation Types

Implement all relation types using the current ActiveGraph relation type API.

---

## 1. derived_from

Connects extracted memory to the observation it came from.

```
(memory_claim)-[:derived_from]->(memory_observation)
(episodic_memory)-[:derived_from]->(memory_observation)
(procedural_memory)-[:derived_from]->(memory_observation)
```

---

## 2. supports

Connects evidence to a claim or answer.

```
(memory_observation)-[:supports]->(memory_claim)
(memory_claim)-[:supports]->(memory_answer)
(episodic_memory)-[:supports]->(memory_answer)
```

---

## 3. contradicts

Connects two incompatible memories.

```
(memory_claim)-[:contradicts]->(memory_claim)
(procedural_memory)-[:contradicts]->(procedural_memory)
```

---

## 4. supersedes

Connects a newer memory to an older memory it replaces.

```
(new_memory_claim)-[:supersedes]->(old_memory_claim)
(new_procedural_memory)-[:supersedes]->(old_procedural_memory)
```

---

## 5. retrieved_for

Connects retrieved memories to a query or retrieval result.

```
(memory_claim)-[:retrieved_for]->(memory_query)
(memory_claim)-[:retrieved_for]->(memory_retrieval_result)
(procedural_memory)-[:retrieved_for]->(memory_retrieval_result)
```

---

## 6. used_in_answer

Connects memories actually used in an answer.

```
(memory_claim)-[:used_in_answer]->(memory_answer)
(procedural_memory)-[:used_in_answer]->(memory_answer)
```

---

## 7. has_quantity

Connects a memory to a numeric claim.

```
(memory_claim)-[:has_quantity]->(quantity_claim)
```

---

## 8. has_temporal_ref

Connects a memory to a temporal reference.

```
(episodic_memory)-[:has_temporal_ref]->(temporal_ref)
(memory_claim)-[:has_temporal_ref]->(temporal_ref)
```

---

## 9. about_entity

Connects memory to an entity object if ActiveGraph has a generic entity object type available.

**Note:** Defer this relation if ActiveGraph does not have generic entity objects.

```
(memory_claim)-[:about_entity]->(entity)
```

---

## 10. same_entity_as

Connects two entity-like references judged to refer to the same thing.

**Note:** Defer if entity model is not available.

---

## 11. validated_by

Connects a memory or answer to an evaluation that validates it.

```
(memory_answer)-[:validated_by]->(memory_evaluation)
```

---

## 12. invalidated_by

Connects a memory or answer to an evaluation that invalidates it.

```
(memory_answer)-[:invalidated_by]->(memory_evaluation)
(memory_claim)-[:invalidated_by]->(memory_evaluation)
```

---

## 13. consolidated_into

Connects older duplicate/overlapping memories to a consolidated memory.

```
(memory_claim)-[:consolidated_into]->(memory_claim)
```

---

## 14. governed_by_policy

Connects memory operations or outputs to the policy that governed them.

```
(memory_claim)-[:governed_by_policy]->(memory_policy)
(memory_retrieval_result)-[:governed_by_policy]->(memory_policy)
(memory_answer)-[:governed_by_policy]->(memory_policy)
```
