# CRAM/AICOR Ontology Integration

This directory is an **incremental extension** of TigerGraph GraphRAG on the `neemGraph` branch. It is not wired into document ingestion or TigerGraph storage yet.

## Milestone 1: ontology semantic registry

`registry.py` parses a local OWL ontology serialized as Turtle and emits a JSON index of:

- Declared named OWL classes, labels, named superclasses, and direct subclass restrictions
- Declared OWL object, datatype, and annotation properties
- Named domains and ranges, and OWL property characteristics
- Original IRIs, input filename, and SHA-256 fingerprint

Run locally (Python 3.10+):

```bash
python -m pip install rdflib pytest
python -m ontology_integration.registry /path/to/cram-aicor-ontology.ttl --output /tmp/cram-registry.json
python -m pytest tests/test_ontology_registry.py
```

**Important boundaries:** The registry is an index, not a reasoner or a complete OWL transformation. Anonymous class expressions beyond direct `rdfs:subClassOf` restrictions, property chains, RDF lists, equivalent-class restrictions, and complex property expressions are not yet fully indexed. A registry entry must not be interpreted as a SHACL constraint. RDF parsing does not require LLM or TigerGraph access.

Do not commit proprietary/private source datasets or environment credentials. Keep the ontology file external until repository publication and licensing decisions are settled.

## Incremental roadmap

| Milestone | Deliverable | Acceptance test |
|---|---|---|
| 1 | OWL registry and offline tests | Deterministic parsing of a small fixture and real CRAM/AICOR Turtle |
| 2 | Rich OWL axiom index and module selector | Extract relevant `ActionPlanning`, `Execution`, `GroundedDesignator` neighborhood without losing IRIs |
| 3 | Canonical provenance-aware assertion schema | Identical assertions from document, NEEM and JSON adapters normalize to one contract |
| 4 | Deterministic NEEM and structured adapters | Fixture logs create reproducible, uniquely identified assertions |
| 5 | Document extraction bridge | Validated schema-guided candidates with source span evidence |
| 6 | SHACL/OWL validation and entity resolution | Quarantine violations; preserve asserted vs inferred facts |
| 7 | TigerGraph schema projection, loader and GraphRAG retrieval | Idempotent graph loading, provenance queries and grounded answers |

Before milestone 7, audit the existing GraphRAG knowledge graph building and retrieval packages in the fork to select actual integration points. Do not modify upstream ingestion paths until their interfaces have been verified.
