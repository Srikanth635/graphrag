"""Offline NEEM ingestion end-to-end fixture without TigerGraph."""
import json
import sqlite3
from pathlib import Path
from ontology_integration.neem_ingest import ingest_neem

def test_offline_neem_ingest_and_resume(tmp_path: Path):
    db=tmp_path/"pickup.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE DesignatorDAO(database_id INTEGER PRIMARY KEY, polymorphic_type TEXT);
        CREATE TABLE PlanNodeDAO(database_id INTEGER PRIMARY KEY, status TEXT);
        CREATE TABLE ExecutionDataDAO(database_id INTEGER PRIMARY KEY);
        CREATE TABLE ActionNodeDAO(
          database_id INTEGER PRIMARY KEY,
          _execution_data_id INTEGER REFERENCES ExecutionDataDAO(database_id));
        INSERT INTO DesignatorDAO VALUES(4,'PickUpActionDAO');
        INSERT INTO PlanNodeDAO VALUES(1,'NOT_STARTED');
        INSERT INTO ActionNodeDAO VALUES(8,NULL);
        """)
    ontology=tmp_path/"ontology.ttl"
    ontology.write_text('@prefix owl: <http://www.w3.org/2002/07/owl#> . '
        '<http://aicor.knowledge/l2-ontology.owl#Designator> a owl:Class .')
    output=tmp_path/"output"
    first=ingest_neem(db,ontology,neem_id="pickup",output_dir=output,page_size=1)
    assert first["sql_source_rows"]==3
    assert first["owl_candidates"]==1
    assert first["sql_staged_assertions"]==first["sql_candidate_assertions_expected"]
    assert first["sql_unmatched_fk_targets"]==0
    assert not first["ontology_wide_semantic_mapping_complete"]
    assert not first["tigergraph_ingestion_performed"]
    assert len((output/"ontology_candidates.jsonl").read_text().splitlines())==1
    assert json.loads((output/"manifest.json").read_text())==first
    resumed=ingest_neem(db,ontology,neem_id="pickup",output_dir=output,
                        page_size=1,resume=True)
    assert resumed==first
