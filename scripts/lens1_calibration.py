"""Calibration of the Lens 1 firing bar (SPEC.md section 3 discipline).

Usage:
    python scripts/lens1_calibration.py

The live act rule fires Lens 1 when ANY ONE of its indicators reaches
elevated (the worst-of / 1-of rule). This study asks whether raising that
bar (require 2 or 3 elevated) meaningfully improves specificity without
losing recession capture — the same filed, point-in-time discipline used
for the Lens 2 alarm.

Honest scope: only three of the six status-driving indicators have clean
free history back to 1970 (yield curve, Sahm, labour). HY spreads (free
endpoint from 2023), the PMI proxy, and the LEI proxy cannot be
reconstructed, so this calibrates the COUNT rule on the reconstructable
core-of-three. The live lens ORs six, so it fires somewhat MORE often than
the core here — the direction of the finding (1-of is very sensitive)
therefore holds a fortiori.

Reuses the point-in-time machinery from forward_returns / signal_map. Python
datetime months are 1-indexed; month arithmetic uses dateutil.relativedelta.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date

from dateutil.relativedelta import relativedelta

from forward_returns import build_signal_grid
from lens1 import find_sustained_inversions, three_month_average_rise
from signal_map import usrec_spans
from sources.fred import fetch_series
from util import DATA_DIR, ROOT, clean_series, dump_json, load_json, utc_now_iso

HORIZON = 12


def median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def core_elevated_counts(month_ends: list[str], thresholds: dict) -> dict[str, int]:
    """Count of the three reconstructable core indicators elevated per month."""
    yc_params = thresholds["yield_curve_10y3m"]
    sahm_trigger = thresholds["sahm_rule"]["elevated_level"]
    labour = thresholds["labour_market"]

    yc_dates, yc_values = fetch_series("T10Y3M")
    yc_clean_d, yc_clean_v = clean_series(yc_dates, yc_values)
    yc_episodes = find_sustained_inversions(
        yc_dates, yc_values, yc_params["sustained_inversion_min_observations"])
    sahm_d, sahm_v = clean_series(*fetch_series("SAHMREALTIME"))
    un_d, un_v = clean_series(*fetch_series("UNRATE"))
    pay_d, pay_v = clean_series(*fetch_series("PAYEMS"))

    def latest_leq(dates, values, iso):
        i = bisect_right(dates, iso)
        return values[i - 1] if i else None

    def yc_elevated(iso):
        spread = latest_leq(yc_clean_d, yc_clean_v, iso)
        if spread is None or spread < 0:
            return False
        t = date.fromisoformat(iso)
        for start, end in reversed(yc_episodes):
            end_d = date.fromisoformat(end)
            if end_d < t:
                return t <= end_d + relativedelta(months=+yc_params["elevated_window_months"])
        return False

    def labour_elevated(iso):
        i_un, i_pay = bisect_right(un_d, iso), bisect_right(pay_d, iso)
        if i_un < 15 or i_pay < 4:
            return False
        rise = three_month_average_rise(un_v[:i_un])
        changes = [b - a for a, b in zip(pay_v[i_pay - 4:i_pay - 1], pay_v[i_pay - 3:i_pay])]
        return rise >= labour["elevated_rise"] or (sum(changes) / len(changes)) < 0

    counts = {}
    for iso in month_ends:
        sahm = latest_leq(sahm_d, sahm_v, iso)
        counts[iso] = (
            int(yc_elevated(iso))
            + int(sahm is not None and sahm >= sahm_trigger)
            + int(labour_elevated(iso))
        )
    return counts


def episodes_of(flags: list[bool]):
    eps, run = [], 0
    out = []
    for i, f in enumerate(flags):
        if f:
            run = run + 1 if run else 1
            if run == 1:
                start = i
        elif run:
            out.append((start, i - 1))
            run = 0
    if run:
        out.append((start, len(flags) - 1))
    return out


def main() -> int:
    thresholds = load_json(DATA_DIR / "thresholds.json")
    grid, meta = build_signal_grid()  # has iso, close, lens2_alarm, lens3_bear per month
    isos = [g["iso"] for g in grid]
    closes = [g["close"] for g in grid]
    counts = core_elevated_counts(isos, thresholds)

    def fwd12(i):
        return (closes[i + HORIZON] / closes[i] - 1.0) * 100.0 if i + HORIZON < len(closes) else None

    def worst12(i):
        outs = [closes[i + k] / closes[i] - 1.0 for k in range(1, 13) if i + k < len(closes)]
        return min(outs) * 100.0 if outs else None

    uncond = [r for i in range(len(isos)) if (r := fwd12(i)) is not None]
    base_med = median(uncond)
    base_hit = 100.0 * sum(1 for r in uncond if r > 0) / len(uncond)

    recessions = usrec_spans(isos[0])
    rec_starts = [date.fromisoformat(s["start"]) for s in recessions]

    print(f"Sample: {isos[0]} to {isos[-1]} ({len(isos)} months), "
          f"{len(rec_starts)} NBER recessions. Base 12m median {base_med:+.1f}%, hit {base_hit:.0f}%.\n")
    print("Reconstructable core = yield curve, Sahm, labour (3 of the 6 live status indicators).\n")

    rule_rows = []
    for k in (1, 2, 3):
        fires = [counts[iso] >= k for iso in isos]
        active = sum(fires)
        eps = episodes_of(fires)
        cond = [r for i, f in enumerate(fires) if f and (r := fwd12(i)) is not None]
        cond_med = median(cond) if cond else None
        cond_hit = 100.0 * sum(1 for r in cond if r > 0) / len(cond) if cond else None

        # Recession capture: an NBER recession is "caught" if the rule fired at
        # any point in the 12 months up to and including its start month.
        caught = 0
        for rs in rec_starts:
            window_hit = any(
                fires[i] and 0 <= (rs.year - date.fromisoformat(isos[i]).year) * 12
                + (rs.month - date.fromisoformat(isos[i]).month) <= 12
                for i in range(len(isos))
            )
            caught += int(window_hit)

        # False alarms: firing episodes with no recession starting within the
        # following 12 months of the episode's onset.
        false_alarms = 0
        for (i0, i1) in eps:
            onset = date.fromisoformat(isos[i0])
            near_rec = any(0 <= (rs.year - onset.year) * 12 + (rs.month - onset.month) <= 12
                           for rs in rec_starts)
            false_alarms += int(not near_rec)

        print(f"Lens 1 fires at >= {k} of 3 elevated:")
        print(f"   active {active}/{len(isos)} months ({100*active/len(isos):.0f}%), {len(eps)} episodes")
        print(f"   recessions caught (fired within 12m before onset): {caught}/{len(rec_starts)}")
        print(f"   false-alarm episodes (no recession within 12m): {false_alarms}/{len(eps)}")
        if cond_med is not None:
            print(f"   12m fwd conditional median {cond_med:+.1f}% (hit {cond_hit:.0f}%) vs base {base_med:+.1f}% ({base_hit:.0f}%)")

        # Combined act-rule impact: (lens1_k OR lens2_alarm) AND lens3_bear.
        combined = [(fires[i] or grid[i]["lens2_alarm"]) and grid[i]["lens3_bear"]
                    for i in range(len(isos))]
        c_eps = episodes_of(combined)
        deep = 0
        for (i0, _) in c_eps:
            w = worst12(i0)
            if w is not None and w <= -20.0:
                deep += 1
        print(f"   combined act rule with this bar: {sum(combined)} months, {len(c_eps)} episodes, "
              f"{deep} caught >20% drawdowns\n")

        rule_rows.append({
            "k": k,
            "label": ("≥ 1 of 3 (current)" if k == 1 else f"≥ {k} of 3"),
            "active_months": active,
            "active_pct": round(100 * active / len(isos)),
            "episodes": len(eps),
            "recessions_caught": caught,
            "false_alarm_episodes": false_alarms,
            "cond_median_pct": round(cond_med, 1) if cond_med is not None else None,
            "combined_episodes": len(c_eps),
            "combined_deep_drawdowns": deep,
        })

    payload = {
        "computed_as_of": utc_now_iso(),
        "sample_start": isos[0], "sample_end": isos[-1],
        "sample_months": len(isos), "recession_count": len(rec_starts),
        "base_median_pct": round(base_med, 1), "base_hit_pct": round(base_hit),
        "current_k": 1,
        "core_note": (
            "Point-in-time 1970–2026, reconstructed on the three status indicators with clean "
            "free history (yield curve, Sahm, labour); HY spreads, PMI, and LEI have no free "
            "history to reconstruct. Recession capture = fired within 12 months before an NBER "
            "onset. The live lens ORs all six, so it fires somewhat more than this core."),
        "finding": (
            "Raising the bar is counterproductive: recession capture and combined-rule drawdown "
            "protection both fall, because the core indicators lead by different amounts and "
            "rarely align before onset. Specificity comes from the Lens 3 confirmation gate, not "
            "a higher Lens 1 bar. The 1-of (worst-of) bar is kept; the slots show the depth."),
        "memo_url": ("https://github.com/phuazz/market-regime-dashboard/blob/main/reviews/"
                     "2026-07-04_lens1-firing-bar-calibration.md"),
        "rules": rule_rows,
    }
    out = DATA_DIR / "lens1_calibration.json"
    dump_json(out, payload)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
