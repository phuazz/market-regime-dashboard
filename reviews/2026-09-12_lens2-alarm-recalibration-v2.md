# Lens 2 alarm level on real-time data — running memo (v2)

Date: 2026-09-12 (Saturday) · Project: market-regime-dashboard · Status: FILED, CONTESTED, recommendation WITHDRAWN
Pre-registration: `reviews/2026-09-12_alarm-recalibration-v2/PREREG.md`, frozen in commit
`22e14bf` before any figure existed; two amendments committed in `25c04c7`, also before any
figure existed. Script `recalibrate_v2.py`, output `result_v2.json`, both in that folder.
Supersedes the evidential claims of `reviews/2026-09-12_lens2-alarm-recalibration.md`
(CONTESTED) and answers its adversarial review.

> ## ERRATUM — RECOMMENDATION WITHDRAWN. The level is undecidable on outcomes.
>
> The adversarial read returned DO NOT SIGN
> (`reviews/2026-09-12_alarm-recalibration-v2/ADVERSARIAL_REVIEW.md`). Three decisive
> findings were re-verified against this study's own output before this note was written,
> and all three hold.
>
> **1. The discriminating months are 3 of 5, not 4 of 7.** NFCI is absent before 2011-05-25
> in the real-time arm, so the 2007-09 composite ran on five gauges. Every one of the seven
> GFC months reads `pe, rule20, vvg` triggered on a five-gauge denominator. At n=5, 57.1%
> bites as 3 of 5 and 62.5% as 4 of 5. The sentence "four of seven did, from December 2007"
> describes a rule that was never evaluated: on today's seven gauges those same three
> triggered gauges read 3 of 7 = 42.9%, **below the line this memo recommended**. The
> finding is the missing gauge, not the level — it vanishes on the comparability arm, where
> 57.1% has no GFC firing at all, and it would vanish with any sixth gauge. Two of the seven
> months carry `near_line: ['pe']` and should have been reported as months this study cannot
> call, under its own pre-registered rule. They were counted.
>
> **2. The melt-up table is wrong in two of four windows.** It states zero firings at any
> level in all four. This study's own output has **1998-09 and 1998-10 firing at every
> candidate level**, inside the 1991-98 window, and 2003-02/03 firing at 42.9% and 50%. That
> column was never computed — it was inferred from "Lens 3 never confirmed inside those
> windows", which is also false: the reconstruction has bear months in three of the four.
> The correct statement is that melt-up firings are identical at both live candidates, not
> that they cost nothing. Worse, the 1998 firing is not in the filed `act_spans`: the
> real-time treatment manufactures a joint false positive the dashboard never had, ahead of
> a +20% year.
>
> **3. Lens 1 was already elevated through all seven months.** `data/signal_map.json`
> `lens1_spans` records Lens 1 elevated 2007-08-31 → 2010-05-28, and the filed `act_spans`
> cover 2007-12→2008-03 and 2008-06→2009-03. Under the rule as coded, the risk-reduction
> signal fired in every one of those months at the stored line already. This memo named that
> check as an open question needing a separate study; it was answerable from a file this
> study had already opened for its own guard.
>
> **Consequence.** Under the full rule, 57.1% and 62.5% produce identical outcomes in every
> month from 1988 to 2026. H5 is confirmed only for the Lens 2 path in isolation, which is
> not the rule; for the rule it fails, exactly as the pre-registration predicted — and the
> pre-registration's own consequence therefore applies: **the level cannot be chosen on
> signal outcomes at all.** What survives is an arming-month difference in 2021, in one IPO
> arm, which this memo itself classifies as not an outcome.
>
> The recommendation to move to 4 of 7 is withdrawn. `alarm_share_pct` remains 62.5 and no
> file was changed on the strength of this record. The text below is left as filed.
>
> Both studies today produced a confident recommendation out of the structure of a small
> denominator, in opposite directions. That pattern, not either answer, is the finding worth
> carrying forward.

