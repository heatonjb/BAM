# Stylised Facts for an Enterprise Simulator, and a First Fit

**Question.** A seeded enterprise simulator that reconciles to a ledger can be internally exact and still be economically arbitrary. Exact articulation does not imply that firms in the simulator grow, fail, and disperse the way real firms do. This study measures a small set of firm-level regularities from public XBRL, states them as a validation battery, and scores a moment-matched Gaussian generator against two of them. Matching the battery is necessary. It is not sufficient for behavioural realism, and several regularities a simulator would need are not in the public file at all.

## What was pulled

The XBRL frames endpoint, 24 October 2026, declared User-Agent, one value per CIK [T2] U.S. SEC, EDGAR XBRL APIs, "frames".

| Series | Period | Firms with a positive or present value |
|---|---|---:|
| `Assets` | CY2023Q4I | 6,396 with assets > 0 (6,429 reported) |
| `Assets` | CY2022Q4I | 6,871 |
| `Revenues` | CY2023 | 2,679 |
| `Revenues` | CY2022 | 2,793 |
| `NetIncomeLoss` | CY2023 | 6,387 |
| `NetIncomeLoss` | CY2022 | 6,812 |
| `GrossProfit` | CY2023 | 2,790 |

`Revenues` is not the full revenue universe. A synonym union of standard revenue tags covers 5,344 firms in the same pull. Every growth and margin figure below is conditional on the filer having used the `Revenues` tag, not a contracts-with-customer tag. That is a comparability cut, and it selects against some large operating companies that tag revenue the other way. The moments are for a tag-defined population, not for "US public firms".

Winsorisation, declared in advance: revenue growth kept only if both years are positive and growth is in (−0.9, 5); gross margin kept in (−1, 1.5); profit margin kept in (−2, 2). These cuts remove ratio explosions from a near-zero denominator. They also remove genuine extreme growers above 500%. The tail shares below are therefore lower bounds on extremity.

## The regularities

**Size.** Log assets (natural log of the dollar total), n = 6,396. Mean 19.41, standard deviation 3.63, median 19.99, 10th percentile 15.03, 90th percentile 23.41, skewness −0.94. A symmetric lognormal fitted to that mean and variance is the usual first model of firm size, in the line of Axtell's Zipf finding for establishment and firm counts [T1] Axtell 2001, *Zipf Distribution of U.S. Firm Sizes*, Science 293:1818–1820. The negative skew in the logs is the deviation that matters: the left tail is heavier than a Gaussian in log-assets, or the right tail is thinner. A reporting threshold (small filers, shells, and firms that do not carry a clean instant `Assets` fact) can produce exactly this shape. A simulator that draws log assets from a Gaussian with these two moments will under-represent the small-firm mass relative to this extract, by up to 0.71 log-points at a decile (see the fit section). It will not reproduce a Zipf plot unless the draw is exponential in the log, which a Gaussian is not, in the far tail.

**Growth.** Revenue growth, `Revenues` CY2023 over CY2022 minus one, n = 2,111 after the winsor cut. Mean 0.141, median 0.038, standard deviation 0.654, 10th percentile −0.35, 90th percentile +0.51, skewness +3.66. The centre of the distribution is a low-single-digit grower. The mean is pulled by a right tail. This is the qualitative shape Stanley and co-authors reported for company growth — a tent-like distribution, much heavier in the shoulders than a Gaussian with the same variance, and not a lognormal of the growth rate itself [T1] Stanley et al. 1996, *Scaling behaviour in the growth of companies*, Nature 379:804–806. The skew here is positive rather than symmetric, which a pure Laplace (two-sided exponential) also will not fit. An asymmetric Laplace, or a Laplace in the body plus a separate acquisition tail, is the generator class the numbers point to. A Gaussian is the wrong class, and the fit section measures how wrong.

**Variance declines with size, then stalls.** Growth observations that also have positive CY2023 assets were split into quintiles of log assets (about 405 firms each).

| Size quintile | n | Mean growth | SD of growth |
|---|---:|---:|---:|
| 1 (smallest) | 405 | 0.240 | 1.044 |
| 2 | 405 | 0.149 | 0.692 |
| 3 | 406 | 0.127 | 0.457 |
| 4 | 405 | 0.084 | 0.337 |
| 5 (largest) | 406 | 0.092 | 0.437 |

The standard deviation falls by a factor of three from the first quintile to the fourth. The fifth quintile ticks back up to 0.44. A simulator in which every firm draws growth from one distribution, regardless of size, will fail this table in the first comparison. The scaling is the regularity — roughly, variance falls with size through most of the range, which is the Stanley relation — and the uptick at the top is a warning not to impose a monotone power law all the way through the largest filers, where acquisitions and one-off items dominate a two-year window.

