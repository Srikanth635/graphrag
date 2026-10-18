"""Entity resolution proposals must never silently merge entities."""
from ontology_integration.entity_resolution import EntityRecord, propose_links

def test_labels_alone_are_not_identity():
    neem=EntityRecord("urn:neem:thing:1","neem","pickup","Cup","DesignatorDAO/1")
    doc=EntityRecord("urn:document:mention:1","document","paper","cup","chars:4-7")
    result=propose_links([neem,doc])
    assert len(result)==1
    assert result[0].decision=="insufficient_evidence"
    assert result[0].reason=="same_label_only"

def test_shared_external_identifier_still_requires_review():
    neem=EntityRecord("urn:neem:thing:1","neem","pickup","Cup","row/1","ean:123")
    doc=EntityRecord("urn:document:mention:1","document","paper","Mug","chars:4-7","ean:123")
    results=propose_links([neem,doc])
    assert len(results)==1 and results[0].decision=="review_required"
    assert results[0].proposal_id==propose_links([neem,doc])[0].proposal_id

def test_equal_canonical_identity():
    neem=EntityRecord("urn:entity:1","neem","pickup","Cup","row/1")
    other=EntityRecord("urn:entity:1","neem","pickup","Cup","row/1")
    assert propose_links([neem,other])[0].decision=="already_identical"
