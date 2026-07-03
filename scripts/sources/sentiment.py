"""Sentiment and positioning sources for Lens 2 (market-peak froth).

Licence discipline: the AAII workbook is fetched at runtime and used
in-memory to calibrate percentile triggers; the raw history is never
written to disk or committed (AAII terms of service). Only the current
headline and derived statistics are published. The same
headline-plus-derivation pattern applies to NAAIM and multpl.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import xlrd

from sources.scrape import ScrapeError, fetch_bytes, fetch_text

AAII_XLS_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
NAAIM_URL = "https://naaim.org/programs/naaim-exposure-index/"
MULTPL_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio"
MULTPL_PE_TABLE_URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
RENAISSANCE_STATS_URL = "https://www.renaissancecapital.com/IPO-Center/Stats"


def percentile_rank(values: list[float], target: float) -> float:
    """Share of values at or below target, in percent."""
    if not values:
        raise ValueError("percentile_rank of empty list")
    return 100.0 * sum(1 for v in values if v <= target) / len(values)


def fetch_aaii() -> dict:
    """Return the current AAII week plus spread statistics from full history.

    The workbook's SENTIMENT sheet carries weekly rows since 1987: date
    serial in column 0, bullish/neutral/bearish fractions in columns 1-3,
    bull-bear spread in column 6. Footer rows carry text and are skipped.
    """
    book = xlrd.open_workbook(file_contents=fetch_bytes(AAII_XLS_URL))
    sheet = book.sheet_by_name("SENTIMENT")
    weeks: list[tuple[str, float, float, float]] = []
    for r in range(sheet.nrows):
        serial = sheet.cell_value(r, 0)
        bullish = sheet.cell_value(r, 1)
        bearish = sheet.cell_value(r, 3)
        spread = sheet.cell_value(r, 6)
        if not all(isinstance(v, float) for v in (serial, bullish, bearish, spread)):
            continue
        # Excel serial to date via the workbook's own datemode (date library
        # handles the conversion; Python months are 1-indexed).
        day = xlrd.xldate_as_datetime(serial, book.datemode).date()
        weeks.append((day.isoformat(), bullish * 100.0, bearish * 100.0, spread * 100.0))
    if len(weeks) < 500:
        raise ScrapeError(f"AAII workbook parsed only {len(weeks)} weekly rows; layout changed")
    weeks.sort()
    spreads = [w[3] for w in weeks]
    ordered = sorted(spreads)
    p90 = ordered[int(0.9 * (len(ordered) - 1))]
    week_ending, bullish_pct, bearish_pct, spread_pp = weeks[-1]
    return {
        "week_ending": week_ending,
        "bullish_pct": round(bullish_pct, 1),
        "bearish_pct": round(bearish_pct, 1),
        "spread_pp": round(spread_pp, 1),
        "spread_p90_pp": round(p90, 1),
        "spread_percentile": round(percentile_rank(spreads, spread_pp), 1),
        "history_weeks": len(weeks),
    }


def fetch_naaim() -> dict:
    """Return the current NAAIM Exposure Index headline.

    The page renders the number in its own element straight after the
    "Exposure Index number is" heading; page ids can contain digits, so the
    pattern anchors on the tag structure rather than a digit-free gap. The
    page carries no reliable as-of date (event promos repeat other dates),
    so the builder stamps the run date with an approximation note.
    """
    text = fetch_text(NAAIM_URL)
    match = re.search(
        r"Exposure Index number is[^<]*</h\d>\s*<div[^>]*>\s*([0-9]{1,3}(?:\.[0-9]{1,2})?)\s*</div>",
        text,
    )
    if not match:
        raise ScrapeError("NAAIM layout changed: exposure headline not found")
    return {"exposure": float(match.group(1)), "as_of": None}


def fetch_multpl_pe() -> dict:
    """Return the current trailing S&P 500 P/E from multpl."""
    text = fetch_text(MULTPL_PE_URL)
    match = re.search(r"Current S&P 500 PE Ratio[^0-9]{0,40}([0-9]{1,3}\.[0-9]{1,2})", text)
    if not match:
        raise ScrapeError("multpl layout changed: current P/E not found")
    return {"value": float(match.group(1))}


def fetch_multpl_pe_history() -> tuple[list[str], list[float], list[bool]]:
    """Return monthly trailing P/E history (oldest first) from multpl.

    Recent months carry an <abbr title="Estimate"> dagger inside the value
    cell — multpl marks them as estimates pending final earnings. The third
    return value flags those rows so the UI can surface the uncertainty.
    """
    text = fetch_text(MULTPL_PE_TABLE_URL)
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
        parsed.append((day.isoformat(), float(value_match.group(1)), "abbr" in cell_body))
    if len(parsed) < 200:
        raise ScrapeError(f"multpl by-month table parsed only {len(parsed)} rows; layout changed")
    parsed.sort()
    return (
        [d for d, _, _ in parsed],
        [v for _, v, _ in parsed],
        [e for _, _, e in parsed],
    )


def fetch_renaissance_ipo_stats() -> dict:
    """Return US IPO issuance statistics from the Renaissance Capital page.

    The page embeds Highcharts configs: an annual chart (year categories
    with "Proceeds in Billions (US$)" and "Number of IPOs" series) and a
    monthly chart for the current year. Series are matched by name and by
    length against the category count, so chart order changes do not break
    the parse.
    """
    text = fetch_text(RENAISSANCE_STATS_URL)
    years_match = re.search(r'"categories":\[((?:"(?:19|20)[0-9]{2}",?)+)\]', text)
    if not years_match:
        raise ScrapeError("Renaissance layout changed: year categories not found")
    years = [int(y) for y in re.findall(r"[0-9]{4}", years_match.group(1))]

    series: dict[str, list[list[float]]] = {}
    for data_blob, name in re.findall(
        r'"data":\[((?:\{"y":[0-9.]+\},?)+)\][^\[\]]*?"name":"([^"]+)"', text
    ):
        values = [float(v) for v in re.findall(r'"y":([0-9.]+)', data_blob)]
        series.setdefault(name, []).append(values)

    def pick(name: str, length: int) -> list[float]:
        for candidate in series.get(name, []):
            if len(candidate) == length:
                return candidate
        raise ScrapeError(f"Renaissance layout changed: no '{name}' series of length {length}")

    proceeds = pick("Proceeds in Billions (US$)", len(years))
    counts = pick("Number of IPOs", len(years))
    monthly_counts = pick("Number of IPOs", 12)

    as_of = date.today().isoformat()
    stamp = re.search(r"as of ([0-9]{2})/([0-9]{2})/([0-9]{4})", text)
    if stamp:
        # strptime parses the US-format stamp (months are 1-indexed).
        as_of = datetime.strptime("/".join(stamp.groups()), "%m/%d/%Y").date().isoformat()

    months_elapsed = 0
    for index, value in enumerate(monthly_counts):
        if value > 0:
            months_elapsed = index + 1
    if months_elapsed == 0:
        raise ScrapeError("Renaissance layout changed: monthly counts are all zero")

    current_year = years[-1]
    return {
        "current_year": current_year,
        "as_of": as_of,
        "months_elapsed": months_elapsed,
        "ytd_proceeds_bn": proceeds[-1],
        "ytd_count": int(counts[-1]),
        "annual_proceeds_bn": dict(zip(years, proceeds)),
        "annual_counts": {y: int(c) for y, c in zip(years, counts)},
    }
