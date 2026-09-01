"""Command-line entry points for collection."""

from __future__ import annotations

import argparse
import logging
import time

from .collector import collect_once
from .config import Settings


def _collect_and_log(settings: Settings) -> None:
    path = collect_once(settings)
    logging.info("Saved snapshot to %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bangladesh Hajj data collector")
    parser.add_argument("command", choices=("scrape-once", "run-scheduler"))
    args = parser.parse_args()
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "scrape-once":
        _collect_and_log(settings)
        return

    settings.validate()
    logging.info("Collector started; interval=%s minutes", settings.interval_minutes)
    while True:
        try:
            _collect_and_log(settings)
        except Exception:
            logging.exception("Collection failed; retrying at the next interval")
        time.sleep(settings.interval_minutes * 60)


if __name__ == "__main__":
    main()
