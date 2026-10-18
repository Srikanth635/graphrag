"""Supplemental OWL characteristic checks with review-not-inference semantics."""
from __future__ import annotations
from dataclasses import dataclass
from rdflib import URIRef
from rdflib.namespace import OWL,RDF
from .assertions import TermKind

@dataclass(frozen=True)
class AxiomFinding:
    code: str
    severity: str
    assertion_ids: tuple[str,...]
    rationale: str
    def to_dict(self):
        return vars(self).copy()

def check_axiom_characteristics(ontology, assertions):
    """Check direct irreflexive/asymmetric violations, without full OWL reasoning."""
    assertions=tuple(assertions)
    irreflexive={str(p) for p in ontology.subjects(RDF.type, OWL.IrreflexiveProperty) if isinstance(p,URIRef)}
    asymmetric={str(p) for p in ontology.subjects(RDF.type, OWL.AsymmetricProperty) if isinstance(p,URIRef)}
    functional={str(p) for p in ontology.subjects(RDF.type, OWL.FunctionalProperty) if isinstance(p,URIRef)}
    by_sp={}
    triple_map={}
    output=[]
    for a in assertions:
        p=a.predicate.value
        by_sp.setdefault((a.subject.value,p),[]).append(a)
        if a.object.kind != TermKind.IRI:continue
        triple_map.setdefault((a.subject.value,p,a.object.value),[]).append(a)
        if p in irreflexive and a.subject.value==a.object.value:
            output.append(AxiomFinding('irreflexive_self_edge','error',(a.assertion_id,),
                                       'An irreflexive property cannot relate a resource to itself'))
    seen=set()
    for (s,p,o),links in triple_map.items():
        if p not in asymmetric or s==o:continue
        for reverse in triple_map.get((o,p,s),[]):
            for a in links:
                pair=tuple(sorted((a.assertion_id, reverse.assertion_id)))
                if pair not in seen:
                    seen.add(pair)
                    output.append(AxiomFinding('asymmetric_bidirectional','error',pair,
                                               'Asymmetric property asserted in both directions'))
    for (s,p), links in by_sp.items():
        if p not in functional:continue
        for i,a in enumerate(links):
            for b in links[i+1:]:
                if a.object==b.object:continue
                pair=tuple(sorted((a.assertion_id,b.assertion_id)))
                if a.object.kind==TermKind.LITERAL and b.object.kind==TermKind.LITERAL:
                    level='warning'
                    reason='Different literal lexical values require datatype-aware value comparison'
                else:
                    level='info'
                    reason='Functional object property may imply resource equality; not an automatic inconsistency'
                output.append(AxiomFinding('functional_competing_values',level,pair,reason))
    return tuple(sorted(output,key=lambda i:(i.code,i.assertion_ids)))
