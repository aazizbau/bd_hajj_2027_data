import hashlib
import json

import requests

from src.hajj_data.collector import save_snapshot


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
