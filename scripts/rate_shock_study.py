"""Rate-shock study — does a spike in the 10-year Treasury yield derail an equity bull market?

Runs the battery frozen in `reviews/2026-09-13_rate-shock_PREREG.md` (Amendment 1,
2026-09-14). Read that document before changing anything here: every threshold, arm,
null and gate in this file is pre-registered, and a change to one of them is not a code
change, it is a protocol breach.

Run on demand. This is deliberately NOT wired into any scheduled workflow, following the
`forward_returns.py` precedent — a study is run once and filed, not refreshed nightly.

    python scripts/rate_shock_study.py --step0    # availability probes, FAIL_STOP
    python scripts/rate_shock_study.py --run      # the battery, writes the results files

Standard library plus `dateutil` only, matching the rest of this repository. Nothing here
adds a dependency: an import missing from requirements.txt silently broke the daily
refresh once already (2026-07-04, fixed in 8c14518), and every workflow gates on
`unittest discover`.

DATES: all month arithmetic through `dateutil` (Python months are 1-indexed). Session
offsets are INDEX offsets into the common trading-session list, never calendar-day
arithmetic — the prereg requires this, and it is also the only way 63 sessions means the
same thing in 1966 and 2026.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import date

from dateutil.parser import isoparse

from sources.fred import fetch_series
from sources.prices import fetch_yahoo_daily

# --- pre-registered constants (PREREG §3, §4). Do not tune. ----------------------------
DGS10_SERIES = "DGS10"
SPX_SYMBOL = "^GSPC"

# Amendment 2 (2026-09-14): the window starts 1970, not 1962. ^GSPC through this path
# begins 1970-01-02 — period1=0 is the Unix epoch and the endpoint refuses a pre-epoch
# request — so the registered 1962 start is unattainable from the registered source. The
# amendment moves the WINDOW only. The bars below keep their registered values and are
# reported as failed rather than rewritten to numbers the data clears.
WINDOW_START = date(1970, 1, 1)
SEEN_ARM_START = date(1995, 1, 1)      # the BCA chart's window; SEEN, no confirmatory status
CONFIRM_ARM_END = date(1994, 12, 31)   # downgraded to probably-unseen by Amendment 1

SHOCK_SESSIONS = 63                    # ~3 months, the claim as published
REARM_SESSIONS = 126                   # ~6 months between triggers; episode = trigger
VOL_WINDOW_YEARS = 10                  # A3 scaling window, closing at t-63
HORIZONS = (63, 126, 252)              # headline 252
HEADLINE_HORIZON = 252
PERCENTILES = (90, 95, 99)             # our thresholds; headline p95
HEADLINE_PERCENTILE = 95
BCA_REPLICATION_BP = 100.0             # their published line — replication target ONLY

# Step-0 FAIL_STOP bars, AS REGISTERED (PREREG §3). These are deliberately left at the
# values frozen on 2026-09-13 even where the data cannot clear them. Restating a bar after
# watching it fail is boundary-shopping, and it would erase the weakness from the output.
MIN_DGS10_OBS = 15_000
MIN_SPX_OBS = 15_000
MIN_CONFIRM_SESSIONS = 8_000
MIN_ALIGNMENT_SHARE = 0.98
FIRST_DATE_NO_LATER_THAN = date(1962, 1, 31)
MAX_SESSION_GAP = 15                   # consecutive-observation gap, in observations of the other series

# Amendment 2's exemption: NAMED probes, ONE cause, nothing else. These three fail because
# the equity history starts in 1970; they are reported FAILED-AS-REGISTERED and do not halt
# the study, and every confirmatory claim it makes carries a standing THIN flag. Any other
# Step-0 failure still stops the run with no partial result, exactly as §3 registers.
AMENDMENT_2_EXEMPT = {"spx_obs", "spx_start", "confirm_sessions"}
AMENDMENT_2_CAUSE = ("equity history begins 1970-01-02, so the registered 1962 window is "
                     "unattainable from the registered source (PREREG Amendment 2)")


class Step0Failure(RuntimeError):
    """Raised when a pre-registered availability probe fails. No partial run follows."""


# --- data layer -----------------------------------------------------------------------

def load_yields() -> dict[str, float]:
    """DGS10 as {iso date: percent}. FRED writes '.' for a non-publication day."""
    dates, values = fetch_series(DGS10_SERIES)
    return {d: float(v) for d, v in zip(dates, values) if v is not None}


def load_spx() -> dict[str, float]:
    """^GSPC daily closes as {iso date: close}.

    Price-only, no dividends — disclosed in PREREG §3. Conditional and base statistics
    are computed on the identical basis, so the comparison stays like-for-like; absolute
    return levels are understated throughout and the write-up must say so.
    """
    dates, values = fetch_yahoo_daily(SPX_SYMBOL)
    return {d: float(v) for d, v in zip(dates, values) if v is not None}


def common_sessions(yields: dict[str, float], spx: dict[str, float]) -> list[str]:
    """Sorted dates on which BOTH series print, from WINDOW_START.

    This list IS the trading calendar for the study. Every offset in the battery — the
    63-session shock window, the 126-session re-arm, the 252-session outcome horizon — is
    an index offset into it, so alignment between the two series is guaranteed by
    construction rather than asserted.
    """
    start = WINDOW_START.isoformat()
    return sorted(d for d in (yields.keys() & spx.keys()) if d >= start)


# --- Step 0: availability probes (PREREG §3). Any failure stops the study. -------------

def _max_gap(sessions: list[str], universe: list[str]) -> tuple[int, str]:
    """Largest run of `universe` dates missing between consecutive `sessions` entries."""
    index = {d: i for i, d in enumerate(universe)}
    worst, where = 0, ""
    for earlier, later in zip(sessions, sessions[1:]):
        gap = index[later] - index[earlier] - 1
        if gap > worst:
            worst, where = gap, f"{earlier} to {later}"
    return worst, where


def step0(verbose: bool = True) -> dict:
    """Run every pre-registered probe.

    Raises Step0Failure if any NON-EXEMPT bar is missed. The three probes named in
    `AMENDMENT_2_EXEMPT` are reported as FAILED-AS-REGISTERED and carried, which is the
    owner's recorded decision and not a softening of the protocol: the exemption is tied to
    one documented cause, and the resulting THIN flag travels with every confirmatory claim.
    """
    checks: list[tuple[str, str, bool, str]] = []

    yields = load_yields()
    spx = load_spx()

    y_dates = sorted(yields)
    s_dates = sorted(spx)
    y_first = isoparse(y_dates[0]).date()
    s_first = isoparse(s_dates[0]).date()

    checks.append((
        "dgs10_obs", f"{DGS10_SERIES} observation count",
        len(y_dates) >= MIN_DGS10_OBS,
        f"{len(y_dates):,} (bar {MIN_DGS10_OBS:,})"))
    checks.append((
        "dgs10_start", f"{DGS10_SERIES} starts on or before {FIRST_DATE_NO_LATER_THAN}",
        y_first <= FIRST_DATE_NO_LATER_THAN,
        f"first observation {y_first}"))
    checks.append((
        "spx_obs", f"{SPX_SYMBOL} observation count",
        len(s_dates) >= MIN_SPX_OBS,
        f"{len(s_dates):,} (bar {MIN_SPX_OBS:,})"))
    checks.append((
        "spx_start", f"{SPX_SYMBOL} starts on or before {FIRST_DATE_NO_LATER_THAN}",
        s_first <= FIRST_DATE_NO_LATER_THAN,
        f"first observation {s_first}"))

    sessions = common_sessions(yields, spx)
    confirm = [d for d in sessions if d <= CONFIRM_ARM_END.isoformat()]
    seen = [d for d in sessions if d >= SEEN_ARM_START.isoformat()]

    checks.append((
        "confirm_sessions",
        f"confirmatory arm {WINDOW_START.year}-{CONFIRM_ARM_END.year} common sessions",
        len(confirm) >= MIN_CONFIRM_SESSIONS,
        f"{len(confirm):,} (bar {MIN_CONFIRM_SESSIONS:,})"))

    # Alignment: of the equity sessions inside the window, how many also carry a yield?
    in_window = [d for d in s_dates if d >= WINDOW_START.isoformat()]
    share = len(sessions) / len(in_window) if in_window else 0.0
    checks.append((
        "alignment", "yield/equity session alignment",
        share >= MIN_ALIGNMENT_SHARE,
        f"{share:.4%} of {len(in_window):,} equity sessions (bar {MIN_ALIGNMENT_SHARE:.0%})"))

    gap, where = _max_gap(sessions, in_window)
    checks.append((
        "max_gap", "largest run of equity sessions with no yield print",
        gap <= MAX_SESSION_GAP,
        f"{gap} sessions{(' at ' + where) if where else ''} (bar {MAX_SESSION_GAP})"))

    registered_failures = [
        {"probe": cid, "label": label, "realised": detail, "status": "FAILED-AS-REGISTERED",
         "cause": AMENDMENT_2_CAUSE}
        for cid, label, ok, detail in checks if not ok and cid in AMENDMENT_2_EXEMPT]
    halting = [label for cid, label, ok, _ in checks
               if not ok and cid not in AMENDMENT_2_EXEMPT]

    if verbose:
        for cid, label, ok, detail in checks:
            mark = "PASS" if ok else ("FAIL*" if cid in AMENDMENT_2_EXEMPT else "FAIL")
            print(f"  {mark:<5} {label:<58} {detail}")
        print(f"\n  common sessions {sessions[0]} to {sessions[-1]}: {len(sessions):,}")
        print(f"  confirmatory arm (to {CONFIRM_ARM_END}): {len(confirm):,}")
        print(f"  seen arm (from {SEEN_ARM_START}):        {len(seen):,}")
        if registered_failures:
            print(f"\n  FAIL* = FAILED-AS-REGISTERED under PREREG Amendment 2 "
                  f"({len(registered_failures)} of them). The bar is left at its registered "
                  f"value rather than restated.\n  Cause: {AMENDMENT_2_CAUSE}.\n"
                  f"  Consequence: every confirmatory claim in this study carries a THIN flag.")

    if halting:
        raise Step0Failure(
            "Step-0 probes failed outside the Amendment 2 exemption, so the study does not "
            f"run and no partial result is filed (PREREG §3): {'; '.join(halting)}")

    return {"yields": yields, "spx": spx, "sessions": sessions,
            "confirm_sessions": confirm, "seen_sessions": seen,
            "registered_failures": registered_failures,
            "thin": bool(registered_failures)}


# =====================================================================================
# The battery (PREREG §4 and §5). Every constant it reads is pre-registered; none is
# chosen here, and changing one is a protocol breach rather than a code change.
# =====================================================================================

import json
import math
import random
import statistics
from collections import Counter, defaultdict

SEED = 20260913          # frozen in PREREG §5
NULL_DRAWS = 2_000
DD_THRESHOLD = -0.20     # a "drawdown" for H2 and for the H1a outcome indicator
H1A_DELTA = 0.15         # +15pp on P(MaxDD252 <= -20%), the economic floor
H1B_DELTA = -0.05        # -5pp on the median 252-session forward return
POWER_FLOOR = 0.80       # below this a clause is DEMOTED from a gate to a disclosure
VOL_WINDOW_SESSIONS = VOL_WINDOW_YEARS * 252


def _pct(values: list[float], q: float) -> float:
    """Linear-interpolated percentile. `statistics.quantiles` cannot take an arbitrary q."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# --- shock statistics: three arms (PREREG §4) -----------------------------------------

