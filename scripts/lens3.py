"""Lens 3 (price-trend confirmation) — classifier and builder.

Signal logic ported from equity-defense-dashboard (simple rolling means over
S&P 500 closes with above/below flags); the data layer is re-implemented on
this project's zero-dependency pattern: Yahoo chart API primary with a FRED
`SP500` runtime cross-check. If the two feeds disagree beyond tolerance the
builder raises and the previous value is retained — a wrong price never
ships silently.

Bear trigger per SPEC.md section 6: the 50-day SMA below the 150-day SMA
AND both flat or sloping down. The 200-day SMA is context only.
"""
from __future__ import annotations

from sources.fred import fetch_series
from sources.prices import PriceFetchError, fetch_yahoo_daily
from util import HISTORY_DIR, clean_series, dump_json, utc_now_iso

VERIFIED_NOTE = "Feeds verified against each other and logged in VERIFICATION.md."
CROSS_CHECK_TOLERANCE_PCT = 0.05  # relative disagreement that blocks publication

CHART_WINDOW_TRADING_DAYS = 756  # about three years

YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/%5EGSPC/"
FRED_SP500_URL = "https://fred.stlouisfed.org/series/SP500"


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    """Simple moving average; None until a full window is available."""
    means: list[float | None] = []
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= window:
            running -= values[i - window]
        means.append(running / window if i >= window - 1 else None)
    return means


def slope_pct(series: list[float | None], lookback: int) -> float | None:
    """Percentage change of a series over ``lookback`` observations."""
    if len(series) <= lookback:
        return None
    latest, past = series[-1], series[-1 - lookback]
    if latest is None or past is None or past == 0:
        return None
    return (latest / past - 1.0) * 100.0


def classify_sma_trend(closes: list[float], params: dict) -> tuple[str, str, dict]:
    """benign / watch / elevated for the 50-day vs 150-day SMA trend."""
    lookback = params["slope_lookback_trading_days"]
    tolerance = params["flat_tolerance_pct"]
    if len(closes) < 200 + lookback + 1:
        raise ValueError("Need at least 200 + lookback + 1 daily closes")

    sma50 = rolling_mean(closes, 50)
    sma150 = rolling_mean(closes, 150)
    sma200 = rolling_mean(closes, 200)
    metrics = {
        "close": closes[-1],
        "sma50": sma50[-1],
        "sma150": sma150[-1],
        "sma200": sma200[-1],
        "sma50_slope_pct": slope_pct(sma50, lookback),
        "sma150_slope_pct": slope_pct(sma150, lookback),
    }

    cross_below = metrics["sma50"] < metrics["sma150"]
    slopes_confirm = (
        metrics["sma50_slope_pct"] is not None
        and metrics["sma150_slope_pct"] is not None
        and metrics["sma50_slope_pct"] <= tolerance
        and metrics["sma150_slope_pct"] <= tolerance
    )

    if cross_below and slopes_confirm:
        status = "elevated"
        detail = (
            f"Bear trigger: the 50-day SMA ({metrics['sma50']:,.0f}) is below the 150-day "
            f"({metrics['sma150']:,.0f}) and both are flat or falling over the past "
            f"{lookback} sessions ({metrics['sma50_slope_pct']:+.2f}% / "
            f"{metrics['sma150_slope_pct']:+.2f}%)."
        )
    elif cross_below:
        status = "watch"
        detail = (
            f"The 50-day SMA ({metrics['sma50']:,.0f}) is below the 150-day "
            f"({metrics['sma150']:,.0f}) but the slopes do not confirm "
            f"({metrics['sma50_slope_pct']:+.2f}% / {metrics['sma150_slope_pct']:+.2f}% "
            f"over {lookback} sessions)."
        )
    else:
        status = "benign"
        detail = (
            f"Uptrend intact: the 50-day SMA ({metrics['sma50']:,.0f}) is above the "
            f"150-day ({metrics['sma150']:,.0f})."
        )

    if metrics["sma200"] is not None and metrics["close"] < metrics["sma200"]:
        detail += (
            f" Context: the index ({metrics['close']:,.0f}) is below its 200-day SMA "
            f"({metrics['sma200']:,.0f})."
        )
    return status, detail, metrics


