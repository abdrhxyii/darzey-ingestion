# R2 Storage Layout

R2 stores only original source files and immutable ingestion manifests.

```text
raw/<source>/<document-type>/<stable-source-id>/<language>/<file>.pdf
manifests/<source>/<document-type>/<stable-source-id>/<file>.json
```

Example for Extra Gazette No. `2501/95`:

```text
raw/documents.gov.lk/extra-gazette/2501-95/en/2501-95--sha256-a1b2c3d4e5f67890.pdf
manifests/documents.gov.lk/extra-gazette/2501-95/2501-95--sha256-a1b2c3d4e5f67890.json
```

## Key rules

- `source` is the official website host, for example `documents.gov.lk`.
- `document-type` is the normalized source category, for example
  `extra-gazette` or `judgment`.
- `stable-source-id` is the official source identifier, not an internal scraper
  ID. For Extra Gazettes it is the Gazette number with `/` replaced by `-`.
- `language` is `en`, `si`, `ta`, or `und` when the source does not identify it.
- The filename includes the first 16 characters of the full SHA-256 hash; the
  manifest records the full hash.
- Dates are manifest fields, never universal R2 path segments. Their meaning is
  source-specific: Gazette date, sitting date, judgment date, and so on.
- R2 must not store extracted text, chunks, embeddings, or vector data.
