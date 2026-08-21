# LegalAI Data Ingestion

Private-first ingestion pipeline for preserving official Sri Lankan legal
documents. The first milestone stores original PDFs and collection manifests.

This project intentionally does **not** implement RAG, embeddings, or vector
search yet. It creates page-cited processing artifacts so a later private
retrieval store can index them without losing official PDF provenance.

## First milestone

For each discovered document, the pipeline will:

1. retain the official source and document metadata;
2. hash the downloaded PDF with SHA-256;
3. create an immutable R2 object key;
4. upload the original PDF to private object storage;
5. write a JSON manifest for audit and reprocessing;
6. skip an unchanged document when its hash already exists.
7. extract native text and use local OCRmyPDF/Tesseract only when pages lack
   usable text;
8. write an immutable derived text/OCR artifact under `derived/`.

The source-specific network connector is deliberately kept separate from this
storage core. This prevents an unverified Government Printer API assumption
from becoming the storage contract.

## Layout

```text
src/legalai_ingestion/
  models.py              # normalized source and manifest records
  object_keys.py         # deterministic R2 paths
  manifests.py           # JSON manifest serialization
  connectors/             # one adapter per official source
  storage/                # R2 and local test adapters
tests/                    # non-destructive unit tests
```

## Configuration

Production credentials must be supplied by the deployment secret manager. Do
not commit them to this repository.

```text
R2_ENDPOINT_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
```

## Run tests

```powershell
python -m pytest
```

The next approved milestone is one verified connector, beginning with a small
Extra Gazette sample. No full historical crawl should be enabled until the
sample has passed source, hash, PDF, manifest, and provenance checks.

## Current automation

The GitHub Actions workflow checks the R2 credentials and collects the first
page of Extra Gazettes every six hours. It follows the public download proxy
used by `documents.gov.lk`, stores each original PDF under `raw/`, and stores a
provenance manifest under `manifests/`. It extracts selectable text with
PyMuPDF and uses OCRmyPDF/Tesseract (`eng+sin+tam`) only when a page has too
little native text. The resulting page text and page-cited chunks are stored as
an immutable processing artifact under `derived/`; these artifacts are not a
vector database or the future canonical retrieval store. The workflow
intentionally starts with the first page only; historical backfill requires a
separate approved job.
