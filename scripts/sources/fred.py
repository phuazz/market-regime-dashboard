"""Fetch helpers for FRED series via the keyless fredgraph.csv endpoint.

The endpoint returns the full observation history for a series as CSV with
the header ``observation_date,<SERIES_ID>``. Missing observations (market
holidays and unposted dates) arrive as empty strings or ".". No API key is
required. Every series ID used in this project is verified against two
independent sources before first use — see VERIFICATION.md.
"""
from __future__ import annotations

import csv
import io
import urllib.request

FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
USER_AGENT = "navigo-market-regime-dashboard/1.0 (internal data pipeline)"


class FredFetchError(RuntimeError):
    """Raised when a FRED series cannot be fetched or parsed."""


def fetch_series(series_id: str, timeout: int = 60) -> tuple[list[str], list[float | None]]:
    """Return ``(dates, values)`` for one FRED series, oldest observation first.

    Dates are ISO ``YYYY-MM-DD`` strings exactly as FRED publishes them.
    Values are floats, or None where the observation is missing.
    """
    url = FREDGRAPH_URL.format(series_id=series_id)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8-sig")

    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or header[0] != "observation_date" or series_id not in header:
        raise FredFetchError(f"Unexpected fredgraph header for {series_id}: {header}")
    column = header.index(series_id)

    dates: list[str] = []
    values: list[float | None] = []
    for row in reader:
        if len(row) <= column:
            continue
        raw = row[column].strip()
        dates.append(row[0])
        values.append(float(raw) if raw not in ("", ".") else None)

    if not dates:
        raise FredFetchError(f"No observations returned for {series_id}")
    return dates, values