def shock_series(sessions: list[str], yields: dict[str, float]) -> dict[str, list]:
    """A1 absolute bp, A2 proportional, A3 volatility-scaled. None where undefined.

    A3's scaling window CLOSES at t-63, so no part of the move being measured informs its
    own scaling. That costs roughly ten and a half years of runway at the start of the
    window, which is reported rather than hidden.
    """
    y = [yields[d] for d in sessions]
    n = len(sessions)
    a1: list = [None] * n
    a2: list = [None] * n
    a3: list = [None] * n

    for i in range(SHOCK_SESSIONS, n):
        prior = y[i - SHOCK_SESSIONS]
        a1[i] = (y[i] - prior) * 100.0                 # percent -> basis points
        a2[i] = (y[i] / prior - 1.0) if prior else None

    for i in range(SHOCK_SESSIONS, n):
        end = i - SHOCK_SESSIONS                        # the window closes here
        start = end - VOL_WINDOW_SESSIONS
        if start < SHOCK_SESSIONS:
            continue
        window = [a1[j] for j in range(start, end + 1) if a1[j] is not None]
        if len(window) < VOL_WINDOW_SESSIONS // 2:
            continue
        sd = statistics.pstdev(window)
        if sd > 0 and a1[i] is not None:
            a3[i] = a1[i] / sd
    return {"A1": a1, "A2": a2, "A3": a3}


