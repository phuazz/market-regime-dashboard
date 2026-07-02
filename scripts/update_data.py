"""Update data/ JSON files from sourced public data.

Usage:
    python scripts/update_data.py [--group daily|monthly|quarterly|all]

Phase 1 wires a single indicator (yield curve, FRED T10Y3M) end to end.
Later phases extend the registry at the bottom of this module. Every
indicator carries its own source_url, secondary_source_url, and as_of date
(SPEC.md section 9), and every series ID is verified against two independent
sources before first use (VERIFICATION.md).

Date handling: Python datetime months are 1-indexed (January = 1). All month
arithmetic goes through dateutil.relativedelta; day offsets go through
datetime.timedelta. Nothing is computed by hand.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from dateutil.relativedelta import relativedelta

from sources.fred import fetch_series

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
    1: ["yield_curve_10y3m"],
    2: [],
    3: [],
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


def latest_observation(dates: list[str], values: list[float | None]) -> tuple[str, float]:
    """Return the most recent non-missing observation as (iso_date, value)."""
    for d, v in zip(reversed(dates), reversed(values)):
        if v is not None:
            return d, v
    raise ValueError("Series contains no non-missing observations")


def find_sustained_inversions(
    dates: list[str], values: list[float | None], min_observations: int
) -> list[tuple[str, str]]:
    """Return sustained inversion episodes as (start, end) ISO date pairs.

    An episode is a run of at least ``min_observations`` consecutive
    non-missing observations strictly below zero. Missing observations
    (market holidays) do not break a run. The episode end is the date of the
    last negative observation before the spread turns non-negative. A run
    still open at the end of the series is included when long enough.
    """
    episodes: list[tuple[str, str]] = []
    run_start: str | None = None
    run_end: str | None = None
    run_length = 0
    for d, v in zip(dates, values):
        if v is None:
            continue
        if v < 0:
            if run_start is None:
                run_start = d
            run_end = d
            run_length += 1
        else:
            if run_start is not None and run_length >= min_observations:
                episodes.append((run_start, run_end))
            run_start, run_end, run_length = None, None, 0
    if run_start is not None and run_length >= min_observations:
        episodes.append((run_start, run_end))
    return episodes


def classify_yield_curve(
    dates: list[str], values: list[float | None], params: dict
) -> tuple[str, str]:
    """Classify the yield-curve indicator as benign, watch, or elevated.

    Rules (Navigo-chosen defaults, pending confirmation — data/thresholds.json):
    - watch: the latest spread is below zero (curve currently inverted);
    - elevated: the latest spread is at or above zero and the most recent
      sustained inversion ended within ``elevated_window_months`` of the
      latest observation date (the re-steepening risk window);
    - benign: anything else.
    """
    as_of_str, latest_value = latest_observation(dates, values)
    if latest_value < 0:
        return "watch", f"The curve is inverted ({latest_value:+.2f} on {as_of_str})."

    min_obs = params["sustained_inversion_min_observations"]
    window_months = params["elevated_window_months"]
    as_of = date.fromisoformat(as_of_str)
    for start, end in reversed(find_sustained_inversions(dates, values, min_obs)):
        end_date = date.fromisoformat(end)
        # Month arithmetic via relativedelta (Python months are 1-indexed).
        # relativedelta clamps month-end dates, e.g. 2024-02-29 + 12 months
        # gives 2025-02-28. The window is inclusive of its final day.
        window_close = end_date + relativedelta(months=+window_months)
        if end_date < as_of <= window_close:
            return (
                "elevated",
                f"A sustained inversion ({start} to {end}) ended within the "
                f"{window_months}-month re-steepening risk window.",
            )
        break  # Only the most recent episode can place today inside the window.
    return "benign", (
        f"The spread is positive ({latest_value:+.2f}) and no sustained "
        f"inversion ended within the trailing {window_months} months."
    )


def threshold_text(params: dict) -> str:
    return (
        "Below zero = watch. Within {m} months after a sustained inversion "
        "(at least {n} consecutive daily observations below zero) ends = "
        "elevated. Otherwise benign. Navigo-chosen parameters, pending "
        "confirmation."
    ).format(m=params["elevated_window_months"], n=params["sustained_inversion_min_observations"])


def build_yield_curve(thresholds: dict) -> tuple[dict, dict]:
    """Fetch T10Y3M and return (indicator, history) payloads."""
    params = thresholds["yield_curve_10y3m"]
    dates, values = fetch_series("T10Y3M")
    status, detail = classify_yield_curve(dates, values, params)
    as_of, value = latest_observation(dates, values)

    indicator = {
        "id": "yield_curve_10y3m",
        "name": "Yield Curve (10yr - 3mo)",
        "lens": 1,
        "value": value,
        "unit": "pct",
        "as_of": as_of,
        "status": status,
        "threshold": threshold_text(params),
        "source_url": "https://fred.stlouisfed.org/series/T10Y3M",
        "secondary_source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
        "notes": (
            f"{detail} Series identity verified against two independent "
            "sources on 2026-07-02 (see VERIFICATION.md). History file: "
            "data/history/t10y3m.json."
        ),
    }
    history = {
        "series_id": "T10Y3M",
        "name": indicator["name"],
        "unit": "pct",
        "source_url": indicator["source_url"],
        "updated_at": utc_now_iso(),
        "dates": [d for d, v in zip(dates, values) if v is not None],
        "values": [v for v in values if v is not None],
    }
    return indicator, history


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def update_lens_file(lens: int, built: list[dict]) -> Path:
    """Merge freshly built indicators into data/lens<N>.json by id.

    Indicators from other cadence groups are preserved; rows keep the
    canonical order so the UI is stable regardless of which group ran.
    """
    path = DATA_DIR / f"lens{lens}.json"
    existing = load_json(path) or {}
    by_id = {ind["id"]: ind for ind in existing.get("indicators", [])}
    for ind in built:
        by_id[ind["id"]] = ind
    order = CANONICAL_ORDER[lens]
    indicators = [by_id[i] for i in order if i in by_id]
    indicators += [ind for key, ind in by_id.items() if key not in order]

    title, subtitle = LENS_TITLES[lens]
    dump_json(
        path,
        {
            "lens": lens,
            "title": title,
            "subtitle": subtitle,
            "updated_at": utc_now_iso(),
            "indicators": indicators,
        },
    )
    return path


# Registry: builder callables per cadence group. Each returns
# (indicator_dict, history_dict_or_None). Later phases append here.
GROUPS: dict[str, list] = {
    "daily": [build_yield_curve],
    "monthly": [],
    "quarterly": [],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        choices=["daily", "monthly", "quarterly", "all"],
        default="all",
        help="Which cadence group to refresh (default: all).",
    )
    args = parser.parse_args(argv)
    groups = ["daily", "monthly", "quarterly"] if args.group == "all" else [args.group]

    thresholds = load_json(DATA_DIR / "thresholds.json")
    if thresholds is None:
        raise SystemExit("data/thresholds.json is missing; it must exist before updating data.")

    built_by_lens: dict[int, list[dict]] = {}
    for group in groups:
        for builder in GROUPS[group]:
            indicator, history = builder(thresholds)
            built_by_lens.setdefault(indicator["lens"], []).append(indicator)
            if history is not None:
                history_path = HISTORY_DIR / f"{history['series_id'].lower()}.json"
                dump_json(history_path, history)
                print(f"wrote {history_path.relative_to(ROOT)} ({history_path.stat().st_size:,} bytes)")

    for lens, built in sorted(built_by_lens.items()):
        path = update_lens_file(lens, built)
        statuses = ", ".join(f"{i['id']}={i['status']}" for i in built)
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes): {statuses}")

    if not built_by_lens:
        print("No builders registered for the requested group; nothing to do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
