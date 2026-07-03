"""Lens 2 (market-peak froth) — classifiers, builders, and the composite.

Each gauge is triggered / quiet / eased; the composite is the share of
in-composite gauges triggered. The alarm level is deliberately unset until
ZH picks one (SPEC.md section 5 — do not default to 80%); until then the
combined read treats Lens 2 as not firing. The SLOOS row is a froth-off
context read and sits outside the composite. The inverted yield curve is
excluded entirely — it already lives in Lens 1 (SPEC.md section 5 note).

Trigger levels are calibrated from each series' own full history where a
free history exists (AAII spread deciles, multpl P/E percentiles, NFCI
percentiles, Rule-of-20 sum percentiles) and from documented absolute
conventions otherwise. All parameters live in data/thresholds.json as
independently chosen defaults pending confirmation.

Date handling: Python datetime months are 1-indexed; month arithmetic uses
dateutil.relativedelta only.
"""
from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from sources import sentiment
from sources.fred import fetch_series
from sources.sentiment import percentile_rank
from util import (
    append_scrape_history,
    percentile,
    clean_series,
    latest_observation,
    utc_now_iso,
    write_fred_history,
)

VERIFIED_NOTE = "Series identity verified against two sources (VERIFICATION.md)."


# ---------------------------------------------------------------------------
# Pure classifiers (tested in tests/test_lens2.py)

def classify_confidence(percentile: float, params: dict) -> tuple[str, str]:
    if percentile >= params["trigger_percentile"]:
        return "triggered", (
            f"Sentiment sits at the {percentile:.0f}th percentile of its full history — "
            f"the household optimism typical of market tops."
        )
    return "quiet", (
        f"Sentiment sits at the {percentile:.0f}th percentile of its full history — "
        f"nowhere near the optimism seen at tops."
    )


def classify_aaii(spread_pp: float, p90_pp: float, params: dict) -> tuple[str, str]:
    if spread_pp >= p90_pp:
        return "triggered", (
            f"The bull-bear spread of {spread_pp:+.1f} pp is in the top decile of the "
            f"full weekly history (decile line {p90_pp:+.1f} pp)."
        )
    if spread_pp < params["eased_below_pp"]:
        return "eased", (
            f"Bears outnumber bulls (spread {spread_pp:+.1f} pp) — retail euphoria is off."
        )
    return "quiet", (
        f"The bull-bear spread of {spread_pp:+.1f} pp is below the top-decile line "
        f"({p90_pp:+.1f} pp)."
    )


def classify_naaim(exposure: float, params: dict) -> tuple[str, str]:
    if exposure >= params["trigger_level"]:
        return "triggered", (
            f"Active managers report {exposure:.0f}% average equity exposure — "
            f"effectively all-in, with little cash left to add."
        )
    return "quiet", (
        f"Active managers report {exposure:.0f}% average equity exposure, below the "
        f"{params['trigger_level']:.0f} all-in line."
    )


def classify_pe(percentile: float, params: dict) -> tuple[str, str]:
    if percentile >= params["trigger_percentile"]:
        return "triggered", (
            f"The trailing multiple sits at the {percentile:.0f}th percentile of monthly "
            f"history since 1871 — a lot of optimism is already priced."
        )
    return "quiet", (
        f"The trailing multiple sits at the {percentile:.0f}th percentile of monthly "
        f"history since 1871."
    )


def classify_rule_of_20(total: float, percentile: float, params: dict) -> tuple[str, str]:
    if total > params["fair_value_sum"] and percentile >= params["trigger_percentile"]:
        return "triggered", (
            f"P/E plus inflation totals {total:.1f}, well above the {params['fair_value_sum']:.0f} "
            f"fair-value line and at the {percentile:.0f}th percentile of history since 1948."
        )
    if total > params["fair_value_sum"]:
        return "quiet", (
            f"P/E plus inflation totals {total:.1f}, above {params['fair_value_sum']:.0f} but not "
            f"in the historical extreme tail ({percentile:.0f}th percentile)."
        )
    return "quiet", (
        f"P/E plus inflation totals {total:.1f}, at or below the "
        f"{params['fair_value_sum']:.0f} fair-value line."
    )


