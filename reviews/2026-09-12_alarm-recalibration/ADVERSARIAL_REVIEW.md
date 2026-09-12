# Adversarial review of the 2026-09-12 alarm recalibration — DO NOT SIGN as written

Produced 2026-09-12 by a Fable 5 session commissioned to falsify the record, per the
owner's instruction that the finished study go to an adversarial read before sign-off.
Filed verbatim. Nothing in the study was modified by the reviewer.

**Independently re-verified before this file was written** (the reviewer is not taken on
trust): the gauge-count date from `git log` on `data/lens2.json`; the live IPO gauge status
against the study grid; the NFCI real-time ranks from ALFRED at four vintages; and the
contemporaneity of the combined rule in `scripts/forward_returns.py:152` and
`template.html:553`. All four hold. Findings 1 to 5 below are accepted.

Outstanding from the reviewer's own "not verified" list: the AAII margin at 2021-03-25,
real-time vintages for multpl P/E and Michigan, and H1 2018 IPO proceeds.

---

## Verdict: DO NOT SIGN as written

Keeping 5 of 7 may still be the right judgement, and nothing is operationally urgent — the
live composite is 3 of 7 today, armed under neither candidate. But the record's evidential
claims do not hold.

## Claim A — 62.5% is 5 of 8 at eight gauges and 5 of 7 at seven; boundary handling. CONFIRMED, with a date error

Arithmetic holds: 4/7 = 57.1 < 62.5 ≤ 71.4 = 5/7. Boundary handling is consistent
everywhere: the study uses `share >= level − 1e-9` on the raw share (`recalibrate.py` line
240); `lens2.summarise()` rounds to one decimal then tests `share >= alarm_share_pct` (line
152); `forward_returns.py` line 145 tests the raw share; `util.minimum_triggered()` mirrors
the rounding; the template only consumes `alarm_state === "at_or_above"` (lines 520, 545,
955) and never recomputes. No k/7 or k/8 value sits within rounding of the line.

The date is wrong. PREREG, memo, ledger row, register `cause_of_death`, `thresholds.json`
and `util.py` all say the count fell to seven on 2026-08-25. The `data/lens2.json` history
shows `gauge_count` 7 from commit `d2937e7` (2026-08-11) and the NAAIM row carries its own
message "PARKED 2026-08-12 … 105 days" — the row's builder parked it, not the general
staleness guard (that guard, `PARK_AFTER_DAYS`, was only added in `86d4e5d` on 2026-08-25,
which is where the date came from). Material consequence: from 2026-08-13 to 2026-08-19 the
live composite read 4 of 7 (57.1%: P/E, IPO, Rule of 20, value-vs-growth at +15.9 pp).
Under 4-of-7 the dashboard would have been armed for that week; under the stored line it
read "below". The memo does not disclose that the two candidates differed in the live
reading four weeks before the study.

## Claim B — sets identical before 2006-07; the 2000 window discriminates nothing. CONFIRMED

`n_A == n_B` and `k_A == k_B` on every grid row before 2006-07-31, and the 2000-window
armed lists are identical at every level. True by construction, as the memo says. Nit: the
availability table omits 2006-07 → 2006-08 (A 6, B 5).

## Claim C — NAAIM thins 2021 from seven months to three; marginal fifth at 04, 06, 10, 11. CONFIRMED on the current-vintage grid; not robust to vintage

Verified against the frozen CSV directly: exposure 103.72 / 91.72 / 92.83 / 103.35 / 103.14
at the 04/06/08/10/11 month-ends, 52.02 / 68.30 / 78.39 / 55.02 at 03/05/07/09. On the
current-vintage grid the memo's table is exact. On real-time NFCI (below) the same
comparison is "six months to two" and the marginal months are 04, 06, 08, 11 — 2021-03 was
never a five-gauge month on either set.

## Claim D — "first arm is 2021-03 under both levels; lowering the line buys continuity, not earliness". DISPUTED

