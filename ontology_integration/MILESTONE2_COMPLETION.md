# Milestone 2 — Completed scoped deliverables

Branch: `neemGraph`. This phase builds the **structural OWL analysis
and extraction-contract foundation**, not a general OWL 2 DL reasoner.

## Delivered

1. `axioms.py`: structural index for named classes, nested restriction
   expressions, equivalent/disjoint class axioms, subproperty, inverse
   and property-chain references. No OWL entailment.
2. `module_builder.py:audit_coverage`: machine-readable counts and a list of
   ontology patterns which the index does not yet fully cover.
3. `module_builder.py:select_bounded_module`: deterministic, exact-IRI,
   depth-limited selection with a hard entry budget and configurable
   outgoing/bidirectional traversal.
4. `module_builder.py:extraction_contract`: versioned ontology-aligned
   classes, properties and restriction-derived relationship *hints*, with
   evidence and no-invented-fillers safety policies.
5. Offline fixture tests exercising valid and invalid selection requests.

## Commands

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_ontology_registry.py tests/test_ontology_axioms.py tests/test_module_builder.py

python -m ontology_integration.module_builder /path/to/cram-aicor-ontology.ttl \
  --seed 'http://aicor.knowledge/l2-ontology.owl#Execution' \
  --depth 2 --max-entries 25 --direction outgoing \
  --output /tmp/cram-m2-extraction-contract.json \
  --audit-output /tmp/cram-m2-coverage.json
```

## Local acceptance results (2026-10-18)

- Full offline regression (Milestones 1 and 2): **6 passed**.
- Real CRAM/AICOR ontology: **11,596** RDF triples; **1,983** named
  class/property entries indexed.
- Bounded `Execution` module: **25** entries (17 classes, 8 properties),
  correctly reports `truncated=true`, and emits 8 OWL-derived relationship hints.
- Ontology audit identifies **1,341** OWL restrictions, **3,410** subclass
  axioms, **14** equivalent-class axioms, **135** disjointWith axioms, and
  **12** AllDisjointClasses groups.

## Semantic boundaries / known gaps

This phase **does not** implement OWL reasoning, OWL imports, SHACL,
entity linking, NEEM ingestion, TigerGraph loading, or GraphRAG runtime.
Specifically, the structural axiom index does **not fully index**
`AllDisjointClasses` (12 groups in the supplied ontology), datatype facets,
arbitrary anonymous-subject axioms or every OWL 2 expression. The coverage
report makes such gaps explicit rather than presenting a false complete
translation. These should be preserved and checked against the authoritative
OWL ontology by the later semantic validation/reasoning component.

The entry budget is a hard maximum, but currently selects equally relevant
neighbor IRIs in lexical order. Future relevance ranking and retrieval-aware
budgets can be added without changing the generated contract's core shape.
This is suitable as a deterministic and testable **initial module compiler**,
not as a final high-recall OWL module extractor.

## Next milestone

Milestone 3: define a typed candidate assertion envelope with source,
provenance, ontology checksum, confidence, time interval, statement kind,
and validation lifecycle. Add lossless JSON serialization and deterministic
identity keys before implementing source adapters.
