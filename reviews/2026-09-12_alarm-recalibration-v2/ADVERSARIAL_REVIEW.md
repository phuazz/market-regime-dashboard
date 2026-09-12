# Adversarial review of the v2 alarm recalibration — DO NOT SIGN

Produced 2026-09-12 by a Fable 5 session, the second such read on this question. Filed
verbatim. Nothing in the study was modified by the reviewer.

**Independently re-verified before this file was written.** Three decisive claims were
checked against the study's own output and the repository's own files, and all three hold:

1. The seven discriminating GFC months are **3 of 5**, not 4 of 7 — every one reads
   `pe, rule20, vvg` triggered on a five-gauge denominator, because NFCI is absent before
   2011-05-25 in the real-time arm. Two of them carry `near_line: ['pe']`.
2. **1998-09 and 1998-10 fired at every candidate level** and sit inside the 1991-98
   melt-up window. The memo's melt-up table states zero firings in all four windows. That
   number was never computed; it was inferred, and it is wrong.
3. `data/signal_map.json` `lens1_spans` has Lens 1 elevated **2007-08-31 → 2010-05-28**,
   covering all seven discriminating months, and the filed `act_spans` include
   2007-12-31 → 2008-03-31 and 2008-06-30 → 2009-03-31. The full rule already fired in
   those months at the stored line.

The recommendation is withdrawn. See the erratum at the head of
`reviews/2026-09-12_lens2-alarm-recalibration-v2.md`.

---

## Freeze claim — CONFIRMED

`22e14bf` (21:45:39 +0800) created PREREG.md and `recalibrate_v2.py`; `25c04c7` (21:49:18)
changed the script only for the two declared amendments (AAII cache loader replacing
`fetch_aaii_history`, `FIRST_NFCI_VINTAGE` guard in `nfci_at`); `b514c09` (22:06:25) added
only `result_v2.json` and the memo. `git diff 25c04c7 HEAD` on the script is empty.
`git diff a7ddace HEAD` outside `reviews/` is empty, so the promise that no published file
carries the unsigned verdict was kept.

## A. The fired-month quantity — reconstruction CONFIRMED, the "4 of 7 versus 5 of 7" framing DISPUTED

Lens 3: I recomputed bear months from `gspc.json` with `lens3.py`'s own `rolling_mean` and
`slope_pct` (50 below 150, both 20-session slopes at or below +0.1%). Identical to the
study's 69 months on the 1988→2026 grid. The counts 7 (62.5%) and 14 (57.1%) are exact, in
both IPO arms, and the difference is exactly 2007-12, 2008-02, 2008-06/07/08, 2009-02/03.

What the memo does not say is what denominator those months had. In the real-time arm set B
has four gauges 1990-07→2006-08, five 2006-09→2011-05 (NFCI absent), six from 2011-06, and
seven only in the lag arm from 2020-01. The arithmetic of the two candidates across those
denominators:

| n | 57.1% bites as | 62.5% bites as |
|---|---|---|
| 4 | 3 of 4 | 3 of 4 |
| 5 | **3 of 5** | **4 of 5** |
| 6 | 4 of 6 | 4 of 6 |
| 7 | 4 of 7 | 5 of 7 |
| 8 | 5 of 8 | 5 of 8 |

The candidates are the same rule at four, six and eight gauges. They differ at five and at
seven. No bear month in the sample had a seven-gauge composite at or above 4 of 7
(2020-03/04 read 3 of 7 in the lag arm; 2022 read 2 of 7). Every one of the seven
discriminating months is a **3-of-5** month: `pe`, `rule20`, `vvg` triggered, `aaii` and
`umcsent` quiet. The memo's sentence "four of seven did, from December 2007" describes a
rule that was never evaluated. On today's seven gauges the same three triggered gauges read
3 of 7 = 42.9%, below the recommended line.

The three gauges that fired are not froth readings. Trailing P/E rose from 22.35 (2007-12)
to 26.83 (2008-08) to 84.5 and 110.4 (2009-02/03) while the index fell from 1,468 to 735 —
the earnings denominator collapsed. Rule of 20 is that P/E plus 4–5% CPI. Value-vs-growth
cleared +10 pp because financials, the value leg, collapsed. The 2009-02/03 "cost" and the
2007-08 "capture" are one mechanism.

Two of the seven months are "cannot call" by the PREREG's own rule: P/E ranked 92.3
(2007-12) and 91.6 (2008-02) against a 90 line, and the grid flags both
`near_line: ['pe']`. The PREREG says such months are "listed as a month the study cannot
call, rather than being silently counted". They were counted, and the GFC is not a named
window so its near-line months were never reported.

