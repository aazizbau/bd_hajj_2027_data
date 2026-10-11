#!/usr/bin/env python3
"""Create an animated dashboard from the processed Hajj registration data.

By default, the script reads ``data/processed/hajj_2027_registration.csv`` and
writes ``data/exports/hajj_registration_race.gif``. Frames always come from
actual snapshot rows; no registration values are fabricated.

Examples:
    python hajj_racing_lines.py
    python hajj_racing_lines.py --out data/exports/preview.gif --step 18 --fps 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter  # noqa: E402


DEFAULT_CSV = Path("data/processed/hajj_2027_registration.csv")
DEFAULT_OUTPUT = Path("data/exports/hajj_registration_race.gif")
TIMEZONE = "Asia/Dhaka"

COLORS = {
    "reg_non": "#38D9FF",
    "reg_gov": "#F6C55D",
    "pre_non": "#A78BFA",
    "pre_gov": "#FE8A73",
    "govt_ratio": "#FFCE73",
    "pre_ratio": "#EEA0E7",
    "pace_non": "#38D9FF",
    "pace_gov": "#F6C55D",
    "pace_all": "#99F6C7",
}
BG = "#081425"
PANEL = "#0D2135"
WHITE = "#EFF6FF"
MUTED = "#A3B7CA"

COLUMN_ALIASES = {
    "registered_pligrim_nongovt": (
        "registered_pligrim_nongovt",
        "registered_pilgrim_nongovt",
    ),
    "registered_pligrim_govt": (
        "registered_pligrim_govt",
        "registered_pilgrim_govt",
    ),
    "pre_registered_pilgrim_nongovt": (
        "pre_registered_pilgrim_nongovt",
        "pre_registered_pligrim_nongovt",
    ),
    "pre_registered_pilgrim_govt": (
        "pre_registered_pilgrim_govt",
        "pre_registered_pligrim_govt",
    ),
}


def load_data(path: str | Path) -> pd.DataFrame:
    """Load, validate, and derive chart series from a processed snapshot CSV."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Input CSV does not exist: {path}")

    frame = pd.read_csv(path)
    if "timestamp_utc" not in frame.columns:
        raise ValueError("Missing required column: timestamp_utc")

    mapping: dict[str, str] = {}
    for canonical, candidates in COLUMN_ALIASES.items():
        match = next((column for column in candidates if column in frame.columns), None)
        if match is None:
            raise ValueError(
                f"Missing column for {canonical}; available columns: "
                f"{list(frame.columns)}"
            )
        mapping[match] = canonical

    frame = frame.rename(columns=mapping)
    frame["time"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="coerce")
    frame = (
        frame.dropna(subset=["time"])
        .sort_values("time")
        .drop_duplicates("time", keep="last")
    )
    if frame.empty:
        raise ValueError("Input CSV contains no valid timestamped rows")

    count_columns = list(COLUMN_ALIASES)
    for column in count_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[count_columns].isna().any().any():
        raise ValueError("Some input counts are missing or not numeric")
    if (frame[count_columns] < 0).any().any():
        raise ValueError("Input counts cannot be negative")

    frame = frame.set_index("time").tz_convert(TIMEZONE)
    frame["registered_total"] = (
        frame["registered_pligrim_govt"]
        + frame["registered_pligrim_nongovt"]
    )
    frame["pre_registered_total"] = (
        frame["pre_registered_pilgrim_govt"]
        + frame["pre_registered_pilgrim_nongovt"]
    )

    # These are government/non-government ratios, not government shares of total.
    frame["registered_gov_to_non_pct"] = (
        100
        * frame["registered_pligrim_govt"]
        / frame["registered_pligrim_nongovt"].replace(0, np.nan)
    )
    frame["pre_gov_to_non_pct"] = (
        100
        * frame["pre_registered_pilgrim_govt"]
        / frame["pre_registered_pilgrim_nongovt"].replace(0, np.nan)
    )

    # Interpolate the cumulative value at exactly 24 hours before each snapshot.
    # This handles the dataset's irregular collection intervals more accurately
    # than treating 24 rows as 24 hours.
    time_ns = frame.index.tz_convert("UTC").asi8.astype(np.float64)
    earlier = time_ns - 24 * 60 * 60 * 1e9
    pace_columns = (
        ("non", "registered_pligrim_nongovt"),
        ("gov", "registered_pligrim_govt"),
        ("total", "registered_total"),
    )
    for suffix, column in pace_columns:
        values = frame[column].to_numpy(dtype=float)
        previous = np.interp(earlier, time_ns, values, left=np.nan, right=np.nan)
        pace = values - previous
        pace[earlier < time_ns[0]] = np.nan
        frame[f"pace_{suffix}"] = pace

    return frame


