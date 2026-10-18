"""Append-only provenance events with replayable, hash-checked JSONL history.

In-memory journal; durable transactional storage is not provided.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Iterable
from .assertions import Assertion, AssertionStatus, digest, instant

@dataclass(frozen=True)
class ProvenanceEvent:
    assertion_id: str
    previous_status: str | None
    status: str
    occurred_at: str
    actor: str
    detail: str = ""
    prev_event_id: str | None = None

    def __post_init__(self):
        instant(self.occurred_at)
        if not self.actor.strip():
            raise ValueError("Actor must be nonempty")
        AssertionStatus(self.status)
        if self.previous_status is not None:
            AssertionStatus(self.previous_status)

    def to_dict(self):
        return {"assertion_id": self.assertion_id,
                "previous_status": self.previous_status, "status": self.status,
                "occurred_at": self.occurred_at, "actor": self.actor,
                "detail": self.detail, "prev_event_id": self.prev_event_id}

    @property
    def event_id(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class ProvenanceJournal:
    def __init__(self, assertions: Iterable[Assertion] = ()):
        self._snapshots = {a.assertion_id: a for a in assertions}
        self._events: list[ProvenanceEvent] = []

    def current(self, assertion_id: str) -> Assertion:
        return self._snapshots[assertion_id]

    @property
    def events(self) -> tuple[ProvenanceEvent, ...]:
        return tuple(self._events)

    def change(self, assertion_id: str, status: str, *,
               occurred_at: str, actor: str, detail: str = "") -> ProvenanceEvent:
        old = self._snapshots[assertion_id]
        updated = old.transition(AssertionStatus(status))
        prior = next((e for e in reversed(self._events)
                      if e.assertion_id == assertion_id), None)
        event = ProvenanceEvent(assertion_id, old.status.value, updated.status.value,
                                occurred_at, actor, detail,
                                prior.event_id if prior else None)
        if prior and instant(occurred_at) < instant(prior.occurred_at):
            raise ValueError("Event timestamp predates earlier event")
        self._snapshots[assertion_id] = updated
        self._events.append(event)
        return event

    def to_jsonl(self):
        return "".join(json.dumps({**event.to_dict(), "event_id": event.event_id},
                                  sort_keys=True) + "\n" for event in self._events)

    @classmethod
    def replay(cls, assertions: Iterable[Assertion], data: str):
        journal = cls(assertions)
        for line in data.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            claimed_id = payload.pop("event_id", None)
            event = ProvenanceEvent.from_dict(payload)
            if claimed_id != event.event_id:
                raise ValueError("Event history chain mismatch")
            if journal.current(event.assertion_id).status.value != event.previous_status:
                raise ValueError("Event history status mismatch")
            rebuilt = journal.change(event.assertion_id, event.status,
                                     occurred_at=event.occurred_at,
                                     actor=event.actor, detail=event.detail)
            if rebuilt.event_id != event.event_id:
                raise ValueError("Event history chain mismatch")
        return journal
