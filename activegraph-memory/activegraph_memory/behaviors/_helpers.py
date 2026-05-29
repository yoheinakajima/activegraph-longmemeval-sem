"""Shared helpers for memory pack behaviors.

Pure functions — no graph mutation, no clock, no network.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

from activegraph_memory.constants import (
    EPISODIC_CUES,
    MEMORY_TYPES,
    PROCEDURAL_CUES,
    STATUS_ACTIVE,
)
from activegraph_memory.tools.text_normalize import extract_keywords, normalize, tokenize

# ---------------------------------------------------------------- classification


def classify_observation(text: str) -> str:
    """Return one of: 'procedural', 'episodic', 'semantic'."""
    if not text:
        return "semantic"
    low = " " + text.lower() + " "
    if any(c in low for c in PROCEDURAL_CUES):
        return "procedural"
    if any(c in low for c in EPISODIC_CUES):
        return "episodic"
    return "semantic"


# ---------------------------------------------------------------- query routing


_DEEP_HINTS = (
    "when", "timeline", "history", "list all", "every", "how many",
    "how much", "since", "before", "after", "compare", "contradict",
    "changed", "date", "dates", "year", "month",
)


def query_mode(question: str) -> str:
    low = (question or "").lower()
    if any(h in low for h in _DEEP_HINTS):
        return "deep"
    # numbers in question -> deep
    if re.search(r"\d", low):
        return "deep"
    return "standard"


def detect_required_data(question: str) -> list[str]:
    """Heuristic: when a query asks for specifics, flag the kind of evidence
    the answerer should look for. The fallback retriever uses this list."""
    low = (question or "").lower()
    req: list[str] = []
    if re.search(r"\b(how much|how many|what is the|what's the)\b.*\b(amount|number|target|size|count|percent|percentage|\$|%)", low):
        req.append("numeric_value")
    if re.search(r"\b(when|what date|what time)\b", low):
        req.append("temporal_value")
    if "why" in low.split():
        req.append("reason")
    return req


# ---------------------------------------------------------------- subject keying


_LEADING_MARKERS = {
    "update", "updated", "actually", "correction", "note", "fyi",
    "btw", "so", "well", "okay", "ok", "now", "today", "yesterday",
    "edit", "fix",
}


def subject_key(text: str, *, n_tokens: int = 2) -> str:
    """A stable key for grouping memories about the same subject.

    Strips common conversational markers ("update", "actually", "now", ...)
    anywhere in the prefix so that "Yohei lives in Tokyo" and
    "Update: Yohei now lives in SF" key the same way.
    """
    toks = [t for t in tokenize(text) if t and t not in _LEADING_MARKERS]
    return " ".join(toks[:n_tokens])


_SUPERSEDE_CUES = (" now ", " now,", "now called", " changed to ", " renamed ",
                   " actually ", " correction", " correction:", " updated to ",
                   " is now ", " was renamed")


def text_signals_supersession(new_text: str) -> bool:
    low = " " + (new_text or "").lower() + " "
    return any(c in low for c in _SUPERSEDE_CUES)


# ---------------------------------------------------------------- temporal


_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december",
           "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
           "oct", "nov", "dec")
_RELATIVE = {
    "today": 0, "yesterday": -1, "tomorrow": 1,
    "last week": -7, "next week": 7,
    "a week ago": -7, "an hour ago": 0, "the other day": -1,
}

# "two weeks ago", "3 days ago", "a month ago", "last month", "last year".
_AGO_RE = re.compile(
    r"\b(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(day|week|month|year)s?\s+ago\b",
    re.IGNORECASE,
)
_LAST_NEXT_RE = re.compile(
    r"\b(last|next)\s+(month|year)\b", re.IGNORECASE
)
# Ongoing duration: "for six weeks now", "for about three months". Resolves to
# the START of the activity (anchor - N units) so the reader can compute how
# long an activity had been going at the time of a later dated event.
_DURATION_RE = re.compile(
    r"\bfor\s+(?:about\s+|around\s+|almost\s+|over\s+|nearly\s+)?"
    r"(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(day|week|month|year)s?\b",
    re.IGNORECASE,
)


def find_temporal_refs(text: str) -> list[dict[str, Any]]:
    """Return raw mentions: [{'text': ..., 'kind': 'iso'|'month'|'relative'}]."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(t: str, kind: str) -> None:
        key = (t.lower(), kind)
        if key not in seen:
            seen.add(key)
            found.append({"text": t, "kind": kind})

    low = (text or "").lower()
    for m in _DATE_ISO.finditer(text or ""):
        _add(m.group(0), "iso")
    # Spans consumed by the richer "N units ago" / "last month" patterns so the
    # fixed-phrase loop below does not double-count (e.g. "a week ago").
    for m in _AGO_RE.finditer(text or ""):
        _add(m.group(0), "relative")
    for m in _LAST_NEXT_RE.finditer(text or ""):
        _add(m.group(0), "relative")
    for m in _DURATION_RE.finditer(text or ""):
        _add(m.group(0), "duration")
    for phrase in _RELATIVE:
        if phrase in low:
            _add(phrase, "relative")
    # Month-day style: "May 26", "may 26"
    month_re = re.compile(
        r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\b",
        re.IGNORECASE,
    )
    for m in month_re.finditer(text or ""):
        _add(m.group(0), "month_day")
    return found


