# PRE-REGISTRATION — Does a spike in the 10-year Treasury yield derail an equity bull market?

- Written **2026-09-13 (Sunday, SGT — weekday verified with `datetime`/`dateutil`, not from memory)**,
  before any code and before any data beyond the Step-0 availability probes named in §3.
  **Status once committed: FROZEN.** Post-results changes to any parameter, gate or verdict rule are
  prohibited; correctness bug fixes are permitted, must be logged in the running memo, and force a
  rerun of the whole battery.
- Context: **Personal.** Source under test: BCA Research, Chart 17, "Treasuries Need Much Bigger
  Spike To Derail Bull Market", © BCA Research 2026, retrieved as an image 2026-09-13. Series shown:
  US 10-year Treasury yield, 3-month change, basis points, approximately 1995 to 2026; chart source
  line "US Department of Treasury"; note line "shading denotes US bear markets and 20% market
  corrections".
- Licensed vendor material. **No BCA series values, chart or threshold is reproduced anywhere in this
  study's outputs.** Their +100bp line is treated as a *published claim to be replicated*, in the
  manner of the Johnston 3.5% credit threshold in `studies/2026-08-29_spx-washout-gauges_PREREG.md`,
  never as an adopted threshold of ours. Our own thresholds are derived independently in §4.
- Every figure transcribed from the image in §1 is **approximate, single-source and unverified**.
  They are replication targets, never inputs.
- Not investment advice. **Intended tier: Fable 5** for the confirmatory pass (§9).

## 0. Prior work inherited (`/ledger-check`, 2026-09-13 — verdict NOT COVERED, three adjacent records)

Searched `studies/hypotheses_index.md` whole (220 records; coverage 133 of 134 rows, so a miss there
is weak evidence) and grepped `STUDIES_LEDGER.md` on *rate shock, yield spike, 10-year Treasury, 10y
yield, DGS10, term premium, bond/equity*. No record tests a rate-change signal against equities.

- `2026-07-03-market-regime-dashboard-3` (†, unreviewed extraction): "any single lens works as a
  standalone market timer" — REJECTED. Cause of death: *no lens separates forward returns from the
  unconditional base; lenses are state descriptions, not timers.* This is the house prior the source
  chart asks us to violate, and it is why §6 forbids any adoption consequence.
- `2026-08-08-event-studies-3` (†): the lead-triage filter — only PRICE-based vendor leads reproduce
  on our data. A Treasury yield change is price-based and free from FRED, so this lead is
  **admissible** where sentiment, breadth and proprietary-indicator leads were data-gated.
- `2026-08-30-spx-washout-gauges-6`: credit (Baa − 10y) is the binding crisis gauge. That is the
  *spread*, not the level or change of the risk-free yield. Disjoint from this question, but it
  means any surviving rate-shock gauge must be shown not to be a credit gauge in disguise (§5, H1c).
- `2026-09-12-market-regime-dashboard-1..5`: the seven-gauge alarm-level question, all five rejected
  and now parked (commit 8223890). **Adding an eighth gauge reopens it.** §6 binds accordingly.
- Daggered records are unreviewed extractions; confirm against the filed document before any detail
  becomes load-bearing.

### 0b. PRIOR LOOKS (seen-data doctrine, `studies/2026-09-03_prereg-design-lessons.md` §5)

| Panel | Statistic family | Cells read | Verdict / direction | Use here |
|---|---|---|---|---|
| DGS10 3m-change × SPX bear/correction shading, **~1995–2026** | rate-spike events vs equity drawdowns | the whole window, visually, at chart resolution, by BCA and by this session | direction: large spikes appear mostly NOT to coincide with shading | **PRIOR, not evidence.** No confirmatory status may be claimed on this window |
| DGS10 3m-change × SPX, **1962–1994** | same family | none — the chart does not show it | — | **CONFIRMATORY SET** |
| SPX monthly forward returns 1970→ | lens-conditional forward returns | `2026-07-03-market-regime-dashboard-3` | rejected | machinery reused; different family |

Confirmatory set: **(DGS10 × SPX, 1962-01 to 1994-12) and the post-freeze accrual.** Mandatory
different data: yes, for any positive claim about H1 — the modern window is SEEN through the chart,
so a pass there is replication, not discovery, and must be labelled as such.

