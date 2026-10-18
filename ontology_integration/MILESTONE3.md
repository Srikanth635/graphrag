# Milestone 3 — Unified assertion contract (completed scoped foundation)

Milestone 3 provides a source-neutral RDF-compatible assertion interface,
independent of any individual CRAM/AICOR class. It does **not** parse raw NEEM
datasets, invoke the document LLM, reason over OWL, or write to TigerGraph.

## Files

- `assertions.py`: RDF terms, statement IDs, source-specific assertion IDs,
  provenance fields, timestamps, confidence, lifecycle and JSON.
- `pipeline_contract.py`: deterministic/idempotent assertion batches;
  JSON and JSONL round trips; RDFLib term conversion; loss-aware RDF
  triple projection; declared ontology vocabulary checks; common adapter
  input for NEEM, documents, and structured records.
- `provenance.py`: in-memory transition journal with append-only JSONL event
  serialization, replay and hash-checked per-assertion history chain.
- `tests/test_ontology_assertions.py` and `tests/test_pipeline_contract.py`:
  fixture-based regression checks.

## Run offline

```bash
python -m pip install rdflib pytest
python -m pytest -q \
  tests/test_ontology_registry.py \
  tests/test_ontology_axioms.py \
  tests/test_module_builder.py \
  tests/test_ontology_assertions.py \
  tests/test_pipeline_contract.py
```

Local smoke run: **16 tests passed** across combined local milestone
fixtures (2026-10-18). These are local code tests, not hosted GitHub CI.
The real uploaded CRAM/AICOR ontology was also used to verify the vocabulary
check: 1,017 declared named classes, 966 declared properties, and recognition
of `realizesDesignator` as a declared object property.

## Identity and interoperability guarantees

- Different sources may assert the same RDF statement while retaining distinct
  assertion IDs and independent evidence.
- Reingesting the same exact batch produces the same batch ID.
- Repeated identical assertions collapse in a batch; conflicting snapshots
  sharing an assertion ID are rejected, not silently overwritten.
- Assertion JSONL preserves evidence and graph context. A plain RDF Graph
  export deliberately rejects named graph assertions and scoped blank nodes
  because projection could lose essential information.
- Source-specific input records must already have mapped RDF terms. This is
  an **adapter boundary**, not a parser for arbitrary JSON/NEEM schemas.
- Ontology vocabulary `strict=True` checks declared class and property IRIs;
  it does not check OWL domain/range implications, entailments, SHACL rules
  or imported external vocabulary. An unknown IRI can be left for review
  with `strict=False`.
- Provenance events record status transitions and a replayable linked hash.
  This catches accidental corruption of archived JSONL records, but it is
  **not cryptographically authenticated** (an adversary could rewrite
  the full chain). Use signed or externally anchored audit records for
  adversarial tamper evidence.
- Journal lifecycle history is memory-resident until explicitly serialized.
  Persistent transactional event storage, entity-resolution merge histories,
  source-span offsets, OWL reasoning and TigerGraph IO are future work.

## Next milestone

Milestone 4: implement deterministic source adapters, starting with a
representative NEEM export and one structured JSON fixture, then connect
those adapters to the normalized assertion interface.
