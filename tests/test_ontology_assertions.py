"""Milestone 3 offline assertion contract tests."""
from dataclasses import replace
import json

import pytest

from ontology_integration.assertions import (
    Assertion, AssertionStatus, RDFTerm, SourceEvidence, TermKind,
)

BASE = "http://aicor.knowledge/l2-ontology.owl#"


def iri(value):
    return RDFTerm(TermKind.IRI, value)


def sample(source_type="neem", source_id="neem-7"):
    return Assertion(
        subject=iri("urn:neem:execution:123"),
        predicate=iri(BASE + "realizesDesignator"),
        object=iri("urn:neem:designator:9"),
        evidence=SourceEvidence(source_type, source_id, "event/123", "deterministic"),
        ontology_sha256="a" * 64,
        confidence=0.9,
        valid_from="2026-10-18T12:00:00+02:00",
        valid_to="2026-10-18T12:01:00+02:00",
    )


def test_cross_source_statement_identity():
    neem, doc = sample(), sample("document", "paper-2")
    assert neem.statement_id == doc.statement_id
    assert neem.assertion_id != doc.assertion_id
    assert neem.transition("validated").assertion_id == neem.assertion_id


def test_roundtrip_and_digest_protection():
    original = sample()
    assert Assertion.from_json(original.to_json()) == original
    changed = json.loads(original.to_json())
    changed["object"]["value"] = "urn:neem:designator:other"
    with pytest.raises(ValueError, match="digest mismatch"):
        Assertion.from_dict(changed)


def test_lifecycle_guards():
    item = sample()
    assert item.transition("validated").transition("asserted").transition("retracted").status == AssertionStatus.RETRACTED
    with pytest.raises(ValueError):
        item.transition("asserted")
    with pytest.raises(ValueError):
        item.transition("inferred")
    inferred = replace(item, status="inferred", derived_from=(item.statement_id,))
    assert inferred.transition("retracted").status == AssertionStatus.RETRACTED


def test_rdf_timestamp_and_confidence_validation():
    with pytest.raises(ValueError):
        RDFTerm(TermKind.IRI, "relative")
    with pytest.raises(ValueError):
        RDFTerm(TermKind.LITERAL, "x", datatype=BASE + "Text", language="en")
    with pytest.raises(ValueError):
        replace(sample(), predicate=RDFTerm(TermKind.LITERAL, "p"))
    with pytest.raises(ValueError):
        replace(sample(), confidence=float("nan"))
    with pytest.raises(ValueError):
        replace(sample(), valid_from="2026-10-18T13:00:00+02:00")
    with pytest.raises(ValueError):
        replace(sample(), ontology_sha256="bad")


def test_blank_node_scoping_and_language_literals():
    left = replace(sample(), subject=RDFTerm(TermKind.BNODE, "b1"))
    right = replace(left, evidence=replace(left.evidence, source_id="neem-8"))
    assert left.statement_id != right.statement_id
    literal = replace(sample(), object=RDFTerm(TermKind.LITERAL, "Grasp", language="en"))
    assert Assertion.from_json(literal.to_json()) == literal
