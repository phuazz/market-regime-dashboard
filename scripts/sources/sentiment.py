"""Sentiment and positioning sources for Lens 2 (market-peak froth).

Licence discipline: the AAII workbook is fetched at runtime and used
in-memory to calibrate percentile triggers; the raw history is never
written to disk or committed (AAII terms of service). Only the current
headline and derived statistics are published. The same
headline-plus-derivation pattern applies to multpl.

The NAAIM Exposure Index was removed on 2026-09-12. NAAIM put current
readings behind a subscription on 2026-08-01 and delayed the public series
by three months, so no current value is retrievable from public data.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime

import xlrd

from sources.scrape import ScrapeError, fetch_bytes, fetch_text

AAII_XLS_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
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


def _highcharts_configs(text: str) -> list[dict]:
    """Return every Highcharts option object embedded in the page, parsed.

    Each chart on the Renaissance stats page is emitted as
    `var ChartOptions = {...};Highcharts.chart("<id>",ChartOptions);`. The
    object is walked brace by brace rather than matched with a regex, because
    the config nests several levels deep and its string values contain braces
    of their own ("pointFormat":"{series.name}: <b>{point.y}</b>"), so the scan
    tracks whether it is inside a string literal.

    Parsing the object is what makes the caller indifferent to key order. The
    previous regex required "data" before "name" within a series; the annual
    chart writes them in that order and the monthly charts write them the other
    way round, which is what broke the monthly parse.
    """
    configs = []
    for match in re.finditer(r"var ChartOptions\s*=\s*\{", text):
        start = match.end() - 1
        depth, in_string, escaped = 0, False, False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        configs.append(json.loads(text[start : index + 1]))
                    except json.JSONDecodeError:
                        pass
                    break
    return configs


def _chart_series(config: dict, name: str) -> list[float]:
    """Return the y values of the named series in a parsed Highcharts config."""
    for series in config.get("series", []):
        if series.get("name") == name:
            return [float(point["y"]) for point in series.get("data", [])]
    raise ScrapeError(f"Renaissance layout changed: no '{name}' series in chart")


def fetch_renaissance_ipo_stats() -> dict:
    """Return US IPO issuance statistics from the Renaissance Capital page.

    The page embeds Highcharts configs: an annual chart (year categories with
    "Proceeds in Billions (US$)" and "Number of IPOs" series) and one monthly
    chart per year, each rendering into `pricings<year>Chart`. The annual chart
    is found by its year categories and the monthly chart is bound to the
    current year by its render target, so neither the order of the charts on
    the page nor the presence of the prior-year monthly chart can select the
    wrong series.
    """
    text = fetch_text(RENAISSANCE_STATS_URL)
    configs = _highcharts_configs(text)
    if not configs:
        raise ScrapeError("Renaissance layout changed: no Highcharts config found")

    def categories(config: dict) -> list[str]:
        axes = config.get("xAxis") or [{}]
        return axes[0].get("categories", [])

    annual = next(
        (c for c in configs if all(re.fullmatch(r"(19|20)[0-9]{2}", x) for x in categories(c) or ["-"])),
        None,
    )
    if annual is None:
        raise ScrapeError("Renaissance layout changed: year categories not found")
    years = [int(y) for y in categories(annual)]
    current_year = years[-1]

    proceeds = _chart_series(annual, "Proceeds in Billions (US$)")
    counts = _chart_series(annual, "Number of IPOs")
    if len(proceeds) != len(years) or len(counts) != len(years):
        raise ScrapeError("Renaissance layout changed: annual series do not match the year axis")

    target = f"pricings{current_year}Chart"
    monthly = next((c for c in configs if c.get("chart", {}).get("renderTo") == target), None)
    if monthly is None:
        raise ScrapeError(f"Renaissance layout changed: no monthly chart rendering into {target}")
    monthly_counts = _chart_series(monthly, "Number of IPOs")
    if len(monthly_counts) != 12:
        raise ScrapeError(
            f"Renaissance layout changed: {target} has {len(monthly_counts)} months, expected 12"
        )
    # Guard against having taken the monthly chart of the wrong year, which
    # would corrupt months_elapsed and therefore the annualised pace without
    # producing anything that looks wrong. The two charts are rendered from the
    # same snapshot and have agreed exactly in every year checked.
    if int(sum(monthly_counts)) != int(counts[-1]):
        raise ScrapeError(
            f"Renaissance mismatch: {target} sums to {int(sum(monthly_counts))} IPOs but the "
            f"annual chart reports {int(counts[-1])} for {current_year}"
        )

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

    return {
        "current_year": current_year,
        "as_of": as_of,
        "months_elapsed": months_elapsed,
        "ytd_proceeds_bn": proceeds[-1],
        "ytd_count": int(counts[-1]),
        "annual_proceeds_bn": dict(zip(years, proceeds)),
        "annual_counts": {y: int(c) for y, c in zip(years, counts)},
    }
