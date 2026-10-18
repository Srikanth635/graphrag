# Milestone 5 — Ontology-guided document ingestion, first increment

Branch: `neemGraph`. The TigerGraph GraphRAG README documents an existing
document ingestion/preprocessing process: local uploads convert PDFs and
other documents to text before graph ingestion. This increment deliberately
**reuses that preprocessed text as input** rather than introducing a competing
PDF parser or another vector database.

## Added components

- `document_chunks.py`: deterministic, overlapping Unicode character-offset
  chunks; stable document SHA-256 and chunk IDs; exact-source verification.
- `document_modules.py`: deterministic lexical ranking across **every**
  indexed OWL class/property, bounded module selection and extraction
  contract generation using Milestone 2. This is a retrieval baseline,
  not a semantic embedding/reranker service.
- `document_assertions.py`: strict external-extractor adapter. It accepts
  candidate records only when ontology IRIs belong to the selected contract
  and the verbatim evidence matches the chunk at the supplied offsets;
  outputs Milestone 3 RDF candidate assertions with document provenance.
- `tests/test_document_ingestion.py`: tests for chunk replay, overlap,
  ontology-wide retrieval, evidence, class guarding and no-match paths.

## Example usage

```python
from ontology_integration.axioms import build_axiom_index
from ontology_integration.document_chunks import chunk_text
from ontology_integration.document_modules import plan_extraction
from ontology_integration.document_assertions import extraction_request, accept_candidates

index = build_axiom_index("cram-aicor-ontology.ttl")
text = "Robot action descriptions from an already preprocessed document."
for chunk in chunk_text(text, document_id="paper-001"):
    plan = plan_extraction(chunk, index, top_k=8, module_entries=50)
    if plan["contract"] is None:
        continue
    request = extraction_request(chunk, plan["contract"])
    # Pass request to a configured trusted extraction service / human review.
    # The service must return candidate dictionaries with exact evidence spans.
    candidates = []
    batch = accept_candidates(chunk, text, plan["contract"], candidates)
    print(batch.batch_id)
```

## Semantic and runtime limitations

1. **No LLM extraction has been invoked yet**. The bridge prepares an
   extraction request and validates candidates, but requires an extractor.
2. The lexical ranker is conservative and may miss synonyms or multiword
   expressions; contextual embedding retrieval and fallback ontology-wide
   search are planned.
3. The extractor must supply trustworthy entity IRIs; stable document mention
   IDs and cross-source linking require a dedicated entity-linking stage.
4. Supported document input here is UTF-8 text already produced by GraphRAG's
   preprocessing; PDF/layout, OCR, image captions and upload APIs are not
   duplicated or modified.
5. OWL restrictions are hints, never evidence or validation constraints.
6. No TigerGraph DB writes or remote GraphRAG API integration occur.
7. GitHub CI has been updated to include the test file. Its actual result
   has **not been verified**; the local environment cannot clone GitHub
   because DNS/network access is unavailable.

## Milestone acceptance still ahead

Add configured extractor interface and fixture replay, stronger ontology
retrieval (labels/synonyms/context), document entity identity and relation
validation, then integrate the GraphRAG preprocessed-document handoff and
run combined NEEM/document ingestion tests on the branch.
