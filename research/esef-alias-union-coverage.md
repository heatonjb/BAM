# Alias Unions, Coverage Recovery, and Whether the Comparability Tax Transfers to ESEF

**Question.** A live EDGAR measurement found that the comparability tax on middle-layer metrics is mostly peer-set exclusion, not disagreement among firms that report the same tag. The proposed remedy was an alias union: accept a documented chain of standard tags, and the peer cell gets larger. This study measures how much of that gap a strict synonym union actually recovers, how much only a *broader, different construct* can recover, and whether the same pluralism appears in EU ESEF filings under `ifrs-full`.

## Data and the three regimes

SEC numbers are from the XBRL frames endpoint, pulled 24 October 2026, `User-Agent` declared, 0.12 s between calls [T2] U.S. SEC, EDGAR XBRL APIs, "frames". Duration tags use `CY2023`; instant tags use `CY2023Q4I`. One value was kept per CIK, first tag in the chain that had a fact. ESEF numbers are from 468 XBRL-JSON packages cached from `filings.xbrl.org`, twelve countries, face facts only (dimensions exactly concept, entity, period, unit), annual durations of 300–400 days [T2] XBRL International, filings.xbrl.org API.

Three regimes, declared before the counts:

- **P** — the single preferred tag.
- **S** — P plus strict synonyms: standard tags that a careful reader would still call the same construct.
- **U** — S plus broad tags that measure something else (interest income as "revenue"; SG&A as "selling and marketing"; payables-and-accrued as "payables").

U is the ceiling of a naive union. S is the largest union that does not change the metric's meaning. The quantity that matters is the share of the P-to-U gap that S recovers. A union that only recovers coverage by changing the construct has not recovered the metric.

Deprecated tags that older alias lists still carry — `SalesRevenueNet`, `SalesRevenueGoodsNet`, `SalesRevenueServicesNet`, `CostOfGoodsSold`, `CostOfServices`, `CostOfSales` — returned HTTP 404 on the current frames endpoint. They add zero firms. An alias chain copied from a 2018 taxonomy is partly dead. That is itself a comparability tax, paid by the analyst rather than the filer.

## Coverage, SEC CY2023

| Metric | n(P) | n(S) | n(U) | Coverage loss of P vs U | Share of that gap recovered by S |
|---|---:|---:|---:|---:|---:|
| Revenue | 3,142 | 5,344 | 5,672 | 44.6% | 87.0% |
| COGS | 1,895 | 3,398 | 3,398 | 44.2% | 100% |
| S&M expense | 1,273 | 1,683 | 5,582 | 77.2% | 9.5% |
| Receivables | 3,393 | 4,169 | 4,169 | 18.6% | 100% |
| Inventory | 2,705 | 2,753 | 2,776 | 2.6% | 67.6% |
| Payables | 3,909 | 4,214 | 5,274 | 25.9% | 22.3% |

Preferred revenue is `RevenueFromContractWithCustomerExcludingAssessedTax` (3,142). Strict synonyms — including-tax revenue, `Revenues`, and the three sales-revenue tags of which the last three 404 — add 2,202 firms. Broad bank and utility lines (`InterestAndDividendIncomeOperating` 479, `NoninterestIncome` 436, `RevenuesNetOfInterestExpense` 64, regulated operating revenue 24) add only 328 more. **For revenue, a synonym union restores most of the missing peer set without changing the construct.** The residual 328 firms are financial and utility reporters for whom "revenue" is a different object. They should be a separate peer universe, not folded in to inflate *n*.

COGS is the clean case. `CostOfGoodsAndServicesSold` (1,895) plus `CostOfRevenue` (1,675) is the entire union. The other three names 404. Synonyms recover 100% of the gap, and there is no honest "broad" tag left. The 44% coverage loss of the preferred tag is an alias problem with a one-line fix.

Inventory is already a preferred-tag metric. `InventoryNet` covers 2,705 of 2,776 firms in the broadest chain (loss 2.6%). Component tags (finished goods, raw materials, WIP) are breakdowns, not substitutes; adding them as if they were synonyms would double-count a firm that reports both the total and the parts. The chain used here is first-present-wins, so a firm with `InventoryNet` is not also taken from a component. The 71-firm gap is real but too small to move a decile in a wide cell.

S&M is the opposite case, and it is the one that matters for the middle layer. Strict synonyms (`MarketingExpense` 230, `SellingExpense` 245) add 410 firms, 9.5% of the gap. The other 3,899 firms appear only when `SellingGeneralAndAdministrativeExpense` (2,097) or `GeneralAndAdministrativeExpense` (3,591) is allowed. Those tags are not selling-and-marketing. An alias union that "recovers" S&M coverage by substituting SG&A has changed the metric. This matches the earlier finding that the S&M fallback measures a different construct, and it measures the size of the temptation: the broad union is 4.4 times the preferred set.

Payables sit in between. `AccountsPayableTradeCurrent` adds 305 firms (22% of the gap). The rest arrive only through payables-and-accrued and current-and-noncurrent combinations, which mix trade payables with accruals and with long-term amounts. A DPO built on U is not a DPO.

