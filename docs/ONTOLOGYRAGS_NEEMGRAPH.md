# OntologyRAGs on TigerGraph GraphRAG (`neemGraph` branch)

This branch extends the upstream **TigerGraph GraphRAG v2.0.3** application
with an experimental ontology-guided ingestion toolkit under
`ontology_integration/`. It is **not** an end-to-end production-ready
ontology GraphRAG service, and simply opening the existing web UI does not
automatically execute the ontology workflows.

## Architecture

```text
                       OWL/RDF ontology
                             |
                registry / OWL axiom indexing
                             |
             bounded ontology extraction modules
                             |
      +----------------------+----------------------+
      |                                             |
NEEM SQLite / trusted SQL dump                preprocessed document text
DAO schema/FK/inheritance                     chunks / scoped extraction
source-level RDF statements                   LLM or replay candidates
      |                                             |
      +----------------------+----------------------+
                             |
              shared evidence-backed assertion model
                             |
               structural OWL checks + optional SHACL
               identity review + temporal conflict review
                             |
                approved / candidate-aware staging
                             |
        separate TigerGraph OntologyStagingGraph (opt-in)
                             |
           FUTURE: approved domain KG projection + GraphRAG retrieval
```

## Milestone implementation and acceptance

| Milestone | Implemented branch capabilities | Acceptance still pending |
|---|---|---|
| 1 — Registry | OWL/RDF named vocabulary registry and metadata | Exact current-commit CI verification |
| 2 — OWL module selection | Axiom indexing, bounded per-input semantic modules | Complete OWL entailment/import reasoning |
| 3 — Assertion contract | RDF terms, assertion IDs, evidence, candidate/validated lifecycle, JSONL | Production persistence and status governance |
| 4 — NEEM SQL | SQLite profiling, inheritance and FK extraction, whole-database paging, fingerprints, quality audits | More reviewed source-to-OWL mappings and whole-flow integration |
| 5 — Documents | Preprocessed-text chunking, lexical ontology module retrieval, configurable OpenAI-compatible extraction, evidence checks | Live LLM, accuracy evaluation and GraphRAG preprocessing API handoff |
| 6 — Validation | Structural/axiom/temporal diagnostics, link proposals, review ledger, optional SHACL | Full reasoning, approved SHACL shape coverage, durable review integration |
| 7 — TigerGraph | Source-preserving staging plans, guarded staging upserts and read-back, approved-only **offline** fact projections | Live TigerGraph deployment, promotion to native GraphRAG domain KG and end-to-end retrieval |

**Do not interpret “implemented” as “tested in a running TigerGraph stack”.**
The actual pickup example yielded 13 source-backed candidate
`rdf:type Designator` assertions; all remain candidates, with zero
approved-for-production promotions. Existing staging tests use fake
connections. GitHub Actions results must be checked independently.

## Source inputs and sample commands

Do not commit robot experience databases, research documents, credentials,
or derived private output to Git. The supplied test data is **not** part
of this repository. Place your own files outside the checkout or in
an ignored local directory.

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_sqlite_neem.py tests/test_document_pipeline.py \
  tests/test_semantic_validation.py tests/test_tigergraph_staging.py

# Offline NEEM extraction to source staging + separate OWL candidates
python -m ontology_integration.neem_ingest pickup_neem.sqlite \
  --ontology cram-aicor-ontology.ttl --neem-id pickup-001 \
  --output-dir pickup-staging

# Check ontology candidates against structural and OWL characteristics
python -m ontology_integration.review_report \
  pickup-staging/ontology_candidates.jsonl \
  --ontology cram-aicor-ontology.ttl \
  --output pickup-review.json

# Offline plan; does NOT write to TigerGraph
python -m ontology_integration.tigergraph_stage_cli \
  pickup-staging/ontology_candidates.jsonl \
  --output pickup-stage-plan.json
```

Document extraction uses
`python -m ontology_integration.document_cli` with either `--replay`
or `--llm`. For OpenAI, configure the HTTPS chat completions endpoint,
a selected model, and `ONTOLOGYRAG_LLM_API_KEY` locally. Never paste
keys into the repository or sample config.

## The existing web application

The upstream application includes the React + TypeScript + Vite
`graphrag-ui/` frontend. Its routes include login (`/`), chat
(`/chat`), graph setup (`/setup/kg-admin`), document ingestion
(`/setup/kg-admin/ingest`, see the routes in `src/main.tsx`), and trace
logs. The browser entry point through nginx is `http://localhost`
with default ports in `docker-compose.yml`.

These are **upstream GraphRAG features**. There are not yet dedicated UI
screens for ontology registry/module inspection, NEEM import, mapping review
or OWL validation. Those workflows currently run through Python CLIs.
GraphRAG's existing document ingest UI is not yet wired to the new
ontology extraction pipeline.

## Container support

The branch's `graphrag/Dockerfile` now copies
`ontology_integration/` into the backend image and installs RDFLib.
The Compose `graphrag` image uses the isolated local tag
`ontologyrag/graphrag:neemGraph` so it does not overwrite upstream's
`tigergraph/graphrag:latest` tag.

See [Docker build and test runbook](./DOCKER_NEEMGRAPH.md). The branch
also includes a manually triggered GitHub Actions Docker build workflow.
The image has **not** been built or booted in this assistant execution
environment: no Docker daemon, Docker CLI, or TigerGraph server is present.

## Repository locations

- `ontology_integration/` — Milestones 1–7 modules and per-milestone docs
- `ontology_integration/gsql/ontology_staging.gsql` — isolated staging schema proposal
- `graphrag/` — GraphRAG backend and Dockerfile
- `ecc/` — upstream extraction service
- `graphrag-ui/` — existing React frontend
- `docker-compose.yml` — five application services; TigerGraph DB commented
- `configs/server_config.json` — **example** service and model settings;
  do not commit populated API keys
- `.github/workflows/ontology-neem-ci.yml` — offline regression tests

## Final acceptance checklist

- [ ] Full suite passes on the exact `neemGraph` commit
- [ ] Backend + UI Docker images build
- [ ] All five Compose application services start and UI loads
- [ ] TigerGraph server is provisioned and authenticated
- [ ] Dedicated staging schema installed and live upsert/read-back verified
- [ ] OpenAI document extraction evaluated against labelled examples
- [ ] Representative NEEM-to-OWL mapping decisions approved
- [ ] Validated assertions projected into an approved domain KG
- [ ] GraphRAG retrieval retrieves and cites approved ontology facts

This checklist intentionally stays open until each operation is evidenced.
