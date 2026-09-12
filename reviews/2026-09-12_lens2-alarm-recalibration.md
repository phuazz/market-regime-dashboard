# Lens 2 alarm level on the gauge set now running — running memo

> ## CONTESTED — DO NOT SIGN. Erratum, 2026-09-12, same day
>
> The adversarial review commissioned on this record
> (`reviews/2026-09-12_alarm-recalibration/ADVERSARIAL_REVIEW.md`) returned DO NOT SIGN, and
> its decisive findings were independently re-verified before this note was written. Two of
> the three reasons given under "Reading" below do not survive real-time data:
>
> 1. **"No post-2006 melt-up false arm" is false.** The reconstruction scores NFCI on
>    today's vintage. NFCI is heavily revised, one-directionally, over 2016-2019: at
>    2017-08-25 it was −0.87 on the vintage of the day (rank 4.5, triggered) against −0.56
>    today (rank 29.6, quiet); at 2018-06-29, −0.78 then (rank 8.3, triggered) against −0.54
>    now. On real-time data set B at 5 of 7 arms in 2017-08, 2017-12 and 2018-06.
> 2. **"The first arm is 2021-03 under both levels" is false in real time.** The 2021-03-26
>    NFCI print was −0.635 on the 2021-04-02 vintage, rank 24.3 — outside the loosest
>    quintile. Set B was 4 of 7 that month, not 5 of 7. On the data of the day, 5-of-7 first
>    arms in 2021-09: six months later than 4-of-7, which is the reverse of the "continuity,
>    not earliness" claim the recommendation leans on.
> 3. The third reason — no standalone forward-return edge — is symmetric and cuts both ways.
>
> Four further errors, all verified: the gauge count fell on **2026-08-11** (commit
> `d2937e7`, the NAAIM builder parking its own row), not 2026-08-25 (when the general
> staleness guard was added) — and for the week of 2026-08-13 the live composite read 4 of
> 7, so the two candidate lines differed in the live reading four weeks before this study,
> which this memo does not disclose. The combined rule is contemporaneous
> (`forward_returns.py:152`, `(l1 or l2) and l3`), so the sentence below about being "armed
> and waiting well before confirmation" describes a rule the dashboard does not implement;
> Lens 3 first confirmed in 2022-03, when the composite was 2 of 7 under every candidate.
> The IPO gauge as reconstructed is not the live rule and under-counts the live composite by
> one gauge in every month where both are observable. And the sensitivity paragraph's
> "changes nothing at 62.5%" holds for set B only — under set A the no-lag variant adds a
> 2020-07/08 arm inside a named melt-up control.
>
> **Nothing was changed in the dashboard on the strength of this record, and nothing should
> be.** `alarm_share_pct` remains 62.5 because that is what was adopted on 2026-07-03, not
> because this revisit endorsed it. The verdict language this record put into
> `data/thresholds.json` and `scripts/util.py` before review has been backed out.
>
> The text below is left as filed. A re-filed record needs NFCI on ALFRED vintages, the IPO
> gauge under the live rule or its divergence declared, the joint rule's contemporaneity
> stated, the date corrected, the 42.9% candidate restored to the results table, and the
> recommendation restated as the judgement the pre-registration promised.

Date: 2026-09-12 · Project: market-regime-dashboard · Status: FILED, CONTESTED, verdict not signed
Pre-registration: `reviews/2026-09-12_alarm-recalibration/PREREG.md`, frozen in commit
`53bae29` before any figure was computed.
Script: `reviews/2026-09-12_alarm-recalibration/recalibrate.py` (frozen in the same commit).
Output: `reviews/2026-09-12_alarm-recalibration/result.json`.
Builds on `reviews/2026-07-03_lens2-alarm-calibration.md`, which adopted 62.5% and asked
to be revisited "at any gauge addition or removal".

**Recommendation: keep the alarm at 62.5%. No change to `thresholds.json`.**
Owner sign-off outstanding; the record goes to a Fable 5 session for an adversarial read
before the verdict is signed.

## Question

NAAIM was removed from the composite on 2026-09-12 (paywalled at source). The gauge count
went from eight to seven. Does 62.5% remain the right arming line on the set that is left?

## What the removal did to the live alarm, before any evidence

A share threshold on a small denominator is lumpy. At eight gauges, 62.5% is exactly 5 of
8. At seven, the lowest share at or above 62.5% is **5 of 7 (71.4%)**, because 4 of 7 is
57.1% and sits below the line. The stored number did not change and the rule it expresses
did: the alarm now demands a strictly higher fraction of the set than the one that was
adopted. That happened on 2026-08-25 when the staleness guard parked the row, and nobody
decided it.

