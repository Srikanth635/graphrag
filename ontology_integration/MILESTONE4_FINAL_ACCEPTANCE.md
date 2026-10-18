# Milestone 4: NEEM SQL source ingestion acceptance report

Date: 2026-10-18. Branch: `neemGraph`.

## Delivery

The **NEEM SQLite source-ingestion pipeline is implemented** without external
JSON mapping files. Source-faithful RDF statements, explicit reviewed OWL
candidates and non-promoted mapping decisions are kept **separate**.

Latest modules:
- `sqlite_neem.py`: schema introspection and initial source staging
- `neem_reconstruction.py`: read-only table + FK + inherited-row statement staging
- `neem_identity.py`: canonical SQL row identity across PK=FK DAO parent chains;
  creates **no** owl:sameAs statements
- `neem_export.py`: paged all-populated-table JSONL export with SHA-256 manifest
- `neem_full_scan.py`: exact all-table source statement coverage audit
- `neem_audit.py`: trusted SQL dump vs SQLite integrity/row-count comparison
- `semantic_map.py`: explicit conservative DesignatorDAO -> OWL Designator
- `neem_quality_gate.py`: ontology checksum, SQL integrity and mapping review
- `neem_ingest.py`: single offline CLI to stage source statements, produce
  separate ontology candidate JSONL, and write acceptance manifest
- Branch workflow `.github/workflows/ontology-neem-ci.yml` plus offline fixture tests

## Repeatable offline command

```bash
python -m pip install rdflib pytest
python -m ontology_integration.neem_ingest pickup_neem.sqlite \
  --ontology cram-aicor-ontology.ttl \
  --neem-id pickup-001 \
  --output-dir pickup-staging \
  --page-size 500
```

Run again with `--resume` against the same unchanged source snapshot.
The output includes separate `source/manifest.json`, staged SQL assertion
pages, `ontology_candidates.jsonl`, `quality.json`, and top-level
`manifest.json`. Never treat SQL-source predicates as ontology properties.

## Real pickup database evidence (locally checked)

- 1,724 SQL tables / 125 populated
- 31,878 SQL rows
- 107,907 **potential source-level** RDF statements under the current staging
  rules, of which 16,187 link joined-inheritance rows and 23,386 reference
  other SQL rows by ordinary foreign keys
- 0 unresolved foreign-key targets, `PRAGMA integrity_check = ok`
- 222 populated SQL table/column property pairs
- 5,130 null field occurrences omitted
- 13 DesignatorDAO -> owl:Designator **candidate** assertions
- 0 ExecutionDataDAO rows, and 0 non-null ActionNodeDAO execution references
- 27 plan nodes: 26 NOT_STARTED and 1 SUCCEEDED
- SQL dump row counts match the SQLite database across all 1,724 tables;
  this is **not** a byte-for-byte or row-value-equivalence guarantee

A local three-test quality-gate suite passed, and the identity resolver was
manually verified against the real pickup inherited-row chains:
`PickUpActionDAO(4)` -> `ActionDescriptionDAO(4)` ->
`DesignatorDAO(4)` share canonical source identity
`urn:neem:entity:pickup-001:DesignatorDAO:4`.

The 107,907 figure comes from an exhaustive read-only full-database scan,
not a claimed completed 107,907-row export through GitHub CI.
The exact checked-out-branch regression suite is still **unverified** because
the execution container lacks direct GitHub network access. The last GitHub
commit query returned no completed status checks. The workflow is committed,
but passing hosted CI must not be inferred.

## Deferred semantic and infrastructure dependencies

**The source adapter can cover every populated table; exhaustive semantic
OWL promotion is not yet proved.** User-provided files do not establish
that PlanNodeDAO instances are performed `Execution` instances, or that
PlanEdgeDAO edges satisfy ontology `hasSubaction`. The quality gate keeps
these mappings explicitly unapproved.

In addition, no independent arbitrary structured-data dataset/mapping is
available yet, and TigerGraph/GraphRAG Docker integration and SHACL/OWL
reasoning have not run here. These are **not** deliverables verified by this
offline SQL pipeline. Further semantic mapping decisions require source
semantics/evidence and are not safely automatable via table name matching.

## Closure recommendation

Mark **Milestone 4A (NEEM SQL extraction and normalized-source staging)
implemented, acceptance pending exact branch CI**. Do not call the broader
**Milestone 4B (exhaustive ontology mapping and live integration) complete**.
A technical limitation is more honest than fabricating ontology semantics.
