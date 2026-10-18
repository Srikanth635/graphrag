"""Select ontology classes/properties for each text chunk by lexical evidence.

Candidate ranking is deterministic, not a neural retrieval model. Every
ontology class/property remains eligible: no Execution-specific shortlist.
"""
from __future__ import annotations
import re
from .module_builder import select_bounded_module, extraction_contract

WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
STOP = {"the","and","for","from","with","this","that","into","over","under",
        "some","thing","part","type","class","property","of","to","an","is",
        "a","as","or","in","on","at","be","by","has","are","was","were"}

def tokens(value: str) -> set[str]:
    split = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return {w.lower() for w in WORD.findall(split) if len(w)>2 and w.lower() not in STOP}

def _local_name(iri):
    return iri.rsplit("#",1)[-1].rsplit("/",1)[-1]

def rank_ontology_entries(text: str, index: dict, *, top_k: int=8):
    if top_k < 1:
        raise ValueError("top_k must be positive")
    content = tokens(text)
    ranked=[]
    for group in ("classes","properties"):
        for item in index[group]:
            labels=item.get("labels",[])
            lexical=tokens(_local_name(item["iri"]))
            for label in labels:
                lexical |= tokens(label)
            intersection=content & lexical
            if not intersection:
                continue
            exact_name=_local_name(item["iri"]).lower() in text.lower()
            score=2*len(intersection)+(3 if exact_name else 0)
            ranked.append({"iri":item["iri"],"score":score,
                           "matched_terms":sorted(intersection),"category":group})
    return sorted(ranked,key=lambda x:(-x["score"],x["iri"]))[:top_k]

def plan_extraction(chunk, index: dict, *, top_k=8, module_entries=40, depth=1):
    matches=rank_ontology_entries(chunk.text,index,top_k=top_k)
    if not matches:
        return {"chunk_id":chunk.chunk_id,"seeds":[],"contract":None,
                "reason":"no_supported_lexical_ontology_match"}
    module=select_bounded_module(index,[m["iri"] for m in matches],
                                 max_entries=module_entries,depth=depth)
    return {"chunk_id":chunk.chunk_id,"seeds":matches,
            "contract":extraction_contract(module),
            "module":{"selected_count":module["selected_count"],
                      "truncated":module["truncated"]}}
