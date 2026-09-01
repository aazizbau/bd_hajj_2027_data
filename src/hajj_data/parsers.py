"""Source-specific parsing belongs here once the official format is known."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def parse_snapshot(path: Path) -> pd.DataFrame:
    """Parse a raw snapshot without modifying it.

    Implement and test the exact JSON fields or HTML selectors after the
    official source has been identified.
    """
    raise NotImplementedError(f"No parser has been configured for {path}")
