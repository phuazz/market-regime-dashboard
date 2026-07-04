# Recession & Market-Peak Dashboard

A three-lens macro dashboard — recession risk, market-peak froth, and
price-trend confirmation — built entirely from sourced public data. Internal
IC grade now; structured for later promotion to client-facing without
a rebuild. The design brief is [SPEC.md](SPEC.md); operating constraints are
[CLAUDE.md](CLAUDE.md); series verification is logged in
[VERIFICATION.md](VERIFICATION.md).

The taxonomy and layout are inspired by a public reference dashboard (see
`reference/`); every threshold, weight, and value is rebuilt independently
from public data. No proprietary third-party values are reproduced.

## Status

**All seven build phases are complete** (2026-07-03). **Live at
https://phuazz.github.io/market-regime-dashboard/** with scheduled GitHub
Actions refreshes. All three lenses are live: Lens 1 (seven recession-risk
indicators), Lens 2 (eight froth gauges plus a SLOOS context row, composite
= share triggered, alarm confirmed at 62.5%), and Lens 3 (50-day vs
150-day SMA with an inline-SVG chart; Yahoo feed cross-checked against FRED
`SP500` on every run). The combined read is live: the Lens 2 alarm was
adopted at 62.5% (5 of 8 gauges) on 2026-07-03 from the filed calibration
study in `reviews/`, and the risk-reduction signal (Lens 1 elevated or Lens 2 at alarm,
confirmed by Lens 3) renders prominently on the page. The current read is
on the live page. Phase 5 is live: conditional forward-return panels per
lens and for the risk-reduction signal (point-in-time reconstruction 1970–2026, filed
in `reviews/2026-07-03_forward-returns.md`; recompute on demand with
`python scripts/forward_returns.py` — deliberately not in the scheduled
workflows). Phase 6 is live: the signal map (log-scale S&P 500 from 1990
with NBER recession shading via verified `USREC`, Lens 1 elevated bands,
Lens 2 alarm crossings, and risk-reduction-signal strips; regenerate with
`python scripts/signal_map.py`). The map starts 1990 rather than SPEC
section 8's 2006 so the dot-com episode — the strongest signal case —
stays visible.

All status thresholds are independently chosen parameters held in
`data/thresholds.json`, **confirmed by ZH on 2026-07-03** for the
proof-of-concept phase (the yield-curve sustained-inversion definition and
the HY OAS absolute anchors were accepted with documented caveats — see the
`_meta` block). The Lens 2 alarm and the Lens 1 firing bar are backed by
filed calibrations in `reviews/`.

## Automation and publication

GitHub Pages serves `docs/` from `main` at
https://phuazz.github.io/market-regime-dashboard/. Two workflows keep it
fresh (`.github/workflows/`):

- **daily.yml** — weekdays 23:30 UTC (07:30 Singapore next morning), after
  the US close: yield curve, HY OAS, labour internals, S&P 500 trend.
- **monthly.yml** — Mondays 12:00 UTC: Sahm rule, PMI proxy, LEI headline,
  Shiller CAPE. Monthly prints land on scattered days, so a weekly poll
  catches each within seven days; the history files append at most one
  point per reference month.

