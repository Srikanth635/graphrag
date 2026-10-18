"""Regression tests for bounded module selection, coverage and extraction contracts."""
from pathlib import Path

import pytest

from ontology_integration.axioms import build_axiom_index
from ontology_integration.module_builder import (
    audit_coverage, extraction_contract, select_bounded_module,
)

TTL = """@prefix x: <http://example.org/#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
x:A a owl:Class ;
 rdfs:subClassOf [ a owl:Restriction ;
 owl:onProperty x:rel ; owl:someValuesFrom x:B ] .
x:B a owl:Class ; rdfs:subClassOf x:C .
x:C a owl:Class .
x:rel a owl:ObjectProperty .
"""


def test_bounded_module_contract_and_coverage(tmp_path: Path):
    path = tmp_path / "test.ttl"
    path.write_text(TTL)
    index = build_axiom_index(path)
    seed = "http://example.org/#A"
    module = select_bounded_module(index, [seed], depth=2, max_entries=3)
    assert module["selected_count"] == 3
    assert module["truncated"]
    assert module == select_bounded_module(index, [seed], depth=2, max_entries=3)

    contract = extraction_contract(module)
    assert contract["policy"]["do_not_invent_existential_fillers"]
    assert contract["relation_hints"][0]["subject_class"] == seed
    assert contract["relation_hints"][0]["predicate_iri"] == "http://example.org/#rel"
    assert audit_coverage(path, index)["patterns"]["restrictions"] == 1


def test_module_invalid_inputs(tmp_path: Path):
    path = tmp_path / "test.ttl"
    path.write_text(TTL)
    index = build_axiom_index(path)
    seed = "http://example.org/#A"
    for kwargs in ({"depth": -1}, {"max_entries": 0}, {"direction": "unknown"}):
        with pytest.raises(ValueError):
            select_bounded_module(index, [seed], **kwargs)
    with pytest.raises(ValueError):
        select_bounded_module(index, [])
    with pytest.raises(ValueError):
        select_bounded_module(index, ["http://example.org/#Unknown"])
    with pytest.raises(ValueError):
        select_bounded_module(index, [seed, "http://example.org/#B"], max_entries=1)
