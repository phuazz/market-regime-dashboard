"""Update data/ JSON files from sourced public data.

Usage:
    python scripts/update_data.py [--group daily|monthly|quarterly|all]

Builders live in lens-specific modules (scripts/lens1.py, lens2.py, lens3.py).
Every indicator carries source_url, secondary_source_url, and as_of (SPEC.md
section 9); every series ID is verified against two independent sources before
first use (VERIFICATION.md).

A failing builder is non-fatal: its previous JSON entry is preserved (the merge
below is by indicator id), the error is printed, and the process exits non-zero
so automation surfaces the failure. A scrape breaking upstream therefore
degrades to a stale-but-sourced value, never a wrong one.

Stale, however, is only safe if it is visible. Retaining the previous entry
silently is what let the Conference Board LEI row read "watch, six-month -0.3%,
as of May 2026" for four weeks after the reading had turned positive: the
builder raised rather than guessing, the workflow exited 1, and the row on the
page looked exactly like a current one. So a retained row is now marked, and
past a per-group budget it is parked on the same terms the NAAIM row already
uses -- demoted to context so it cannot fire a trigger, dropped from the Lens 2
composite, and carrying a message that says how long it has been failing and
why. Parking reverses itself on the first successful rebuild.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import lens1
import lens2
import lens3
from util import CANONICAL_ORDER, DATA_DIR, LENS_TITLES, ROOT, dump_json, load_json, utc_now_iso

# One registry across all lens modules, keyed by cadence group.
GROUPS: dict[str, list] = {
    group: lens1.GROUPS[group] + lens2.GROUPS[group] + lens3.GROUPS[group]
    for group in ("daily", "monthly", "quarterly")
}

LENSES = (1, 2, 3)

# How long a row may go without a successful rebuild before it is parked. The
# budget is set by how often the row is POLLED, not by how often the underlying
# series prints. The monthly and quarterly groups are polled weekly, so two
# missed polls plus slack is the point at which "the refresh did not run" stops
# being a blip and starts being a break; the daily group gets four days on the
# same reasoning. A budget on as_of would not work: as_of is a reference date,
# so a perfectly fresh LEI row is dated the first of the reference month and is
# already eight weeks old on the day it is published.
PARK_AFTER_DAYS = {"daily": 4, "monthly": 16, "quarterly": 16}

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_timestamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def mark_retained(row: dict, group: str, reason: str, now: datetime | None = None) -> dict:
    """Return a copy of a retained row annotated with why it did not refresh.

    `now` is injectable for tests only; datetime is immutable and cannot be
    monkeypatched, and every decision here is a date difference.

    The clock starts at the first failed run rather than at the row's as_of,
    and it survives repeated failures: `stale.since` is written once and read
    back on every subsequent run, so the age is the true length of the outage.

    Below the budget the row is left exactly as it was and only the bookkeeping
    is written, because a single failed poll is a blip, not a stale reading, and
    flipping a row to context on a transient network error would move the Lens 2
    composite for no reason. Past the budget the row parks:

      * status becomes "context", which the lens roll-ups and the digest both
        exclude, so a reading nobody can refresh cannot fire a trigger;
      * in_composite goes False where the key exists, so it cannot drive the
        Lens 2 share either. Lens 1 rows have no such key and do not gain one;
      * the value and as_of are left alone. They are the last successful read,
        they are dated, and showing them beside the message is more honest than
        blanking them -- the same call the NAAIM parked row made.
    """
    now = now or datetime.now(timezone.utc)
    stale = dict(row.get("stale") or {})
    # First mark of an outage: the row still holds its real status here, which
    # is the only moment it can be captured.
    if "since" not in stale:
        stale["kind"] = "builder_failure"
        stale["since"] = now.strftime(_TIMESTAMP_FORMAT)
        stale["status_before"] = row.get("status")
        if "in_composite" in row:
            stale["was_in_composite"] = row["in_composite"]

    days = (now - _parse_timestamp(stale["since"])).days
    parked = days >= PARK_AFTER_DAYS[group]
    stale.update({"days": days, "reason": reason, "group": group, "parked": parked})

    marked = {**row, "stale": stale}
    if parked:
        since_date = stale["since"][:10]
        stale["message"] = (
            f"STALE — the refresh for this row has failed since {since_date} ({days} days), so "
            f"the value and date shown are its last successful read rather than a current one. "
            f"The row is demoted to context and sits outside the lens roll-up until a refresh "
            f"succeeds, which happens automatically. Reason: {reason}"
        )
        marked["status"] = "context"
        if "in_composite" in marked:
            marked["in_composite"] = False
    return marked


def update_lens_file(lens: int, built: list[dict], thresholds: dict,
                     marks: dict[str, tuple[str, str]] | None = None,
                     now: datetime | None = None) -> str:
    """Merge freshly built indicators into data/lens<N>.json by id.

    `marks` maps the id of a row whose builder failed this run to its (group,
    reason). Those rows are annotated before the composite is computed, so a
    parked gauge is already out of the share it would otherwise distort.
    """
    path = DATA_DIR / f"lens{lens}.json"
    existing = load_json(path) or {}
    by_id = {ind["id"]: ind for ind in existing.get("indicators", [])}
    for ind in built:
        by_id[ind["id"]] = ind
    for ind_id, (group, reason) in (marks or {}).items():
        if ind_id in by_id:
            by_id[ind_id] = mark_retained(by_id[ind_id], group, reason, now)
    order = CANONICAL_ORDER[lens]
    indicators = [by_id[i] for i in order if i in by_id]
    indicators += [ind for key, ind in by_id.items() if key not in order]

    title, subtitle = LENS_TITLES[lens]
    payload = {
        "lens": lens,
        "title": title,
        "subtitle": subtitle,
        "updated_at": utc_now_iso(),
        "indicators": indicators,
    }
    if lens == 2:
        alarm = thresholds.get("lens2_composite", {}).get("alarm_share_pct")
        payload["composite"] = lens2.summarise(indicators, alarm)
    dump_json(path, payload)
    # Reported relative to the repo when it sits inside it, absolute otherwise
    # (the tests point DATA_DIR at a temporary directory).
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def attribute_failures(failures: list[tuple[str, str, str]]) -> tuple[dict, list[str]]:
    """Map each failed builder to the row it produces, via the row's own record.

    Every successfully built row records the builder that produced it, so the
    mapping is derived from output rather than kept in a second registry that
    could silently disagree with it. The cost is that a builder which has never
    succeeded cannot be attributed; those are returned separately and reported
    rather than passed over, because an unmarkable row is exactly the silent
    staleness this is meant to end.
    """
    by_builder = {name: (group, reason) for name, group, reason in failures}
    marks: dict[int, dict[str, tuple[str, str]]] = {}
    attributed: set[str] = set()
    for lens in LENSES:
        for row in (load_json(DATA_DIR / f"lens{lens}.json") or {}).get("indicators", []):
            if row.get("builder") in by_builder:
                marks.setdefault(lens, {})[row["id"]] = by_builder[row["builder"]]
                attributed.add(row["builder"])
    return marks, sorted(set(by_builder) - attributed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        choices=["daily", "monthly", "quarterly", "all"],
        default="all",
        help="Which cadence group to refresh (default: all).",
    )
    args = parser.parse_args(argv)
    groups = ["daily", "monthly", "quarterly"] if args.group == "all" else [args.group]

    thresholds = load_json(DATA_DIR / "thresholds.json")
    if thresholds is None:
        raise SystemExit("data/thresholds.json is missing; it must exist before updating data.")

    built_by_lens: dict[int, list[dict]] = {}
    failures: list[tuple[str, str, str]] = []
    for group in groups:
        for builder in GROUPS[group]:
            try:
                indicator = builder(thresholds)
            except Exception as error:  # noqa: BLE001 — isolate per-builder failures
                failures.append((builder.__name__, group, str(error)))
                print(f"ERROR {builder.__name__}: {error}")
                continue
            # Recorded so a later failure of this builder can find its row.
            indicator["builder"] = builder.__name__
            built_by_lens.setdefault(indicator["lens"], []).append(indicator)
            print(f"built {indicator['id']}: {indicator['status']} "
                  f"({indicator['value']} as of {indicator['as_of']})")

    marks, unattributed = attribute_failures(failures)
    for name in unattributed:
        print(f"WARNING {name} failed and no existing row records it as its builder; "
              f"that row cannot be marked stale. It will be markable once the builder succeeds once.")

    for lens in sorted(set(built_by_lens) | set(marks)):
        path = update_lens_file(lens, built_by_lens.get(lens, []), thresholds, marks.get(lens))
        built_count = len(built_by_lens.get(lens, []))
        marked = marks.get(lens, {})
        parked = [i for i in (load_json(DATA_DIR / f"lens{lens}.json") or {}).get("indicators", [])
                  if i["id"] in marked and (i.get("stale") or {}).get("parked")]
        suffix = f", {len(marked)} retained ({len(parked)} parked)" if marked else ""
        print(f"wrote {path} ({built_count} indicator(s) refreshed{suffix})")
        for row in parked:
            print(f"  PARKED {row['id']}: not refreshed for {row['stale']['days']} days")

    if failures:
        print(f"{len(failures)} builder(s) failed; previous values retained for those rows.")
        return 1
    if not built_by_lens:
        print("No builders registered for the requested group; nothing to do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
