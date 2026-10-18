"""Joined-inheritance canonical identity tests."""
import sqlite3
from pathlib import Path
import pytest
from ontology_integration.neem_identity import resolve_identity

def test_canonical_identity_across_inherited_rows(tmp_path: Path):
    db=sqlite3.connect(tmp_path/"inheritance.sqlite")
    db.executescript("""
    CREATE TABLE DesignatorDAO(database_id INTEGER PRIMARY KEY);
    CREATE TABLE ActionDescriptionDAO(database_id INTEGER PRIMARY KEY
      REFERENCES DesignatorDAO(database_id));
    CREATE TABLE PickUpActionDAO(database_id INTEGER PRIMARY KEY
      REFERENCES ActionDescriptionDAO(database_id),
      _object_designator_id INTEGER REFERENCES DesignatorDAO(database_id));
    INSERT INTO DesignatorDAO VALUES(4);
    INSERT INTO DesignatorDAO VALUES(5);
    INSERT INTO ActionDescriptionDAO VALUES(4);
    INSERT INTO PickUpActionDAO VALUES(4,5);
    """)
    derived=resolve_identity(db,"PickUpActionDAO",4,neem_id="pickup")
    parent=resolve_identity(db,"DesignatorDAO",4,neem_id="pickup")
    assert derived.canonical_iri==parent.canonical_iri
    assert derived.lineage == ("PickUpActionDAO","ActionDescriptionDAO","DesignatorDAO")
    other=resolve_identity(db,"DesignatorDAO",5,neem_id="pickup")
    assert other.canonical_iri!=derived.canonical_iri
    with pytest.raises(ValueError):
        resolve_identity(db,"PickUpActionDAO",99,neem_id="pickup")
    db.close()

def test_unknown_table_rejected(tmp_path: Path):
    db=sqlite3.connect(tmp_path/"empty.sqlite")
    with pytest.raises(ValueError,match="Unknown"):
        resolve_identity(db,"AbsentDAO",4,neem_id="pickup")
    db.close()