def triggers(stat: list, threshold: float) -> list[int]:
    """Crossings from below, then the 126-session re-arm. Episode = trigger (PREREG §4)."""
    crossings = [i for i in range(1, len(stat))
                 if stat[i] is not None and stat[i - 1] is not None
                 and stat[i] >= threshold > stat[i - 1]]
    kept: list[int] = []
    for i in crossings:
        if not kept or i - kept[-1] > REARM_SESSIONS:
            kept.append(i)
    return kept


# --- outcomes (PREREG §4) -------------------------------------------------------------

def forward_return(closes: list[float], entry: int, horizon: int):
    if entry + horizon >= len(closes):
        return None
    return closes[entry + horizon] / closes[entry] - 1.0


def max_drawdown(closes: list[float], entry: int, horizon: int = HEADLINE_HORIZON):
    """Largest peak-to-trough decline within `horizon` sessions after entry.

    Measured from the running maximum INSIDE the window, per PREREG §4 — not from the entry
    price, which would score a rally followed by a fall as no drawdown at all.
    """
    if entry + horizon >= len(closes):
        return None
    peak = closes[entry]
    worst = 0.0
    for j in range(entry, entry + horizon + 1):
        if closes[j] > peak:
            peak = closes[j]
        dd = closes[j] / peak - 1.0
        if dd < worst:
            worst = dd
    return worst


