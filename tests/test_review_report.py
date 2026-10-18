"""Milestone 6 unified diagnostic review tests."""
from hashlib import sha256
from ontology_integration.assertions import Assertion, RDFTerm, SourceEvidence
from ontology_integration.semantic_validation import SemanticValidator
from ontology_integration.review_report import compile_review

def test_report_does_not_promote_assertions(tmp_path):
    ontology=tmp_path/'ontology.ttl'
    ontology.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
    <urn:test:Person> a owl:Class .
    <urn:test:hasState> a owl:FunctionalProperty, owl:DatatypeProperty .''')
    fingerprint=sha256(ontology.read_bytes()).hexdigest()
    def observation(value,index):
        return Assertion(subject=RDFTerm('iri','urn:test:subject'),
                         predicate=RDFTerm('iri','urn:test:hasState'),
                         object=RDFTerm('literal',value),
                         evidence=SourceEvidence('document','paper',f'chars:{index}','test'),
                         ontology_sha256=fingerprint)
    report=compile_review(SemanticValidator.from_turtle(ontology),
                          [observation('a',1),observation('b',2)])
    assert report['validated_assertions']==0
    assert report['checked']==2
    assert len(report['axiom_findings'])==1
    assert len(report['temporal_review'])==1
    assert report['temporal_review'][0]['decision']=='review_required'
