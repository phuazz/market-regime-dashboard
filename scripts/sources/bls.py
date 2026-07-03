"""Fetch helper for the BLS public API (v1, keyless).

Used by scripts/verify_series.py to cross-check FRED labour series against
the originating agency. The runtime pipeline reads FRED; this module exists
so the two-source verification is repeatable on demand.
"""
from __future__ import annotations

import json
import urllib.request

BLS_API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
USER_AGENT = "market-regime-dashboard/1.0 (verification)"

# BLS series IDs for the FRED labour series used in Lens 1.
BLS_EQUIVALENTS = {
    "UNRATE": "LNS14000000",     # unemployment rate, seasonally adjusted
    "PAYEMS": "CES0000000001",   # total nonfarm payrolls, thousands, SA
    "UEMP27OV": "LNS13008636",   # unemployed 27 weeks and over, thousands, SA
}

# BLS reference periods are months (M01..M12, 1-indexed like Python datetime).
_MONTH_BY_PERIOD = {f"M{m:02d}": m for m in range(1, 13)}


def fetch_bls_series(series_ids: list[str], start_year: int, end_year: int) -> dict[str, dict[str, float]]:
    """Return {series_id: {"YYYY-MM-01": value}} from the BLS public API."""
    body = json.dumps(
        {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    ).encode("utf-8")
    request = urllib.request.Request(
        BLS_API_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API request failed: {payload.get('message')}")

    out: dict[str, dict[str, float]] = {}
    for series in payload["Results"]["series"]:
        points: dict[str, float] = {}
        for row in series["data"]:
            month = _MONTH_BY_PERIOD.get(row["period"])
            if month is None:  # skip annual averages (M13)
                continue
            raw = row["value"].replace(",", "").strip()
            if raw in ("", "-"):  # BLS placeholder for unavailable values
                continue
            points[f"{row['year']}-{month:02d}-01"] = float(raw)
        out[series["seriesID"]] = points
    return out
