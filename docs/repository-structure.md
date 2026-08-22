# Repository Structure

This repository preserves source documents in private R2. It does not store
OCR text, chunks, embeddings, or vectors.

```text
src/legalai_ingestion/
  models.py                    # Shared discovered/stored document records
  object_keys.py               # R2 key construction; no source-specific logic
  manifests.py                 # Immutable manifest serialization
  pipeline.py                  # Shared PDF + manifest preservation service

  connectors/
    documents_gov_lk.py         # Current documents.gov.lk Extra Gazette listing
    documents_gov_lk_archive.py # Historical Extra Gazette archive by year
    <source>.py                 # One future official-source adapter

  storage/
    base.py                     # Object-store interface
    r2.py                       # Production R2 implementation
    local.py                    # Non-destructive test implementation

scripts/
  ingest_extra_gazettes.py      # Recurring current-listing sync
  backfill_extra_gazettes.py    # Manual historical archive backfill

.github/workflows/
  validate-and-check-r2.yml     # Tests and six-hour current-listing sync
  backfill-extra-gazettes.yml   # Manual, year-range historical backfill

docs/
  repository-structure.md
  r2-storage-layout.md
  sources/
    documents-gov-lk-extra-gazettes.md

tests/
  test_ingestion_core.py
  test_extra_gazette_archive.py
```

## Rule for new sources

Create one connector per official website. The connector may discover and
download documents, but it must not construct R2 paths directly. It returns
`DiscoveredDocument` records to the shared preservation pipeline.
