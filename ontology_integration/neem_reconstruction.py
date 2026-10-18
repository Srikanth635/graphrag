"""Schema-aware, read-only NEEM SQLite reconstruction.

This adapter reconstructs DAO inheritance and source FK links without claiming
that planning data describes executed actions. It never executes SQL from input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from rdflib.namespace import RDF, XSD
from .assertions import Assertion, RDFTerm, SourceEvidence, TermKind
from .pipeline_contract import AssertionBatch
from .sqlite_neem import table_iri, source_predicate, SOURCE_NS, quote_sql_identifier

INHERITANCE_PREDICATE = SOURCE_NS + "inheritsRowFrom"
BLOB_PREDICATE = SOURCE_NS + "binarySha256"
TIME_PREDICATE = SOURCE_NS + "timestampLexical"
@dataclass(frozen=True)
class Page:
    batch: AssertionBatch
    next_key: str | None
    table: str
    inspected_rows: int
    unmatched_foreign_keys: int


def open_readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _iri(iri):
    return RDFTerm(TermKind.IRI, iri)


def _value(value, type_name, table, column):
    declared = type_name.upper()
    if isinstance(value, bytes):
        return _iri("urn:neem:blob:sha256:" + hashlib.sha256(value).hexdigest())
    if "BOOL" in declared and isinstance(value, int):
        return RDFTerm(TermKind.LITERAL, str(bool(value)).lower(), str(XSD.boolean))
    if "DATE" in declared or "TIME" in declared:
        # Source timestamps are timezone-naive: retain lexical form; do not infer UTC.
        return RDFTerm(TermKind.LITERAL, str(value))
    if isinstance(value, int):
        return RDFTerm(TermKind.LITERAL, str(value), str(XSD.integer))
    if isinstance(value, float):
        return RDFTerm(TermKind.LITERAL, repr(value), str(XSD.double))
    return RDFTerm(TermKind.LITERAL, str(value))


def _pk_and_fks(db, table):
    q = quote_sql_identifier(table)
    cols = db.execute("PRAGMA table_info(" + q + ")").fetchall()
    pks = [r["name"] for r in cols if r["pk"]]
    if len(pks) != 1:
        raise ValueError("Exactly one primary key required: " + table)
    fks = {r["from"]: (r["table"], r["to"])
           for r in db.execute("PRAGMA foreign_key_list(" + q + ")")}
    return pks[0], {r["name"]: r["type"] for r in cols}, fks


def profile_relationships(path):
    """Inspect FK topology and lifecycle values; no ontology promotion."""
    db = open_readonly(path)
    try:
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        inheritance = []
        foreign_keys = []
        for table in tables:
            key, _, fks = _pk_and_fks(db, table)
            for col, (target, target_key) in sorted(fks.items()):
                edge = {"table": table, "column": col,
                        "target_table": target, "target_column": target_key}
                (inheritance if col == key and key == "database_id"
                 and target_key == "database_id" else foreign_keys).append(edge)
        counts = {}
        for table in ("PlanNodeDAO", "PlanEdgeDAO", "DesignatorDAO",
                      "ActionNodeDAO", "ExecutionDataDAO"):
            if table in tables:
                counts[table] = db.execute(
                    "SELECT COUNT(*) FROM " + quote_sql_identifier(table)).fetchone()[0]
        statuses = {}
        if "PlanNodeDAO" in tables:
            statuses = {str(r[0]): r[1] for r in db.execute(
                "SELECT status, COUNT(*) FROM PlanNodeDAO GROUP BY status")}
        return {"inheritance_edges": inheritance, "foreign_key_edges": foreign_keys,
                "record_counts": counts, "plan_lifecycle_values": statuses}
    finally:
        db.close()


def extract_page(path, *, neem_id, ontology_sha256, table,
                 after_key=None, page_size=500, check_fk=True):
    """Read one stable, ordered page. Checkpoint is (table, last primary key).

    Page checkpoint is valid for immutable snapshots only: changing databases
    between pages invalidates reproducibility.
    """
    if page_size < 1 or not neem_id or not neem_id.strip():
        raise ValueError("Positive page_size and nonempty neem_id required")
    db = open_readonly(path)
    try:
        available = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in available:
            raise ValueError("Unknown table: " + table)
        pk, declared, fks = _pk_and_fks(db, table)
        q = quote_sql_identifier(table)
        sql = "SELECT * FROM " + q
        params = []
        if after_key is not None:
            sql += " WHERE " + quote_sql_identifier(pk) + " > ?"
            params.append(after_key)
        sql += " ORDER BY " + quote_sql_identifier(pk) + " LIMIT ?"
        params.append(page_size + 1)
        rows = db.execute(sql, params).fetchall()
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        assertions = []
        missing = 0
        for row in rows:
            sid = table_iri(neem_id, table, row[pk])
            evidence = SourceEvidence("neem_sqlite", neem_id,
                        f"{table}/{row[pk]}", "sqlite_schema_reconstruction")
            def add(pred, value):
                assertions.append(Assertion(_iri(sid), _iri(pred), value,
                                            evidence, ontology_sha256))
            add(str(RDF.type), _iri(SOURCE_NS + quote(table, safe="")))
            for col in row.keys():
                val = row[col]
                if col == pk or val is None:
                    continue
                if col in fks and fks[col][1] == "database_id":
                    dest, dest_pk = fks[col]
                    if check_fk:
                        exists = db.execute(
                            "SELECT 1 FROM " + quote_sql_identifier(dest)
                            + " WHERE " + quote_sql_identifier(dest_pk) + "=? LIMIT 1",
                            (val,)).fetchone()
                        if exists is None:
                            missing += 1
                    target = _iri(table_iri(neem_id, dest, val))
                    add(INHERITANCE_PREDICATE if col == pk else source_predicate(table,col), target)
                else:
                    add(source_predicate(table,col), _value(val,declared.get(col,""),table,col))
            # In joined inheritance the primary-key column is also an FK.
            if pk in fks and fks[pk][1] == "database_id":
                dest, dest_pk = fks[pk]
                if check_fk:
                    exists = db.execute(
                        "SELECT 1 FROM " + quote_sql_identifier(dest)
                        + " WHERE " + quote_sql_identifier(dest_pk) + "=? LIMIT 1",
                        (row[pk],)).fetchone()
                    if exists is None:
                        missing += 1
                add(INHERITANCE_PREDICATE, _iri(table_iri(neem_id, dest, row[pk])))
        return Page(AssertionBatch(tuple(assertions),
                    batch_label=f"neem_sqlite:{neem_id}:{table}"),
                    str(rows[-1][pk]) if has_more and rows else None,
                    table, len(rows), missing)
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sqlite")
    p.add_argument("--ontology", required=True)
    p.add_argument("--neem-id", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--page-size", type=int, default=500)
    p.add_argument("--after-key")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    fingerprint = hashlib.sha256(Path(args.ontology).read_bytes()).hexdigest()
    page = extract_page(args.sqlite, neem_id=args.neem_id,
                        ontology_sha256=fingerprint, table=args.table,
                        after_key=args.after_key, page_size=args.page_size)
    Path(args.output).write_text(page.batch.to_jsonl(), encoding="utf-8")
    print(json.dumps({"count": len(page.batch.assertions),
          "next_key": page.next_key, "missing_fk": page.unmatched_foreign_keys,
          "batch_id": page.batch.batch_id}))

if __name__ == "__main__":
    main()
