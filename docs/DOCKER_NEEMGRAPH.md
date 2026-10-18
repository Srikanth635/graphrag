# Build and test `neemGraph` with Docker Compose

The repository already has a React frontend and a five-service GraphRAG
Compose stack. The custom ontology modules are now **included in the
backend image** on the `neemGraph` branch.

**Status of this document:** build/run instructions are prepared and the
Dockerfile is modified, but this assistant's environment has **no Docker
CLI or daemon** and cannot clone GitHub via DNS. Docker builds and live
startup have **not yet been executed here**.

## Requirements

- A local clone of the `neemGraph` branch
- Docker Engine and **Docker Compose v2** with build support (the UI uses
  `additional_contexts`)
- Sufficient disk, memory and network access for multiple large Python
  dependency installations, Node/pnpm and Golang builds
- An existing accessible TigerGraph instance, or a separately configured
  local TigerGraph server; it is not started by the current Compose file
- LLM credentials later, if you want live document extraction or GraphRAG
  chat/embeddings. **Not required for offline ontology smoke checks.**

The Docker Compose file currently has a TigerGraph service **commented
out**. The example server config points to `http://tigergraph`, which
will not resolve unless you separately create that service or edit the
database hostname to a reachable server. Connecting to the backend/UI is
not the same as validating a TigerGraph graph.

## 1. Clone and inspect

```bash
git clone https://github.com/Srikanth635/graphrag.git
cd graphrag
git switch neemGraph
git rev-parse --short HEAD

docker version
docker compose version
docker compose config --quiet
```

The backend Dockerfile now copies `ontology_integration/` and
installs `rdflib>=7,<9`; Compose names the locally built backend
`ontologyrag/graphrag:neemGraph` to avoid overwriting the upstream tag.

## 2. Build

To build only the customized backend and existing UI:

```bash
docker compose build graphrag graphrag-ui
```

Or build the complete application set:

```bash
docker compose build
```

The Dockerfile performs a Python import smoke test for the NEEM,
document, semantic validation and TigerGraph staging modules **during
the backend build**. This proves packaging/imports, not graph loading.

## 3. Run ontology tools inside the built image (no TigerGraph required)

```bash
docker compose run --rm --no-deps graphrag \
  python -c "import ontology_integration.neem_ingest, ontology_integration.semantic_validation, ontology_integration.document_pipeline, ontology_integration.tigergraph_staging; print('ontology imports OK')"
```

For a real local dataset, use the provided **example override** and put
the files into the ignored `local-data/` directory:

```bash
mkdir -p local-data
# Copy your own pickup_neem.sqlite and cram-aicor-ontology.ttl into local-data/
docker compose -f docker-compose.yml -f docker-compose.ontology.override.example.yml \
  run --rm --no-deps graphrag \
  python -m ontology_integration.neem_quality_gate \
  /data/pickup_neem.sqlite /data/cram-aicor-ontology.ttl \
  --neem-id pickup-local \
  --output /output/pickup-quality.json
```

The override maps `./local-data` read-only into `/data` and creates
`./local-output` for results. Do not check private records or secrets
into Git.

## 4. Configure TigerGraph and start the web stack

The current `configs/server_config.json` contains an example
`db_config.hostname` and placeholder `YOUR_LLM_API_KEY_HERE`. Use
your own supported TigerGraph hostname and authenticated configuration.
Review the upstream README for TigerGraph provisioning and GraphRAG
graph initialization. Do not commit credentials to `neemGraph`.

With a reachable TigerGraph database:

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=100 graphrag graphrag-ecc graphrag-ui nginx
```

Open:

- `http://localhost` — nginx / React application, login screen
- `http://localhost:3000` — React service directly
- `http://localhost:8000` — GraphRAG backend (API; not the ontology UI)
- `http://localhost:8001` — ECC service
- `http://localhost:8002` — chat-history

If authentication or graph initialization fails, inspect the logs and
server config instead of assuming the ontology integration is broken.
The existing UI only implements the upstream GraphRAG features; the
Milestone 4–7 ontology review tools are currently Python CLI interfaces.

## 5. TigerGraph staging is separate and opt-in

`ontology_integration/gsql/ontology_staging.gsql` is a **proposed
isolated** `OntologyStagingGraph` schema. Have an authorized TigerGraph
operator review it for your installed server version. Only after the
schema is installed should you enable `stage_to_tigergraph(...,
enable_write=True, expected_graph="OntologyStagingGraph")` on an
authenticated connection. Always run dry-run first, then read-back
reconciliation. Candidate assertions never become trusted graph facts
by being staged.

There is **no automatic hookup** from the upstream web UI into the
custom NEEM ingestion or approved-fact promotion flow, and there is
no verified live TigerGraph insertion yet.

## 6. Quick troubleshooting

- `docker: command not found`: install Docker and Docker Compose v2 on
  the host and ensure the daemon is running.
- UI build says `additional_contexts` unsupported: update Compose v2.
- `No module named ontology_integration`: check out the branch and
  rebuild `graphrag` after the Dockerfile change.
- Backend cannot resolve `tigergraph`: connect/configure a real database;
  the default Compose database service is commented out.
- Application builds but chatbot cannot answer: check graph initialization,
  LLM/embedding service setup and connectivity separately.
- `getVertexTypes`/read-back shape mismatch: the staging adapter targets
  a specific pyTigerGraph response contract and needs a server-backed
  compatibility test before enabling writes.

## Completion evidence to record

Save the checked-out commit SHA, `docker compose config` result,
backend/UI build logs, `docker compose ps`, runtime logs, source
assertion counts and the staging read-back report. Full project
acceptance requires a real document/NEEM-to-GraphRAG retrieval test,
not only successfully built containers.
