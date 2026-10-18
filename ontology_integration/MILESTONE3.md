# Milestone 3: ontology-wide assertion envelope

This is the first Milestone 3 increment, deliberately independent of the
existing TigerGraph GraphRAG runtime and of any specific CRAM/AICOR class.

## Contract

`ontology_integration.assertions` contains:

- `RDFTerm`: IRI, literal (datatype OR language), or scoped blank node.
- `SourceEvidence`: source type, stable source ID, local record locator,
  extraction method, optional excerpt and observation timestamp.
- `Assertion`: RDF subject/predicate/object and optional graph name,
  source evidence, ontology SHA-256, confidence, validity interval,
  inference dependencies and lifecycle status.
- `statement_id`: SHA-256 of the canonical RDF statement/quad, shared by
  independent observations of the same statement.
- `assertion_id`: SHA-256 of the statement ID plus source identity,
  locator and extraction method. Two different sources are never collapsed.
- Strict candidate -> validated -> asserted transitions; quarantine,
  inferred and retraction states are supported.
- JSON serialization, identity verification on deserialization and tests.

Run: `python -m pytest -q tests/test_ontology_assertions.py`.

## Critical distinctions

- A document stating a fact and a NEEM log recording the same fact share
  the **statement_id**, but have different **assertion_id** values.
- The stable identifiers are **content identities**, not graph identity
  resolution. Distinct aliases referring to the same entity remain distinct.
- Identity deliberately excludes confidence, lifecycle and validity times:
  changing those metadata does not change the source-backed assertion ID.
  A history/event store will be needed to track changes over time.
- Blank nodes have source-local scope; original source IDs must be stable.
- The ontology SHA-256 is a version fingerprint, **not** an ontology
  membership check. Validate actual class/property vocabulary later.
- `INFERRED` status requires parent statement IDs; this code does not
  perform OWL reasoning or calculate inference derivations.
- A validated assertion is not automatically a true, consistent or
  source-supported fact. SHACL/OWL semantic checking belongs to Milestone 6.
- A complete provenance implementation should add document span offsets,
  temporal provenance, confidence calibration, persistent audit events and
  graph loading later. Do not discard supporting source records.

## Acceptance scope

An offline local prototype passed five tests using RDF values,
cross-source identity, JSON serialization, transition enforcement,
source-scoped blank nodes and temporal validation.

The connector has committed the implementation and pytest file to
`neemGraph`; hosted CI on that exact branch is **not yet verified**.

## Next increments

1. Source-neutral assertion batch and idempotent serialization.
2. RDFLib conversion tests and ontology IRI membership checks.
3. Versioned provenance events and schema compatibility mapping for
   NEEM, documents and structured adapters.

No real-source ingestion or TigerGraph write operations are performed yet.