def outcomes_at(closes: list[float], entries: list[int]) -> dict:
    """Entry is the session AFTER the trigger; horizons that do not fit are dropped."""
    out: dict = {"n": len(entries), "returns": {}}
    for h in HORIZONS:
        out["returns"][h] = [r for r in (forward_return(closes, e, h) for e in entries)
                             if r is not None]
    dds = [d for d in (max_drawdown(closes, e) for e in entries) if d is not None]
    out["maxdd"] = dds
    out["dd_hits"] = sum(1 for d in dds if d <= DD_THRESHOLD)
    out["p_dd"] = (out["dd_hits"] / len(dds)) if dds else float("nan")
    head = out["returns"][HEADLINE_HORIZON]
    out["median_252"] = statistics.median(head) if head else float("nan")
    return out


# --- the drawdown set for H2, defined WITHOUT reference to any rate data (PREREG §4) ----

def drawdown_episodes(sessions: list[str], closes: list[float],
                      threshold: float = DD_THRESHOLD) -> list[dict]:
    """Declines of at least 20% from a running all-time high to the trough before recovery."""
    episodes: list[dict] = []
    peak_i = 0
    i = 1
    while i < len(closes):
        if closes[i] >= closes[peak_i]:
            peak_i = i
            i += 1
            continue
        trough_i = i
        j = i
        while j < len(closes) and closes[j] < closes[peak_i]:
            if closes[j] < closes[trough_i]:
                trough_i = j
            j += 1
        depth = closes[trough_i] / closes[peak_i] - 1.0
        if depth <= threshold:
            episodes.append({"peak_index": peak_i, "peak_date": sessions[peak_i],
                             "trough_date": sessions[trough_i],
                             "depth": round(depth, 4),
                             "recovered": j < len(closes)})
        if j < len(closes):
            peak_i = j
            i = j + 1
        else:
            break
    return episodes


# --- nulls: BOTH count-matched (PREREG §5) --------------------------------------------
#
# A whole-window resample of the unconditional series is NOT a null for a conditional
# statistic, and is not computed here. N1 draws the realised trigger count uniformly. N2
# also matches the realised count PER DECADE, and N2 is the comparator that decides: an
# absolute basis-point rule fires more when yields and yield volatility are high, so N2 is
# what separates "this signal carries information" from "this signal fires in bad decades".

def _eligible(stat: list, n_sessions: int) -> list[int]:
    """Sessions where a trigger could have occurred and the headline horizon still fits."""
    return [i for i in range(1, n_sessions)
            if stat[i] is not None and i + 1 + HEADLINE_HORIZON < n_sessions]


def _draw(pool: list[int], k: int, rng: random.Random) -> list[int]:
    """k indices from pool, honouring the same 126-session separation as a real trigger."""
    picked: list[int] = []
    for _ in range(60):
        picked = []
        for cand in rng.sample(pool, min(len(pool), max(k * 8, 1))):
            if all(abs(cand - p) > REARM_SESSIONS for p in picked):
                picked.append(cand)
            if len(picked) == k:
                return sorted(picked)
    return sorted(picked)


