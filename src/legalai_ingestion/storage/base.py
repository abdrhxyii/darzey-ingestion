from __future__ import annotations

from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None:
        ...

    def exists(self, key: str) -> bool:
        ...

    def get(self, key: str) -> bytes | None:
        ...

    def replace(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None:
        ...
