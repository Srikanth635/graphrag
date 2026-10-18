"""Conservative OWL/RDFS validation for source-backed RDF assertion candidates.

No closed-world domain/range rejection and no claim of complete OWL-DL reasoning.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL
from .assertions import TermKind

@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    assertion_id: str
    explanation: str
    def to_dict(self):
        return vars(self).copy()

@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[Issue, ...]
    checked: int
    @property
    def error_count(self):
        return sum(i.severity == "error" for i in self.issues)
    def to_dict(self):
        return {"checked":self.checked,"errors":self.error_count,
                "issues":[i.to_dict() for i in self.issues]}

class SemanticValidator:
    """Local checks plus warnings for incomplete OWL open-world information."""
    def __init__(self, ontology: Graph, ontology_sha256: str):
        self.graph = ontology
        self.fingerprint = ontology_sha256
        self.classes = {str(s) for s in ontology.subjects(RDF.type, OWL.Class) if isinstance(s,URIRef)}
        kinds = (OWL.ObjectProperty,OWL.DatatypeProperty,OWL.AnnotationProperty)
        self.property_kinds = {str(s):{str(t) for t in ontology.objects(s,RDF.type)}
                               for kind in kinds for s in ontology.subjects(RDF.type,kind)
                               if isinstance(s,URIRef)}
        self.domains = {p:tuple(ontology.objects(URIRef(p),RDFS.domain)) for p in self.property_kinds}
        self.ranges = {p:tuple(ontology.objects(URIRef(p),RDFS.range)) for p in self.property_kinds}
        self.parents = {}
        for child,parent in ontology.subject_objects(RDFS.subClassOf):
            if isinstance(child,URIRef) and isinstance(parent,URIRef):
                self.parents.setdefault(str(child),set()).add(str(parent))
        self.disjoint = set()
        for left,right in ontology.subject_objects(OWL.disjointWith):
            if isinstance(left,URIRef) and isinstance(right,URIRef):
                self.disjoint.add(frozenset((str(left),str(right))))

    @classmethod
    def from_turtle(cls,path):
        path=Path(path)
        return cls(Graph().parse(str(path),format="turtle"),sha256(path.read_bytes()).hexdigest())

    def ancestors(self,iri):
        todo=[iri]
        seen=set()
        while todo:
            item=todo.pop()
            if item in seen: continue
            seen.add(item)
            todo.extend(self.parents.get(item,()))
        return seen

    def validate(self,assertions):
        assertions=tuple(assertions)
        issues=[]
        types={}
        for a in assertions:
            if a.predicate.value==str(RDF.type) and a.object.kind==TermKind.IRI:
                types.setdefault(a.subject.value,set()).add(a.object.value)
        for a in assertions:
            def add(severity,code,reason):
                issues.append(Issue(severity,code,a.assertion_id,reason))
            if a.ontology_sha256!=self.fingerprint:
                add("error","ontology_fingerprint_mismatch","Assertion targets a different ontology file")
            p=a.predicate.value
            if p==str(RDF.type):
                if a.object.kind!=TermKind.IRI:
                    add("error","rdf_type_not_iri","rdf:type requires an IRI object")
                elif a.object.value not in self.classes:
                    add("warning","unrecognized_class","Class not explicitly declared in loaded ontology")
            elif p not in self.property_kinds:
                add("warning","unrecognized_predicate","Predicate not explicitly declared in loaded ontology")
            else:
                kinds=self.property_kinds[p]
                if str(OWL.ObjectProperty) in kinds and a.object.kind==TermKind.LITERAL:
                    add("error","object_property_literal","OWL object property has literal object")
                if str(OWL.DatatypeProperty) in kinds and a.object.kind!=TermKind.LITERAL:
                    add("error","datatype_property_resource","OWL datatype property has resource object")
                if self.domains[p] or self.ranges[p]:
                    add("info","domain_range_open_world",
                        "Domain/range imply types; missing explicit types do not prove invalidity")
            if p==str(RDF.type) and a.object.kind==TermKind.IRI:
                known=types.get(a.subject.value,())
                inherited=set().union(*(self.ancestors(t) for t in known)) if known else set()
                if any(dis <= inherited for dis in self.disjoint):
                    add("error","explicit_disjoint_types",
                        "Asserted types contain disjoint named classes or superclasses")
        return ValidationResult(tuple(sorted(issues,key=lambda i:(i.assertion_id,i.code,i.severity))),len(assertions))
