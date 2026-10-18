"""Checkpoint and export integrity tests."""
import json
import sqlite3
from pathlib import Path
import pytest
from ontology_integration.neem_export import export_snapshot, verify_export

def sample(tmp_path):
    path = tmp_path / "source.sqlite"
    ontology = tmp_path / "ontology.ttl"
    ontology.write_text("@prefix ex: <urn:example:> . ex:A ex:B ex:C .")
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE DemoDAO (database_id INTEGER PRIMARY KEY, status TEXT);
        INSERT INTO DemoDAO VALUES(1,'NOT_STARTED');
        INSERT INTO DemoDAO VALUES(2,'SUCCEEDED');
        INSERT INTO DemoDAO VALUES(3,'NOT_STARTED');
        """)
    return path, ontology

def test_paginated_export_resume_and_checksums(tmp_path):
    db, ontology=sample(tmp_path)
    dest=tmp_path/"out"
    result=export_snapshot(db, ontology_path=ontology, neem_id="pickup",
                           tables=["DemoDAO"], output_dir=dest, page_size=2)
    assert len(result["pages"])==2
    assert sum(p["assertions"] for p in result["pages"])==6
    assert result["pages"][-1]["final"]
    assert verify_export(dest)==result
    resumed=export_snapshot(db, ontology_path=ontology, neem_id="pickup",
                            tables=["DemoDAO"], output_dir=dest,
                            page_size=2, resume=True)
    assert resumed==result
    with pytest.raises(ValueError,match="Existing manifest"):
        export_snapshot(db, ontology_path=ontology, neem_id="pickup",
                        tables=["DemoDAO"], output_dir=dest, page_size=2)

def test_tamper_and_source_change_rejected(tmp_path):
    db, ontology=sample(tmp_path)
    dest=tmp_path/"out"
    result=export_snapshot(db, ontology_path=ontology, neem_id="pickup",
                           tables=["DemoDAO"], output_dir=dest, page_size=1)
    target=dest/result["pages"][0]["file"]
    target.write_text("corrupted")
    with pytest.raises(ValueError,match="checksum"):
        verify_export(dest)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO DemoDAO VALUES(4,'NOT_STARTED')")
    with pytest.raises(ValueError,match="fingerprint changed"):
        export_snapshot(db, ontology_path=ontology, neem_id="pickup",
                        tables=["DemoDAO"], output_dir=dest,
                        page_size=1, resume=True)


def test_all_populated_auto_discovery(tmp_path):
    db, ontology = sample(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE EmptyDAO (database_id INTEGER PRIMARY KEY)")
    dest = tmp_path / "all_tables"
    result = export_snapshot(db, ontology_path=ontology, neem_id="pickup",
                             output_dir=dest, page_size=2)
    assert result["tables"] == ["DemoDAO"]
    assert verify_export(dest) == result
