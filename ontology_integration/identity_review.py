"""Append-only, hash-linked identity decisions; never emits owl:sameAs automatically."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

DECISIONS = frozenset({'approve', 'reject', 'defer'})

def _hash(event):
    return sha256(json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

@dataclass(frozen=True)
class ReviewEvent:
    proposal_id: str
    decision: str
    reviewer: str
    rationale: str
    evidence: tuple[str, ...]
    previous_hash: str
    event_hash: str
    def to_dict(self):
        return {'proposal_id': self.proposal_id, 'decision': self.decision,
                'reviewer': self.reviewer, 'rationale': self.rationale,
                'evidence': list(self.evidence), 'previous_hash': self.previous_hash,
                'event_hash': self.event_hash}

def verify_events(events):
    previous = '0' * 64
    for row in events:
        body = {k: row[k] for k in ('proposal_id', 'decision', 'reviewer', 'rationale', 'evidence', 'previous_hash')}
        if row['previous_hash'] != previous or _hash(body) != row['event_hash']:
            raise ValueError('Identity review audit chain failed verification')
        if row['decision'] not in DECISIONS or not row['reviewer'].strip() or not row['rationale'].strip():
            raise ValueError('Invalid identity review event')
        previous = row['event_hash']
    return previous

class IdentityReviewLedger:
    def __init__(self, path):
        self.path = Path(path)
    def read(self):
        if not self.path.exists():
            return []
        events = [json.loads(line) for line in self.path.read_text(encoding='utf-8').splitlines() if line.strip()]
        verify_events(events)
        return events
    def append(self, proposal, *, decision, reviewer, rationale, evidence):
        if decision not in DECISIONS or not reviewer.strip() or not rationale.strip():
            raise ValueError('A valid review decision, reviewer and rationale are required')
        if proposal.decision not in ('review_required', 'insufficient_evidence'):
            raise ValueError('Only reviewable proposals can be adjudicated')
        if decision == 'approve' and (proposal.decision != 'review_required' or not evidence):
            raise ValueError('Approval requires a reviewable evidence-based proposal and independent evidence')
        history = self.read()
        event = {'proposal_id': proposal.proposal_id, 'decision': decision,
                 'reviewer': reviewer, 'rationale': rationale, 'evidence': list(evidence),
                 'previous_hash': verify_events(history)}
        event['event_hash'] = _hash(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + '\n')
        return ReviewEvent(**{**event, 'evidence': tuple(event['evidence'])})
    def latest_decisions(self):
        return {event['proposal_id']: event['decision'] for event in self.read()}
