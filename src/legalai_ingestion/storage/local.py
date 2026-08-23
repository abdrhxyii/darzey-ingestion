from __future__ import annotations

from pathlib import Path


class LocalObjectStore:
    """Non-production store used for deterministic, non-destructive tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None:
        del content_type, metadata
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_bytes()
            if existing != body:
                raise FileExistsError(f"Refusing to overwrite different object: {key}")
            return
        target.write_bytes(body)

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def get(self, key: str) -> bytes | None:
        target = self.root / key
        return target.read_bytes() if target.exists() else None

    def replace(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None:
        """Write mutable operational state used by resumable backfills."""

        del content_type, metadata
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
