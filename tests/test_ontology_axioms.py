"""Offline tests for advanced OWL indexing and ontology neighborhood selection."""
from pathlib import Path

import pytest

from ontology_integration.axioms import build_axiom_index, select_module

EX = "https://example.org/#"
TTL = """@prefix ex: <https://example.org/#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Execution a owl:Class ;
  rdfs:subClassOf [ a owl:Restriction ;
                    owl:onProperty ex:realizes ;
                    owl:someValuesFrom ex:Designator ] ;
  owl:disjointWith ex:Plan .
ex:Designator a owl:Class .
ex:Plan a owl:Class ;
  owl:equivalentClass [ a owl:Class ;
                        owl:unionOf (ex:Execution ex:Designator) ] .
ex:realizes a owl:ObjectProperty ;
  owl:propertyChainAxiom (ex:realizes ex:realizes) .
"""


def test_expression_index_and_module(tmp_path: Path):
    source = tmp_path / "fixture.ttl"
    source.write_text(TTL, encoding="utf-8")
    index = build_axiom_index(source)
    assert len(index["classes"]) == 3

    execution = next(x for x in index["classes"] if x["iri"] == EX + "Execution")
    subclass = next(
        x for x in execution["axioms"] if x["predicate"].endswith("subClassOf")
    )
    assert subclass["expression"]["kind"] == "restriction"
    assert subclass["expression"][
        "http://www.w3.org/2002/07/owl#onProperty"
    ] == [{"iri": EX + "realizes"}]

    plan = next(x for x in index["classes"] if x["iri"] == EX + "Plan")
    assert any("unionOf" in str(a) for a in plan["axioms"])
    prop = index["properties"][0]
    assert prop["axioms"][0]["expression"]["list"] == [
        {"iri": EX + "realizes"}
    ] * 2

    module = select_module(index, [EX + "Execution"], 1)
    assert EX + "Designator" in {x["iri"] for x in module["classes"]}
    assert EX + "realizes" in {x["iri"] for x in module["properties"]}
    assert select_module(index, [EX + "Execution"], 0)["selected_count"] == 1
    with pytest.raises(ValueError):
        select_module(index, [EX + "Unknown"])


def test_determinism(tmp_path: Path):
    source = tmp_path / "fixture.ttl"
    source.write_text(TTL, encoding="utf-8")
    assert build_axiom_index(source) == build_axiom_index(source)