def classify_value_growth(spread_6m_pp: float, params: dict) -> tuple[str, str]:
    if spread_6m_pp >= params["trigger_pp"]:
        return "triggered", (
            f"Growth leads value by {spread_6m_pp:+.1f} pp over six months — the crowding "
            f"pattern of froth-on leadership."
        )
    if spread_6m_pp < params["eased_below_pp"]:
        return "eased", (
            f"Value leads growth over six months ({spread_6m_pp:+.1f} pp) — froth "
            f"leadership has switched off."
        )
    return "quiet", (
        f"Growth leads value by {spread_6m_pp:+.1f} pp over six months, below the "
        f"{params['trigger_pp']:.0f} pp froth line."
    )


def classify_nfci(value: float, loose_percentile: float, params: dict) -> tuple[str, str]:
    if loose_percentile <= params["trigger_percentile"]:
        return "triggered", (
            f"Financial conditions ({value:+.2f}) are looser than "
            f"{100 - loose_percentile:.0f}% of readings since 1971 — complacency, "
            f"not safety."
        )
    return "quiet", (
        f"Financial conditions ({value:+.2f}) sit at the {loose_percentile:.0f}th "
        f"loosest percentile since 1971, outside the complacent tail."
    )


def classify_ipo(annualised: float, prior_years: list[float], params: dict) -> tuple[str, str]:
    percentile = percentile_rank(prior_years, annualised)
    if percentile >= params["trigger_percentile"]:
        return "triggered", (
            f"Annualised issuance pace ranks at the {percentile:.0f}th percentile of the "
            f"prior years available — deal-making at cycle highs."
        )
    return "quiet", (
        f"Annualised issuance pace ranks at the {percentile:.0f}th percentile of the "
        f"prior years available."
    )


def summarise(indicators: list[dict], alarm_share_pct: float | None) -> dict:
    """Composite block: share of in-composite gauges triggered."""
    gauges = [i for i in indicators if i.get("in_composite")]
    triggered = sum(1 for i in gauges if i["status"] == "triggered")
    eased = sum(1 for i in gauges if i["status"] == "eased")
    share = round(100.0 * triggered / len(gauges), 1) if gauges else 0.0
    if alarm_share_pct is None:
        alarm_state = "pending"
    else:
        alarm_state = "at_or_above" if share >= alarm_share_pct else "below"
    return {
        "gauge_count": len(gauges),
        "triggered_count": triggered,
        "eased_count": eased,
        "share_pct": share,
        "alarm_share_pct": alarm_share_pct,
        "alarm_state": alarm_state,
    }


# ---------------------------------------------------------------------------
# Builders

def build_consumer_confidence(thresholds: dict) -> dict:
    params = thresholds["consumer_confidence_proxy"]
    dates, values = clean_series(*fetch_series("UMCSENT"))
    write_fred_history("UMCSENT", "University of Michigan consumer sentiment", "index",
                       "https://fred.stlouisfed.org/series/UMCSENT", dates, values)
    pct_rank = percentile_rank(values, values[-1])
    status, detail = classify_confidence(pct_rank, params)
    return {
        "id": "consumer_confidence_proxy",
        "chart_line": {
            "value": round(percentile(values, params["trigger_percentile"]), 1),
            "label": "current trigger (75th percentile of history)",
        },
        "name": "Consumer Confidence",
        "qualifier": "Michigan sentiment, proxy",
        "lens": 2,
        "in_composite": True,
        "value": values[-1],
        "unit": "index",
        "signed": False,
        "decimals": 1,
        "cadence": "monthly",
        "as_of": dates[-1],
        "status": status,
        "description": (
            "Household optimism, which runs hot near market tops. The Conference Board "
            "index is licensed, so the University of Michigan sentiment index is the "
            "documented free proxy."
        ),
        "threshold": (
            "Triggered at or above the {p:.0f}th percentile of the full monthly history."
        ).format(p=params["trigger_percentile"]),
        "source_url": "https://fred.stlouisfed.org/series/UMCSENT",
        "secondary_source_url": "http://www.sca.isr.umich.edu/",
        "notes": (
            f"{detail} Proxy substitution: the Conference Board confidence index is licensed; "
            f"Michigan sentiment is a different survey that can diverge from it. {VERIFIED_NOTE}"
        ),
    }


