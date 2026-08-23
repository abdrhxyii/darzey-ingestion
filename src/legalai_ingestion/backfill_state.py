"""Durable, small state records for resumable source-preservation backfills."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol


class StateStore(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def replace(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None: ...


def extra_gazette_checkpoint_key(from_year: int, to_year: int) -> str:
    return f"state/documents.gov.lk/extra-gazette/backfills/{from_year}-{to_year}.json"


@dataclass(frozen=True)
class BackfillCheckpoint:
    """The next official listing page to process for one fixed year range."""

    source: str
    document_type: str
    from_year: int
    to_year: int
    next_page: int
    status: str
    updated_at: str

    @classmethod
    def new(cls, *, from_year: int, to_year: int) -> "BackfillCheckpoint":
        return cls(
            source="documents.gov.lk",
            document_type="extra-gazette",
            from_year=from_year,
            to_year=to_year,
            next_page=1,
            status="in_progress",
            updated_at=_utc_now(),
        )

    @classmethod
    def from_bytes(cls, body: bytes) -> "BackfillCheckpoint":
        payload = json.loads(body.decode("utf-8"))
        return cls(**payload)

    def with_progress(self, *, next_page: int, completed: bool = False) -> "BackfillCheckpoint":
        return BackfillCheckpoint(
            source=self.source,
            document_type=self.document_type,
            from_year=self.from_year,
            to_year=self.to_year,
            next_page=next_page,
            status="completed" if completed else "in_progress",
            updated_at=_utc_now(),
        )

    def to_bytes(self) -> bytes:
        return (json.dumps(asdict(self), indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_extra_gazette_checkpoint(store: StateStore, *, from_year: int, to_year: int) -> BackfillCheckpoint:
    body = store.get(extra_gazette_checkpoint_key(from_year, to_year))
    if body is None:
        return BackfillCheckpoint.new(from_year=from_year, to_year=to_year)
    checkpoint = BackfillCheckpoint.from_bytes(body)
    if (
        checkpoint.source != "documents.gov.lk"
        or checkpoint.document_type != "extra-gazette"
        or checkpoint.from_year != from_year
        or checkpoint.to_year != to_year
    ):
        raise ValueError("Extra Gazette backfill checkpoint does not match the requested year range")
    return checkpoint


def save_extra_gazette_checkpoint(store: StateStore, checkpoint: BackfillCheckpoint) -> None:
    store.replace(
        extra_gazette_checkpoint_key(checkpoint.from_year, checkpoint.to_year),
        checkpoint.to_bytes(),
        content_type="application/json",
        metadata={"kind": "backfill-checkpoint"},
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
