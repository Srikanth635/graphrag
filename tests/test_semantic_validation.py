"""Milestone 6 local structural validation tests."""
from hashlib import sha256
from rdflib.namespace import RDF
from ontology_integration.assertions import Assertion, RDFTerm, SourceEvidence
from ontology_integration.semantic_validation import SemanticValidator

EX="http://example.org/"

def item(p,o,h):
    return Assertion(RDFTerm("iri","urn:test:entity"),RDFTerm("iri",p),o,
                     SourceEvidence("document","doc","chars:0-4","fixture"),h)

def test_open_world_domain_and_explicit_disjoint(tmp_path):
    path=tmp_path/"ontology.ttl"
    path.write_text("""@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://example.org/Robot> a owl:Class ; owl:disjointWith <http://example.org/Place> .
<http://example.org/Place> a owl:Class .
<http://example.org/handles> a owl:ObjectProperty ;
  rdfs:domain <http://example.org/Robot> .
<http://example.org/name> a owl:DatatypeProperty .""")
    validator=SemanticValidator.from_turtle(path)
    hash_=sha256(path.read_bytes()).hexdigest()
    cases=[
      item(EX+"handles",RDFTerm("iri","urn:test:object"),hash_),
      item(EX+"handles",RDFTerm("literal","cup"),hash_),
      item(EX+"name",RDFTerm("iri","urn:test:object"),hash_),
      item(str(RDF.type),RDFTerm("iri",EX+"Robot"),hash_),
      item(str(RDF.type),RDFTerm("iri",EX+"Place"),hash_),
    ]
    result=validator.validate(cases)
    codes={x.code for x in result.issues}
    assert result.checked==5
    assert {"domain_range_open_world","object_property_literal",
            "datatype_property_resource","explicit_disjoint_types"}<=codes
    assert result.error_count>=3

def test_ontology_checksum_and_unrecognized_predicate(tmp_path):
    path=tmp_path/"ontology.ttl"
    path.write_text('<http://example.org/Robot> a <http://www.w3.org/2002/07/owl#Class> .')
    validator=SemanticValidator.from_turtle(path)
    result=validator.validate([item(EX+"unknown",RDFTerm("literal","x"),"a"*64)])
    assert {x.code for x in result.issues}=={
        "ontology_fingerprint_mismatch","unrecognized_predicate"}
