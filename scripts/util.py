"""Shared helpers for the data pipeline (JSON IO, series maths, history files)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"

LENS_TITLES = {
    1: ("Recession risk", "Leading and coincident indicators of an economic downturn."),
    2: ("Market-peak froth", "Public-data gauges of euphoria and complacency."),
    3: ("Price trend", "Confirmation that the market is actually rolling over."),
}

# Canonical row order per lens. Extended as later phases add indicators.
CANONICAL_ORDER = {
    1: [
        "yield_curve_10y3m",
        "sahm_rule",
        "hy_credit_spreads",
        "pmi_manufacturing_proxy",
        "leading_indicators",
        "labour_market",
        "shiller_cape",
    ],
    2: [],
    3: ["sma_trend_sp500"],
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_observation(dates: list[str], values: list[float | None]) -> tuple[str, float]:
    """Return the most recent non-missing observation as (iso_date, value)."""
    for d, v in zip(reversed(dates), reversed(values)):
        if v is not None:
            return d, v
    raise ValueError("Series contains no non-missing observations")


def clean_series(dates: list[str], values: list[float | None]) -> tuple[list[str], list[float]]:
    """Drop missing observations, keeping dates and values aligned."""
    pairs = [(d, v) for d, v in zip(dates, values) if v is not None]
    return [d for d, _ in pairs], [v for _, v in pairs]


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in 0–100) without numpy."""
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (q / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def write_fred_history(series_id: str, name: str, unit: str, source_url: str,
                       dates: list[str], values: list[float]) -> Path:
    """Write a full-series history file for a FRED series."""
    path = HISTORY_DIR / f"{series_id.lower()}.json"
    dump_json(path, {
        "series_id": series_id,
        "name": name,
        "unit": unit,
        "source_url": source_url,
        "updated_at": utc_now_iso(),
        "dates": dates,
        "values": values,
    })
    return path


def append_scrape_history(filename: str, meta: dict, as_of: str, value: float) -> Path:
    """Append one (as_of, value) point to an accumulating scrape-history file.

    Scraped sources (PMI, LEI, CAPE) have no freely fetchable history, so the
    pipeline accumulates its own: one point per reference period, first write
    wins for a given as_of.
    """
    path = HISTORY_DIR / filename
    existing = load_json(path) or {**meta, "points": []}
    if not any(p["as_of"] == as_of for p in existing["points"]):
        existing["points"].append({"as_of": as_of, "value": value, "recorded_at": utc_now_iso()})
        existing["points"].sort(key=lambda p: p["as_of"])
    existing.update(meta)
    existing["updated_at"] = utc_now_iso()
    dump_json(path, existing)
    return path