Intramonth on the current vintage: fine. NFCI first crossed on the 2021-03-12 weekly print,
AAII on 2021-03-25 (bulls 50.9%, bears 20.6%, spread +30.3 — AAII's own article),
value-vs-growth was −10 to −36 pp from January to July, Michigan never triggered. So at
weekly resolution both levels arm in March 2021 and neither in January or February.

On the data available at the time it fails. The 2021-03-26 NFCI observation was −0.635 on
the 2021-04-02 vintage, rank 24.3 against the loosest-20% line of −0.664 (margin −0.029).
On today's vintage it is −0.652, rank 18.9 (margin +0.014). The whole history was
re-estimated: the line itself moved by 0.026. Set B at 2021-03 was therefore 4 of 7 in real
time, not 5 of 7. Real-time 2021 on set B: 4-of-7 arms 2021-03 → 2021-11 continuously
(unchanged); 5-of-7 arms 2021-09 and 2021-10 only (2021-08-27 also fails its vintage at
rank 20.20, margin −0.002 — a coin-flip month under either vintage; 2021-03 is not). Set A
at 5-of-8 first armed 2021-04 in real time. So the recommended line is six months later
than 4-of-7 and five months later than the line it was meant to preserve. "Buys continuity,
not earliness" is the reverse of what the data of the day show.

The claim also does not survive the joint rule as coded. `forward_returns.py` line 152
(`combined_act = (l1 or l2) and l3`) and the template (`armed.length && lens3Confirms`) are
contemporaneous. The Lens 3 bear condition first held on 2022-03-07 (month-end 2022-03-31),
when the composite was 2 of 7 (IPO, Rule of 20) under either set, either vintage. No
candidate level, on any set, would have fired the risk-reduction signal on Lens 2 in
2021–22; the arm had lapsed by 2021-12. "Under either level the signal was armed and
waiting well before confirmation" describes a rule the dashboard does not implement.

## Claim E — 2017-08 and 2018-06 arms are "an availability artefact, not a property of the live set". DISPUTED, twice over

The arithmetic half holds (4 of 6 = 66.7% clears 62.5%; 4 of 7 would not). The inference
half assumes the seventh gauge (IPO) was quiet in those months — the study cannot evaluate
it (`min_priors=3` puts the gauge's entry in 2020), and asserting it is exactly the mode-2
inference the PREREG forbids. Under the live rule (annualised YTD against the prior years
on the Renaissance page), Renaissance's own annual series — 2010 $38.7bn, 2011 $36.3bn,
2012 $42.7bn, 2013 $54.9bn, 2014 $85.3bn, 2015 $30.0bn, 2016 $18.8bn, 2017 $35.5bn, 2018
$46.8bn (2018 annual review, primary) — means 2018-06 triggers at the 80th percentile if
first-half 2018 proceeds exceeded about $27.5bn, under any prior window from two years to
eight. I could not verify the H1 2018 figure (the 2Q18 review URL is dead; my recollection
of roughly $28bn is unverified and marked as such). For 2017-08 the 3Q17 review gives 1Q17
$9.9bn, 2Q17 $10.6bn, 3Q17 $4.1bn: an annualised pace of about $35bn ranks 28.6th against
2010–2016 (not triggered) but 100th against 2016 alone (triggered), so the answer depends
on which prior window the page then showed. Untested either way.

The stronger objection: on real-time NFCI those months are 5-of-6 regardless of IPO. NFCI
was −0.89 / −0.89 / −0.78 at 2017-08-25, 2017-12-29 and 2018-06-29 on the vintages of the
day (ranks 4.2, 2.7, 8.3); today's vintage has them at −0.56 / −0.62 / −0.54 (ranks 29.6,
23.5, 33.1), never triggered. The 2016–2019 readings were revised upward by 0.25–0.35
between the 2018-07 and 2021-04 vintages. In real time NFCI sat in its loosest quintile in
44 of the 78 months 2016-01 → 2022-06 (essentially all of 2016-08 → 2020-02); the study's
grid has it triggered in zero of the 2016–2019 months. Consequences: set B at 71.4% arms
2017-08, 2017-12 and 2018-06 in real time — the "no melt-up arm at all" property does not
exist; set B at 62.5% (4 of 6 then) arms 20 of the 24 months 2016-12 → 2018-06 plus 2019-11
→ 2020-02; set A at 62.5% arms twelve months in that window plus 2019-12, not the single
month 2017-12 the memo reports.

One more inherited error: the 2018-06 "costly joint false positive" (2026-07-03 memo,
reused here as the case against 4-of-7) was not joint. The bear condition first held
2018-12-13, when the composite was 1–2 of 6 on either vintage; the filed `signal_map.json`
has no 2018 act span. The arm and the cross were six months apart.

## Claim F — the IPO reconstruction supports the mode-2 repair. DISPUTED

The reconstruction is not the live rule. Live (`lens2.py` lines 477–487): annualised
year-to-date proceeds of year Y against prior completed years. Study primary: year Y−1's
completed total (lag 1); sensitivity: year Y's completed total (lag 0). Neither is the live
gauge, and the in-sample check the study did not run shows it: at 2026-07-31, 2026-08-31
and 2026-09-11 the live `lens2.json` has the IPO gauge triggered (YTD $142.5bn → $145.8bn,
100th percentile) and the composite one gauge higher than the study grid, which has IPO
quiet (2025's $44.0bn ranks 55.6th). The "computed" gauge under-counts the live composite
by exactly one gauge in every month where both are observable — the same one-gauge
deal-froth bias the July memo flagged for its excluded gauge. Lag 1 also carries the 2021
record through all of 2022 as "triggered" while issuance collapsed to $7.7bn (grid rows
2022-02 → 06). For 2021 the coarseness is harmless — issuance was a record under any rule —
so "the mapping was correct" is corroborated, not measured under the live rule. The
sensitivity paragraph is wrong for set A: lag 0 adds a 2020-07 → 2020-08 arm at 62.5% (5 of
8: IPO, NAAIM, P/E, Rule of 20, value-vs-growth) inside the named 2020-08 melt-up control
(`sensitivity_ipo_lag_0.levels["62.5"].A`); "changes nothing at 62.5% or 71.4%" holds for
set B only. Separately, the repo history has 2018 at $46.9bn and the Renaissance PDF says
$46.8bn — a two-source discrepancy of 0.1 to note.

## Claim G — does the recommendation follow from the frozen rule? DISPUTED in part

The rule as written returns 71.4%; the memo concedes this and then stores 62.5 on an
identity that holds only at exactly seven available gauges. On the study's own grid 62.5%
fails clause 3 (adds 2017-08 and 2018-06 to set A's 2017-12); it is rescued by the
"availability artefact" argument, which is not in the frozen rule and is itself disputed
above. The two numbers diverge the next time a gauge parks (62.5 → 4 of 6; 71.4 → 5 of 6),
which is the failure mode the study was commissioned on; recommendation 2's "4 of 6" is a
share-preserving choice that contradicts the rule's output without saying so. The
pre-registered 42.9% candidate is absent from the results table. On real-time data the
literal rule still returns 71.4%, but only because clause 3 is relative to set A and set A
made thirteen melt-up arms in real time, so "adds none beyond" is a weak bar — and the
three reasons the memo gives for the answer are, respectively, false (no melt-up arm),
false (no earliness) and symmetric (no standalone edge cuts both ways). The PREREG's
commitment — verdict inconclusive on evidence, recommendation explicitly a judgement —
survives as one sentence in the memo; the ledger row, both register records,
`thresholds.json` and `util.py` state it as settled. Commit `9eb0835`, seven minutes after
filing and before any review, wrote the now-falsified "first arm is 2021-03 at both … buys
continuity rather than earliness" into `data/thresholds.json` `candidate_rationale` and
"endorsed 62.5%" into `scripts/util.py` — the unsigned verdict is already in published
data.

On the status-quo question: I cannot speak to motive, but the record's structure — literal
output 71.4, mapped back to the stored 62.5, a post-hoc exemption for 62.5's own clause-3
failure, a symmetric argument used one way, and the week in August when the candidates
differed left out — is what anchoring on the stored number would look like.

## Things the study missed

1. Real-time NFCI (above). The revision is large and one-directional for 2016–2019 and on
   the wrong side of a thin margin at 2021-03 and 2021-08.
2. The joint rule is contemporaneous, so 2021 was a miss under every candidate and 2018-06
   was never a joint event.
3. The live reading was 4 of 7 for a week in mid-August 2026.
4. Date of the count change (2026-08-11/12, not 08-25) in six places.
5. `template.html` hard-codes "62.5%" in copy at lines 272 and 1145 rather than reading
   `alarm_share_pct` — harmless while the number stays, a trap if it changes.

Not verified by the reviewer: the AAII margin at 2021-03-25 (the workbook is behind a bot
wall; AAII is unrevised, so this affects nothing above); real-time vintages of multpl P/E
and Michigan (both far from their lines in the decisive months); H1 2018 IPO proceeds. The
reviewer's vintage grid inherits the study's own publication-lag convention (observation
date, not release date).

## What a re-filed record needs

NFCI scored on ALFRED vintages (the fetch works; the other gauges can stay); the IPO gauge
either reconstructed under the live rule or its divergence declared; the joint-rule
contemporaneity stated with the 2021 and 2018 outcomes corrected; the date fixed; the 42.9%
row restored; and the recommendation restated as the judgement the PREREG promised, with
`thresholds.json` `candidate_rationale` and the `util.py` comment reverted to "pending"
until it is taken.

Sources: [Renaissance 2018 US IPO Annual Review](https://www.renaissancecapital.com/Review/2018_US_Review_Press.pdf),
[Renaissance 3Q 2017 US IPO Quarterly Review](https://www.renaissancecapital.com/review/3Q17USReview.pdf),
[Renaissance updated 2018 annual review note](https://www.renaissancecapital.com/IPO-Center/News/61344/Renaissance-Capitals-Updated-2018-US-IPO-Annual-Review),
[AAII Sentiment Survey, week of 2021-03-25](https://www.aaii.com/latest/article/13667-aaii-sentiment-survey-optimism-jumps-to-a-new-2021-high),
ALFRED NFCI vintages via `https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=NFCI&vintage_date=YYYY-MM-DD`.
