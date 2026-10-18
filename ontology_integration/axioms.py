"""Structural OWL axiom index and bounded ontology module selection.

This is NOT an OWL entailment engine or a SHACL validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

AXIOM_PREDICATES = (
    RDFS.subClassOf, OWL.equivalentClass, OWL.disjointWith,
    OWL.disjointUnionOf, OWL.complementOf,
)
PROPERTY_AXIOMS = (
    RDFS.subPropertyOf, OWL.equivalentProperty, OWL.propertyDisjointWith,
    OWL.inverseOf, OWL.propertyChainAxiom,
)
EXPRESSION_PREDICATES = (
    OWL.onProperty, OWL.someValuesFrom, OWL.allValuesFrom, OWL.hasValue,
    OWL.hasSelf, OWL.minCardinality, OWL.maxCardinality, OWL.cardinality,
    OWL.minQualifiedCardinality, OWL.maxQualifiedCardinality,
    OWL.qualifiedCardinality, OWL.onClass, OWL.onDataRange,
    OWL.intersectionOf, OWL.unionOf, OWL.oneOf, OWL.complementOf,
)
LIST_PREDICATES = {
    OWL.intersectionOf, OWL.unionOf, OWL.oneOf,
    OWL.disjointUnionOf, OWL.propertyChainAxiom,
}
ORDERED_LIST_PREDICATES = {OWL.propertyChainAxiom}


def _key(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _expression(graph: Graph, node, seen: frozenset[BNode] = frozenset()):
    if isinstance(node, URIRef):
        return {"iri": str(node)}
    if isinstance(node, Literal):
        return {
            "literal": str(node),
            "datatype": str(node.datatype) if node.datatype else None,
            "language": node.language,
        }
    if not isinstance(node, BNode):
        raise ValueError(f"Unsupported RDF node: {type(node)}")
    if node in seen:
        return {"cycle": True}
    seen = seen | {node}
    result = {
        "kind": "restriction"
        if (node, RDF.type, OWL.Restriction) in graph else "anonymous_expression"
    }
    for predicate in EXPRESSION_PREDICATES:
        values = []
        for value in graph.objects(node, predicate):
            if predicate in LIST_PREDICATES:
                items = [_expression(graph, item, seen) for item in Collection(graph, value)]
                if predicate not in ORDERED_LIST_PREDICATES:
                    items.sort(key=_key)
                values.append({"list": items})
            else:
                values.append(_expression(graph, value, seen))
        if values:
            result[str(predicate)] = sorted(values, key=_key)
    return result


def _referenced_iris(expression) -> set[str]:
    if isinstance(expression, list):
        result = set()
        for item in expression:
            result.update(_referenced_iris(item))
        return result
    if isinstance(expression, dict):
        result = {expression["iri"]} if "iri" in expression else set()
        for key, value in expression.items():
            if key != "iri":
                result.update(_referenced_iris(value))
        return result
    return set()


def build_axiom_index(source: str | Path) -> dict:
    source = Path(source)
    graph = Graph().parse(source, format="turtle")
    classes = sorted(
        set(x for x in graph.subjects(RDF.type, OWL.Class) if isinstance(x, URIRef)),
        key=str,
    )
    properties = sorted(
        {
            x for kind in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
            for x in graph.subjects(RDF.type, kind) if isinstance(x, URIRef)
        },
        key=str,
    )
    entries = []
    for node in classes:
        axioms = []
        for predicate in AXIOM_PREDICATES:
            for value in graph.objects(node, predicate):
                if predicate in LIST_PREDICATES:
                    operands = [_expression(graph, x) for x in Collection(graph, value)]
                    operands.sort(key=_key)
                    expression = {"list": operands}
                else:
                    expression = _expression(graph, value)
                axioms.append({"predicate": str(predicate), "expression": expression})
        entries.append({
            "iri": str(node),
            "labels": sorted(set(map(str, graph.objects(node, RDFS.label)))),
            "axioms": sorted(axioms, key=_key),
        })
    property_entries = []
    for node in properties:
        axioms = []
        for predicate in PROPERTY_AXIOMS:
            for value in graph.objects(node, predicate):
                expression = (
                    {"list": [_expression(graph, item) for item in Collection(graph, value)]}
                    if predicate in LIST_PREDICATES else _expression(graph, value)
                )
                axioms.append({"predicate": str(predicate), "expression": expression})
        property_entries.append({
            "iri": str(node),
            "axioms": sorted(axioms, key=_key),
        })
    return {
        "source": source.name,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "triple_count": len(graph),
        "classes": entries,
        "properties": property_entries,
        "semantics": "Structural OWL index; no entailment, no SHACL validation",
    }


def select_module(index: dict, seeds: list[str], max_depth: int = 1) -> dict:
    """Expand exact class/property IRI seeds across linked OWL axiom references."""
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    entries = {
        entry["iri"]: entry
        for group in ("classes", "properties")
        for entry in index[group]
    }
    unknown = sorted(set(seeds) - entries.keys())
    if unknown:
        raise ValueError(f"Unknown ontology IRIs: {unknown}")
    neighbors = {iri: set() for iri in entries}
    for iri, entry in entries.items():
        for axiom in entry["axioms"]:
            for related in _referenced_iris(axiom["expression"]):
                if related in entries and related != iri:
                    neighbors[iri].add(related)
                    neighbors[related].add(iri)
    selected = set(seeds)
    frontier = set(seeds)
    for _ in range(max_depth):
        frontier = (
            set().union(*(neighbors[iri] for iri in frontier)) - selected
            if frontier else set()
        )
        selected |= frontier
    return {
        "source_sha256": index["sha256"],
        "seeds": sorted(set(seeds)),
        "max_depth": max_depth,
        "classes": [entry for entry in index["classes"] if entry["iri"] in selected],
        "properties": [entry for entry in index["properties"] if entry["iri"] in selected],
        "selected_count": len(selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Index OWL axioms or select an ontology module")
    parser.add_argument("ontology")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", action="append", default=[], help="Exact class/property IRI")
    parser.add_argument("--depth", type=int, default=1)
    args = parser.parse_args()
    index = build_axiom_index(args.ontology)
    result = select_module(index, args.seed, args.depth) if args.seed else index
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Saved {result.get('selected_count', len(index['classes']) + len(index['properties']))}"
        f" ontology entries to {out}"
    )


if __name__ == "__main__":
    main()
