# Milestone 4 — Conservative SQL/OWL semantic alignment (increment 2)

We inspected the uploaded `pickup_neem.sqlite` rather than guessing from
similarly named SQL tables. The raw data is not committed.

## Verified observations

- `DesignatorDAO`: 13 rows with polymorphic types including
  `PickUpActionDAO` and motion/action variants.
- `DesignatorNodeDAO`: 13 rows, each with a designator reference.
- `PlanNodeDAO`: 27 rows; 26 `NOT_STARTED`, one `SUCCEEDED`.
- `ActionNodeDAO`: 5 rows, **none** have a non-null
  `_execution_data_id`.
- `PickUpActionDAO`: one row, ID 4, with a designator parent.
- `PlanEdgeDAO` stores parent/child plan-node references. No direct
  mapping to OWL `hasSubaction` or executed actions is asserted.

## Explicit mapping (v1)

The source base table `DesignatorDAO` is mapped to the declared
ontology class `http://aicor.knowledge/l2-ontology.owl#Designator`.
Each SQL designator yields a **candidate** `rdf:type` assertion with
stable SQL row identity, ontology source hash, and a human-readable
mapping rationale. This is a reviewed domain correspondence based on
the table's polymorphic role and ontology declaration; later semantic
validation is still required.

The adapter `semantic_map.py` checks that the class actually exists
in the complete user ontology. It refuses an undeclared class and
never automatically maps a plan lifecycle status to an OWL execution
or achievement claim.

## Local acceptance

The real uploaded pickup dataset yielded **13 candidate owl:type
Designator assertions** with a stable batch digest. Three new fixture
tests passed; the complete local suite containing the milestone tests
passed **22 tests**.

The test suite ran against locally combined files; GitHub hosted CI and
runtime TigerGraph integration have not been verified.

## Safety and further work

The remaining SQL structure is retained in the staging namespace
`urn:neem:sql-schema:`, not promoted to ontology predicates.
Before adding more mapped terms, reconstruct DAO inheritance, verify
entity co-reference, align temporal semantics, and evaluate candidate
relationships with domain and range axioms. A class declaration alone
does not prove a table row is a valid instance. Continue keeping
assertions in `candidate` status until semantic review.

## Run

```python
from ontology_integration.semantic_map import mapped_designators, summarize_mapping
batch = mapped_designators(
    "pickup_neem.sqlite",
    neem_id="pickup-001",
    ontology_path="cram-aicor-ontology.ttl",
)
print(len(batch.assertions), batch.batch_id)
print(summarize_mapping("pickup_neem.sqlite"))
```