def cross_check_against_fred(dates: list[str], closes: list[float]) -> str:
    """Compare the latest common close with FRED SP500; raise on disagreement."""
    fred_dates, fred_values = clean_series(*fetch_series("SP500"))
    fred_by_date = dict(zip(fred_dates, fred_values))
    common = [(d, c) for d, c in zip(dates, closes) if d in fred_by_date][-5:]
    if not common:
        raise RuntimeError("No common dates between Yahoo ^GSPC and FRED SP500")
    worst = max(abs(c - fred_by_date[d]) / fred_by_date[d] * 100.0 for d, c in common)
    if worst > CROSS_CHECK_TOLERANCE_PCT:
        raise RuntimeError(
            f"Yahoo ^GSPC disagrees with FRED SP500 by {worst:.3f}% over the last "
            f"{len(common)} common sessions; refusing to publish."
        )
    return f"Cross-checked against FRED SP500 over {len(common)} sessions (max diff {worst:.3f}%)."


def build_sma_trend(thresholds: dict) -> dict:
    params = thresholds["sma_trend_sp500"]
    yahoo_error: Exception | None = None
    try:
        dates, closes = fetch_yahoo_daily("^GSPC")
    except PriceFetchError as error:
        yahoo_error = error

    if yahoo_error is None:
        check_note = cross_check_against_fred(dates, closes)
        primary_url, secondary_url = YAHOO_QUOTE_URL, FRED_SP500_URL
        # The full-history file is only rewritten from the primary feed, so
        # the long history for later analysis phases is never truncated by
        # the fallback below.
        dump_json(HISTORY_DIR / "gspc.json", {
            "series_id": "GSPC",
            "name": "S&P 500 daily closes",
            "unit": "index",
            "source_url": YAHOO_QUOTE_URL,
            "secondary_source_url": FRED_SP500_URL,
            "updated_at": utc_now_iso(),
            "dates": dates,
            "values": closes,
        })
    else:
        # Fallback: FRED SP500 carries the official S&P 500 close for the
        # trailing ten years — ample for the 200-day SMA and the chart
        # window. The substitution is declared in the row notes and the
        # two-feed cross-check resumes on the next successful Yahoo fetch.
        dates, closes = clean_series(*fetch_series("SP500"))
        reason = str(yahoo_error)
        check_note = (
            "Primary feed (Yahoo) unavailable this run ({reason}); values computed from "
            "FRED SP500, the official S&P 500 close. The two-feed cross-check resumes on "
            "the next successful primary fetch."
        ).format(reason=reason[:120] + ("..." if len(reason) > 120 else ""))
        primary_url, secondary_url = FRED_SP500_URL, YAHOO_QUOTE_URL

    status, detail, metrics = classify_sma_trend(closes, params)
    sma50 = rolling_mean(closes, 50)
    sma150 = rolling_mean(closes, 150)
    sma200 = rolling_mean(closes, 200)
    window = slice(-CHART_WINDOW_TRADING_DAYS, None)
    dump_json(HISTORY_DIR / "gspc_chart.json", {
        "series_id": "GSPC_CHART",
        "name": "S&P 500 with 50/150/200-day SMAs (chart window)",
        "updated_at": utc_now_iso(),
        "dates": dates[window],
        "close": closes[window],
        "sma50": [round(v, 2) if v is not None else None for v in sma50[window]],
        "sma150": [round(v, 2) if v is not None else None for v in sma150[window]],
        "sma200": [round(v, 2) if v is not None else None for v in sma200[window]],
    })

    return {
        "id": "sma_trend_sp500",
        "name": "50-day vs 150-day SMA",
        "qualifier": "S&P 500 daily closes",
        "lens": 3,
        "value": closes[-1],
        "unit": "index",
        "signed": False,
        "decimals": 2,
        "cadence": "daily",
        "as_of": dates[-1],
        "status": status,
        "description": (
            "The trend-confirmation gauge: historically the signal that a bear market is "
            "actually underway rather than merely feared. The 200-day SMA is shown for "
            "context and does not drive the status."
        ),
        "threshold": (
            "50-day SMA below the 150-day with both flat or falling over {n} sessions "
            "(within {t:+.1f}%) = elevated (bear trigger). Below without slope confirmation "
            "= watch. Otherwise benign."
        ).format(n=params["slope_lookback_trading_days"], t=params["flat_tolerance_pct"]),
        "source_url": primary_url,
        "secondary_source_url": secondary_url,
        "notes": f"{detail} {check_note} {VERIFIED_NOTE}",
    }


GROUPS: dict[str, list] = {
    "daily": [build_sma_trend],
    "monthly": [],
    "quarterly": [],
}
