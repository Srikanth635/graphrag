"""Generate a TigerGraph staging plan from Milestone 3 JSONL, offline."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .assertions import Assertion
from .tigergraph_staging import stage_plan, write_plan

def main():
    parser=argparse.ArgumentParser(description="Offline TigerGraph staging projection; never writes to a server")
    parser.add_argument("assertions_jsonl")
    parser.add_argument("--output",required=True)
    parser.add_argument("--label",default="ontology-staging")
    args=parser.parse_args()
    assertions=[Assertion.from_json(line) for line in
                Path(args.assertions_jsonl).read_text(encoding="utf-8").splitlines()
                if line.strip()]
    plan=stage_plan(assertions,label=args.label)
    write_plan(plan,args.output)
    print(json.dumps({"count":plan["count"],"vertex_type":plan["vertex_type"],
                      "payload_sha256":plan["payload_sha256"],
                      "server_writes":0}))

if __name__=="__main__":
    main()