def build_aaii(thresholds: dict) -> dict:
    params = thresholds["retail_euphoria_aaii"]
    survey = sentiment.fetch_aaii()
    status, detail = classify_aaii(survey["spread_pp"], survey["spread_p90_pp"], params)
    append_scrape_history(
        "aaii_spread.json",
        {
            "series_id": "AAII_BULL_BEAR_SPREAD",
            "name": "AAII bull-bear spread (weekly)",
            "unit": "pp",
            "source_url": sentiment.AAII_XLS_URL,
            "collection": (
                "Current week only; the full AAII workbook is used in-memory to calibrate "
                "the decile line and is not redistributed (AAII terms of service)."
            ),
        },
        survey["week_ending"],
        survey["spread_pp"],
    )
    return {
        "id": "retail_euphoria_aaii",
        "chart_line": {
            "value": survey["spread_p90_pp"],
            "label": "top-decile line (full weekly history)",
        },
        "name": "Retail Euphoria",
        "qualifier": "AAII bull-bear survey",
        "lens": 2,
        "in_composite": True,
        "value": survey["spread_pp"],
        "unit": "pp",
        "signed": True,
        "decimals": 1,
        "cadence": "weekly",
        "as_of": survey["week_ending"],
        "status": status,
        "description": (
            "Share of individual investors bullish minus bearish in the weekly AAII survey. "
            "Extreme bullishness is a contrarian warning — when everyone is optimistic, the "
            "buyers are already in."
        ),
        "threshold": (
            "Triggered when the spread reaches the top decile of the full weekly history "
            "(currently {p:+.1f} pp); eased when bears outnumber bulls."
        ).format(p=survey["spread_p90_pp"]),
        "source_url": "https://www.aaii.com/sentimentsurvey",
        "secondary_source_url": sentiment.AAII_XLS_URL,
        "notes": (
            f"{detail} This week: bulls {survey['bullish_pct']:.1f}%, bears "
            f"{survey['bearish_pct']:.1f}%; spread percentile {survey['spread_percentile']:.0f} "
            f"across {survey['history_weeks']:,} weeks since 1987. {VERIFIED_NOTE}"
        ),
    }


def build_naaim(thresholds: dict) -> dict:
    params = thresholds["manager_bullishness_naaim"]
    reading = sentiment.fetch_naaim()
    status, detail = classify_naaim(reading["exposure"], params)
    as_of = reading["as_of"] or utc_now_iso()[:10]
    as_of_note = "" if reading["as_of"] else (
        " As-of stamped at collection time; NAAIM posts the number weekly without a "
        "machine-readable date."
    )
    append_scrape_history(
        "naaim_exposure.json",
        {
            "series_id": "NAAIM_EXPOSURE",
            "name": "NAAIM Exposure Index (weekly)",
            "unit": "index",
            "source_url": sentiment.NAAIM_URL,
            "collection": "Accumulated from the weekly public headline; no licensed history is redistributed.",
        },
        as_of,
        reading["exposure"],
    )
    return {
        "id": "manager_bullishness_naaim",
        "name": "Manager Bullishness",
        "qualifier": "NAAIM exposure",
        "lens": 2,
        "in_composite": True,
        "value": reading["exposure"],
        "unit": "index",
        "signed": False,
        "decimals": 2,
        "cadence": "weekly",
        "as_of": as_of,
        "status": status,
        "description": (
            "Active money managers' reported average equity exposure on a 0-200 scale. "
            "Near 100 means managers are all-in with little cash left to deploy — "
            "crowded positioning."
        ),
        "threshold": "Triggered at or above {t:.0f} (all-in positioning).".format(
            t=params["trigger_level"]
        ),
        "source_url": sentiment.NAAIM_URL,
        "secondary_source_url": "https://naaim.org/",
        "notes": f"{detail}{as_of_note} {VERIFIED_NOTE}",
    }


