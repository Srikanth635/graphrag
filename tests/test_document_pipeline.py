"""Contract tests for the complete provider-neutral document pipeline."""
import pytest
from rdflib.namespace import RDF
from ontology_integration.document_pipeline import ingest_text, mention_iri, replay_provider
from ontology_integration.document_chunks import chunk_text

EX = "http://aicor.knowledge/l2-ontology.owl#"
INDEX = {
  "sha256": "a"*64,
  "classes": [{"iri":EX+"Designator","labels":["Designator"],"axioms":[]}],
  "properties": [],
}

def response_for(text):
    pos=text.index("designator")
    return {
      "subject_mention":{"start":pos,"end":pos+10,"text":"designator"},
      "predicate_iri":str(RDF.type),
      "object":{"kind":"iri","value":EX+"Designator"},
      "evidence_start":pos,"evidence_end":pos+10,
      "evidence_text":"designator",
    }

def test_end_to_end_replay_and_stable_mentions():
    text="The designator describes the target."
    def provider(req): return [response_for(req["text"])]
    one=ingest_text(text,document_id="paper-1",ontology_index=INDEX,provider=provider,max_chars=100,overlap=20)
    two=ingest_text(text,document_id="paper-1",ontology_index=INDEX,provider=provider,max_chars=100,overlap=20)
    assert one.to_dict()==two.to_dict()
    assert len(one.candidates.assertions)==1
    a=one.candidates.assertions[0]
    assert a.subject.value.startswith("urn:ontologyrag:mention:")
    assert a.object.value==EX+"Designator"
    assert a.evidence.excerpt=="designator"
    assert a.status.value=="candidate"
    assert a.ontology_sha256=="a"*64
    assert a.evidence.locator.endswith("chars:4-14")

def test_reject_non_grounded_mentions_and_unapproved_class():
    text="The designator describes the target."
    def invalid(req):
        x=response_for(req["text"])
        x["subject_mention"]["text"]="fabricated"
        return [x]
    with pytest.raises(ValueError,match="Mention text"):
        ingest_text(text,document_id="paper",ontology_index=INDEX,provider=invalid,max_chars=100,overlap=20)
    def invalid_class(req):
        x=response_for(req["text"])
        x["object"]={"kind":"iri","value":EX+"Execution"}
        return [x]
    with pytest.raises(ValueError,match="Unapproved ontology class"):
        ingest_text(text,document_id="paper",ontology_index=INDEX,provider=invalid_class,max_chars=100,overlap=20)

def test_reject_provider_fabricated_entity_iris():
    text="The designator describes the target."
    def invalid(req):
        x=response_for(req["text"])
        x["subject_iri"]="urn:robot:allegedly-same"
        return [x]
    with pytest.raises(ValueError,match="Raw entity IRIs"):
        ingest_text(text,document_id="paper",ontology_index=INDEX,provider=invalid,max_chars=100,overlap=20)

def test_replay_and_no_match():
    text="The designator describes the target."
    chunk=chunk_text(text,document_id="paper",max_chars=100,overlap=20)[0]
    saved={chunk.chunk_id:[response_for(text)]}
    batch=ingest_text(text,document_id="paper",ontology_index=INDEX,provider=replay_provider(saved),max_chars=100,overlap=20)
    assert len(batch.candidates.assertions)==1
    no_match=ingest_text("Unrelated astronomy",document_id="paper",ontology_index=INDEX,
                         provider=lambda _:pytest.fail("No matched ontology module"),max_chars=100,overlap=20)
    assert no_match.selected_chunks==0
    assert no_match.chunks==1
    assert len(no_match.candidates.assertions)==0
    with pytest.raises(ValueError,match="recorded extraction response"):
        ingest_text(text,document_id="other",ontology_index=INDEX,provider=replay_provider(saved),max_chars=100,overlap=20)

def test_mention_id_is_source_scoped():
    h="a"*64
    a=mention_iri("paper-1",h,0,4,label="Robot")
    assert a!=mention_iri("paper-2",h,0,4,label="Robot")
    assert a==mention_iri("paper-1",h,0,4,label="Robot")
