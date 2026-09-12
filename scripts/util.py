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
    2: [
        "consumer_confidence_proxy",
        "retail_euphoria_aaii",
        "growth_expectation_pe",
        "deal_ipo_froth",
        "rule_of_20",
        "value_vs_growth",
        "credit_complacency_nfci",
        "sloos_tightening",
    ],
    3: ["sma_trend_sp500"],
}

# The Lens 2 composite's membership, named rather than inferred from whichever
# rows happen to carry in_composite on the day.
#
# WHY THIS EXISTS. The alarm is a SHARE, so its bite depends on how many gauges
# are in the set, and a share threshold on a small denominator is lumpy: 62.5%
# is exactly 5 of 8 at eight gauges but 5 of 7 at seven, because 4 of 7 is 57.1%
# and sits below the line. When NAAIM parked on 2026-08-25 the count fell from
# eight to seven and the alarm tightened with it, unannounced and undecided; the
# row was removed outright on 2026-09-12 and the recalibration
# (reviews/2026-09-12_lens2-alarm-recalibration.md) endorsed 62.5% on the seven,
# but the silence is the defect this list guards against.
#
# tests/test_composite_alarm.py fails if a member is added or deleted without
# this list being updated, which makes the next change a decision rather than an
# accident. A member that PARKS is not a change to the set and does not fail the
# guard — parking is temporary and already reported by the weekly digest, which
# names the effective bite while it lasts.
COMPOSITE_SET = (
    "consumer_confidence_proxy",
    "retail_euphoria_aaii",
    "growth_expectation_pe",
    "deal_ipo_froth",
    "rule_of_20",
    "value_vs_growth",
    "credit_complacency_nfci",
)


def minimum_triggered(alarm_share_pct: float, gauge_count: int) -> int:
    """Gauges that must trigger to arm the alarm, at this set size.

    Mirrors lens2.summarise exactly, INCLUDING its rounding of the share to one
    decimal before the comparison: re-deriving it from raw floats would disagree
    with the live code at a boundary, and a guard that computes the rule its own
    way is not a guard.
    """
    if gauge_count <= 0:
        raise ValueError("gauge_count must be positive")
    for triggered in range(gauge_count + 1):
        if round(100.0 * triggered / gauge_count, 1) >= alarm_share_pct:
            return triggered
    return gauge_count + 1          # unreachable at any alarm at or below 100


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
