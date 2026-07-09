"""Weekly regime-dashboard digest.

Diffs the three lens data files against their committed state roughly seven days
ago (read out of git history) and produces an email that gives, at a glance, a
sense of what moved this week:

  1. a one-line takeaway synthesising the week;
  2. "this week's moves" — the top few movers, ranked, with direction and a
     one-line rationale (arrow glyph = direction, colour = improving/worsening);
  3. a full by-lens breakdown — every indicator with its value, weekly change,
     distance to its nearest trigger, and status.

The roll-up logic here mirrors template.html exactly (STATUS_RANK, worstStatus,
lens2SlotDef, renderCombined) so the email reports the same states the live
dashboard shows. If that logic changes on the page, change it here too.

Distance-to-trigger is shown as a number only where the displayed value is the
quantity the threshold tests (INDICATOR_META below, cross-checked against
data/thresholds.json). Where the trigger is a percentile or a derived quantity
the raw value does not equal (LEI six-month change, the multi-factor labour
read, IPO annualised pace), no distance is claimed — status only. No fabricated
precision.

Date handling (CLAUDE.md): the seven-day look-back is a datetime.timedelta.
timedelta rolls across month and year boundaries without any manual month
arithmetic (Python months are 1-indexed, but timedelta is unit-agnostic, so
indexing does not enter into it). See tests/test_weekly_digest.py for the
month-boundary and year-boundary edge cases.

Usage
-----
  python scripts/weekly_digest.py --print              print subject + text body
  python scripts/weekly_digest.py --print --write-html write the HTML body to a file
  python scripts/weekly_digest.py --since HEAD~8       diff against an explicit ref
  python scripts/weekly_digest.py --send               send via Gmail SMTP

--send reads three environment variables and refuses to run without them:
  MAIL_USERNAME  the sending Gmail account
  MAIL_PASSWORD  a Gmail App Password (not the account password)
  MAIL_TO        one recipient, or several comma-separated (e.g. "a@x.com, b@y.com")
No email address is stored in this file or the workflow; they arrive as secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DASHBOARD_URL = "https://phuazz.github.io/market-regime-dashboard/"

# Mirrors STATUS_RANK in template.html. Statuses outside this map (context,
# triggered, quiet, eased) are deliberately unranked: they never contribute to
# a lens worst-of roll-up. Valuation (shiller_cape) carries status "context"
# for exactly this reason.
STATUS_RANK = {"benign": 0, "watch": 1, "elevated": 2}
STATUS_LABEL = {
    "benign": "Benign", "watch": "Watch", "elevated": "Elevated",
    "context": "Context", "triggered": "Triggered", "quiet": "Quiet",
    "eased": "Eased",
}

# Short unit suffixes for value formatting in the email body.
UNIT_SUFFIX = {"pct": "%", "pp": " pp", "usd_bn": "bn", "index": "", "ratio": "", "bp": " bp"}

# Per-indicator interpretation, cross-checked against data/thresholds.json.
#   polarity: +1 if a higher value is deterioration (toward recession / froth),
#             -1 if a lower value is deterioration, 0 if the displayed value is
#             not itself the signal (weekly move shown neutrally, no distance).
#   trigger : how to measure distance to the nearest firing line, in the value's
#             own units, or None where the trigger is a percentile / derived
#             quantity the raw value does not equal.
#             ("level", L, "below"|"above", name) — benign side is below/above L.
#             ("chart_line", name)                — line is the indicator's own
#                                                    chart_line.value (native units).
#   delta_pct: show the weekly change as a percentage of the prior level.
INDICATOR_META = {
    # Lens 1 — recession risk
    "yield_curve_10y3m":         {"polarity": -1, "trigger": ("level", 0.0, "above", "inversion")},
    "sahm_rule":                 {"polarity": 1,  "trigger": ("level", 0.35, "below", "the watch line")},
    "hy_credit_spreads":         {"polarity": 1,  "trigger": ("level", 4.0, "below", "the watch line")},
    "pmi_manufacturing_proxy":   {"polarity": -1, "trigger": ("level", 50.0, "above", "the 50 line")},
    "leading_indicators":        {"polarity": 0,  "trigger": None},
    "labour_market":             {"polarity": 1,  "trigger": None},
    "shiller_cape":              {"polarity": 0,  "trigger": None},
    # Lens 2 — market-peak froth
    "consumer_confidence_proxy": {"polarity": 1,  "trigger": ("chart_line", "the 75th-pct trigger")},
    "retail_euphoria_aaii":      {"polarity": 1,  "trigger": ("chart_line", "the top-decile line")},
    "manager_bullishness_naaim": {"polarity": 1,  "trigger": ("level", 90.0, "below", "the 90 all-in line")},
    "growth_expectation_pe":     {"polarity": 1,  "trigger": ("chart_line", "the 90th-pct trigger")},
    "deal_ipo_froth":            {"polarity": 0,  "trigger": None},
    "rule_of_20":                {"polarity": 1,  "trigger": None},
    "value_vs_growth":           {"polarity": 1,  "trigger": ("level", 10.0, "below", "the 10pp trigger")},
    "credit_complacency_nfci":   {"polarity": -1, "trigger": ("chart_line", "the complacent tail")},
    # Lens 3 — price trend
    "sma_trend_sp500":           {"polarity": -1, "trigger": None, "delta_pct": True},
}


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def lookback_cutoff(today: date, days: int = 7) -> date:
    """Return the calendar date `days` before `today`.

    A pure helper so the boundary behaviour is unit-testable. timedelta handles
    month-end and year-end rollovers; there is no manual month or weekday math.
    """
    return today - timedelta(days=days)


# --------------------------------------------------------------------------- #
# Git access
# --------------------------------------------------------------------------- #
def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def find_baseline(days: int = 7) -> tuple[str, str, bool]:
    """Find the commit to diff against: the last one at or before `days` ago.

    Returns (sha, iso_commit_date, is_inception). If the repository is younger
    than the look-back window, fall back to the root commit and flag it so the
    email can say "since inception" rather than implying a full week of history.
    """
    cutoff = lookback_cutoff(datetime.now(timezone.utc).date(), days)
    # --before is exclusive of the given instant; passing the cutoff date means
    # "the newest commit strictly before midnight UTC on the cutoff day".
    sha = _git(["rev-list", "-1", f"--before={cutoff.isoformat()}", "HEAD"])
    is_inception = False
    if not sha:
        sha = _git(["rev-list", "--max-parents=0", "HEAD"])
        is_inception = True
    commit_date = _git(["show", "-s", "--format=%cI", sha])
    return sha, commit_date, is_inception


def read_current(name: str) -> dict:
    """Read a data file from the working tree (equals HEAD inside CI)."""
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def read_at_ref(ref: str, name: str) -> dict | None:
    """Read a data file as of a git ref. Returns None if it did not exist then."""
    try:
        blob = _git(["show", f"{ref}:data/{name}"])
    except subprocess.CalledProcessError:
        return None
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Roll-up logic (mirror of template.html)
# --------------------------------------------------------------------------- #
def worst_status(indicators: list[dict]) -> str:
    worst = "benign"
    for ind in indicators:
        status = ind.get("status")
        if status in STATUS_RANK and STATUS_RANK[status] > STATUS_RANK[worst]:
            worst = status
    return worst


def status_counts(indicators: list[dict]) -> dict:
    ranked = [i for i in indicators if i.get("status") in STATUS_RANK]
    return {
        "total": len(ranked),
        "elevated": sum(1 for i in ranked if i["status"] == "elevated"),
        "watch": sum(1 for i in ranked if i["status"] == "watch"),
    }


def lens1_fires(lens1: dict) -> bool:
    return worst_status(lens1["indicators"]) == "elevated"


def lens2_fires(lens2: dict) -> bool:
    return lens2.get("composite", {}).get("alarm_state") == "at_or_above"


def lens3_confirms(lens3: dict) -> bool:
    return worst_status(lens3["indicators"]) == "elevated"


def combined_state(lens1: dict, lens2: dict, lens3: dict) -> tuple[str, str]:
    """Return (state, message) where state is 'none' | 'armed' | 'fired'.

    Mirrors renderCombined() in template.html, including the message wording.
    """
    counts = status_counts(lens1["indicators"])
    armed = []
    if lens1_fires(lens1):
        armed.append(
            f"recession risk is elevated ({counts['elevated']} of {counts['total']} indicators)"
        )
    if lens2_fires(lens2):
        armed.append("the froth composite is at alarm")

    composite = lens2["composite"]
    share = fmt_share(composite["share_pct"])
    alarm = fmt_share(composite["alarm_share_pct"])

    if armed and lens3_confirms(lens3):
        message = (
            "RISK-REDUCTION SIGNAL FIRED — reduce risk, not liquidate: "
            + " and ".join(armed)
            + ", confirmed by the price-trend bear trigger."
        )
        return "fired", message
    if armed:
        message = (
            "ARMED — " + " and ".join(armed)
            + "; no action until Lens 3 confirms with the trend bear trigger."
        )
        return "armed", message
    message = (
        f"No risk-reduction signal — recession risk is not elevated and the froth "
        f"composite ({share}%) is below the {alarm}% alarm."
    )
    return "none", message


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def fmt_share(value) -> str:
    """Trim a percentage to a tidy string: 62.5 -> '62.5', 50.0 -> '50'."""
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def fmt_value(ind: dict) -> str:
    value = ind.get("value")
    if value is None:
        return "—"
    decimals = ind.get("decimals", 2)
    text = f"{value:,.{decimals}f}"  # comma grouping reads index levels cleanly
    if ind.get("signed") and value > 0:
        text = "+" + text
    return text + UNIT_SUFFIX.get(ind.get("unit"), "")


# --------------------------------------------------------------------------- #
# Distance to trigger (headroom)
# --------------------------------------------------------------------------- #
def headroom(record: dict):
    """Return (room, line_name) or None.

    room > 0 means the indicator is that far from its firing line (not yet
    triggered); room < 0 means it is that far past the line (triggered). Units
    are the indicator's own. None where no clean single trigger applies.
    """
    meta = INDICATOR_META.get(record.get("id"))
    if not meta or not meta.get("trigger"):
        return None
    value = record.get("value")
    if value is None:
        return None
    trig = meta["trigger"]
    if trig[0] == "level":
        _, line, benign, name = trig
        room = (line - value) if benign == "below" else (value - line)
    elif trig[0] == "chart_line":
        line = record.get("chart_line")
        if line is None:
            return None
        name = trig[1]
        room = (line - value) if meta["polarity"] > 0 else (value - line)
    else:
        return None
    return room, name


def headroom_text(record: dict):
    hr = headroom(record)
    if hr is None:
        return None
    room, name = hr
    decimals = record.get("decimals", 2)
    mag = f"{abs(room):,.{decimals}f}"
    return f"{mag} from {name}" if room >= 0 else f"{mag} past {name}"


def trigger_metric_text(tm: dict, status: str):
    """Render "<label> <metric> · <distance> from the <line> <tier> line".

    For indicators whose displayed value is not the quantity the threshold tests.
    Distance is measured to the next worse tier from the current status, in the
    metric's own units, so the reader sees both the metric and how much room is
    left before it escalates.
    """
    if not tm or tm.get("value") is None:
        return None
    dec = tm.get("decimals", 2)
    suffix = UNIT_SUFFIX.get(tm.get("unit"), "")
    metric_str = f"{tm.get('label', 'metric')} {tm['value']:+.{dec}f}{suffix}"

    if status == "elevated":
        target, tier = tm.get("elevated_at"), "elevated"
    elif status == "watch":
        target, tier = tm.get("elevated_at"), "elevated"
    else:  # benign or unranked
        target, tier = tm.get("watch_at"), "watch"
    if target is None:
        return metric_str

    # benign_side says which side of the line is safe; room > 0 means not yet crossed.
    room = (tm["value"] - target) if tm.get("benign_side") == "above" else (target - tm["value"])
    rel = "from" if room >= 0 else "past"
    line_str = f"{target:.{dec}f}{suffix}"
    return f"{metric_str} · {abs(room):.{dec}f} {rel} the {line_str} {tier} line"


def distance_text(record: dict):
    """Distance-to-trigger for a row: the trigger metric if one is supplied,
    otherwise the headroom computed from the displayed value."""
    tm = record.get("trigger_metric")
    if tm:
        return trigger_metric_text(tm, record.get("status"))
    return headroom_text(record)


# --------------------------------------------------------------------------- #
# Snapshot and diff
# --------------------------------------------------------------------------- #
def _ind_record(ind: dict) -> dict:
    chart_line = ind.get("chart_line") or {}
    return {
        "id": ind["id"],
        "name": ind.get("name", ind["id"]),
        "status": ind.get("status"),
        "value": ind.get("value"),
        "value_text": fmt_value(ind),
        "unit": ind.get("unit"),
        "signed": ind.get("signed", False),
        "decimals": ind.get("decimals", 2),
        "as_of": ind.get("as_of"),
        "chart_line": chart_line.get("value"),
        # Some indicators display one value but the status tests another (LEI level
        # vs its six-month change; the labour level vs the Sahm-style rise). When
        # the builder supplies that metric and its lines, the digest shows distance
        # to the next tier in the metric's own units.
        "trigger_metric": ind.get("trigger_metric"),
    }


def snapshot(lens1: dict, lens2: dict, lens3: dict) -> dict:
    """Compact the three lens files into the fields the digest compares.

    Each lensN is an ordered id -> record map (Python dicts preserve insertion
    order, so iterating yields file/display order).
    """
    state, message = combined_state(lens1, lens2, lens3)

    def index(lens):
        return {ind["id"]: _ind_record(ind) for ind in lens["indicators"]}

    composite = lens2["composite"]
    return {
        "combined": {"state": state, "message": message},
        "lens1": index(lens1),
        "lens2": index(lens2),
        "lens3": index(lens3),
        "counts1": status_counts(lens1["indicators"]),
        "lens_status": {
            "lens1": worst_status(lens1["indicators"]),
            "lens3": worst_status(lens3["indicators"]),
        },
        "composite": {
            "share_pct": composite["share_pct"],
            "triggered_count": composite["triggered_count"],
            "gauge_count": composite["gauge_count"],
            "alarm_share_pct": composite["alarm_share_pct"],
            "alarm_state": composite["alarm_state"],
        },
    }


def diff_snapshots(old: dict | None, new: dict) -> list[dict]:
    """Return an ordered list of change records, most material first.

    Each record is {kind, headline, detail}. If `old` is None (no comparable
    baseline) an empty list is returned and the caller reports a baseline-only
    digest.
    """
    if old is None:
        return []
    changes: list[dict] = []

    # 1. Combined risk-reduction signal — the single most important line.
    if old["combined"]["state"] != new["combined"]["state"]:
        labels = {"none": "No signal", "armed": "ARMED", "fired": "SIGNAL FIRED"}
        changes.append({
            "kind": "combined",
            "headline": f"Risk-reduction signal: {labels[old['combined']['state']]} "
                        f"→ {labels[new['combined']['state']]}",
            "detail": new["combined"]["message"],
        })

    # 2. Lens 2 composite: the alarm crossing, then share, then count.
    oc, nc = old["composite"], new["composite"]
    if oc["alarm_state"] != nc["alarm_state"]:
        crossed = "crossed its alarm" if nc["alarm_state"] == "at_or_above" else "fell back below its alarm"
        changes.append({
            "kind": "composite_alarm",
            "headline": f"Lens 2 froth composite {crossed} ({fmt_share(nc['alarm_share_pct'])}%)",
            "detail": f"Now {fmt_share(nc['share_pct'])}% triggered "
                      f"({nc['triggered_count']} of {nc['gauge_count']} gauges).",
        })
    elif oc["share_pct"] != nc["share_pct"]:
        changes.append({
            "kind": "composite_share",
            "headline": f"Lens 2 froth composite {fmt_share(oc['share_pct'])}% "
                        f"→ {fmt_share(nc['share_pct'])}%",
            "detail": f"{nc['triggered_count']} of {nc['gauge_count']} gauges triggered "
                      f"(alarm at {fmt_share(nc['alarm_share_pct'])}%).",
        })

    # 3. Indicator status flips across all three lenses.
    for lens_key, lens_label in (("lens1", "Lens 1"), ("lens2", "Lens 2"), ("lens3", "Lens 3")):
        for ind_id, cur in new[lens_key].items():
            prev = old[lens_key].get(ind_id)
            if prev is None or prev["status"] == cur["status"]:
                continue
            old_label = STATUS_LABEL.get(prev["status"], prev["status"])
            new_label = STATUS_LABEL.get(cur["status"], cur["status"])
            changes.append({
                "kind": "indicator",
                "headline": f"{lens_label} · {cur['name']}: {old_label} → {new_label}",
                "detail": f"Now {cur['value_text']} (as of {cur['as_of']}).",
            })

    return changes


# --------------------------------------------------------------------------- #
# Weekly moves
# --------------------------------------------------------------------------- #
def _delta_text(delta: float, record: dict, is_pct: bool, new_print: bool, arrow: str) -> str:
    if delta is None:
        return "—"
    if arrow == "flat":
        return "unchanged" if new_print else "no new print"
    sign = "+" if delta > 0 else "-"
    if is_pct or record.get("unit") == "pct":
        return f"{sign}{abs(delta):.1f}% wk" if is_pct else f"{sign}{abs(delta):.{record.get('decimals', 2)}f}% wk"
    return f"{sign}{abs(delta):.{record.get('decimals', 2)}f} wk"


def compute_moves(old: dict | None, new: dict) -> dict:
    """Return id -> move record for every current indicator.

    Empty when there is no baseline. A move carries the weekly delta, a
    direction arrow, a sense (better / worse / neutral from the indicator's
    polarity), whether a fresh print landed, and any status change.
    """
    moves: dict = {}
    if old is None:
        return moves
    for lens_key in ("lens1", "lens2", "lens3"):
        old_lens = old.get(lens_key, {})
        for ind_id, cur in new[lens_key].items():
            prev = old_lens.get(ind_id)
            if not prev:
                continue
            ov, nv = prev.get("value"), cur.get("value")
            new_print = prev.get("as_of") != cur.get("as_of")
            status_changed = prev.get("status") != cur.get("status")
            meta = INDICATOR_META.get(ind_id, {})
            is_pct = bool(meta.get("delta_pct"))
            if ov is None or nv is None:
                moves[ind_id] = {"delta": None, "arrow": "flat", "sense": "neutral",
                                 "is_pct": is_pct, "new_print": new_print,
                                 "status_changed": status_changed, "old_status": prev.get("status"),
                                 "text": "—"}
                continue
            delta = (nv - ov) / ov * 100.0 if (is_pct and ov) else (nv - ov)
            arrow = "up" if delta > 1e-9 else ("down" if delta < -1e-9 else "flat")
            polarity = meta.get("polarity", 0)
            if arrow == "flat" or polarity == 0:
                sense = "neutral"
            else:
                sense = "worse" if (delta * polarity > 0) else "better"
            moves[ind_id] = {
                "delta": delta, "arrow": arrow, "sense": sense, "is_pct": is_pct,
                "new_print": new_print, "status_changed": status_changed,
                "old_status": prev.get("status"),
                "text": _delta_text(delta, cur, is_pct, new_print, arrow),
            }
    return moves


def _mover_rationale(record: dict, mv: dict) -> str:
    if mv["status_changed"]:
        base = (f"{STATUS_LABEL.get(mv['old_status'], mv['old_status'])} → "
                f"{STATUS_LABEL.get(record['status'], record['status'])}")
    else:
        base = mv["text"]
    hr = distance_text(record)
    return f"{base}, {hr}" if hr else base


def rank_movers(new: dict, moves: dict, limit: int = 3) -> list[dict]:
    """Rank the week's most material indicator moves, most material first.

    Score: a status flip dominates; otherwise a move is weighted by the fraction
    of its remaining headroom it consumed toward the trigger (a small absolute
    move that eats a lot of the room to the line is material), with a percentage
    move for the index trend and a small floor for any other real move.
    """
    scored = []
    for lens_key in ("lens1", "lens2", "lens3"):
        for ind_id, rec in new[lens_key].items():
            mv = moves.get(ind_id)
            if not mv:
                continue
            if not mv["status_changed"] and mv["arrow"] == "flat":
                continue
            score = 0.0
            if mv["status_changed"]:
                score += 2.0
                if rec["status"] in ("elevated", "triggered"):
                    score += 0.5
            if mv["delta"] is not None and mv["arrow"] != "flat":
                hr = headroom(rec)
                if hr and hr[0] > 0 and mv["sense"] == "worse":
                    score += min(1.0, abs(mv["delta"]) / hr[0])
                elif mv["is_pct"]:
                    score += min(1.0, abs(mv["delta"]) / 2.0)
                else:
                    score += 0.15
            scored.append((score, ind_id, rec, mv))

    scored.sort(key=lambda t: (t[0], abs(t[3]["delta"] or 0.0)), reverse=True)
    movers = []
    for score, ind_id, rec, mv in scored[:limit]:
        if score <= 0:
            continue
        movers.append({
            "id": ind_id, "name": rec["name"], "value_text": rec["value_text"],
            "arrow": mv["arrow"], "sense": mv["sense"], "status": rec["status"],
            "rationale": _mover_rationale(rec, mv),
        })
    return movers


# --------------------------------------------------------------------------- #
# Narrative and lens headers
# --------------------------------------------------------------------------- #
def narrative(new: dict, movers: list[dict], has_baseline: bool, changes: list[dict]) -> str:
    """A one-to-two sentence, rules-generated synthesis of the week."""
    state = new["combined"]["state"]
    comp = new["composite"]
    share = fmt_share(comp["share_pct"])
    alarm = fmt_share(comp["alarm_share_pct"])
    alarm_rel = "at" if comp["alarm_state"] == "at_or_above" else "below"
    c = new["counts1"]
    l1, l3 = new["lens_status"]["lens1"], new["lens_status"]["lens3"]

    if l1 == "elevated":
        l1w = f"recession risk elevated ({c['elevated']} of {c['total']})"
    elif l1 == "watch":
        l1w = f"recession risk on watch ({c['watch']} of {c['total']}, none elevated)"
    else:
        l1w = "recession risk benign"
    l3w = {"benign": "trend intact", "watch": "trend weakening",
           "elevated": "trend confirming the downturn"}[l3]

    if state == "fired":
        lead = f"Risk-reduction signal fired this week — {l3w}."
    elif state == "armed":
        lead = f"A lens is armed and awaiting Lens 3 confirmation; {l3w}."
    else:
        opener = "Quiet week" if (has_baseline and not changes) else "No risk-reduction signal"
        lead = f"{opener} — {l1w}; froth {share}% ({alarm_rel} the {alarm}% alarm); {l3w}."

    if movers:
        drift = f"Biggest move: {movers[0]['name']} — {movers[0]['rationale']}."
    elif not has_baseline:
        drift = "Week-over-week moves begin once the digest holds a full week of history (from ~9 July)."
    else:
        drift = "No indicator changed tier and no notable weekly move."
    return f"{lead} {drift}"


def lens_header(new: dict, lens_key: str) -> dict:
    """Return {word, detail, chip} for a lens section header."""
    if lens_key == "lens2":
        comp = new["composite"]
        rel = "at" if comp["alarm_state"] == "at_or_above" else "below"
        return {
            "word": f"{fmt_share(comp['share_pct'])}% triggered",
            "detail": f"{comp['triggered_count']} of {comp['gauge_count']} gauges · "
                      f"{rel} the {fmt_share(comp['alarm_share_pct'])}% alarm",
            "chip": "elevated" if comp["alarm_state"] == "at_or_above" else "benign",
        }
    if lens_key == "lens1":
        status = new["lens_status"]["lens1"]
        c = new["counts1"]
        if status == "elevated":
            detail = f"{c['elevated']} of {c['total']} elevated" + (f", {c['watch']} on watch" if c["watch"] else "")
        elif status == "watch":
            detail = f"{c['watch']} of {c['total']} on watch, none elevated"
        else:
            detail = f"all {c['total']} benign, none elevated"
        return {"word": STATUS_LABEL[status], "detail": detail, "chip": status}
    # lens3
    status = new["lens_status"]["lens3"]
    word = {"benign": "Intact", "watch": "Weakening", "elevated": "Confirming"}[status]
    return {"word": word, "detail": "50-day vs 150-day trend", "chip": status}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_subject(new: dict, changes: list[dict]) -> str:
    share = fmt_share(new["composite"]["share_pct"])
    if not changes:
        state_word = {"none": "no signal", "armed": "ARMED", "fired": "SIGNAL FIRED"}[
            new["combined"]["state"]
        ]
        return f"Regime dashboard: quiet week — {state_word}, froth {share}%"
    lead = changes[0]["headline"]
    n = len(changes)
    suffix = "" if n == 1 else f" (+{n - 1} more)"
    return f"Regime dashboard: {lead}{suffix}"


_LENS_TITLES = (("lens1", "RECESSION RISK"), ("lens2", "MARKET-PEAK FROTH"), ("lens3", "PRICE TREND"))
_ARROW_TEXT = {"up": "▲", "down": "▼", "flat": "–"}


def _moves_empty_note(moves: dict) -> str:
    if not moves:
        return "Week-over-week moves begin once the digest holds a full week of history (from ~9 July)."
    return "No notable moves — a quiet week."


def render_text(new: dict, movers: list[dict], moves: dict, narrative_text: str, baseline_label: str) -> str:
    lines = ["REGIME DASHBOARD — WEEKLY DIGEST", baseline_label, "", narrative_text, ""]

    lines.append("THIS WEEK'S MOVES")
    if movers:
        for m in movers:
            lines.append(f"  {_ARROW_TEXT[m['arrow']]} {m['name']} — {m['rationale']} "
                         f"[{STATUS_LABEL.get(m['status'], m['status'])}]")
    else:
        lines.append(f"  {_moves_empty_note(moves)}")
    lines.append("")

    for lens_key, title in _LENS_TITLES:
        head = lens_header(new, lens_key)
        lines.append(f"{title} — {head['word']} · {head['detail']}")
        for ind_id, rec in new[lens_key].items():
            mv = moves.get(ind_id, {})
            dtxt = mv.get("text", "")
            piece = rec["value_text"]
            if dtxt and dtxt not in ("—",):
                piece += f" ({dtxt})"
            hr = distance_text(rec)
            tail = f", {hr}" if hr else ""
            lines.append(f"  {rec['name']}: {piece}{tail} — {STATUS_LABEL.get(rec['status'], rec['status'])}")
        lines.append("")

    lines.append(new["combined"]["message"])
    lines.append(f"Full dashboard: {DASHBOARD_URL}")
    return "\n".join(lines)


STATUS_COLOUR = {
    "elevated": "#c0392b", "fired": "#c0392b", "watch": "#b45309",
    "armed": "#b45309", "benign": "#1a8754", "none": "#1a8754",
    "context": "#6b7280", "triggered": "#b45309", "quiet": "#6b7280",
    "eased": "#1a8754",
}
DELTA_COLOUR = {"better": "#1a8754", "worse": "#b45309", "neutral": "#8a8f98"}


def _chip_html(status: str) -> str:
    colour = STATUS_COLOUR.get(status, "#6b7280")
    label = STATUS_LABEL.get(status, status.capitalize())
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            f'font-size:12px;font-weight:600;color:#fff;background:{colour}">{label}</span>')


def _delta_html(mv: dict) -> str:
    if not mv or mv.get("delta") is None or mv.get("arrow") == "flat":
        txt = mv.get("text", "") if mv else ""
        return f'<span style="color:#8a8f98;font-size:12px">{txt}</span>' if txt else ""
    glyph = "▲" if mv["arrow"] == "up" else "▼"
    colour = DELTA_COLOUR.get(mv["sense"], "#8a8f98")
    return (f'<span style="color:{colour};font-size:12px;white-space:nowrap">'
            f'{glyph} {mv["text"]}</span>')


def _section_html(new: dict, lens_key: str, moves: dict) -> str:
    head = lens_header(new, lens_key)
    title = {"lens1": "Recession risk", "lens2": "Market-peak froth", "lens3": "Price trend"}[lens_key]
    parts = [
        '<div style="margin:22px 0 6px;display:flex;align-items:baseline;justify-content:space-between;gap:8px">',
        f'<span style="font-size:15px;font-weight:600">{title}</span>',
        f'<span style="font-size:12px;color:#6b7280">{head["word"]} · {head["detail"]}</span>',
        '</div>',
        '<table style="border-collapse:collapse;width:100%;font-size:14px">',
    ]
    for ind_id, rec in new[lens_key].items():
        hr = distance_text(rec) or ""
        parts.append(
            '<tr>'
            f'<td style="padding:6px 8px 6px 0;border-bottom:1px solid #f0f0f0;color:#1f2328">{rec["name"]}</td>'
            f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;font-family:ui-monospace,Menlo,Consolas,monospace;'
            f'font-size:13px;color:#4b5563;white-space:nowrap">{rec["value_text"]}</td>'
            f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0">{_delta_html(moves.get(ind_id))}</td>'
            f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;color:#6b7280;font-size:12px">{hr}</td>'
            f'<td style="padding:6px 0;border-bottom:1px solid #f0f0f0;text-align:right">{_chip_html(rec["status"])}</td>'
            '</tr>'
        )
    parts.append("</table>")
    return "".join(parts)


def render_html(new: dict, movers: list[dict], moves: dict, narrative_text: str, baseline_label: str) -> str:
    parts = [
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
        'max-width:660px;margin:0 auto;color:#1f2328;font-size:15px;line-height:1.5">',
        '<h2 style="font-size:18px;margin:0 0 2px">Regime dashboard — weekly digest</h2>',
        f'<p style="color:#6b7280;font-size:13px;margin:0 0 16px">{baseline_label}</p>',
        f'<div style="padding:12px 14px;background:#f0f6f2;border-radius:8px;font-size:14px;'
        f'line-height:1.6;margin:0 0 8px">{narrative_text}</div>',
    ]

    parts.append('<h3 style="font-size:15px;margin:22px 0 6px">This week’s moves</h3>')
    if movers:
        parts.append('<table style="border-collapse:collapse;width:100%;font-size:14px">')
        for m in movers:
            glyph = _ARROW_TEXT[m["arrow"]]
            colour = DELTA_COLOUR.get(m["sense"], "#8a8f98")
            parts.append(
                '<tr>'
                f'<td style="padding:7px 8px 7px 0;border-bottom:1px solid #f0f0f0;'
                f'color:{colour};font-size:15px;width:14px">{glyph}</td>'
                f'<td style="padding:7px 8px;border-bottom:1px solid #f0f0f0">'
                f'<strong>{m["name"]}</strong> '
                f'<span style="color:#4b5563;font-size:13px">— {m["rationale"]}</span></td>'
                f'<td style="padding:7px 8px;border-bottom:1px solid #f0f0f0;font-family:ui-monospace,Menlo,Consolas,monospace;'
                f'font-size:13px;color:#4b5563;text-align:right;white-space:nowrap">{m["value_text"]}</td>'
                f'<td style="padding:7px 0;border-bottom:1px solid #f0f0f0;text-align:right">{_chip_html(m["status"])}</td>'
                '</tr>'
            )
        parts.append("</table>")
    else:
        parts.append(
            f'<p style="padding:10px 14px;background:#f6f6f4;border-left:3px solid #c9c9c4;'
            f'border-radius:0 6px 6px 0;margin:0;color:#4b5563;font-size:14px">{_moves_empty_note(moves)}</p>'
        )

    for lens_key, _title in _LENS_TITLES:
        parts.append(_section_html(new, lens_key, moves))

    parts.append(
        f'<p style="margin:22px 0 6px;color:#4b5563;font-size:14px">{new["combined"]["message"]}</p>'
    )
    parts.append(
        f'<p style="margin:14px 0 0"><a href="{DASHBOARD_URL}" '
        f'style="color:#1d4ed8;text-decoration:none;font-weight:600">Open the full dashboard →</a></p>'
    )
    parts.append("</div>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Build and send
# --------------------------------------------------------------------------- #
def build_digest(since_ref: str | None) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body)."""
    new = snapshot(read_current("lens1.json"), read_current("lens2.json"), read_current("lens3.json"))

    if since_ref:
        ref, baseline_iso, is_inception = since_ref, None, False
    else:
        ref, baseline_iso, is_inception = find_baseline(days=7)

    old_lens1 = read_at_ref(ref, "lens1.json")
    old_lens2 = read_at_ref(ref, "lens2.json")
    old_lens3 = read_at_ref(ref, "lens3.json")
    old = None
    if old_lens1 and old_lens2 and old_lens3:
        # A schema change between the baseline and now (a renamed field, a
        # composite block that did not exist yet) must not crash the unattended
        # job. Degrade to a baseline-only digest instead.
        try:
            old = snapshot(old_lens1, old_lens2, old_lens3)
        except (KeyError, TypeError, StopIteration):
            old = None

    changes = diff_snapshots(old, new)
    moves = compute_moves(old, new)
    movers = rank_movers(new, moves)
    narrative_text = narrative(new, movers, old is not None, changes)

    if is_inception:
        baseline_label = "since the dashboard went live"
    elif baseline_iso:
        baseline_label = f"since {baseline_iso[:10]}"
    else:
        baseline_label = f"since {ref}"

    subject = render_subject(new, changes)
    text = render_text(new, movers, moves, narrative_text, baseline_label)
    html = render_html(new, movers, moves, narrative_text, baseline_label)
    return subject, text, html


