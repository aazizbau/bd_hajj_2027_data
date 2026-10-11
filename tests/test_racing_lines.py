from pathlib import Path

import pandas as pd
import pytest

from hajj_racing_lines import DEFAULT_CSV, load_data


def test_defaults_to_project_processed_csv() -> None:
    assert DEFAULT_CSV == Path("data/processed/hajj_2027_registration.csv")


def test_loads_project_csv_schema(tmp_path: Path) -> None:
    csv_path = tmp_path / "hajj_2027_registration.csv"
    csv_path.write_text(
        "timestamp_utc,registered_pligrim_govt,registered_pligrim_nongovt,"
        "pre_registered_pilgrim_govt,pre_registered_pilgrim_nongovt\n"
        "2026-09-01T00:00:00Z,10,90,20,180\n"
        "2026-09-02T00:00:00Z,15,105,22,178\n",
        encoding="utf-8",
    )

    frame = load_data(csv_path)

    assert len(frame) == 2
    assert str(frame.index.tz) == "Asia/Dhaka"
    assert frame["registered_total"].iloc[-1] == 120
    assert frame["pre_registered_total"].iloc[-1] == 200
    assert pd.isna(frame["pace_total"].iloc[0])
    assert frame["pace_total"].iloc[-1] == 20


def test_accepts_corrected_pilgrim_column_aliases(tmp_path: Path) -> None:
    csv_path = tmp_path / "corrected.csv"
    csv_path.write_text(
        "timestamp_utc,registered_pilgrim_govt,registered_pilgrim_nongovt,"
        "pre_registered_pilgrim_govt,pre_registered_pilgrim_nongovt\n"
        "2026-09-01T00:00:00Z,10,90,20,180\n",
        encoding="utf-8",
    )

    frame = load_data(csv_path)

    assert frame["registered_total"].iloc[0] == 100
    assert frame["registered_gov_to_non_pct"].iloc[0] == pytest.approx(
        100 * 10 / 90
    )


def test_rejects_csv_without_valid_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(
        "timestamp_utc,registered_pligrim_govt,registered_pligrim_nongovt,"
        "pre_registered_pilgrim_govt,pre_registered_pilgrim_nongovt\n"
        "not-a-date,1,2,3,4\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no valid timestamped rows"):
        load_data(csv_path)
