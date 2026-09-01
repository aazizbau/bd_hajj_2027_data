import hashlib
import json
from datetime import datetime, timezone

import requests

from src.hajj_data.collector import append_csv, save_snapshot
from src.hajj_data.parsers import RegistrationStats


def test_save_snapshot_writes_data_and_metadata(tmp_path) -> None:
    response = requests.Response()
    response.status_code = 200
    response.url = "https://hajj.gov.bd/data"
    response.headers["content-type"] = "application/json"
    response._content = b'{"count": 42}'

    path = save_snapshot(response, tmp_path)

    assert path.read_bytes() == response.content
    metadata = json.loads(path.with_suffix(".json.metadata.json").read_text())
    assert metadata["sha256"] == hashlib.sha256(response.content).hexdigest()
    assert metadata["source_url"] == response.url


def test_append_csv_adds_one_header_and_multiple_rows(tmp_path) -> None:
    path = tmp_path / "output.csv"
    stats = RegistrationStats(607, 884, 3602, 61165)
    timestamp = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

    append_csv(stats, path, timestamp)
    append_csv(stats, path, timestamp)

    lines = path.read_text().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("timestamp_utc,registered_pligrim_govt")
    assert lines[1].startswith("2026-09-01T12:00:00Z,607,884,3602,61165")