_WORD_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
              "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _shift_months(dt: datetime, months: int) -> datetime:
    """Add (or subtract) calendar months, clamping the day to month length."""
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    # last valid day of the target month
    if month == 12:
        nxt = datetime(year + 1, 1, 1)
    else:
        nxt = datetime(year, month + 1, 1)
    last_day = (nxt - timedelta(days=1)).day
    return dt.replace(year=year, month=month, day=min(dt.day, last_day))


def _parse_qty(qty_raw: str) -> Optional[int]:
    n = _WORD_NUMS.get(qty_raw, None)
    if n is None:
        try:
            n = int(qty_raw)
        except ValueError:
            n = None
    return n


def _subtract_units(anchor: datetime, n: int, unit: str) -> Optional[datetime]:
    if unit == "day":
        return anchor - timedelta(days=n)
    if unit == "week":
        return anchor - timedelta(weeks=n)
    if unit == "month":
        return _shift_months(anchor, -n)
    if unit == "year":
        return _shift_months(anchor, -12 * n)
    return None


def _resolve_duration_start(low: str, anchor: datetime) -> Optional[datetime]:
    """Resolve an ongoing-duration phrase ("for six weeks") to the activity's
    start date (anchor - N units)."""
    m = _DURATION_RE.match(low) or _DURATION_RE.search(low)
    if not m:
        return None
    n = _parse_qty(m.group(1).lower())
    if n is None:
        return None
    return _subtract_units(anchor, n, m.group(2).lower())


def _resolve_relative(low: str, anchor: datetime) -> Optional[datetime]:
    """Resolve a lowercased relative phrase against ``anchor``. Returns None
    when the phrase carries no usable offset."""
    if low in _RELATIVE:
        return anchor + timedelta(days=_RELATIVE[low])
    m = _AGO_RE.match(low) or _AGO_RE.search(low)
    if m:
        n = _parse_qty(m.group(1).lower())
        if n is not None:
            resolved = _subtract_units(anchor, n, m.group(2).lower())
            if resolved is not None:
                return resolved
    m = _LAST_NEXT_RE.match(low) or _LAST_NEXT_RE.search(low)
    if m:
        direction, unit = m.group(1).lower(), m.group(2).lower()
        sign = -1 if direction == "last" else 1
        if unit == "month":
            return _shift_months(anchor, sign)
        if unit == "year":
            return _shift_months(anchor, sign * 12)
    return None


def resolve_temporal(mention: dict[str, Any],
                     anchor: Optional[datetime]) -> dict[str, Any]:
    """Try to resolve a mention against an anchor datetime."""
    kind = mention["kind"]
    text = mention["text"]
    if kind == "iso":
        try:
            y, mo, d = map(int, text.split("-"))
            return {
                "resolved_at": datetime(y, mo, d),
                "anchor": None,
                "resolution_method": "explicit_date",
                "confidence": 1.0,
            }
        except ValueError:
            pass
    if kind == "relative" and anchor is not None:
        resolved = _resolve_relative(text.lower(), anchor)
        if resolved is not None:
            return {
                "resolved_at": resolved,
                "anchor": anchor.date().isoformat(),
                "resolution_method": "relative_to_observation",
                "confidence": 0.9,
            }
    if kind == "duration" and anchor is not None:
        resolved = _resolve_duration_start(text.lower(), anchor)
        if resolved is not None:
            return {
                "resolved_at": resolved,
                "anchor": anchor.date().isoformat(),
                "resolution_method": "duration_start",
                "confidence": 0.8,
            }
    return {
        "resolved_at": None,
        "anchor": anchor.date().isoformat() if anchor else None,
        "resolution_method": "unresolved",
        "confidence": 0.5,
    }


# ---------------------------------------------------------------- numbers


_MONEY_RANGE = re.compile(
    r"\$(\d+(?:\.\d+)?)\s*[\u2013\u2014\-]\s*(\d+(?:\.\d+)?)\s*([kmbt])?",
    re.IGNORECASE,
)
_MONEY = re.compile(r"\$(\d+(?:\.\d+)?)\s*([kmbt])?", re.IGNORECASE)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_BARE_NUM = re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\b")
_NUM_WITH_UNIT = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(investments?|companies|reserves|years?|months?|days?|hours?|people|users|customers)\b",
    re.IGNORECASE,
)

