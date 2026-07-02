"""Lens 1 (recession risk) — classifiers and indicator builders.

Every builder returns an indicator dict following the SPEC.md section 9
schema (plus display fields: description, qualifier, cadence, signed,
decimals) and writes its own history file. Classifiers are pure functions
over (data, params) so tests/test_status.py can exercise thresholds without
network access. All parameters live in data/thresholds.json and are
Navigo-chosen defaults pending confirmation.

Date handling: Python datetime months are 1-indexed. Month arithmetic uses
dateutil.relativedelta only.
"""
from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

from sources import scrape
from sources.fred import fetch_series
from util import (
    append_scrape_history,
    clean_series,
    latest_observation,
    utc_now_iso,
    write_fred_history,
)

VERIFIED_NOTE = "Series identity verified against two sources (VERIFICATION.md)."


# ---------------------------------------------------------------------------
# Yield curve (10yr - 3mo)

def find_sustained_inversions(
    dates: list[str], values: list[float | None], min_observations: int
) -> list[tuple[str, str]]:
    """Return sustained inversion episodes as (start, end) ISO date pairs.

    An episode is a run of at least ``min_observations`` consecutive
    non-missing observations strictly below zero. Missing observations
    (market holidays) do not break a run. A run still open at the end of
    the series is included when long enough.
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
    """benign / watch / elevated for the 10yr-3mo spread (see thresholds.json)."""
    as_of_str, latest_value = latest_observation(dates, values)
    if latest_value < 0:
        return "watch", f"The curve is inverted ({latest_value:+.2f} on {as_of_str})."

    min_obs = params["sustained_inversion_min_observations"]
    window_months = params["elevated_window_months"]
    as_of = date.fromisoformat(as_of_str)
    for start, end in reversed(find_sustained_inversions(dates, values, min_obs)):
        end_date = date.fromisoformat(end)
        # Month arithmetic via relativedelta (Python months are 1-indexed).
        # relativedelta clamps month-end dates (2024-02-29 + 12 months gives
        # 2025-02-28). The window is inclusive of its final day.
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


def build_yield_curve(thresholds: dict) -> dict:
    params = thresholds["yield_curve_10y3m"]
    dates, values = fetch_series("T10Y3M")
    status, detail = classify_yield_curve(dates, values, params)
    as_of, value = latest_observation(dates, values)
    clean_dates, clean_values = clean_series(dates, values)
    write_fred_history("T10Y3M", "Yield Curve (10yr - 3mo)", "pct",
                       "https://fred.stlouisfed.org/series/T10Y3M", clean_dates, clean_values)
    return {
        "id": "yield_curve_10y3m",
        "name": "Yield Curve (10yr - 3mo)",
        "qualifier": "term spread",
        "lens": 1,
        "value": value,
        "unit": "pct",
        "signed": True,
        "decimals": 2,
        "cadence": "daily",
        "as_of": as_of,
        "status": status,
        "description": (
            "The 10-year minus 3-month Treasury constant-maturity spread. A negative reading "
            "(inversion) has historically preceded US recessions; the risk window extends "
            "through the re-steepening that follows a sustained inversion."
        ),
        "threshold": (
            "Below zero = watch. Within {m} months after a sustained inversion (at least {n} "
            "consecutive daily observations below zero) ends = elevated. Otherwise benign."
        ).format(m=params["elevated_window_months"], n=params["sustained_inversion_min_observations"]),
        "source_url": "https://fred.stlouisfed.org/series/T10Y3M",
        "secondary_source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
        "notes": f"{detail} {VERIFIED_NOTE}",
    }


# ---------------------------------------------------------------------------
# Sahm Rule

def classify_sahm(value: float, params: dict) -> tuple[str, str]:
    if value >= params["elevated_level"]:
        return "elevated", (
            f"The Sahm reading of {value:+.2f} is at or above the published "
            f"{params['elevated_level']:.2f} trigger."
        )
    if value >= params["watch_level"]:
        return "watch", (
            f"The Sahm reading of {value:+.2f} sits in the "
            f"{params['watch_level']:.2f}–{params['elevated_level']:.2f} watch band."
        )
    return "benign", f"The Sahm reading of {value:+.2f} is below the watch band."


def build_sahm(thresholds: dict) -> dict:
    params = thresholds["sahm_rule"]
    dates, values = fetch_series("SAHMREALTIME")
    as_of, value = latest_observation(dates, values)
    status, detail = classify_sahm(value, params)
    clean_dates, clean_values = clean_series(dates, values)
    write_fred_history("SAHMREALTIME", "Sahm Rule (real-time)", "pp",
                       "https://fred.stlouisfed.org/series/SAHMREALTIME", clean_dates, clean_values)
    return {
        "id": "sahm_rule",
        "name": "Sahm Rule",
        "qualifier": "jobs momentum",
        "lens": 1,
        "value": value,
        "unit": "pp",
        "signed": True,
        "decimals": 2,
        "cadence": "monthly",
        "as_of": as_of,
        "status": status,
        "description": (
            "Rise of the three-month average unemployment rate above its low of the previous "
            "twelve months. The published 0.50 trigger has fired at the start of every US "
            "recession since 1970 (Sahm 2019)."
        ),
        "threshold": (
            "At or above {e:.2f} = elevated (published Sahm trigger). {w:.2f}-{e:.2f} = watch."
        ).format(e=params["elevated_level"], w=params["watch_level"]),
        "source_url": "https://fred.stlouisfed.org/series/SAHMREALTIME",
        "secondary_source_url": "https://www.currentmarketvaluation.com/models/sahm-rule.php",
        "notes": (
            f"{detail} The real-time variant (SAHMREALTIME) is used so historical values "
            f"reflect data as originally published; construction recomputed from UNRATE. "
            f"{VERIFIED_NOTE}"
        ),
    }


# ---------------------------------------------------------------------------
# High-yield credit spreads (ICE BofA US High Yield OAS)

def classify_hy_oas(values: list[float], params: dict) -> tuple[str, str, dict]:
    latest = values[-1]
    stats = {
        "rise_63d_bp": (latest - values[-64]) * 100 if len(values) >= 64 else None,
    }
    rise = stats["rise_63d_bp"] or 0.0
    if latest >= params["elevated_level"] or rise >= params["elevated_rise_bp"]:
        status = "elevated"
        detail = (
            f"OAS of {latest:.2f} is at or above the {params['elevated_level']:.2f} elevated "
            f"level, or has widened {rise:.0f} bp over 63 trading days."
        )
    elif latest >= params["watch_level"] or rise >= params["watch_rise_bp"]:
        status = "watch"
        detail = (
            f"OAS of {latest:.2f} is at or above the {params['watch_level']:.2f} watch level, "
            f"or has widened {rise:.0f} bp over 63 trading days."
        )
    else:
        status = "benign"
        detail = (
            f"OAS of {latest:.2f} is below the {params['watch_level']:.2f} watch level with a "
            f"63-trading-day change of {rise:+.0f} bp."
        )
    if latest <= params["complacency_level"]:
        detail += (
            f" Complacency note: the spread is at or below {params['complacency_level']:.2f} — "
            f"historically tight, a sign of reach-for-yield rather than safety."
        )
    return status, detail, stats


def build_hy_oas(thresholds: dict) -> dict:
    params = thresholds["hy_credit_spreads"]
    dates, values = fetch_series("BAMLH0A0HYM2")
    clean_dates, clean_values = clean_series(dates, values)
    status, detail, _ = classify_hy_oas(clean_values, params)
    as_of, value = clean_dates[-1], clean_values[-1]
    write_fred_history("BAMLH0A0HYM2", "ICE BofA US High Yield OAS", "pct",
                       "https://fred.stlouisfed.org/series/BAMLH0A0HYM2", clean_dates, clean_values)
    return {
        "id": "hy_credit_spreads",
        "name": "High-Yield Credit Spreads",
        "qualifier": "HY OAS",
        "lens": 1,
        "value": value,
        "unit": "pct",
        "signed": False,
        "decimals": 2,
        "cadence": "daily",
        "as_of": as_of,
        "status": status,
        "description": (
            "Option-adjusted spread of the ICE BofA US High Yield Index over Treasuries. "
            "The cleanest market-priced stress gauge: it widens sharply into downturns, "
            "and unusually tight spreads signal complacency rather than safety."
        ),
        "threshold": (
            "At or above {wl:.2f}, or widening {w} bp over 63 trading days = watch. At or above "
            "{el:.2f}, or widening {e} bp = elevated. At or below {cl:.2f} adds a complacency "
            "note without changing status."
        ).format(
            wl=params["watch_level"], el=params["elevated_level"], cl=params["complacency_level"],
            w=params["watch_rise_bp"], e=params["elevated_rise_bp"],
        ),
        "source_url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        "secondary_source_url": "https://www.gurufocus.com/economic_indicators/5735/bofa-us-high-yield-index-optionadjusted-spread",
        "notes": (
            f"{detail} Absolute levels are Navigo anchors near the published long-run median and "
            f"75th percentile; the keyless FRED endpoint serves this ICE-licensed series from "
            f"{clean_dates[0]} only, so window percentiles would drift. {VERIFIED_NOTE}"
        ),
    }


# ---------------------------------------------------------------------------
# Manufacturing PMI (S&P Global headline as the documented ISM proxy)

def classify_pmi(current: float, three_months_ago: float | None, params: dict) -> tuple[str, str]:
    if current < params["elevated_level"] and three_months_ago is not None and current < three_months_ago:
        return "elevated", (
            f"PMI of {current:.1f} is below {params['elevated_level']:.0f} and lower than "
            f"three months earlier ({three_months_ago:.1f})."
        )
    if current < params["watch_level"]:
        return "watch", f"PMI of {current:.1f} is below the {params['watch_level']:.0f} expansion line."
    return "benign", f"PMI of {current:.1f} is above the {params['watch_level']:.0f} expansion line."


def build_pmi(thresholds: dict) -> dict:
    params = thresholds["pmi_manufacturing_proxy"]
    scraped = scrape.fetch_spglobal_pmi()
    reference = scraped["reference_month"] or date.today().replace(day=1).isoformat()
    history_path = append_scrape_history(
        "pmi_spglobal_us_mfg.json",
        {
            "series_id": "SPGLOBAL_US_MFG_PMI",
            "name": "S&P Global US Manufacturing PMI (headline)",
            "unit": "index",
            "source_url": "https://www.pmi.spglobal.com/",
            "collection": "Accumulated from monthly public press headlines; no licensed history is redistributed.",
        },
        reference,
        scraped["value"],
    )
    # Trend input: the accumulated print three months before the reference
    # month, when available (month arithmetic via relativedelta).
    from util import load_json  # local import to avoid an unused symbol at module scope
    history = load_json(history_path) or {"points": []}
    target = (date.fromisoformat(reference) - relativedelta(months=3)).isoformat()
    three_months_ago = next((p["value"] for p in history["points"] if p["as_of"] == target), None)
    status, detail = classify_pmi(scraped["value"], three_months_ago, params)
    return {
        "id": "pmi_manufacturing_proxy",
        "name": "Manufacturing PMI",
        "qualifier": "S&P Global, ISM proxy",
        "lens": 1,
        "value": scraped["value"],
        "unit": "index",
        "signed": False,
        "decimals": 1,
        "cadence": "monthly",
        "as_of": reference,
        "status": status,
        "description": (
            "Purchasing managers' survey of US manufacturing; readings below 50 indicate "
            "contraction. The ISM headline is licensed, so the S&P Global US Manufacturing "
            "PMI headline is used as the documented free proxy."
        ),
        "threshold": (
            "Below {w:.0f} = watch. Below {e:.0f} and lower than three months earlier = elevated."
        ).format(w=params["watch_level"], e=params["elevated_level"]),
        "source_url": scraped["source_url"],
        "secondary_source_url": (
            "https://www.pmi.spglobal.com/Public/Release/PressReleases"
            if scraped["source_url"] == scrape.TRADINGECONOMICS_PMI_URL
            else "https://tradingeconomics.com/united-states/manufacturing-pmi"
        ),
        "notes": (
            f"{detail} Proxy substitution: ISM headline is licensed; the S&P Global headline "
            f"is a different survey that can diverge from ISM. {VERIFIED_NOTE}"
        ),
    }


# ---------------------------------------------------------------------------
# Leading indicators (Conference Board LEI public headline)

def classify_lei(six_month_pct: float | None, params: dict) -> tuple[str, str]:
    if six_month_pct is None:
        raise ValueError("LEI six-month change unavailable; refusing to classify without it")
    if six_month_pct <= params["elevated_six_month_pct"]:
        return "elevated", (
            f"The six-month change of {six_month_pct:+.1f}% is at or below the "
            f"{params['elevated_six_month_pct']:+.1f}% elevated line."
        )
    if six_month_pct < 0:
        return "watch", f"The six-month change of {six_month_pct:+.1f}% is negative."
    return "benign", f"The six-month change of {six_month_pct:+.1f}% is not negative."


def build_lei(thresholds: dict) -> dict:
    params = thresholds["leading_indicators"]
    scraped = scrape.fetch_conference_board_lei()
    status, detail = classify_lei(scraped["six_month_pct"], params)
    append_scrape_history(
        "lei_conference_board.json",
        {
            "series_id": "CB_US_LEI_HEADLINE",
            "name": "Conference Board US LEI (public headline)",
            "unit": "index",
            "source_url": scrape.CONFERENCE_BOARD_LEI_URL,
            "collection": "Accumulated from monthly public press headlines; no licensed history is redistributed.",
        },
        scraped["reference_month"],
        scraped["level"],
    )
    return {
        "id": "leading_indicators",
        "name": "Leading Economic Index",
        "qualifier": "Conference Board headline, 6-month trend",
        "lens": 1,
        "value": scraped["level"],
        "unit": "index",
        "signed": False,
        "decimals": 1,
        "cadence": "monthly",
        "as_of": scraped["reference_month"],
        "status": status,
        "description": (
            "Composite of ten forward-looking inputs built to turn down before the economy "
            "does. Status is driven by the six-month growth rate, not the monthly level."
        ),
        "threshold": (
            "Six-month change below zero = watch. At or below {e:+.1f}% over six months "
            "(about -4% annualised, aligned with the Conference Board's published "
            "recession-signal research) = elevated."
        ).format(e=params["elevated_six_month_pct"]),
        "source_url": scraped["source_url"],
        "secondary_source_url": "https://www.prnewswire.com/news/the-conference-board/",
        "notes": (
            f"{detail} Monthly change {scraped['mom_pct']:+.1f}%. Licence note: only the "
            f"publicly announced headline figures are displayed; no licensed series is "
            f"redistributed. {VERIFIED_NOTE}"
        ),
    }


# ---------------------------------------------------------------------------
# Labour market (unemployment, payrolls, internals)

def three_month_average_rise(values: list[float]) -> float:
    """Sahm-style rise: latest 3-month average minus its prior-12-month low."""
    if len(values) < 15:
        raise ValueError("Need at least 15 monthly observations")
    avg3 = [sum(values[i - 2 : i + 1]) / 3 for i in range(2, len(values))]
    return round(avg3[-1] - min(avg3[-13:-1]), 2)


def classify_labour(inputs: dict, params: dict) -> tuple[str, str]:
    rise = inputs["rise"]
    payroll = inputs["payroll_3mo_avg_thousands"]
    uemp_yoy = inputs["uemp27ov_yoy_pct"]
    ccsa_26wk = inputs["ccsa_26wk_pct"]

    internals_soft = (
        uemp_yoy is not None
        and ccsa_26wk is not None
        and uemp_yoy > params["watch_uemp27ov_yoy_pct"]
        and ccsa_26wk > params["watch_ccsa_26wk_pct"]
    )
    if rise >= params["elevated_rise"] or payroll < 0:
        return "elevated", (
            f"Unemployment rise of {rise:+.2f} pp or negative three-month average payroll "
            f"change ({payroll:+.0f}k) signals a turning labour market."
        )
    if rise >= params["watch_rise"] or payroll < params["watch_payroll_3mo_avg_thousands"] or internals_soft:
        reasons = []
        if rise >= params["watch_rise"]:
            reasons.append(f"unemployment rise {rise:+.2f} pp")
        if payroll < params["watch_payroll_3mo_avg_thousands"]:
            reasons.append(f"payroll 3-month average {payroll:+.0f}k")
        if internals_soft:
            reasons.append(
                f"internals softening (long-term unemployed {uemp_yoy:+.0f}% YoY, "
                f"continued claims {ccsa_26wk:+.1f}% over 26 weeks)"
            )
        return "watch", "Watch: " + "; ".join(reasons) + "."
    return "benign", (
        f"Headline and internals are steady: unemployment rise {rise:+.2f} pp, payroll "
        f"3-month average {payroll:+.0f}k, long-term unemployed "
        f"{uemp_yoy:+.0f}% YoY, continued claims {ccsa_26wk:+.1f}% over 26 weeks."
    )


def build_labour(thresholds: dict) -> dict:
    params = thresholds["labour_market"]
    unrate_dates, unrate_values = clean_series(*fetch_series("UNRATE"))
    payems_dates, payems_values = clean_series(*fetch_series("PAYEMS"))
    uemp_dates, uemp_values = clean_series(*fetch_series("UEMP27OV"))
    ccsa_dates, ccsa_values = clean_series(*fetch_series("CCSA"))

    write_fred_history("UNRATE", "Unemployment rate", "pct",
                       "https://fred.stlouisfed.org/series/UNRATE", unrate_dates, unrate_values)
    write_fred_history("PAYEMS", "Total nonfarm payrolls", "thousands",
                       "https://fred.stlouisfed.org/series/PAYEMS", payems_dates, payems_values)
    write_fred_history("UEMP27OV", "Unemployed 27 weeks and over", "thousands",
                       "https://fred.stlouisfed.org/series/UEMP27OV", uemp_dates, uemp_values)
    write_fred_history("CCSA", "Continued claims (SA)", "thousands",
                       "https://fred.stlouisfed.org/series/CCSA", ccsa_dates, ccsa_values)

    payroll_changes = [b - a for a, b in zip(payems_values[-4:-1], payems_values[-3:])]
    uemp_latest_date = date.fromisoformat(uemp_dates[-1])
    # Same month one year earlier, via relativedelta (months are 1-indexed).
    yoy_target = (uemp_latest_date - relativedelta(years=1)).isoformat()
    uemp_yoy_pct = None
    if yoy_target in uemp_dates:
        base = uemp_values[uemp_dates.index(yoy_target)]
        uemp_yoy_pct = round((uemp_values[-1] / base - 1.0) * 100.0, 1)
    ccsa_26wk_pct = (
        round((ccsa_values[-1] / ccsa_values[-27] - 1.0) * 100.0, 1) if len(ccsa_values) >= 27 else None
    )

    inputs = {
        "rise": three_month_average_rise(unrate_values),
        "payroll_3mo_avg_thousands": sum(payroll_changes) / len(payroll_changes),
        "uemp27ov_yoy_pct": uemp_yoy_pct,
        "ccsa_26wk_pct": ccsa_26wk_pct,
    }
    status, detail = classify_labour(inputs, params)
    return {
        "id": "labour_market",
        "name": "Labour Market",
        "qualifier": "unemployment / payrolls / internals",
        "lens": 1,
        "value": unrate_values[-1],
        "unit": "pct",
        "signed": False,
        "decimals": 1,
        "cadence": "monthly",
        "as_of": unrate_dates[-1],
        "status": status,
        "description": (
            "Unemployment rate and payroll momentum, checked against internals (long-term "
            "unemployed, continued claims). These confirm a downturn once underway; the "
            "trend matters more than the headline level."
        ),
        "threshold": (
            "Unemployment 3-month average at least {wr:.2f} pp above its 12-month low, payroll "
            "3-month average below {wp:.0f}k, or softening internals (long-term unemployed "
            "over {wu:.0f}% YoY and continued claims over {wc:.0f}% in 26 weeks) = watch. "
            "Rise at or above {er:.2f} pp or negative payroll 3-month average = elevated."
        ).format(
            wr=params["watch_rise"], wp=params["watch_payroll_3mo_avg_thousands"],
            wu=params["watch_uemp27ov_yoy_pct"], wc=params["watch_ccsa_26wk_pct"],
            er=params["elevated_rise"],
        ),
        "source_url": "https://fred.stlouisfed.org/series/UNRATE",
        "secondary_source_url": "https://www.bls.gov/news.release/empsit.nr0.htm",
        "notes": (
            f"{detail} Inputs: UNRATE, PAYEMS, UEMP27OV (BLS), CCSA (DOL), all via FRED and "
            f"cross-checked at the originating agencies. {VERIFIED_NOTE}"
        ),
    }


# ---------------------------------------------------------------------------
# Valuation (Shiller CAPE) — context only, never a lens trigger

def build_cape(thresholds: dict) -> dict:
    params = thresholds["shiller_cape"]
    scraped = scrape.fetch_multpl_cape()
    as_of = scraped["as_of"]
    as_of_note = ""
    if as_of is None:
        as_of = utc_now_iso()[:10]
        as_of_note = " As-of date approximated to the run date (multpl timestamp not parsed)."
    flag_note = ""
    if scraped["value"] >= params["flag_level"]:
        mean_text = f" (multpl long-run mean {scraped['mean']:.2f}, median {scraped['median']:.2f})" \
            if scraped["mean"] and scraped["median"] else ""
        flag_note = (
            f" The reading is far above long-run norms{mean_text}, which historically maps to "
            f"weak decade-ahead returns — a caveat on future returns, not a recession timer."
        )
    append_scrape_history(
        "shiller_cape_multpl.json",
        {
            "series_id": "MULTPL_SHILLER_CAPE",
            "name": "Shiller CAPE (multpl daily print)",
            "unit": "ratio",
            "source_url": scrape.MULTPL_CAPE_URL,
            "collection": "Accumulated from multpl.com daily prints (latest-price basis).",
        },
        as_of,
        scraped["value"],
    )
    return {
        "id": "shiller_cape",
        "name": "Valuation",
        "qualifier": "Shiller CAPE",
        "lens": 1,
        "value": scraped["value"],
        "unit": "ratio",
        "signed": False,
        "decimals": 2,
        "cadence": "daily",
        "as_of": as_of,
        "status": "context",
        "description": (
            "Price divided by the ten-year average of inflation-adjusted earnings. A high "
            "reading means an expensive market and weak long-run return expectations — it "
            "does not time tops, and markets can stay expensive for years."
        ),
        "threshold": (
            "Context only — never a timing trigger. Flagged when above {f:.0f} as a long-run "
            "return caveat."
        ).format(f=params["flag_level"]),
        "source_url": scrape.MULTPL_CAPE_URL,
        "secondary_source_url": "https://www.gurufocus.com/economic_indicators/56/sp-500-shiller-cape-ratio",
        "notes": (
            "Method note: multpl prints a daily CAPE on the latest price with lagged earnings; "
            "the Shiller dataset and GuruFocus use monthly average prices, so monthly prints sit "
            "slightly below the daily figure in a rising market. Cross-checked within tolerance "
            f"at first use; see VERIFICATION.md.{flag_note}{as_of_note}"
        ),
    }


# ---------------------------------------------------------------------------
# Registry (imported by scripts/update_data.py)

GROUPS: dict[str, list] = {
    "daily": [build_yield_curve, build_hy_oas, build_labour],
    "monthly": [build_sahm, build_pmi, build_lei, build_cape],
    "quarterly": [],
}
