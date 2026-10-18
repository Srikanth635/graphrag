"""Whole-database scan counts match the source assertion model."""
import sqlite3
from pathlib import Path
from ontology_integration.neem_full_scan import scan_database

def test_full_scan_counts_and_fk_integrity(tmp_path:Path):
    path=tmp_path/"fixture.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE ParentDAO(database_id INTEGER PRIMARY KEY, text_value TEXT);
        CREATE TABLE ChildDAO(
          database_id INTEGER PRIMARY KEY REFERENCES ParentDAO(database_id),
          _parent_id INTEGER REFERENCES ParentDAO(database_id), status TEXT);
        CREATE TABLE EmptyDAO(database_id INTEGER PRIMARY KEY);
        INSERT INTO ParentDAO VALUES(1,'robot');
        INSERT INTO ParentDAO VALUES(2,NULL);
        INSERT INTO ChildDAO VALUES(1,2,'NOT_STARTED');
        """)
    report=scan_database(path)
    assert report["tables"]==3
    assert report["populated_tables"]==2
    assert report["rows"]==3
    assert report["candidate_source_assertions"]==7
    assert report["inheritance_assertions"]==1
    assert report["ordinary_fk_assertions"]==1
    assert report["missing_fk_targets"]==0
    assert report["null_columns_skipped"]==1
    assert report["integrity"]=="ok"
