"""HTTP collection and immutable raw snapshot storage."""

from __future__ import annotations

import hashlib
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings
from .parsers import RegistrationStats, parse_registration_payload


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def fetch(settings: Settings) -> requests.Response:
    response = requests.get(
        settings.source_url,
        headers={"User-Agent": settings.user_agent, "Accept": "application/json,text/html"},
        timeout=settings.timeout_seconds,
    )
    response.raise_for_status()
    return response


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def fetch_registration_data(
    settings: Settings,
) -> tuple[requests.Response, requests.Response]:
    """Load the homepage session, then call the endpoint used by its JavaScript."""
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "application/json,text/html",
    }
    with requests.Session() as session:
        page_response = session.get(
            settings.source_url, headers=headers, timeout=settings.timeout_seconds
        )
        page_response.raise_for_status()
        soup = BeautifulSoup(page_response.text, "html.parser")
        count_script = next(
            (
                script.get_text()
                for script in soup.find_all("script")
                if "getCountData" in script.get_text()
            ),
            "",
        )
        token_match = re.search(
            r"url:\s*['\"]getCountData['\"].*?"
            r"['\"]X-CSRF-TOKEN['\"]\s*:\s*['\"]([^'\"]+)",
            count_script,
            flags=re.DOTALL,
        )
        if token_match is None:
            raise ValueError("getCountData CSRF token was not found on the homepage")

        api_response = session.post(
            urljoin(page_response.url, "getCountData"),
            headers={
                **headers,
                "X-CSRF-TOKEN": token_match.group(1),
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=settings.timeout_seconds,
        )
        api_response.raise_for_status()
        return page_response, api_response


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


def append_csv(
    stats: RegistrationStats, output_path: Path, collected_at: datetime
) -> None:
    """Append one complete observation, writing the header only once."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": collected_at.isoformat().replace("+00:00", "Z"),
        "registered_pligrim_govt": stats.registered_pligrim_govt,
        "registered_pligrim_nongovt": stats.registered_pligrim_nongovt,
        "pre_registered_pilgrim_govt": stats.pre_registered_pilgrim_govt,
        "pre_registered_pilgrim_nongovt": stats.pre_registered_pilgrim_nongovt,
    }
    fieldnames = list(row)
    with output_path.open("a+", encoding="utf-8", newline="") as csv_file:
        csv_file.seek(0, os.SEEK_END)
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if csv_file.tell() == 0:
            writer.writeheader()
        writer.writerow(row)
        csv_file.flush()
        os.fsync(csv_file.fileno())


def collect_once(settings: Settings) -> Path:
    settings.validate()
    page_response, api_response = fetch_registration_data(settings)
    save_snapshot(page_response, settings.raw_data_dir)
    save_snapshot(api_response, settings.raw_data_dir)
    stats = parse_registration_payload(api_response.json())
    append_csv(stats, settings.output_csv, datetime.now(timezone.utc))
    return settings.output_csv
