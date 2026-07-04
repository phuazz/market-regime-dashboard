# Lens 1 firing-bar calibration — running memo

Date: 2026-07-04 · Project: market-regime-dashboard · Status: REVIEWED
Script: `scripts/lens1_calibration.py` (rerunnable; point-in-time). Builds
on the Lens 2 alarm calibration and the phase 5 forward-return study, and
reuses their reconstruction machinery.

## Question

The live risk-reduction signal fires Lens 1 when *any one* of its indicators reaches
elevated (the worst-of / 1-of rule). ZH challenged the low bar: does it make
sense, or should firing require 2+ elevated? Judged point-in-time against
recession capture, false alarms, forward returns, and combined-rule
drawdown protection.

## Method

Monthly grid 1970–2026 (671 months, 8 NBER recessions). Reconstructed the
elevated *count* of the three core indicators with clean free history —
yield curve (re-steepening window), Sahm (≥0.50), labour (unemployment rise
≥0.35 pp or negative three-month payrolls) — and tested Lens 1 = {≥1, ≥2,
≥3 of 3}. Scope caveat: HY spreads (free history from 2023), the PMI proxy,
and the LEI proxy cannot be reconstructed, so this calibrates the count rule
on three of the six live status indicators. The live lens ORs six, so it
fires somewhat more often than this core; the direction of the finding holds
a fortiori.

## Results

| Lens 1 rule | Active months | Recessions caught (fired ≤12m before onset) | False-alarm episodes | Risk-reduction signal: deep drawdowns caught |
|---|---|---|---|---|
| ≥ 1 of 3 (current) | 207 / 671 (31%) | **6 of 8** | 9 of 15 | **7** (of 17 episodes) |
| ≥ 2 of 3 | 161 / 671 (24%) | 3 of 8 | 11 of 13 | 5 (of 13) |
| ≥ 3 of 3 | 8 / 671 (1%) | 0 of 8 | 2 of 2 | 2 (of 2) |

Conditional 12-month forward return is ≈ base rate for every rule (+11.9%
vs +11.2%) — Lens 1 has no standalone timing edge at any bar, as expected
for a sensitivity screen.

## Reading

Raising the bar is counterproductive, and the reason is structural. The core
recession indicators lead by materially different amounts — the yield curve
re-steepens 12–18 months ahead, Sahm fires at onset, labour weakens at or
after onset — so they rarely stand elevated *simultaneously* in the
pre-recession window. Requiring 2+ therefore does not sharpen the signal; it
blinds the lens to recessions where the inputs do not align (capture
collapses 6/8 → 3/8 → 0/8), while barely improving the false-alarm fraction
(the survivors are mid-cycle stress episodes where inputs happen to coincide).
Decisively, in the risk-reduction signal — the only thing acted on — a higher
Lens 1 bar *reduces* deep-drawdown capture (7 → 5 → 2), i.e. it makes the
framework miss bears.

The 1-of bar is thus not merely defensible; on this evidence it is the
correct design for a sensitivity layer. Specificity is supplied by the Lens
3 confirmation gate, which already cuts 207 raw Lens-1 months to 57
combined-rule months. The false positives are the intended price of
sensitivity, and unconfirmed arms cost nothing.

## Recommendation

**Keep Lens 1 firing at ≥ 1 elevated (worst-of).** Do not raise the bar. The
right response to the "too sensitive" concern is to surface *depth* — how
many indicators are elevated — so a shallow 1-of-6 elevation reads as weaker
than a broad one. That intensity display was shipped 2026-07-04 (the slots
now show "N of 6 elevated"). Re-run this calibration if the gauge set
changes or if HY/PMI/LEI gain reconstructable history (which would let the
count rule be tested on all six).

## Caveats

Reconstructed on three of six status indicators; a count rule on the full
six is untestable with free history. Current-vintage FRED series; monthly
grid; 8 recession episodes is a small, clustered sample — the leading-lag
mechanism, not the pooled counts, is the load-bearing finding.
