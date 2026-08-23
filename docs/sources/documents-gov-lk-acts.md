# documents.gov.lk — Acts

## Verified source format

The official public page is `https://documents.gov.lk/web/acts`. Its page
configuration identifies the upstream route as `act/get-all`; the private host
configured by the website is deliberately not called by this project.

Each official table record contains `actNoText`, `date`, descriptions, and an
array of language-specific `contents` file paths. Downloads use the public
official proxy:

```text
https://documents.gov.lk/api/content-file-proxy?file=/<uploaded-file>
```

## Source identity

```text
source:          documents.gov.lk
document_type:   act
stable_source_id: Act number, for example 18-2026
languages:       en, si, ta when published by the source
```

## Jobs

| Job | Entry point | Purpose |
| --- | --- | --- |
| Current sync | `scripts/ingest_acts.py` | Checks the first official listing page every six hours. |
| Historical backfill | `scripts/backfill_acts.py` | Uses public-page pagination and preserves only the chosen publication-year range. |

## R2 objects

```text
raw/documents.gov.lk/act/18-2026/en/18-2026--sha256-<hash-prefix>.pdf
manifests/documents.gov.lk/act/18-2026/18-2026--sha256-<hash-prefix>.json
```
