"""Milestone 7: deterministic TigerGraph staging projection and guarded writer.

This intentionally does not project unreviewed ontology triples into GraphRAG's
trusted Entity/Relationship graph. It requires a separate staging vertex type.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import re
from typing import Iterable

from .assertions import Assertion, AssertionStatus

STAGING_VERTEX = "OntologyAssertionStage"
STAGING_ATTRIBUTES = frozenset({
    "statement_id", "subject_kind", "subject_value", "predicate_iri",
    "object_kind", "object_value", "object_datatype", "object_language",
    "source_type", "source_id", "source_locator", "source_method",
    "source_excerpt", "source_recorded_at", "derived_from_json", "ontology_sha256", "assertion_status",
    "confidence", "valid_from", "valid_to",
})
ALLOWED_STATUSES = frozenset({
    "candidate", "validated", "quarantined", "asserted",
    "inferred", "retracted",
})


def _value(term):
    return getattr(term.kind, "value", str(term.kind))


def stage_row(assertion: Assertion) -> dict:
    """Losslessly project core RDF and evidence fields to string attributes.

    The full canonical assertion remains in the JSONL source of truth; the
    staging graph is a queryable representation, not an RDF reasoner.
    """
    if assertion.graph is not None or assertion.subject.kind.value == "bnode" or assertion.object.kind.value == "bnode":
        raise ValueError("Named graphs and blank nodes need scoped staging support")
    if assertion.status.value not in ALLOWED_STATUSES:
        raise ValueError("Unknown assertion lifecycle status")
    return {
        "statement_id": assertion.statement_id,
        "subject_kind": _value(assertion.subject),
        "subject_value": assertion.subject.value,
        "predicate_iri": assertion.predicate.value,
        "object_kind": _value(assertion.object),
        "object_value": assertion.object.value,
        "object_datatype": assertion.object.datatype or "",
        "object_language": assertion.object.language or "",
        "source_type": assertion.evidence.source_type,
        "source_id": assertion.evidence.source_id,
        "source_locator": assertion.evidence.locator,
        "source_method": assertion.evidence.method,
        "source_excerpt": assertion.evidence.excerpt or "",
        "source_recorded_at": assertion.evidence.recorded_at or "",
        "derived_from_json": json.dumps(list(assertion.derived_from), separators=(",", ":")),
        "ontology_sha256": assertion.ontology_sha256,
        "assertion_status": assertion.status.value,
        "confidence": "" if assertion.confidence is None else format(assertion.confidence, ".17g"),
        "valid_from": assertion.valid_from or "",
        "valid_to": assertion.valid_to or "",
    }


def stage_plan(assertions: Iterable[Assertion], *, label="ontology-staging") -> dict:
    if not label.strip():
        raise ValueError("Nonempty staging label required")
    rows = {}
    for assertion in assertions:
        row = stage_row(assertion)
        key = assertion.assertion_id
        if key in rows and rows[key] != row:
            raise ValueError("Conflicting versions of the same assertion require event replay")
        rows[key] = row
    vertices = [{"id": id_, "attributes": rows[id_]} for id_ in sorted(rows)]
    payload = json.dumps(vertices, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"format": "ontology-tigergraph-stage-v1", "label": label,
            "vertex_type": STAGING_VERTEX,
            "count": len(vertices),
            "vertices": vertices,
            "payload_sha256": sha256(payload.encode("utf-8")).hexdigest(),
            "policy": "staging_only_no_trusted_graph_promotion"}


def write_plan(plan: dict, destination: str | Path) -> None:
    Path(destination).write_text(json.dumps(plan, sort_keys=True, indent=2,
                                            ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class StageWriteResult:
    attempted: int
    accepted: int
    dry_run: bool
    vertex_type: str


def _schema_attrs(connection, vertex_type):
    """Use the pyTigerGraph getVertexTypes API, but reject unknown return shapes."""
    result = connection.getVertexTypes()
    if not isinstance(result, list):
        raise ValueError("TigerGraph schema inspection returned an unexpected value")
    matching = [entry for entry in result
                if isinstance(entry, dict) and entry.get("Name") == vertex_type]
    if len(matching) != 1:
        raise ValueError("Dedicated staging vertex type is absent or ambiguous")
    entry = matching[0]
    pk = entry.get("PrimaryId")
    attrs = entry.get("Attributes")
    if not isinstance(pk, dict) or pk.get("AttributeName") != "assertion_id":
        raise ValueError("Unexpected staging primary ID definition")
    if not isinstance(attrs, list):
        raise ValueError("Staging schema has no inspectable attributes")
    names = {field.get("AttributeName") for field in attrs if isinstance(field, dict)}
    if not STAGING_ATTRIBUTES <= names:
        raise ValueError("Staging schema is missing required attributes")
    return names


def stage_to_tigergraph(plan: dict, *, connection, enable_write=False,
                        expected_graph=None) -> StageWriteResult:
    """Only perform writes when explicitly opted in and schema verified.

    Caller supplies an authenticated pyTigerGraph-compatible connection.
    No credentials, connection, or graph are created implicitly.
    """
    if plan.get("format") != "ontology-tigergraph-stage-v1" or plan.get("vertex_type") != STAGING_VERTEX:
        raise ValueError("Not an ontology assertion staging plan")
    vertices = plan.get("vertices")
    if not isinstance(vertices, list) or plan.get("count") != len(vertices):
        raise ValueError("Malformed staging payload")
    for item in vertices:
        if not isinstance(item, dict) or set(item) != {"id", "attributes"}:
            raise ValueError("Malformed staged vertex")
        if set(item["attributes"]) != STAGING_ATTRIBUTES:
            raise ValueError("Unexpected staging attribute fields")
    canonical = json.dumps(vertices, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if sha256(canonical.encode("utf-8")).hexdigest() != plan.get("payload_sha256"):
        raise ValueError("Staging payload integrity mismatch")
    if not enable_write:
        return StageWriteResult(len(vertices), 0, True, STAGING_VERTEX)
    if not expected_graph or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", expected_graph):
        raise ValueError("Explicit expected target graph required for writes")
    actual_graph = getattr(connection, "graphname", None)
    if actual_graph != expected_graph:
        raise ValueError("TigerGraph connection targets a different graph")
    _schema_attrs(connection, STAGING_VERTEX)
    accepted = 0
    for row in vertices:
        result = connection.upsertVertex(STAGING_VERTEX, row["id"], row["attributes"])
        if result not in (1, True):
            raise RuntimeError("TigerGraph refused staging upsert; inspect partial writes before retry")
        accepted += 1
    return StageWriteResult(len(vertices), accepted, False, STAGING_VERTEX)
