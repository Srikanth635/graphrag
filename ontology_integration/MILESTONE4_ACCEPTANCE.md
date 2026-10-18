# Milestone 4 — SQL ingestion acceptance and outstanding semantic decisions

## Scope of completion

The **SQL/NEEM source adapter** is implemented: source-faithful read-only
staging, schema/FK/inheritance reconstruction, typed literal handling,
fingerprinted paginated export and resume, JSONL integrity verification,
trusted SQL-dump row-count audit, and a conservative OWL mapping quality gate.

This is **not** complete ontology-wide semantic mapping or TigerGraph graph
population. Only proven correspondences may be promoted into candidate OWL
assertions. The source graph can cover the entire SQL database without
asserting any invented CRAM/AICOR class or property relationship.

## Real pickup NEEM acceptance audit

- 1,724 SQL tables, of which 125 are populated; 31,878 total source rows
- 2,225 declared foreign keys, including 1,201 joined-inheritance links
- `PRAGMA integrity_check`: `ok`; foreign-key violations: zero
- SQL dump matches SQLite table counts across 1,724 tables (counts only)
- 13 DesignatorDAO rows are mapped to **candidate** OWL Designator class
  assertions with the SQL row identifier as evidence
- 27 PlanNodeDAO rows; 26 NOT_STARTED and one SUCCEEDED
- Zero ExecutionDataDAO rows, and zero non-null ActionNodeDAO execution refs
- 4 mapping proposals kept explicitly **not_mapped**: PlanNodeDAO ->
  Execution, PlanEdgeDAO -> hasSubaction, DesignatorNodeDAO reference ->
  realizesDesignator, and PickUpActionDAO -> Execution

See the generated quality report from the private pickup dataset; source data
is not committed to GitHub.

## Commands

Install Python 3.11, rdflib and pytest and run the focused tests:

```bash
python -m pip install rdflib pytest
python -m pytest -q \
  tests/test_sqlite_neem.py tests/test_semantic_map.py \
  tests/test_neem_reconstruction.py tests/test_neem_export.py \
  tests/test_neem_audit.py tests/test_neem_quality_gate.py
```

Export **all populated tables** (default with no `--table`):

```bash
python -m ontology_integration.neem_export pickup_neem.sqlite \
  --ontology cram-aicor-ontology.ttl --neem-id pickup-001 \
  --output-dir pickup-sql-staging --page-size 500
```

Resume against the **unchanged database snapshot** with the same arguments
plus `--resume`. Use `--table SomeDAO` repeatedly to restrict selection.

Run full SQL/OWL quality report:

```bash
python -m ontology_integration.neem_quality_gate pickup_neem.sqlite \
  cram-aicor-ontology.ttl --neem-id pickup-001 \
  --output pickup-mapping-audit.json
```

## Validation evidence

- The quality gate was locally tested against the real pickup SQLite and OWL
  files (three offline tests passed, including two synthetic/negative tests).
- Earlier source-level checks verified full SQL-dump row counts and FK integrity.
- The branch-specific GitHub Actions workflow
  `.github/workflows/ontology-neem-ci.yml` was committed to run the
  offline suite on code changes. **Do not claim it passed without inspecting
  a completed workflow run.**

## Important limitations

- SQL type declarations are not OWL class equivalence assertions.
- Datetime values lacking an offset are retained as lexical values; they
  must not be silently cast to UTC.
- BLOB payloads are hashed, not embedded in the graph; keep original SQLite
  database files for evidence lookup.
- Row counts alone do not establish complete SQL-dump value equality.
- SQL dump replay is appropriate only for a trusted dump.
- No new structured JSON source has been supplied, so no such source adapter
  can be end-to-end tested yet.
- OWL class/property mapping remains incomplete beyond Designator.
- GraphRAG Docker/TigerGraph end-to-end ingestion has not run here.

**Milestone status:** SQL ingestion infrastructure is substantially complete;
ontology-wide mapping coverage and downstream live GraphRAG integration are
not completed. Do not label these dependent capabilities complete.
