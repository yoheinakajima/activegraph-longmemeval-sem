"""Shared constants for the memory pack."""

from __future__ import annotations

MEMORY_TYPES = ("memory_claim", "episodic_memory", "procedural_memory")

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_ARCHIVED = "archived"
STATUS_DELETED = "deleted"
STATUS_NEEDS_REVIEW = "needs_review"

ALL_STATUSES = (
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    STATUS_ARCHIVED,
    STATUS_DELETED,
    STATUS_NEEDS_REVIEW,
)

EXCLUDED_FROM_STANDARD_RETRIEVAL = (
    STATUS_ARCHIVED,
    STATUS_DELETED,
)

PROCEDURAL_CUES = (
    "use ",
    "prefer ",
    "always ",
    "never ",
    "avoid ",
    "for future",
    "should ",
    "don't ",
    "do not ",
    "keep it ",
    "make sure",
)

EPISODIC_CUES = (
    "yesterday",
    "today",
    "last week",
    "last month",
    " met ",
    " decided ",
    " happened ",
    " announced ",
    " signed ",
    " released ",
    " launched ",
    " on may",
    " on june",
    " on jan",
    " in q1",
    " in q2",
    " in q3",
    " in q4",
)
