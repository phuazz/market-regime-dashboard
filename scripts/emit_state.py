"""emit_state.py — publish this repo's lens states in the STATE_CONTRACT shape.

WHAT THIS IS FOR
----------------
A private consumer (the command centre) renders these three lenses, and the
combined risk-reduction read they imply, beside signals from seven other
projects. Until now it did that by reaching INTO this repo and reading exact
JSON pointers out of lens1/lens2/lens3.json from its own side, AND by
re-implementing the combined rule in its own codebase. Both work, and both are
guarded there, but they leave knowledge that belongs here living somewhere
else: rename a key or change the firing rule, and the break surfaces over
there, days later, in a file nobody was editing at the time.

This writes `data/state.json` beside the data it describes, so a rename breaks
here, in this repo's CI, at the moment of the rename. It also mirrors the file
into `docs/data/state.json`, the copy actually served over HTTPS, so the
published contract cannot lag the committed one.

THE COMBINED READ, WHICH THIS REPO ALREADY COMPUTES
---------------------------------------------------
The consumer's contract records the combined signal as consumer-derived, with
a standing note that "a risk_reduction.json emitter would remove the derivation
from the consumer". That is what `regime_risk_reduction` below is. The rule is
unchanged and is the one this repo already displays:

    (Lens 1 elevated OR Lens 2 armed) AND Lens 3 confirming

with "confirming" meaning Lens 3 at `watch` or `elevated`. Both sides compute
it for now and the consumer compares them, so a disagreement between this
repo's rule and the consumer's is reported rather than silently resolved. That
comparison is the point of emitting it at all — until it has agreed for a
while, this is evidence, not authority.

THE FIRING RULES ARE READ FROM thresholds.json, NOT RESTATED
-------------------------------------------------------------
Lens 1 is worst-of over status indicators with `context` rows excluded, per
`_meta.lens1_firing_rule` in thresholds.json; Lens 2's alarm line lives in the
same file. Hard-coding either here would create a second place for a
calibrated number to live, and the 2026-07-04 Lens 1 calibration is exactly
the kind of decision that must not be duplicated into a copy nobody updates.

WHAT IT IS NOT
--------------
  * NOT a new signal and not a recalibration. Every value is copied or applies
    a rule this repo already documents. If this and the dashboard ever
    disagree, the dashboard is right and this is broken.
  * NOT load-bearing here. Nothing in this repo reads data/state.json.

NOTE ON COVERAGE. Since 2026-09-02 the refresh and digest workflows run
tests/test_emit_state.py under pytest, so it gates them (it was a local guard
only before that). The enforcing check on the emission itself is on the
consumer side, which validates every emission against its own registry and
rejects one that disagrees, and which compares this against its own
independent extraction on every run.

Usage:
    python scripts/emit_state.py           # write data/state.json
    python scripts/emit_state.py --check   # validate and print, write nothing
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OUT = DATA / "state.json"

CONTRACT_VERSION = "1"
SOURCE = "market-regime-dashboard"

COMMON = {"role": "risk-state", "horizon": "months",
          "evidence_grade": "adopted-gate", "licence": "public"}

# Statuses that carry a firing opinion. `context` rows (valuation) are excluded
# from the worst-of by the documented rule, not by omission.
SCORED = ("benign", "watch", "elevated")
RANK = {"benign": 0, "watch": 1, "elevated": 2}


class EmitError(Exception):
    """A required input was missing or malformed. Never emit a guess."""


def require(obj, path: str, kind=None):
    cur = obj
    for part in path.split("."):
        if part.endswith("]") and "[" in part:
            key, idx = part[:-1].split("[")
            if key:
                if not isinstance(cur, dict) or key not in cur:
                    raise EmitError(f"missing key `{key}` at pointer `{path}`")
                cur = cur[key]
            if not isinstance(cur, list):
                raise EmitError(f"`{key}` is not a list at pointer `{path}`")
            i = int(idx)
            if not cur or i >= len(cur) or i < -len(cur):
                raise EmitError(f"index [{idx}] out of range at pointer `{path}`")
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or part not in cur:
                raise EmitError(f"missing key `{part}` at pointer `{path}`")
            cur = cur[part]
    if cur is None:
        raise EmitError(f"pointer `{path}` is null")
    if kind is not None and not isinstance(cur, kind):
        want = kind.__name__ if isinstance(kind, type) else "/".join(k.__name__ for k in kind)
        raise EmitError(f"pointer `{path}` is {type(cur).__name__}, expected {want}")
    return cur


def load(name: str):
    p = DATA / name
    if not p.exists():
        raise EmitError(f"source file not found: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EmitError(f"{name} is not valid JSON: {exc}") from exc


def build() -> dict:
    l1, l2, l3 = load("lens1.json"), load("lens2.json"), load("lens3.json")

    # --- Lens 1: worst-of over status indicators, `context` excluded.
    inds = require(l1, "indicators", list)
    scored = [i for i in inds if i.get("status") in SCORED]
    if not scored:
        raise EmitError("lens1 has no status indicators after excluding `context` rows")
    worst = max(scored, key=lambda i: RANK[i["status"]])
    l1_dates = [i["as_of"] for i in scored if i.get("as_of")]
    if not l1_dates:
        raise EmitError("lens1 has no indicator as_of dates")
    l1_as_of = max(l1_dates)
    n_elev = sum(1 for i in scored if i["status"] == "elevated")
    n_watch = sum(1 for i in scored if i["status"] == "watch")

    # --- Lens 2: froth composite against its alarm line.
    share = require(l2, "composite.share_pct", (int, float))
    alarm_state = require(l2, "composite.alarm_state", str)
    if alarm_state not in ("below", "armed"):
        raise EmitError(f"lens2 alarm_state {alarm_state!r} outside {{below, armed}}")
    triggered = require(l2, "composite.triggered_count", int)
    gauges = require(l2, "composite.gauge_count", int)
    l2_inds = require(l2, "indicators", list)
    l2_dates = [i["as_of"] for i in l2_inds if i.get("as_of")]
    if not l2_dates:
        raise EmitError("lens2 has no indicator as_of dates")
    l2_as_of = max(l2_dates)

    # --- Lens 3: price-trend confirmation.
    l3_ind = require(l3, "indicators[0]", dict)
    l3_status = require(l3, "indicators[0].status", str)
    if l3_status not in SCORED:
        raise EmitError(f"lens3 status {l3_status!r} outside {SCORED}")
    l3_as_of = require(l3, "indicators[0].as_of", str)

    # --- The combined read this repo already displays.
    armed = worst["status"] == "elevated" or alarm_state == "armed"
    confirming = l3_status in ("watch", "elevated")
    combined = "ON" if (armed and confirming) else "OFF"

    hint = lambda s: "watch" if s != "benign" else "none"

    signals = {
        "regime_lens1": {
            "as_of": l1_as_of, "state": worst["status"], "value": None,
            "zone": f"{n_elev} elevated / {n_watch} watch of {len(scored)}",
            "action_hint": hint(worst["status"]), "cadence": "monthly",
            "source_file": "data/lens1.json", "computed_at": l1.get("updated_at"), **COMMON,
        },
        "regime_lens2": {
            "as_of": l2_as_of, "state": alarm_state, "value": share,
            "zone": f"{triggered} of {gauges} triggered",
            "action_hint": "watch" if alarm_state == "armed" else "none", "cadence": "daily",
            "source_file": "data/lens2.json", "computed_at": l2.get("updated_at"), **COMMON,
        },
        "regime_lens3": {
            "as_of": l3_as_of, "state": l3_status, "value": l3_ind.get("value"),
            "zone": l3_ind.get("name"), "action_hint": hint(l3_status), "cadence": "daily",
            "source_file": "data/lens3.json", "computed_at": l3.get("updated_at"), **COMMON,
        },
        "regime_risk_reduction": {
            "as_of": max(l1_as_of, l2_as_of, l3_as_of), "state": combined, "value": None,
            "zone": f"L1 {worst['status']} · L2 {alarm_state} · L3 {l3_status}",
            "action_hint": "watch" if combined == "ON" else "none", "cadence": "daily",
            "source_file": "data/lens1.json, data/lens2.json, data/lens3.json",
            "computed_at": l2.get("updated_at"), **COMMON,
        },
    }

    return {
        "contract_version": CONTRACT_VERSION,
        "emitted_by": SOURCE,
        "emitted_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "signals": signals,
    }


def unchanged(payload: dict) -> bool:
    """Same emission as the one on disk, apart from the run's own timestamp?

    `emitted_at` moves every run, so writing unconditionally would leave a diff
    every time and the workflow would commit a no-op on every run. Liveness does
    not need that commit: the consumer judges freshness from `as_of`, so a dead
    emitter still shows up there as a stale state.
    """
    if not OUT.exists():
        return False
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    strip = lambda d: {k: v for k, v in d.items() if k != "emitted_at"}
    return strip(prev) == strip(payload)


def published_for(out: Path) -> Path:
    """Where the served copy of `out` lives: docs/data/, the tree Pages serves.

    docs/ is generated, and build.py copies the whole data tree into it — but
    build.py runs in the refresh workflow, which finishes BEFORE the emitter.
    Leaving the mirror to the next build published a state a full cycle behind
    the committed one: measured 2026-09-12, docs/data/state.json still served
    11 September while data/state.json held 12 September. Whoever writes the
    contract publishes it.

    Derived from `out` rather than fixed, so a test that redirects OUT into a
    temporary directory redirects the mirror with it and cannot write into the
    repository's real docs/ tree.
    """
    return out.parent.parent / "docs" / "data" / out.name


def publish(text: str) -> bool:
    """Mirror the canonical emission into docs/. True when it wrote.

    Runs on the unchanged path too. The mirror falls behind whenever a build
    has not followed an emission, and an emission that changes nothing is
    exactly when nothing else would come along to fix it. Absent a docs/data
    directory it does nothing, which is what makes it inert under test.
    """
    target = published_for(OUT)
    if not target.parent.is_dir():
        return False
    if target.exists() and target.read_text(encoding="utf-8") == text:
        return False
    target.write_text(text, encoding="utf-8")
    return True


def _shown(path: Path) -> Path:
    try:
        return path.relative_to(REPO)
    except ValueError:
        return path


def main(argv: list[str]) -> int:
    try:
        payload = build()
    except EmitError as exc:
        print(f"emit_state: FAILED — {exc}", file=sys.stderr)
        print("emit_state: nothing written; the previous state.json is left as it was.",
              file=sys.stderr)
        return 1

    s = payload["signals"]
    print(f"emit_state: {len(s)} signal(s) — "
          f"L1 {s['regime_lens1']['state']}, L2 {s['regime_lens2']['state']}, "
          f"L3 {s['regime_lens3']['state']} → combined "
          f"{s['regime_risk_reduction']['state']} @ {s['regime_risk_reduction']['as_of']}")

    if "--check" in argv:
        print("emit_state: --check, nothing written.")
        return 0

    if unchanged(payload):
        print("emit_state: state unchanged since the last emission — leaving it as it is.")
        if publish(OUT.read_text(encoding="utf-8")):
            print(f"emit_state: refreshed {_shown(published_for(OUT))}, which had fallen behind.")
        return 0

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(f"emit_state: wrote {_shown(OUT)}")
    if publish(text):
        print(f"emit_state: published {_shown(published_for(OUT))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
