"""Weekly regime-dashboard digest.

Diffs the three lens data files against their committed state roughly seven days
ago (read out of git history) and produces a short email describing what moved:
the combined risk-reduction signal, the Lens 2 froth composite, and any
indicator status flips across the three lenses.

The roll-up logic here mirrors template.html exactly (STATUS_RANK, worstStatus,
lens2SlotDef, renderCombined) so the email reports the same states the live
dashboard shows. If that logic changes on the page, change it here too.

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
    text = f"{value:.{decimals}f}"
    if ind.get("signed") and value > 0:
        text = "+" + text
    return text + UNIT_SUFFIX.get(ind.get("unit"), "")


# --------------------------------------------------------------------------- #
# Snapshot and diff
# --------------------------------------------------------------------------- #
def snapshot(lens1: dict, lens2: dict, lens3: dict) -> dict:
    """Compact the three lens files into the fields the digest compares."""
    state, message = combined_state(lens1, lens2, lens3)

    def index(lens):
        return {
            ind["id"]: {
                "name": ind.get("name", ind["id"]),
                "status": ind.get("status"),
                "value_text": fmt_value(ind),
                "as_of": ind.get("as_of"),
            }
            for ind in lens["indicators"]
        }

    composite = lens2["composite"]
    return {
        "combined": {"state": state, "message": message},
        "lens1": index(lens1),
        "lens2": index(lens2),
        "lens3": index(lens3),
        "counts1": status_counts(lens1["indicators"]),
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


def _standings_rows(new: dict) -> list[tuple[str, str, str]]:
    """(label, value, status_label) rows for the current-standings table."""
    c = new["counts1"]
    comp = new["composite"]
    combined_word = {"none": "No signal", "armed": "Armed", "fired": "Signal fired"}[
        new["combined"]["state"]
    ]
    return [
        ("Risk-reduction signal", combined_word, new["combined"]["state"]),
        ("Lens 1 · Recession risk",
         f"{c['elevated']} elevated, {c['watch']} watch of {c['total']}",
         "elevated" if c["elevated"] else ("watch" if c["watch"] else "benign")),
        ("Lens 2 · Market-peak froth",
         f"{fmt_share(comp['share_pct'])}% triggered ({comp['triggered_count']} of {comp['gauge_count']})",
         "elevated" if comp["alarm_state"] == "at_or_above" else "benign"),
        ("Lens 3 · Price trend",
         next(iter(new["lens3"].values()))["value_text"],
         next(iter(new["lens3"].values()))["status"]),
    ]


def render_text(new: dict, changes: list[dict], baseline_label: str) -> str:
    lines = ["REGIME DASHBOARD — WEEKLY DIGEST", ""]
    if changes:
        lines.append(f"What changed ({baseline_label}):")
        for ch in changes:
            lines.append(f"  • {ch['headline']}")
            lines.append(f"    {ch['detail']}")
    else:
        lines.append(f"No changes {baseline_label}. Current standings:")
    lines.append("")
    lines.append("Where things stand:")
    for label, value, _status in _standings_rows(new):
        lines.append(f"  {label}: {value}")
    lines.append("")
    lines.append(new["combined"]["message"])
    lines.append("")
    lines.append(f"Full dashboard: {DASHBOARD_URL}")
    return "\n".join(lines)


STATUS_COLOUR = {
    "elevated": "#c0392b", "fired": "#c0392b", "watch": "#b45309",
    "armed": "#b45309", "benign": "#1a8754", "none": "#1a8754",
    "context": "#6b7280", "triggered": "#b45309", "quiet": "#6b7280",
    "eased": "#1a8754",
}


def render_html(new: dict, changes: list[dict], baseline_label: str) -> str:
    def chip(status: str) -> str:
        colour = STATUS_COLOUR.get(status, "#6b7280")
        label = STATUS_LABEL.get(status, status.capitalize())
        return (
            f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            f'font-size:12px;font-weight:600;color:#fff;background:{colour}">{label}</span>'
        )

    parts = [
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
        'max-width:640px;margin:0 auto;color:#1f2328;font-size:15px;line-height:1.5">',
        '<h2 style="font-size:18px;margin:0 0 4px">Regime dashboard — weekly digest</h2>',
        f'<p style="color:#6b7280;font-size:13px;margin:0 0 20px">{baseline_label}</p>',
    ]

    if changes:
        parts.append('<h3 style="font-size:15px;margin:0 0 8px">What changed</h3>')
        parts.append('<ul style="padding-left:18px;margin:0 0 20px">')
        for ch in changes:
            parts.append(
                f'<li style="margin-bottom:8px"><strong>{ch["headline"]}</strong>'
                f'<br><span style="color:#4b5563;font-size:14px">{ch["detail"]}</span></li>'
            )
        parts.append("</ul>")
    else:
        parts.append(
            f'<p style="padding:10px 14px;background:#f0f6f2;border-left:3px solid #1a8754;'
            f'border-radius:0 6px 6px 0;margin:0 0 20px">No changes {baseline_label}. '
            f'Standings below.</p>'
        )

    parts.append('<h3 style="font-size:15px;margin:0 0 8px">Where things stand</h3>')
    parts.append('<table style="border-collapse:collapse;width:100%;font-size:14px">')
    for label, value, status in _standings_rows(new):
        parts.append(
            '<tr>'
            f'<td style="padding:7px 12px 7px 0;border-bottom:1px solid #eee;color:#4b5563">{label}</td>'
            f'<td style="padding:7px 8px;border-bottom:1px solid #eee">{value}</td>'
            f'<td style="padding:7px 0;border-bottom:1px solid #eee;text-align:right">{chip(status)}</td>'
            '</tr>'
        )
    parts.append("</table>")

    parts.append(
        f'<p style="margin:18px 0 6px;color:#4b5563;font-size:14px">{new["combined"]["message"]}</p>'
    )
    parts.append(
        f'<p style="margin:18px 0 0"><a href="{DASHBOARD_URL}" '
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

    if is_inception:
        baseline_label = "since the dashboard went live"
    elif baseline_iso:
        baseline_label = f"since {baseline_iso[:10]}"
    else:
        baseline_label = f"since {ref}"

    subject = render_subject(new, changes)
    text = render_text(new, changes, baseline_label)
    html = render_html(new, changes, baseline_label)
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
