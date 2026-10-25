# Reconciliation Against Real Double-Entry Data, and the Cash-Articulation Leg

**Question.** The stock–flow identity `NI_GAAP = NP_TA + ΔInventory × overhead/unit` closes to a zero residual on a synthetic ledger. That result certifies timing consistency inside a constructed cost layer. It does not say whether the identity, or the cash leg it never touched, survives contact with real books. This study runs the cash-articulation invariant on real filings and states, with measured coverage, how much of the throughput identity is even computable from public double-entry data.

## What was measured, and against what

Three corpora were used, chosen because each is public, machine-readable, and closer to a real ledger than a seeded toy.

1. **SEC company facts**, 45 filers drawn as the lowest CIKs that report `RevenueFromContractWithCustomerExcludingAssessedTax` on the CY2023 frames extract. Each filer's full `us-gaap` fact history was pulled from `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` on 24 October 2026, with a declared User-Agent and a 0.12 s pause between calls [T2] U.S. SEC, EDGAR XBRL APIs, "companyfacts".
2. **ESEF annual filings**, 468 XBRL-JSON packages cached from the XBRL International filings API (`filings.xbrl.org`), covering Belgium, Portugal, Denmark, Sweden, Norway, the Netherlands, Finland, Spain, Poland, Austria, France and Italy (29–40 filings each). Facts were read from the OIM JSON `facts` object; only facts whose dimensions were exactly `{concept, entity, period, unit}` were treated as face-statement facts [T2] XBRL International, filings.xbrl.org API; IFRS Foundation, IFRS Taxonomy, `ifrs-full` namespace.
3. **A complete plain-text journal**, the Beancount `examples/example.beancount` file (347,310 bytes, about 2,247 dated transactions, 44 accounts) [T2] Beancount, `examples/example.beancount`.

The cash-flow identity under test is the one ASC 230 requires the statement of cash flows to explain: the sum of operating, investing and financing cash flows, plus the exchange-rate effect, equals the period increase or decrease in the cash total that the balance sheet carries [T2] FASB, ASU 2016-18, *Statement of Cash Flows (Topic 230): Restricted Cash*, Summary. Two implementations were scored separately, because a sloppy period match manufactures false breaks.

- **Flow identity.** `CFO + CFI + CFF + FX − Increase = 0`, all legs sharing the same period end.
- **Balance-sheet roll is not claimed here.** Ending cash minus beginning cash was not scored as a second identity, because the instant cash concept and the increase concept often use different totals (cash only versus cash plus restricted cash). Mixing them is exactly the error ASU 2016-18 was written to stop.

A first pass that matched any FY 2023 fact without requiring a common `end` date produced a spectacular false break (Advanced Micro Devices, residual about −$5.2 billion, relative −0.85) by pairing a 2022 cash stock with later flows. After alignment on `end`, that filing closes to the cent. Every number below is from the aligned pass. Relative residual is `(Increase − predicted) / max(|Increase|, |predicted|, 1)`.

## Cash articulation on SEC filings

All 45 company-facts files parsed. All 45 had a fiscal year-end (2022 or 2023) at which operating, investing, financing and the increase tag were all present.

| Result | Count | Share |
|---|---:|---:|
| Filings with all four flow legs on one `end` date | 45 | 100% |
| Exact, \|relative residual\| < 10⁻⁶ | 42 | 93.3% |
| Within 1% | 42 | 93.3% |
| Within 5% | 43 | 95.6% |
| Median absolute relative residual | 0 | — |

The three non-exact filings, same-period:

| Filer | Period end | Increase | CFO+CFI+CFF(+FX) | Relative residual | FX tag present |
|---|---|---:|---:|---:|---|
| U-Haul Holding Company | 2023-03-31 | 643,613,000 | 4,210,790,000 | −0.847 | no |
| Constellation Brands | 2023-02-28 | −65,900,000 | −62,400,000 | −0.053 | no |
| American Vanguard | 2023-12-31 | −9,028,000 | −8,912,000 | −0.013 | yes |

Abbott Laboratories and AMD, which looked broken under the misaligned matcher, close exactly once the end date is shared (Abbott increase −2,986,000,000; AMD increase −902,000,000). The lesson is methodological before it is economic: **most apparent articulation failures in XBRL are period-join failures, not accounting failures.** A harness that "checks cash articulation" without pinning `fy`, `fp`, `form` and `end` will reject solvent filers.

