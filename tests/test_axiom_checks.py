"""Supplemental OWL property characteristic checks."""
from rdflib import Graph
from ontology_integration.axiom_checks import check_axiom_characteristics
from ontology_integration.assertions import RDFTerm, SourceEvidence, Assertion

def test_characteristics_without_full_owl_reasoner():
    ont=Graph().parse(data='''@prefix owl: <http://www.w3.org/2002/07/owl#> .
    <urn:p:next> a owl:AsymmetricProperty, owl:IrreflexiveProperty .
    <urn:p:value> a owl:FunctionalProperty .''',format='turtle')
    def assertion(s,p,o):
        return Assertion(RDFTerm('iri',s),RDFTerm('iri',p),RDFTerm('iri',o),
                         SourceEvidence('test','fixture',s+p+o,'test'),'a'*64)
    rows=[assertion('urn:x','urn:p:next','urn:x'),
          assertion('urn:x','urn:p:next','urn:y'),
          assertion('urn:y','urn:p:next','urn:x'),
          assertion('urn:x','urn:p:value','urn:y'),
          assertion('urn:x','urn:p:value','urn:z')]
    found=check_axiom_characteristics(ont,rows)
    assert {f.code for f in found}=={
        'irreflexive_self_edge','asymmetric_bidirectional','functional_competing_values'}
    assert next(f for f in found if f.code=='functional_competing_values').severity=='info'
