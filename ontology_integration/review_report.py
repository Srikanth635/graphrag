"""Unified Milestone 6 review report, without mutating source assertions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from rdflib.namespace import RDF, OWL
from rdflib import URIRef
from .semantic_validation import SemanticValidator
from .axiom_checks import check_axiom_characteristics
from .temporal_conflicts import find_conflicting_values

def compile_review(validator, assertions):
    assertions = tuple(assertions)
    structural = validator.validate(assertions).to_dict()
    axioms = check_axiom_characteristics(validator.graph, assertions)
    functional = {str(p) for p in validator.graph.subjects(RDF.type, OWL.FunctionalProperty)
                  if isinstance(p, URIRef)}
    temporal = find_conflicting_values(assertions, functional_predicates=functional)
    return {
        'report_version': 'm6-review-v1', 'ontology_sha256': validator.fingerprint,
        'checked': len(assertions), 'structural': structural,
        'axiom_findings': [x.to_dict() for x in axioms],
        'temporal_review': [x.to_dict() for x in temporal],
        'validated_assertions': 0,
        'policy': 'diagnostic_only_no_auto_promotion_no_owl_dl_entailment',
    }

def main():
    from .assertions import Assertion
    parser = argparse.ArgumentParser()
    parser.add_argument('assertions_jsonl')
    parser.add_argument('--ontology', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    records = [Assertion.from_json(line) for line in
               Path(args.assertions_jsonl).read_text(encoding='utf-8').splitlines() if line.strip()]
    report = compile_review(SemanticValidator.from_turtle(args.ontology), records)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'checked': report['checked'], 'structural_errors': report['structural']['errors'],
                      'axiom_findings': len(report['axiom_findings']),
                      'temporal_reviews': len(report['temporal_review'])}))

if __name__ == '__main__':
    main()