def null_distribution(closes: list[float], stat: list, sessions: list[str],
                      trigger_idx: list[int], stratified: bool, rng: random.Random,
                      draws: int = NULL_DRAWS) -> dict:
    pool = _eligible(stat, len(sessions))
    if not pool or not trigger_idx:
        return {"p_dd": [], "median_252": [], "draws": 0}

    by_decade: dict = defaultdict(list)
    want: dict = {}
    if stratified:
        want = Counter(sessions[i][:3] for i in trigger_idx)
        for i in pool:
            by_decade[sessions[i][:3]].append(i)

    p_dds, medians = [], []
    for _ in range(draws):
        if stratified:
            picks: list[int] = []
            for dec, k in want.items():
                bucket = by_decade.get(dec, [])
                if len(bucket) >= k:
                    picks.extend(_draw(bucket, k, rng))
        else:
            picks = _draw(pool, len(trigger_idx), rng)
        if not picks:
            continue
        res = outcomes_at(closes, [i + 1 for i in picks])
        if res["maxdd"] and res["returns"][HEADLINE_HORIZON]:
            p_dds.append(res["p_dd"])
            medians.append(res["median_252"])
    return {"p_dd": p_dds, "median_252": medians, "draws": len(p_dds)}


def power_at(null_values: list[float], base: float, delta: float, upper_tail: bool,
             rng: random.Random) -> dict:
    """Power to detect an effect of `delta` against this null, plus the exaggeration ratio.

    PREREG §5: computed from the count-matched null AT RUN TIME, written beside the clause,
    and power below 0.80 DEMOTES the clause from a gate to a disclosure. The rule is fixed
    here; only the number is data-driven, so it can never become a parameter choice.
    """
    if len(null_values) < 50:
        return {"power": None, "status": "UNDETERMINED", "note": "null too thin"}
    sd = statistics.pstdev(null_values)
    crit = _pct(null_values, 95 if upper_tail else 5)
    if sd == 0:
        return {"power": None, "status": "UNDETERMINED", "note": "degenerate null"}
    truth = base + delta
    z = (crit - truth) / sd
    power = (1.0 - _norm_cdf(z)) if upper_tail else _norm_cdf(z)

    # Type-M (Gelman and Carlin): among draws that would be called significant, how much
    # does the estimate overstate the truth? At low power this is the number that matters.
    kept = []
    for _ in range(20_000):
        est = rng.gauss(truth, sd)
        if (est >= crit) if upper_tail else (est <= crit):
            kept.append(est)
    exagg = ((statistics.mean(kept) - base) / delta) if (kept and delta) else None

    mde = (crit - base) + (0.8416 * sd if upper_tail else -0.8416 * sd)
    return {"power": round(power, 3),
            "critical_value": round(crit, 4),
            "null_sd": round(sd, 4),
            "mde": round(mde, 4),
            "exaggeration_ratio": round(exagg, 2) if exagg is not None else None,
            "status": "GATE" if power >= POWER_FLOOR else "DISCLOSURE"}


# --- the three questions (PREREG §5) --------------------------------------------------

def h2_necessity(dd_episodes: list[dict], trigger_idx: list[int],
                 lookbacks: tuple[int, ...] = (63, 126, 252)) -> dict:
    """Share of >=20% drawdowns preceded by a trigger. The primary deliverable.

    Descriptive, not inferential: a count needs no power, which is why this survives a
    sample H1 cannot. Primary lookback 126 sessions from the PEAK; 63 and 252 are
    pre-registered sensitivities, not a search.
    """
    result = {"n_drawdowns": len(dd_episodes), "by_lookback": {}, "episodes": []}
    for lb in lookbacks:
        preceded = [e for e in dd_episodes
                    if any(0 <= e["peak_index"] - t < lb for t in trigger_idx)]
        result["by_lookback"][lb] = {
            "preceded": len(preceded),
            "share": round(len(preceded) / len(dd_episodes), 4) if dd_episodes else None}
    for e in dd_episodes:
        hit = any(0 <= e["peak_index"] - t < REARM_SESSIONS for t in trigger_idx)
        result["episodes"].append({"peak_date": e["peak_date"],
                                   "trough_date": e["trough_date"],
                                   "depth": e["depth"],
                                   "preceded_by_spike": hit})
    return result


