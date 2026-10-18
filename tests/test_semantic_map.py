"""Unit tests for conservative NEEM SQL-to-OWL alignment."""
import sqlite3
from pathlib import Path
import pytest
from rdflib.namespace import RDF
from ontology_integration.semantic_map import (
    mapped_designators, summarize_mapping, ClassMapping, BASE,
)

ONTO = """@prefix x: <http://aicor.knowledge/l2-ontology.owl#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
x:Designator a owl:Class .
"""

def fixture(tmp_path):
    db = tmp_path / "neem.sqlite"
    ontology = tmp_path / "ontology.ttl"
    ontology.write_text(ONTO)
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE DesignatorDAO (database_id INTEGER PRIMARY KEY, polymorphic_type TEXT);
        CREATE TABLE DesignatorNodeDAO (database_id INTEGER PRIMARY KEY, _designator_id INTEGER);
        CREATE TABLE ActionNodeDAO (database_id INTEGER PRIMARY KEY, _execution_data_id INTEGER);
        CREATE TABLE PlanNodeDAO (database_id INTEGER PRIMARY KEY, status TEXT);
        INSERT INTO DesignatorDAO VALUES (4,'PickUpActionDAO');
        INSERT INTO DesignatorNodeDAO VALUES (8,4);
        INSERT INTO ActionNodeDAO VALUES (8,NULL);
        INSERT INTO PlanNodeDAO VALUES (8,'NOT_STARTED');
        """)
    return db, ontology

def test_explicit_mapping_is_deterministic(tmp_path):
    db, ontology = fixture(tmp_path)
    first = mapped_designators(db, neem_id="pickup", ontology_path=ontology)
    second = mapped_designators(db, neem_id="pickup", ontology_path=ontology)
    assert first.batch_id == second.batch_id
    assert len(first.assertions) == 1
    assertion = first.assertions[0]
    assert assertion.object.value == BASE + "Designator"
    assert assertion.predicate.value == str(RDF.type)
    assert assertion.evidence.method == "explicit_sql_owl_mapping"
    assert assertion.status.value == "candidate"
    assert "DesignatorDAO:4" in assertion.subject.value

def test_reject_unverified_class(tmp_path):
    db, ontology = fixture(tmp_path)
    with pytest.raises(ValueError, match="not declared"):
        mapped_designators(
            db, neem_id="pickup", ontology_path=ontology,
            class_mappings=(ClassMapping("DesignatorDAO", BASE + "Execution", "unverified"),),
        )

def test_status_is_not_promoted_to_execution(tmp_path):
    db, _ = fixture(tmp_path)
    report = summarize_mapping(db)
    assert report["action_node_execution_refs"] == 0
    assert report["plan_states"] == {"NOT_STARTED": 1}
    assert report["designator_node_links"] == 1
