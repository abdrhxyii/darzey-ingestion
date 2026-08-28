# LegalAI Data Ingestion

Private-first ingestion pipeline for preserving official Sri Lankan legal
documents. The first milestone stores original PDFs and collection manifests.

This project intentionally does **not** implement RAG, embeddings, chunking, or
vector search yet.

## First milestone

For each discovered document, the pipeline will:

1. retain the official source and document metadata;
2. hash the downloaded PDF with SHA-256;
3. create an immutable R2 object key;
4. upload the original PDF to private object storage;
5. write a JSON manifest for audit and reprocessing;
6. skip an unchanged document when its hash already exists.

The source-specific network connector is deliberately kept separate from this
storage core. This prevents an unverified Government Printer API assumption
from becoming the storage contract.

## Layout

```text
src/legalai_ingestion/
  models.py              # normalized source and immutable manifest records
  object_keys.py         # deterministic R2 paths
  manifests.py           # manifest serialization
  connectors/             # source-specific discovery and downloads
  pipeline.py            # source preservation: PDF + manifest to R2
  storage/                # R2 and local test adapters
scripts/                  # sync and historical-backfill entry points
.github/workflows/       # scheduled sync and manual backfill workflows
docs/                     # source and storage contracts
tests/                    # non-destructive unit tests
```

See [repository structure](docs/repository-structure.md) and the
[R2 storage contract](docs/r2-storage-layout.md) before adding a source.

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

## Current operational focus

Bills are currently the active ingestion priority. Bills are discovered from
the live official `https://documents.gov.lk/web/bills` page and their files are
downloaded from the official `api/content-file-proxy` URLs returned by the
site. The private `gvp-api:4500` service, legacy `/view/...` URLs, and third-
party dataset snapshots are not used.

The Bills browser waits for the client-side page to finish loading before
using pagination. This is required because the table can be visible before
the pagination handler is ready. The workflow remains resumable and accepts
an optional `pages_per_run` input (default: 5).

## Resumable document backfills

The repository contains separate backfill workflows for Acts, Bills, Extra
Gazettes, normal Gazettes, and General Forms. Each resumable backfill keeps a
separate checkpoint in R2:

```text
state/documents.gov.lk/act/backfills/<from-year>-<to-year>.json
state/documents.gov.lk/bill/backfills/<from-year>-<to-year>.json
state/documents.gov.lk/gazette/backfills/<from-year>-<to-year>.json
state/documents.gov.lk/general-form/backfills/<from-year>-<to-year>.json
```

The checkpoint records the next official page. It advances only after the
preceding page has fully succeeded, so cancelled workflows resume safely.

For Bills, the checkpoint advances only after the preceding official listing
page has fully succeeded. A failed page is retried on the next run; PDFs are
not fetched until that page's records have been received.

No production ingestion uses the Hugging Face datasets. They are not treated
as a source of truth because their historical PDF URLs can become stale.
