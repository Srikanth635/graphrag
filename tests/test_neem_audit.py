"""Trusted SQL dump fidelity fixture tests."""
import sqlite3
from pathlib import Path
from ontology_integration.neem_audit import compare_trusted_dump

def test_trusted_dump_fidelity(tmp_path:Path):
    source=tmp_path/"source.sqlite"
    with sqlite3.connect(source) as db:
        db.executescript("""
        CREATE TABLE BaseDAO (database_id INTEGER PRIMARY KEY);
        CREATE TABLE ChildDAO (database_id INTEGER PRIMARY KEY
          REFERENCES BaseDAO(database_id), status TEXT);
        INSERT INTO BaseDAO VALUES(1);
        INSERT INTO ChildDAO VALUES(1,'NOT_STARTED');
        """)
        dump="\n".join(db.iterdump())
    sql=tmp_path/"dump.sql"
    sql.write_text(dump)
    report=compare_trusted_dump(source,sql)
    assert report["counts_match"]
    assert report["sqlite_tables"] == report["dump_tables"] == 2
    assert report["foreign_key_violations"]=={"sqlite":0,"dump":0}
    assert report["row_count_mismatches"]==[]

def test_mismatch_detected(tmp_path:Path):
    source=tmp_path/"source.sqlite"
    with sqlite3.connect(source) as db:
        db.executescript("CREATE TABLE T (id INTEGER PRIMARY KEY); INSERT INTO T VALUES(1);")
    sql=tmp_path/"dump.sql"
    sql.write_text("CREATE TABLE T (id INTEGER PRIMARY KEY);")
    result=compare_trusted_dump(source,sql)
    assert not result["counts_match"]
    assert result["row_count_mismatches"][0]["table"]=="T"
