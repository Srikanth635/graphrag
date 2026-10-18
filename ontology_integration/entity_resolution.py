"""Conservative entity linking: propose matches, do not assert owl:sameAs."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re

@dataclass(frozen=True)
class EntityRecord:
    iri: str
    source_type: str
    source_id: str
    label: str
    evidence_locator: str
    verified_external_id: str | None = None
    def __post_init__(self):
        if any(not x or not isinstance(x,str) for x in
               (self.iri,self.source_type,self.source_id,self.label,self.evidence_locator)):
            raise ValueError("Entity evidence fields are mandatory")

@dataclass(frozen=True)
class LinkProposal:
    proposal_id: str
    left: str
    right: str
    decision: str
    reason: str
    evidence: tuple[str,str]
    def to_dict(self):
        return vars(self).copy()

def propose_links(records):
    """Same canonical IRI is identical; verified shared IDs still require review.

    Labels alone never warrant an automatic entity merge.
    """
    records=tuple(records)
    proposals=[]
    for i,left in enumerate(records):
        for right in records[i+1:]:
            if left.iri==right.iri:
                reason="same_canonical_iri"
                decision="already_identical"
            elif left.verified_external_id and left.verified_external_id==right.verified_external_id:
                reason="shared_verified_external_identifier"
                decision="review_required"
            elif re.sub(r"\s+"," ",left.label.strip()).casefold()==re.sub(r"\s+"," ",right.label.strip()).casefold():
                reason="same_label_only"
                decision="insufficient_evidence"
            else:
                continue
            pair=sorted((left.iri,right.iri))
            pid=sha256(json.dumps([pair,reason],separators=(",",":")).encode()).hexdigest()
            proposals.append(LinkProposal(pid,pair[0],pair[1],decision,reason,
                                          (left.evidence_locator,right.evidence_locator)))
    return tuple(sorted(proposals,key=lambda x:x.proposal_id))
