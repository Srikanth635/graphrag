# Milestone 6 — Semantic validation and entity resolution

Branch: `neemGraph` | Updated 2026-10-18

## Implementation

The Milestone 3 provenance-aware candidate RDF envelope is preserved.
**No module in this milestone silently changes assertion status or writes
owl:sameAs relationships**.

1. `semantic_validation.py`: ontology fingerprint, property resource/literal
   mismatch, direct disjoint named classes plus named superclass ancestry,
   and open-world domain/range diagnostics.
2. `axiom_checks.py`: direct irreflexive and asymmetric property contradictions;
   functional property competing values reported conservatively. Different
   resource IRIs under a functional property may imply equality under OWL,
   not automatically a logical contradiction. Literal lexical differences
   are not taken as a definitive datatype-value-space inconsistency.
3. `temporal_conflicts.py`: review candidate generation for potentially
   overlapping validity intervals with different values on explicitly
   functional predicates. Distinct non-overlapping observations are retained.
   Unknown intervals cause review rather than automatic quarantine.
4. `entity_resolution.py`: stable proposals connecting evidence-backed
   NEEM and document entity records. Same label alone cannot merge entities;
   verified external identifiers are a review proposal, not approval.
5. `identity_review.py`: append-only JSONL hash-linked review log with
   `approve`, `reject` or `defer`, reviewer, evidence and rationale;
   tampering with existing records is detectable unless the complete chain
   is maliciously rewritten. This is not a signed or concurrency-safe ledger.
6. `review_report.py`: single diagnostic report combining structural,
   characteristic and temporal checks on Milestone 3 assertion JSONL.
7. `shacl_review.py`: optional `pyshacl` integration for **explicitly
   provided trusted SHACL shapes** (not automatically generated from OWL).
   Imports/advanced SHACL features are disabled.
8. `validation_cli.py`: retained standalone structural validation CLI.

## Verified local evidence

- 12/12 local Milestone 6 tests passed using an equivalent local module
  implementation (including identity tampering, open-world semantics,
  asymmetric/irreflexive/functional characteristics, temporal overlaps,
  NEEM/document identity proposals and explicit SHACL dependency behavior).
- Real supplied ontology: 11,596 triples, 1,017 named OWL classes and
  966 properties; contains 119 named functional and one named asymmetric
  property declaration.
- Real uploaded `pickup_ontology_candidates.jsonl` contains 13
  Designator class candidates. The combined local report checks all 13
  against the real ontology SHA-256 and finds zero structural errors,
  zero OWL characteristic findings and zero temporal review candidates.
  **This does not validate the full NEEM SQL dataset or prove OWL-DL
  consistency.**

## Commands

Install required dependencies and run the regression suite:

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_semantic_validation.py \
  tests/test_entity_resolution.py tests/test_m6_remaining.py \
  tests/test_axiom_checks.py tests/test_review_report.py \
  tests/test_shacl_review.py
```

Generate combined review report:

```bash
python -m ontology_integration.review_report pickup_ontology_candidates.jsonl \
  --ontology cram-aicor-ontology.ttl \
  --output milestone6_pickup_review.json
```

SHACL is an opt-in additional check, not required for ordinary validation:

```bash
python -m pip install pyshacl
```

Then call `shacl_review.check_shacl(data_graph, shapes_graph)` with
explicitly reviewed shapes.

## Acceptance limits and next steps

**Scope delivered:** offline diagnostics and conservative review workflows,
including cross-source identity proposals.

**Not claimed complete:** exhaustive OWL-DL reasoning, SWRL inference,
`owl:imports` resolution, automatic reconciliation to canonical graph
identities, concurrency-safe durable review operations, complete
SHACL-shape coverage, and an exact checkout GitHub CI run. `pyshacl`
was not installed in the local execution environment; its missing-dependency
path, not its actual reasoning result, was tested.

No explicit approval should automatically generate `owl:sameAs` for the
production graph without a separate reviewed entity-mapping commit.
The remaining integration/acceptance work should be handled before
unrestricted TigerGraph writes. Milestone 7 may consume review outputs in
a staging-only mode, but production promotion stays gated.
