"""Repeatable, resumable SQLite NEEM export over immutable database snapshots."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from .neem_reconstruction import extract_page, profile_relationships


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_snapshot(path, *, ontology_path, neem_id, tables, output_dir,
                    page_size=500, resume=False):
    """Export deterministic JSONL page files with checkpoint-bound source hashes.

    A source changed since a checkpoint is rejected. Only the caller owns
    the output directory. No automatic TigerGraph or OWL writes occur.
    """
    if page_size < 1 or not tables or not neem_id.strip():
        raise ValueError("Need page_size > 0, table names, and neem_id")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    source_hash = fingerprint(path)
    ontology_hash = fingerprint(ontology_path)
    manifest_path = directory / "manifest.json"
    settings = {"format": "neem-sqlite-pages-v1", "source_sha256": source_hash,
                "ontology_sha256": ontology_hash, "neem_id": neem_id,
                "tables": sorted(set(tables)), "page_size": page_size}
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text())
        if not resume:
            raise ValueError("Existing manifest; pass resume=True or use another output directory")
        if any(prior.get(k) != v for k,v in settings.items()):
            raise ValueError("Checkpoint settings or source fingerprint changed")
        verify_export(directory)\n        completed = list(prior.get("pages", []))
    else:
        completed = []
        manifest_path.write_text(json.dumps({**settings, "pages": []}, indent=2) + "\n")
    for table in settings["tables"]:
        table_pages = [p for p in completed if p["table"] == table]
        after = table_pages[-1]["last_key"] if table_pages else None
        if table_pages and table_pages[-1]["final"]:
            continue
        page_index = len(table_pages)
        while True:
            page = extract_page(path, neem_id=neem_id, ontology_sha256=ontology_hash,
                                table=table, after_key=after, page_size=page_size)
            if page.unmatched_foreign_keys:
                raise ValueError(f"Broken source foreign keys: {table}: {page.unmatched_foreign_keys}")
            # File names are indexed to avoid injecting arbitrary SQL names into paths.
            table_index = settings["tables"].index(table)
            filename = f"table_{table_index:04d}_page_{page_index:07d}.jsonl"
            blob = page.batch.to_jsonl()
            expected_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            target = directory / filename
            if target.exists():
                raise ValueError("Unexpected existing page: " + filename)
            target.write_text(blob, encoding="utf-8")
            last_key = page.next_key
            # For the final page, retain the last actual row key where possible.
            if last_key is None and page.inspected_rows:
                # This final key isn't used for resume, only for inspection.
                last_key = after
            entry = {"table": table, "file": filename, "sha256": expected_hash,
                     "assertions": len(page.batch.assertions),
                     "rows": page.inspected_rows, "last_key": last_key,
                     "final": page.next_key is None}
            completed.append(entry)
            manifest_path.write_text(
                json.dumps({**settings, "pages": completed}, indent=2) + "\n")
            if page.next_key is None:
                break
            after = page.next_key
            page_index += 1
    if fingerprint(path) != source_hash:
        raise ValueError("Source database changed during export")
    return verify_export(directory)


def verify_export(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    for entry in manifest["pages"]:
        payload = (directory / entry["file"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError("Export page checksum mismatch: " + entry["file"])
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite")
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--neem-id", required=True)
    parser.add_argument("--table", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = export_snapshot(args.sqlite, ontology_path=args.ontology,
                             neem_id=args.neem_id, tables=args.table,
                             output_dir=args.output_dir, page_size=args.page_size,
                             resume=args.resume)
    print(json.dumps({"pages": len(report["pages"]),
                      "assertions": sum(p["assertions"] for p in report["pages"])}))


if __name__ == "__main__":
    main()
