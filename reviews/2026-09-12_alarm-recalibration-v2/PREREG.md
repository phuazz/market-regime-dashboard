# Pre-registration v2 — Lens 2 alarm level, re-run on real-time data

Date: 2026-09-12 (Saturday) · Project: market-regime-dashboard · Status: PRE-REGISTERED, no result yet
Frozen before any figure was computed. `recalibrate_v2.py` is committed with this file and
not edited afterwards; a post-freeze change is recorded here as an amendment with its reason.

## Why there is a second pre-registration

The 2026-09-12 study (`reviews/2026-09-12_lens2-alarm-recalibration.md`) was filed, sent
for an adversarial read, and came back DO NOT SIGN. Its decisive findings were
independently re-verified and hold. Two of its three stated reasons were artefacts of
scoring NFCI on today's vintage; its recommendation is withdrawn. That record's reopen
condition names six repairs, and this study is those repairs, pre-registered afresh rather
than patched into a filed record.

**The verdicts of the first study are not re-opened.** H1 and H2 stand as rejected: 62.5%
on seven gauges does not reproduce the eight-gauge episode set, and no candidate reproduces
it. What failed was the recommendation and the reasons under it. This study asks the
decision question again, on data that was knowable at the time.

## What changes, and why each change is needed

1. **NFCI is scored on ALFRED vintages.** This is the repair that matters. The Chicago Fed
   re-estimates the whole NFCI history weekly, and over 2016-2019 the revisions run
   one-directionally: 2017-08-25 read −0.87 on the vintage of the day (rank 4.5, inside the
   loosest quintile) against −0.56 today (rank 29.6, outside it). At each month-end the
   gauge is computed from the vintage published seven days later — the series as it stood
   when a reader could first have acted on that month — and the expanding percentile line
   is computed from that same vintage, so the line moves with the data as it did in life.
   The other gauges stay on current vintage and the reason is stated per gauge below.
2. **The IPO gauge is declared unreconstructable, and run both ways.** The live rule is
   annualised year-to-date proceeds against prior completed years. Monthly year-to-date
   proceeds do not exist in any source this project holds, so neither the first study's
   one-year-lagged annual proxy nor its no-lag variant is the live gauge; the lagged proxy
   under-counts the live composite by one gauge in every month where both are observable.
   Rather than assert a repair, the composite is computed on two declared arms — IPO
   excluded (matching the 2026-07-03 study) and IPO by the lagged proxy — and the answer is
   reported as robust or not robust to the choice.
3. **The joint rule is computed, not assumed.** The risk-reduction signal is
   `(Lens 1 elevated OR Lens 2 armed) AND Lens 3 confirming`, evaluated in the same month —
   it carries no memory of an earlier arm (`scripts/forward_returns.py:152`,
   `template.html:553`). The first study argued from arming months alone and wrote that the
   signal was "armed and waiting well before confirmation", which the code does not do.
   Lens 3's bear condition is reconstructed here to the live rule (50-day below 150-day, and
   both slopes at or below +0.1% over 20 sessions) so the study can report what the signal
   would actually have done, not what the froth lens alone would have said.
4. **Every pre-registered candidate appears in every results table**, 42.9% included. The
   first study dropped it from the write-up.
5. **The count-change date is 2026-08-11**, commit `d2937e7`, when the NAAIM builder parked
   its own row — not 2026-08-25, when the general staleness guard was added.
6. **The mid-August 2026 week is disclosed.** From 2026-08-13 to 2026-08-19 the live
   composite read 4 of 7, which arms under one candidate and not the other. The candidates
   differed in the live reading four weeks before the first study, which did not say so.

## Vintage treatment, per gauge, declared in advance

| Gauge | Vintage treatment | Reason |
|---|---|---|
| Credit complacency (NFCI) | **ALFRED vintage at month-end + 7 days** | Re-estimated weekly across the whole history; revisions are large and one-directional in the decisive era |
| Consumer confidence (UMCSENT) | current vintage | Near-unrevised; and far from its line in every decisive month |
| Rule of 20 (CPI leg) | current vintage | CPI seasonal factors revise; the sum is far from its line in the decisive months |
| Retail euphoria (AAII) | current vintage | Survey, never revised |
| Growth-expectation froth, value vs growth | current vintage | Prices, never revised |
| Manager bullishness (NAAIM) | frozen licensed copy | Survey, never revised; series ends 2026-07-29 |
| Deal and IPO froth | not reconstructable — two declared arms | See change 2 |
| Lens 3 trend | current vintage | Prices, never revised |

Where a gauge stays on current vintage the claim being made is narrow: that its revisions
cannot move it across its line in the months that decide the answer. Any month where a
current-vintage gauge sits within 5 percentage points of rank of its line is listed in the
results as a month the study cannot call, rather than being silently counted.

## Amendment 1, recorded before any figure existed — the AAII source

`fetch_aaii_history()` failed on the first run: `https://www.aaii.com/files/surveys/sentiment.xls`
returns **403 and an HTML body** to this client. It is not a broken series — the GitHub
Actions runner fetched it successfully on 2026-09-12 (the live row carries as-of
2026-09-10) — so this is a bot block on this machine's address. The adversarial reviewer
hit the same wall.

