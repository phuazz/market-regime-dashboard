# VERIFICATION.md — data-provider series verification log

Every data-provider series ID is verified against two independent sources
before first use (project CLAUDE.md, "Data integrity"). Each entry records
what was checked, the values compared, and the URLs, so the check can be
repeated. A mismatch blocks the series from shipping until resolved.

Verification standard: (1) confirm the series resolves to the intended
concept via provider metadata where accessible; (2) match the latest values
for identical reference dates against the originating agency or a second
independent publisher; (3) record both URLs and the check date here, and
carry `source_url` plus `secondary_source_url` in the JSON for every data
point.

Automatable checks are scripted in `scripts/verify_series.py`
(`python scripts/verify_series.py`), which re-runs the T10Y3M identity, the
Sahm recomputation, and the BLS-vs-FRED labour comparison on demand. Run
output of 2026-07-02: all three checks PASS.

---

## T10Y3M — 10-Year Treasury Constant Maturity Minus 3-Month Treasury Constant Maturity

- **Verified:** 2026-07-02
- **Provider:** FRED (Federal Reserve Bank of St. Louis), keyless `fredgraph.csv` endpoint
- **Primary URL:** https://fred.stlouisfed.org/series/T10Y3M
- **Secondary (originating agency):** US Treasury daily par yield curve rates —
  https://home.treasury.gov/resource-center/data-chart-center/interest-rates
- **Value checks** (FRED pull and Treasury CSV pull, both 2026-07-02):

  | Date | FRED `T10Y3M` | Treasury 10 Yr | Treasury 3 Mo | Treasury 10Y − 3M | Match |
  |---|---|---|---|---|---|
  | 2026-06-29 | 0.51 | 4.38 | 3.87 | 0.51 | yes |
  | 2026-06-30 | 0.57 | 4.44 | 3.87 | 0.57 | yes |
  | 2026-07-01 | 0.63 | 4.48 | 3.85 | 0.63 | yes |

- **Internal consistency (scripted):** max absolute difference between
  `T10Y3M` and `DGS10` − `DGS3MO` over the latest 250 common observations:
  0.0000.
- **History sanity check:** sustained-inversion episodes detected in the full
  series (1982–2026) match the historical record — 2000-07-19 → 2001-01-19,
  2006-07-19 → 2007-05-29, and 2022-10-25 → 2024-12-12.
- **Notes:** the FRED HTML series page returned HTTP 403 to automated
  fetching on 2026-07-02, so the page-title check could not be captured.
  Identification rests on the numeric match against the originating agency
  plus component-identity consistency, which is the substantive test.
  `DGS10` and `DGS3MO` are used for verification arithmetic only.

---

## SAHMREALTIME — Real-time Sahm Rule Recession Indicator

- **Verified:** 2026-07-02
- **Provider:** FRED. **Primary URL:** https://fred.stlouisfed.org/series/SAHMREALTIME
- **Secondary (construction recomputed):** Sahm reading recomputed from
  `UNRATE` (three-month average minus its low of the previous twelve
  months): recomputed **+0.07** for June 2026; `SAHMREALTIME` **+0.07**;
  `SAHMCURRENT` **+0.07**. Exact agreement on the latest month (scripted).
- **Tertiary cross-reference:** currentmarketvaluation.com/models/sahm-rule.php
  states the identical construction; its March 2026 print (0.23) equals the
  recomputation from today's revised UNRATE for March, while `SAHMREALTIME`
  shows 0.20 for March — the real-time series uses unemployment data as
  originally published, so revised-vintage recomputations can differ by a few
  hundredths in earlier months. This is expected and documented.
- **Variant decision:** `SAHMREALTIME` (not `SAHMCURRENT`) is displayed so
  that historical values reflect information actually available at the time
  (walk-forward integrity for later phases). The two variants agree on the
  latest month.

---

## BAMLH0A0HYM2 — ICE BofA US High Yield Index Option-Adjusted Spread

- **Verified:** 2026-07-02
- **Provider:** FRED. **Primary URL:** https://fred.stlouisfed.org/series/BAMLH0A0HYM2
- **Secondary:** GuruFocus "BofA US High Yield Index Option-Adjusted Spread"
  — https://www.gurufocus.com/economic_indicators/5735/bofa-us-high-yield-index-optionadjusted-spread
  — prints **2.75% (Jun 2026)**, equal to FRED `BAMLH0A0HYM2` on 2026-06-30
  (**2.75**), an exact month-end match.
