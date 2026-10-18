# Milestone 2 — OWL axiom index and ontology module selection

This increment adds `ontology_integration/axioms.py`. It is independent of
TigerGraph, LLM services, and the existing document ingestion pipeline.

## What works

- Indexes named OWL class `rdfs:subClassOf`, `owl:equivalentClass`,
  `owl:disjointWith`, and `owl:complementOf` expressions.
- Recursively records anonymous OWL restrictions, intersections, unions, oneOf
  lists, and cardinality values without inventing names for blank nodes.
- Indexes property subproperty/equivalence/disjointness/inverse/chain axioms.
- Retains source ontology checksum (SHA-256) and the original full IRIs.
- Selects a bounded semantic neighborhood from exact class/property IRI seeds.

## Run

Install `rdflib` and `pytest` in an isolated Python environment:

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_ontology_axioms.py
python -m ontology_integration.axioms /path/to/cram-aicor-ontology.ttl \
  --output /tmp/cram-axioms.json
python -m ontology_integration.axioms /path/to/cram-aicor-ontology.ttl \
  --seed 'http://aicor.knowledge/l2-ontology.owl#Execution' \
  --depth 1 --output /tmp/cram-execution-module.json
```

Local verification using the supplied CRAM/AICOR Turtle file on 2026-10-18:
11,596 triples, 1,983 named class/property entries in the advanced index,
and eight selected entries in the one-hop `Execution` module.
Two fixture tests passed; this is **not** a GitHub CI result.

## Explicit limitations

- **Structural index only:** does not compute OWL entailments, perform SHACL
  validation, or map OWL expressions directly into GSQL constraints.
- **Module selection is exploratory:** symmetric graph traversal over references
  may pull unrelated classes through large shared relations. Depth limits
  bound hop count, not module size; add budgets, role-based directions and
  property-domain/range relevance before using with an LLM.
- Only declared, named class/property entries are available as seeds. OWL
  imports are not resolved. Blank-node cycles are marked, and not reconstructed.
- The index does not capture every OWL/RDF construct (notably general RDF
  axioms, datatype facets, AllDisjointClasses lists, equivalent expressions
  asserted on anonymous subjects, and annotation provenance).
- The source OWL file remains authoritative. Existing
  `ontology_integration/registry.py` is unchanged.

## Next small increments

1. Build axiom-coverage metrics against the real CRAM/AICOR ontology.
2. Add ontology-module size budgets and configurable expansion semantics.
3. Combine deterministic ontology compilation with stable extraction-contract
   generation for the `Execution`/NEEM domain.
4. Integrate only after auditing the appropriate GraphRAG ingestion interfaces.