Today all seven gauges are available, so **"62.5%" and "71.4%" are the same rule**. The
live choice is binary: 4 of 7, or 5 of 7.

## Method

Monthly point-in-time reconstruction on the S&P 500 month-end grid, 1988-01 to 2026-09
(465 months), reusing the filed 2026-07-03 script's helpers so both studies compute the
same way. Two sets differing in exactly one gauge: **A** = the eight live at the 62.5%
decision; **B** = the seven live today. Composite share is triggered / available, as the
live code computes it. The criterion is episode capture, not forward returns — the
composite level's lack of a standalone forward-return edge is filed
(`2026-07-03-market-regime-dashboard-1`) and was not re-tested.

Two deliberate departures from the filed run, both recorded in the pre-registration:

- **NAAIM history** is the frozen licensed copy held by the sibling sentiment-composite
  project (1,047 weekly rows, 2006-07-05 to 2026-07-29), read in memory. naaim.org
  withdrew the public workbook when it moved to subscription access, so
  `scripts/alarm_calibration.py` can no longer fetch it and cannot be re-run as written.
- **The IPO gauge is computed, not mapped.** Annual Renaissance proceeds only exist from
  2016, so it is reconstructed at annual resolution with a one-year lag — inside year Y
  the reading is year Y−1's completed proceeds against the live rule (percentile rank
  within prior years at or above 80), which is what a reader inside year Y knew. At least
  three priors are required, so it enters during 2020. The contemporaneous-year variant is
  reported as a declared sensitivity.

One pre-run amendment: an import of `percentile_rank` was corrected from `util` to
`sources.sentiment` (its actual module). The script had not produced a figure at that
point.

Gauge availability, which governs what any comparison can say:

| Span | Set A | Set B |
|---|---|---|
| 1988-01 → 1990-06 | 4 | 4 |
| 1990-07 → 2006-06 | 5 | 5 |
| 2006-09 → 2019-12 | 7 | 6 |
| 2020-01 → 2026-06 | 8 | 7 |

The two sets are **identical before 2006-07**, when NAAIM's history begins. The 2000 top
therefore cannot discriminate between them, and the only genuine top inside the
discriminating era is 2021. This study rests on one discriminating episode and was
pre-registered as such.

## Results

### The 2000 top — identical, as expected

Sets A and B arm the same eight months (1999-11 → 2000-01, 2000-04, 2000-08 → 2000-11) at
62.5%, at 71.4% and at 75%. Nothing here separates the candidates; it is recorded so that
an agreement produced by construction is not read as evidence.

### The 2021 top — the whole of the discriminating evidence

| Month | Set A (8 gauges) | Set B (7 gauges) | Gauges triggered |
|---|---|---|---|
| 2021-01 | 3/8 · 37.5% | 3/7 · 42.9% | ipo, pe, rule20 |
| 2021-02 | 3/8 · 37.5% | 3/7 · 42.9% | ipo, pe, rule20 |
| **2021-03** | **5/8 · 62.5%** | **5/7 · 71.4%** | aaii, ipo, nfci, pe, rule20 |
| 2021-04 | **5/8 · 62.5%** | 4/7 · 57.1% | ipo, **naaim**, nfci, pe, rule20 |
| 2021-05 | 4/8 · 50.0% | 4/7 · 57.1% | ipo, nfci, pe, rule20 |
| 2021-06 | **5/8 · 62.5%** | 4/7 · 57.1% | ipo, **naaim**, nfci, pe, rule20 |
| 2021-07 | 4/8 · 50.0% | 4/7 · 57.1% | ipo, nfci, pe, rule20 |
| **2021-08** | **6/8 · 75.0%** | **5/7 · 71.4%** | ipo, naaim, nfci, pe, rule20, vvg |
| **2021-09** | **5/8 · 62.5%** | **5/7 · 71.4%** | ipo, nfci, pe, rule20, vvg |
| 2021-10 | **5/8 · 62.5%** | 4/7 · 57.1% | ipo, **naaim**, pe, rule20, vvg |
| 2021-11 | **5/8 · 62.5%** | 4/7 · 57.1% | ipo, **naaim**, pe, rule20, vvg |
| 2021-12 | 3/8 · 37.5% | 3/7 · 42.9% | ipo, pe, rule20 |

The mechanism is exact. NAAIM was the marginal fifth gauge in four of the seven months the
eight-gauge set armed (2021-04, 06, 10, 11). Remove it and those four fall to 4 of 7.

**The first arm is 2021-03 under both.** Lowering the line to 4 of 7 does not arm earlier;
it keeps the arm continuous through 2021-03 → 2021-11 instead of three separate months.
The 50/150 bear cross that Lens 3 required did not come until early 2022, so under either
level the signal was armed and waiting well before confirmation.

