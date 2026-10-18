"""Conservative SQL-to-OWL mapping of recorded NEEM designators.

Mappings are explicit reviewed decisions, not string similarity or inference.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3
from rdflib.namespace import RDF
from .assertions import Assertion, RDFTerm, SourceEvidence, TermKind
from .pipeline_contract import AssertionBatch, OntologyVocabulary
from .sqlite_neem import table_iri

BASE = "http://aicor.knowledge/l2-ontology.owl#"

def _connect(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)

@dataclass(frozen=True)
class ClassMapping:
    table: str
    class_iri: str
    rationale: str

DEFAULT_CLASS_MAPPINGS = (
    ClassMapping("DesignatorDAO", BASE + "Designator",
                 "DesignatorDAO is the polymorphic base table for recorded designators."),
)

def mapped_designators(path: str | Path, *, neem_id: str,
                       ontology_path: str | Path,
                       class_mappings=DEFAULT_CLASS_MAPPINGS) -> AssertionBatch:
    """Emit candidate OWL rdf:type statements, preserving SQL row identity."""
    ontology = OntologyVocabulary.from_turtle(ontology_path)
    fingerprint = hashlib.sha256(Path(ontology_path).read_bytes()).hexdigest()
    conn = _connect(path)
    try:
        valid_tables = {x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        items = []
        for mapping in class_mappings:
            if mapping.table not in valid_tables:
                raise ValueError(f"Unknown source table: {mapping.table}")
            if mapping.class_iri not in ontology.classes:
                raise ValueError(f"Class is not declared in ontology: {mapping.class_iri}")
            if not mapping.rationale.strip():
                raise ValueError("Mapping must have a rationale")
            quoted = '"' + mapping.table.replace('"', '""') + '"'
            colnames = {x[1] for x in conn.execute("PRAGMA table_info(" + quoted + ")")}
            if "database_id" not in colnames:
                raise ValueError("Mapping requires database_id primary key")
            ids = conn.execute("SELECT database_id FROM " + quoted + " ORDER BY database_id")
            for (row_id,) in ids:
                item = Assertion(
                    subject=RDFTerm(TermKind.IRI, table_iri(neem_id, mapping.table, row_id)),
                    predicate=RDFTerm(TermKind.IRI, str(RDF.type)),
                    object=RDFTerm(TermKind.IRI, mapping.class_iri),
                    ontology_sha256=fingerprint,
                    evidence=SourceEvidence(
                        source_type="neem_sqlite", source_id=neem_id,
                        locator=f"{mapping.table}/{row_id}",
                        method="explicit_sql_owl_mapping",
                        excerpt=mapping.rationale),
                )
                if not ontology.check(item, strict=True).accepted:
                    raise ValueError("Mapped assertion failed declared vocabulary check")
                items.append(item)
        return AssertionBatch(tuple(items), batch_label="neem_owl_candidates:" + neem_id)
    finally:
        conn.close()

def summarize_mapping(path: str | Path) -> dict:
    """Report source facts without conflating plans and executions."""
    with _connect(path) as conn:
        return {
            "designators": conn.execute("SELECT COUNT(*) FROM DesignatorDAO").fetchone()[0],
            "designator_node_links": conn.execute(
                "SELECT COUNT(*) FROM DesignatorNodeDAO WHERE _designator_id IS NOT NULL"
            ).fetchone()[0],
            "action_node_execution_refs": conn.execute(
                "SELECT COUNT(*) FROM ActionNodeDAO WHERE _execution_data_id IS NOT NULL"
            ).fetchone()[0],
            "plan_states": {
                state: count for state, count in conn.execute(
                    "SELECT status, COUNT(*) FROM PlanNodeDAO GROUP BY status")
            },
            "mapped_owl_classes": [m.class_iri for m in DEFAULT_CLASS_MAPPINGS],
            "unmapped_sql_structures": [
                "PlanNodeDAO", "PlanEdgeDAO", "ActionNodeDAO", "PickUpActionDAO"
            ],
        }