A results file is opened at its declared-cells view only; opening the full grid is a look and is logged.

## 1. The claims under test (transcribed from the image 2026-09-13; all figures approximate)

| # | Claim | Their figure |
|---|---|---|
| C1 | A ~+100bp 3-month rise in the 10-year yield is the level at which Treasuries threaten equities | dashed reference line at +100bp |
| C2 | Such spikes are rare | approximately 7 circled episodes in ~30 years: ~1996, ~2003, ~2004, ~2009, ~2010–11, ~2022, ~2023–24, ranging roughly +105 to +150bp |
| C3 | The derailment threshold lies ABOVE anything recently observed — "much bigger spike" needed | title; current reading approximately +30bp |

**What the chart does and does not establish, read honestly.** The circles mark spikes, not
spike-and-bear coincidences, and whether each sits inside a shaded band is **not determinable at
image resolution** — that alignment is a thing this study measures, not a thing to read off the
picture. If the circled spikes mostly did not coincide with shading, the chart's content is a *null
result* (spikes up to ~150bp did not reliably derail bull markets, n ≈ 7), which C3 then converts
into a positive statement about where a threshold lies. That conversion is the weakest step: if no
observed spike derailed anything, the series contains **no information about the level that would**.
A threshold cannot be located above the maximum observation. C3 is therefore not a finding but an
extrapolation beyond the sample's support, and §5 H3 tests exactly that.

The second weakness is directional. C3 is consumed as comfort — *no spike, therefore the bull is
intact* — which requires a spike to be a **necessary** condition for a drawdown. The chart shows
nothing about that direction, and it is cheap to measure (H2).

## 2. The question

Three, in descending order of what the data can actually settle:

1. **Necessity (H2, descriptive, needs no power).** Of the SPX drawdowns of at least 20% since 1962,
   what share was preceded within six months by a rate spike? This single number decides whether the
   absence of a spike is worth anything as comfort. It is a count, not an inference.
2. **Sufficiency (H1, inferential, expected to be underpowered).** Does a spike raise the probability
   of a subsequent large drawdown, or depress forward returns, against a count-matched null?
3. **Locatability (H3, structural).** Does any observed level of the 3-month change separate
   outcomes, such that a "derailment threshold" is identifiable at all?

**What this study is for.** It is knowable in advance that H1 will be thin: seven to perhaps twenty
independent episodes. Under the power rule in §5 that most likely demotes H1 to a disclosure
returning UNRESOLVED. The deliverable is therefore **H2 and H3** — a hard count and a structural
read — with H1 as an honestly-labelled disclosure. Running this expecting a verdict on H1 would be
running it for the wrong reason.

## 3. Data (Step 0 = FAIL_STOP availability probes; any failure stops the study, no partial run)

- **Rates:** FRED `DGS10`, 10-Year Treasury Constant Maturity Rate, daily, from 1962-01-02, via the
  existing keyless `fredgraph.csv` path in `scripts/sources/fred.py` (curl-first per house practice).
  Not revised, which removes a vintage problem the labour series have.
  **Series-ID status:** `DGS10` is already identity-checked in this repo — `VERIFICATION.md` records
  max absolute difference 0.0000 between `T10Y3M` and `DGS10 − DGS3MO` over 250 observations, against
  a Treasury.gov second source. But that file explicitly scopes `DGS10` to "verification arithmetic
  only". This study **promotes it to a primary decision series**, so it requires its own
  `VERIFICATION.md` entry with a two-source value check (FRED versus the Treasury daily par yield
  curve) on at least three dated observations, written before any outcome statistic is computed.
- **Equities:** `^GSPC` daily closes via `scripts/sources/prices.fetch_yahoo_daily`. **Price-only, no
  dividends** — disclosed. Conditional and base statistics are computed on the identical basis, so
  the comparison is like-for-like; absolute return levels are understated throughout and the write-up
  must say so wherever a level is quoted.