## What changed, and why the answer moved

The first run scored every gauge on today's data. Two repairs change the result.

**NFCI on the vintages of the day.** The Chicago Fed re-estimates the whole NFCI history
weekly, and the 2016-2019 revisions run one way. Scored as published, the credit gauge sits
in its loosest quintile far more often than today's file suggests.

**The joint rule computed rather than assumed.** The risk-reduction signal is
`(Lens 1 elevated OR Lens 2 armed) AND Lens 3 confirming`, in the same month, with no memory
of an earlier arm. Both prior studies chose the level by counting *arming* months. Arming is
not the outcome; firing is. Counting what the Lens 2 path would actually have delivered is
what moves the answer, and neither prior study did it.

A third finding arrived unbidden and belongs to both prior studies as much as this one:
**ALFRED holds no NFCI vintage before 2011-05-25**, because the index was introduced in 2011
and backfilled to 1971. The credit gauge in every pre-2011 month of both earlier
reconstructions is a hindsight construct. The primary arm below therefore has no credit
gauge before 2011, which is what a reader had; the comparability arm keeps it throughout, as
the earlier studies did.

## Guards

| Guard | Result |
|---|---|
| Lens 3 reconstruction vs the live status | agrees (live benign, reconstructed benign at 2026-09-11) |
| Lens 3 reconstruction vs the 10 filed `act_spans` | **10 of 10** contain a reconstructed bear month |
| Vintage-lag sensitivity (3 / 7 / 14 days) | fired counts identical at all three; one 2021 month differs at 14 days |
| Near-line months, flagged not counted | reported per window below |

The 31 reconstructed bear months outside any filed act span are months where Lens 3
confirmed and no lens was armed, which is what an act span requires.

## Results — the live-equivalent set, real-time data

"Fired" means the **Lens 2 path** alone: the composite armed and Lens 3 confirming in the
same month. The full rule can also fire through Lens 1, which this study does not
reconstruct.

| Level | Armed months | Lens-2-path fired months | Which |
|---|---|---|---|
| 42.9% (3 of 7) | 205 | **30** | dot-com, plus 2001-2003 post-crash, 2008-09, covid 2020-03/04 |
| 50% | 189 | 28 | as above less two |
| 57.1% (4 of 7) | 113 | **14** | 1998-09/10, 2000-10→12, 2001-10, 2002-05, **2007-12, 2008-02, 2008-06/07/08, 2009-02/03** |
| 62.5% (the stored line) | 94 | **7** | 1998-09/10, 2000-10→12, 2001-10, 2002-05 |
| 71.4% | 77 | 7 | identical to 62.5% |
| 75% | 75 | 7 | identical |
| 87.5% | 16 | 2 | 2000-10/11 only |

**The stored line never fired through the Lens 2 path in the global financial crisis. Four
of seven did, from December 2007.** That is the finding, and no amount of arming-month
analysis could have produced it.

On the prior studies' own current-vintage basis the same comparison is 62.5% → 2 fired
months and 57.1% → 7: the direction holds, and the earlier basis understates how often the
path fired.

### Melt-up arms cost nothing, which dissolves the argument both prior studies used

| Window | Armed at 57.1% | Armed at 62.5% | Armed at 71.4% | **Fired, any level** | Near-line months |
|---|---|---|---|---|---|
| 1991-98 | 33 | 33 | 33 | **0** | 28 |
| 2003-04 | 12 | 12 | 12 | **0** | 14 |
| 2016-18 | 18 | 18 | 3 | **0** | 36 |
| 2020-08 | 0 | 0 | 0 | **0** | 0 |

Not one melt-up arm produced a signal, at any candidate level, because Lens 3 never
confirmed inside those windows. An arm that never meets a bear cross is invisible: it
changes no action. The 2026-07-03 calibration chose 62.5% partly to "skip most melt-up
noise", and my first study repeated the reasoning. On the joint rule that cost does not
exist. The one genuinely costly case both cite — a 2018-06 arm paired with the 2018-12 cross
— was never joint: the arm had lapsed six months before the cross, as the adversarial review
established independently.

