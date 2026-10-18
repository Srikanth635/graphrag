# Milestone 4 — Real CRAM/NEEM SQL database ingestion (increment 1)

This adapter was developed against the user-provided `pickup_neem.sqlite`
and companion `pickup_neem.sql`. Source data is intentionally **not**
committed to the repository.

## Dataset observations (first fixture)

- SQLite integrity check: `ok`; 1,724 tables, 125 populated.
- PlanNodeDAO: 27 rows; PlanEdgeDAO: 26; PlanEntityDAO: 28.
- DesignatorDAO and DesignatorNodeDAO: 13 rows each.
- PickUpActionDAO: 1 row.
- PlanNodeDAO lifecycle: 26 `NOT_STARTED`, 1 `SUCCEEDED`.
- SQL dump replayed successfully in an in-memory SQLite database; counts
  matched the original for PlanNodeDAO, PlanEdgeDAO, DesignatorDAO and
  PickUpActionDAO.

These status values are recorded source fields. **Do not equate**
`NOT_STARTED` plan nodes with executed robot actions.

## What this increment does

`sqlite_neem.py` reads an existing SQLite database in read-only mode,
discovers all tables, primary keys and declared foreign keys, and turns
selected table rows into the normalized source-backed assertion envelope
from Milestone 3.

- Preserves SQL types (number or text), identifiers and FK references.
- Stages a source-level class for each row under `urn:neem:sql-schema:`.
- References source row identities under `urn:neem:entity:`.
- Uses a per-NEEM namespace to prevent accidental cross-run merges.
- Distinguishes **source schema statements** from CRAM/AICOR OWL assertions.
- Does not load TigerGraph or make any claim about OWL entailment.
- Foreign keys to non-`database_id` columns remain literal for review.

## Run on the supplied data (when available locally)

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_sqlite_neem.py
python -m ontology_integration.sqlite_neem pickup_neem.sqlite \
  --neem-id pickup-001 \
  --ontology /path/to/cram-aicor-ontology.ttl \
  --table PlanNodeDAO --table PlanEdgeDAO \
  --table PlanEntityDAO --table DesignatorDAO \
  --table DesignatorNodeDAO --table PickUpActionDAO \
  --output pickup-staging.jsonl
```

Local smoke test created **329 unique candidate assertions** from these
six selected tables; two runs produced the same batch ID. Three isolated
pytest tests passed. This is local verification, not hosted GitHub CI.

## What still needs implementation before saying Milestone 4 is complete

1. A reviewed, ontology-wide mapping layer: SQL classes/relationships must
   not be matched to similarly named OWL IRIs by string similarity alone.
2. Source-specific temporal typing and datatype handling.
3. Joined DAO inheritance reconstruction and object/designator linking.
4. Configurable table selection, export checkpoints and streaming for large
   NEEM files.
5. Full-database integration tests and SQL dump/SQLite fidelity checks,
   including nulls, FK references, and low-level kinematic data.
6. Provenance for SQL dump version, run identifiers and mapping decisions.

The existing schema-aware GraphRAG path and `main` remain unmodified.