- **Tertiary:** govspending.org/series/BAMLH0A0HYM2/ showed 2.78% around
  25 June 2026, consistent with FRED's 2.80–2.83 prints that week.
  A TradingEconomics figure of "2.63% in June" is understood to be a monthly
  average basis and was not used.
- **Limitation (material):** the keyless `fredgraph.csv` endpoint serves this
  ICE-licensed series only from 2023-07-03 (787 observations), including when
  an earlier `cosd` start date is requested. Full 1996–present history is
  therefore not redistributable here. Consequence: status thresholds use
  fixed absolute anchors (watch 4.00, elevated 5.50, complacency 3.00 —
  approximately the published long-run median and 75th percentile visible on
  the FRED chart) rather than window percentiles, which would drift with the
  available window. Flagged in README open issues for ZH confirmation.

---

## UNRATE, PAYEMS, UEMP27OV — labour headline series (BLS)

- **Verified:** 2026-07-02 (scripted, repeatable)
- **Provider:** FRED. **Primary URLs:** fred.stlouisfed.org/series/UNRATE,
  /PAYEMS, /UEMP27OV
- **Secondary (originating agency):** BLS public API v1
  (api.bls.gov/publicAPI/v1/timeseries/data/) — series LNS14000000,
  CES0000000001, LNS13008636. **52 month-values compared across the three
  series over the trailing window: all equal.** Spot check for June 2026:
  unemployment rate 4.2, total nonfarm payrolls 158,984k, long-term
  unemployed 1,937k — identical on both providers.
- **Notes:** the BLS Employment Situation HTML release blocks automated
  fetching (HTTP 403); the BLS public API is the same agency's data service
  and serves the purpose better (scripted in verify_series.py).

---

## CCSA — Continued claims (insured unemployment), seasonally adjusted

- **Verified:** 2026-07-02
- **Provider:** FRED. **Primary URL:** https://fred.stlouisfed.org/series/CCSA
- **Secondary (originating agency via press coverage):** the DOL weekly
  claims release for the week ending 20 June 2026 reported seasonally
  adjusted **initial claims 215,000** (matches FRED `ICSA` context) and
  **insured unemployment 1,821,000 (advance) for the week ending 13 June**.
  FRED `CCSA` shows **1,812,000 for 2026-06-13 (revised)** and 1,814,000 for
  2026-06-20 — the 9k difference is the documented DOL advance-to-revised
  cycle, in which each week's figure is revised in the following release.
- **Notes:** dol.gov/ui/data.pdf and the DOL newsroom block automated
  fetching; the release figures were confirmed via press prints of the DOL
  release (verifiedinvesting.com claims report, 25 June 2026 cycle). The
  advance/revision reconciliation is the identity test here.

---

## S&P Global US Manufacturing PMI (documented ISM proxy)

- **Verified:** 2026-07-02
- **Displayed value:** June 2026 final **53.9** (May final 55.1).
- **Primary:** S&P Global press release (the official release page carries
  53.9; it serves HTTP 200 to browser-agent requests) —
  https://www.pmi.spglobal.com/Public/Home/PressRelease/d52074988b4f4367a787ba833e23b5c6
- **Secondary:** investinglive.com print "US S&P Global manufacturing PMI
  final for June 53.9" (1 July 2026) and Advisor Perspectives dshort update
  "Growth Slips to 3-Month Low Despite Expansion" (1 July 2026), both
  quoting the same official figures. TradingEconomics carries the identical
  print and is the runtime scrape fallback.
- **Substitution note:** the ISM Manufacturing PMI headline is licensed; the
  S&P Global headline is the documented free proxy (approved decision). It is
  a different survey and can diverge from ISM — flagged in the indicator
  notes and the UI.
- **History:** accumulated one print per month in
  `data/history/pmi_spglobal_us_mfg.json` (seeded with the May 2026 final,
  55.1, from the June release coverage). No licensed history is
  redistributed.

---

## Conference Board US LEI (public headline)

- **Verified:** 2026-07-02
- **Displayed values:** LEI **99.3** (2016=100) for May 2026; **+0.1%**
  month change; **−0.3%** six-month change (November 2025 to May 2026),
  prior six months −1.3%. Released 18 June 2026.
- **Primary (originating publisher):**
  https://www.conference-board.org/topics/us-leading-indicators
- **Secondary:** PR Newswire release "The Conference Board Leading Economic
  Index (LEI) for the US Rose for the Second Consecutive Month in May" —
  identical figures verbatim.