AAII is therefore read from the sibling sentiment-composite project's cached copy
(`C:\dev\sentiment-composite\archive\aaii.csv`, 2,037 weekly rows, 1987-07-24 to
2026-08-20), spread computed as bullish minus bearish, used in memory and never written
into this repository — the same discipline the NAAIM history already runs under.

Two-source verified before use, as the house rule requires: on all eight weeks where the
cache overlaps this repository's own independently scraped `data/history/aaii_spread.json`,
the two agree to within 0.045 pp, which is display rounding (the repo stores one decimal).
The survey is never revised, so a cached copy equals a live fetch for every date it covers,
and its 2026-08-20 end is months after the last decisive month in this study.

## Amendment 2, recorded before any figure existed — NFCI did not exist in real time before 2011

The run stopped at its first pre-2011 month-end: ALFRED returns 404 for every NFCI vintage
before **2011-05-25**, located by bisection. The Chicago Fed introduced the NFCI in 2011 and
backfilled the history to 1971. There is no vintage before that because there was no series.

This is not a data-access problem, it is a finding, and it applies to both prior studies:
**the credit-complacency gauge in the 1990-2011 reconstruction is a hindsight construct, not
a gauge anyone could have read.** The 2026-07-03 calibration's "five gauges from 1990" were
four in real time, and its 2000-top conclusion rests in part on a series that did not exist
in 2000. The same is true of the 2026-09-12 run.

Handling, declared now and before any result:

- **Primary (real-time):** NFCI enters the composite only from 2011-05-25, its first
  vintage. Before that the gauge is absent and the denominator is smaller — which is what a
  reader actually had. Note this changes what a share threshold means in that era, which is
  the same lumpiness this whole study is about.
- **Comparability arm:** NFCI on today's backfilled vintage throughout, which is what both
  prior studies did, reported beside the primary so the effect is isolated rather than
  confounded with the gauge-set question.

Neither arm is privileged in the write-up. The 2000 window is not a discriminating window
for the set question in any case (NAAIM's history starts 2006-07), but the melt-up controls
1991-98 and 2003-04 sit squarely in the affected era and their results change.

## Hypotheses

**H3.** On data available at the time, 5 of 7 (the stored 62.5%) arms at the 2021 top no
later than 4 of 7 does.
*Stated prediction:* H3 fails. The re-verified NFCI ranks put set B at 4 of 7 in 2021-03,
so 5-of-7 is expected to arm months later.

**H4.** On data available at the time, 5 of 7 makes no melt-up false arm over the controls
named in the 2026-07-03 study (1991-98, 2003-04, 2016-18, 2020-08).
*Stated prediction:* H4 fails at 2017-08, 2017-12 and 2018-06.

**H5.** The choice of alarm level changes what the risk-reduction signal would have done —
that is, some candidate produces a FIRED month (Lens 2 armed and Lens 3 confirming in the
same month) that another does not, at any point in 1990-2026.
*Stated prediction:* H5 fails. If it does, the level cannot be chosen on signal outcomes at
all, and the study says so rather than choosing on arming months as though they were
outcomes.

## Decision rule, frozen before the run

There is no mechanical adoption rule this time, and that is deliberate: the first study's
rule returned a level its own author then mapped back to the stored number, which is how a
post-hoc exemption got written as a finding.

This study reports, for each candidate level and each IPO arm, on real-time data: the
arming months, the melt-up arms, the first arm at the 2021 top, and the FIRED months under
the joint rule. **If H5 fails, the record states plainly that the evidence cannot decide the
level, and any recommendation is labelled a judgement with its reasoning exposed —
including, explicitly, which error the judgement prefers.** No recommendation will be
written into `data/thresholds.json`, `scripts/util.py` or any other published file before
owner sign-off; the first study's breach of that is the reason the rule is written down.

## Three ways this could be silently wrong

1. **The vintage convention could itself be the artefact.** Month-end plus seven days is a
   choice; a different lag would give a different real-time NFCI. *Guard:* the sensitivity
   is run at +3 and +14 days as well, and any month whose trigger state differs across the
   three lags is reported as undecidable rather than counted.
2. **Mixed-vintage bias.** NFCI on real-time data and six gauges on current vintage is not
   a single basis. The direction is knowable and must be stated: current vintage makes the
   other gauges look more accurate than they were, so a composite mixing them is, if
   anything, biased toward agreement with today's view. *Guard:* the near-line list above,
   plus a whole-grid re-run with NFCI on current vintage reported side by side, so the
   vintage effect is isolated rather than confounded.
3. **The joint rule could be reconstructed wrongly and quietly acquit every candidate.** If
   the Lens 3 reconstruction never confirms, H5 fails trivially and for the wrong reason.
   *Guard:* the Lens 3 reconstruction is checked against the live `data/lens3.json` status
   on every month where both exist, and against the filed `signal_map.json` act spans; a
   mismatch stops the study rather than being reported.

## Deliverables

`reviews/2026-09-12_lens2-alarm-recalibration-v2.md`, a ledger row superseding nothing (the
first row stays, marked CONTESTED), and register records for H3, H4 and H5. The record goes
to a Fable 5 adversarial read before any verdict is signed, as the first one did.
