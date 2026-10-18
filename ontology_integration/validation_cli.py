"""Offline CLI: structural validation of Milestone 3 assertion JSONL.

Writes review findings; does not mutate assertion status or assert new facts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .assertions import Assertion
from .semantic_validation import SemanticValidator

def main():
    p=argparse.ArgumentParser(description="Conservative ontology validation of assertion JSONL")
    p.add_argument("assertions",help="Milestone 3 JSONL source-backed assertions")
    p.add_argument("--ontology",required=True,help="OWL/RDF ontology in Turtle format")
    p.add_argument("--output",required=True)
    args=p.parse_args()
    validator=SemanticValidator.from_turtle(args.ontology)
    raw=Path(args.assertions).read_text(encoding="utf-8")
    assertions=[Assertion.from_json(line) for line in raw.splitlines() if line.strip()]
    report=validator.validate(assertions).to_dict()
    report["ontology_sha256"]=validator.fingerprint
    report["semantic_scope"]="structural_open_world_no_full_owl_reasoning"
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"checked":report["checked"],"errors":report["errors"],
                      "issues":len(report["issues"])}))

if __name__=="__main__":
    main()
