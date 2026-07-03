# Conditional forward returns (phase 5) — running memo

Date: 2026-07-03 · Project: market-regime-dashboard · Status: REVIEWED
Script: `scripts/forward_returns.py` (writes `data/forward_returns.json`;
run on demand — not in the scheduled workflows). Builds on the alarm
calibration (2026-07-03) and reuses its point-in-time machinery.

## Question

What have S&P 500 forward 3/6/12-month returns looked like when each lens
— and the combined act rule — was active, versus base rates (SPEC.md
section 7)?

## Method

Point-in-time monthly grid from 1970 (bounded by stored daily S&P closes).
Signals: Lens 1 recession core (yield-curve re-steepening window from
1982, real-time Sahm at 0.50, labour momentum — HY/PMI/LEI excluded, no
free history), Lens 2 composite at the adopted 62.5% alarm (from 1990),
Lens 3 bear trigger (50/150 SMA with slope confirmation), and the act rule
((L1 or L2) and L3), with unavailable arms treated as quiet — which only
removes historical signals, never adds them. The three pre-registered
silent-failure mitigations apply (expanding/absolute triggers; per-episode
reporting; vintage and publication-lag caveats).

## Results (12-month horizon; full tables in data/forward_returns.json)

| Signal | Active months / episodes | Cond median / hit | Base median / hit |
|---|---|---|---|
| Lens 1 core | 207 / 15 | +11.9% / 75% | +11.2% / 76% |
| Lens 2 at 62.5% | 36 / 16 | +9.0% / 72% | +12.0% / 80% |
| Lens 3 bear | 123 / 37 | +10.6% / 67% | +11.2% / 76% |
| Combined act | 57 / 17 | +10.7% / 61% | +11.2% / 76% |

Combined-rule episodes, the decision-relevant view: onset at 2000-10 /
2001-01 / 2001-07 / 2002-05 (forward 12m −25.9 / −17.3 / −24.7 / −9.7%)
and 2007-12 / 2008-06 (−38.5 / −28.2%, worst −42.6%) — the two great bears
flagged at or near onset. Against that: fires at V-bottoms with strongly
positive forwards (1982 +52.9%, 1990-09 +26.7%, 2003-02 +36.1%, 2020-03
+53.7%) — recession-coincident elevation plus a downtrend is also what
capitulation looks like. 2022 is absent: the reconstructed composite never
reached 62.5% without the IPO gauge (documented mapping caveat), and
Lens 1 core stayed quiet.

## Reading

No lens is a standalone timer — pooled conditional medians sit at or below
base rates everywhere, and the combined rule's pooled statistics are
dominated by late-fire episodes. The rule's demonstrated value is drawdown
truncation in EXTENDED bears (2000–02, 2008–09), and its demonstrated cost
is whipsaw at V-bottoms (1982, 2020). That is precisely the "reduce risk,
not liquidate" posture: sizing down into confirmed weakness, accepting
give-back when the recovery is fast. The dashboard panel shows conditional
versus base per horizon plus the per-episode range so this asymmetry stays
visible; pooled numbers alone would hide it.

## Caveats

Current-vintage FRED histories (PAYEMS benchmark revisions; SAHMREALTIME
is genuinely real-time); publication lags of two to four weeks on monthly
prints make onset dates optimistic — material at V-bottoms (the 2020-03
fire was realistically actionable mid-April); Lens 1 core omits three of
seven live indicators; Lens 2 reconstruction omits the IPO gauge;
overlapping forward windows across clustered episodes — per-episode
outcomes are the honest unit of evidence.