def build_pe(thresholds: dict) -> dict:
    params = thresholds["growth_expectation_pe"]
    current = sentiment.fetch_multpl_pe()["value"]
    dates, values, estimates = sentiment.fetch_multpl_pe_history()
    pct_rank = percentile_rank(values, current)
    status, detail = classify_pe(pct_rank, params)
    chart_line = {
        "value": round(percentile(values, params["trigger_percentile"]), 2),
        "label": "current trigger (90th percentile since 1871)",
    }
    # Full monthly history for the chart. The trailing P/E is a valuation
    # ratio derived from long-public S&P price and earnings data (the same
    # Shiller-lineage series the CAPE draws on), so the monthly series is
    # public and may be charted — unlike the survey-provider gauges.
    # series_id lower-cases to the history filename referenced by the UI
    # (data/history/multpl_pe.json), so keep it aligned with HISTORY_MAP.
    write_fred_history("MULTPL_PE", "S&P 500 trailing P/E (monthly)", "ratio",
                       sentiment.MULTPL_PE_URL, dates, values)
    estimate_note = (
        " Recent months in the calibration history are multpl estimates pending final "
        "earnings (marked on their table)." if estimates[-1] else ""
    )
    return {
        "id": "growth_expectation_pe",
        "chart_line": chart_line,
        "name": "Growth-Expectation Froth",
        "qualifier": "trailing P/E percentile, proxy",
        "lens": 2,
        "in_composite": True,
        "value": current,
        "unit": "ratio",
        "signed": False,
        "decimals": 2,
        "cadence": "daily",
        "as_of": utc_now_iso()[:10],
        "status": status,
        "description": (
            "How many dollars investors pay per dollar of earnings. A high historical "
            "percentile means optimism is already priced. Forward P/E needs a vendor feed, "
            "so the trailing multiple from multpl is the documented free proxy."
        ),
        "threshold": (
            "Triggered at or above the {p:.0f}th percentile of monthly history since 1871."
        ).format(p=params["trigger_percentile"]),
        "source_url": sentiment.MULTPL_PE_URL,
        "secondary_source_url": sentiment.MULTPL_PE_TABLE_URL,
        "notes": (
            f"{detail} Proxy substitution: trailing, not forward, earnings.{estimate_note} "
            f"{VERIFIED_NOTE}"
        ),
    }


def build_rule_of_20(thresholds: dict) -> dict:
    params = thresholds["rule_of_20"]
    pe_current = sentiment.fetch_multpl_pe()["value"]
    pe_dates, pe_values, _ = sentiment.fetch_multpl_pe_history()
    cpi_dates, cpi_values = clean_series(*fetch_series("CPIAUCSL"))
    write_fred_history("CPIAUCSL", "CPI (all urban consumers, SA)", "index",
                       "https://fred.stlouisfed.org/series/CPIAUCSL", cpi_dates, cpi_values)

    cpi_by_date = dict(zip(cpi_dates, cpi_values))

    def cpi_yoy(iso_month: str) -> float | None:
        # Same month one year earlier via relativedelta (months 1-indexed).
        base_month = (date.fromisoformat(iso_month) - relativedelta(years=1)).isoformat()
        if iso_month in cpi_by_date and base_month in cpi_by_date:
            return (cpi_by_date[iso_month] / cpi_by_date[base_month] - 1.0) * 100.0
        return None

    # Monthly Rule-of-20 sums where both inputs exist (CPI YoY available from 1948).
    pe_by_month = {d[:8] + "01": v for d, v in zip(pe_dates, pe_values)}
    sums = []
    for iso_month, pe in pe_by_month.items():
        yoy = cpi_yoy(iso_month)
        if yoy is not None:
            sums.append(pe + yoy)
    latest_yoy = cpi_yoy(cpi_dates[-1])
    if latest_yoy is None:
        raise ValueError("CPI year-on-year change unavailable for the latest month")
    total = pe_current + latest_yoy
    percentile = percentile_rank(sums, total)
    status, detail = classify_rule_of_20(total, percentile, params)
    return {
        "id": "rule_of_20",
        "name": "Rule of 20",
        "qualifier": "P/E + CPI inflation",
        "lens": 2,
        "in_composite": True,
        "value": round(total, 1),
        "unit": "index",
        "signed": False,
        "decimals": 1,
        "cadence": "monthly",
        "as_of": cpi_dates[-1],
        "status": status,
        "description": (
            "Trailing P/E plus year-on-year CPI inflation. The old rule of thumb calls 20 "
            "fair value; readings far above it mark expensive markets, especially when "
            "inflation is not the driver."
        ),
        "threshold": (
            "Triggered above {f:.0f} and at or above the {p:.0f}th percentile of monthly "
            "history since 1948."
        ).format(f=params["fair_value_sum"], p=params["trigger_percentile"]),
        "source_url": sentiment.MULTPL_PE_URL,
        "secondary_source_url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "notes": (
            f"{detail} Inputs: trailing P/E {pe_current:.2f} (multpl), CPI "
            f"{latest_yoy:+.1f}% YoY (FRED CPIAUCSL, cross-checked at the BLS API). "
            f"{VERIFIED_NOTE}"
        ),
    }


