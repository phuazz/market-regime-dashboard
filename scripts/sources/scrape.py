"""Best-effort scrapers for indicators without a clean data API.

These cover the documented free proxies chosen in the approved plan: the
S&P Global US Manufacturing PMI headline (ISM proxy), the Conference Board
LEI press headline, and the multpl.com Shiller CAPE. Each parser raises
ScrapeError with a clear message on failure; the orchestrator treats a
failed builder as non-fatal and keeps the previous JSON value, so a layout
change upstream degrades to a stale-but-sourced value rather than a wrong
one. Every scraped print is cross-checked at first use per VERIFICATION.md.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import date, datetime

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

MULTPL_CAPE_URL = "https://www.multpl.com/shiller-pe"
SPGLOBAL_LISTING_URL = "https://www.pmi.spglobal.com/Public/Release/PressReleases?language=en"
TRADINGECONOMICS_PMI_URL = "https://tradingeconomics.com/united-states/manufacturing-pmi"
CONFERENCE_BOARD_LEI_URL = "https://www.conference-board.org/topics/us-leading-indicators"

# Month-name mapping is done by the date library (strptime %B / %b), never by
# hand. Python datetime months are 1-indexed.
_MONTH_NAMES = "January|February|March|April|May|June|July|August|September|October|November|December"


class ScrapeError(RuntimeError):
    """Raised when a page cannot be fetched or its expected pattern is absent."""


RETRY_DELAYS_SECONDS = (0, 5, 15)


def fetch_text(url: str, timeout: int = 90) -> str:
    last_error: Exception | None = None
    for delay in RETRY_DELAYS_SECONDS:
        if delay:
            time.sleep(delay)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:  # noqa: BLE001 — retried, then funnelled below
            last_error = error
    raise ScrapeError(
        f"Fetch failed for {url} after {len(RETRY_DELAYS_SECONDS)} attempts: {last_error}"
    ) from last_error


def _month_name_to_first_of_month(name: str, year: int) -> str:
    # strptime handles the month-name lookup (1-indexed months).
    month = datetime.strptime(name, "%B").month
    return date(year, month, 1).isoformat()


def fetch_multpl_cape() -> dict:
    """Return {"value": float, "as_of": iso_date, "mean": float|None, "median": float|None}."""
    text = fetch_text(MULTPL_CAPE_URL)
    value_match = re.search(r"Current Shiller PE Ratio[^0-9]{0,40}([0-9]{1,2}\.[0-9]{1,2})", text)
    if not value_match:
        raise ScrapeError("multpl.com layout changed: current CAPE value not found")
    value = float(value_match.group(1))

    # multpl prints a timestamp like "4:00 PM EDT, Wed Jul 1". The year is not
    # shown, so the run-date year applies; if the parsed month is ahead of the
    # run month, the print belongs to the previous year (year boundary).
    as_of = None
    stamp = re.search(r"[A-Z][a-z]{2},?\s+([A-Z][a-z]{2})\s+([0-9]{1,2})", text)
    if stamp:
        today = date.today()
        month = datetime.strptime(stamp.group(1), "%b").month
        year = today.year - 1 if month > today.month else today.year
        try:
            as_of = date(year, month, int(stamp.group(2))).isoformat()
        except ValueError:
            as_of = None

    mean_match = re.search(r"Mean[^0-9]{0,20}([0-9]{1,2}\.[0-9]{1,2})", text)
    median_match = re.search(r"Median[^0-9]{0,20}([0-9]{1,2}\.[0-9]{1,2})", text)
    return {
        "value": value,
        "as_of": as_of,
        "mean": float(mean_match.group(1)) if mean_match else None,
        "median": float(median_match.group(1)) if median_match else None,
    }


def _parse_pmi_from_text(text: str) -> dict:
    """Extract the US Manufacturing PMI headline and reference month."""
    value_match = re.search(
        r"US Manufacturing PMI[^0-9]{0,400}?([3-6][0-9]\.[0-9])", text, re.IGNORECASE | re.DOTALL
    )
    if not value_match:
        raise ScrapeError("US Manufacturing PMI headline value not found in page text")
    month_match = re.search(rf"in ({_MONTH_NAMES})(?: (20[0-9]{{2}}))?", text)
    reference = None
    if month_match:
        year = int(month_match.group(2)) if month_match.group(2) else date.today().year
        month = datetime.strptime(month_match.group(1), "%B").month
        # Year boundary: a January run reporting a December print belongs to
        # the previous year.
        if month > date.today().month and not month_match.group(2):
            year -= 1
        reference = date(year, month, 1).isoformat()
    return {"value": float(value_match.group(1)), "reference_month": reference}


def fetch_spglobal_pmi() -> dict:
    """Return the latest US Manufacturing PMI headline from S&P Global.

    Tries the official press-release listing first; falls back to the
    TradingEconomics summary of the same print. The returned dict carries
    the URL that actually supplied the number.
    """
    try:
        listing = fetch_text(SPGLOBAL_LISTING_URL)
        link_match = re.search(
            r'href="(/Public/Home/PressRelease/[0-9a-f]{16,40})"[^>]*>(?:(?!</a>).)*?'
            r"US Manufacturing PMI",
            listing,
            re.IGNORECASE | re.DOTALL,
        )
        if not link_match:
            raise ScrapeError("US Manufacturing PMI release link not found in listing")
        release_url = "https://www.pmi.spglobal.com" + link_match.group(1)
        parsed = _parse_pmi_from_text(fetch_text(release_url))
        parsed["source_url"] = release_url
        return parsed
    except ScrapeError:
        parsed = _parse_pmi_from_text(fetch_text(TRADINGECONOMICS_PMI_URL))
        parsed["source_url"] = TRADINGECONOMICS_PMI_URL
        return parsed


def fetch_conference_board_lei() -> dict:
    """Return the latest US LEI headline from the Conference Board topics page."""
    text = fetch_text(CONFERENCE_BOARD_LEI_URL)
    flat = re.sub(r"\s+", " ", text)

    level_match = re.search(
        rf"(?:increased|decreased|rose|fell|ticked (?:up|down))[^.]{{0,120}}?"
        rf"([0-9]+\.[0-9]+)% in ({_MONTH_NAMES}) (20[0-9]{{2}}) to ([0-9]{{2,3}}\.[0-9]+)",
        flat,
    )
    if not level_match:
        raise ScrapeError("Conference Board layout changed: LEI headline sentence not found")
    mom_pct = float(level_match.group(1))
    if re.search(rf"(?:decreased|fell|ticked down)[^.]{{0,120}}?{re.escape(level_match.group(1))}% in", flat):
        mom_pct = -mom_pct
    reference_month = _month_name_to_first_of_month(level_match.group(2), int(level_match.group(3)))
    level = float(level_match.group(4))

    six_match = re.search(r"(down|up|grew|contracted) (?:just |by )?([0-9]+\.[0-9]+)% over the six[- ]month", flat)
    six_month_pct = None
    if six_match:
        six_month_pct = float(six_match.group(2))
        if six_match.group(1) in ("down", "contracted"):
            six_month_pct = -six_month_pct
    return {
        "level": level,
        "mom_pct": mom_pct,
        "six_month_pct": six_month_pct,
        "reference_month": reference_month,
        "source_url": CONFERENCE_BOARD_LEI_URL,
    }
