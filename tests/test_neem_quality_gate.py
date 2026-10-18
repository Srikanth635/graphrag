"""NEEM mapping quality gate: synthetic and real-dataset independent tests."""
import sqlite3
from pathlib import Path
import pytest
from ontology_integration.neem_quality_gate import quality_report

def test_designator_mapping_and_status_guard(tmp_path: Path):
    db = tmp_path / "pickup.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE DesignatorDAO(database_id INTEGER PRIMARY KEY);
        CREATE TABLE PlanNodeDAO(database_id INTEGER PRIMARY KEY, status TEXT);
        CREATE TABLE ExecutionDataDAO(database_id INTEGER PRIMARY KEY);
        CREATE TABLE ActionNodeDAO(database_id INTEGER PRIMARY KEY, _execution_data_id INTEGER);
        INSERT INTO DesignatorDAO VALUES(4);
        INSERT INTO PlanNodeDAO VALUES(1,'NOT_STARTED');
        INSERT INTO ActionNodeDAO VALUES(1,NULL);
        """)
    ontology = tmp_path / "ont.ttl"
    ontology.write_text(
      '@prefix owl: <http://www.w3.org/2002/07/owl#> . '
      '<http://aicor.knowledge/l2-ontology.owl#Designator> a owl:Class .')
    report = quality_report(db, ontology, neem_id="pickup-1")
    assert report["candidate_count"] == 1
    assert report["designator_owl_candidates"][0]["status"] == "candidate"
    assert report["execution_data_records"] == 0
    assert report["action_node_execution_refs"] == 0
    assert report["plan_node_states"] == {"NOT_STARTED": 1}
    assert not report["coverage"]["ontology_mapping_is_exhaustive"]
    assert all(r["decision"] == "not_mapped" for r in report["review_required"])
    assert report == quality_report(db, ontology, neem_id="pickup-1")

def test_missing_owl_class_rejected(tmp_path: Path):
    db = tmp_path / "pickup.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE DesignatorDAO(database_id INTEGER PRIMARY KEY)")
    ontology = tmp_path / "ont.ttl"
    ontology.write_text('<urn:foo> <urn:bar> <urn:baz> .')
    with pytest.raises(ValueError, match="Designator"):
        quality_report(db, ontology, neem_id="pickup")

def test_empty_neem_id_rejected(tmp_path):
    with pytest.raises(ValueError, match="neem_id"):
        quality_report("missing.sqlite", "missing.ttl", neem_id="")
