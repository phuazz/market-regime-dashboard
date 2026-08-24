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
MULTPL_CAPE_TABLE_URL = "https://www.multpl.com/shiller-pe/table/by-month"
SPGLOBAL_LISTING_URL = "https://www.pmi.spglobal.com/Public/Release/PressReleases?language=en"
TRADINGECONOMICS_PMI_URL = "https://tradingeconomics.com/united-states/manufacturing-pmi"
CONFERENCE_BOARD_LEI_URL = "https://www.conference-board.org/topics/us-leading-indicators"

# Month-name mapping is done by the date library (strptime %B / %b), never by
# hand. Python datetime months are 1-indexed.
_MONTH_NAMES = "January|February|March|April|May|June|July|August|September|October|November|December"


class ScrapeError(RuntimeError):
    """Raised when a page cannot be fetched or its expected pattern is absent."""


class StaleFeedError(ScrapeError):
    """Raised when a source parses cleanly but its newest observation is too old.

    Deliberately distinct from a bare ScrapeError, because the two demand
    different responses. A ScrapeError means the parser no longer matches the
    page and someone must fix code. A StaleFeedError means the code is fine and
    the publisher has stopped, which no amount of parsing will repair -- the
    caller may choose to park the row rather than fail the build indefinitely.

    Carries the last good observation so the caller can park on a dated,
    verifiable reading instead of inventing one or holding an undated value.
    """

    def __init__(self, message: str, reading: dict | None = None, age_days: int | None = None):
        super().__init__(message)
        self.reading = reading or {}
        self.age_days = age_days


RETRY_DELAYS_SECONDS = (0, 5, 15)


def fetch_bytes(url: str, timeout: int = 90) -> bytes:
    """Fetch a binary artefact (spreadsheets) with the same retry policy."""
    last_error: Exception | None = None
    for delay in RETRY_DELAYS_SECONDS:
        if delay:
            time.sleep(delay)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": BROWSER_UA, "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:  # noqa: BLE001 — retried, then funnelled below
            last_error = error
    raise ScrapeError(
        f"Fetch failed for {url} after {len(RETRY_DELAYS_SECONDS)} attempts: {last_error}"
    ) from last_error


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


def fetch_multpl_cape_history() -> tuple[list[str], list[float]]:
    """Return monthly Shiller CAPE history (oldest first) from multpl.

    The by-month table has the same markup as the trailing-P/E table. The
    CAPE is Robert Shiller's freely published dataset (Yale), so the monthly
    history is public and may be charted; only survey-provider series (AAII,
    NAAIM, S&P Global, Conference Board) carry redistribution limits.
    """
    text = fetch_text(MULTPL_CAPE_TABLE_URL)
    cells = re.findall(
        r"<td>([A-Z][a-z]{2} [0-9]{1,2}, [0-9]{4})</td>\s*<td[^>]*>(.*?)</td>",
        text,
        re.DOTALL,
    )
    parsed = []
    for raw_date, cell_body in cells:
        value_match = re.search(r"([0-9]{1,3}\.[0-9]{1,2})", cell_body)
        if not value_match:
            continue
        # strptime handles month-name parsing (months are 1-indexed).
        day = datetime.strptime(raw_date, "%b %d, %Y").date()
        parsed.append((day.isoformat(), float(value_match.group(1))))
    if len(parsed) < 200:
        raise ScrapeError(f"multpl CAPE by-month table parsed only {len(parsed)} rows; layout changed")
    parsed.sort()
    return [d for d, _ in parsed], [v for _, v in parsed]


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


# Words the Conference Board uses for the direction of a change, mapped to the
# sign to apply to the magnitude that follows them. Both noun forms ("an
# increase of 0.2%") and verb forms ("fell by 2.4%") appear, and the release
# rewords month to month, so the sign is taken from an explicit word list
# rather than inferred from sentence shape.
_LEI_DIRECTION_SIGN = {
    "increase": 1, "increased": 1, "rose": 1, "grew": 1, "growth": 1, "gain": 1,
    "expanded": 1, "up": 1, "ticked up": 1, "edged up": 1,
    "decrease": -1, "decreased": -1, "decline": -1, "declined": -1, "fell": -1,
    "drop": -1, "dropped": -1, "contraction": -1, "contracted": -1, "down": -1,
    "ticked down": -1, "edged down": -1,
}
_LEI_DIRECTIONS = "|".join(sorted(_LEI_DIRECTION_SIGN, key=len, reverse=True))

