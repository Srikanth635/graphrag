FROM python:3.11.9
WORKDIR /code

COPY common/requirements.txt requirements.txt

RUN apt-get update && apt-get upgrade -y
RUN pip install -r requirements.txt\n# OntologyRAGs modules require RDFLib (not part of the upstream lock list).\nRUN pip install 'rdflib>=7,<9'

COPY graphrag/app /code
COPY common /code/common\n# Include neemGraph ontology integration in the backend image.\nCOPY ontology_integration /code/ontology_integration\nRUN python -c "import ontology_integration.semantic_validation, ontology_integration.neem_ingest, ontology_integration.document_pipeline, ontology_integration.tigergraph_staging"

# Version baked from the repo-root VERSION file. The build date is
# stamped at image-build time so plain ``docker compose build``
# captures both without any args or scripts.
COPY VERSION /code/VERSION
RUN date -u +%Y-%m-%dT%H:%M:%SZ > /code/BUILD_DATE

ENV SERVER_CONFIG="/server_config.json"
ENV LOGLEVEL="INFO"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "websockets-sansio"]
