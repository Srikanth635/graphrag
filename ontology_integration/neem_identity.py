"""Joined-table SQL identity reconstruction without asserting OWL sameAs.

Rows in inheritance tables represent one ORM object only when they have an
existing primary-key foreign-key parent. The root row is the stable key.
"""
from __future__ import annotations
from dataclasses import dataclass
import sqlite3
from pathlib import Path
from .sqlite_neem import table_iri

@dataclass(frozen=True)
class IdentityResolution:
    source_table: str
    database_id: int
    root_table: str
    canonical_iri: str
    lineage: tuple[str, ...]


def resolve_identity(db: sqlite3.Connection, table: str, database_id: int,
                     *, neem_id: str) -> IdentityResolution:
    """Follow valid joined-inheritance PK->FK links, not ordinary references."""
    available = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in available:
        raise ValueError("Unknown DAO table")
    lineage = []
    current = table
    while True:
        if current in lineage:
            raise ValueError("Inheritance cycle detected")
        lineage.append(current)
        q = '"' + current.replace('"', '""') + '"'
        info = list(db.execute("PRAGMA table_info(" + q + ")"))
        keys = [r[1] for r in info if r[5]]
        if keys != ["database_id"]:
            raise ValueError("Expected database_id primary key: " + current)
        if not db.execute("SELECT 1 FROM " + q + " WHERE database_id=? LIMIT 1",
                          (database_id,)).fetchone():
            raise ValueError(f"Row {database_id} absent in {current}")
        parents = [r[2] for r in db.execute("PRAGMA foreign_key_list(" + q + ")")
                   if r[3] == "database_id" and r[4] == "database_id"]
        if len(parents) > 1:
            raise ValueError("Ambiguous multiple SQL inheritance parents")
        if not parents:
            break
        current = parents[0]
    return IdentityResolution(table, database_id, current,
                              table_iri(neem_id,current,database_id), tuple(lineage))


def resolve_identity_path(sqlite_path: str | Path, table: str,
                          database_id: int, *, neem_id: str) -> IdentityResolution:
    db = sqlite3.connect(Path(sqlite_path).resolve().as_uri() + "?mode=ro",uri=True)
    try:
        return resolve_identity(db,table,database_id,neem_id=neem_id)
    finally:
        db.close()