**Gross margin.** `(GrossProfit / Revenues)`, both CY2023, intersection after the cut, n = 1,143. Mean 0.360, median 0.331, standard deviation 0.297, 10th percentile 0.05, 90th percentile 0.77, skewness −0.26. Dispersion is wide: a tenth of the tagged firms sit near a 5% gross margin and a tenth above 77%. Industry mix is inside that dispersion. A single-industry simulator that emits gross margins with a standard deviation of 0.05 is already rejected by this table, even before any behavioural test. A multi-industry simulator must reproduce at least this width, or must condition on an industry and be tested inside that industry. This study did not split by SIC. The unconditional width is the floor.

**Profit margin and its persistence.** Net income over `Revenues`, n = 1,938. Mean −0.067, median 0.035, standard deviation 0.452, 10th percentile −0.67, 90th percentile 0.28, skewness −1.60. The tagged population loses money in the left tail heavily enough to pull the mean below zero while the median firm is modestly profitable. Year-to-year persistence, correlation of the profit margin in CY2022 with CY2023 on the 1,649 firms present in both, is 0.58. Margins are sticky and not fixed. A simulator that redraws profitability independently each period will show a persistence near zero and is rejected. A simulator that freezes each firm's margin forever will show a persistence near one and is also rejected. 0.58 is the target for a two-year gap on this tag population, not a universal constant.

**Inventory and output dynamics** of the kind an object-centric event log can show — cycle time, yield, the variance of receipts versus issues — are not in the frames extract. `InventoryNet` is a stock. It supports a DIO when COGS is present (2,186 firms under a synonym union in the companion measurement) and supports nothing about within-year path. The OCEL inventory simulation used for the reconciliation identity remains the only event-level series in hand, and it is a constructed log, not a panel of firms. No stylised fact about inventory *dynamics* is claimed from EDGAR here.

## The validation battery

Three tiers, in the order a simulator should be forced to pass them. Failing a lower tier makes a higher tier meaningless.

**Tier 1 — conservation.** The ledger identities: trial balance, assets equal liabilities plus equity, cash-flow articulation on a same-period join, retained-earnings roll-forward. These are pass/fail. A simulator that needs a plug to close is not a candidate for tier 2, however pretty its growth charts. This tier was already passed by the append-only prototype on synthetic events. It is listed because economic fit does not relax it.

**Tier 2 — stylised facts, unconditional.** Draw a panel of firms from the seeded generator. Compare to the tables above, on the same winsor cuts:

1. Log-size distribution: mean, sd, skew, and the nine deciles. Maximum absolute decile gap is the headline distance.
2. Growth distribution: mean, median, sd, skew, and the share of observations with absolute growth above 0.5.
3. Growth sd by size quintile: the ratio of quintile-1 sd to quintile-4 sd should be near 3, and the generator must not be forced to be monotone through quintile 5.
4. Gross-margin dispersion: sd near 0.30 unconditional, or a declared industry conditional.
5. Profit-margin persistence over a two-year gap near 0.58, with a negative mean and a positive median.

A fact is "matched" if the generator's statistic lies inside a pre-registered band, not if a plot looks similar. Suggested bands, wide enough to survive the tag-population caveat: decile gap on log assets below 0.3; growth-tail share within 5 percentage points of 0.15; quintile sd ratio between 2 and 4; persistence between 0.4 and 0.7. These bands are a proposal. They were not fitted to a second sample, so they are not a confirmed test. They exist so a later run can fail in public.