The residual that survives alignment is still real. U-Haul's published increase is about 15% of the sum of the three sections. That is not rounding and it is not a missing FX tag of ordinary size; it is a concept-boundary failure — the increase tag and the section tags are not describing the same cash total. Constellation's 5.3% gap, with no FX tag retrieved, is the shape ASU 2016-18 predicts when restricted cash or an exchange effect sits outside the concepts the extractor chose. American Vanguard's 1.3% gap remains even with an FX tag, so tag presence is not a sufficient control.

What this establishes for a ledger harness: on a same-period join, the cash-flow identity is an equality for about 19 filers in 20, and a diagnostic for the rest. It should be implemented as a fail-closed check with a named exemption log, not as a soft score. The exemption log is the product. A zero residual means the tags chosen are a closed set. A non-zero residual means the tag map is incomplete, which is a data-engineering fact, not evidence that the filer's books do not balance.

## Cash-flow identity on ESEF filings

The same identity was scored on IFRS concepts, annual durations of 300–400 days, latest end date in the filing, no extra dimensions:

- `ifrs-full:CashFlowsFromUsedInOperatingActivities`
- `ifrs-full:CashFlowsFromUsedInInvestingActivities`
- `ifrs-full:CashFlowsFromUsedInFinancingActivities`
- `ifrs-full:EffectOfExchangeRateChangesOnCashAndCashEquivalents` (treated as zero when absent)
- `ifrs-full:IncreaseDecreaseInCashAndCashEquivalents`

234 of 468 filings had operating, investing, financing and the increase concept all present as an annual duration. Of those:

| Result | Count | Share of 234 |
|---|---:|---:|
| Exact at 10⁻⁶ | 148 | 63.2% |
| Within 1% | 183 | 78.2% |
| Within 5% | 204 | 87.2% |
| Median absolute relative residual | 0 | — |
| 90th percentile absolute relative residual | 0.111 | — |

The identity holds exactly more often than not, and the median residual is zero, but the tail is an order of magnitude fatter than the SEC sample. Two measurement choices inflate that tail, and both should be stated. First, FX was zero-filled when the concept was missing, which converts a missing leg into a residual. Second, ESEF packages often carry several annual durations (group versus parent, continuing versus discontinued) that share an end date; the extractor kept the latest end, not a declared consolidation axis. Some of the 11% relative residuals are therefore parent/group mismatches, which is the same failure mode as the SEC period-join bug, one axis over.

Instant concepts, which a duration filter incorrectly reports as absent, are in fact common: `CashAndCashEquivalents` appears as an instant in 451 of 468 filings (96.4%), `Inventories` in 304 (65.0%), `TradeAndOtherCurrentPayables` in 214 (45.7%), `TradeReceivables` in only 25 (5.3%). A cash roll-forward that needs beginning and ending cash can be attempted for almost every ESEF filer in this cache. A working-capital roll that needs trade receivables cannot. That is a coverage fact about the IFRS face, not a bug in the cache.

## The throughput identity does not survive contact, because the contact surface is missing

The identity `NI_GAAP = NP_TA + ΔInventory × overhead/unit` needs four quantities: GAAP net income, throughput-accounting net profit (sales minus truly variable cost), the inventory change, and a unit overhead rate. Public XBRL discloses the first and, for many filers, the third. It does not disclose the second or the fourth.

On the CY2023 frames extract pulled the same day:

| Concept a throughput split would need | Firms on the frames endpoint | Note |
|---|---:|---|
| `NetIncomeLoss` (CY2023) | 6,387 | GAAP profit is public |
| `InventoryNet` (CY2023Q4I) | 2,705 | ΔInventory is public for goods firms |
| `CostOfGoodsAndServicesSold` | 1,895 | GAAP cost, not variable cost |
| `CostOfRevenue` | 1,675 | synonym, still absorption cost |
| `LaborAndRelatedExpense` | 940 | not a variable-cost split |
| `OtherCostAndExpenseOperating` | 539 | residual bucket, not overhead/unit |
| `SalesRevenueNet`, `CostOfGoodsSold`, `CostOfSales` | 0 (HTTP 404) | retired from the current frames endpoint |

There is no standard face tag whose definition is "fixed overhead per unit" or "throughput". `VariableLeaseCost` exists (1,835 firms) and is the wrong variable: it is a lease-accounting amount, not a product variable cost. Using it as `overhead/unit` would be a modelling error, not a data-availability success.

