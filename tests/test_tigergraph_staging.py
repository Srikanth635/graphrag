"""Milestone 7 staging safety and idempotent write-contract tests."""
from copy import deepcopy
import pytest
from ontology_integration.assertions import Assertion, RDFTerm, SourceEvidence
from ontology_integration.tigergraph_staging import (
    stage_plan, stage_to_tigergraph, STAGING_ATTRIBUTES, STAGING_VERTEX,
)

SHA = "a"*64

def assertion(value, source="document"):
    return Assertion(
        subject=RDFTerm("iri","urn:entity:one"),
        predicate=RDFTerm("iri","urn:ontology:hasLabel"),
        object=RDFTerm("literal",value),
        ontology_sha256=SHA,
        evidence=SourceEvidence(source,"doc-or-neem","chars:0-5","fixture"),
    )

class FakeConnection:
    graphname="OntologyStagingGraph"
    def __init__(self, valid_schema=True):
        self.calls=[]
        self.valid_schema=valid_schema
    def getVertexTypes(self):
        cols=[{"AttributeName": name} for name in sorted(STAGING_ATTRIBUTES)]
        if not self.valid_schema:
            cols.pop()
        return [{"Name": STAGING_VERTEX,
                 "PrimaryId":{"AttributeName":"assertion_id"},
                 "Attributes":cols}]
    def upsertVertex(self, vertex_type, vertex_id, attrs):
        self.calls.append((vertex_type,vertex_id,attrs.copy()))
        return 1

def test_plan_stability_and_source_distinction():
    a=assertion("cup")
    b=assertion("mug","neem_sqlite")
    first=stage_plan([b,a,a])
    second=stage_plan([a,b])
    assert first==second
    assert first["count"]==2
    assert first["vertices"][0]["attributes"]["ontology_sha256"]==SHA
    assert all(x["attributes"]["assertion_status"]=="candidate"
               for x in first["vertices"])

def test_dry_run_never_calls_database():
    db=FakeConnection()
    plan=stage_plan([assertion("cup")])
    result=stage_to_tigergraph(plan,connection=db)
    assert result.dry_run and result.accepted==0 and not db.calls

def test_opted_in_writer_requires_exact_graph_and_schema():
    db=FakeConnection()
    plan=stage_plan([assertion("cup")])
    with pytest.raises(ValueError,match="target graph"):
        stage_to_tigergraph(plan,connection=db,enable_write=True)
    with pytest.raises(ValueError,match="different graph"):
        stage_to_tigergraph(plan,connection=db,enable_write=True,expected_graph="OtherGraph")
    assert not db.calls
    bad=FakeConnection(valid_schema=False)
    with pytest.raises(ValueError,match="missing required"):
        stage_to_tigergraph(plan,connection=bad,enable_write=True,
                            expected_graph="OntologyStagingGraph")
    assert not bad.calls
    result=stage_to_tigergraph(plan,connection=db,enable_write=True,
                               expected_graph="OntologyStagingGraph")
    assert not result.dry_run and result.accepted==1 and len(db.calls)==1
    assert db.calls[0][0]==STAGING_VERTEX

def test_tampered_plan_refused_before_writes():
    db=FakeConnection()
    plan=stage_plan([assertion("cup")])
    corrupt=deepcopy(plan)
    corrupt["vertices"][0]["attributes"]["object_value"]="fabricated"
    with pytest.raises(ValueError,match="integrity mismatch"):
        stage_to_tigergraph(corrupt,connection=db,enable_write=True,
                            expected_graph="OntologyStagingGraph")
    assert not db.calls

def test_named_graph_rejected_until_supported():
    from dataclasses import replace
    row=assertion("cup")
    with pytest.raises(ValueError,match="Named graphs"):
        stage_plan([replace(row,graph=RDFTerm("iri","urn:graph:one"))])
