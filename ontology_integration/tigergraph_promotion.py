"""Approved-only ontology fact projection; does not write into GraphRAG graph.

A two-level authorization is required: an approved assertion lifecycle AND
a matching signed-off approval manifest bound to the ontology fingerprint.
"""
from __future__ import annotations
from hashlib import sha256
import json
from .assertions import Assertion, AssertionStatus, TermKind

PROMOTABLE=frozenset((AssertionStatus.VALIDATED,AssertionStatus.ASSERTED))

def approved_projection(assertions, *, approved_assertion_ids, ontology_sha256,
                        reviewer, approval_reason):
    if not reviewer or not reviewer.strip() or not approval_reason or not approval_reason.strip():
        raise ValueError("Reviewer and approval reason are mandatory")
    allow=set(approved_assertion_ids)
    if not allow:
        raise ValueError("Empty approval list: fail closed")
    if len(allow)!=len(list(approved_assertion_ids)):
        raise ValueError("Approval manifest contains duplicate assertion IDs")
    assertions=tuple(assertions)
    by_id={a.assertion_id:a for a in assertions}
    if len(by_id)!=len(assertions):
        raise ValueError("Duplicate assertion identities")
    unknown=allow-by_id.keys()
    if unknown:
        raise ValueError("Approval references nonexistent assertions")
    facts=[]
    for assertion_id in sorted(allow):
        a=by_id[assertion_id]
        if a.status not in PROMOTABLE:
            raise ValueError(f"Assertion {assertion_id} has unapproved lifecycle: {a.status.value}")
        if a.ontology_sha256!=ontology_sha256:
            raise ValueError("Ontology version mismatch on approved assertion")
        if a.subject.kind!=TermKind.IRI or a.predicate.kind!=TermKind.IRI or a.object.kind==TermKind.BNODE:
            raise ValueError("Domain projection requires named RDF terms")
        if a.graph is not None:
            raise ValueError("Named graph projection not implemented")
        facts.append({
            "assertion_id":a.assertion_id,
            "statement_id":a.statement_id,
            "subject_iri":a.subject.value,
            "predicate_iri":a.predicate.value,
            "object_kind":a.object.kind.value,
            "object_value":a.object.value,
            "object_datatype":a.object.datatype or "",
            "object_language":a.object.language or "",
            "source_type":a.evidence.source_type,
            "source_id":a.evidence.source_id,
            "source_locator":a.evidence.locator,
            "status":a.status.value,
            "ontology_sha256":a.ontology_sha256,
        })
    canonical=json.dumps(facts,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return {
        "format":"ontology-approved-facts-v1",
        "policy":"projection_only_no_live_graph_write",
        "ontology_sha256":ontology_sha256,
        "reviewer":reviewer,
        "approval_reason":approval_reason,
        "fact_count":len(facts),
        "facts":facts,
        "facts_sha256":sha256(canonical.encode("utf-8")).hexdigest(),
    }

def verify_approved_projection(plan):
    if plan.get("format")!="ontology-approved-facts-v1":
        raise ValueError("Wrong projection format")
    facts=plan.get("facts")
    if not isinstance(facts,list) or len(facts)!=plan.get("fact_count"):
        raise ValueError("Malformed approved fact plan")
    if len({f["assertion_id"] for f in facts})!=len(facts):
        raise ValueError("Duplicate facts")
    payload=json.dumps(facts,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    if sha256(payload.encode("utf-8")).hexdigest()!=plan.get("facts_sha256"):
        raise ValueError("Approved plan checksum mismatch")
    if any(f["ontology_sha256"]!=plan["ontology_sha256"] or
           f["status"] not in ("validated","asserted") for f in facts):
        raise ValueError("Approved plan contains untrusted facts")
    return True
