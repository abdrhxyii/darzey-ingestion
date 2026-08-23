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

## Current automation

The scheduled workflow checks the current official Extra Gazette, Acts, and Bills
listings every six hours. Each document type has a separate manual backfill
workflow for safe, restartable archive batches.

## Extra Gazette backfill

The separate **Backfill Extra Gazettes** workflow is manual and accepts a year
range. It uses the official public Extra Gazette page, not the site's private
API host. Run small ranges, for example `2024` through `2024`; each rerun
safely preserves only R2 objects that do not already exist.

```powershell
python scripts/backfill_extra_gazettes.py --from-year 2024 --to-year 2024
```

## Acts backfill

The separate **Backfill Acts** workflow uses the official public Acts page and
the same immutable PDF + manifest contract. For example:

```powershell
python scripts/backfill_acts.py --from-year 2024 --to-year 2024
```

## Bills backfill

```powershell
python scripts/backfill_bills.py --from-year 2024 --to-year 2024
```