def h3_locatability(stat: list[float | None], closes: list[float], n_sessions: int) -> dict:
    """Outcomes by decile of the shock statistic.

    PREREG §5 pre-commits the reading: if outcomes do not separate monotonically across the
    UPPER deciles, the registered conclusion is that the series cannot locate a derailment
    threshold in either direction, and the source claim is unfalsifiable on this evidence
    rather than true or false.
    """
    pairs = [(stat[i], i) for i in range(n_sessions)
             if stat[i] is not None and i + 1 + HEADLINE_HORIZON < n_sessions]
    if not pairs:
        return {}
    values = sorted(v for v, _ in pairs)
    cuts = [_pct(values, q) for q in range(10, 100, 10)]
    buckets: dict[int, list[int]] = defaultdict(list)
    for v, i in pairs:
        buckets[sum(1 for c in cuts if v > c)].append(i)

    out = {"max_observed": round(max(values), 4), "deciles": []}
    for b in sorted(buckets):
        res = outcomes_at(closes, [i + 1 for i in buckets[b]])
        has_ret = bool(res["returns"][HEADLINE_HORIZON])
        out["deciles"].append({
            "decile": b + 1,
            "n": res["n"],
            "median_252": round(res["median_252"], 4) if has_ret else None,
            "p_dd20": round(res["p_dd"], 4) if res["maxdd"] else None})
    upper = [d["median_252"] for d in out["deciles"][-3:] if d["median_252"] is not None]
    out["upper_deciles_monotone"] = len(upper) == 3 and upper[0] > upper[1] > upper[2]
    return out


def run(probe: dict, verbose: bool = True) -> dict:
    """The whole battery, once."""
    rng = random.Random(SEED)
    sessions = probe["sessions"]
    closes = [probe["spx"][d] for d in sessions]
    n = len(sessions)
    arms = shock_series(sessions, probe["yields"])
    dd_episodes = drawdown_episodes(sessions, closes)

    base = outcomes_at(closes, [i + 1 for i in range(n) if i + 1 + HEADLINE_HORIZON < n])

    results: dict = {
        "prereg": "reviews/2026-09-13_rate-shock_PREREG.md (Amendments 1 and 2)",
        "window": {"start": sessions[0], "end": sessions[-1], "sessions": n},
        "thin": probe["thin"],
        "registered_failures": probe["registered_failures"],
        "basis": "^GSPC price-only (no dividends); conditional and base on the identical basis",
        "base_rates": {"n": base["n"],
                       "median_252": round(base["median_252"], 4),
                       "p_dd20": round(base["p_dd"], 4)},
        "drawdowns": {"n": len(dd_episodes),
                      "episodes": [{"peak_date": e["peak_date"],
                                    "trough_date": e["trough_date"],
                                    "depth": e["depth"]} for e in dd_episodes]},
        "arms": {},
    }

    cells = []
    for arm, stat in arms.items():
        defined = [v for v in stat if v is not None]
        thresholds = {"p%d" % q: _pct(defined, q) for q in PERCENTILES}
        if arm == "A1":
            thresholds["bca_100bp_REPLICATION"] = BCA_REPLICATION_BP
        first_defined = next((sessions[i] for i, v in enumerate(stat) if v is not None), None)
        arm_out = {"defined_from": first_defined,
                   "n_defined": len(defined),
                   "thresholds": {},
                   "h3": h3_locatability(stat, closes, n)}

        for name, thr in thresholds.items():
            idx = triggers(stat, thr)
            res = outcomes_at(closes, [i + 1 for i in idx])
            has_ret = bool(res["returns"][HEADLINE_HORIZON])
            cell = {
                "threshold": round(thr, 4),
                "n_triggers": len(idx),
                "trigger_dates": [sessions[i] for i in idx],
                "triggers_per_decade": dict(sorted(Counter(
                    sessions[i][:3] + "0s" for i in idx).items())),
                "median_252": round(res["median_252"], 4) if has_ret else None,
                "p_dd20": round(res["p_dd"], 4) if res["maxdd"] else None,
                "forward_medians": {h: (round(statistics.median(v), 4) if v else None)
                                    for h, v in res["returns"].items()},
                "h2": h2_necessity(dd_episodes, idx),
            }
            if name == "p%d" % HEADLINE_PERCENTILE and len(idx) >= 2:
                n1 = null_distribution(closes, stat, sessions, idx, False, rng)
                n2 = null_distribution(closes, stat, sessions, idx, True, rng)
                cell["nulls"] = {"N1_uniform_draws": n1["draws"],
                                 "N2_stratified_draws": n2["draws"]}
                cell["H1a_power"] = power_at(n2["p_dd"], base["p_dd"], H1A_DELTA, True, rng)
                cell["H1b_power"] = power_at(n2["median_252"], base["median_252"],
                                             H1B_DELTA, False, rng)
            arm_out["thresholds"][name] = cell
            cells.append(arm + ":" + name)
        results["arms"][arm] = arm_out

    results["cells_computed"] = cells
    if verbose:
        _report(results)
    return results


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else "{:+.2%}".format(value)


