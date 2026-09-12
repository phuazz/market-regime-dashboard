# Pre-registration — Lens 2 alarm level on the gauge set now running

Date: 2026-09-12 · Project: market-regime-dashboard · Status: PRE-REGISTERED, no result yet
Frozen before any figure was computed. The study script `recalibrate.py` in this
folder is committed in the same commit as this file and is not edited afterwards;
any change to it after the first run is recorded here as an amendment with its reason.

## Why this exists

`reviews/2026-07-03_lens2-alarm-calibration.md` adopted 62.5% (5 of 8 gauges) as the
arming line, and closes by asking for a revisit "at any gauge addition or removal (the
level is a share, but its bite depends on the set's heterogeneity)". A gauge was removed.
NAAIM moved its Exposure Index to subscription access on 2026-08-01 and delays the free
series by three months; the row parked on 2026-08-25 and was deleted from the dashboard
on 2026-09-12.

The removal changed the live alarm without a decision being taken. A share threshold on a
small denominator is lumpy: at eight gauges, 62.5% is exactly 5 of 8; at seven, the lowest
share at or above 62.5% is 5 of 7 (71.4%), because 4 of 7 is 57.1%. The same number now
demands a strictly higher fraction of the set.

## What prior work already settles, and is not re-run here

- `2026-07-03-market-regime-dashboard-1` (no-effect): the composite level carries no
  standalone forward-return edge. **This study is therefore not scored on forward
  returns.** Scoring it that way would re-run a question already answered.
- `2026-07-03-market-regime-dashboard-2` (confirmed): 62.5% was chosen on episode
  capture — every 2000-window arm, both 2021 arms via an IPO-gauge mapping; 75% never
  fires on the modern set; 87.5% marks melt-ups. Episode capture is therefore the
  criterion here too, so that the answer is comparable to the decision it revisits.
- `2026-09-02-sentiment-composite-1` (rejected): CFTC TFF asset-manager positioning as a
  NAAIM substitute is on HOLD in a sibling project. No substitute gauge is proposed here.
  This study is about the level on the set that exists, not about refilling the slot.

## Hypotheses

**H1.** On the seven-gauge set now running, a 62.5% alarm reproduces the arming episodes
that the eight-gauge set produced at 62.5%.

*Stated prediction, before the run:* H1 fails at 2021. NAAIM was near all-in through that
year and is expected to be among the gauges triggered at the peak, so removing it while
holding the percentage should drop the 2021 arm.

**H2.** Some candidate level on the seven-gauge set reproduces the eight-gauge episode
set at 62.5%. Candidates are stated as counts, because only eight composite values exist:

| Count | Share |
|---|---|
| 3 of 7 | 42.9% |
| 4 of 7 | 57.1% |
| 5 of 7 | 71.4% |

## Decision rule, frozen before the run

Adopt the lowest candidate that satisfies all three:

1. arms in the 2000 window, where the eight-gauge set at 62.5% armed;
2. arms in the 2021 window, where the eight-gauge set at 62.5% armed;
3. adds no melt-up false arm against the controls the original study named —
   1991-98, 2003-04, 2016-18, 2020-08 — beyond those the eight-gauge line already made.

If no candidate satisfies all three, report the trade-off table and recommend nothing.
The alarm level remains ZH's decision (SPEC.md section 3).

## The discriminating sample is one episode, and will be reported as such

NAAIM's history begins 2006-07. Before that, the eight-gauge and seven-gauge sets are
identical by construction, so the 2000 window cannot discriminate between them and
clause 1 is satisfied by both candidates trivially. Within 2006-2026 the froth lens has
one genuine top: 2021. (2007-09 was a Lens 1 event; the original study records that the
froth lens correctly stayed quiet.)

