# Milestone 7 — TigerGraph ontology assertion staging (increment 1)

Branch: `neemGraph`. This increment does **not** modify TigerGraph GraphRAG's
existing `Entity`/`Relationship` ingestion paths.

## Purpose

Provide a loss-conscious, reproducible **staging projection** for the
Milestone 3 JSONL assertion model. Candidate, quarantined, validated,
asserted, inferred and retracted records retain their lifecycle status.
Inserting a vertex in a staging graph does **not** make it trusted.

## Components

- `tigergraph_staging.py`: deterministic, SHA-256 checked staging plans;
  asserts stable source-qualified assertion IDs; optional pyTigerGraph
  upserts guarded by explicit `enable_write=True`, matching graph name,
  and a verified dedicated staging vertex schema.
- `tigergraph_stage_cli.py`: completely offline JSONL-to-plan conversion.
  This command has **no** TigerGraph connectivity or write capability.
- `tests/test_tigergraph_staging.py`: plan determinism, preserving source
  distinction and lifecycle status, default dry-run, explicit opt-in and
  schema checks, tampering rejection, and unsupported named-graph rejection.

## Proposed **isolated staging** schema

The following is a proposed schema for a **separate** TigerGraph graph.
Review and apply through your environment's GSQL tools before enabling
the Python writer. It has **not** been executed on a live TigerGraph.

```gsql
CREATE VERTEX OntologyAssertionStage (
  PRIMARY_ID assertion_id STRING,
  statement_id STRING,
  subject_kind STRING,
  subject_value STRING,
  predicate_iri STRING,
  object_kind STRING,
  object_value STRING,
  object_datatype STRING,
  object_language STRING,
  source_type STRING,
  source_id STRING,
  source_locator STRING,
  source_method STRING,
  source_excerpt STRING,
  source_recorded_at STRING,
  derived_from_json STRING,
  ontology_sha256 STRING,
  assertion_status STRING,
  confidence STRING,
  valid_from STRING,
  valid_to STRING
) WITH primary_id_as_attribute="true";

CREATE GRAPH OntologyStagingGraph (OntologyAssertionStage);
```

All attributes are represented as strings to avoid lossy interpretation
of RDF literal lexical forms, timezone offsets, confidence, and
assertion lineage. Optional attributes use empty strings in this staging
projection; the source JSONL remains authoritative for null-vs-empty
distinctions. Inferred assertion derivation references are preserved as
a JSON-encoded list. Blank nodes and named graphs are currently
rejected until scoped representation is implemented.

The staging writer expects `connection.getVertexTypes()` to provide
the expected vertex `Name`, `PrimaryId.AttributeName`, and
`Attributes[].AttributeName` entries. Version-specific pyTigerGraph
schema shapes should be checked in a real environment before enabling
writes.

## First run: offline only

```bash
python -m ontology_integration.tigergraph_stage_cli \
  pickup_ontology_candidates.jsonl \
  --output pickup_stage_plan.json \
  --label pickup-001
```

Expected input: 13 previously mapped `Designator` candidates. The
result includes `OntologyAssertionStage` vertices, not trusted
GraphRAG entities or ontology inference statements.

## Developer write-gate example (no automatic connection)

```python
# connection must already be authenticated and set to OntologyStagingGraph
from ontology_integration.tigergraph_staging import stage_to_tigergraph

result = stage_to_tigergraph(plan, connection=connection)  # dry-run
# Only after independent schema verification and staging-graph approval:
result = stage_to_tigergraph(
    plan, connection=connection,
    enable_write=True, expected_graph="OntologyStagingGraph")
```

The writer upserts one vertex per assertion ID; repeated calls with
the same identical plan are idempotent at the vertex-key level.
Errors during a multi-vertex write can leave partial data; operators
must inspect/reconcile before retry.

## Security and promotion policy

- Never point the writer to the production GraphRAG graph.
- Do not promote candidate/quarantined assertions into trusted graph
  vertices or edges. Such promotion requires explicit validated status,
  review, schema-specific projection and integration tests.
- There is **no** implicit TigerGraph client creation and no credentials
  are written to disk.
- No live server, network, schema migration or Docker verification was
  performed in this increment.
- GitHub CI execution of the committed tests is pending.

## Next increments

1. Run exact-branch fixture suite and correct integration compatibility.
2. Confirm staged schema against a running TigerGraph instance.
3. Add read-back/reconciliation and batch acknowledgement semantics.
4. Implement a separate approved-only projection for domain KG facts,
   with source provenance and conflict gates.
5. Integrate ingestion into GraphRAG's service without bypassing its
   schema-aware document pipeline.

## Second increment — read-back reconciliation and approved-only projection

Additional modules on `neemGraph`:

- `tigergraph_reconcile.py`: after explicit staging writes, calls
  `getVerticesById` to compare exact returned attributes and IDs against
  the staging plan. Missing, changed, duplicate or unexpected vertices
  trigger a hard failure; the adapter never silently rewrites them.
  This operation is **not transactional**; partial writes may have occurred
  if the remote connection fails midway.
- `tigergraph_promotion.py`: produces a **projection-only** JSON artifact
  for explicitly approved assertion IDs when their Milestone 3 status is
  already `validated` or `asserted`. The input must include an exact
  ontology fingerprint, reviewer and rationale. Candidate, quarantined,
  inferred, retracted and missing IDs are rejected. This does **not**
  write facts into the production graph and does not itself verify that a
  purported `validated` record was genuinely reviewed.
- `gsql/ontology_staging.gsql`: version-reviewable staging graph proposal.
- `tests/test_tigergraph_reconcile_promotion.py`: fake-server round-trip,
  idempotent repeat, tampered read-back and approval guard tests.

### Local acceptance evidence

The previously exported `milestone7_pickup_stage_plan.json` was inspected
against its SHA-256 canonical payload and has **13 unique vertex IDs**, each
with a source locator. All 13 remain `candidate`. Consequently **zero**
pickup assertions currently qualify for promotion into the trusted graph.
No status is modified merely for the purpose of demonstrating ingestion.

The exact branch's GitHub CI tests are committed but the completed CI outcome
is **not yet available**. The remote TigerGraph server is unavailable in this
execution environment: Docker, pyTigerGraph and TigerGraph endpoint credentials
are absent. No live schema installation, insertion, reconciliation or GraphRAG
query can truthfully be claimed.

### Safe runbook for later live test

1. Check out `neemGraph`, run its regression suite and explicitly verify
   the current GitHub Actions result.
2. Review `gsql/ontology_staging.gsql` against your TigerGraph release and
   create a dedicated staging graph. Never overwrite the existing GraphRAG
   graph schema.
3. Export the assertion JSONL into a staging plan using
   `tigergraph_stage_cli.py`; examine source fingerprints, statuses and
   counts before proceeding.
4. Obtain an authenticated, **staging-graph-scoped** pyTigerGraph connection;
   verify its `getVertexTypes` and `getVerticesById` response shapes.
5. Call `apply_and_reconcile(plan,connection=connection,
   expected_graph="OntologyStagingGraph",enable_write=False)` first.
6. Only after authorization, set `enable_write=True` and require complete
   read-back reconciliation. Inspect partial writes if an exception occurs.
7. Separately review individual assertions and identity links before
   building a trusted GraphRAG projection.

### Milestone closure

**Offline staging/projection adapters are implemented; full Milestone 7
production acceptance remains blocked on a live TigerGraph instance, exact
branch CI, approved data, and a schema-specific trusted GraphRAG
integration/retrieval test.** The reader must not infer those capabilities
from successful offline schema/projection checks.
