# documents.gov.lk — Gazettes

Gazettes are organized by publication date. One official issue date can publish
multiple PDFs, each identified by its official part and section.

```text
source:          documents.gov.lk
document_type:   gazette
stable_source_id: <date>-part-<part>-section-<section>
```

Example:

```text
raw/documents.gov.lk/gazette/2026-08-21-part-1-section-2/si/2026-08-21-part-1-section-2--sha256-<hash-prefix>.pdf
manifests/documents.gov.lk/gazette/2026-08-21-part-1-section-2/2026-08-21-part-1-section-2--sha256-<hash-prefix>.json
```

The connector reads the official public date list and issue pages. It only
preserves original PDF files; EPUB alternatives are excluded.
