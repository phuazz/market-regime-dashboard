"""Update data/ JSON files from sourced public data.

Usage:
    python scripts/update_data.py [--group daily|monthly|quarterly|all]

Builders live in lens-specific modules (scripts/lens1.py and, in later
phases, lens2/lens3). Every indicator carries source_url,
secondary_source_url, and as_of (SPEC.md section 9); every series ID is
verified against two independent sources before first use (VERIFICATION.md).

A failing builder is non-fatal: its previous JSON entry is preserved (the
merge below is by indicator id), the error is printed, and the process exits
non-zero so automation surfaces the failure. A scrape breaking upstream
therefore degrades to a stale-but-sourced value, never a wrong one.
"""
from __future__ import annotations

import argparse

import lens1
import lens3
from util import CANONICAL_ORDER, DATA_DIR, LENS_TITLES, ROOT, dump_json, load_json, utc_now_iso

# One registry across all lens modules, keyed by cadence group.
GROUPS: dict[str, list] = {
    group: lens1.GROUPS[group] + lens3.GROUPS[group]
    for group in ("daily", "monthly", "quarterly")
}


def update_lens_file(lens: int, built: list[dict]) -> str:
    """Merge freshly built indicators into data/lens<N>.json by id."""
    path = DATA_DIR / f"lens{lens}.json"
    existing = load_json(path) or {}
    by_id = {ind["id"]: ind for ind in existing.get("indicators", [])}
    for ind in built:
        by_id[ind["id"]] = ind
    order = CANONICAL_ORDER[lens]
    indicators = [by_id[i] for i in order if i in by_id]
    indicators += [ind for key, ind in by_id.items() if key not in order]

    title, subtitle = LENS_TITLES[lens]
    dump_json(path, {
        "lens": lens,
        "title": title,
        "subtitle": subtitle,
        "updated_at": utc_now_iso(),
        "indicators": indicators,
    })
    return str(path.relative_to(ROOT))


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
    failures: list[str] = []
    for group in groups:
        for builder in GROUPS[group]:
            try:
                indicator = builder(thresholds)
            except Exception as error:  # noqa: BLE001 — isolate per-builder failures
                failures.append(f"{builder.__name__}: {error}")
                print(f"ERROR {builder.__name__}: {error}")
                continue
            built_by_lens.setdefault(indicator["lens"], []).append(indicator)
            print(f"built {indicator['id']}: {indicator['status']} "
                  f"({indicator['value']} as of {indicator['as_of']})")

    for lens, built in sorted(built_by_lens.items()):
        path = update_lens_file(lens, built)
        print(f"wrote {path} ({len(built)} indicator(s) refreshed)")

    if failures:
        print(f"{len(failures)} builder(s) failed; previous values retained for those rows.")
        return 1
    if not built_by_lens:
        print("No builders registered for the requested group; nothing to do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
