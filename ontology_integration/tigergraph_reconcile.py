"""Read-back reconciliation for a dedicated TigerGraph assertion staging graph.

A read-back mismatch is a hard failure, not an automatic rewrite.
"""
from __future__ import annotations
from dataclasses import dataclass
from .tigergraph_staging import STAGING_VERTEX, STAGING_ATTRIBUTES, stage_to_tigergraph

@dataclass(frozen=True)
class Reconciliation:
    expected: int
    matched: int
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]
    unexpected: tuple[str, ...]
    @property
    def complete(self):
        return not (self.missing or self.mismatched or self.unexpected) and self.expected == self.matched
    def to_dict(self):
        return dict(expected=self.expected, matched=self.matched, missing=list(self.missing),
                    mismatched=list(self.mismatched), unexpected=list(self.unexpected),
                    complete=self.complete)

def _returned_attributes(vertex):
    attributes = vertex.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("Unexpected TigerGraph vertex attributes response")
    result={}
    for key, value in attributes.items():
        if isinstance(value, dict) and "value" in value:
            value=value["value"]
        if value is None:
            value=""
        if not isinstance(value, str):
            raise ValueError("Staging attributes must be returned as strings")
        result[key]=value
    return result

def reconcile_staging(plan, *, connection, expected_graph):
    """Verify exact expected staging vertices using pyTigerGraph getVerticesById.

    The read-back account must be scoped to the dedicated staging graph.
    """
    stage_to_tigergraph(plan, connection=connection, enable_write=False)
    if not expected_graph or getattr(connection,"graphname",None)!=expected_graph:
        raise ValueError("Read-back graph identity mismatch")
    expected={v["id"]:v["attributes"] for v in plan["vertices"]}
    if len(expected)!=len(plan["vertices"]):
        raise ValueError("Duplicate staging IDs")
    found={}
    for id_ in sorted(expected):
        rows=connection.getVerticesById(STAGING_VERTEX,id_)
        if not isinstance(rows,list):
            raise ValueError("Unexpected TigerGraph read-back response")
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get("v_id"),(str,int)):
                raise ValueError("Unexpected TigerGraph vertex response")
            row_id=str(row["v_id"])
            if row_id in found:
                raise ValueError("Duplicate vertex returned by TigerGraph")
            found[row_id]=_returned_attributes(row)
    missing=tuple(sorted(expected.keys()-found.keys()))
    extra=tuple(sorted(found.keys()-expected.keys()))
    mismatch=tuple(sorted(k for k in expected.keys()&found.keys()
                          if found[k]!=expected[k]))
    matched=len(expected)-len(missing)-len(mismatch)
    return Reconciliation(len(expected),matched,missing,mismatch,extra)

def apply_and_reconcile(plan, *, connection, expected_graph, enable_write=False):
    """Writes require explicit opt-in. After writes always perform read-back."""
    result=stage_to_tigergraph(plan,connection=connection,expected_graph=expected_graph,
                               enable_write=enable_write)
    if result.dry_run:
        return {"dry_run":True,"attempted":result.attempted,"accepted":0}
    check=reconcile_staging(plan,connection=connection,expected_graph=expected_graph)
    if not check.complete:
        raise RuntimeError("Staging write/read-back failed reconciliation: "+str(check.to_dict()))
    return {"dry_run":False,"attempted":result.attempted,"accepted":result.accepted,
            "reconciliation":check.to_dict()}