def build_value_growth(thresholds: dict) -> dict:
    from sources.prices import fetch_yahoo_daily

    params = thresholds["value_vs_growth"]
    sessions = params["window_trading_days"]
    rpg_dates, rpg = fetch_yahoo_daily("RPG", period1=0)
    rpv_dates, rpv = fetch_yahoo_daily("RPV", period1=0)
    common = sorted(set(rpg_dates) & set(rpv_dates))
    if len(common) < sessions + 1:
        raise ValueError("Insufficient overlapping RPG/RPV history for the window")
    rpg_by, rpv_by = dict(zip(rpg_dates, rpg)), dict(zip(rpv_dates, rpv))
    last, past = common[-1], common[-1 - sessions]
    growth_return = (rpg_by[last] / rpg_by[past] - 1.0) * 100.0
    value_return = (rpv_by[last] / rpv_by[past] - 1.0) * 100.0
    spread = round(growth_return - value_return, 1)
    status, detail = classify_value_growth(spread, params)
    # Full rolling-spread history for the chart, computed from RPG/RPV daily
    # closes (Yahoo prices — chartable). One point per session once the
    # six-month window is available.
    spread_dates, spread_values = [], []
    for i in range(sessions, len(common)):
        d, base = common[i], common[i - sessions]
        g = (rpg_by[d] / rpg_by[base] - 1.0) * 100.0
        v = (rpv_by[d] / rpv_by[base] - 1.0) * 100.0
        spread_dates.append(d)
        spread_values.append(round(g - v, 2))
    # series_id lower-cases to the history filename (data/history/rpg_rpv_spread.json).
    write_fred_history("RPG_RPV_SPREAD", "Growth minus value, six-month price-return spread", "pp",
                       "https://finance.yahoo.com/quote/RPG/", spread_dates, spread_values)
    return {
        "id": "value_vs_growth",
        "name": "Value vs Growth",
        "qualifier": "RPG minus RPV, 6 months",
        "lens": 2,
        "in_composite": True,
        "value": spread,
        "unit": "pp",
        "signed": True,
        "decimals": 1,
        "cadence": "daily",
        "as_of": last,
        "status": status,
        "description": (
            "Six-month price-return gap between S&P 500 pure growth (RPG) and pure value "
            "(RPV). Sustained growth leadership marks froth-on speculation; value "
            "leadership eases it."
        ),
        "threshold": (
            "Triggered when growth leads by {t:.0f} pp or more over {n} trading sessions "
            "(about six months); eased when value leads."
        ).format(t=params["trigger_pp"], n=sessions),
        "source_url": "https://finance.yahoo.com/quote/RPG/",
        "secondary_source_url": "https://stockanalysis.com/etf/rpg/",
        "notes": (
            f"{detail} Price returns, not total returns: RPV distributes a materially higher "
            f"yield, so the spread slightly flatters growth (well inside the trigger margin). "
            f"{VERIFIED_NOTE}"
        ),
    }


def build_nfci(thresholds: dict) -> dict:
    params = thresholds["credit_complacency_nfci"]
    dates, values = clean_series(*fetch_series("NFCI"))
    write_fred_history("NFCI", "Chicago Fed National Financial Conditions Index", "index",
                       "https://fred.stlouisfed.org/series/NFCI", dates, values)
    loose_percentile = percentile_rank(values, values[-1])
    status, detail = classify_nfci(values[-1], loose_percentile, params)
    return {
        "id": "credit_complacency_nfci",
        "chart_line": {
            "value": round(percentile(values, params["trigger_percentile"]), 3),
            "label": "complacent tail (loosest quintile since 1971)",
        },
        "name": "Credit Complacency",
        "qualifier": "Chicago Fed NFCI",
        "lens": 2,
        "in_composite": True,
        "value": values[-1],
        "unit": "index",
        "signed": True,
        "decimals": 2,
        "cadence": "weekly",
        "as_of": dates[-1],
        "status": status,
        "description": (
            "The Chicago Fed's weekly composite of financial conditions; negative is looser "
            "than average. Deeply loose conditions signal complacent risk appetite — the "
            "fuel of late-cycle froth."
        ),
        "threshold": (
            "Triggered when conditions are in the loosest {p:.0f}% of weekly readings "
            "since 1971."
        ).format(p=params["trigger_percentile"]),
        "source_url": "https://fred.stlouisfed.org/series/NFCI",
        "secondary_source_url": "https://www.chicagofed.org/research/data/nfci/current-data",
        "notes": f"{detail} {VERIFIED_NOTE}",
    }