The near-line column is a real limit, not a footnote: 36 of the months in the 2016-18 window
have a gauge within 5 rank points of its line, so that window's arming counts are soft.

### The 2021 top

| Level | Real-time | Current vintage |
|---|---|---|
| 57.1% | 2021-03 → 2021-11 | 2021-03 → 2021-11 |
| 62.5% / 71.4% | **2021-09, 2021-10** | 2021-03, 08, 09 |

Neither level fired: Lens 3 did not confirm until 2022-03, by which time the composite was
back to 2 of 7. The 2021 episode cannot rank the candidates on outcomes. It does show the
stored line arming six months later than 4 of 7 on the data of the day — five months later
at the 14-day vintage lag.

## Verdicts

**H3 — on real-time data 5 of 7 arms no later than 4 of 7 at the 2021 top: REJECTED, as
predicted.** Six months later (2021-09 against 2021-03); five at the 14-day lag.

**H4 — 5 of 7 makes no melt-up false arm: REJECTED, as predicted.** Eighteen arming months
across 2016-18 at the stored line. The finding is real and, per the table above, immaterial.

**H5 — the level changes what the signal would have done: CONFIRMED, against my stated
prediction.** I predicted no candidate would produce a fired month another did not, which
would have made the level undecidable on outcomes. It is wrong: 7 fired months at the stored
line against 14 at 4 of 7 and 30 at 3 of 7. The level is decidable on outcomes, and both
prior studies chose it on the wrong quantity.

## Reading, and the judgement

Three of seven is out: its extra firings are post-crash 2001-2003 and the covid bottom in
2020-03/04 — reducing risk near lows, which is the expensive error.

Between the two live candidates, four of seven buys the 2007-12 → 2008-08 sequence and costs
two firings at the 2009 bottom. Five of seven avoids those two and forfeits the whole GFC
sequence on this path. Melt-up arms, the traditional argument for the higher line, cost
nothing once the joint rule is respected.

I would move to 4 of 7. The error it prefers — arming often, firing only when the trend
confirms — is the cheaper one on this evidence, because the joint rule already supplies the
discipline the higher line was standing in for.

Two checks would strengthen or overturn this, and both are separate pre-registered studies
rather than additions to this one:

1. **Score the fired months.** Forward returns from each firing would separate the 2007-08
   sequence from the 2009-02/03 pair. This study deliberately did not do it: it was not
   pre-registered, and the composite *level* is already on record as carrying no standalone
   forward-return edge, which is a different question from the joint rule's outcomes.
2. **Reconstruct Lens 1.** If Lens 1 was already elevated through 2007-08, the Lens 2 path's
   GFC capture is redundancy rather than new information, and the case for 4 of 7 weakens to
   the 2021 earliness alone. The 2026-07-03 review calls 2007 "a Lens 1 event", which points
   that way but was never computed.

## Caveats

The primary arm mixes bases by construction: NFCI real-time, six gauges current-vintage. The
direction is stated — current vintage flatters the other gauges' accuracy — and the
comparability arm isolates it. No credit gauge before 2011-05-25 in the primary arm, which
changes pre-2011 denominators and therefore what a share meant then. The IPO gauge is not
reconstructable under the live rule; both declared arms are reported and the conclusions
above hold in each. Near-line months are flagged, not counted, and they are numerous in the
melt-up windows. Monthly grid, so intramonth crossings are missed. AAII from a cached copy
(PREREG amendment 1), NAAIM from a frozen licensed copy ending 2026-07-29, neither written
into this repository.

One shortfall against the pre-registration, disclosed rather than quietly dropped: the Lens
3 guard was specified as a check on every month where the live status exists, and the script
checks only the latest month. The act-span check above was added afterwards to compensate
and is the stronger of the two, but it was not the guard as written.
