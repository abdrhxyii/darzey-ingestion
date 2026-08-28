# Agent Instructions

## Project purpose

This repository preserves original legal documents published by government
websites. The ingestion system stores the raw source files and their metadata
manifests in R2. Text extraction, OCR, chunking, embeddings, search, and RAG
are separate later stages.

The system must support multiple government websites and multiple document
types under each website.

## Repository organization

The repository currently uses a flat connector naming convention. Keep this
structure unless a deliberate migration is requested:

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
document type's URLs, discovery method, pagination, response parsing, metadata
mapping, and official file URL construction. Shared behavior remains in the
common connector helpers, pipeline, state, and storage modules.

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

Do not create a second connector for behavior already covered by an existing
`documents_gov_lk.py` helper or archive module. Add a small source-specific
function and reuse the shared pipeline instead.

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
