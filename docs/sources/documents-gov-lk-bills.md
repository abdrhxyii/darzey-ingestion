# documents.gov.lk — Bills

The official public page is `https://documents.gov.lk/web/bills`. Its public
table configuration identifies `bill/get-all`; the project does not call the
website's private upstream host.

Each record exposes `billNoText`, `date`, descriptions, and language-specific
file paths. PDFs are downloaded through the official public proxy.

```text
source:          documents.gov.lk
document_type:   bill
stable_source_id: Bill number, for example 57-2026
languages:       en, si, ta when published by the source
```

```text
raw/documents.gov.lk/bill/57-2026/en/57-2026--sha256-<hash-prefix>.pdf
manifests/documents.gov.lk/bill/57-2026/57-2026--sha256-<hash-prefix>.json
```

`scripts/ingest_bills.py` syncs the current first page every six hours.
`scripts/backfill_bills.py` preserves a selected publication-year range.
