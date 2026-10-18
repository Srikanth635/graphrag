"""Read-only SQLite NEEM staging adapter.

Emit source-faithful RDF assertions using SQL-schema IRIs. Do NOT interpret
DAO table names as OWL class names or foreign keys as OWL properties.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote
from rdflib.namespace import RDF, XSD
from .assertions import Assertion, RDFTerm, SourceEvidence, TermKind
from .pipeline_contract import AssertionBatch

SOURCE_NS = "urn:neem:sql-schema:"
ENTITY_NS = "urn:neem:entity:"


def term_iri(value):
    return RDFTerm(TermKind.IRI, value)


def term_lit(value):
    if isinstance(value, bool):
        return RDFTerm(TermKind.LITERAL, str(value).lower(), str(XSD.boolean))
    if isinstance(value, int):
        return RDFTerm(TermKind.LITERAL, str(value), str(XSD.integer))
    if isinstance(value, float):
        return RDFTerm(TermKind.LITERAL, str(value), str(XSD.double))
    return RDFTerm(TermKind.LITERAL, str(value))


def table_iri(neem_id, table, row_id):
    return ENTITY_NS + quote(neem_id, safe="") + ":" + quote(table, safe="") + ":" + quote(str(row_id), safe="")


def source_predicate(table, column):
    return SOURCE_NS + quote(table, safe="") + "/" + quote(column, safe="")


def quote_sql_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _connect(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def profile_sqlite(path):
    db = _connect(path)
    try:
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        entries = []
        for name in tables:
            n = db.execute("SELECT COUNT(*) FROM " + quote_sql_identifier(name)).fetchone()[0]
            cols = [{"name": r[1], "type": r[2], "primary_key": bool(r[5])}
                    for r in db.execute("PRAGMA table_info(" + quote_sql_identifier(name) + ")")]
            fks = [{"column": r[3], "target_table": r[2], "target_column": r[4]}
                   for r in db.execute("PRAGMA foreign_key_list(" + quote_sql_identifier(name) + ")")]
            entries.append({"table": name, "rows": n, "columns": cols, "foreign_keys": fks})
        return {"tables": entries, "table_count": len(entries),
                "populated_table_count": sum(e["rows"] > 0 for e in entries)}
    finally:
        db.close()


def export_sqlite(path, *, neem_id, ontology_sha256, tables, max_rows=None):
    """Stage selected source tables without claiming ontology alignment."""
    if not neem_id.strip():
        raise ValueError("neem_id is required")
    db = _connect(path)
    db.row_factory = sqlite3.Row
    try:
        available = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if any(t not in available for t in tables):
            raise ValueError("Unknown source table")
        assertions = []
        for table in sorted(set(tables)):
            info = list(db.execute("PRAGMA table_info(" + quote_sql_identifier(table) + ")"))
            pk = [r["name"] for r in info if r["pk"]]
            if len(pk) != 1:
                raise ValueError(f"Expected one primary key in {table}")
            pk_col = pk[0]
            fks = {r["from"]: (r["table"], r["to"])
                   for r in db.execute("PRAGMA foreign_key_list(" + quote_sql_identifier(table) + ")")}
            sql = "SELECT * FROM " + quote_sql_identifier(table) + " ORDER BY " + quote_sql_identifier(pk_col)
            if max_rows is not None:
                if max_rows < 0:
                    raise ValueError("max_rows must be nonnegative")
                sql += " LIMIT " + str(max_rows)
            for row in db.execute(sql):
                subject = term_iri(table_iri(neem_id, table, row[pk_col]))
                evidence = SourceEvidence("neem_sqlite", neem_id,
                    f"{table}/{row[pk_col]}", "sqlite_deterministic")
                assertions.append(Assertion(subject, term_iri(str(RDF.type)),
                    term_iri(SOURCE_NS + quote(table, safe="")), evidence, ontology_sha256))
                for column in row.keys():
                    value = row[column]
                    if value is None or column == pk_col:
                        continue
                    if column in fks and fks[column][1] == "database_id":
                        obj = term_iri(table_iri(neem_id, fks[column][0], value))
                    else:
                        obj = term_lit(value)
                    assertions.append(Assertion(subject, term_iri(source_predicate(table, column)),
                        obj, evidence, ontology_sha256))
        return AssertionBatch(tuple(assertions), batch_label="neem_sqlite:" + neem_id)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite")
    parser.add_argument("--neem-id", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--table", action="append", required=True)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    fingerprint = hashlib.sha256(Path(args.ontology).read_bytes()).hexdigest()
    batch = export_sqlite(args.sqlite, neem_id=args.neem_id,
                          ontology_sha256=fingerprint, tables=args.table, max_rows=args.max_rows)
    Path(args.output).write_text(batch.to_jsonl(), encoding="utf-8")
    print(json.dumps({"assertions": len(batch.assertions), "batch_id": batch.batch_id}))


if __name__ == "__main__":
    main()
