"""Contradictory observation review, never closed-world rejection of alternatives."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations

@dataclass(frozen=True)
class Conflict:
    left_assertion_id: str
    right_assertion_id: str
    kind: str
    decision: str
    reason: str
    def to_dict(self):
        return vars(self).copy()

def _parse_time(text):
    if text is None:
        return None
    time = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if time.tzinfo is None or time.utcoffset() is None:
        raise ValueError('Temporal review requires timezone-aware timestamps')
    return time.astimezone(timezone.utc)

def _overlap(a, b):
    a_start, a_end = _parse_time(a.valid_from), _parse_time(a.valid_to)
    b_start, b_end = _parse_time(b.valid_from), _parse_time(b.valid_to)
    if a_start and a_end and a_start >= a_end:
        raise ValueError('Invalid assertion interval')
    if b_start and b_end and b_start >= b_end:
        raise ValueError('Invalid assertion interval')
    return ((not a_end or not b_start or a_end > b_start)
            and (not b_end or not a_start or b_end > a_start))

def find_conflicting_values(assertions, *, functional_predicates=()):
    """Review competing values for explicitly designated functional predicates.

    Unbounded intervals are uncertain, not proof of a contradiction.
    """
    allowed = set(functional_predicates)
    groups = {}
    for assertion in assertions:
        if assertion.predicate.value in allowed:
            groups.setdefault((assertion.subject.value, assertion.predicate.value), []).append(assertion)
    flagged = []
    for group in groups.values():
        for left, right in combinations(group, 2):
            if left.object == right.object or not _overlap(left, right):
                continue
            ids = sorted((left.assertion_id, right.assertion_id))
            flagged.append(Conflict(ids[0], ids[1], 'competing_functional_values',
                                    'review_required',
                                    'Distinct values for a functional predicate with potentially overlapping validity'))
    return tuple(sorted(flagged, key=lambda item: (item.left_assertion_id, item.right_assertion_id)))
