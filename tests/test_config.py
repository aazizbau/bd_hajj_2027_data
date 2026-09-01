from dataclasses import replace

import pytest

from src.hajj_data.config import Settings


def test_rejects_invalid_url() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        replace(Settings(), source_url="not-a-url").validate()


def test_rejects_overly_frequent_collection() -> None:
    settings = replace(
        Settings(), source_url="https://hajj.gov.bd/data", interval_minutes=30
    )
    with pytest.raises(ValueError, match="at least 60"):
        settings.validate()