**Tier 3 — event-log replay and calibration to a named series.** Replay a real order-to-cash log (or a filer's inventory and revenue quarterly path) through the simulator's operational core and score cycle time, yield, and the quarterly revenue path. Public annual frames cannot support this tier. Quarterly company-facts could support a weak version — four revenue points, not an event log. That pull was not done. Tier 3 is specified so that a tier-2 pass is not mistaken for a finished validation.

## Fit of a moment-matched Gaussian generator

The generator under test is the obvious one, seed 20260820: draw log assets from a Gaussian with the empirical mean and sd, and draw growth from an independent Gaussian with the empirical growth mean and sd. It is the generator a team will ship if the requirement is "match the first two moments" and nothing is said about shape. n equals the empirical n, so sampling error is small relative to the gaps below.

**Log assets, closer than growth.** Empirical deciles (10th through 90th): 15.03, 16.75, 17.93, 19.03, 19.99, 20.80, 21.54, 22.35, 23.41. Gaussian deciles: 14.89, 16.48, 17.62, 18.55, 19.46, 20.46, 21.39, 22.57, 24.12. The largest absolute gap is 0.71 log-points, at the 90th percentile, where the Gaussian is too heavy. Against the proposed band of 0.3, this generator **fails** tier 2 on size, but the failure is a tail-shape failure of a few tenths of a log, not an order-of-magnitude failure. A skew-normal or a mixture (operating firms plus a shell mass) would be the next candidate. A Gaussian is an acceptable scaffold for the body and an unacceptable model of the right tail of this extract.

**Growth, the wrong family.** Share of observations with absolute growth above 0.5: empirical 0.154, Gaussian 0.456. The Gaussian puts nearly half its mass outside ±50% growth because the standard deviation (0.65) is inflated by a skew of +3.66. Matching the variance of a skewed, peaked distribution with a Gaussian overstates both tails and still cannot produce the skew. The generator fails the tail test by 30 percentage points, six times the proposed 5-point band. It also cannot produce the quintile table, because growth is drawn independently of size: every quintile gets sd 0.65, against an empirical range of 0.34 to 1.04.

The corrective generator, not implemented here, is small to state. Draw size from a skew-normal or a two-component log mixture calibrated to the deciles. Draw growth from an asymmetric Laplace whose scale falls with size through the first four quintiles and is flat or slightly higher in the fifth. Draw a persistent profitability component with AR(1) coefficient near 0.58, and an independent shock wide enough to keep the profit-margin sd near 0.45. Then reject any draw that breaks tier 1. That is a specification, not a result. The result is that the moment-matched Gaussian, which is what "calibrated to real series" often means in a slide, fails two of the five tier-2 tests on the first try, and fails the growth test by a wide margin.

## What public data cannot validate

A simulator can match every number in this note and still be behaviourally vacuous. Stylised facts constrain the marginal distributions of outcomes. They do not constrain the mechanisms that produced them. Two mechanisms consistent with a growth sd that falls with size are a real capacity constraint (large firms cannot double) and an accounting artefact (large firms' revenue tags are smoother because they are more diversified). The frames extract cannot tell those apart. A price experiment inside the simulator — the thing a harness is for — has no public counterpart in this file. No frames tag is a demand elasticity. No frames tag is a marketing response. No frames tag is the lag between a decision and its appearance in revenue.

Specifically unvalidatable from this pull:

- Demand elasticity, marketing response, and price paths. Annual revenue is an integral, not a demand curve.
- Within-year inventory dynamics, yields, and cycle times. The stock is annual.
- The effect of an intervention. There is no control firm. Synthetic control would need a treated event and a donor pool; neither was defined.
- Constraint behaviour: covenant breaches, distress financing, the distribution of runway. `NetIncomeLoss` and `Assets` do not encode covenants.
- Agent behaviour. A simulator can be realistic as a data-generating process and still be a bad model of what a manager, or a model, will do. The agent probe is a separate measurement.
- Industry-conditional facts. SIC was not joined. The gross-margin sd of 0.30 is an upper bound on within-industry dispersion, because industry mix is inside it. A simulator of one industry that matches 0.30 is matching the wrong target.

The tag caveat cuts the other way as well. Because the growth panel is the `Revenues` tag and not the synonym union, a generator matched to these moments is matched to a subset. Rebuilding the panel on the synonym union (5,344 firms against 2,679) could move the mean and the tail. Until that rebuild, the moments are provisional on the tag. They are still firm enough to reject a Gaussian growth draw.

## What this establishes

- On the CY2023 frames extract, log assets (n = 6,396) have sd 3.63 and skew −0.94. A Gaussian in the logs misses the 90th percentile by 0.71 log-points.
- Revenue growth (n = 2,111, `Revenues` tag, two-year) has mean 0.14, median 0.04, sd 0.65, skew +3.66. Absolute growth above 50% is 15% of firms. A Gaussian with the same mean and sd puts 46% of draws beyond that line.
- Growth volatility falls with size from sd 1.04 in the smallest quintile to 0.34 in the fourth, then rises to 0.44 in the largest. A size-blind growth draw cannot pass.
- Gross margin (n = 1,143) has sd 0.30. Profit margin (n = 1,938) has mean −0.07, median +0.03, and a two-year persistence of 0.58 (n = 1,649).
- A moment-matched Gaussian generator fails the pre-stated tail test and cannot represent the size-volatility table. Matching the first two moments is not calibration.

## What this does not establish

- It does not validate any running enterprise simulator against these facts. The generator scored here is a two-line draw, not the ledger prototype. The prototype's seeded event generator was not refit to this panel.
- It does not establish that real firm growth is Laplace. The skew is positive; a symmetric Laplace is the literature's shape, not this extract's shape [T1] Stanley et al. 1996, Nature 379:804–806, the symmetric tent those authors report.
- It does not establish a Zipf coefficient. Log-asset deciles are not a rank-size regression, and the left-skew says a pure power law will not fit the whole extract [T1] Axtell 2001, Science 293:1818–1820.
- It does not survive a change of revenue tag unexamined. The panel is `Revenues`, not the synonym union.
- It does not license a claim that a simulator which passed tier 2 would give reliable advice. Tier 2 is a filter against generators that are already unlike firms. It is not a test of a decision.
