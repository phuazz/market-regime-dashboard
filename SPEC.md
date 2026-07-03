# SPEC.md — Recession & Market-Peak Dashboard

## 1. Purpose and audience
A single-page dashboard giving three lenses on bear-market risk:

1. **Recession risk** — is the economy turning?
2. **Market-peak froth** — is the market priced and positioned like a top?
3. **Price trend** — is the market actually rolling over?

Audience: internal IC and personal use now. Design and copy must be factual and fully sourced
so the page can be promoted to client-facing later. Do not assert a house view. Leave a
clearly marked disclaimer placeholder in the footer of `template.html` for later completion; do not
draft compliance or marketing language now.

The design is inspired by Adam Khoo's three-lens dashboard (see `reference/`). The taxonomy and
layout are borrowed; **all thresholds, weights, and values are rebuilt independently from public
data.** Do not reproduce his proprietary numbers.

## 2. Combining logic (the actionable rule)
- A single lens firing is **not** an act signal.
- Act rule: Lens 1 elevated **OR** Lens 2 at or above its alarm level, **then confirmed by** Lens 3
  (trend rollover). Only the combination is actionable.
- The action when confirmed is **reduce risk, not liquidate** — the signals carry false positives.
- Display each lens status independently and show the combined read prominently at the top.

## 3. Thresholds
All thresholds below are **proposed defaults, to be confirmed by ZH** before go-live. They are
documented and auditable, not inherited from any third party. Mark each threshold in the UI as an
independently chosen parameter.

## 4. Lens 1 — Recession risk
Leading and coincident indicators of an economic downturn. Status: benign / watch / elevated.

| Indicator | Source (verify series ID) | Cadence | Proposed status logic |
|---|---|---|---|
| Yield curve (10yr − 3mo) | FRED `T10Y3M` | Daily | < 0 = watch; sustained inversion then re-steepening = elevated |
| Sahm Rule | FRED `SAHMREALTIME` (confirm vs `SAHMCURRENT`) | Monthly | ≥ 0.50 = elevated; 0.35–0.50 = watch |
| High-yield credit spreads (HY OAS) | FRED `BAMLH0A0HYM2` | Daily | Rapid widening or above long-run median = watch/elevated; very tight = complacency note |
| ISM Manufacturing PMI | ISM (licensed). Free proxy: S&P Global US Mfg PMI or regional Fed surveys | Monthly | < 50 = watch; falling and < 48 = elevated |
| Leading indicators | Conference Board LEI (licensed). Use published 6-mo growth rate or a constructed proxy | Monthly | 6-mo growth deeply negative = elevated |
| Labour market | FRED `UNRATE`, `PAYEMS`, plus internals `UEMP27OV`, `CCSA` | Monthly / weekly | Rising unemployment trend + softening internals = watch |
| Valuation (Shiller CAPE) | multpl.com or Shiller Yale data; cross-check GuruFocus | Monthly | Context only — high level flagged, but **not** a timing trigger |

Notes:
- ISM headline and Conference Board LEI / Consumer Confidence are licensed and not cleanly free on
  FRED. Use documented free proxies and flag the substitution in `notes`.
- Valuation is a long-run-return caveat, not a recession timer. Label it as such.

## 5. Lens 2 — Market-peak froth
Public-data gauges of euphoria and complacency. Each is "triggered" or "not". Composite = share of
indicators triggered. Alarm level: **ZH to set** (do not default to 80%).

| Indicator | Source (verify) | Cadence | Trigger logic |
|---|---|---|---|
| Consumer confidence | Conference Board CC (licensed). Free proxy: FRED `UMCSENT` | Monthly | Elevated relative to history |
| Retail euphoria | AAII bull-bear survey (aaii.com) | Weekly | Bulls-minus-bears in top decile |
| Manager bullishness | NAAIM Exposure Index (naaim.org) | Weekly | Near or above 90–100 (all-in) |
| Growth-expectation froth | Forward P/E percentile — vendor feed; free proxy: trailing P/E from multpl | Monthly | High historical percentile |
| Deal & IPO froth | Needs a free proxy: IPO count (Stock Analysis / Renaissance) or SIFMA issuance | Monthly/Qtrly | Issuance at cycle highs |
| Rule of 20 | Trailing P/E (multpl) + YoY CPI (FRED `CPIAUCSL`) | Monthly | (P/E + CPI) well above 20 |
| Value vs Growth (6m) | RPV vs RPG (or IVE vs IVW) price data | Daily | Growth leadership = froth-on; value leadership eases it |
| Credit complacency | FRED `NFCI` (or `ANFCI`) | Weekly | Deeply loose (negative) = complacent |
| Tightening credit (SLOOS) | FRED `DRTSCILM` | Quarterly | Net tightening = watch (froth-off) |

Notes:
- Khoo lists the inverted yield curve inside the froth lens as well. **Do not double-count it** — it
  already sits in Lens 1. If retained here, treat it as a complacency read only and document the
  choice.
- Flag the hardest-to-source items (Deal & IPO froth, forward P/E percentile) and use a documented
  proxy rather than a guess.

## 6. Lens 3 — Price-trend confirmation
| Indicator | Source | Cadence | Bear trigger |
|---|---|---|---|
| 50-day vs 150-day SMA (S&P 500) | `^GSPC` daily closes (yfinance / stooq); confirm vs a second feed | Daily | 50-day crosses below 150-day **and** both flatten or slope down; show 200-day for context |

## 7. Upgrade over the reference: conditional forward returns
For each lens (and for the combined signal), compute the historical distribution of S&P 500 forward
3-, 6-, and 12-month returns **conditioned on the signal being active**, versus the unconditional
base rate. Display as a small panel per lens. This replaces binary red/green with decision-useful
context and applies the entry-point-discipline principle in CLAUDE.md.

## 8. Signal map (later phase)
An S&P 500 log-scale chart, 2006–present, marking historically where Lens 1 turned elevated and
where Lens 2 crossed its alarm, with recession shading. Reference layout in
`reference/signal-map.png`.

## 9. Data pipeline
- JSON schema per indicator:
  ```json
  {
    "id": "yield_curve_10y3m",
    "name": "Yield Curve (10yr - 3mo)",
    "lens": 1,
    "value": 0.62,
    "unit": "pct",
    "as_of": "2026-06-30",
    "status": "benign",
    "threshold": "< 0 = watch",
    "source_url": "https://fred.stlouisfed.org/series/T10Y3M",
    "secondary_source_url": "...",
    "notes": ""
  }
  ```
- GitHub Actions: one daily job for daily/weekly FRED and market series; a monthly job for monthly
  prints; a quarterly job for SLOOS. Commit refreshed `data/` and rebuild `docs/`.
- `template.html` fetch fallback reads `data/` directly so the page works before the build step.

## 10. Suggested build phases (produce a detailed multi-turn plan before coding)
1. Scaffold repo, add `CLAUDE.md`, `SPEC.md`, `reference/`, and the JSON schema. Wire one indicator
   (yield curve) end to end: `data/` → `build.py` → `docs/`, with the fetch fallback working.
2. Complete Lens 1 (all FRED-sourceable series), verifying each series ID against two sources.
3. Add Lens 3 (SMA logic ported from Equity Defense).
4. Add Lens 2 sentiment sources (AAII, NAAIM, NFCI, SLOOS) and the composite plus alarm logic.
5. Add the conditional forward-return panels.
6. Add the signal map.
7. Automate with GitHub Actions and verify the standalone fetch fallback.
