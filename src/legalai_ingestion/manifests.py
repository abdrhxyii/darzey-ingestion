from __future__ import annotations

import json

from .models import StoredDocument


def manifest_bytes(document: StoredDocument) -> bytes:
    """Serialize a deterministic UTF-8 audit manifest."""

    return (
        json.dumps(document.to_manifest(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
