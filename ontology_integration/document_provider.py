"""Optional OpenAI-compatible chat-completions JSON extractor.

Does not run without explicit endpoint/model/key. Treat response as untrusted:
the document pipeline validates all evidence spans and ontology IRIs.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

class ChatCompletionsProvider:
    def __init__(self, *, endpoint: str, model: str, api_key: str,
                 timeout_seconds: int = 90):
        parsed=urlsplit(endpoint)
        if parsed.scheme!="https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("HTTPS endpoint without embedded credentials required")
        if not model.strip() or not api_key.strip() or timeout_seconds < 1:
            raise ValueError("Model, key and positive timeout required")
        self.endpoint=endpoint
        self.model=model
        self.api_key=api_key
        self.timeout_seconds=timeout_seconds

    @classmethod
    def from_env(cls):
        for key in ("ONTOLOGYRAG_LLM_ENDPOINT","ONTOLOGYRAG_LLM_MODEL","ONTOLOGYRAG_LLM_API_KEY"):
            if not os.getenv(key):
                raise ValueError("Missing configured variable: "+key)
        return cls(endpoint=os.environ["ONTOLOGYRAG_LLM_ENDPOINT"],
                   model=os.environ["ONTOLOGYRAG_LLM_MODEL"],
                   api_key=os.environ["ONTOLOGYRAG_LLM_API_KEY"])

    def __call__(self, request: dict) -> list[dict]:
        prompt={
          "role":"user",
          "content":json.dumps(request,ensure_ascii=False),
        }
        body={"model":self.model,"temperature":0,
              "messages":[{"role":"system","content":
                "You extract source-grounded ontology facts. Return ONLY a JSON array. "
                "Each item needs subject_mention {start,end,text}, predicate_iri, "
                "object (for rdf:type, a class iri or for literals {kind,value,datatype/language}), "
                "or object_mention {start,end,text} for relations; and evidence_start, "
                "evidence_end, evidence_text. All offsets are 0-based Unicode character "
                "indices into the provided text; never invent entities or infer execution."},prompt]}
        payload=json.dumps(body).encode("utf-8")
        req=Request(self.endpoint,data=payload,method="POST",headers={
            "Authorization":"Bearer "+self.api_key,
            "Content-Type":"application/json"})
        with urlopen(req,timeout=self.timeout_seconds) as resp:
            data=resp.read(2_000_001)
        if len(data)>2_000_000:
            raise ValueError("LLM response exceeded 2 MB")
        outer=json.loads(data)
        content=outer["choices"][0]["message"]["content"]
        if not isinstance(content,str):
            raise ValueError("Model must return JSON string content")
        records=json.loads(content)
        if not isinstance(records,list) or len(records)>200:
            raise ValueError("Model output must contain at most 200 candidates")
        return records
