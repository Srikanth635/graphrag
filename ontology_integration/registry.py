"""OWL/RDF ontology registry builder for ontology-guided ingestion.

This module does not equate OWL restrictions with closed-world validation rules.
It emits a lossless-enough structural index with original IRIs and restriction
descriptions; the source OWL graph remains authoritative for reasoning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

RESTRICTION_FIELDS = (
    OWL.onProperty,
    OWL.someValuesFrom,
    OWL.allValuesFrom,
    OWL.hasValue,
    OWL.minCardinality,
    OWL.maxCardinality,
    OWL.cardinality,
    OWL.minQualifiedCardinality,
    OWL.maxQualifiedCardinality,
    OWL.qualifiedCardinality,
    OWL.onClass,
    OWL.onDataRange,
)
PROPERTY_TYPES = (
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
)
CHARACTERISTICS = (
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.TransitiveProperty,
    OWL.SymmetricProperty,
    OWL.AsymmetricProperty,
    OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty,
)


def _value(node):
    if isinstance(node, Literal):
        return {"value": str(node), "datatype": str(node.datatype) if node.datatype else None, "language": node.language}
    if isinstance(node, URIRef):
        return {"iri": str(node)}
    return {"anonymous": True}


def _label(graph: Graph, subject: URIRef) -> list[str]:
    return sorted({str(v) for v in graph.objects(subject, RDFS.label)})


def _restriction(graph: Graph, node: BNode) -> dict:
    result = {}
    for predicate in RESTRICTION_FIELDS:
        values = list(graph.objects(node, predicate))
        if values:
            result[str(predicate)] = [_value(value) for value in values]
    return result


def build_registry(path: str | Path) -> dict:
    """Parse Turtle and enumerate declared OWL vocabulary and restrictions."""
    path = Path(path)
    graph = Graph()
    graph.parse(path, format="turtle")
    raw = path.read_bytes()
    classes = sorted(
        (subject for subject in graph.subjects(RDF.type, OWL.Class) if isinstance(subject, URIRef)),
        key=str,
    )
    properties = sorted(
        {subject for kind in PROPERTY_TYPES for subject in graph.subjects(RDF.type, kind)
         if isinstance(subject, URIRef)},
        key=str,
    )
    class_entries = []
    for subject in classes:
        parent_iris = []
        restrictions = []
        for parent in graph.objects(subject, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                parent_iris.append(str(parent))
            elif isinstance(parent, BNode) and (parent, RDF.type, OWL.Restriction) in graph:
                restrictions.append(_restriction(graph, parent))
        class_entries.append({
            "iri": str(subject),
            "labels": _label(graph, subject),
            "parent_iris": sorted(set(parent_iris)),
            "restrictions": restrictions,
        })
    property_entries = []
    for subject in properties:
        property_entries.append({
            "iri": str(subject),
            "labels": _label(graph, subject),
            "types": sorted(str(kind) for kind in PROPERTY_TYPES if (subject, RDF.type, kind) in graph),
            "domain_iris": sorted(str(v) for v in graph.objects(subject, RDFS.domain) if isinstance(v, URIRef)),
            "range_iris": sorted(str(v) for v in graph.objects(subject, RDFS.range) if isinstance(v, URIRef)),
            "characteristics": sorted(str(kind) for kind in CHARACTERISTICS if (subject, RDF.type, kind) in graph),
        })
    return {
        "source": path.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "triple_count": len(graph),
        "classes": class_entries,
        "properties": property_entries,
        "notes": "OWL open-world axioms are metadata; this registry does not perform reasoning or SHACL validation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a JSON registry from a Turtle OWL ontology")
    parser.add_argument("ontology", help="Path to ontology .ttl file")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()
    registry = build_registry(args.ontology)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(registry['classes'])} classes and {len(registry['properties'])} properties to {output}")


if __name__ == "__main__":
    main()
