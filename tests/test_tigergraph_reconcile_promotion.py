"""Milestone 7 read-back and promotion safety tests with a fake TigerGraph API."""
from dataclasses import replace
from copy import deepcopy
import pytest
from ontology_integration.assertions import Assertion, RDFTerm, SourceEvidence, AssertionStatus
from ontology_integration.tigergraph_staging import stage_plan, STAGING_VERTEX, STAGING_ATTRIBUTES
from ontology_integration.tigergraph_reconcile import apply_and_reconcile, reconcile_staging
from ontology_integration.tigergraph_promotion import approved_projection, verify_approved_projection

SHA="a"*64

def sample():
    return Assertion(
        RDFTerm("iri","urn:robot:one"), RDFTerm("iri","urn:p:label"),
        RDFTerm("literal","cup"),
        SourceEvidence("document","paper","chars:1-4","evidence"), SHA)

class FakeTigerGraph:
    graphname="OntologyStagingGraph"
    def __init__(self, *, corrupt=False, omit=False):
        self.records={}
        self.corrupt=corrupt
        self.omit=omit
    def getVertexTypes(self):
        return [{"Name":STAGING_VERTEX,
                 "PrimaryId":{"AttributeName":"assertion_id"},
                 "Attributes":[{"AttributeName":s} for s in STAGING_ATTRIBUTES]}]
    def upsertVertex(self, vertex_type, vertex_id, attrs):
        self.records[vertex_id]=attrs.copy()
        return 1
    def getVerticesById(self, vertex_type, vertex_id):
        if self.omit or vertex_id not in self.records:
            return []
        attrs=deepcopy(self.records[vertex_id])
        if self.corrupt:attrs["object_value"]="changed"
        return [{"v_id":vertex_id,"v_type":vertex_type,
                 "attributes":{k:{"value":v} for k,v in attrs.items()}}]

def test_guarded_stage_write_and_readback():
    plan=stage_plan([sample()])
    db=FakeTigerGraph()
    dry=apply_and_reconcile(plan,connection=db,expected_graph=db.graphname)
    assert dry["dry_run"] and db.records=={}
    applied=apply_and_reconcile(plan,connection=db,expected_graph=db.graphname,enable_write=True)
    assert applied["accepted"]==1 and applied["reconciliation"]["complete"]
    again=apply_and_reconcile(plan,connection=db,expected_graph=db.graphname,enable_write=True)
    assert again["reconciliation"]["complete"]
    assert len(db.records)==1

def test_readback_mismatch_is_not_silently_retried():
    plan=stage_plan([sample()])
    db=FakeTigerGraph(corrupt=True)
    with pytest.raises(RuntimeError,match="reconciliation"):
        apply_and_reconcile(plan,connection=db,expected_graph=db.graphname,enable_write=True)

def test_approval_requires_both_review_and_validated_lifecycle():
    candidate=sample()
    with pytest.raises(ValueError,match="unapproved lifecycle"):
        approved_projection([candidate],approved_assertion_ids=[candidate.assertion_id],
                            ontology_sha256=SHA,reviewer="human",approval_reason="reviewed")
    accepted=replace(candidate,status=AssertionStatus.VALIDATED)
    plan=approved_projection([accepted],approved_assertion_ids=[accepted.assertion_id],
                             ontology_sha256=SHA,reviewer="human",approval_reason="reviewed")
    assert plan["fact_count"]==1
    assert verify_approved_projection(plan)
    damaged=deepcopy(plan)
    damaged["facts"][0]["object_value"]="fabricated"
    with pytest.raises(ValueError,match="checksum"):
        verify_approved_projection(damaged)

def test_missing_approval_and_ontology_mismatch_fail_closed():
    accepted=replace(sample(),status=AssertionStatus.VALIDATED)
    params=dict(approved_assertion_ids=[accepted.assertion_id],
                ontology_sha256=SHA,reviewer="human",approval_reason="verified")
    with pytest.raises(ValueError,match="nonexistent"):
        approved_projection([],**params)
    with pytest.raises(ValueError,match="version"):
        approved_projection([accepted],**{**params,"ontology_sha256":"b"*64})
    with pytest.raises(ValueError,match="Empty approval"):
        approved_projection([accepted],**{**params,"approved_assertion_ids":[]})
