"""Milestone 5 offline document ingestion foundation tests."""
from pathlib import Path
import pytest
from rdflib.namespace import RDF
from ontology_integration.document_chunks import chunk_text, verify_chunk
from ontology_integration.document_modules import rank_ontology_entries, plan_extraction
from ontology_integration.document_assertions import accept_candidates, extraction_request

EX="https://example.org/#"
INDEX={"sha256":"a"*64,
       "classes":[{"iri":EX+"RobotAction","labels":["Robot action"],"axioms":[]},
                  {"iri":EX+"Container","labels":["Container"],"axioms":[]}],
       "properties":[{"iri":EX+"targetsObject","axioms":[]}]}

def test_chunk_offsets_overlap_and_replay():
    original=("Robot action targets object.\n\n" * 35)+"A container is on the table."
    a=chunk_text(original,document_id="doc-1",max_chars=100,overlap=20)
    b=chunk_text(original,document_id="doc-1",max_chars=100,overlap=20)
    assert a==b and len(a)>2
    assert all(verify_chunk(c,original) for c in a)
    assert a[1].start < a[0].end
    assert all(c.document_sha256==a[0].document_sha256 for c in a)
    with pytest.raises(ValueError):
        chunk_text(original,document_id="doc-1",max_chars=60,overlap=60)

def test_ontology_wide_seed_selection_without_hardcoding():
    text="The robot action targets object and the container is stationary."
    ranked=rank_ontology_entries(text,INDEX,top_k=3)
    assert {x["iri"] for x in ranked} >= {EX+"RobotAction",EX+"Container"}
    chunk=chunk_text(text,document_id="doc",max_chars=100)[0]
    plan=plan_extraction(chunk,INDEX,top_k=3,module_entries=5)
    assert plan["contract"]["ontology_sha256"]=="a"*64
    assert {x["iri"] for x in plan["contract"]["classes"]}=={EX+"RobotAction",EX+"Container"}
    assert plan_extraction(chunk,INDEX,top_k=1,module_entries=1)["module"]["selected_count"]==1

def test_candidate_evidence_and_ontology_guards():
    original="A robot action moves a container."
    chunk=chunk_text(original,document_id="doc-7",max_chars=80)[0]
    contract=plan_extraction(chunk,INDEX,top_k=3,module_entries=3)["contract"]
    record={"subject_iri":"urn:doc:doc-7:action:1",
            "predicate_iri":str(RDF.type),
            "object":{"kind":"iri","value":EX+"RobotAction"},
            "evidence_start":2,"evidence_end":14,
            "evidence_text":"robot action"}
    request=extraction_request(chunk,contract)
    assert request["text"]==original
    result=accept_candidates(chunk,original,contract,[record])
    assert len(result.assertions)==1
    assert result.assertions[0].status.value=="candidate"
    assert result.assertions[0].evidence.locator.endswith("chars:2-14")
    assert result.assertions[0].ontology_sha256=="a"*64
    with pytest.raises(ValueError,match="evidence"):
        accept_candidates(chunk,original,contract,[{**record,"evidence_text":"fake"}])
    with pytest.raises(ValueError,match="class"):
        accept_candidates(chunk,original,contract,
                          [{**record,"object":{"kind":"iri","value":EX+"Unknown"}}])
    with pytest.raises(ValueError,match="match"):
        accept_candidates(chunk,original+" corrupted",contract,[record])

def test_unmatched_document_returns_no_contract():
    chunk=chunk_text("Unrelated quantum mechanics terms.",
                     document_id="doc-8",max_chars=80)[0]
    plan=plan_extraction(chunk,INDEX)
    assert plan["contract"] is None and plan["seeds"]==[]