## Population-shift tax is not the tag-choice tax

Expanding the peer set moves percentiles even for firms whose own number did not change. That movement is reported here as a population-shift tax, and it must not be confused with the tag-choice tax (the movement of a firm that has two different values for two tags).

| Metric | Decile churn, P population scored inside S | Mean percentile shift | Decile churn, S inside U |
|---|---:|---:|---:|
| Revenue | 0.543 | 5.5 points | 0.054 |
| COGS | 0.680 | 7.2 points | 0.000 |
| S&M | 0.339 | 3.4 points | 0.541 |
| Receivables | 0.052 | 0.55 points | 0.000 |
| Inventory | 0.005 | 0.05 points | 0.008 |
| Payables | 0.049 | 0.49 points | 0.157 |

COGS is the illustration. Synonyms add 1,503 firms, all of them a same-construct tag. Firms that already reported the preferred tag see a 68% chance of changing decile, and a mean percentile move of 7.2 points, solely because the peer distribution changed. Their own COGS number is untouched. A decision rule that says "do not benchmark a firm whose percentile moves more than a decile under alias substitution" will reject COGS for the wrong reason if it does not separate substitution of the firm's tag from expansion of the peer set.

The practical rule, restated against these counts:

1. Build the peer set under S, not under P and not under U.
2. Score the firm on the first tag in the S chain that it reports. Do not rescore it under a second tag unless the decision is explicitly about tag disagreement.
3. Treat U-only firms as out of universe, and say so. For S&M that is most of the apparent universe.
4. A decile move caused by peer-set expansion is a reason to publish the peer-set definition, not a reason to call the metric fragile.

Under that rule, revenue, COGS, receivables and inventory are benchmarkable on S. S&M is benchmarkable only for the 1,683 firms inside S (and only 1,273 of those on the preferred tag). DPO is benchmarkable on S (4,214) and not on U.

## Derived middle-layer metrics under the strict union

Coverage of a ratio is the intersection of its legs, so a union helps only if it helps the scarce leg.

| Ratio | Firms under P | Firms under S | Lift |
|---|---:|---:|---:|
| Gross margin (revenue − COGS) / revenue | 1,310 | 3,306 | +152% |
| S&M / revenue, strict tags only | 807 | 1,572 | +95% |
| DSO (receivables / revenue × 365) | 2,174 | 3,967 | +82% |
| DIO (inventory / COGS × 365) | 1,349 | 2,186 | +62% |
| DPO (payables / COGS × 365) | 1,438 | 2,630 | +83% |

Gross margin is the largest win. The preferred-tag intersection is 1,310 firms; the synonym intersection is 3,306. That is the difference between a thin industry cell and a cell that can support deciles. DSO, DIO and DPO each gain 60–80%. None of these lifts uses a broad, different-construct tag. They are available to anyone who maintains the synonym list and drops the 404 names.

S&M intensity still tops out at 1,572 firms under a honest union, against a revenue synonym universe of 5,344. Direct share is about 0.29. That is the same fragility as before, now with the recovery attempt measured and found wanting. The metric stays fragile because the taxonomy's specific tags are sparsely used, not because an alias list was too short.

## Does this transfer to ESEF?

The ESEF cache is not a frames extract. It is 468 annual packages, so the right comparison is concept presence inside a filing, not a cross-filer frames count. Annual face facts:

| IFRS concept | Filings with an annual duration fact | Share of 468 |
|---|---:|---:|
| `ifrs-full:Revenue` | 318 | 68.0% |
| `ifrs-full:RevenueFromContractsWithCustomers` | 58 | 12.4% |
| `ifrs-full:ProfitLoss` | 449 | 96.0% |
| `ifrs-full:CostOfSales` | 153 | 32.7% |
| `ifrs-full:GrossProfit` | 138 | 29.5% |
| `ifrs-full:AdministrativeExpense` | 105 | 22.4% |
| `ifrs-full:SellingExpense` | 33 | 7.1% |
| `ifrs-full:SellingGeneralAndAdministrativeExpense` | 18 | 3.8% |
| Operating cash flow | 430 | 91.9% |
| Investing cash flow | 436 | 93.2% |
| Financing cash flow | 439 | 93.8% |
| Increase in cash | 255 | 54.5% |

Revenue pluralism is real and small. Both revenue concepts appear as annual facts in 11 filings; `Revenue` alone in 307; `RevenueFromContractsWithCustomers` alone in 47; neither in 103. A two-tag synonym union for revenue would cover 365 filings (78.0%) against 318 for the primary tag, a recovery of 47 filings, 14.8% relative. That is much less pluralism than us-gaap revenue, where the preferred tag is only 55% of the synonym union (3,142 / 5,344). **Standard-tag pluralism is a us-gaap fact more than an IFRS fact, at least for the top line.** IFRS filers mostly pick `ifrs-full:Revenue` and stop.

