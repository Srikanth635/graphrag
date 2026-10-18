"""Deterministic ontology module budgets, coverage audit and extraction contracts.

The generated contract is extraction guidance, NOT an OWL reasoner or validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .axioms import _referenced_iris, build_axiom_index

RESTRICTION = str(OWL.onProperty)


def audit_coverage(source: str | Path, index: dict) -> dict:
    """Measure structural axiom coverage and known unsupported OWL patterns."""
    graph = Graph().parse(str(source), format="turtle")
    indexed = {e["iri"] for kind in ("classes", "properties") for e in index[kind]}
    patterns = {
        "named_classes": sum(isinstance(s, URIRef) for s in graph.subjects(RDF.type, OWL.Class)),
        "anonymous_classes": sum(isinstance(s, BNode) for s in graph.subjects(RDF.type, OWL.Class)),
        "restrictions": sum(1 for _ in graph.subjects(RDF.type, OWL.Restriction)),
        "subclass_axioms": sum(1 for _ in graph.triples((None, RDFS.subClassOf, None))),
        "equivalent_classes": sum(1 for _ in graph.triples((None, OWL.equivalentClass, None))),
        "disjoint_classes": sum(1 for _ in graph.triples((None, OWL.disjointWith, None))),
        "property_chains": sum(1 for _ in graph.triples((None, OWL.propertyChainAxiom, None))),
        "owl_imports": sum(1 for _ in graph.triples((None, OWL.imports, None))),
        "all_disjoint_classes": sum(1 for _ in graph.subjects(RDF.type, OWL.AllDisjointClasses)),
        "datatype_restrictions": sum(1 for _ in graph.triples((None, OWL.onDatatype, None))),
    }
    indexed_subjects = {URIRef(iri) for iri in indexed}
    unsupported = {
        "anonymous_subject_class_axioms": sum(
            isinstance(s, BNode) for p in (RDFS.subClassOf, OWL.equivalentClass, OWL.disjointWith)
            for s in graph.subjects(p, None)),
        "class_axioms_on_undeclared_subjects": sum(
            isinstance(s, URIRef) and s not in indexed_subjects
            for p in (RDFS.subClassOf, OWL.equivalentClass, OWL.disjointWith)
            for s in graph.subjects(p, None)),
        "all_disjoint_classes": patterns["all_disjoint_classes"],
        "datatype_restrictions": patterns["datatype_restrictions"],
        "owl_imports_not_resolved": patterns["owl_imports"],
    }
    return {
        "source_sha256": index["sha256"], "triple_count": len(graph),
        "patterns": patterns, "not_fully_indexed": unsupported,
        "indexed_named_entries": len(index["classes"]) + len(index["properties"]),
        "status": "structural_coverage_only_no_reasoning",
    }


def _neighbors(index: dict, direction: str) -> dict[str, set[str]]:
    entries = {e["iri"]: e for kind in ("classes", "properties") for e in index[kind]}
    links = {iri: set() for iri in entries}
    for iri, entry in entries.items():
        for axiom in entry["axioms"]:
            for linked in _referenced_iris(axiom["expression"]):
                if linked in entries and linked != iri:
                    links[iri].add(linked)
                    if direction == "both":
                        links[linked].add(iri)
    return links


def select_bounded_module(index: dict, seeds: list[str], *, depth: int = 1,
                          max_entries: int = 50, direction: str = "outgoing") -> dict:
    """Deterministic breadth-first module selection with a hard entry limit."""
    if depth < 0 or max_entries < 1 or direction not in ("outgoing", "both"):
        raise ValueError("Invalid module depth, max_entries, or direction")
    entries = {e["iri"]: e for kind in ("classes", "properties") for e in index[kind]}
    seed_set = set(seeds)
    unknown = seed_set - entries.keys()
    if unknown:
        raise ValueError(f"Unknown ontology IRIs: {sorted(unknown)}")
    if not seed_set:
        raise ValueError("At least one seed IRI is required")
    if len(seed_set) > max_entries:
        raise ValueError("The seed count exceeds max_entries")
    links = _neighbors(index, direction)
    selected = set(seed_set)
    frontier = sorted(seed_set)
    truncated = False
    for _ in range(depth):
        candidates = sorted({v for u in frontier for v in links[u]} - selected)
        room = max_entries - len(selected)
        if len(candidates) > room:
            truncated = True
        additions = candidates[:room]
        selected.update(additions)
        frontier = additions
        if not frontier:
            break
    return {
        "source_sha256": index["sha256"], "seeds": sorted(seed_set),
        "max_depth": depth, "max_entries": max_entries, "direction": direction,
        "truncated": truncated, "selected_count": len(selected),
        "classes": [e for e in index["classes"] if e["iri"] in selected],
        "properties": [e for e in index["properties"] if e["iri"] in selected],
    }


def extraction_contract(module: dict) -> dict:
    """Produce exact-IRI extraction instructions with evidence and OWL safety policies."""
    properties = {e["iri"] for e in module["properties"]}
    hints = []
    for entry in module["classes"]:
        for axiom in entry["axioms"]:
            def visit(node):
                if isinstance(node, list):
                    for item in node:
                        yield from visit(item)
                elif isinstance(node, dict):
                    if node.get("kind") == "restriction":
                        for target in node.get(RESTRICTION, []):
                            if isinstance(target, dict) and target.get("iri") in properties:
                                yield {
                                    "subject_class": entry["iri"],
                                    "predicate_iri": target["iri"],
                                    "owl_expression": node,
                                    "usage": "extraction_hint_only",
                                }
                    for value in node.values():
                        yield from visit(value)
            hints.extend(visit(axiom["expression"]))
    hints.sort(key=lambda v: (v["subject_class"], v["predicate_iri"],
                              json.dumps(v["owl_expression"], sort_keys=True)))
    return {
        "contract_version": "1", "ontology_sha256": module["source_sha256"],
        "classes": [{"iri": e["iri"], "labels": e.get("labels", [])} for e in module["classes"]],
        "properties": [{"iri": e["iri"]} for e in module["properties"]],
        "relation_hints": hints,
        "policy": {
            "only_use_declared_iris": True,
            "require_source_evidence": True,
            "do_not_invent_existential_fillers": True,
            "owl_hints_are_not_shacl_constraints": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit OWL and build an extraction contract")
    parser.add_argument("ontology")
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-output")
    parser.add_argument("--seed", action="append", required=True)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--max-entries", type=int, default=50)
    parser.add_argument("--direction", choices=["outgoing", "both"], default="outgoing")
    args = parser.parse_args()
    index = build_axiom_index(args.ontology)
    module = select_bounded_module(
        index, args.seed, depth=args.depth,
        max_entries=args.max_entries, direction=args.direction,
    )
    contract = extraction_contract(module)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"module": module, "contract": contract}, indent=2) + "\n")
    if args.audit_output:
        audit_path = Path(args.audit_output)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(audit_coverage(args.ontology, index), indent=2) + "\n")
    print(f'Selected {module["selected_count"]} entries; truncated={module["truncated"]}')


if __name__ == "__main__":
    main()
