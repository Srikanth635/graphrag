"""DAO reconstruction fixtures: inheritance, pagination, lifecycle, and FK quality."""
import sqlite3
from pathlib import Path
from rdflib.namespace import XSD
import pytest
from ontology_integration.neem_reconstruction import (
    extract_page, profile_relationships, INHERITANCE_PREDICATE,
)
from ontology_integration.sqlite_neem import SOURCE_NS

SHA = "a"*64

def fixture(tmp_path: Path):
    path=tmp_path/"pickup.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE DesignatorDAO (database_id INTEGER PRIMARY KEY, polymorphic_type TEXT);
        CREATE TABLE ActionDescriptionDAO (
          database_id INTEGER PRIMARY KEY REFERENCES DesignatorDAO(database_id));
        CREATE TABLE PickUpActionDAO (
          database_id INTEGER PRIMARY KEY REFERENCES ActionDescriptionDAO(database_id),
          _object_designator_id INTEGER REFERENCES DesignatorDAO(database_id),
          tolerate_grasp_stall BOOLEAN, started_at DATETIME, payload BLOB);
        CREATE TABLE PlanNodeDAO (database_id INTEGER PRIMARY KEY,status TEXT);
        INSERT INTO DesignatorDAO VALUES(1,'PickUpActionDAO');
        INSERT INTO DesignatorDAO VALUES(2,'ObjectDesignatorDAO');
        INSERT INTO ActionDescriptionDAO VALUES(1);
        INSERT INTO PickUpActionDAO VALUES
          (1,2,0,'2026-10-14 12:56:59.465848',X'00FF');
        INSERT INTO PlanNodeDAO VALUES(1,'NOT_STARTED');
        INSERT INTO PlanNodeDAO VALUES(2,'SUCCEEDED');
        """)
    return path

def test_inheritance_fk_blob_and_naive_time(tmp_path):
    path=fixture(tmp_path)
    page=extract_page(path,neem_id="trial",ontology_sha256=SHA,table="PickUpActionDAO")
    assert page.unmatched_foreign_keys == 0
    assert page.next_key is None
    assert any(a.predicate.value==INHERITANCE_PREDICATE and
               "ActionDescriptionDAO:1" in a.object.value for a in page.batch.assertions)
    assert any(a.predicate.value.endswith("/_object_designator_id") and
               "DesignatorDAO:2" in a.object.value for a in page.batch.assertions)
    flag=next(a for a in page.batch.assertions if a.predicate.value.endswith("/tolerate_grasp_stall"))
    assert flag.object.datatype == str(XSD.boolean) and flag.object.value=="false"
    instant=next(a for a in page.batch.assertions if a.predicate.value.endswith("/started_at"))
    assert instant.object.value == "2026-10-14 12:56:59.465848"
    assert instant.object.datatype is None
    assert any(a.object.value.startswith("urn:neem:blob:sha256:") for a in page.batch.assertions)

def test_paging_and_status_fidelity(tmp_path):
    path=fixture(tmp_path)
    first=extract_page(path,neem_id="trial",ontology_sha256=SHA,
                       table="PlanNodeDAO",page_size=1)
    second=extract_page(path,neem_id="trial",ontology_sha256=SHA,
                        table="PlanNodeDAO",page_size=1,after_key=first.next_key)
    assert first.next_key=="1" and second.next_key is None
    statuses=[a.object.value for page in (first,second) for a in page.batch.assertions
              if a.predicate.value.endswith("/status")]
    assert statuses==["NOT_STARTED","SUCCEEDED"]
    assert all(a.status.value=="candidate" for page in (first,second) for a in page.batch.assertions)
    assert first.batch.batch_id == extract_page(path,neem_id="trial",ontology_sha256=SHA,
                       table="PlanNodeDAO",page_size=1).batch.batch_id

def test_profile_and_reject_invalid(tmp_path):
    path=fixture(tmp_path)
    report=profile_relationships(path)
    assert any(e["table"]=="PickUpActionDAO" and
               e["target_table"]=="ActionDescriptionDAO" for e in report["inheritance_edges"])
    assert report["plan_lifecycle_values"]=={"NOT_STARTED":1,"SUCCEEDED":1}
    with pytest.raises(ValueError):
        extract_page(path,neem_id="trial",ontology_sha256=SHA,
                     table="PickUpActionDAO",page_size=0)
    with pytest.raises(ValueError):
        extract_page(path,neem_id="trial",ontology_sha256=SHA,table="MissingDAO")