**This study therefore rests on n=1 discriminating episode and cannot be presented as a
calibration.** It can say what the arithmetic does and what would have happened in 2021.
If the result turns on that single episode, the verdict is `inconclusive` on evidence and
the recommendation is explicitly a judgement about which error is preferred, not a
measurement. This is committed in advance so that a clean-looking single-episode result
cannot be written up as though it were a calibrated one.

## Method

Monthly point-in-time reconstruction on the S&P 500 month-end grid, reusing the filed
script's helpers (`scripts/alarm_calibration.py`: expanding percentile ranks, as-of
lookups, month-end grid) so both studies compute the same way.

Gauge set, matching the live composite exactly:

| Gauge | Trigger | History from |
|---|---|---|
| Consumer confidence (UMCSENT) | expanding 75th percentile | 1978 |
| Retail euphoria (AAII spread) | expanding 90th percentile, 3-year burn-in | 1990 |
| Growth-expectation froth (multpl P/E) | expanding 90th percentile | 1871 |
| Rule of 20 (P/E + CPI YoY) | above 20 and expanding 80th percentile | 1948 |
| Credit complacency (NFCI) | expanding loosest 20% | 1971 |
| Value vs growth (RPG−RPV, 126 sessions) | ≥ +10 pp | late 2006 |
| Deal and IPO froth (Renaissance annual proceeds) | ≥ 80th percentile of prior years | see below |
| Manager bullishness (NAAIM), **set A only** | ≥ 90 | 2006-07 |

Set A = all eight, the set live at the 2026-07-03 decision.
Set B = set A less NAAIM, the seven running today.
The composite share is triggered / available, as the live code computes it.

**The IPO gauge is computed, not mapped.** The original study excluded it and inferred its
2021 contribution; that inference is one of the silent-failure modes below. Only annual
proceeds exist historically (2016-2026, eleven points), so it is reconstructed at annual
resolution with a **one-year lag** — during year Y the reading is year Y−1's completed
proceeds against the 80th percentile of the years before that, which is what a reader
inside year Y actually knew. At least three prior years are required, so the gauge enters
during 2020. A contemporaneous-year variant (no lag, full-year actual) is a declared
sensitivity, reported to show the direction of the look-ahead it would introduce.

**NAAIM history** is the frozen licensed copy at `C:\dev\sentiment-composite\archive\naaim.csv`
(1,047 weekly rows, 2006-07-05 to 2026-07-29), read in memory. Nothing licensed is written
into this repository, matching the discipline of the filed study.

## Three ways this could be silently wrong

1. **Basis drift.** Comparing an eight-gauge composite over one period against a
   seven-gauge one over another would conflate the gauge change with a period change.
   *Guard:* both sets are computed on the identical month grid from identical inputs,
   differing in exactly one gauge; eras are reported separately and never pooled, and the
   pre-2006 identity of the two sets is stated rather than presented as agreement.
2. **The IPO mapping is an inference, not a measurement.** The adopted level's own 2021
   justification rests on asserting that IPO issuance was at records and would have
   carried the live share to 62.5%. If that assertion is wrong, the decision being
   revisited is wrong, and so is anything calibrated against it. *Guard:* compute the
   gauge and report whether it actually triggered, including the year it entered and the
   thinness of an 80th percentile taken over three to five annual observations.
3. **Vintage.** The reconstruction uses today's vintage: NFCI is re-estimated weekly, and
   multpl's recent months are estimates pending final earnings. A trigger that fires in
   the reconstruction may not have fired on the data available at the time. Inherited from
   the filed study, restated here rather than quietly dropped, with the direction of bias
   named where it can be named.

A fourth, specific to the removal: the frozen NAAIM history ends 2026-07-29, so set A
cannot be evaluated past that date. Months after it are reported for set B only.

## Deliverables

Running memo at `reviews/2026-09-12_lens2-alarm-recalibration.md`, a ledger row, and one
register record per tested hypothesis. The finished record goes to a Fable 5 session for
an adversarial read before any verdict is signed off and before the alarm is changed.
