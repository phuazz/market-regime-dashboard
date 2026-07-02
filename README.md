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

Phase 2 of 7 complete (2026-07-02): Lens 1 is fully live — seven indicators,
each verified against two sources before first use, with scripted
re-verification for the automatable checks. Current read: five benign, LEI
on watch (six-month change negative), valuation shown as context only.
Phases 3–7 (Lens 3 trend, Lens 2 froth composite, conditional forward
returns, signal map, GitHub Actions automation) are planned and not yet
built.

All status thresholds are Navigo-chosen proposed defaults, held in
`data/thresholds.json` and marked in the UI, **pending confirmation by ZH
before go-live**.

## Architecture

```
template.html          Source of truth for the UI (< 200 KB, fetch fallback)
data/                  JSON per logical group; every data point carries
                       source_url, secondary_source_url, as_of, notes
data/history/          Series histories (fetched at runtime, never inlined).
                       FRED series carry full available history; scraped
                       headlines (PMI, LEI, CAPE) accumulate one point per
                       period because no licensed history is redistributed.
scripts/update_data.py Refreshes data/ (--group daily|monthly|quarterly)
scripts/lens1.py       Lens 1 classifiers and builders (pure logic + fetch)
scripts/verify_series.py Repeatable two-source verification checks
scripts/build.py       Injects data/ JSON into template.html -> docs/index.html
docs/                  GitHub Pages output. Generated, never hand-edited.
```

Indicator JSON follows the SPEC.md section 9 schema plus display fields
(`description`, `qualifier`, `cadence`, `signed`, `decimals`).

## Working on it

```
python scripts/update_data.py --group all     # refresh data/
python scripts/verify_series.py               # scripted two-source checks
python -m unittest discover -s tests          # date and threshold tests
python scripts/build.py                       # build docs/index.html
npx serve .                                   # dev: open template.html (fetch fallback)
npx serve docs                                # test the built output
```

## Data sources (live)

| Indicator | Series / source | Secondary source | Cadence |
|---|---|---|---|
| Yield curve (10yr − 3mo) | FRED `T10Y3M` | US Treasury par yield curve | Daily |
| Sahm Rule | FRED `SAHMREALTIME` | Recomputed from `UNRATE`; CMV cross-reference | Monthly |
| High-yield spreads | FRED `BAMLH0A0HYM2` | GuruFocus HY OAS page | Daily |
| Manufacturing PMI | S&P Global headline (ISM proxy; scrape with TradingEconomics fallback) | Press prints of the same release | Monthly |
| Leading indicators | Conference Board LEI public headline | PR Newswire release | Monthly |
| Labour market | FRED `UNRATE`, `PAYEMS`, `UEMP27OV`, `CCSA` | BLS public API; DOL release coverage | Monthly / weekly |
| Valuation (Shiller CAPE) | multpl.com daily print | GuruFocus monthly print | Daily (context only) |

Planned sources for later phases are listed in SPEC.md sections 5–6 and must
be verified per VERIFICATION.md before first use.

## Reference material

`reference/` holds layout reference only (no values are reused):
`header-overall-read.png`, `lens1-recession-rows.png`,
`lens2-froth-composite.png`, `lens2-froth-rows.png`, `lens2-lens3-trend.png`,
`glossary.png`, `signal-map.png`, and the source video memo PDF.

## Open issues

1. **Thresholds pending confirmation** — every parameter in
   `data/thresholds.json` is a proposed default; ZH to confirm before
   go-live. Two deserve specific attention: the labour-market internals rule
   (currently requires both long-term unemployed +15% YoY **and** continued
   claims +5% over 26 weeks; June 2026 data shows +17% YoY but claims flat,
   hence benign) and the HY OAS absolute anchors (next item).
2. **HY OAS history depth** — the keyless FRED endpoint serves the
   ICE-licensed spread series only from mid-2023, so status uses fixed
   absolute anchors (watch 4.00 / elevated 5.50 / complacency 3.00) rather
   than window percentiles. Alternative: a FRED API key (Actions secret)
   may serve full history; decision for ZH in phase 7.
3. **Sustained-inversion definition** — the strict rule (60 consecutive
   daily observations below zero) captures 2000, 2006–07, and 2022–24 but
   excludes the choppy 1989 and 2019 inversions. A days-in-window
   alternative would include them. Decide before the signal map and
   forward-return studies (phases 5–6) depend on it.
4. **Scrape fragility (PMI, LEI, CAPE)** — best-effort scrapers with
   fallbacks; a failed scrape retains the previous value and exits non-zero
   so automation surfaces it. The official S&P Global release blocks some
   fetchers; the TradingEconomics fallback supplied the June print
   (source_url records which supplier actually served each value).
5. **Lens 2 alarm level** — deliberately unset; ZH to choose in phase 4 from
   percentile-derived candidates.

*Last updated: 2026-07-02.*
