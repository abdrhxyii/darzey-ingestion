# Repository Structure

This repository preserves source documents in private R2. It does not store
OCR text, chunks, embeddings, or vectors.

```text
src/legalai_ingestion/
  models.py                    # Shared discovered/stored document records
  object_keys.py               # R2 key construction; no source-specific logic
  manifests.py                 # Immutable manifest serialization
  pipeline.py                  # Shared PDF + manifest preservation service
  backfill_state.py            # Mutable R2 checkpoints for bounded archive runs

  connectors/
    documents_gov_lk.py         # Current documents.gov.lk Extra Gazette listing
    documents_gov_lk_archive.py # Historical Extra Gazette archive by year
    documents_gov_lk_acts.py    # Current documents.gov.lk Acts listing
    documents_gov_lk_acts_archive.py # Historical Acts archive by year
    documents_gov_lk_bills.py   # Current documents.gov.lk Bills listing
    documents_gov_lk_bills_archive.py # Historical Bills archive by year
    documents_gov_lk_gazettes.py # Gazette issue-date and part/section discovery
    documents_gov_lk_gazettes_archive.py # Historical Gazette date-list archive
    <source>.py                 # One future official-source adapter

  storage/
    base.py                     # Object-store interface
    r2.py                       # Production R2 implementation
    local.py                    # Non-destructive test implementation

scripts/
  ingest_extra_gazettes.py      # Recurring current-listing sync
  backfill_extra_gazettes.py    # Resumable historical archive batch
  ingest_acts.py                # Recurring current Acts sync
  backfill_acts.py              # Manual historical Acts backfill
  ingest_bills.py               # Recurring current Bills sync
  backfill_bills.py             # Manual historical Bills backfill
  ingest_gazettes.py            # Recurring current Gazette sync
  backfill_gazettes.py          # Manual historical Gazette backfill

.github/workflows/
  validate-and-check-r2.yml     # Tests and six-hour current-listing sync
  backfill-extra-gazettes.yml   # Scheduled/manual, resumable Extra Gazette batches
  backfill-acts.yml             # Manual, year-range Acts backfill
  backfill-bills.yml            # Manual, year-range Bills backfill
  backfill-gazettes.yml         # Manual, year-range Gazette backfill

docs/
  repository-structure.md
  r2-storage-layout.md
  sources/
    documents-gov-lk-extra-gazettes.md
    documents-gov-lk-acts.md
    documents-gov-lk-bills.md
    documents-gov-lk-gazettes.md

tests/
  test_ingestion_core.py
  test_extra_gazette_archive.py
```

## Rule for new sources

Create one connector per official website. The connector may discover and
download documents, but it must not construct R2 paths directly. It returns
`DiscoveredDocument` records to the shared preservation pipeline.