Both run the offline tests first, commit only when data changed, and mark
the run failed if any builder failed — in that case the affected rows keep
their previous values (stale-but-sourced, with the run visible in the
Actions tab). The `reference/` folder and this machine's local files are
not needed by automation. Local sessions should start with
`git pull --rebase origin main` to pick up bot commits.

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
scripts/lens3.py       Lens 3 SMA trend logic (ported from equity-defense-dashboard)
scripts/verify_series.py Repeatable two-source verification checks
scripts/build.py       Injects data/ JSON into template.html -> docs/index.html
docs/                  GitHub Pages output. Generated, never hand-edited.
```

Indicator JSON follows the SPEC.md section 9 schema plus display fields
(`description`, `qualifier`, `cadence`, `signed`, `decimals`).

## Charts

Every indicator row with a history file expands in place (the "History"
toggle) to a Plotly time-series chart — styled per the vault design system
(`C:\dev\design.md`), all charts (rows, Lens 3 SMA, and the signal map)
migrated to Plotly with unified hover. Each chart carries: the active
threshold lines (drawn from `data/thresholds.json`, including build-time
computed levels for the percentile-calibrated gauges); NBER recession
bands, plus S&P bear-market bands on the Lens 2 froth gauges; a statistics
strip (latest value as an ordinal percentile of its own history, median,
dated extremes); and a series-page drill-down link. Histories are
lazy-fetched per chart from `data/history/`; the page degrades gracefully
when the CDN is unreachable.

**History depth by source class:**
- **Full public history** — FRED series (decades), plus Shiller CAPE and
  trailing P/E (public Shiller-lineage data, monthly since 1871 via the
  multpl by-month tables), the RPG−RPV value/growth spread (computed from
  Yahoo closes, daily since 2006), and US IPO proceeds (Renaissance annual,
  from 2016).
- **Accumulating** — the four survey-provider gauges whose licences forbid
  redistributing back-history (AAII, NAAIM, S&P Global PMI, Conference
  Board LEI). These show a clean status panel until enough points
  accumulate (from July 2026), then plot; their full histories are used
  in-memory for calibration but never written to the repo.

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
| S&P 500 trend (Lens 3) | Yahoo chart API `^GSPC` (daily, from 1970) | FRED `SP500`, checked on every run | Daily |
| Consumer confidence (Lens 2) | FRED `UMCSENT` (CB proxy) | Michigan release press prints | Monthly |
| Retail euphoria (Lens 2) | AAII workbook, current week + in-memory decile calibration | AAII weekly article | Weekly |
| Manager bullishness (Lens 2) | NAAIM public headline | Aggregator mirrors (lagged) | Weekly |
| Growth-expectation froth (Lens 2) | multpl trailing P/E vs its own 1871 table | Provider dispersion documented | Daily |
| Rule of 20 (Lens 2) | multpl P/E + FRED `CPIAUCSL` | BLS API for CPI | Monthly |
| Deal & IPO froth (Lens 2) | Renaissance Capital stats page | Matches the published annual record | Monthly |
| Value vs growth (Lens 2) | `RPG` − `RPV` six-month spread (Yahoo) | Verified Yahoo endpoint; tickers confirmed | Daily |
| Credit complacency (Lens 2) | FRED `NFCI` percentile | Chicago Fed CSV (vintage-tolerant) | Weekly |
| Tightening credit (Lens 2, context) | FRED `DRTSCILM` | Fed SLOOS release | Quarterly |
| Recession shading (signal map) | FRED `USREC` | NBER business-cycle chronology | On demand |

Planned sources for the remaining phases are listed in SPEC.md sections 7–8
and must be verified per VERIFICATION.md before first use.

## Reference material

`reference/` holds layout reference only (no values are reused):
`header-overall-read.png`, `lens1-recession-rows.png`,
`lens2-froth-composite.png`, `lens2-froth-rows.png`, `lens2-lens3-trend.png`,
`glossary.png`, `signal-map.png`, and the source video memo PDF.

The folder is **local-only and git-ignored**: it contains third-party
dashboard screenshots and an internal memo, so it is excluded from the
public repository and from git history. SPEC.md references to
`reference/...` therefore resolve only on machines holding a local copy.

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
   may serve full history; standing decision for ZH.
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
5. **Lens 2 alarm level — decided.** Adopted at 62.5% (5 of 8) by ZH on
   2026-07-03 from the filed calibration
   (`reviews/2026-07-03_lens2-alarm-calibration.md`): an arming line for
   Lens 3 confirmation, not a standalone signal. Re-run the calibration at
   any gauge addition or removal. Two Lens 2 items remain for future
   review: the IPO gauge is coarse by construction (Renaissance history
   from 2016, seasonal annualisation), and the P/E gauge is
   within-methodology consistent on multpl's as-reported basis (provider
   levels differ; see VERIFICATION.md).
6. **Stooq blocked** — the Stooq CSV endpoint named in SPEC.md now requires a
   JavaScript proof-of-work and is not automatable; FRED `SP500` serves as
   the S&P second feed instead (exact agreement with Yahoo; see
   VERIFICATION.md). Price history starts 1970 (Yahoo daily), which covers
   the phase 5–6 studies.
7. **FRED endpoint fingerprint rules** — the CDN in front of
   `fredgraph.csv` admits clients per (network path, client fingerprint,
   user agent): python-urllib is tarpitted from datacentre IPs with any
   agent, and a spoofed browser agent is tarpitted from residential IPs,
   while curl under its own identity passes everywhere tested. The fetcher
   is therefore curl-first with a urllib fallback (`scripts/sources/fred.py`);
   probe with `python scripts/net_probe.py` before changing any transport.
   Evidence logged in VERIFICATION.md (2026-07-03).

*Last updated: 2026-07-03.*
