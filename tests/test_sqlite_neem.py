"""Read-only SQLite NEEM adapter acceptance tests."""
import sqlite3
from pathlib import Path
import pytest

from ontology_integration.sqlite_neem import export_sqlite, profile_sqlite, SOURCE_NS

SHA = "a" * 64


def fixture(tmp_path: Path):
    path = tmp_path / "neem.sqlite"
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE PlanNodeDAO (
        database_id INTEGER PRIMARY KEY, status TEXT, start_time TEXT);
    CREATE TABLE PlanEdgeDAO (
        database_id INTEGER PRIMARY KEY,
        _parent_id INTEGER REFERENCES PlanNodeDAO(database_id),
        _child_id INTEGER REFERENCES PlanNodeDAO(database_id));
    INSERT INTO PlanNodeDAO VALUES(1,'NOT_STARTED','2026-10-14 12:00:00');
    INSERT INTO PlanNodeDAO VALUES(2,'SUCCEEDED',NULL);
    INSERT INTO PlanEdgeDAO VALUES(10,1,2);
    """)
    db.commit()
    db.close()
    return path


def test_schema_profile(tmp_path):
    source = fixture(tmp_path)
    profile = profile_sqlite(source)
    assert profile["table_count"] == 2
    assert profile["populated_table_count"] == 2
    edge = next(t for t in profile["tables"] if t["table"] == "PlanEdgeDAO")
    assert len(edge["foreign_keys"]) == 2


def test_deterministic_cross_table_staging(tmp_path):
    source = fixture(tmp_path)
    first = export_sqlite(source, neem_id="trial-1", ontology_sha256=SHA,
                          tables=["PlanNodeDAO", "PlanEdgeDAO"])
    second = export_sqlite(source, neem_id="trial-1", ontology_sha256=SHA,
                           tables=["PlanEdgeDAO", "PlanNodeDAO"])
    assert first.batch_id == second.batch_id
    assert len(first.assertions) == 8
    assert all(a.evidence.source_type == "neem_sqlite" for a in first.assertions)
    statuses = [a for a in first.assertions
                if a.predicate.value == SOURCE_NS + "PlanNodeDAO/status"]
    assert {a.object.value for a in statuses} == {"NOT_STARTED", "SUCCEEDED"}
    parent = next(a for a in first.assertions
                  if a.predicate.value == SOURCE_NS + "PlanEdgeDAO/_parent_id")
    assert parent.object.kind.value == "iri"
    assert "PlanNodeDAO:1" in parent.object.value
    assert all(a.status.value == "candidate" for a in first.assertions)


def test_unknown_table_row_limit_and_readonly(tmp_path):
    source = fixture(tmp_path)
    with pytest.raises(ValueError, match="Unknown"):
        export_sqlite(source, neem_id="trial", ontology_sha256=SHA, tables=["unknown"])
    limited = export_sqlite(source, neem_id="trial", ontology_sha256=SHA,
                            tables=["PlanNodeDAO"], max_rows=1)
    assert len(limited.assertions) == 3
    assert sqlite3.connect(source).execute("SELECT COUNT(*) FROM PlanNodeDAO").fetchone()[0] == 2