_UNIT_MULTIPLIER = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}


def find_quantities(text: str) -> list[dict[str, Any]]:
    """Return raw quantity mentions with rough owner/property heuristics."""
    found: list[dict[str, Any]] = []
    if not text:
        return found

    # Money ranges first
    for m in _MONEY_RANGE.finditer(text):
        lo, hi, unit = m.group(1), m.group(2), (m.group(3) or "").lower()
        mult = _UNIT_MULTIPLIER.get(unit, 1)
        owner, prop = _guess_owner_property(text, m.start(), m.end())
        found.append({
            "raw_value": m.group(0),
            "value": (float(lo) + float(hi)) / 2 * mult,
            "unit": "USD" if unit in _UNIT_MULTIPLIER else "USD",
            "exactness": "range",
            "owner": owner,
            "property": prop,
            "can_sum_exactly": False,
        })

    # Single money
    consumed_spans = [(m.start(), m.end()) for m in _MONEY_RANGE.finditer(text)]
    for m in _MONEY.finditer(text):
        if any(s <= m.start() < e for s, e in consumed_spans):
            continue
        val, unit = m.group(1), (m.group(2) or "").lower()
        mult = _UNIT_MULTIPLIER.get(unit, 1)
        owner, prop = _guess_owner_property(text, m.start(), m.end())
        found.append({
            "raw_value": m.group(0),
            "value": float(val) * mult,
            "unit": "USD",
            "exactness": "exact",
            "owner": owner,
            "property": prop,
            "can_sum_exactly": True,
        })

    # Percentages
    for m in _PERCENT.finditer(text):
        val = m.group(1)
        owner, prop = _guess_owner_property(text, m.start(), m.end())
        found.append({
            "raw_value": m.group(0),
            "value": float(val),
            "unit": "%",
            "exactness": "exact",
            "owner": owner,
            "property": prop,
            "can_sum_exactly": False,
        })

    # Numbers with explicit units like "36 investments"
    for m in _NUM_WITH_UNIT.finditer(text):
        val, unit = m.group(1), m.group(2).lower()
        owner, prop = _guess_owner_property(text, m.start(), m.end())
        found.append({
            "raw_value": m.group(0),
            "value": float(val),
            "unit": unit,
            "exactness": "exact",
            "owner": owner,
            "property": unit,
            "can_sum_exactly": True,
        })

    return found


def _guess_owner_property(text: str, start: int, end: int) -> tuple[Optional[str], Optional[str]]:
    """Cheap heuristic: owner = first capitalized noun phrase in the sentence;
    property = first content keyword in the local context. Good enough to
    not attach numbers to the wrong entity in the canonical examples."""
    # Sentence around the match
    sent_start = max(0, text.rfind(".", 0, start) + 1, text.rfind("\n", 0, start) + 1)
    sent_end = end
    for sep in (".", "\n"):
        idx = text.find(sep, end)
        if idx != -1:
            sent_end = min(sent_end if sent_end > end else len(text), idx)
            break
    sent = text[sent_start:sent_end].strip()

    owner = None
    # First capitalized run with at least 2 chars
    for tok in sent.split():
        clean = tok.strip(",.;:!?()[]\"'")
        if clean and clean[0].isupper() and len(clean) >= 2 and not clean.isupper():
            owner = clean
            # Try to extend with following capitalized tokens (e.g., "Fund III")
            idx = sent.split().index(tok)
            extra = []
            for n in sent.split()[idx + 1: idx + 3]:
                c = n.strip(",.;:!?()[]\"'")
                if c and (c[0].isupper() or c.isdigit()):
                    extra.append(c)
                else:
                    break
            if extra:
                owner = " ".join([clean, *extra])
            break

    # Property: look at words right before the match
    prefix = text[max(0, start - 40):start].lower()
    cand_props = ("target", "size", "reserves", "investments", "revenue",
                  "margin", "growth", "valuation", "burn", "runway",
                  "investments", "companies", "users", "customers")
    prop = next((p for p in cand_props if p in prefix), None)
    return owner, prop


# ---------------------------------------------------------------- retrieval support


def memory_view(graph, *, types: tuple[str, ...] = MEMORY_TYPES,
                statuses: tuple[str, ...] = (STATUS_ACTIVE,)):
    return [
        o for o in graph.all_objects()
        if o.type in types and (o.data or {}).get("status") in statuses
    ]


def coerce_question_keywords(question: str) -> list[str]:
    return extract_keywords(question)


def content_signature(text: str) -> str:
    """Normalized signature for near-duplicate detection."""
    return normalize(text)
