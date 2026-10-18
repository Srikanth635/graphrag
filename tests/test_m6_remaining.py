"""Milestone 6 cross-source and review-ledger tests."""
from dataclasses import dataclass
import pytest
from ontology_integration.identity_review import IdentityReviewLedger
from ontology_integration.entity_resolution import EntityRecord, propose_links
from ontology_integration.temporal_conflicts import find_conflicting_values
from ontology_integration.assertions import RDFTerm

def test_review_approval_and_tamper(tmp_path):
    a=EntityRecord('urn:doc:1','document','doc','Cup','chars:1-4','item:123')
    b=EntityRecord('urn:neem:1','neem','pickup','Cup','DesignatorDAO/1','item:123')
    proposal=propose_links([a,b])[0]
    file=tmp_path/'review.jsonl'
    ledger=IdentityReviewLedger(file)
    ledger.append(proposal,decision='approve',reviewer='reviewer-1',
                  rationale='Independently verified serial',evidence=('serial:123',))
    assert ledger.latest_decisions()[proposal.proposal_id]=='approve'
    file.write_text(file.read_text().replace('reviewer-1','fake-reviewer'))
    with pytest.raises(ValueError,match='chain'):
        ledger.read()

def test_no_approval_for_label_only(tmp_path):
    a=EntityRecord('urn:doc:1','document','doc','Cup','chars:1-4')
    b=EntityRecord('urn:neem:1','neem','pickup','Cup','DesignatorDAO/1')
    p=propose_links([a,b])[0]
    with pytest.raises(ValueError,match='Approval'):
        IdentityReviewLedger(tmp_path/'review.jsonl').append(
            p,decision='approve',reviewer='reviewer',rationale='label only',evidence=('label:cup',))

def test_temporal_overlap_and_disjoint_intervals():
    @dataclass(frozen=True)
    class Observation:
        assertion_id:str
        subject:RDFTerm
        predicate:RDFTerm
        object:RDFTerm
        valid_from:str|None
        valid_to:str|None
    s=RDFTerm('iri','urn:entity:1');p=RDFTerm('iri','urn:property:status')
    a=Observation('a',s,p,RDFTerm('literal','ON'),'2026-10-18T10:00:00+00:00','2026-10-18T11:00:00+00:00')
    b=Observation('b',s,p,RDFTerm('literal','OFF'),'2026-10-18T11:00:00+00:00','2026-10-18T12:00:00+00:00')
    c=Observation('c',s,p,RDFTerm('literal','OFF'),'2026-10-18T10:30:00+00:00','2026-10-18T11:30:00+00:00')
    assert find_conflicting_values([a,b],functional_predicates={p.value})==()
    assert len(find_conflicting_values([a,c],functional_predicates={p.value}))==1
    assert find_conflicting_values([a,c],functional_predicates=())==()

def test_mixed_neem_document_no_unjustified_merges():
    doc=EntityRecord('urn:ontologyrag:mention:alpha','document','paper','cup','chars:4-7')
    neem=EntityRecord('urn:neem:entity:pickup:DesignatorDAO:2','neem','pickup','cup','DesignatorDAO/2')
    assert propose_links([doc,neem])[0].decision=='insufficient_evidence'
