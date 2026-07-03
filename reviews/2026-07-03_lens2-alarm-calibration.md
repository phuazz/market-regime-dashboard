# Lens 2 alarm-level calibration — running memo

Date: 2026-07-03 · Project: market-regime-dashboard · Status: REVIEWED
**Decision: adopted at 62.5% (5 of 8) by ZH, 2026-07-03.** Wired into
`data/thresholds.json` (`lens2_composite`) the same day; the combined read
is live from this change.
Script: `scripts/alarm_calibration.py` (rerunnable; all histories fetched
in-memory, nothing licensed is redistributed). Builds on the WS0/WS1
threshold-robustness lesson (breadth-thrust-etf, 2026-07-02): prefer
plateaus to point-optimised thresholds.

## Question

Which composite alarm level (share of froth gauges triggered) should arm
Lens 2 in the act rule — 50, 62.5, 75, or 87.5 percent — judged by S&P 500
forward returns over 1/3/6/12-month horizons, macro-fund style?

## Method

Monthly point-in-time reconstruction of the composite, 1990-07 to 2026-07.
Percentile triggers (AAII top decile, P/E 90th, Rule-of-20 tail, NFCI
loosest quintile, Michigan 75th) use expanding windows — the line at month
t uses only data through t. Absolute triggers (NAAIM 90, value-growth
+10 pp, Rule-of-20's 20) are point-in-time by construction. Gauge count
grows with data availability: five gauges from 1990, seven from 2007
(NAAIM, RPG−RPV join). The IPO gauge is excluded (history starts 2016).
Forward returns from month-end onset; per-episode outcomes reported
because pooled statistics over clustered episodes overstate independence.

Three ways this could be silently wrong, stated before code: (1)
look-ahead via full-sample trigger lines — mitigated with expanding
windows; (2) current-vintage histories (NFCI re-estimates weekly; Michigan
and CPI near-unrevised) and month-end availability approximations —
direction of bias modest, documented; (3) few independent episodes with
overlapping forward windows — per-episode reporting, no significance
claims. Standing caveat: the gauge set itself was chosen knowing this
history.

## Results

Unconditional base rates (12m): Panel A (1990→, 421 obs) median +12.0%,
hit 80%. Panel B (2007→, 223 obs) median +13.2%, hit 78%.

| Level | Active months (A / B) | 12m median (A) | 12m hit (A) | Verdict |
|---|---|---|---|---|
| ≥ 50% | 131 / 23 | +9.0% | 78% | Broad watch band; many benign arms |
| ≥ 62.5% | 36 / 1 | +9.0% | 72% | Catches every 2000-window arm; rare on the modern set |
| ≥ 75% | 35 / 0 | +9.0% | 74% | Identical to 62.5 pre-2006; never fires post-2007 |
| ≥ 87.5% | 4 / 0 | +26.2% | 100% | Fires only in melt-ups (1996-97, 2004) — perverse |

Signal episodes that mattered:

- **2000 top** (five-gauge era): ≥62.5% armed 1999-11→2000-01 (fwd12
  −5.3%), 2000-04 (−14.0%, worst −20.1%), 2000-08→11 (−25.3%). The 50/150
  bear cross confirmed around 2000-10 — the combination worked.
- **2021 top** (seven-gauge era): shares peaked at 57% (4 of 7) in
  2021-06 (fwd12 −11.9%) and 2021-08→11 (−12.6%, worst −16.3%). The bear
  cross confirmed in early 2022. Note: the live composite has eight gauges
  including IPO issuance, which was at records through 2020-21 — the
  reconstructed 4/7 (57%) is therefore the live 5/8 (62.5%) in deal-froth
  eras. Reconstructed shares understate live shares by up to one gauge in
  exactly the episodes that matter.
- **False arms absorbed by design**: 1991-98 and 2003-04 melt-ups, 2016-18,
  2020-08 — strong positive forwards, but Lens 3 never confirmed a bear
  cross in the window, so the act rule stayed silent. The one costly joint
  false positive: 2018-06 arm (57%) plus the brief 2018-12 cross, ahead of
  the +29% 2019 rally. The 2001-02 arms (60%) were post-crash
  loose-money reads with bad forwards — a reminder the composite is not a
  buy signal either.

## Reading

The composite level alone does not separate forward returns from base
rates (conditional 12m medians sit a few points BELOW unconditional, with
small clustered samples) — froth is not a timer, which is precisely why
SPEC section 2 requires Lens 3 confirmation before acting. The alarm level
should therefore be chosen for episode-marking usefulness in the joint
rule, not for standalone predictive power: high enough to skip most
melt-up noise, low enough to actually arm at real tops on the modern,
wider gauge set where unanimity is structurally rarer.

- 87.5%: rejected — historically marks reflation melt-ups, and an alarm
  that fires only in rallies is worse than none.
- 75%: rejected as primary — never reached on the modern set; an alarm
  that cannot fire is a design failure.
- 62.5% vs 50%: 62.5 sits on the informative edge. It captured every
  2000-window arm, and with the IPO gauge live it is the modern
  equivalent of the 4-of-7 line that marked both 2021 arms. 50% remains
  visible on the dashboard as the composite share itself (a de facto
  watch level) without arming the act rule through every melt-up.

## Recommendation

**Set the alarm at 62.5% (5 of 8 gauges)**, understood as an arming line
for Lens 3 confirmation, not a standalone signal. Revisit after the phase
6 signal map overlays arm and confirmation dates jointly, and at any gauge
addition or removal (the level is a share, but its bite depends on the
set's heterogeneity).

## Caveats

Current-vintage histories; monthly grid (intramonth spikes missed);
publication-lag approximations of up to a few weeks on monthly prints;
episode counts are small (two genuine tops in the sample; 2007 was a
Lens 1 event, and the froth lens correctly stayed quiet then); the IPO
gauge could not be reconstructed and its absence biases reconstructed
shares down in deal-froth eras (direction favours choosing the lower of
two otherwise-tied candidates, which the recommendation does).
