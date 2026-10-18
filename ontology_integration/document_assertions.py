"""Strict evidence-to-assertion bridge for preprocessed documents.

Candidate extraction is external (LLM or rule engine). This module rejects
unsupported claims and only emits Milestone 3 candidate assertions after
checking contract membership and exact text evidence.
"""
from __future__ import annotations
import hashlib
from rdflib.namespace import RDF
from .assertions import Assertion, RDFTerm, SourceEvidence, TermKind
from .pipeline_contract import AssertionBatch
from .document_chunks import verify_chunk

def accept_candidates(chunk, original_text: str, contract: dict, records: list[dict]) -> AssertionBatch:
    if not verify_chunk(chunk,original_text):
        raise ValueError("Source chunk evidence does not match original document")
    if contract.get("contract_version") != "1":
        raise ValueError("Unsupported extraction contract")
    allowed_classes={c["iri"] for c in contract["classes"]}
    allowed_properties={p["iri"] for p in contract["properties"]}
    approved=[]
    for i,record in enumerate(records):
        pred=record["predicate_iri"]
        obj=record["object"]
        subject=record["subject_iri"]
        local_start,local_end=record["evidence_start"],record["evidence_end"]
        if not isinstance(local_start,int) or not isinstance(local_end,int):
            raise ValueError("Evidence offsets must be integers")
        if not 0<=local_start<local_end<=len(chunk.text):
            raise ValueError("Evidence span outside chunk")
        excerpt=record["evidence_text"]
        if not isinstance(excerpt,str) or chunk.text[local_start:local_end]!=excerpt or not excerpt.strip():
            raise ValueError("Candidate evidence does not match source verbatim")
        if pred==str(RDF.type):
            if obj.get("kind") != "iri" or obj.get("value") not in allowed_classes:
                raise ValueError("Unapproved ontology class")
        elif pred not in allowed_properties:
            raise ValueError("Unapproved ontology predicate")
        s=RDFTerm(TermKind.IRI,subject)
        p=RDFTerm(TermKind.IRI,pred)
        o=RDFTerm(**obj)
        evidence=SourceEvidence(
            source_type="document",source_id=chunk.document_id,
            locator=f"sha256:{chunk.document_sha256}/chars:{chunk.start+local_start}-{chunk.start+local_end}",
            method="ontology_guided_candidate",
            excerpt=excerpt)
        approved.append(Assertion(
            subject=s,predicate=p,object=o,evidence=evidence,
            ontology_sha256=contract["ontology_sha256"],
            confidence=record.get("confidence")))
    return AssertionBatch(tuple(approved),batch_label="document:"+chunk.document_id)


def extraction_request(chunk, contract: dict) -> dict:
    """JSON-friendly prompt payload; no LLM/network service is invoked."""
    return {
        "chunk_id":chunk.chunk_id,
        "document_sha256":chunk.document_sha256,
        "text":chunk.text,
        "contract":contract,
        "instructions":[
            "Use only ontology class and property IRIs from the contract.",
            "Emit candidate facts only when the supplied text supports them.",
            "Report the verbatim evidence_text and its character offsets inside the chunk.",
            "Do not invent entity identifiers, action executions, or existential fillers.",
            "Use explicit confidence only when calibrated; omission is allowed.",
            "Never treat OWL restrictions as automatically observed facts.",
        ],
    }
