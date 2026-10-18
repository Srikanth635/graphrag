# Milestone 5 — Ontology-guided document ingestion acceptance

Branch: `neemGraph`. Date: 2026-10-18.

## Implemented

The document-ingestion contract is connected end-to-end **offline**:
GraphRAG-preprocessed UTF-8 text -> deterministic source-exact chunks ->
ontology-wide lexical ranking of classes and properties ->
bounded ontology extraction contract -> pluggable extraction provider ->
strict evidence and class/property checks -> provenance-aware candidate
RDF assertions (Milestone 3).

Source ontology includes 1,017 named classes and 966 named properties.
The lexical seed selector searches the full index, **not** the small
`Execution` demonstration subset.

Files:
- `document_chunks.py`: SHA-256, overlap, Unicode character spans.
- `document_modules.py`: lexical ranking, dynamic ontology modules.
- `document_assertions.py`: exact IRI and verbatim evidence gate.
- `document_pipeline.py`: synchronous provider-neutral orchestration,
  source-scoped mention IDs; prevents LLM-invented cross-source entity IDs.
- `document_provider.py`: optional HTTPS chat-completions extractor.
  Requires a configured endpoint, model and API key. The untrusted model
  output is checked by the pipeline before becoming candidate RDF facts.
- `document_cli.py`: local CLI, either replay a JSON response fixture or
  use a configured HTTPS LLM.
- `tests/test_document_ingestion.py`,
  `tests/test_document_pipeline.py`,
  `tests/test_document_provider.py`: offline tests and provider mock.

## Run — deterministic replay

Use the supplied example text/replay artifact, or create your own replay
mapping keyed by `chunk_id`:

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_document_ingestion.py \
  tests/test_document_pipeline.py tests/test_document_provider.py

python -m ontology_integration.document_cli pickup_note.txt \
  --ontology cram-aicor-ontology.ttl \
  --document-id sample-pickup-note \
  --replay pickup_replay.json \
  --output-dir pickup-document-output
```

Output: `assertions.jsonl` with provenance-backed candidate statements
and `manifest.json` with document and batch checksums.

## Run — configured model

The adapter uses an **explicit** OpenAI-compatible chat-completions URL.
Configure these environment variables securely:

```bash
export ONTOLOGYRAG_LLM_ENDPOINT='https://your-provider.example/v1/chat/completions'
export ONTOLOGYRAG_LLM_MODEL='your-model'
export ONTOLOGYRAG_LLM_API_KEY='your-key'
python -m ontology_integration.document_cli preprocessed-document.txt \
  --ontology cram-aicor-ontology.ttl \
  --document-id research-note-001 \
  --llm --output-dir document-output
```

Never put API keys in repositories. The provider is synchronous; does
not implement retries, asynchronous queues or service-level controls.

## Evidence and identity safety

- Records must provide verifiable mention spans and verbatim supporting
  text; unsupported spans or ontology IRIs are rejected.
- Subject/object mention IDs depend on document ID, document SHA-256
  and exact character span. They do not assert entity equivalence
  across documents or to SQL NEEM entities.
- `rdf:type` class IRIs must belong to the selected ontology contract.
- Ontology restrictions are retrieval hints, not observed facts.
- All accepted statements remain candidate assertions; OWL reasoning,
  SHACL checks and manual review happen separately.
- Empty ontology lexical matches produce no claims rather than guessed
  ontology entities.
- A verbatim excerpt alone does not prove semantic truth. An extractor
  still needs evaluation for accuracy, confidence and recall.

## Actual verification status

Two isolated HTTP provider tests passed **locally** against the new
provider implementation, without a network call. The deterministic replay
fixture's SHA and evidence offsets were verified against a real text file,
and its OWL `Designator` IRI was verified in the supplied ontology index.

The branch-specific GitHub CI workflow includes all three document test
files, but **the full suite on the exact committed GitHub checkout has
not yet been verified**. There was no external LLM endpoint or credentials
available to perform a live model extraction test; the TigerGraph Docker
stack also has not been started here.

## Acceptance interpretation

The **offline document pipeline and pluggable extraction contract are
implemented**, but broader Milestone 5 production acceptance is still
blocked on a live configured LLM test, end-to-end GraphRAG preprocessor
handoff/API hook, robust ontology recall evaluation, and exact branch CI.
Do **not** report the full production ingestion system as verified.

Next: integrate with the existing GraphRAG preprocessing callback and
evaluate a human-reviewed document corpus before TigerGraph projection.
