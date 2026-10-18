"""RDFLib bridge, ontology vocabulary checks, deterministic assertion batches."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Iterable
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF
from .assertions import Assertion, RDFTerm, SourceEvidence, TermKind, digest

def to_rdflib(term: RDFTerm):
    if term.kind == TermKind.IRI:
        return URIRef(term.value)
    if term.kind == TermKind.BNODE:
        return BNode(term.value)
    return Literal(term.value, lang=term.language,
                   datatype=URIRef(term.datatype) if term.datatype else None)

def from_rdflib(node) -> RDFTerm:
    if isinstance(node, URIRef):
        return RDFTerm(TermKind.IRI, str(node))
    if isinstance(node, BNode):
        return RDFTerm(TermKind.BNODE, str(node))
    if isinstance(node, Literal):
        datatype = str(node.datatype) if node.datatype else None
        if datatype == "http://www.w3.org/2001/XMLSchema#string":
            datatype = None
        return RDFTerm(TermKind.LITERAL, str(node), datatype, node.language)
    raise TypeError(f"Unsupported RDFLib term: {type(node)!r}")

def to_rdflib_graph(assertions: Iterable[Assertion]) -> Graph:
    """Only a triple projection: JSONL is needed to preserve provenance."""
    graph = Graph()
    for a in assertions:
        if a.graph is not None:
            raise ValueError("Named graph would be lost in plain Graph export; use JSONL")
        if any(term.kind == TermKind.BNODE for term in (a.subject, a.object)):
            raise ValueError("Blank-node scope would be lost; use JSONL")
        graph.add((to_rdflib(a.subject), to_rdflib(a.predicate), to_rdflib(a.object)))
    return graph

@dataclass(frozen=True)
class VocabularyReport:
    accepted: bool
    errors: tuple[str, ...] = ()

class OntologyVocabulary:
    """Check explicitly declared vocabulary, not OWL entailment or SHACL."""
    def __init__(self, graph: Graph):
        types = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
        self.properties = frozenset(str(s) for typ in types for s in graph.subjects(RDF.type, typ)
                                    if isinstance(s, URIRef))
        self.classes = frozenset(str(s) for s in graph.subjects(RDF.type, OWL.Class)
                                 if isinstance(s, URIRef))

    @classmethod
    def from_turtle(cls, path: str | Path):
        return cls(Graph().parse(str(path), format="turtle"))

    def check(self, assertion: Assertion, *, strict: bool = False) -> VocabularyReport:
        errors = []
        pred = assertion.predicate.value
        if pred == str(RDF.type):
            if assertion.object.kind != TermKind.IRI:
                errors.append("rdf:type object must be a class IRI")
            elif strict and assertion.object.value not in self.classes:
                errors.append(f"Class IRI not declared: {assertion.object.value}")
        elif strict and pred not in self.properties:
            errors.append(f"Predicate IRI not declared: {pred}")
        return VocabularyReport(not errors, tuple(errors))

@dataclass(frozen=True)
class AssertionBatch:
    assertions: tuple[Assertion, ...]
    batch_label: str = "ingestion"
    schema_version: str = field(default="1", init=False)

    def __post_init__(self):
        if not self.batch_label.strip():
            raise ValueError("Batch label must be nonempty")
        by_id = {}
        for a in self.assertions:
            if a.assertion_id in by_id and a.to_dict() != by_id[a.assertion_id].to_dict():
                raise ValueError("Conflicting snapshots of the same assertion")
            by_id[a.assertion_id] = a
        object.__setattr__(self, "assertions", tuple(by_id[k] for k in sorted(by_id)))

    @property
    def batch_id(self):
        return digest({"schema_version": self.schema_version,
                       "assertions": [a.to_dict() for a in self.assertions]})

    def to_dict(self):
        return {"schema_version": self.schema_version, "batch_id": self.batch_id,
                "batch_label": self.batch_label, "assertions": [a.to_dict() for a in self.assertions]}

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data):
        if data.get("schema_version") != "1":
            raise ValueError("Unsupported batch schema")
        batch = cls(tuple(Assertion.from_dict(a) for a in data["assertions"]),
                    batch_label=data["batch_label"])
        if batch.batch_id != data.get("batch_id"):
            raise ValueError("Batch digest mismatch")
        return batch

    @classmethod
    def from_json(cls, data):
        return cls.from_dict(json.loads(data))

    def to_jsonl(self):
        return "".join(a.to_json() + "\n" for a in self.assertions)

    @classmethod
    def from_jsonl(cls, data, *, label="ingestion"):
        return cls(tuple(Assertion.from_json(line) for line in data.splitlines() if line.strip()), label)

def normalize_sources(records: Iterable[dict], ontology_sha256: str) -> AssertionBatch:
    """Adapter boundary for already mapped document/NEEM/structured records."""
    results = []
    for r in records:
        evidence = SourceEvidence(
            source_type=r["source_type"], source_id=r["source_id"],
            locator=r["locator"], method=r["method"],
            excerpt=r.get("excerpt"), recorded_at=r.get("recorded_at"))
        results.append(Assertion(
            subject=RDFTerm(**r["subject"]), predicate=RDFTerm(**r["predicate"]),
            object=RDFTerm(**r["object"]), evidence=evidence,
            ontology_sha256=ontology_sha256,
            graph=RDFTerm(**r["graph"]) if r.get("graph") else None,
            confidence=r.get("confidence"), valid_from=r.get("valid_from"),
            valid_to=r.get("valid_to")))
    return AssertionBatch(tuple(results))