### Post-2006 episodes by candidate level

| Level | Set A (as adopted) | Set B (today's seven) |
|---|---|---|
| 57.1% (4 of 7) | 2016-12→2017-02, 2017-05→06, 2017-08→12, 2018-06, 2019-12, 2021-03→04, 2021-06, 2021-08→11 | 2017-08, 2017-12, 2018-06, **2021-03→2021-11** |
| 62.5% | 2017-12, 2021-03→04, 2021-06, 2021-08→11 | 2017-08, 2017-12, 2018-06, 2021-03, 2021-08→09 |
| 71.4% (5 of 7) | 2017-12, 2021-08 | **2021-03, 2021-08→09** — no melt-up arm at all |

The 2017-08 and 2018-06 arms that appear under set B at 62.5% are an **availability
artefact, not a property of the live set**: in that era set B had six gauges, so 4 of 6 is
66.7% and clears the line, where the same four of seven would not. With all seven
available, as they are now, 62.5% is identical to the 71.4% column.

### Sensitivity — the IPO gauge without the lag

The contemporaneous-year variant (look-ahead inside the year) changes nothing at 62.5% or
71.4%. At 57.1% it adds a 2020-01 → 2020-09 arm, because 2020's completed proceeds were a
record. The look-ahead is therefore loosening, and only at the lower candidate.

## Verdicts against the pre-registration

**H1 — 62.5% on the seven-gauge set reproduces the eight-gauge episode set: REJECTED.**
It preserves the 2021 arm but thins it from seven months to three and drops 2021-04, 06,
10 and 11.

**The pre-registered prediction was wrong.** I predicted H1 would fail by losing the 2021
arm altogether. It does not: 2021-03, 08 and 09 reach 5 of 7 without NAAIM, because aaii
and vvg carried those months. The direction of the finding survives; the mechanism I
predicted does not, and the error is recorded rather than smoothed over.

**H2 — some candidate reproduces the adopted episode set: REJECTED.** None does. 57.1%
over-captures 2021 (nine months against seven) and adds 2017-08 and 2018-06; 62.5% and
71.4% under-capture it (three months) and add nothing.

**Decision rule, applied as frozen** — the lowest candidate that arms in 2000, arms in
2021, and adds no post-2006 melt-up arm beyond the eight-gauge line's — returns **71.4%,
which is 5 of 7, which is what 62.5% already means on the live set.**

## Reading

Keeping 62.5% is the answer the frozen rule gives, and the reasons are stronger than the
single episode behind them:

- It is the only candidate that arms at both real tops and makes no post-2006 melt-up
  false arm. 4 of 7 would have armed in 2017-08, 2017-12 and 2018-06 — the last of which
  the filed 2026-07-03 study already identified as the one costly joint false positive,
  paired with the brief 2018-12 bear cross ahead of the +29% 2019 rally.
- Lowering the line buys continuity, not earliness. The first arm is 2021-03 either way,
  and earliness is what an arming condition awaiting Lens 3 confirmation is for.
- The composite carries no standalone forward-return edge, so a looser line does not buy
  information; it buys more months in a state that only matters when Lens 3 confirms.

What this study does **not** establish: that 5 of 7 is calibrated. One discriminating
episode cannot calibrate anything, and the pre-registration committed to saying so. The
recommendation is that the current setting survives the scrutiny the gauge removal
demanded, not that it has been optimised.

## Recommendation

1. **Keep `alarm_share_pct` at 62.5.** No change to `thresholds.json`; the alarm that has
   been running since 2026-08-25 is the one this study endorses.
2. **Record what the share means in counts**, in `thresholds.json` and SPEC.md: 5 of 8 at
   eight gauges, 5 of 7 at seven, 4 of 6 at six. The failure this study was commissioned
   to examine was not a wrong number, it was a number whose bite changed silently.
3. **Guard it.** A test asserting the live gauge count matches a recorded expected count,
   failing on any change, would have surfaced the 8→7 shift on the day it happened. That
   is proposed, not yet written, and belongs in a separate commit from this record.

## Caveats

Current-vintage histories (NFCI re-estimates weekly; multpl's recent months are estimates
pending final earnings), so a reconstructed trigger may not have fired on the data
available at the time — inherited from the filed study and not repaired here. Monthly
grid, so intramonth crossings are missed. The IPO gauge's own trigger is a percentile rank
over three to five annual observations and is therefore coarse by construction: with four
priors it means "above every prior year". The frozen NAAIM history ends 2026-07-29, so
set A is not evaluable past that date. One discriminating episode, as pre-registered.