def _report(r: dict) -> None:
    w = r["window"]
    thin = "  [THIN - see registered_failures]" if r["thin"] else ""
    print("\n  Window {} to {}, {:,} sessions{}".format(w["start"], w["end"], w["sessions"], thin))
    print("  Basis: " + r["basis"])
    b = r["base_rates"]
    print("  Unconditional base (n={:,}): median 252-session return {}, P(MaxDD252 <= -20%) {:.1%}"
          .format(b["n"], _fmt_pct(b["median_252"]), b["p_dd20"]))

    print("\n  Drawdowns of 20% or more in the window: {}".format(r["drawdowns"]["n"]))
    for e in r["drawdowns"]["episodes"]:
        print("    {} -> {}  {:+.1%}".format(e["peak_date"], e["trough_date"], e["depth"]))

    for arm, a in r["arms"].items():
        print("\n  --- arm {} (defined from {}, {:,} sessions) ---"
              .format(arm, a["defined_from"], a["n_defined"]))
        for name, c in a["thresholds"].items():
            print("    {:<24} threshold {:>9.3f}   triggers {:>3}   median252 {:>8}   P(dd20) {:>6}"
                  .format(name, c["threshold"], c["n_triggers"],
                          _fmt_pct(c["median_252"]),
                          "n/a" if c["p_dd20"] is None else "{:.1%}".format(c["p_dd20"])))
            h2 = c["h2"]["by_lookback"].get(REARM_SESSIONS, {})
            share = h2.get("share") or 0.0
            print("      H2 necessity @126 sessions: {} of {} drawdowns preceded ({:.1%})"
                  .format(h2.get("preceded"), c["h2"]["n_drawdowns"], share))
            print("      triggers per decade: {}".format(c["triggers_per_decade"]))
            for leg in ("H1a_power", "H1b_power"):
                if leg in c:
                    p = c[leg]
                    print("      {}: power {} -> {}   MDE {}   type-M {}"
                          .format(leg, p.get("power"), p.get("status"),
                                  p.get("mde"), p.get("exaggeration_ratio")))
        h3 = a["h3"]
        if h3:
            print("    H3 upper-decile monotone: {}   max observed {}"
                  .format(h3["upper_deciles_monotone"], h3["max_observed"]))
            print("      decile median252: " + "  ".join(
                "{}:{}".format(d["decile"], _fmt_pct(d["median_252"])) for d in h3["deciles"]))


def main(argv: list[str]) -> int:
    if "--step0" in argv or "--run" in argv:
        try:
            probe = step0(verbose="--step0" in argv)
        except Step0Failure as exc:
            print("\n  --> STOP: {}".format(exc))
            return 1
        n = len(probe["registered_failures"])
        if "--step0" in argv:
            tail = ("; {} probe(s) FAILED-AS-REGISTERED and carried under Amendment 2 - "
                    "confirmatory claims are THIN".format(n)) if n else "; all probes pass"
            print("\n  --> step0: clear to run" + tail)
            return 0

        results = run(probe)
        out = Path(__file__).resolve().parent.parent / "reviews" / "2026-09-13_rate-shock"
        out.mkdir(parents=True, exist_ok=True)
        # PREREG §10: the verdict reader opens _declared; opening _full is a look and is logged.
        declared = {k: v for k, v in results.items() if k != "arms"}
        declared["arms"] = {
            arm: {"thresholds": {name: {k: v for k, v in cell.items()
                                        if k not in ("trigger_dates",)}
                                 for name, cell in a["thresholds"].items()},
                  "h3": a["h3"]}
            for arm, a in results["arms"].items()}
        (out / "rate_shock_declared.json").write_text(
            json.dumps(declared, indent=2), encoding="utf-8")
        (out / "rate_shock_full.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8")
        print("\n  --> wrote {}".format(out))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
