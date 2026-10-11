# Bangladesh Hajj 2027 Data

A Python project for collecting public Hajj 2027 statistics from an authorized
Bangladesh government website once per hour, preserving timestamped raw
snapshots, and analysing changes over time.

## Important data rules

- Confirm that automated access is allowed by the site's terms and `robots.txt`.
- Prefer an official API or downloadable dataset when one exists.
- Collect only fields needed for the analysis. Pilgrim records may contain
  sensitive personal data; do not commit, publish, or unnecessarily retain it.
- Keep the one-hour interval (or a slower rate) and identify the collector with
  an honest user agent and contact address.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

The source defaults to `https://ehaj.hajj.gov.bd/`. Edit `.env` to set your
contact address in the user agent or override another setting.

## Run

Collect one snapshot:

```bash
python -m src.hajj_data.cli scrape-once
```

Run the collector continuously every hour:

```bash
python -m src.hajj_data.cli run-scheduler
```

Each successful collection appends a UTC-timestamped row to
`data/processed/hajj_2027_registration.csv`. Bengali digits are stored as plain
integers. A failed request or missing page element does not append an incomplete
row.

The homepage fills its counters dynamically. The collector first loads the
homepage to establish a session and obtain its CSRF token, then calls the same
`getCountData` endpoint used by the site's JavaScript.

For a server, prefer invoking `scrape-once` through cron or a systemd timer so
the schedule survives restarts. The built-in scheduler is convenient for local
development.

## Registration race animation

Render an animated dashboard from the processed registration history:

```bash
python hajj_racing_lines.py
```

The script reads `data/processed/hajj_2027_registration.csv` and writes
`data/exports/hajj_registration_race.gif` by default. To make a smaller preview:

```bash
python hajj_racing_lines.py \
  --out data/exports/hajj_registration_preview.gif \
  --step 18 --fps 10
```

Use `--csv` to select another compatible CSV, or `--max-frames` for a quick
rendering check. MP4 output is also supported when FFmpeg is installed.

## Layout

```text
src/hajj_data/       collection and processing code
tests/               automated tests
data/raw/            immutable timestamped source responses (ignored by Git)
data/processed/      cleaned datasets (ignored by Git)
data/exports/        shareable, reviewed outputs (ignored by Git)
notebooks/           exploratory analysis
logs/                runtime logs (ignored by Git)
```

The collector also preserves every complete source response under `data/raw/`
for auditability.
