"""Provider-neutral ontology-guided document ingestion; no implicit LLM calls.

Ingest preprocessed UTF-8 text from GraphRAG. ExtractionProvider receives a
validated ontology-scoped request and returns source-grounded candidate records.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
import json
import re

from rdflib.namespace import RDF

from .document_chunks import chunk_text, verify_chunk
from .document_modules import plan_extraction
from .document_assertions import extraction_request, accept_candidates
from .pipeline_contract import AssertionBatch


class ExtractionProvider(Protocol):
    def __call__(self, request: dict) -> list[dict]: ...


@dataclass(frozen=True)
class DocumentResult:
    document_id: str
    document_sha256: str
    chunks: int
    selected_chunks: int
    candidates: AssertionBatch
    skipped_chunks: tuple[str, ...]

    def to_dict(self):
        return {"document_id": self.document_id, "document_sha256": self.document_sha256,
                "chunks": self.chunks, "selected_chunks": self.selected_chunks,
                "skipped_chunks": list(self.skipped_chunks),
                "candidate_count": len(self.candidates.assertions),
                "batch_id": self.candidates.batch_id}


def mention_iri(document_id: str, document_sha256: str, start: int, end: int,
                *, label: str) -> str:
    """Stable mention ID; deliberately not a cross-document entity identity."""
    if not document_id.strip() or not re.fullmatch(r"[0-9a-f]{64}", document_sha256):
        raise ValueError("Invalid source document identity")
    if start < 0 or end <= start or not label.strip():
        raise ValueError("Invalid mention span")
    payload = json.dumps([document_id, document_sha256, start, end, label],
                         ensure_ascii=False, separators=(",", ":"))
    return "urn:ontologyrag:mention:" + sha256(payload.encode("utf-8")).hexdigest()


def _mention_from_span(mention: dict, chunk, full_text: str) -> str:
    begin, end = mention.get("start"), mention.get("end")
    label = mention.get("text")
    if not isinstance(begin, int) or isinstance(begin, bool) or not isinstance(end, int) or isinstance(end, bool):
        raise ValueError("Mention offsets must be integers")
    if not isinstance(label, str) or not 0 <= begin < end <= len(chunk.text):
        raise ValueError("Invalid mention evidence span")
    if chunk.text[begin:end] != label or not label.strip():
        raise ValueError("Mention text does not match original source")
    return mention_iri(chunk.document_id, chunk.document_sha256,
                       chunk.start + begin, chunk.start + end, label=label)


def _verify_and_normalize(records: list[dict], chunk, full_text: str) -> list[dict]:
    """Resolve declared mention spans to deterministic source-specific IRIs.

    Raw entity IRIs provided by an extractor are forbidden: an extractor
    cannot claim external entity co-reference without a verified linker.
    """
    result = []
    for record in records:
        row = dict(record)
        if ("subject_iri" in row or
            (isinstance(row.get("object"), dict) and row["object"].get("kind") == "iri"
             and row.get("predicate_iri") != str(RDF.type))):
            raise ValueError("Raw entity IRIs require a separate verified linker")
        subject = row.pop("subject_mention", None)
        if not isinstance(subject, dict):
            raise ValueError("Missing subject mention")
        row["subject_iri"] = _mention_from_span(subject, chunk, full_text)
        target = row.pop("object_mention", None)
        if target is not None:
            if row.get("predicate_iri") == str(RDF.type):
                raise ValueError("rdf:type must use an approved class IRI")
            if "object" in row:
                raise ValueError("Provide exactly one object form")
            row["object"] = {"kind": "iri", "value": _mention_from_span(target, chunk, full_text)}
        elif row.get("predicate_iri") != str(RDF.type) and "object" not in row:
            raise ValueError("Missing object")
        result.append(row)
    return result


def ingest_text(text: str, *, document_id: str, ontology_index: dict,
                provider: ExtractionProvider, max_chars: int = 1800,
                overlap: int = 160, top_k: int = 8,
                module_entries: int = 40, depth: int = 1) -> DocumentResult:
    """Complete local boundary from preprocessed text to candidate RDF batch.

    Provider calls are synchronous; callers configure remote LLMs separately.
    A missing ontology match produces no assertions, not invented ontology IRIs.
    """
    chunks = chunk_text(text, document_id=document_id,
                        max_chars=max_chars, overlap=overlap)
    assertions = []
    skipped = []
    selected = 0
    for chunk in chunks:
        if not verify_chunk(chunk, text):
            raise ValueError("Chunk no longer matches its source")
        plan = plan_extraction(chunk, ontology_index, top_k=top_k,
                               module_entries=module_entries, depth=depth)
        contract = plan["contract"]
        if contract is None:
            skipped.append(chunk.chunk_id)
            continue
        selected += 1
        request = extraction_request(chunk, contract)
        raw = provider(request)
        if not isinstance(raw, list):
            raise ValueError("Provider must return a list of candidate dictionaries")
        normalized = _verify_and_normalize(raw, chunk, text)
        batch = accept_candidates(chunk, text, contract, normalized)
        assertions.extend(batch.assertions)
    return DocumentResult(document_id, sha256(text.encode("utf-8")).hexdigest(),
                          len(chunks), selected,
                          AssertionBatch(tuple(assertions), batch_label="document:" + document_id),
                          tuple(skipped))


def replay_provider(responses: dict[str, list[dict]]) -> ExtractionProvider:
    """Offline replay keyed by exact chunk ID. Unknown requests are errors."""
    def respond(request: dict) -> list[dict]:
        key = request["chunk_id"]
        if key not in responses:
            raise ValueError("No recorded extraction response for chunk: " + key)
        return responses[key]
    return respond