def parse_recipients(raw: str | None) -> list[str]:
    """Split a comma-separated MAIL_TO into a clean address list.

    Forgiving so that adding a second recipient to the secret is low-risk:
    stray whitespace and empty fields (a trailing comma) are dropped.
    "phuazz@gmail.com, eileen@example.com" -> two addresses.
    """
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def send_email(subject: str, text: str, html: str) -> None:
    username = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_PASSWORD")
    recipients = parse_recipients(os.environ.get("MAIL_TO"))
    missing = [k for k, v in
               (("MAIL_USERNAME", username), ("MAIL_PASSWORD", password), ("MAIL_TO", recipients))
               if not v]
    if missing:
        raise SystemExit(f"Cannot send: missing environment variable(s) {', '.join(missing)}.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username
    # send_message extracts every address in the To header, so a comma-separated
    # MAIL_TO reaches all recipients with no further wiring.
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(username, password)
        server.send_message(msg)
    print(f"Sent: {subject} -> {', '.join(recipients)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and optionally send the weekly regime digest.")
    parser.add_argument("--send", action="store_true", help="send via Gmail SMTP (needs MAIL_* env vars)")
    parser.add_argument("--print", dest="do_print", action="store_true", help="print subject and text body")
    parser.add_argument("--write-html", metavar="PATH", help="write the HTML body to a file (dev preview)")
    parser.add_argument("--since", metavar="REF", help="diff against an explicit git ref instead of 7 days ago")
    args = parser.parse_args(argv)

    # The digest body uses em-dashes and arrows; make the local preview legible
    # on a Windows console (cp1252 by default) without affecting the UTF-8 MIME
    # that --send builds.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    subject, text, html = build_digest(args.since)

    if args.write_html:
        Path(args.write_html).write_text(html, encoding="utf-8")
        print(f"Wrote HTML body to {args.write_html}")
    if args.do_print or not (args.send or args.write_html):
        print("=" * 70)
        print(f"SUBJECT: {subject}")
        print("=" * 70)
        print(text)
    if args.send:
        send_email(subject, text, html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
