"""Ontology-wide RDF assertion envelope; no OWL reasoning or TigerGraph IO."""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

HEX = re.compile(r"^[0-9a-f]{64}$")
LANG = re.compile(r"^[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*$")


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def iri_valid(value):
    return (isinstance(value, str) and bool(value) and bool(urlsplit(value).scheme)
            and not any(c.isspace() or ord(c) < 32 for c in value))


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("Expected ISO8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamp requires explicit timezone")
    return result.astimezone(timezone.utc)


class TermKind(str, Enum):
    IRI = "iri"
    LITERAL = "literal"
    BNODE = "bnode"


@dataclass(frozen=True)
class RDFTerm:
    kind: TermKind
    value: str
    datatype: str | None = None
    language: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "kind", TermKind(self.kind))
        if not isinstance(self.value, str):
            raise ValueError("Term value must be text")
        if self.kind == TermKind.IRI:
            if not iri_valid(self.value) or self.datatype or self.language:
                raise ValueError("IRI term must contain only an absolute IRI")
        elif self.kind == TermKind.BNODE:
            if not self.value or self.datatype or self.language:
                raise ValueError("Blank node needs an ID without literal metadata")
        else:
            if self.datatype and not iri_valid(self.datatype):
                raise ValueError("Literal datatype requires an absolute IRI")
            if self.datatype and self.language:
                raise ValueError("Literal cannot combine datatype and language")
            if self.language and not LANG.fullmatch(self.language):
                raise ValueError("Invalid language tag")

    def to_dict(self):
        return {"kind": self.kind.value, "value": self.value,
                "datatype": self.datatype, "language": self.language}


class AssertionStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    QUARANTINED = "quarantined"
    ASSERTED = "asserted"
    INFERRED = "inferred"
    RETRACTED = "retracted"


TRANSITIONS = {
    AssertionStatus.CANDIDATE: {AssertionStatus.VALIDATED, AssertionStatus.QUARANTINED},
    AssertionStatus.VALIDATED: {AssertionStatus.ASSERTED, AssertionStatus.QUARANTINED},
    AssertionStatus.QUARANTINED: {AssertionStatus.CANDIDATE},
    AssertionStatus.ASSERTED: {AssertionStatus.RETRACTED},
    AssertionStatus.INFERRED: {AssertionStatus.RETRACTED},
    AssertionStatus.RETRACTED: set(),
}


@dataclass(frozen=True)
class SourceEvidence:
    source_type: str
    source_id: str
    locator: str
    method: str
    excerpt: str | None = None
    recorded_at: str | None = None

    def __post_init__(self):
        if any(not isinstance(s, str) or not s.strip()
               for s in (self.source_type, self.source_id, self.locator, self.method)):
            raise ValueError("Source metadata must be nonempty")
        if self.recorded_at:
            instant(self.recorded_at)

    def to_dict(self):
        return vars(self).copy()


@dataclass(frozen=True)
class Assertion:
    subject: RDFTerm
    predicate: RDFTerm
    object: RDFTerm
    evidence: SourceEvidence
    ontology_sha256: str
    status: AssertionStatus = AssertionStatus.CANDIDATE
    graph: RDFTerm | None = None
    confidence: float | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    derived_from: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, "status", AssertionStatus(self.status))
        if self.subject.kind == TermKind.LITERAL or self.predicate.kind != TermKind.IRI:
            raise ValueError("Invalid RDF triple subject or predicate")
        if self.graph and self.graph.kind == TermKind.LITERAL:
            raise ValueError("Graph name cannot be a literal")
        if not isinstance(self.ontology_sha256, str) or not HEX.fullmatch(self.ontology_sha256):
            raise ValueError("Ontology fingerprint must be lowercase SHA256")
        if self.confidence is not None and (
            not isinstance(self.confidence, (float, int))
            or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Confidence outside [0,1]")
        if self.valid_from:
            instant(self.valid_from)
        if self.valid_to:
            instant(self.valid_to)
        if self.valid_from and self.valid_to and instant(self.valid_from) > instant(self.valid_to):
            raise ValueError("Invalid temporal interval")
        if self.status == AssertionStatus.INFERRED and not self.derived_from:
            raise ValueError("Inferred assertion requires derivation references")
        if any(not isinstance(d, str) or not HEX.fullmatch(d) for d in self.derived_from):
            raise ValueError("Derivation references must be statement SHA256 IDs")

    @property
    def statement_id(self):
        quad = {"subject": self.subject.to_dict(), "predicate": self.predicate.to_dict(),
                "object": self.object.to_dict(), "graph": self.graph.to_dict() if self.graph else None}
        if any(t.kind == TermKind.BNODE for t in (self.subject, self.object, self.graph) if t):
            quad["blank_node_scope"] = [self.evidence.source_type, self.evidence.source_id]
        return digest(quad)

    @property
    def assertion_id(self):
        return digest({"statement_id": self.statement_id,
                       "source": [self.evidence.source_type, self.evidence.source_id,
                                  self.evidence.locator, self.evidence.method]})

    def transition(self, status: AssertionStatus):
        status = AssertionStatus(status)
        if status not in TRANSITIONS[self.status]:
            raise ValueError("Invalid assertion lifecycle transition")
        return replace(self, status=status)

    def to_dict(self):
        return {"schema_version": "1", "statement_id": self.statement_id,
                "assertion_id": self.assertion_id,
                "subject": self.subject.to_dict(), "predicate": self.predicate.to_dict(),
                "object": self.object.to_dict(), "graph": self.graph.to_dict() if self.graph else None,
                "evidence": self.evidence.to_dict(), "ontology_sha256": self.ontology_sha256,
                "status": self.status.value, "confidence": self.confidence,
                "valid_from": self.valid_from, "valid_to": self.valid_to,
                "derived_from": list(self.derived_from)}

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data):
        if data.get("schema_version") != "1":
            raise ValueError("Unsupported assertion schema version")
        result = cls(
            subject=RDFTerm(**data["subject"]),
            predicate=RDFTerm(**data["predicate"]),
            object=RDFTerm(**data["object"]),
            graph=RDFTerm(**data["graph"]) if data.get("graph") else None,
            evidence=SourceEvidence(**data["evidence"]),
            ontology_sha256=data["ontology_sha256"],
            status=data["status"], confidence=data.get("confidence"),
            valid_from=data.get("valid_from"), valid_to=data.get("valid_to"),
            derived_from=tuple(data.get("derived_from", [])),
        )
        if result.statement_id != data.get("statement_id") or result.assertion_id != data.get("assertion_id"):
            raise ValueError("Assertion digest mismatch")
        return result

    @classmethod
    def from_json(cls, raw):
        return cls.from_dict(json.loads(raw))