# The month-over-month headline: "(LEI) for the US increased by 0.2% in July
# 2026 to 99.5 (2016=100)". The same sentence shape is used for the CEI and the
# LAG further down the release, so callers must anchor on "(LEI)" before it --
# see _lei_release_window.
_LEI_LEVEL_RE = re.compile(
    rf"({_LEI_DIRECTIONS})[^.]{{0,120}}?"
    rf"([0-9]+\.[0-9]+)% in ({_MONTH_NAMES}) (20[0-9]{{2}}) to ([0-9]{{2,3}}\.[0-9]+)"
)

# The six-month growth rate, in the two shapes the release has used. Ordered:
# the first is the August 2026 rewrite, the second the earlier wording. Both put
# the direction word before the magnitude.
#
# The August 2026 sentence reads: "the LEI's six-month growth rate turned
# positive, to an increase of 0.2% between January and July 2026, a sharp
# reversal from its 1.3% contraction over the previous six months." Neither
# pattern can match that trailing 1.3% -- it is a magnitude-then-direction
# clause about the PRIOR window -- and test_lei_source pins that, because
# picking it up would flip the sign of the published figure silently.
_LEI_SIX_MONTH_PATTERNS = (
    re.compile(rf"six[- ]month growth rate[^.]{{0,100}}?({_LEI_DIRECTIONS}) of ([0-9]+\.[0-9]+)%"),
    re.compile(rf"({_LEI_DIRECTIONS})(?: just| by)? ([0-9]+\.[0-9]+)% over the six[- ]month"),
)


def _lei_release_window(flat: str) -> str:
    """Return the LEI paragraph of the press release, and only that paragraph.

    The release repeats the same sentence shapes for the Coincident (CEI) and
    Lagging (LAG) indexes, and the page also carries an explanatory blurb and
    meta tags that name the LEI. Searching the whole page therefore works only
    for as long as the LEI happens to come first -- it does today, which is why
    the previous version of this parser was right by luck rather than by
    construction. The window is cut from the LEI headline sentence to the start
    of the CEI paragraph so a reordering upstream cannot silently substitute the
    CEI's numbers for the LEI's.
    """
    for match in _LEI_LEVEL_RE.finditer(flat):
        # A sentence belongs to whichever index was named most recently before
        # it, so the test is the LAST marker in the prefix rather than the mere
        # presence of "(LEI)". The explanatory blurb above the release names all
        # three indexes, which is why presence alone is not enough.
        markers = re.findall(r"\((?:LEI|CEI|LAG)\)", flat[max(0, match.start() - 400) : match.start()])
        if not markers or markers[-1] != "(LEI)":
            continue
        window = flat[match.start() : match.start() + 1500]
        cei = window.find("(CEI)")
        return window[:cei] if cei > 0 else window
    raise ScrapeError("Conference Board layout changed: LEI headline sentence not found")


def fetch_conference_board_lei() -> dict:
    """Return the latest US LEI headline from the Conference Board topics page."""
    flat = re.sub(r"\s+", " ", fetch_text(CONFERENCE_BOARD_LEI_URL))
    window = _lei_release_window(flat)

    level_match = _LEI_LEVEL_RE.search(window)
    mom_pct = float(level_match.group(2)) * _LEI_DIRECTION_SIGN[level_match.group(1)]
    reference_month = _month_name_to_first_of_month(level_match.group(3), int(level_match.group(4)))
    level = float(level_match.group(5))

    six_month_pct = None
    for pattern in _LEI_SIX_MONTH_PATTERNS:
        six_match = pattern.search(window)
        if six_match:
            six_month_pct = float(six_match.group(2)) * _LEI_DIRECTION_SIGN[six_match.group(1)]
            break
    # A six-month change outside this band has never been printed, including
    # 2008 and 2020, so it means the wrong number was picked up rather than a
    # remarkable month. Refuse it instead of classifying on it.
    if six_month_pct is not None and abs(six_month_pct) > 15:
        raise ScrapeError(
            f"Conference Board layout changed: implausible six-month change {six_month_pct:+.1f}%"
        )
    return {
        "level": level,
        "mom_pct": mom_pct,
        "six_month_pct": six_month_pct,
        "reference_month": reference_month,
        "source_url": CONFERENCE_BOARD_LEI_URL,
    }
