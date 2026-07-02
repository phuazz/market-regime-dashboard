# Navigo Recession & Market-Peak Dashboard

A three-lens macro dashboard — recession risk, market-peak froth, and
price-trend confirmation — built entirely from sourced public data. Internal
Navigo IC grade now; structured for later promotion to client-facing without
a rebuild. The design brief is [SPEC.md](SPEC.md); operating constraints are
[CLAUDE.md](CLAUDE.md); series verification is logged in
[VERIFICATION.md](VERIFICATION.md).

The taxonomy and layout are inspired by a public reference dashboard (see
`reference/`); every threshold, weight, and value is rebuilt independently
from public data. No proprietary third-party values are reproduced.

## Status

Phase 1 of 7 complete (2026-07-02): repository scaffold plus one indicator —
the 10-year minus 3-month yield curve — wired end to end from FRED through
`data/` and `scripts/build.py` to `docs/index.html`, with the standalone
fetch fallback working. Phases 2–7 (full Lens 1, Lens 3 trend, Lens 2 froth
composite, conditional forward returns, signal map, GitHub Actions
automation) are planned and not yet built.

All status thresholds are Navigo-chosen proposed defaults, held in
`data/thresholds.json` and marked in the UI, **pending confirmation by ZH
before go-live**.

## Architecture

```
template.html          Source of truth for the UI (< 200 KB, fetch fallback)
data/                  JSON per logical group; every data point carries
                       source_url, secondary_source_url, as_of, notes
data/history/          Full series histories (fetched at runtime, never inlined)
scripts/update_data.py Refreshes data/ from public sources (--group daily|monthly|quarterly)
scripts/build.py       Injects data/ JSON into template.html -> docs/index.html
docs/                  GitHub Pages output. Generated, never hand-edited.
```

## Working on it

```
python scripts/update_data.py --group daily   # refresh data/
python -m unittest discover -s tests          # date edge-case and logic tests
python scripts/build.py                       # build docs/index.html
npx serve .                                   # dev: open template.html (fetch fallback)
npx serve docs                                # test the built output
```

## Data sources (live)

| Indicator | Series | Primary source | Secondary source | Cadence |
|---|---|---|---|---|
| Yield curve (10yr − 3mo) | FRED `T10Y3M` | fred.stlouisfed.org/series/T10Y3M | US Treasury daily par yield curve | Daily |

Planned sources for later phases are listed in SPEC.md sections 4–6 and must
be verified per VERIFICATION.md before first use.

## Reference material

`reference/` holds layout reference only (no values are reused):
`header-overall-read.png`, `lens1-recession-rows.png`,
`lens2-froth-composite.png`, `lens2-froth-rows.png`, `lens2-lens3-trend.png`,
`glossary.png`, `signal-map.png`, and the source video memo PDF.

## Open issues

1. **Thresholds pending confirmation** — every parameter in
   `data/thresholds.json` is a proposed default; ZH to confirm before
   go-live.
2. **Sustained-inversion definition** — the strict rule (60 consecutive
   daily observations below zero) captures 2000, 2006–07, and 2022–24 but
   excludes the choppy 1989 and 2019 inversions, which repeatedly crossed
   zero. A days-in-window alternative (for example, at least 45 negative
   observations within a trailing 90) would include them. Decision needed in
   phase 2, before the signal map and forward-return studies depend on it.
3. **FRED HTML pages return 403 to automated fetching** — series identity
   checks rest on numeric matching against originating agencies, documented
   per series in VERIFICATION.md.
4. **Lens 2 alarm level** — deliberately unset; ZH to choose in phase 4 from
   percentile-derived candidates.

*Last updated: 2026-07-02.*