def build_ipo(thresholds: dict) -> dict:
    params = thresholds["deal_ipo_froth"]
    stats = sentiment.fetch_renaissance_ipo_stats()
    current_year = stats["current_year"]
    months = stats["months_elapsed"]
    # Annualisation is a crude 12/months scale-up of the year-to-date pace;
    # issuance is seasonal, so this is an approximation and is labelled as
    # such (months are 1-indexed via the date library).
    annualised = stats["ytd_proceeds_bn"] * 12.0 / months
    prior = [stats["annual_proceeds_bn"][y] for y in sorted(stats["annual_proceeds_bn"]) if y < current_year]
    status, detail = classify_ipo(annualised, prior, params)
    # Annual proceeds history for the chart (Renaissance publishes the annual
    # series; public). Completed years are dated at year-end; the current
    # year is its year-to-date point, flagged in the note.
    ipo_dates, ipo_values = [], []
    for year in sorted(stats["annual_proceeds_bn"]):
        if year == current_year:
            ipo_dates.append(stats["as_of"])
            ipo_values.append(stats["ytd_proceeds_bn"])
        else:
            ipo_dates.append(f"{year}-12-31")
            ipo_values.append(stats["annual_proceeds_bn"][year])
    write_fred_history("RENAISSANCE_IPO_PROCEEDS", "US IPO proceeds by year (Renaissance Capital)",
                       "usd_bn", sentiment.RENAISSANCE_STATS_URL, ipo_dates, ipo_values)
    return {
        "id": "deal_ipo_froth",
        "name": "Deal & IPO Froth",
        "qualifier": "US IPO proceeds, proxy",
        "lens": 2,
        "in_composite": True,
        "value": stats["ytd_proceeds_bn"],
        "unit": "usd_bn",
        "signed": False,
        "decimals": 1,
        "cadence": "monthly",
        "as_of": stats["as_of"],
        "status": status,
        "description": (
            "New-listing volume clusters at tops, when cheap financing and high confidence "
            "embolden dealmakers. US IPO proceeds from Renaissance Capital serve as the "
            "documented free proxy for broader issuance."
        ),
        "threshold": (
            "Triggered when the annualised year-to-date proceeds pace reaches the "
            "{p:.0f}th percentile of the prior years available (from {y})."
        ).format(p=params["trigger_percentile"], y=min(stats["annual_proceeds_bn"])),
        "source_url": sentiment.RENAISSANCE_STATS_URL,
        "secondary_source_url": "https://stockanalysis.com/ipos/statistics/",
        "notes": (
            f"{detail} Year to date: ${stats['ytd_proceeds_bn']:.1f}bn across {months} months "
            f"({stats['ytd_count']} IPOs); annualised ${annualised:.0f}bn. Chart shows full-year "
            f"proceeds with the current year as a year-to-date point. History window is short "
            f"({len(prior)} prior years) — a coarse gauge, flagged per SPEC. {VERIFIED_NOTE}"
        ),
    }


def build_sloos(thresholds: dict) -> dict:
    dates, values = clean_series(*fetch_series("DRTSCILM"))
    write_fred_history("DRTSCILM", "SLOOS: net share of banks tightening C&I standards", "pct",
                       "https://fred.stlouisfed.org/series/DRTSCILM", dates, values)
    latest = values[-1]
    if latest > 0:
        detail = (
            f"A net {latest:+.1f}% of banks are tightening standards for large and "
            f"mid-sized firms — froth-off pressure building in credit supply."
        )
    else:
        detail = (
            f"A net {latest:+.1f}% of banks report easing standards — no tightening "
            f"pressure from bank credit."
        )
    return {
        "id": "sloos_tightening",
        "name": "Tightening Credit",
        "qualifier": "Fed SLOOS, C&I standards",
        "lens": 2,
        "in_composite": False,
        "value": latest,
        "unit": "pct",
        "signed": True,
        "decimals": 1,
        "cadence": "quarterly",
        "as_of": dates[-1],
        "status": "context",
        "description": (
            "Net share of banks tightening commercial-loan standards in the Fed's quarterly "
            "Senior Loan Officer Survey. A froth-off read: tightening credit withdraws the "
            "fuel. Context only — it does not feed the composite."
        ),
        "threshold": "Context row — net tightening (above zero) is a froth-off pressure note.",
        "source_url": "https://fred.stlouisfed.org/series/DRTSCILM",
        "secondary_source_url": "https://www.federalreserve.gov/data/sloos.htm",
        "notes": f"{detail} {VERIFIED_NOTE}",
    }


GROUPS: dict[str, list] = {
    "daily": [build_aaii, build_naaim, build_value_growth, build_nfci],
    "monthly": [build_consumer_confidence, build_pe, build_rule_of_20, build_ipo],
    "quarterly": [build_sloos],
}
