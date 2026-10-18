"""Offline fidelity comparison of trusted SQL dumps and SQLite snapshots.

Never execute untrusted SQL dumps: executescript can run arbitrary SQL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

def compare_trusted_dump(sqlite_file, sql_dump):
    """Compare every table's row count plus relational and integrity checks.

    Source SQL dump is executed in an isolated in-memory SQLite connection;
    caller must trust the dump. Value-by-value equality is NOT established.
    """
    original = sqlite3.connect(Path(sqlite_file).resolve().as_uri()+"?mode=ro",uri=True)
    replay = sqlite3.connect(":memory:")
    try:
        replay.executescript(Path(sql_dump).read_text(encoding="utf-8"))
        def tables(db):
            return {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        left, right = tables(original), tables(replay)
        counts = []
        for t in sorted(left | right):
            quoted = '"' + t.replace('"','""') + '"'
            a = original.execute("SELECT COUNT(*) FROM "+quoted).fetchone()[0] if t in left else None
            b = replay.execute("SELECT COUNT(*) FROM "+quoted).fetchone()[0] if t in right else None
            if a != b:
                counts.append({"table":t,"sqlite_count":a,"dump_count":b})
        integrity = {
            "sqlite": original.execute("PRAGMA integrity_check").fetchone()[0],
            "dump": replay.execute("PRAGMA integrity_check").fetchone()[0],
        }
        fk = {
            "sqlite": len(original.execute("PRAGMA foreign_key_check").fetchall()),
            "dump": len(replay.execute("PRAGMA foreign_key_check").fetchall()),
        }
        return {"sqlite_sha256": hashlib.sha256(Path(sqlite_file).read_bytes()).hexdigest(),
                "dump_sha256": hashlib.sha256(Path(sql_dump).read_bytes()).hexdigest(),
                "sqlite_tables": len(left), "dump_tables": len(right),
                "missing_in_dump": sorted(left-right),
                "missing_in_sqlite": sorted(right-left),
                "row_count_mismatches": counts,
                "foreign_key_violations": fk, "integrity": integrity,
                "counts_match": not counts and left == right,
                "note": "Row count fidelity only; no row-value equivalence claim"}
    finally:
        replay.close()
        original.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite")
    parser.add_argument("trusted_sql_dump")
    parser.add_argument("--output",required=True)
    args = parser.parse_args()
    result = compare_trusted_dump(args.sqlite,args.trusted_sql_dump)
    Path(args.output).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"counts_match":result["counts_match"],
                      "sqlite_tables":result["sqlite_tables"]}))

if __name__=="__main__":
    main()
