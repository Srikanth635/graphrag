"""Evidence-preserving document chunks for ontology-guided GraphRAG.

Input is preprocessed UTF-8 text. Reuse GraphRAG's existing PDF/document
preprocessor upstream; no duplicate PDF parser is introduced here.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import re

@dataclass(frozen=True)
class DocumentChunk:
    document_id: str
    chunk_id: str
    text: str
    start: int
    end: int
    document_sha256: str

    def __post_init__(self):
        if not self.document_id.strip() or not self.text or self.start < 0 or self.end <= self.start:
            raise ValueError("Invalid document chunk")
        if len(self.text) != self.end-self.start:
            raise ValueError("Chunk offsets must match text length")

    def to_dict(self):
        return vars(self).copy()


def chunk_text(text: str, *, document_id: str, max_chars: int = 1800,
               overlap: int = 160) -> tuple[DocumentChunk, ...]:
    """Deterministic character-offset chunks with sentence/paragraph boundaries.

    Character offsets refer to the exact original preprocessed Unicode text.
    Chunk boundaries favor whitespace; offsets always remain source-exact.
    """
    if not isinstance(text, str) or not document_id.strip():
        raise ValueError("Document text and ID are required")
    if max_chars < 64 or overlap < 0 or overlap >= max_chars:
        raise ValueError("Invalid chunk size or overlap")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    chunks = []
    start = 0
    while start < len(text):
        if not text[start:].strip():
            break
        end = min(len(text),start+max_chars)
        if end < len(text):
            candidates = list(re.finditer(r"\n\n|[.!?][ \t\n]|\s+",text[start:end]))
            cut = [m.end() for m in candidates if m.end() >= int(max_chars*.6)]
            if cut:
                end = start+cut[-1]
        if end <= start:
            raise ValueError("Non-advancing chunker")
        value=text[start:end]
        if value.strip():
            chunk_id=hashlib.sha256(json.dumps(
                [document_id,sha,start,end],separators=(",",":")).encode()).hexdigest()
            chunks.append(DocumentChunk(document_id,chunk_id,value,start,end,sha))
        if end == len(text):
            break
        start=max(start+1,end-overlap)
    return tuple(chunks)


def verify_chunk(chunk: DocumentChunk, original_text: str) -> bool:
    return (hashlib.sha256(original_text.encode("utf-8")).hexdigest()
            == chunk.document_sha256
            and original_text[chunk.start:chunk.end] == chunk.text)
