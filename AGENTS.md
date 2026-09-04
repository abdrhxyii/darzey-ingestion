# Agent Instructions

## Project purpose

This repository preserves original legal documents published by government
websites. The ingestion system stores the raw source files and their metadata
manifests in R2. Text extraction, OCR, chunking, embeddings, search, and RAG
are separate later stages.

The system must support multiple government websites and multiple document
types under each website.

## Repository organization

Connectors are grouped by government website. The documents.gov.lk connector
uses `connectors/documents_gov_lk/` with `common.py` for shared HTTP/PDF
helpers, `archive.py` for shared pagination, and separate `acts.py`,
`bills.py`, `extra_gazettes.py`, and `forms.py` modules. Matching `_archive.py`
modules contain historical discovery for the types that need it. Normal
Gazettes are intentionally removed from active ingestion.

```text
src/legalai_ingestion/
├── models.py
├── manifests.py
├── object_keys.py
├── pipeline.py
├── backfill_state.py
├── connectors/
│   ├── documents_gov_lk.py                    # shared source helpers
│   ├── documents_gov_lk_<type>.py             # current-page discovery
│   ├── documents_gov_lk_<type>_archive.py     # historical/backfill discovery
│   └── ...
└── storage/
    ├── r2.py
    └── local.py
```

The `_archive.py` suffix means historical, paginated, or year-range backfill
logic. It is an implementation pattern, not a separate storage area and not
an indication that the code is obsolete.

Each `<type>.py` and `<type>_archive.py` file owns only that source and
document type's URLs, discovery method, response parsing, metadata mapping,
and official file URL construction. Shared pagination belongs in `archive.py`;
shared HTTP, language normalization, PDF validation, pipeline, state, and
storage behavior must not be duplicated in type modules.

Shared code owns downloading, PDF validation, hashing, R2 keys, manifests,
checkpoints, retries, and common logging. Do not copy shared behavior into
individual source connectors.

Use names matching the existing implementation for scripts, tests, and
documentation:

```text
scripts/<action>_resumable_documents_<source>.py
tests/test_<source>_<area>.py
docs/<source>-<area>.md
.github/workflows/<action>-<document-type>.yml
```

Do not create a second connector for behavior already covered by `common.py` or
`archive.py`. Add a small source-specific function and reuse the shared
pipeline instead.

## Source-of-truth rules

- Treat each official government website as the source of truth for its own
  records and files.
- Use the public official interface or documented public endpoint actually
  used by that website.
- Do not use private internal hosts, guessed endpoints, stale URLs, or
  third-party snapshots as production sources.
- Keep source URLs and source metadata in every manifest.
- Do not mix records from different websites under one source identity.

## Preservation and correctness

- Preserve raw files unchanged.
- Validate that a downloaded file is the expected document type before saving.
- Calculate and record a SHA-256 checksum and byte size.
- Store an immutable raw object and its JSON manifest in R2.
- Use deterministic object keys containing source, document type, identity,
  language where applicable, and content hash.
- Make reruns idempotent: existing verified immutable objects must not be
  overwritten.
- Record progress after successful units of work so interrupted jobs resume
  safely and retry only incomplete work.

## Testing rules

- Never run tests or commands that erase databases, buckets, or stored source
  documents.
- Do not run a full production backfill as a development test.
- Prefer unit tests with saved response fixtures for parsers and normalizers.
- For live checks, use a small page/document limit and disable uploads when
  testing discovery or pagination.
- Before a production run, verify the current official response shape and the
  official download URL pattern.
- Test one source and document type at a time.
- Keep credentials in environment variables or deployment secrets; never
  commit them or print them in logs.

## R2 storage model

R2 is the durable preservation store and the source of truth for ingestion
outputs and resumable progress. The pipeline stores three kinds of objects:

```text
raw/<source>/<document-type>/<document-id>/<language>/<document-id>--sha256-<first-16-hash>.pdf
manifests/<source>/<document-type>/<source-id>/<source-id>--sha256-<first-16-hash>.json
state/<source>/<document-type>/backfills/<range>.json
```

The exact key builders are implemented in `object_keys.py`; use those helpers
instead of constructing keys in connectors or workflows.

### Raw documents

Each successfully downloaded original file is stored under `raw/`. Raw files
must be preserved byte-for-byte and must never be overwritten. The key
contains the source, document type, stable source identity, language when
available, and a SHA-256 content-hash prefix. Different content produces a
different immutable object key.

Before upload, the downloader must verify the HTTP result and expected file
format. For PDFs this includes checking the PDF signature (`%PDF`) and
recording the complete SHA-256 digest and byte size.

### Metadata manifests

Every stored raw document has a JSON manifest under `manifests/`. A manifest
records the normalized document identity and provenance, including source,
document type, source ID, document number where available, title, language,
publication date, official listing page, official download URL, R2 object key,
SHA-256 digest, byte size, and pipeline version.

Manifests are immutable evidence of what was saved. Do not silently rewrite an
existing manifest. If the source metadata changes or a file changes, preserve
the new version under its new content-hash key and retain the provenance that
led to it.

### Checkpoints and processing state

Backfill checkpoints are stored under `state/`. A checkpoint records the
source, document type, requested range, next official page or batch, status,
and update time. It advances only after the corresponding unit has completed
successfully. A failed or interrupted unit must remain retryable.

Checkpoint state is not proof that every document was saved. A page-level
checkpoint may only advance after all documents on that page have succeeded;
future per-document retry state must remain separate from page progress. Do not
mark a backfill complete merely because a workflow process exited normally.

R2 object existence is used for idempotency, but an object should be treated
as complete only when its raw file and manifest have both been successfully
stored and their recorded hash/size agree. Reruns should skip verified
immutable objects and retry incomplete or failed work.

### R2 configuration

The storage adapter receives these deployment secrets through environment
variables:

```text
R2_ENDPOINT_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
```

Never place credentials in source files, manifests, logs, fixtures, workflow
arguments, or commits. Do not delete, bulk-replace, or reset R2 objects or
state during development. Any cleanup requires an explicit, narrowly scoped
request and a prior inventory of the exact objects affected.

### Preservation flow

All source connectors should follow this order:

```text
official discovery
  → normalized document record
  → download and validate
  → calculate SHA-256 and byte size
  → write immutable raw object
  → write immutable metadata manifest
  → update durable checkpoint/state
```

Discovery metadata must come from the official source. Storage code must not
infer missing source facts, repair URLs silently, or replace official
provenance with values from another source.

## Change workflow

Before changing ingestion code:

1. inspect the current connector, workflow, tests, and working-tree changes;
2. confirm the behavior against the official source when the change concerns
   discovery or downloading;
3. make the smallest source-specific change possible;
4. add or update non-destructive tests;
5. run the relevant tests and review the diff;
6. clearly report what was verified and what was not verified.

Do not silently broaden a task from one source or document type to another.
