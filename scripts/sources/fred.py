"""Fetch helpers for FRED series via the keyless fredgraph.csv endpoint.

The endpoint returns the full observation history for a series as CSV with
the header ``observation_date,<SERIES_ID>``. Missing observations (market
holidays and unposted dates) arrive as empty strings or ".". No API key is
required. Every series ID used in this project is verified against two
independent sources before first use — see VERIFICATION.md.

Transport note (probed on 2026-07-03, local machine and GitHub runner —
see scripts/net_probe.py and VERIFICATION.md): the CDN in front of FRED
matches the client fingerprint against the claimed identity per network
path. python-urllib is tarpitted from datacentre IPs with any user agent,
and a spoofed browser agent is tarpitted from residential IPs, while curl
under its own default agent passes on every path tested. The transport is
therefore curl-first (honest identity), alternating with urllib across
retries. Do not "simplify" this back to a single transport or spoof agents.
"""
from __future__ import annotations

import csv
import io
import shutil
import subprocess
import time
import urllib.request

FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
BOT_UA = "market-regime-dashboard/1.0 (data pipeline)"
RETRY_DELAYS_SECONDS = (0, 5, 15)


class FredFetchError(RuntimeError):
    """Raised when a FRED series cannot be fetched or parsed."""


def _curl_fetch(url: str, timeout: int) -> str:
    curl = shutil.which("curl")
    if curl is None:
        raise FredFetchError("curl is not available on this machine")
    result = subprocess.run(
        [curl, "-s", "--fail", "--max-time", str(timeout), url],
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0 or not result.stdout:
        raise FredFetchError(f"curl exited {result.returncode} for {url}")
    return result.stdout.lstrip("\ufeff")


def _urllib_fetch(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": BOT_UA, "Accept": "text/csv,text/plain,*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig")


def fetch_series(series_id: str, timeout: int = 60) -> tuple[list[str], list[float | None]]:
    """Return ``(dates, values)`` for one FRED series, oldest observation first.

    Dates are ISO ``YYYY-MM-DD`` strings exactly as FRED publishes them.
    Values are floats, or None where the observation is missing.
    """
    url = FREDGRAPH_URL.format(series_id=series_id)
    transports = ([_curl_fetch] if shutil.which("curl") else []) + [_urllib_fetch]
    last_error: Exception | None = None
    text: str | None = None
    for attempt, delay in enumerate(RETRY_DELAYS_SECONDS):
        if delay:
            time.sleep(delay)
        transport = transports[attempt % len(transports)]
        try:
            text = transport(url, timeout)
            break
        except Exception as error:  # noqa: BLE001 — retried, then funnelled below
            last_error = error
    if text is None:
        raise FredFetchError(
            f"Fetch failed for {series_id} after {len(RETRY_DELAYS_SECONDS)} attempts: {last_error}"
        )

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
