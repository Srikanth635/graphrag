"""Read-only SQLite/OWL mapping quality gate; never infer execution from plans."""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

BASE = "http://aicor.knowledge/l2-ontology.owl#"
DESIGNATOR = BASE + "Designator"

def quality_report(sqlite_path, ontology_path, *, neem_id):
    if not neem_id or not neem_id.strip():
        raise ValueError("neem_id must not be empty")
    ontology = Graph().parse(str(ontology_path), format="turtle")
    if (URIRef(DESIGNATOR), RDF.type, OWL.Class) not in ontology:
        raise ValueError("Ontology lacks explicitly mapped Designator class")
    db = sqlite3.connect(Path(sqlite_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        names = sorted(row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        populations = {}
        fk_total = inherits = 0
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            populations[name] = db.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0]
            fks = list(db.execute("PRAGMA foreign_key_list(" + quoted + ")"))
            fk_total += len(fks)
            inherits += sum(1 for fk in fks if fk[3] == "database_id" and fk[4] == "database_id")
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        violations = len(db.execute("PRAGMA foreign_key_check").fetchall())
        candidates = []
        if "DesignatorDAO" in names:
            for (id_,) in db.execute('SELECT database_id FROM "DesignatorDAO" ORDER BY database_id'):
                candidates.append({
                    "source_table": "DesignatorDAO", "source_pk": id_,
                    "class_iri": DESIGNATOR, "status": "candidate",
                    "evidence": f"DesignatorDAO/{id_}", "mapping": "explicit_sql_owl_mapping"})
        statuses = {}
        if "PlanNodeDAO" in names:
            statuses = {str(v): n for v,n in db.execute(
                'SELECT status, COUNT(*) FROM "PlanNodeDAO" GROUP BY status')}
        refs = 0
        if "ActionNodeDAO" in names:
            refs = db.execute(
                'SELECT COUNT(*) FROM "ActionNodeDAO" WHERE _execution_data_id IS NOT NULL'
            ).fetchone()[0]
        review = [
            {"source": "PlanNodeDAO", "proposed_owl": BASE+"Execution",
             "decision": "not_mapped", "reason": "Plan lifecycle is not execution evidence"},
            {"source": "PlanEdgeDAO", "proposed_owl": BASE+"hasSubaction",
             "decision": "not_mapped", "reason": "Plan hierarchy does not imply action-part semantics"},
            {"source": "DesignatorNodeDAO._designator_id",
             "proposed_owl": BASE+"realizesDesignator", "decision": "not_mapped",
             "reason": "Reference to a designator is not an observed Execution"},
            {"source": "PickUpActionDAO", "proposed_owl": BASE+"Execution",
             "decision": "not_mapped", "reason": "Action description is not execution evidence"},
        ]
        total = sum(populations.values())
        return {
            "format": "neem-mapping-audit-v1", "neem_id": neem_id,
            "source_sha256": hashlib.sha256(Path(sqlite_path).read_bytes()).hexdigest(),
            "ontology_sha256": hashlib.sha256(Path(ontology_path).read_bytes()).hexdigest(),
            "integrity": integrity, "foreign_key_violations": violations,
            "table_count": len(names),
            "populated_tables": sum(n > 0 for n in populations.values()),
            "total_source_rows": total, "declared_fk_links": fk_total,
            "inheritance_fk_links": inherits,
            "designator_owl_candidates": candidates, "candidate_count": len(candidates),
            "plan_node_states": statuses,
            "action_node_execution_refs": refs,
            "execution_data_records": populations.get("ExecutionDataDAO", 0),
            "review_required": review,
            "coverage": {
                "raw_sql": "all_tables_available_to_read_only_staging",
                "mapped_owl_class": "Designator",
                "unmapped_sql_rows": total-len(candidates),
                "ontology_mapping_is_exhaustive": False,
            },
        }
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite")
    parser.add_argument("ontology")
    parser.add_argument("--neem-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = quality_report(args.sqlite, args.ontology, neem_id=args.neem_id)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: report[k] for k in (
        "table_count", "total_source_rows", "candidate_count", "foreign_key_violations")}))

if __name__ == "__main__":
    main()
