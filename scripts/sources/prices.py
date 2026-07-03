"""Price feeds for index series.

Primary: the Yahoo Finance chart API (the same endpoint the yfinance library
wraps), fetched with a browser user agent and no dependencies. Second feed
for verification: FRED `SP500`, the official S&P 500 close carried on the
already-verified keyless endpoint (ten-year window). Stooq, named in
SPEC.md as an option, now sits behind a JavaScript proof-of-work challenge
and is not automatable — documented in VERIFICATION.md.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Two equivalent hosts; retries alternate between them because datacentre
# IP ranges (GitHub Actions runners) are throttled per host.
YAHOO_CHART_URL = (
    "https://{host}/v8/finance/chart/{symbol}"
    "?period1={period1}&period2=9999999999&interval=1d"
)
YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
RETRY_DELAYS_SECONDS = (0, 5, 15, 30)
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class PriceFetchError(RuntimeError):
    """Raised when a price feed cannot be fetched or parsed."""


def fetch_yahoo_daily(symbol: str, period1: int = 0, timeout: int = 90) -> tuple[list[str], list[float]]:
    """Return (dates, closes) for a symbol from the Yahoo chart API.

    Timestamps convert to UTC dates via the date library. The final
    observation is dropped when its date equals the run date in UTC, because
    the US session may still be open; once the session has closed (evening
    US time is already the next UTC day), the bar keeps. Documented in
    VERIFICATION.md.
    """
    last_error: Exception | None = None
    payload = None
    for attempt, delay in enumerate(RETRY_DELAYS_SECONDS):
        if delay:
            time.sleep(delay)
        url = YAHOO_CHART_URL.format(
            host=YAHOO_HOSTS[attempt % len(YAHOO_HOSTS)],
            symbol=urllib.parse.quote(symbol),
            period1=period1,
        )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            break
        except Exception as error:  # noqa: BLE001 — retried, then funnelled below
            last_error = error
    if payload is None:
        raise PriceFetchError(
            f"Yahoo chart fetch failed for {symbol} after "
            f"{len(RETRY_DELAYS_SECONDS)} attempts: {last_error}"
        ) from last_error

    try:
        result = payload["chart"]["result"][0]
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as error:
        raise PriceFetchError(f"Yahoo chart payload malformed for {symbol}") from error

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dates: list[str] = []
    values: list[float] = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        if day == today_utc:
            continue  # potentially incomplete session
        dates.append(day)
        values.append(round(float(close), 2))
    if not dates:
        raise PriceFetchError(f"No completed daily closes returned for {symbol}")
    return dates, values
