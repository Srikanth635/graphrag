"""Small offline tests for the first ontology registry milestone."""
from pathlib import Path

from ontology_integration.registry import build_registry


ONTOLOGY = """@prefix ex: <https://example.org/cram#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Execution a owl:Class ;
  rdfs:label "Execution" ;
  rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty ex:realizesDesignator ;
    owl:someValuesFrom ex:GroundedDesignator
  ] .
ex:GroundedDesignator a owl:Class .
ex:realizesDesignator a owl:ObjectProperty, owl:FunctionalProperty ;
  rdfs:domain ex:Execution ;
  rdfs:range ex:GroundedDesignator .
"""


def test_registry_preserves_iris_and_restrictions(tmp_path: Path):
    path = tmp_path / "example.ttl"
    path.write_text(ONTOLOGY, encoding="utf-8")
    registry = build_registry(path)

    assert registry["triple_count"] > 0
    assert len(registry["source_sha256"]) == 64
    classes = {value["iri"]: value for value in registry["classes"]}
    execution = classes["https://example.org/cram#Execution"]
    assert execution["labels"] == ["Execution"]
    assert execution["restrictions"][0][
        "http://www.w3.org/2002/07/owl#someValuesFrom"
    ] == [{"iri": "https://example.org/cram#GroundedDesignator"}]

    prop = registry["properties"][0]
    assert prop["iri"] == "https://example.org/cram#realizesDesignator"
    assert "http://www.w3.org/2002/07/owl#FunctionalProperty" in prop["characteristics"]
    assert prop["domain_iris"] == ["https://example.org/cram#Execution"]


def test_registry_digest_changes_with_file_content(tmp_path: Path):
    path = tmp_path / "ontology.ttl"
    path.write_text(ONTOLOGY, encoding="utf-8")
    initial = build_registry(path)
    path.write_text(ONTOLOGY + "\n# revised\n", encoding="utf-8")
    revised = build_registry(path)
    assert initial["source_sha256"] != revised["source_sha256"]
    assert initial["triple_count"] == revised["triple_count"]
