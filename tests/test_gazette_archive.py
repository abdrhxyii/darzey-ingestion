from __future__ import annotations

import json
from urllib.error import HTTPError

from legalai_ingestion.connectors import documents_gov_lk_gazettes as gazettes


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_decode_gazette_date_page():
    dates, total = gazettes._decode_gazette_dates_response(
        json.dumps({"dates": ["2026-08-21T00:00:00.000Z"], "total": 1053}).encode()
    )
    assert dates == ["2026-08-21"]
    assert total == 1053


def test_fetch_gazette_date_page_retries_transient_failure(monkeypatch):
    responses = [HTTPError("https://example.test", 503, "recovering", {}, None), _Response(b'{"dates": [], "total": 0}')]

    def fake_urlopen(_request, timeout):
        assert timeout == 60
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(gazettes, "urlopen", fake_urlopen)
    monkeypatch.setattr(gazettes.time, "sleep", lambda _seconds: None)
    assert gazettes.fetch_gazette_date_page(1, attempts=2, retry_delay_seconds=0) == ([], 0)
