# Milestone 4 — SQLite NEEM integration report (2026-10-18)

## Scope achieved

This is an incremental **NEEM SQL staging** pipeline, not a general
ORM-to-OWL compiler. User data stays outside Git. Changes on `neemGraph`:

- `sqlite_neem.py`: SQLite schema profile and source-qualified assertions
- `semantic_map.py`: explicit `DesignatorDAO` -> OWL `Designator`
  candidate class assertions only
- `neem_reconstruction.py`: inherited DAO PK->FK links, FK object links,
  source table identities, typed primitives, preserving timezone-naive
  timestamps as lexical strings and BLOBs as content hashes
- `neem_export.py`: bounded paged JSONL export, checkpoint manifests tied
  to SQL snapshot and ontology hashes, resumes and page-checksum verification
- `neem_audit.py`: row-count comparison against a **trusted** SQL dump,
  integrity and foreign-key checks
- `tests/test_neem_reconstruction.py`, `tests/test_neem_export.py`,
  `tests/test_neem_audit.py`: focused fixture tests

## Findings from the real uploaded pickup NEEM

- SQLite database passes `PRAGMA integrity_check` with `ok`.
- Schema contains 1,724 tables (125 populated), with 2,225 declared
  foreign-key links, of which 1,201 are joined-inheritance PK links.
- `PRAGMA foreign_key_check` reports zero violations.
- The supplied SQL dump reproduces row counts on all 1,724 tables
  and also has zero foreign-key-check violations.
- `PlanNodeDAO` has 27 records (26 `NOT_STARTED`, one `SUCCEEDED`).
- `PlanEdgeDAO` has 26 rows, `DesignatorDAO` 13, `ActionNodeDAO` 5,
  `PickUpActionDAO` 1, and `ExecutionDataDAO` **zero**.
- `PickUpActionDAO.database_id` is inherited from
  `ActionDescriptionDAO.database_id`, which inherits from
  `DesignatorDAO.database_id`.
- `ActionNodeDAO` inherits from `DesignatorNodeDAO`, which inherits
  from `PlanNodeDAO`; this is a source schema representation of plans
  and does not imply an observed execution.
- A class alignment to `Designator` creates 13 candidate triples;
  uncertain subclass/action/plan semantics remain in the SQL-source layer.

## Test status

The full SQLite/dump relationship and row-count audit above was actually
run against user uploads in the interactive execution environment.
The newly committed Python modules have fixture test code in the branch;
**GitHub CI and an exact checked-out-branch pytest run remain unverified**.
Do not infer passing automated CI from successful direct SQL audits.

Run tests in a checkout:

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_neem_reconstruction.py \
  tests/test_neem_export.py tests/test_neem_audit.py \
  tests/test_sqlite_neem.py tests/test_semantic_map.py
```

Example resumable export:

```bash
python -m ontology_integration.neem_export pickup_neem.sqlite \
  --ontology cram-aicor-ontology.ttl --neem-id pickup-001 \
  --table DesignatorDAO --table PlanNodeDAO --table PlanEdgeDAO \
  --table PickUpActionDAO --page-size 100 \
  --output-dir local_export
```

To resume an interrupted export, supply the same arguments and `--resume`.
Keep the database unchanged between pages. Checkpoints record the complete
file SHA-256 but are not signed. Output pages are only for source-reconstructed
candidate statements, not semantic validations.

## Deliberate limitations / follow-ups

- A successful source-FK join is **not** an OWL property mapping.
- SQL type hints are preserved where clear; timezone-naive timestamps
  cannot safely become timezone-aware instants.
- Binary content is fingerprinted, **not copied** into the RDF batch;
  retain the original SQLite database for retrieval and provenance.
- DAO polymorphism and identity across multiple NEEM files require
  further cross-run resolution and explicit mapping review.
- No ontology predicate mappings for plan edges, object designators, pose
  traces, or execution outcomes are asserted without stronger evidence.
- No raw structured JSON/database source exists yet for its adapter.
- No TigerGraph runtime ingestion, vectorization or graph-retrieval test
  has occurred; those belong to later integration milestones.
- The SQL fidelity check compares row counts, not full row-value equality.
- SQL dumps must be trusted before using `neem_audit.py` because the
  utility executes dump statements in a local in-memory SQLite database.

**Milestone status:** NEEM SQLite extraction/reconstruction groundwork
implemented. End-to-end Milestone 4 semantic population and integration
cannot truthfully be declared complete yet; the remaining OWL mappings
require additional domain interpretation and runtime validation.
