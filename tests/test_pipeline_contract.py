"""Cross-source batch, RDF conversion, vocabulary and provenance tests."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD
from ontology_integration.assertions import RDFTerm
from ontology_integration.pipeline_contract import (
    AssertionBatch, OntologyVocabulary, from_rdflib, to_rdflib,
    to_rdflib_graph, normalize_sources)
from ontology_integration.provenance import ProvenanceJournal

EX = "https://example.org/#"
SHA = "a" * 64

def record(source_type, source_id):
    return {"source_type":source_type,"source_id":source_id,
            "locator":"record/1","method":"mapped",
            "subject":{"kind":"iri","value":"urn:robot:execution:1"},
            "predicate":{"kind":"iri","value":EX+"realizes"},
            "object":{"kind":"iri","value":"urn:robot:designator:2"}}

def test_three_source_roundtrip_and_idempotence():
    batch = normalize_sources([record("neem","n1"),record("document","p1"),
                               record("structured","db1")], SHA)
    assert len(batch.assertions) == 3
    assert len({a.statement_id for a in batch.assertions}) == 1
    assert len({a.assertion_id for a in batch.assertions}) == 3
    assert AssertionBatch.from_json(batch.to_json()) == batch
    assert AssertionBatch.from_jsonl(batch.to_jsonl()) == batch
    assert AssertionBatch(tuple(reversed(batch.assertions))).batch_id == batch.batch_id
    assert len(AssertionBatch(batch.assertions + batch.assertions).assertions) == 3
    tampered = json.loads(batch.to_json())
    tampered["assertions"][0]["subject"]["value"] = "urn:tampered"
    with pytest.raises(ValueError):
        AssertionBatch.from_dict(tampered)

def test_conflicting_snapshots():
    a = normalize_sources([record("neem","n1")],SHA).assertions[0]
    with pytest.raises(ValueError, match="Conflicting"):
        AssertionBatch((a,replace(a,confidence=0.3)))

def test_rdflib_bridge_and_lossy_projection_rejected():
    for term in (URIRef(EX+"x"),Literal("bonjour",lang="fr"),Literal("10",datatype=XSD.integer)):
        assert to_rdflib(from_rdflib(term)) == term
    a = normalize_sources([record("neem","n1")],SHA).assertions[0]
    assert len(to_rdflib_graph([a])) == 1
    with pytest.raises(ValueError,match="Named graph"):
        to_rdflib_graph([replace(a,graph=RDFTerm("iri",EX+"graph"))])
    with pytest.raises(ValueError,match="Blank-node"):
        to_rdflib_graph([replace(a,subject=RDFTerm("bnode","b1"))])

def test_ontology_membership(tmp_path:Path):
    path = tmp_path/"ontology.ttl"
    path.write_text('@prefix ex: <https://example.org/#> .\n'
                    '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n'
                    'ex:Execution a owl:Class . ex:realizes a owl:ObjectProperty .')
    vocab = OntologyVocabulary.from_turtle(path)
    a = normalize_sources([record("neem","n1")],SHA).assertions[0]
    assert vocab.check(a,strict=True).accepted
    unknown = replace(a,predicate=RDFTerm("iri",EX+"Unknown"))
    assert not vocab.check(unknown,strict=True).accepted
    assert vocab.check(unknown).accepted
    typed = replace(a,predicate=RDFTerm("iri",str(RDF.type)),
                    object=RDFTerm("iri",EX+"Execution"))
    assert vocab.check(typed,strict=True).accepted
    assert not vocab.check(replace(typed,object=RDFTerm("iri",EX+"Missing")),strict=True).accepted

def test_history_replay_and_tampering():
    a = normalize_sources([record("neem","n1")],SHA).assertions[0]
    journal = ProvenanceJournal([a])
    journal.change(a.assertion_id,"validated",occurred_at="2026-10-18T12:00:00Z",actor="validator")
    journal.change(a.assertion_id,"asserted",occurred_at="2026-10-18T12:02:00Z",actor="reviewer")
    assert ProvenanceJournal.replay([a],journal.to_jsonl()).current(a.assertion_id).status.value == "asserted"
    with pytest.raises(ValueError):
        journal.change(a.assertion_id,"candidate",occurred_at="2026-10-18T12:03:00Z",actor="reviewer")
    lines = journal.to_jsonl().splitlines()
    bad = json.loads(lines[1]); bad["actor"] = "attacker"
    with pytest.raises(ValueError,match="chain mismatch"):
        ProvenanceJournal.replay([a],lines[0]+"\n"+json.dumps(bad)+"\n")