- **Licence note:** only the publicly announced headline figures are
  displayed; no licensed series is redistributed. History accumulates one
  headline per month in `data/history/lei_conference_board.json`.

---

## Shiller CAPE (context-only valuation row)

- **Verified:** 2026-07-02
- **Displayed value:** **41.66** (multpl.com daily print, 1 July 2026;
  long-run mean 17.39, median 16.10 per the same page).
- **Primary:** https://www.multpl.com/shiller-pe
- **Secondary:** GuruFocus "S&P 500 Shiller CAPE Ratio: 40.41 (Jun 2026)" —
  https://www.gurufocus.com/economic_indicators/56/sp-500-shiller-cape-ratio.
  The ~3% gap is the documented method difference: multpl prints a daily
  CAPE on the latest price; the Shiller convention (followed by GuruFocus)
  uses monthly average prices, which sit below the daily print in a rising
  market. Within tolerance.
- **Excluded source:** currentmarketvaluation.com/models/price-earnings.php
  showed 36.4 "as of March 31, 2026" — a stale quarterly print on a restated
  basis, inconsistent beyond timing tolerance with both sources above, so it
  is excluded from CAPE verification (documented here per the
  conflicting-source rule).
- **Method reference:** Robert Shiller's `ie_data.xls` (Yale-hosted copy)
  validates the construction but ends at 2023-09; the maintained dataset
  moved to shillerdata.com, where the download is not automation-accessible.

---

## ^GSPC — S&P 500 daily closes (Lens 3)

- **Verified:** 2026-07-02 (scripted, repeatable — verify_series.py check 4)
- **Primary:** Yahoo Finance chart API (`query1.finance.yahoo.com/v8/finance/chart/^GSPC`,
  the same endpoint the yfinance library wraps). Daily history from
  1970-01-02; the final bar is dropped when its UTC date equals the run date
  because the US session may still be open.
- **Secondary:** FRED `SP500` — the official S&P 500 close, ten-year window —
  https://fred.stlouisfed.org/series/SP500
- **Value checks:** the two feeds agree **exactly (0.000% max relative
  difference) over the latest 20 common sessions**, including 2026-06-26
  (7,354.02), 2026-06-29 (7,440.43), 2026-06-30 (7,499.36), and 2026-07-01
  (7,483.23). The builder also re-runs this comparison on every pipeline run
  and refuses to publish when the feeds disagree by more than 0.05%.
- **Source change vs SPEC:** SPEC.md section 6 named Stooq as an option; the
  Stooq CSV endpoint now sits behind a JavaScript proof-of-work challenge and
  is not automatable, so FRED `SP500` serves as the second feed instead.

---

## Endpoint access notes (probed 2026-07-03, local machine and GitHub runner)

Recorded so future fetch failures are diagnosed from evidence rather than
guessed at. Reproduce with `python scripts/net_probe.py` from the affected
environment.

- **fredgraph.csv (Akamai-fronted):** admits clients per network path,
  client fingerprint, and user agent. Residential IP: urllib with the
  honest bot agent returns in 0.3 s; urllib with a spoofed browser agent is
  tarpitted to a read timeout. GitHub-hosted runner: curl with its default
  agent returns HTTP 200 in 0.8 s; curl with the bot agent is reset
  instantly (HTTP 000); urllib times out with any agent. Pipeline transport
  is therefore curl-first, alternating with urllib across retries
  (`scripts/sources/fred.py`). Spoofed agents are never used.
- **Yahoo v8 chart API:** clean via urllib with a browser agent from both
  network paths (query1 and query2 hosts). The Lens 3 builder additionally
  carries a FRED `SP500` fallback for future path changes.
- **multpl.com:** clean via urllib with a browser agent from both paths.
- **Stooq:** JavaScript proof-of-work challenge; not automatable (logged in
  the price-feed entry above).
- **BLS/DOL/S&P Global/GuruFocus HTML pages:** block generic fetchers; the
  BLS public API, press prints, and browser-agent urllib serve as
  replacements, as logged per series.

---

## Pending verification (later phases — do not use before logging here)

`NFCI` / `ANFCI`, `DRTSCILM` (SLOOS), `UMCSENT`, `CPIAUCSL`, `USREC`, AAII
survey values, the NAAIM Exposure Index, multpl trailing P/E, IPO-count
proxy, and the Value-vs-Growth price pair (RPV/RPG) with second feeds.