- **Window:** 1962-01-02 to the last complete session. Split at 1994-12-31 into the SEEN arm
  (1995→, the chart's window) and the CONFIRMATORY arm (1962–1994).
- **Step-0 probes (all must pass):** `DGS10` returns at least 15,000 observations with first date on
  or before 1962-01-31 and no gap exceeding 15 sessions outside known market closures; `^GSPC` daily
  present from on or before 1962-01-31 with at least 15,000 observations; the 1962–1994 arm holds at
  least 8,000 common sessions; the two series align on at least 98% of sessions after holiday
  reconciliation; `python -m unittest discover -s tests` green before and after any code lands.
- **No new third-party imports.** Every dependency is already in the repo. (The 2026-07-04 CI failure
  came from an import absent from `requirements.txt`; if any import is added it goes in that file in
  the same commit.)

## 4. Signal definitions (frozen)

**The shock statistic**, measured on trading days, 63 sessions ≈ 3 months:

- **A1 — absolute (the replication arm):** `y_t − y_{t−63}`, in basis points. This is the claim as
  published and is the arm in which C1/C2/C3 are replicated.
- **A2 — proportional:** `y_t / y_{t−63} − 1`.
- **A3 — vol-scaled (the design arm):** `(y_t − y_{t−63}) / σ_{t−63}`, where `σ` is the standard
  deviation of 63-session changes over the **10 years ending at t−63** — the estimation window closes
  before the measurement window opens, so no part of the measured move informs its own scaling.

A1 is primary for replication; **A3 is primary for any design or adoption read**, because an absolute
basis-point threshold is not like-for-like across a sample in which the 10-year ran from roughly 0.5%
to roughly 16%. A +100bp move on a 1.3% base and on a 7% base are not the same shock in discount-rate
or duration terms, and a rule stated in basis points will mechanically fire more in high-yield, high-
volatility eras. That is the single most likely source of a spurious result here.

**Thresholds.** Ours are percentiles of the full-window distribution of the arm's statistic —
**p90, p95, p99; headline p95** — computed once on 1962→ and frozen before any outcome is read.
BCA's +100bp is reported **alongside**, as a replication of C1, never as our threshold.

**Trigger.** A trigger is the first session on which the statistic crosses the threshold from below
with no crossing in the trailing 126 sessions (≈ 6 months). **Episode = trigger**; there is no
merging beyond that rule. The realised trigger list, and the per-decade trigger counts, are printed
**before** any outcome statistic is computed (§7 guard 3).

**Outcomes**, all measured from the close of the session following the trigger (no signal-close
fiction; `DGS10` publishes with a one-business-day lag, so one full session of slack is structural):

- Forward price return at 63 / 126 / **252 sessions (headline — "derail the bull market" is a slow
  claim)**.
- `MaxDD252`: the largest peak-to-trough decline of `^GSPC` closes within the 252 sessions after
  entry, measured from the running maximum within that window.
- Indicator outcomes: `MaxDD252 ≤ −10%` and `≤ −20%`.

**The drawdown set for H2**, defined independently of any rate data: a drawdown is a decline of at
least 20% in `^GSPC` daily closes from a running all-time high to the subsequent trough, the trough
being the minimum before the running maximum is recovered. Overlapping declines are one drawdown.
The peak date is the reference date for the lookback.

**Date handling.** All date arithmetic through `datetime`/`dateutil`/pandas (**Python months are
1-indexed**). Session offsets are index-based on the trading calendar, never calendar-day arithmetic.
Unit tests include one month boundary and one year boundary, per the repo rule.

## 5. Hypotheses, metrics, nulls and power

**Nulls.** Two, both **count-matched** — each draws the realised number of triggers with the realised
cluster structure, and is scored through the comparator's own code path:

- **N1 (uniform):** trigger dates drawn uniformly over the window, realised count, minimum 126-session
  separation enforced as in the signal.
- **N2 (era-stratified):** as N1, but the per-decade trigger counts are matched to the realised ones.
  **N2 is the comparator that matters:** it isolates whether the signal carries information beyond
  "it fires in bad decades". A whole-window resample of the unconditional series is **not** a null for
  a conditional statistic and will not be computed or cited (`prereg-design-lessons` §3.3).

2,000 draws, seed 20260913, both nulls, both arms, all three thresholds.

**H2 — necessity (primary deliverable; descriptive, no null, no power requirement).**
Of the drawdowns of at least 20% since 1962, the share preceded within **126 sessions** of the peak by
an A1 trigger at the p95 threshold, and separately at BCA's +100bp. Reported drawdown by drawdown with
dates, so the reader sees which bears had a rate shock in front of them and which did not. Lookback
sensitivity at 63 and 252 sessions, declared in advance. The same table is produced for A3.

**H1 — sufficiency (inferential).**
- **H1a:** `P(MaxDD252 ≤ −20%)` after a trigger exceeds the unconditional base rate.
- **H1b:** the median 252-session forward return after a trigger is below the unconditional base.
- **H1c (contamination check, reported):** the same two statistics conditioned on triggers at which
  the Baa − 10y spread was below 3.5% — that is, rate shocks that were not also credit events, so a
  surviving effect is not `2026-08-30-spx-washout-gauges-6` in disguise.

**H3 — locatability (structural, reported, no gate).**
The outcome statistics by decile of the shock statistic, plus the maximum observed value of each arm
and the outcomes at the top decile. **Pre-committed reading:** if outcomes do not separate
monotonically across the upper deciles, the registered conclusion is that *the series cannot locate a
derailment threshold in either direction*, and C3 is unfalsifiable on this evidence rather than true
or false. This outcome is a result, not a failure.

**POWER — one line per verdict-deciding clause** (`prereg-design-lessons` §3.5, applied):

- **H1a.** Effect size δ it must detect: **+15pp** on `P(MaxDD252 ≤ −20%)` over base — below that a
  gauge is not worth a seat. Null: N2, count-matched and era-stratified.
- **H1b.** δ: **−5pp** on the median 252-session forward return. Null: N2.
- The runner computes power at δ from N2 **at run time**, writes it beside the clause, and applies the
  pre-committed consequence: **power below 0.80 demotes the clause from gate to DISCLOSURE.** A
  demoted clause that fails is **UNRESOLVED** and cannot return a negative verdict on its own; a
  demoted clause that passes is **SUGGESTIVE**, reported with its exaggeration ratio (Gelman–Carlin
  type M), and cannot carry a CONFIRMED verdict on its own.
- The verdict mapping in §6 is written over gate-status clauses only, so it stays reachable when H1a
  and H1b are demoted — which, on an expected 7 to 20 episodes, is the likely case.
- Sub-sample quantifier: the SEEN (1995→) and CONFIRMATORY (1962–94) arms are each scored separately.
  A demoted arm is reported as UNRESOLVED at its stated MDE and does not carry a verdict alone.

**Multiple-testing budget (exhaustive; nothing outside this list may be reported as evidence).**
Arms {A1, A2, A3} × thresholds {p90, p95, p99} × window arms {full, 1995→, 1962–94} for the H1a/H1b
statistics at {63, 126, 252}; the +100bp replication cell in A1 only; H2 at lookbacks {63, 126, 252}
for A1 and A3 at p95; H1c at p95; H3 deciles for A1 and A3, full window.

**Inference discipline.** The episode is the unit. Trigger counts, not day counts, are headlined in
every table and in the abstract. No pooled t-statistic over overlapping 252-session windows will be
computed or cited. Every branch of the verdict carries the THIN flag where the arm holds fewer than
20 triggers.

## 6. Decision gates and verdict mapping (frozen)

| Verdict | Condition | Bound consequence |
|---|---|---|
| **NECESSITY-VOID** | H2 share below 50% at the primary lookback | The absence of a rate spike carries no information about equity risk. The comfort reading of C3 is void and is recorded as such. Memo only. |
| **NECESSITY-WEAK** | H2 share 50% to 70% | Recorded as a partial precondition, not usable alone. Memo only. |
| **NECESSITY-HOLDS** | H2 share at or above 70% | The spike is a candidate necessary condition. **Even here, no adoption** — routes to §6 adoption clause. |
| **SUFFICIENCY-*** | H1a and H1b as scored, with gate or disclosure status attached | Reported with power, MDE and, where SUGGESTIVE, the exaggeration ratio. |
| **NOT-LOCATABLE** | H3 shows no monotone separation in the upper deciles | C3 is unfalsifiable on this series. This is the registered expectation. |

**Adoption clause, binding whatever the verdict.** Nothing from this study is wired into the
dashboard by this registration. Two independent reasons: `2026-07-03-market-regime-dashboard-3`
holds that no single lens times the market, so the ceiling here is a gauge, not a signal; and the
seven-gauge alarm-level question was **parked** on 2026-09-12 with a guard as its revisit trigger, so
adding an eighth gauge silently reopens a question the owner closed. Any adoption requires a separate
kickoff, after that question resolves, and states the new alarm level explicitly.

**Accrual clause (the only true out-of-sample).** The modern window is SEEN through the chart and the
1962–94 arm is read once, here. Whatever the verdict, the frozen A1 and A3 definitions at p95 are
scored prospectively on the next trigger after the freeze date. The registration IS the freeze.

## 7. The three ways this will be silently wrong (each guard verified by making it fail first)

1. **Overlapping windows counted as independent observations.** Sixty-four years of daily data on a
   63-session change produces tens of thousands of rows and perhaps a dozen independent events; a
   pooled p-value over them would be confidently wrong. This is the failure mode that produced
   "thin n=3, IGNORE" in `2026-08-08-event-studies-2` and "4–7 usable events in 28 years" in
   `2026-08-01-breadth-thrust-signal-3`.
   *Guards: 126-session re-arm; episode as the unit; count-matched N1/N2; trigger counts headlined;
   power computed and the demotion rule applied mechanically. Failure drill: score N2's own draws as
   if they were the signal — the pipeline must return the null value.*
2. **The modern sample is SEEN, so a pass there is replication dressed as discovery.** BCA chose the
   +100bp line and the circled episodes after seeing this data; this session has now seen the same
   picture. Treating 1995→ as a test would be threshold-shopping at one remove.
   *Guards: the PRIOR LOOKS table in §0b; percentile thresholds derived on the full window rather
   than eyeballed; 1962–94 declared as the confirmatory panel before any look; the accrual clause;
   the +100bp cell labelled REPLICATION in every table it appears in.*
3. **Non-stationarity doing the work.** A1 will fire far more often when yields and yield volatility
   are high, and those eras differ from the modern one in inflation, policy regime and equity
   valuation. An apparent effect could be pure era selection.
   *Guards: the A3 vol-scaled arm; per-decade trigger counts printed BEFORE any outcome statistic;
   N2 era-stratified as the decisive comparator; the SEEN/CONFIRMATORY split reported separately
   rather than pooled. Failure drill: run A1 on a synthetic yield path with the realised volatility
   term structure but no relationship to equities — the per-decade trigger counts must still
   concentrate, and N2 must then price that concentration away.*

A fourth, data-layer: **look-ahead through the scaling window and the publication lag.** *Guards:
A3's σ window closes at t−63; entry at the session after the trigger; a +1-session input-shift
mutation test on `DGS10` must change the trigger set, or the series is not actually wired in.*

## 8. Pre-registered predictions (stated so they can be wrong)

1. **H2 returns NECESSITY-VOID** — below 50%, and I would put roughly 70% odds on it. Specifically I
   expect the 2000–02, 2008–09 and 2020 drawdowns to carry no preceding A1 trigger; in two of those
   yields fell hard into the decline.
2. **H1a and H1b are both demoted to disclosures and return UNRESOLVED**, roughly 85% odds, on an
   episode count in the 7 to 20 range per arm.
3. **A1 trigger counts concentrate pre-1995 by a factor of three or more** against the post-1995 rate;
   A3 roughly stabilises them. Roughly 75% odds. If A1 does *not* concentrate, my non-stationarity
   objection is weaker than stated and the write-up must say so.
4. **H3 returns NOT-LOCATABLE.** No monotone separation across the upper deciles.
5. Directional, no gate: in the 1962–94 arm, rate spikes and equity weakness co-occur more strongly
   than in the modern arm, because inflation was the common driver. If the modern arm is the stronger
   one, that is evidence against my whole framing and is to be reported as such.

If predictions 1 and 4 both land, the honest summary of the source chart is that it shows a null
result with n ≈ 7 and reads a positive conclusion off it in both directions.

## 9. Why the tier matters

Every failure mode here is quiet: a null that is not count-matched, an era effect read as a signal,
a threshold chosen after the picture, a p-value over overlapping windows. Each returns a confident
wrong answer rather than an error. There is no mechanical dashboard phase in this study.

## 10. Filing and scope

On completion: a row in `C:\dev\STUDIES_LEDGER.md`; one record per tested hypothesis in
`studies/hypotheses.yaml`; regenerate the index; all four guards green (`ledger_parse.py --check`,
`check_register.py`, `build_register_index.py` then `--check`). Running memo at
`reviews/2026-09-13_rate-shock.md`; code at `scripts/rate_shock_study.py`, **run on demand and not
added to any scheduled workflow** (the `forward_returns.py` precedent); outputs under
`reviews/2026-09-13_rate-shock/`, with `_declared.json` holding the budget's cells and
`_full.json` everything else — the verdict reader opens the first, and opening the second is a look
and is logged. A `VERIFICATION.md` entry for `DGS10` as a primary series lands before any outcome
statistic is computed. No public page, no dashboard change, no scheduled task from this study; any
deployment consequence routes through the adoption clause in §6 only.

**Owner sign-off: given 2026-09-13 in session. This commit is the freeze** — from here the document
is immutable except for logged correctness fixes, which force a rerun of the whole battery.

---

## Amendment 1, recorded before any figure existed — a second vendor chart arrived, and it is a LOOK

Received **2026-09-14 (Monday, weekday verified with a date library)**, before `rate_shock_study.py`
existed, before any Step-0 probe had been run, and before any figure in this study had been
computed. Recorded here rather than absorbed silently, because the SEEN-data doctrine treats the
declaration as the thing that makes a confirmatory claim meaningful.

**What arrived.** A Goldman Sachs chart, "When does it hurt?", captioned as a reminder on when
rising rates start to hurt stocks. It plots the **average 1-month S&P 500 return** by bucket of the
**z-score of the 1-month change in the 10-year US Treasury yield, scored against the past three
years**, with paired bars for nominal and real yields, over buckets `<(2), (2)-(1), (1)-(0.5),
(0.5)-0, 0-0.5, 0.5-1, 1-2, >2`, and an annotation that 2σ today is approximately 60bp. Licensed
vendor material: no value, bar or bucket of theirs is reproduced in this study's outputs, and as
with the BCA +100bp line, anything of theirs is a replication target and never an adopted threshold.

**Why it is a look and not merely context.** Under D1 a LOOK is any human read of an outcome
statistic computed on a panel with a rule definition. This is exactly that: a rule (z-scored rate
change, bucketed) and an outcome statistic (average S&P return) on the US 10-year-versus-S&P panel.
Under D2 the unit is the pair (panel, statistic family), and the family here — a **volatility-scaled**
rate-change statistic — is the family of this study's **A3 arm**, which §4 names primary for any
design read. The §0b table is therefore incomplete as frozen, and this amendment extends it.

| Panel | Statistic family | Cells read | Verdict / direction | Use here |
|---|---|---|---|---|
| 10-year yield z-scored 1m change × S&P 1m return, **window unstated** | vol-scaled rate-change buckets, nominal and real | all eight buckets, both yield types, as bucket means | direction: **both tails negative**, middle positive — an inverted-U | **PRIOR, not evidence.** Extends the §0b declaration to the A3 family |

**Three consequences, none of which touches a parameter, gate or verdict rule. The freeze holds.**

1. **The confirmatory panel is downgraded, not voided.** §0b declared 1962–1994 confirmatory
   because the BCA chart does not show it. This chart states no window at all, so it may reach into
   that period. Under D4 a family read on a superset is seen to the extent of the overlap. The
   overlap is partial and the statistic differs — 1-month change against my 63-session change, a
   3-year scaling window against my 10-year one, bucket means against my trigger-episode statistics
   — so the honest grade is **probably unseen, window unstated**, and 1962–1994 is reported as a
   weaker confirmation than §0b claimed. **The post-freeze accrual is now the only uncontaminated
   confirmation**, which was already the accrual clause's claim and is now the binding one.
2. **The conservative reading is registered, and it is the one that constrains this study more.**
   The chart does not say whether its outcome is the *same* month's equity return or the *following*
   month's. A coincident statistic would tell me almost nothing about my forward statistic and would
   be the convenient assumption; a forward statistic makes this a near-neighbour read of my A3
   family. **It is treated as a look at both readings.** Assuming coincidence would let me claim
   later that an A3 result was unforeseen when it may not have been.
3. **No prediction is revised.** The §8 predictions were written on 2026-09-13 and stand exactly as
   registered. The chart's inverted-U shape — large falls in yields as damaging as large rises — is
   consistent with prediction 1, that necessity fails because bears arrive without rate spikes and
   sometimes with yields collapsing. That consistency is noted and the 70 per cent odds are **not**
   moved. Updating a registered lean towards a chart seen after the freeze is the precise failure
   this document exists to prevent.

**One successor question, named and explicitly NOT tested here (Amendment 1).** The chart's shape suggests the
operative variable is the **magnitude** of the rate move in either direction — a volatility effect —
rather than a rise specifically. This registration is spike-only by construction: every trigger in
§4 is a crossing from below a high threshold. A two-tailed test is a different hypothesis, and
adding it now would be a post-hoc hypothesis fitted to a chart. It requires **fresh
pre-registration** inheriting this record, and its own answer to the question that decides whether
it is tradable at all: whether the relationship is coincident or forward. A coincident relationship
between a monthly rate change and the same month's equity return is a correlation, not a signal —
the rate change is not known until the month it describes has ended.

## Amendment 2, recorded before any figure existed — the equity history does not reach 1962

Recorded **2026-09-14 (Monday, weekday verified with a date library)**, after the Step-0 probes ran
and before the battery was written. Step-0 probes are availability checks and are explicitly **not
looks** under D1, so nothing about any outcome informed this amendment: no forward return, no
trigger, no drawdown and no bucket had been computed when it was written. Owner decision taken in
session on the same day.

**What failed.** Three of seven probes, all one cause. `^GSPC` through this repository's Yahoo path
starts **1970-01-02**, not 1962: `period1=0` is the Unix epoch and the endpoint refuses a pre-epoch
request rather than serving earlier bars. So §3's registered window is unattainable from §3's
registered source — 14,295 equity observations against a 15,000 bar, and a 1962–1994 confirmatory
arm of 6,233 common sessions against a bar of 8,000. The bar was set on my own unverified
assumption about what the source serves, which is precisely the assumption §3 exists to test before
a result can be fitted around it. It also matches this repository's own history: `forward_returns.py`
has always been bounded at 1970 for the same reason.

Two alternatives were checked and closed before the amendment was proposed. A negative `period1` is
refused by the API. Stooq now sits behind a JavaScript proof-of-work bot check, which is not
something to defeat. A third, moving the equity source to the licensed Norgate history, was put to
the owner and declined: this repository is public, so licensed history could not be committed here
and the study would have to move to the private vault, contradicting §10.

**What is amended, and it is one thing.** The study window becomes **1970-01-02 to the last
complete session**. The confirmatory arm becomes **1970-01-02 to 1994-12-31** (6,233 common
sessions); the SEEN arm is unchanged at 1995 onward.

**What is NOT amended, deliberately.** The three registered bars keep their registered values. They
are **not** rewritten to numbers the data happens to clear — that would be restating a threshold
after watching it fail, which the register names boundary-shopping, and it would erase the weakness
from the output. Instead:

- Probe `^GSPC observation count` (bar 15,000): **FAILED-AS-REGISTERED**, realised 14,295.
- Probe `^GSPC starts on or before 1962-01-31`: **FAILED-AS-REGISTERED**, realised 1970-01-02.
- Probe confirmatory-arm sessions (bar 8,000): **FAILED-AS-REGISTERED**, realised 6,233.
- Every confirmatory claim in this study therefore carries a standing **THIN** flag, and the three
  failures are reported in the results file and repeated beside the verdict rather than held in a
  footnote.
- The exemption is named and bounded: it covers these three probes and this cause only. Any other
  Step-0 failure still halts the study with no partial run, exactly as §3 registers.

**The cost, stated plainly because it falls on the primary deliverable.** Losing 1962–1969 removes
a stretch containing at least two well-known declines of 20 per cent or more in the S&P 500 — the
1962 break and the 1966 bear. H2 is a *share of drawdowns*, so its denominator is exactly where the
loss bites: the count is computed over a smaller drawdown set than registered, and the write-up
must give the realised drawdown count beside the share every time it is quoted. A share over ten
events is a different object from a share over thirteen, and the reader is entitled to see which
one is on the page.

**No gate, threshold, arm, null or verdict rule moves.** The freeze otherwise holds in full, and
the §8 predictions stand exactly as registered on 2026-09-13.