So the identity was not "run and found to fail" on a real firm. It was **not instantiated**, and the reason is measurable. Of the four legs, two are standard-tag facts and two are internal cost-accounting facts that no mandate requires. The synthetic run's zero residual remains a conservation proof. It is not an empirical claim about any named company. Treating the zero as evidence that GAAP and throughput profits are reconciled in the wild would be a category error: the reconciliation term is exactly the number management accounting does not publish.

What a real-firm test would require, and does not have here: a costed bill of materials or a standard-cost file with the fixed-overhead rate, the production volume used to absorb it, and the inventory sub-ledger that distinguishes variable from absorbed cost. None of those appear in the company-facts files or the ESEF packages. Municipal open-books and the Beancount example do not supply them either. The Beancount file is a complete journal of personal accounts (about 2,247 transactions). A line parser that only sums explicit USD postings cannot close the accounting equation, because Beancount infers the residual posting of an unbalanced transaction; the parsed class totals (Assets 8,568, Liabilities −2,942, Equity −3,219) leave a 2,407 residual that is a parser gap, not a books gap. That file is evidence that a journal can be public. It is not evidence about absorption costing.

## What a harness should implement

The cash leg is implementable today, and the implementation is short if the join is strict.

1. Select facts with `form ∈ {10-K, 10-K/A, 20-F, 40-F}`, `fp = FY`, and a single `end`.
2. Resolve increase, CFO, CFI, CFF, and FX by a documented alias list, in that order. Do not zero-fill FX silently; record whether it was present.
3. Compute the residual in integer minor units. Exact means \|residual\| = 0 after scaling to cents, not "within a percent". The SEC sample's exact rate (42/45) is the bar; the 1% band hides American Vanguard.
4. On failure, emit the tag names and the end date, not a boolean. U-Haul is a map bug or a concept-boundary case until a human reads the 10-K; it is not automatically a fraud flag.
5. Do not attempt `NP_TA` from GAAP lines. If a consumer asks for the throughput reconciliation, the honest output is "insufficient disclosure", with the two missing legs named.

The ESEF extractor should add a consolidation axis (group versus parent) before the 63% exact rate is treated as an IFRS base rate. Until then, 63% exact / 11% at the 90th percentile is an upper bound on breakage and a lower bound on extractor error.

## What this establishes

- On 45 SEC filers, same-period cash-flow articulation is exact for 42 and within 5% for 43. The median residual is zero. A misaligned period join manufactures billion-dollar false breaks; AMD is the example.
- The failures that survive alignment (U-Haul at −85% relative, Constellation at −5.3%, American Vanguard at −1.3%) are concept-boundary failures, consistent with the restricted-cash problem ASU 2016-18 names, not with random noise.
- On 234 ESEF filings with all flow legs, the same identity is exact for 63% and within 1% for 78%. The fatter tail is partly extractor ambiguity (FX zero-fill, group versus parent).
- Instant cash is present in 96% of the ESEF cache; trade receivables in 5%. Working-capital identities are not uniformly observable under IFRS tags.
- The throughput identity cannot be computed from public GAAP or IFRS. Net income and inventory are public; variable cost and overhead per unit are not. Retired us-gaap tags that older alias lists still name (`SalesRevenueNet`, `CostOfGoodsSold`, `CostOfSales`) 404 on the current frames endpoint.

## What this does not establish

- It does not validate the GAAP/throughput identity on any real firm. The missing legs are internal. A zero residual on a synthetic cost layer remains a conservation proof.
- It does not say the three SEC breaks are errors in the filers' books. They are failures of the chosen tag map to be a closed set. Reading the 10-K would be required to separate a filing error from an extractor miss.
- It does not estimate a population articulation rate. The SEC sample is 45 low-CIK revenue reporters, not a random draw of filers. The ESEF cache is a convenience sample of filings that had a processed JSON URL, capped near 40 per country, with no United Kingdom package in the cache.
- It does not test retained-earnings roll-forward, intercompany elimination, or multi-currency translation as ledger invariants. Those were exercised on the synthetic prototype, not here.
- The Beancount example does not close under a naive posting parser, and that fact says nothing about Beancount's own balance check.

## Procedure

Frames and company facts were pulled with `User-Agent: business-as-machine research contact@example.com`. The aligned cash-flow join keeps the latest-filed USD fact for each tag whose `end` equals the candidate year-end, restricted to annual forms. ESEF facts were restricted to the four standard dimensions and to durations of 300–400 days. Relative residual uses the larger of the absolute increase and the absolute predicted change as the denominator, so a near-zero increase cannot explode the ratio. The pull date is 24 October 2026; frames extracts move when filers restate, so a later pull will not reproduce the firm counts to the unit.
