"""CLI for ontology-guided ingestion of GraphRAG-preprocessed UTF-8 documents."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .axioms import build_axiom_index
from .document_pipeline import ingest_text, replay_provider
from .document_provider import ChatCompletionsProvider

def main():
    p=argparse.ArgumentParser(description="Extract ontology-backed candidate assertions from preprocessed text")
    p.add_argument("text_file")
    p.add_argument("--ontology",required=True)
    p.add_argument("--document-id",required=True)
    p.add_argument("--output-dir",required=True)
    provider=p.add_mutually_exclusive_group(required=True)
    provider.add_argument("--replay",help="JSON dictionary of chunk-id -> candidate-array")
    provider.add_argument("--llm",action="store_true",help="Use configured HTTPS chat-completions API")
    p.add_argument("--chunk-chars",type=int,default=1800)
    p.add_argument("--overlap",type=int,default=160)
    p.add_argument("--top-k",type=int,default=8)
    p.add_argument("--module-entries",type=int,default=40)
    args=p.parse_args()
    text=Path(args.text_file).read_text(encoding="utf-8")
    index=build_axiom_index(args.ontology)
    extractor=(ChatCompletionsProvider.from_env() if args.llm
               else replay_provider(json.loads(Path(args.replay).read_text(encoding="utf-8"))))
    result=ingest_text(text,document_id=args.document_id,ontology_index=index,
                       provider=extractor,max_chars=args.chunk_chars,overlap=args.overlap,
                       top_k=args.top_k,module_entries=args.module_entries)
    out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    if (out/"assertions.jsonl").exists() or (out/"manifest.json").exists():
        raise FileExistsError("Output files already exist; choose an empty directory")
    (out/"assertions.jsonl").write_text(result.candidates.to_jsonl(),encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps(result.to_dict(),indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result.to_dict(),indent=2))

if __name__=="__main__":
    main()