## B. "Melt-up arms cost nothing" — DISPUTED; the table is wrong in two of four windows

The memo's claim rests on "Lens 3 never confirmed inside those windows". From the study's
own `lens3_bear_months`: 1991-98 contains 1994-04/05 and 1998-09/10; 2003-04 contains
2003-02/03 and 2004-08/09; 2016-18 contains 2016-01/02 and 2018-12. Lens 3 confirmed inside
three of the four windows. Intersecting the study's own per-window armed lists with its own
bear months:

- 1991-98: **1998-09 and 1998-10 fired at every level from 42.9% to 75%, in both arms**
  (3 of 4: pe, rule20, umcsent). Forward 12 months +26.1% and +24.1%. The memo's table
  says 0.
- 2003-04: 2003-02/03 fired at 42.9% and 50% (2 of 4). The table says 0.
- 2016-18 and 2020-08: 0, correct (composite 1–2 of 6; no bear month in the 2020 window).

The windows are not drawn to make it true; the column was simply derived wrongly. The 1998
firing is the LTCM correction ahead of a +20% year — exactly the joint false positive the
higher line was meant to guard against. It does not separate 57.1% from 62.5% (both are
3 of 4 at n = 4), so the correct statement is "melt-up firings are identical at both live
candidates", not "cost nothing".

One thing the memo missed here: 1998-09/10 is **not** in the filed `act_spans`, because the
filed map scored NFCI on today's backfilled vintage (3 of 5 = 60%, below 62.5%). The
real-time treatment, by deleting NFCI from the denominator, adds a 1998 joint false positive
at every candidate level. The record presents the real-time arm as strictly more faithful;
it also manufactures a firing the dashboard never had.

## C. NFCI real-time treatment — first vintage CONFIRMED, bias direction not stated and decisive

Probed directly: `alfredgraph.csv?id=NFCI&vintage_date=2011-05-18` and `2011-05-24` return
404, `2011-05-25` and `2011-06-01` return 200 (33,431 bytes, history from 1973-01-05). The
absence handling in `nfci_at` is coherent: `None` before 2011-05-25, the gauge drops out of
`statuses`, the denominator shrinks. The expanding rank is computed from the vintage's own
history as declared.

The memo says the absence "changes pre-2011 denominators and therefore what a share meant
then" and stops. The direction is computable and it is the whole result. NFCI on today's
vintage in the discriminating months is +0.56 to +2.14, ranks 77 to 91 — tight, quiet.
Removing a quiet gauge raises the share: 3 of 5 = 60% clears 57.1%; 3 of 6 = 50% does not.
The study's own comparability arm confirms it:
`current_vintage.levels["57.1"].B_excl.fired` contains no month between 2003 and 2020. Set A
(NAAIM added, six gauges in 2007-09) at 57.1% real-time: no GFC month either. Any sixth
gauge, whichever it is, deletes the finding.

The memo's line "on the prior studies' own current-vintage basis the same comparison is
62.5% → 2 fired months and 57.1% → 7: the direction holds" is true as counts and conceals
that the headline finding does not replicate on the arm the PREREG said would not be less
privileged. The current-vintage 7-versus-2 difference is itself the n = 5 lumpiness in
1990-2006 (3 of 5 versus 4 of 5 with NFCI present), not the GFC.

For the question actually being decided — which share to store for a seven-gauge set that
includes NFCI — the comparability arm is the relevant one, and on it the two live candidates
produce identical Lens-2-path firings in every month of the sample.

## D. The 2021 result — CONFIRMED in the lag arm, arm-dependent and unlabelled

