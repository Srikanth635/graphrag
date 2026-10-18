"""Offline NEEM SQL ingestion entrypoint with separated source and OWL outputs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .neem_export import export_snapshot, verify_export
from .semantic_map import mapped_designators
from .neem_quality_gate import quality_report
from .neem_full_scan import scan_database

def ingest_neem(sqlite_path, ontology_path, *, neem_id, output_dir,
                page_size=500, resume=False):
    """Run source staging and conservative OWL promotion; no graph writes."""
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    sql_dir=out/"source"
    if (out/"manifest.json").exists() and not resume:
        raise ValueError("Existing NEEM output; use resume or a new directory")
    source=export_snapshot(sqlite_path,ontology_path=ontology_path,
                           neem_id=neem_id,tables=None,output_dir=sql_dir,
                           page_size=page_size,resume=resume)
    verified=verify_export(sql_dir)
    if source!=verified:
        raise ValueError("Export manifest changed during verification")
    quality=quality_report(sqlite_path,ontology_path,neem_id=neem_id)
    if quality["integrity"]!="ok" or quality["foreign_key_violations"]:
        raise ValueError("Source SQLite integrity failed")
    coverage=scan_database(sqlite_path)
    if coverage["missing_fk_targets"]:
        raise ValueError("Unresolved source foreign keys")
    candidates=mapped_designators(sqlite_path,neem_id=neem_id,
                                  ontology_path=ontology_path)
    owl_file=out/"ontology_candidates.jsonl"
    owl_file.write_text(candidates.to_jsonl(),encoding="utf-8")
    audit_file=out/"quality.json"
    audit_file.write_text(json.dumps(quality,indent=2)+"\n",encoding="utf-8")
    summary={
        "schema_version":"neem-sql-acceptance-v1",
        "neem_id":neem_id,
        "source_sha256":quality["source_sha256"],
        "ontology_sha256":quality["ontology_sha256"],
        "sql_pages":len(source["pages"]),
        "sql_staged_assertions":sum(p["assertions"] for p in source["pages"]),
        "sql_source_rows":coverage["rows"],
        "sql_candidate_assertions_expected":coverage["candidate_source_assertions"],
        "sql_unmatched_fk_targets":coverage["missing_fk_targets"],
        "owl_candidates":len(candidates.assertions),
        "owl_candidate_batch_id":candidates.batch_id,
        "unreviewed_mapping_decisions":len(quality["review_required"]),
        "ontology_wide_semantic_mapping_complete":False,
        "tigergraph_ingestion_performed":False,
        "source_manifest":"source/manifest.json",
        "owl_candidate_file":"ontology_candidates.jsonl",
        "quality_file":"quality.json",
    }
    if summary["sql_staged_assertions"]!=summary["sql_candidate_assertions_expected"]:
        raise ValueError("Staged assertion count differs from full source scan")
    (out/"manifest.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("sqlite")
    parser.add_argument("--ontology",required=True)
    parser.add_argument("--neem-id",required=True)
    parser.add_argument("--output-dir",required=True)
    parser.add_argument("--page-size",type=int,default=500)
    parser.add_argument("--resume",action="store_true")
    a=parser.parse_args()
    result=ingest_neem(a.sqlite,a.ontology,neem_id=a.neem_id,
                       output_dir=a.output_dir,page_size=a.page_size,resume=a.resume)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
