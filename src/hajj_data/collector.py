"""HTTP collection and immutable raw snapshot storage."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def fetch(settings: Settings) -> requests.Response:
    response = requests.get(
        settings.source_url,
        headers={"User-Agent": settings.user_agent, "Accept": "application/json,text/html"},
        timeout=settings.timeout_seconds,
    )
    response.raise_for_status()
    return response


def save_snapshot(response: requests.Response, raw_dir: Path) -> Path:
    collected_at = datetime.now(timezone.utc)
    day_dir = raw_dir / collected_at.strftime("%Y/%m/%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = collected_at.strftime("%Y%m%dT%H%M%SZ")
    content_type = response.headers.get("content-type", "").lower()
    extension = ".json" if "json" in content_type else ".html"
    data_path = day_dir / f"pilgrims_{stamp}{extension}"
    data_path.write_bytes(response.content)

    metadata = {
        "collected_at_utc": collected_at.isoformat(),
        "source_url": response.url,
        "status_code": response.status_code,
        "content_type": content_type,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "data_file": data_path.name,
    }
    data_path.with_suffix(data_path.suffix + ".metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return data_path


def collect_once(settings: Settings) -> Path:
    settings.validate()
    return save_snapshot(fetch(settings), settings.raw_data_dir)
