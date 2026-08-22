# documents.gov.lk — Extra Gazettes

## Scope

This adapter preserves the original PDF versions of Extraordinary Gazettes from
`documents.gov.lk` in private R2.

## Source identity

```text
source:          documents.gov.lk
document_type:   extra-gazette
stable_source_id: Gazette number, for example 2501-95
languages:       en, si, ta when published by the source
```

## Jobs

| Job | Entry point | Purpose |
| --- | --- | --- |
| Current sync | `scripts/ingest_extra_gazettes.py` | Checks the current official listing every six hours. |
| Historical backfill | `scripts/backfill_extra_gazettes.py` | Scans the current official paginated records API once and preserves only the chosen publication-year range. |

## R2 objects

```text
raw/documents.gov.lk/extra-gazette/2501-95/en/2501-95--sha256-<hash-prefix>.pdf
manifests/documents.gov.lk/extra-gazette/2501-95/2501-95--sha256-<hash-prefix>.json
```

## Manifest fields

The manifest records source identity, title, official page URL, source PDF URL,
R2 object key, full SHA-256, byte size, content type, language, Gazette number,
publication date, archive year when applicable, download timestamp, pipeline
version, and status.

## Safety rules

- Validate that each download is a PDF before storing it.
- Do not overwrite an object with different bytes.
- Backfill runs are rate-limited and can be re-run after interruption.
- Original PDFs remain unchanged after preservation.
