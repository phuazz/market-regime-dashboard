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
# The number left the main page in 2026: naaim.org now embeds three widgets from
# index.naaim.org. /embeddable/number renders client-side and comes back empty to
# a plain fetch; /embeddable/table is static HTML and carries a dated series.
NAAIM_TABLE_URL = "https://index.naaim.org/embeddable/table"
# Weekly series. Three cycles of slack absorbs a missed post or a holiday week;
# beyond that the reading is not "current" in any sense the dashboard should
# imply, and saying so beats publishing a stale number as though it were live.
NAAIM_MAX_AGE_DAYS = 21
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


def fetch_naaim(today: date | None = None) -> dict:
    """Return the current NAAIM Exposure Index headline, with its real date.

    Rewritten 2026-08-11. The previous implementation anchored on the phrase
    "Exposure Index number is" on naaim.org; that phrase no longer appears
    anywhere on the page, so the builder had failed every run since at least
    2026-08-04 and the dashboard had been retaining a previous value for this
    row. NAAIM now embeds the widget from index.naaim.org.

    The dated table is used rather than the number widget, for two reasons.
    /embeddable/number renders client-side and returns an empty document to a
    plain fetch. And the table carries a real week-ending date per row, which
    removes the old "as-of stamped at collection time" approximation the
    builder had to apologise for -- a genuine gain in provenance.

    Licence discipline (module docstring): the table exposes ~130 weeks of
    history, and none of it is returned here. Only the newest row is taken,
    preserving the headline-plus-derivation pattern; back-filling the series
    would redistribute NAAIM's history.

    Raises ScrapeError with the parsed date and its age when the newest row is
    older than NAAIM_MAX_AGE_DAYS, which is a different fault from a layout
    change and must not be reported as one: a stale upstream is a sourcing
    decision for the operator, not a parser to repair.
    """
    text = fetch_text(NAAIM_TABLE_URL)
    # Date cell followed by the NAAIM number cell. US MM/DD/YYYY, parsed with
    # strptime -- never split by hand (Python months are 1-indexed).
    rows = re.findall(
        r"(\d{2}/\d{2}/\d{4})\s*</td>\s*<td[^>]*>\s*(-?[0-9]{1,3}(?:\.[0-9]{1,2})?)\s*<",
        text,
    )
    if not rows:
        raise ScrapeError(
            f"NAAIM layout changed: no dated rows parsed from {NAAIM_TABLE_URL}"
        )
    parsed = []
    for raw_date, raw_value in rows:
        try:
            parsed.append((datetime.strptime(raw_date, "%m/%d/%Y").date(), float(raw_value)))
        except ValueError:
            continue
    if not parsed:
        raise ScrapeError("NAAIM layout changed: dated rows found but none parsed")
    parsed.sort()
    week_ending, exposure = parsed[-1]

    age_days = ((today or date.today()) - week_ending).days
    if age_days > NAAIM_MAX_AGE_DAYS:
        raise ScrapeError(
            f"NAAIM feed is stale, not misparsed: newest dated row is "
            f"{week_ending.isoformat()}, {age_days} days old (budget {NAAIM_MAX_AGE_DAYS}). "
            f"Parsed {len(parsed)} rows from {NAAIM_TABLE_URL}. As at 2026-08-11 the "
            f"/embeddable/number widget also returns an empty body, so no current reading is "
            f"retrievable from NAAIM's published widgets. Whether NAAIM has paused the survey "
            f"or its migration is incomplete cannot be determined from here -- this dashboard "
            f"did scrape a value in late July, so do not assume the series ended in April."
        )
    return {"exposure": exposure, "as_of": week_ending.isoformat()}


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