def style_axis(axis: plt.Axes, title: str, ylabel: str) -> None:
    axis.set_facecolor(PANEL)
    axis.set_title(title, color=WHITE, loc="left", fontsize=12, weight="bold", pad=12)
    axis.set_ylabel(ylabel, color=MUTED, fontsize=9)
    axis.tick_params(colors=MUTED, labelsize=8)
    axis.grid(color="#50657C", alpha=0.23, linewidth=0.7)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %d", tz=TIMEZONE))
    axis.margins(x=0.025)


def format_value(value: float, kind: str) -> str:
    if not np.isfinite(value):
        return "n/a"
    if kind == "ratio":
        return f"{value:.1f}%"
    return f"{value:,.0f}"


def create_animation(
    frame: pd.DataFrame,
    output: str | Path,
    step: int = 6,
    fps: int = 15,
    dpi: int = 125,
    max_frames: int | None = None,
) -> tuple[Path, int]:
    """Render the prepared data to an MP4 or animated GIF."""
    if frame.empty:
        raise ValueError("Cannot animate an empty dataset")
    if step < 1 or fps < 1 or dpi < 1:
        raise ValueError("step, fps, and dpi must be positive integers")
    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be positive when provided")

    output = Path(output)
    suffix = output.suffix.lower()
    if suffix not in {".gif", ".mp4"}:
        raise ValueError("Output filename must end in .mp4 or .gif")
    if suffix == ".mp4" and not FFMpegWriter.isAvailable():
        raise RuntimeError(
            "MP4 output requires ffmpeg. Install ffmpeg or select a .gif output."
        )

    figure, axes = plt.subplots(2, 2, figsize=(16, 9), facecolor=BG)
    plt.subplots_adjust(
        top=0.86, bottom=0.10, left=0.07, right=0.88, hspace=0.38, wspace=0.23
    )
    axes = axes.ravel()
    style_axis(axes[0], "REGISTERED • COMPLETED", "Pilgrims")
    style_axis(axes[1], "PRE-REGISTERED • REPORTED REMAINING", "Pilgrims")
    style_axis(axes[2], "GOV / NON-GOV RATIO", "Gov ÷ Non-gov (%)")
    style_axis(
        axes[3],
        "REGISTRATION VELOCITY • TRAILING 24 HOURS",
        "New registrations / 24 h",
    )

    groups = [
        [
            (
                "Non-gov registered",
                "registered_pligrim_nongovt",
                COLORS["reg_non"],
                "count",
            ),
            (
                "Gov registered",
                "registered_pligrim_govt",
                COLORS["reg_gov"],
                "count",
            ),
        ],
        [
            (
                "Non-gov pre-reg",
                "pre_registered_pilgrim_nongovt",
                COLORS["pre_non"],
                "count",
            ),
            (
                "Gov pre-reg",
                "pre_registered_pilgrim_govt",
                COLORS["pre_gov"],
                "count",
            ),
        ],
        [
            (
                "Registered ratio",
                "registered_gov_to_non_pct",
                COLORS["govt_ratio"],
                "ratio",
            ),
            (
                "Pre-registered ratio",
                "pre_gov_to_non_pct",
                COLORS["pre_ratio"],
                "ratio",
            ),
        ],
        [
            ("Non-gov pace", "pace_non", COLORS["pace_non"], "count"),
            ("Gov pace", "pace_gov", COLORS["pace_gov"], "count"),
            ("Combined pace", "pace_total", COLORS["pace_all"], "count"),
        ],
    ]

    times = mdates.date2num(frame.index.to_pydatetime())
    time_span = times[-1] - times[0]
    right_padding = time_span * 0.20 if time_span else 1 / 24
    artists = []
    for axis, group in zip(axes, groups, strict=True):
        for label, column, color, kind in group:
            (line,) = axis.plot(
                [], [], lw=2.8, color=color, label=label, solid_capstyle="round"
            )
            (point,) = axis.plot(
                [],
                [],
                marker="o",
                markersize=7,
                color=color,
                markeredgecolor=WHITE,
                markeredgewidth=0.65,
            )
            annotation = axis.annotate(
                "",
                xy=(0, 0),
                xytext=(11, 0),
                textcoords="offset points",
                color=color,
                fontsize=10,
                weight="bold",
                va="center",
                bbox={
                    "boxstyle": "round,pad=.25",
                    "fc": BG,
                    "ec": color,
                    "alpha": 0.95,
                    "lw": 0.8,
                },
                path_effects=[patheffects.withStroke(linewidth=1, foreground=BG)],
            )
            artists.append(
                (axis, line, point, annotation, label, column, color, kind)
            )
        axis.legend(
            loc="upper left",
            fontsize=8,
            facecolor=PANEL,
            edgecolor="#3A5670",
            labelcolor=WHITE,
        )
        axis.set_xlim(times[0], times[-1] + right_padding)

    figure.text(
        0.07,
        0.955,
        "HAJJ 2027  /  BANGLADESH REGISTRATION RACE",
        color=WHITE,
        fontsize=21,
        fontweight="bold",
    )
    clock = figure.text(
        0.07, 0.905, "", color="#F6C55D", fontsize=13, fontweight="bold"
    )
    figure.text(
        0.88,
        0.045,
        "Source: collected snapshots  •  Bangladesh time (UTC+06)",
        color=MUTED,
        ha="right",
        fontsize=9,
    )
    figure.text(
        0.07,
        0.045,
        "Pre-registration values are reported counts, not independently verified conversion flows.",
        color=MUTED,
        fontsize=8,
    )

    positions = list(range(0, len(frame), step))
    if positions[-1] != len(frame) - 1:
        positions.append(len(frame) - 1)
    if max_frames is not None:
        positions = positions[:max_frames]

    values = {
        column: frame[column].to_numpy(dtype=float)
        for group in groups
        for _, column, _, _ in group
    }

    def update(animation_index: int):
        row_index = positions[animation_index]
        clock.set_text(
            frame.index[row_index].strftime("%d %B %Y  •  %I:%M %p BST")
        )
        for _, line, point, annotation, label, column, _, kind in artists:
            y_values = values[column][: row_index + 1]
            x_values = times[: row_index + 1]
            mask = np.isfinite(y_values)
            line.set_data(x_values[mask], y_values[mask])
            if mask.any():
                final_index = np.flatnonzero(mask)[-1]
                point.set_data(
                    [x_values[final_index]], [y_values[final_index]]
                )
                annotation.xy = (
                    x_values[final_index],
                    y_values[final_index],
                )
                annotation.set_text(
                    f"{label}: {format_value(y_values[final_index], kind)}"
                )
                annotation.set_visible(True)
            else:
                point.set_data([], [])
                annotation.set_visible(False)

        for axis, group in zip(axes, groups, strict=True):
            visible_parts = [
                values[column][: row_index + 1][
                    np.isfinite(values[column][: row_index + 1])
                ]
                for _, column, _, _ in group
            ]
            visible = np.concatenate(visible_parts)
            if len(visible):
                low = min(0.0, float(visible.min()))
                high = max(float(visible.max()), 1.0)
                pad = max((high - low) * 0.13, 0.1 if axis is axes[2] else 1)
                axis.set_ylim(low - pad * 0.25, high + pad)

        return [clock] + [
            item
            for _, line, point, annotation, *_ in artists
            for item in (line, point, annotation)
        ]

    animation = FuncAnimation(
        figure,
        update,
        frames=len(positions),
        interval=1000 / fps,
        blit=False,
        repeat=False,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = (
        PillowWriter(fps=fps)
        if suffix == ".gif"
        else FFMpegWriter(
            fps=fps, bitrate=3800, extra_args=["-pix_fmt", "yuv420p"]
        )
    )
    try:
        animation.save(str(output), writer=writer, dpi=dpi)
    finally:
        plt.close(figure)

    return output, len(positions)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Input CSV path (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output MP4 or GIF (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--step",
        type=positive_int,
        default=6,
        help="Use every Nth snapshot (default: 6)",
    )
    parser.add_argument("--fps", type=positive_int, default=15)
    parser.add_argument("--dpi", type=positive_int, default=125)
    parser.add_argument(
        "--max-frames",
        type=positive_int,
        default=None,
        help="Optional frame limit for quick preview renders",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    frame = load_data(args.csv)
    output, frame_count = create_animation(
        frame,
        args.out,
        step=args.step,
        fps=args.fps,
        dpi=args.dpi,
        max_frames=args.max_frames,
    )
    print(f"Created {output} ({frame_count} frames; {len(frame)} source snapshots).")
    print(f"Final total registered: {frame.registered_total.iloc[-1]:,.0f}")


if __name__ == "__main__":
    main()