Real-time, IPO lag arm (n = 7): 57.1% arms 2021-03→11 at lags 3, 7 and 14; 62.5% arms
2021-09/10 at lags 3 and 7, 2021-08/09/10 at lag 14. "Six months later, five at the 14-day
lag" is exact. Fired counts are identical across all three lags. AAII at 2021-03-25 is +30.4
in the cache (AAII's article says +30.3, display rounding); the cache agrees with the
repository's eight overlapping weeks to 0.045 pp.

But the memo's 2021 table is the lag arm and does not say so. In the excl arm (n = 6) both
candidates arm 2021-09/10 and nothing else — they are the same rule at six gauges. "The
conclusions above hold in each [arm]" is false for H3. The lag arm is the defensible one for
2021 (issuance was a record under any rule), which the memo should say rather than leave the
reader to discover. NFCI is near-line in 2021-02/03/07/08/09/10; the 2021 window has 13
cannot-call months in the JSON and the memo's 2021 table reports none.

## E. Does the recommendation follow? — DISPUTED; the filed signal map answers the memo's own caveat

The memo names Lens 1 redundancy as an open check requiring a separate study. It is
answerable from `data/signal_map.json`, which the study already read for the act-span check.
`lens1_spans` has Lens 1 elevated continuously **2007-08-31 → 2010-05-28**. All seven
discriminating months fall inside it, and all seven fall inside filed `act_spans`
(2007-12→2008-03 and 2008-06→2009-03). Under the rule as coded, `(l1 or l2) and l3`, the
risk-reduction signal fired in every one of those months under the stored line already. The
2009-02/03 "cost" is likewise already delivered by Lens 1.

So under the full rule, 57.1% and 62.5% produce identical outcomes in every month from 1988
to 2026. The only Lens-2-path firings that are not also Lens 1 months are 1998-09/10 and
2000-10/11/12, and both candidates fire all five. H5 is confirmed for the Lens 2 path in
isolation, which is not the rule; for the rule, H5 fails as the PREREG predicted, and the
PREREG's own consequence applies: "the level cannot be chosen on signal outcomes at all".

On the metric switch: applied to the first study's question, fired months say nothing — 2021
fired at no level, 2016-18 at no level, 1998 at every level. The reversal is carried entirely
by seven months in a 57-month five-gauge era, on three earnings-collapse readings, two of
them cannot-call, already covered by Lens 1. That is not evidence for a level; it is the
denominator.

Also mislabelled: at n = 5, 42.9%, 50% and 57.1% are all 3 of 5, so the "3 of 7" candidate
the memo rules out produced exactly the same GFC firings as the one it recommends; its extra
firings are 2-of-4 and 3-of-6 months. And no candidate fires through the Lens 2 path in the
Lehman months 2008-09→2009-01 (2 of 5 = 40%): the path dropped out before the crash and
re-fired at the bottom.

## F. The Lens 3 guard — act-span check CONFIRMED, not independent; gap closed by my recompute

10 of 10 act spans contain a reconstructed bear month (38 bear months inside spans, 31
outside — the memo's 31 is right). But `forward_returns.py` lines 95–102 build the act spans
from the same formula on the same `gspc.json`, so the check is two implementations of one
formula agreeing on one file. It is broader than the single-month check, not stronger. The
PREREG guard as written ("every month where the live status exists") was unimplementable:
`data/lens3.json` holds one status. My independent recompute with the live module's
functions is the check that closes the gap; nothing rides on it.

## Other probes

IPO arms: fired lists are identical between excl and lag at 57.1% and above; no headline
flips. The memo's headline "Armed months" column is the lag arm (205/189/113/94/77/75/16) —
the arm the PREREG says is not the live gauge — unlabelled.

Mid-August 2026 week: disclosed in PREREG and `thresholds.json`. Confirmed.

## Verdict: DO NOT SIGN

The record repaired what the first review asked for — NFCI on vintages, the joint rule
computed, the 42.9% row, the date, the disclosure, the published-file discipline — and the
freeze is genuine. But the finding it built on those repairs is a denominator artefact:
3 of 5 with NFCI absent, not 4 of 7; it vanishes with any sixth gauge and on the study's own
comparability arm; two of its seven months are cannot-call under the PREREG; the "cost
nothing" table is wrong in two of four windows and hides a 1998 joint false positive the
real-time treatment itself created; and Lens 1, already in the filed signal map, fired every
one of those months anyway, so the full rule's outcome is identical under both candidates in
every month of the sample.

What survives is a real-time arming-month difference in 2021 in one IPO arm, which the memo
itself classes as not an outcome. On this evidence the level is undecidable on outcomes —
H5's predicted result — and the choice reverts to the judgement the PREREG promised. The
honest basis for that judgement is the 2026-07-03 intent (5 of 8 with IPO was adopted as
"the modern equivalent of the 4-of-7 line" reconstructed without IPO), and on today's seven,
which include IPO, that intent maps to 5 of 7 at least as naturally as to 4 of 7. Two studies
in one day have each produced a confident recommendation from the structure of a small
denominator; the pattern is worth noting when the third is commissioned.

A re-filed record needs: fired months reported net of Lens 1 from the filed `lens1_spans`;
the comparability arm as primary for the "which rule for today's set" question, with the
real-time arm as the fidelity check; the cannot-call rule applied to every window including
the GFC; the melt-up table corrected; every table labelled by IPO arm; and the recommendation
stated as undecidable on outcomes with the judgement basis exposed.