The middle layer does not transfer as a success. Cost of sales is present in a third of filings. Selling expense is present in 7%. Gross profit in 30%. A European peer cell for S&M intensity, built the same way as the SEC cell, would be a few dozen firms in this cache, not hundreds. The verdict "S&M is fragile" transfers. The verdict "COGS is repairable by a synonym union" does not have the same repair available: the cache did not show a widely used second cost concept doing the work `CostOfRevenue` does in the United States. `ProfitLoss` at 96% and the three cash-flow sections above 90% show that the primary statements are tagged; the scarce objects are the analytical subtotals.

Instant working-capital tags, which a duration filter hides, change the DSO/DIO/DPO picture and should be stated so the zero is not misread. `CashAndCashEquivalents` is an instant in 451 filings (96%), `Inventories` in 304 (65%), `TradeAndOtherCurrentPayables` in 214 (46%), `TradeReceivables` in 25 (5%). DIO is more buildable under IFRS than DSO. A US-style DSO chain has no IFRS analogue in this sample.

Country coverage in the cache is roughly balanced (40 filings for most countries, 29 for Portugal, 39 for Spain) and contains no United Kingdom package. Nothing below should be read as a UKSEF result.

## What the alias union can and cannot restore

It can restore, on SEC data, the peer set for revenue (87% of the gap, and the remaining 13% should stay out), all of the COGS gap, all of the receivables gap, and most of the small inventory gap. Those restorations multiply derived-metric coverage by 1.6 to 2.5 for gross margin, DSO, DIO and DPO.

It cannot restore S&M. Nine-tenths of the apparent gap is SG&A and G&A. Folding those in raises *n* and destroys the construct, and the population-shift tax from S to U on S&M is a 54% decile churn — the signature of a different distribution, not of a larger sample of the same one.

It cannot be copied to ESEF as a tag list. The IFRS primary revenue tag is already the dominant choice. The damage in Europe is missing subtotals (cost of sales, selling expense, trade receivables), which an alias union does not invent. Extension taxonomies and note-level tags were not searched; some of the 103 filings with neither revenue concept may carry a local extension. That search would raise coverage and, by Debreceny's finding that a large share of extensions are unnecessary, would often be reaching for a concept the base taxonomy already has [T1] Debreceny et al. 2011, *Flex or Break?*, Accounting Horizons 25(4):631, Abstract, ¶1. It would not create a selling-expense fact the filer did not tag.

The published comparability literature is consistent with this split. Pairwise non-comparability of about 63% is what you get when each pair must share a concept and filers pick different standard tags [T1] Zhu & Wu, *Interoperability of XBRL Financial Statements in the U.S.*, Abstract, ¶1. Face-statement extension rates near 9% and all-items custom-tag rates near 17–21% describe a different margin — notes and custom concepts — which is not the margin that moved these frame counts [T2] SEC DERA, *U.S. GAAP – XBRL Custom Tags Trend 2022–2024*, Section I, ¶1; [T2] Ling & Liu, *XBRL Data Comparability*, CPA Journal, "Extension use over time", ¶3. The dominant SEC threat, on this pull, remains standard-tag pluralism. The dominant ESEF threat, on this cache, is absence of the analytical subtotal.

## What this establishes

- A strict synonym union recovers 87% of the SEC revenue coverage gap and 100% of the COGS gap, and lifts gross-margin coverage from 1,310 to 3,306 firms, without changing the construct.
- The same union recovers 9.5% of the S&M gap. The rest is a different metric. S&M stays fragile.
- Inventory's preferred tag already covers 97.4% of its chain. Alias work there is wasted.
- Percentile churn from expanding the peer set is large (COGS 68% decile churn) even when no firm's own value changed. That churn is not the tag-choice tax and must not be used as a fragility test.
- Several tags in inherited alias lists 404 on the current frames endpoint and contribute nothing.
- Under IFRS, revenue pluralism is mild (`Revenue` alone in 307 filings, the contracts tag alone in 47, both in 11). Cost of sales (33%), selling expense (7%) and trade receivables (5%) are the binding constraints. The fragile/repairable split transfers; the repair itself does not.

## Limitations and what remains unmeasured

- Frames counts are a single pull (24 October 2026) of CY2023. Restatements and taxonomy migration move them. No as-filed versus as-restated toggle was repeated here.
- First-present-wins hides dual reporters. The tag-choice tax for firms that report both `CostOfGoodsAndServicesSold` and `CostOfRevenue` was not recomputed; the earlier measurement of that disagreement still stands and is a different number from the population-shift tax in the table above.
- ESEF is a convenience sample of processed JSON filings, capped near 40 per country, with no UK file. Local extension concepts were not resolved, so the 103 filings with neither standard revenue tag are an upper bound on true revenue absence.
- No SIC or NAICS peer cells were rebuilt. Finer industry cells raise the tax; the coverage lifts here are universe-level and will shrink inside a four-digit industry.
- Companies House iXBRL was not pulled. UKSEF may sit between us-gaap pluralism and IFRS sparsity; that is unmeasured.
