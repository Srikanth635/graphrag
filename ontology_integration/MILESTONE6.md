# Milestone 6 — Semantic validation and entity resolution (increment 1)

Branch: `neemGraph`, started 2026-10-18.

## Implemented

- `semantic_validation.py`: conservative structural checks on Milestone 3
  source-backed RDF assertions against the loaded ontology:
  ontology SHA-256 mismatch, unrecognized named class/property, literal
  vs. resource mismatch for OWL object/datatype properties, and explicitly
  incompatible named OWL disjoint classes (including named superclasses).
  RDFS domain/range are treated as open-world type implications, **not**
  closed-world rejection criteria.
- `entity_resolution.py`: deterministic source-evidence identity
  proposals. Same canonical IRI = already identical. Shared independently
  verified external identifier = review required. Equal labels alone =
  insufficient evidence. **No automatic owl:sameAs**.
- `validation_cli.py`: validate existing Milestone 3 JSONL assertions,
  serialize an inspection report without changing assertion status.
- `tests/test_semantic_validation.py` and
  `tests/test_entity_resolution.py`: five local regression tests.

## Local verification

5/5 tests passed in an isolated local test fixture. The real provided
CRAM/AICOR Turtle ontology loaded successfully, with **1,017 explicitly
declared classes and 966 properties**. A source-backed
`rdf:type <http://aicor.knowledge/l2-ontology.owl#Designator>`
assertion using the exact ontology SHA-256 produced zero structural issues.

The existing GitHub CI workflow was updated to include Milestone 6 tests,
but a completed CI run **has not been verified**. The branch code is committed;
the local tests used an equivalent local test implementation.

## Example

```bash
python -m pip install rdflib pytest
python -m pytest -q tests/test_semantic_validation.py tests/test_entity_resolution.py

python -m ontology_integration.validation_cli pickup_ontology_candidates.jsonl \
  --ontology cram-aicor-ontology.ttl \
  --output milestone6_review.json
```

## Scope limits and next acceptance work

This is **not a complete OWL-DL reasoner, SHACL validator, or entity merge
engine**. The current checker does not evaluate complex restrictions,
property chains, imported ontologies, anonymous disjoint lists, inverse
properties, property characteristics, datatype lexical validity, or
functional-property clashes. Those require reasoning and targeted tests.

A shared label, similar noun phrase or common robot action plan must
not be promoted to a cross-source identity without independent evidence.
Reviewers must adjudicate link proposals before any controlled ID mapping.

Next increments: SHACL or reasoner-assisted consistency checks, controlled
identity registry with explicit approval/rejection audit history, conflict
handling across observations and temporal windows, plus combined NEEM and
document evidence tests. Running OpenAI models live remains optional until
the user performs the configured local Milestone 5 test.
