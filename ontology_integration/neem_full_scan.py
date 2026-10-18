"""Whole-database, read-only staging coverage audit.

Counts the RDF statements that neem_reconstruction.extract_page would stage,
without creating a large JSONL artifact. OWL assertion count is separate.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path

def scan_database(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        summary={"tables":len(tables),"populated_tables":0,"rows":0,
                 "candidate_source_assertions":0,"inheritance_assertions":0,
                 "ordinary_fk_assertions":0,"missing_fk_targets":0,
                 "binary_fields":0,"null_columns_skipped":0,
                 "source_properties_with_values":0,
                 "integrity":db.execute("PRAGMA integrity_check").fetchone()[0]}
        seen=set()
        for table in tables:
            q='"'+table.replace('"','""')+'"'
            cols=list(db.execute("PRAGMA table_info("+q+")"))
            pk=[r["name"] for r in cols if r["pk"]]
            if len(pk)!=1:
                raise ValueError("Expected one source primary key: "+table)
            fks={r["from"]:(r["table"],r["to"]) for r in db.execute(
                "PRAGMA foreign_key_list("+q+")")}
            populated=False
            for row in db.execute("SELECT * FROM "+q):
                populated=True
                summary["rows"]+=1
                summary["candidate_source_assertions"]+=1
                for column in row.keys():
                    if column==pk[0]:
                        continue
                    value=row[column]
                    if value is None:
                        summary["null_columns_skipped"]+=1
                        continue
                    summary["candidate_source_assertions"]+=1
                    seen.add((table,column))
                    if isinstance(value,bytes):
                        summary["binary_fields"]+=1
                    if column in fks:
                        summary["ordinary_fk_assertions"]+=1
                        dest,dest_col=fks[column]
                        target='"'+dest.replace('"','""')+'"'
                        target_column='"'+dest_col.replace('"','""')+'"'
                        if db.execute("SELECT 1 FROM "+target+" WHERE "+target_column+
                                      "=? LIMIT 1",(value,)).fetchone() is None:
                            summary["missing_fk_targets"]+=1
                if pk[0] in fks:
                    summary["inheritance_assertions"]+=1
                    summary["candidate_source_assertions"]+=1
                    dest,dest_col=fks[pk[0]]
                    target='"'+dest.replace('"','""')+'"'
                    target_column='"'+dest_col.replace('"','""')+'"'
                    if db.execute("SELECT 1 FROM "+target+" WHERE "+target_column+
                                  "=? LIMIT 1",(row[pk[0]],)).fetchone() is None:
                        summary["missing_fk_targets"]+=1
            if populated:
                summary["populated_tables"]+=1
        summary["source_properties_with_values"]=len(seen)
        return summary
    finally:
        db.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("sqlite")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=scan_database(args.sqlite)
    Path(args.output).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
if __name__=="__main__":
    main()
