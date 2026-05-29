"""Deterministic stratified sampling over question types.

Given the full set of instances and a target size, produce a fixed,
reproducible id set (seed=42) that is representative across all question
types (including the abstention variants). Sampling is stratified by
``question_type`` using proportional allocation with largest-remainder
rounding, so each tier mirrors the dataset's type distribution.
"""

from __future__ import annotations

import random
from collections import defaultdict

from .config import SAMPLE_SEED
from .dataset import Instance


def stratified_sample(
    instances: list[Instance], size: int, seed: int = SAMPLE_SEED
) -> list[str]:
    """Return a sorted list of ``question_id`` of length ``min(size, N)``.

    Deterministic for a fixed (instances, size, seed): groups by question
    type, shuffles each group with a seeded RNG, allocates per-type counts
    proportional to type frequency (largest remainder), and takes the head
    of each shuffled group.
    """
    total = len(instances)
    if size >= total:
        return sorted(i.question_id for i in instances)

    groups: dict[str, list[str]] = defaultdict(list)
    for inst in instances:
        groups[inst.question_type].append(inst.question_id)

    # Stable, seeded shuffle within each type.
    rng = random.Random(seed)
    for qtype in sorted(groups):
        ids = sorted(groups[qtype])  # stable base order
        rng.shuffle(ids)
        groups[qtype] = ids

    # Largest-remainder proportional allocation.
    exact = {qt: size * len(ids) / total for qt, ids in groups.items()}
    alloc = {qt: int(v) for qt, v in exact.items()}
    remainder = size - sum(alloc.values())
    order = sorted(
        groups, key=lambda qt: (exact[qt] - alloc[qt], qt), reverse=True
    )
    for qt in order[:remainder]:
        alloc[qt] += 1

    # Clamp to availability (can't take more than a type has).
    chosen: list[str] = []
    for qt in sorted(groups):
        k = min(alloc[qt], len(groups[qt]))
        chosen.extend(groups[qt][:k])

    return sorted(chosen)
