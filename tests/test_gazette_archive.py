from legalai_ingestion.connectors.documents_gov_lk_gazettes_archive import (
    _dates_from_server_action,
)


def test_gazette_dates_from_server_action():
    response = '0:{"a":"$@1"}\n1:{"dates":["2026-08-21T00:00:00.000Z"],"total":1053}'
    assert _dates_from_server_action(response) == ["2026-08-21"]


def test_gazette_dates_from_compact_server_action():
    response = '0:{"a":"$@1"} 1:{"dates":["2026-08-14T00:00:00.000Z"],"total":1053}'
    assert _dates_from_server_action(response) == ["2026-08-14"]
