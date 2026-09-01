"""Environment-based project configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    source_url: str = os.getenv("HAJJ_SOURCE_URL", "")
    timeout_seconds: int = int(os.getenv("HAJJ_REQUEST_TIMEOUT_SECONDS", "30"))
    user_agent: str = os.getenv(
        "HAJJ_USER_AGENT", "BD-Hajj-2027-Research/0.1"
    )
    timezone: str = os.getenv("HAJJ_TIMEZONE", "Asia/Dhaka")
    interval_minutes: int = int(os.getenv("HAJJ_SCRAPE_INTERVAL_MINUTES", "60"))
    raw_data_dir: Path = Path(os.getenv("HAJJ_RAW_DATA_DIR", "data/raw"))
    log_level: str = os.getenv("HAJJ_LOG_LEVEL", "INFO").upper()

    def validate(self) -> None:
        if not self.source_url or "example.gov.bd" in self.source_url:
            raise ValueError("Set HAJJ_SOURCE_URL in .env to the official source URL")
        if self.interval_minutes < 60:
            raise ValueError("Scrape interval must be at least 60 minutes")
