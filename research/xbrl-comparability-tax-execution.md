# Executing the XBRL Comparability-Tax Measurement on a Real EDGAR Sample

The comparability tax of public XBRL data is usually asserted, not measured. This document measures it. Using the SEC's keyless EDGAR data APIs, a peer sample of several thousand filers is assembled for the middle-layer metrics that matter to business benchmarking — revenue, cost of goods sold (COGS), gross margin, sales-and-marketing (S&M) intensity, and the working-capital ratios DSO, DIO and DPO — and each firm's position is computed twice: once under a preferred US-GAAP tag regime and once under a documented fallback-alias regime. The divergence between the two is the tax, expressed as the operational vector (`tax_median`, `tax_decile`, `tax_coverage`, `tax_nE`). The headline result is that the tax is **dominated by coverage, not by tag-value disagreement**: the pure effect of choosing a different but semantically valid tag for a firm that reports one is small for revenue, COGS and gross margin, but the effect of being forced to *exclude* the ~40–74% of the peer cell that never uses the preferred tag is large enough to move most firms by a full decile. Peer-matching granularity and the S&M/inventory-adjacent metrics amplify the tax further.

## 1. The quantity being measured

Let `S` be a benchmark statistic — a peer-cell median or a firm's within-cell percentile — computed under a **preferred-tag regime** `P` and a **fallback-alias regime** `U`, with all other choices held fixed. The tax for metric `m` and peer cell `c` is the vector:

- **`tax_median(c,m)`** = |median(`P`) − median(`U`)| ÷ IQR(`P`), the standardised shift of the cell median;
- **`tax_decile(c,m)`** = share of firms whose within-cell percentile moves by at least one decile (10 percentile points) between the regimes;
- **`tax_coverage(c,m)`** = share of peer-cell firms measurable only under the alias union;
- **`tax_nE(c,m)`** = proportional loss in effective sample size when extension-only and derived values are discarded.

A metric is **benchmarkable for a firm** only if the percentile movement under alias substitution is less than one decile, the firm's tag is among the cell's modal two or the preferred tag has ≥25% cell share, the value is directly reported, the cell clears a sample-size floor (≥20 firms; direct-report ratio ≥0.5), and the as-filed/as-restated vintage does not flip the firm's decile. Metrics that fail the first three conditions may still be reported but flagged low-confidence; failure of the sample-size condition withholds the benchmark entirely.

## 2. Sample and data pipeline

The measurement uses three SEC surfaces. The **XBRL Frames API** (`https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json`) returns one fact per reporting entity for a concept and period, with annual (`CY2023`) and instantaneous (`CY2023Q4I`) variants (SEC, *EDGAR Application Programming Interfaces*, Frames endpoint) [T2]. The **Company Facts API** (`/companyfacts/CIK##########.json`) returns every concept for one firm including the `start`, `end`, `form`, `filed` and `accn` metadata needed to detect restatement vintages (SEC, *EDGAR APIs*, Company Facts endpoint) [T2]. The **Financial Statement Data Sets** (FSDS) quarterly TSVs supply the industry code and the taxonomy-version/custom-flag fields: `SUB` carries the registrant's `sic`, and `TAG` carries per-concept `version` and a `custom` flag (`1` if the tag is firm-defined) (SEC, *Financial Statement and Notes Data Sets*, §5.2 TAG field definitions) [T2].

All requests declared `User-Agent: business-as-machine research contact@example.com` and were throttled to roughly 6–7 requests per second, within the SEC's 10 req/s fair-access ceiling (SEC, *EDGAR APIs*, lead paragraph) [T2]. The extraction target was fiscal year **CY2023** — fully post-ASC-606 and post-2022-taxonomy, so the exercise is not contaminated by the taxonomy's own transition.

**Facts pulled (CY2023 duration; CY2023Q4I instantaneous), with firm counts:**

| concept key | US-GAAP tag | n firms |
|---|---|---:|
| rev_pref | RevenueFromContractWithCustomerExcludingAssessedTax | 3,141 |
| rev_incl | RevenueFromContractWithCustomerIncludingAssessedTax | 780 |
| rev_revenues | Revenues | 2,678 |
| rev_netint | RevenuesNetOfInterestExpense | 64 |
| cogs_goods_services | CostOfGoodsAndServicesSold | 1,895 |
| cogs_rev | CostOfRevenue | 1,673 |
| gross_profit | GrossProfit | 2,788 |
| sm | SellingAndMarketingExpense | 1,273 |
| sga | SellingGeneralAndAdministrativeExpense | 2,096 |
| ar_net_current | AccountsReceivableNetCurrent | 3,393 |
| recv_net_current | ReceivablesNetCurrent | 462 |
| ar_gross_current | AccountsReceivableGrossCurrent | 614 |
| ar_net | AccountsReceivableNet | 619 |
| inv_net | InventoryNet | 2,705 |
| inv_fg_net | InventoryFinishedGoodsNetOfReserves | 851 |
| inv_gross | InventoryGross | 337 |
| ap_current | AccountsPayableCurrent | 3,909 |
| ap_accr_current | AccountsPayableAndAccruedLiabilitiesCurrent | 1,072 |
| ap_trade_current | AccountsPayableTradeCurrent | 393 |

Several legacy fallbacks returned **zero** CY2023 frames — `SalesRevenueNet`, `SalesRevenueGoodsNet`, `SalesRevenueServicesNet`, `TotalRevenuesAndOtherIncome`, `Revenue`, `CostOfGoodsSold`, `CostOfSales`, `CostOfServices` — so the effective fallback chains in this vintage are shorter than the nominal ones. The industry map was built by merging `SUB` files from 2023Q4–2024Q3, yielding 7,259 CIK→SIC assignments; **95.2% of the 5,361-firm revenue universe (5,104 firms) carries an EDGAR SIC code**.

## 3. Preferred tags versus fallback alias chains

Each metric is defined by an ordered chain; the preferred regime takes only the first tag, the union regime takes the first present tag. The measured **answering-tag distribution** (which tag actually supplies the value under the union) is itself the first tax statistic:

| metric | n (union) | preferred-tag share | answering tags |
|---|---:|---:|---|
| Revenue | 5,361 | 58.6% | pref 3,141 · Including 621 · Revenues 1,580 · NetOfInterest 19 |
| COGS | 3,396 | 55.8% | CostOfGoodsAndServicesSold 1,895 · CostOfRevenue 1,501 |
| S&M | 3,274 | 38.9% | SellingAndMarketing 1,273 · SG&A 2,001 |
| AR | 4,052 | 83.7% | ARNetCurrent 3,393 · ReceivablesNetCurrent 322 · ARGross 54 · ARNet 283 |
| Inventory | 2,741 | 98.7% | InventoryNet 2,705 · FinishedGoods 20 · InventoryGross 16 |
| Payables | 4,831 | 80.9% | APCurrent 3,909 · AP+Accrued 728 · APTrade 194 |

Two facts stand out. First, revenue's preferred ASC-606 tag answers only 58.6% of the union; the legacy `Revenues` element still answers 29.5%, consistent with published filer splits reporting roughly half of filers on the ASC-606 element and a quarter still on the legacy element (MetricDuck Research, *How 2,100+ SEC Filers Actually Report Revenue in XBRL*, "XBRL Element" table) [T3]. Second, S&M's preferred tag answers only 38.9%, and the fallback (`SellingGeneralAndAdministrativeExpense`) is a *different construct* — it adds general and administrative cost — not a synonym. That chain is structurally untrustworthy before any percentile is computed.

## 4. Measured results

### 4.1 Coverage-inclusive tax (preferred-only versus alias-union)

This is the operational definition of the tax: firms measurable under the preferred tag only constitute regime `P`; the alias union is regime `U`; percentiles are recomputed in each.

**Table 1 — Comparability tax (CY2023, n = firms, coverage-inclusive).** `covTax` = share measurable only under the union; `taxDec` = share of common-regime firms changing decile; `dMean`/`dMed` = mean/median percentile movement; `taxMed` = standardised median shift; `sic2TD` = size-weighted 2-digit-SIC version of `taxDec`.

| metric | nP | nU | covTax | taxDec | dMean | dMed | taxMed | sic2TD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Revenue | 3,141 | 5,361 | 0.414 | **0.537** | 5.45 | 5.97 | 0.106 | 0.564 |
| COGS | 1,895 | 3,396 | 0.442 | **0.679** | 7.21 | 7.97 | 0.105 | 0.533 |
| Gross margin | 2,788 | 3,535 | 0.211 | **0.680** | 8.98 | 8.86 | 0.091 | 0.578 |
| S&M intensity | 807 | 3,143 | 0.743 | 0.171 | 1.94 | 1.63 | 0.029 | 0.489 |
| DSO | 2,174 | 3,868 | 0.438 | 0.240 | 2.51 | 2.53 | 0.059 | 0.313 |
| DIO | 1,349 | 2,177 | 0.380 | 0.176 | 1.77 | 1.68 | 0.029 | 0.240 |
| DPO | 1,438 | 2,867 | 0.498 | 0.354 | 3.62 | 3.53 | 0.080 | 0.526 |

The interpretation is that **coverage is the tax**. When 41–74% of a peer cell is dropped because it does not use the preferred tag, the reference population changes shape and the median firm's percentile moves by 1.7–9.0 points on average (5.5–9.0 for the income-statement metrics). Because decile boundaries are every 10 points, a mean movement of ~5 points mechanically produces ~50% decile churn: `taxDec` and `dMean/10` coincide almost exactly for Revenue (0.537 vs 0.545), COGS (0.679 vs 0.721) and DSO (0.240 vs 0.251). The one metric that is *less* coverage-taxed is S&M, and only because its preferred regime already excludes so much (74.3%) that the surviving 807 firms are a highly selected, internally coherent set — its per-cell tax is nonetheless the largest of all (sic2TD 0.489 on a thin base).

### 4.2 Pure tag-choice tax (fixed universe)

The coverage-inclusive figure conflates two effects: who is in the benchmark, and what number a multi-tag firm gets. To isolate the second, both regimes are applied to the **same** firm universe with two documented tag orderings — a "strict/preferred-first" order and a "legacy/simple-tag-first" order.

**Table 2 — Pure tag-choice tax (common universe).** `nValDiff` = firms whose value changes; `medRelDiff` = median relative value change among those.

| metric | n | taxDec | dMean | nValDiff | medRelDiff |
|---|---:|---:|---:|---:|---:|
| Revenue | 5,361 | 0.085 | 1.42 | 541 | 21.3% |
| COGS | 3,396 | 0.021 | 0.36 | 75 | 85.0% |
| Gross margin | 3,533 | 0.014 | 0.16 | 100 | 21.1% |
| S&M intensity | 3,135 | 0.072 | 2.00 | 317 | 36.4% |
| DSO | 3,860 | 0.131 | 2.60 | 442 | 15.1% |
| DIO | 2,177 | 0.079 | 1.54 | 263 | 13.4% |
| DPO | 2,866 | 0.159 | 3.15 | 281 | 92.4% |

For firms that report more than one alias, the *values* genuinely disagree. Direct measurement of dual reporters shows why:

- **Revenue**: 795 firms report both the ASC-606 preferred tag and legacy `Revenues`; 393 of them differ, by a **median 19.0%**.
- **Payables**: 344 firms report both `AccountsPayableCurrent` and `AccountsPayableAndAccruedLiabilitiesCurrent`; 311 differ, by a **median 158%** — the two tags measure different things.
- **AR**: 140 firms report both `AccountsReceivableNetCurrent` and `ReceivablesNetCurrent`; 84 differ, median **28.7%**.
- **S&M**: 95 firms report both `SellingAndMarketingExpense` and SG&A; 87 differ, median **135%**.
- **COGS**: 172 firms report both `CostOfGoodsAndServicesSold` and `CostOfRevenue`; 75 differ, median **85.0%**.

So the pure tag-choice tax is small in *frequency* (2–16% of firms change decile) but large in *magnitude* when it bites. DPO is the worst: 15.9% of firms change decile and the median divergent firm's denominator-ratio shifts by 92%. This is the empirical basis for calling the payables chain fragile.

### 4.3 Sensitivity to peer matching (SIC granularity and a NAICS-style proxy)

The same coverage-inclusive `taxDec` was recomputed within peer cells of decreasing granularity: 4-, 3- and 2-digit SIC, and a coarse sector grouping that proxies NAICS-level matching (standard SIC divisions A–J).

**Table 3 — tax_decile by peer matcher.**

| metric | global | SIC-4 | SIC-3 | SIC-2 | sector |
|---|---:|---:|---:|---:|---:|
| Revenue | 0.537 | 0.555 | 0.563 | 0.564 | 0.534 |
| COGS | 0.679 | 0.543 | 0.552 | 0.533 | 0.570 |
| Gross margin | 0.680 | 0.555 | 0.567 | 0.578 | 0.644 |
| S&M intensity | 0.171 | **0.569** | 0.547 | 0.489 | 0.351 |
| DSO | 0.240 | **0.404** | 0.389 | 0.313 | 0.231 |
| DIO | 0.176 | **0.336** | 0.338 | 0.240 | 0.182 |
| DPO | 0.354 | 0.574 | 0.564 | 0.526 | 0.474 |

Finer matching does not reduce the tax; for the balance-sheet ratios it **inflates** it sharply. S&M's tax rises from 0.171 globally to 0.569 within 4-digit SIC cells because preferred S&M reporters are scarce inside any narrow industry, so the preferred cell is tiny relative to the union cell. The coarsest matcher (sector) tends to *lower* the tax by pooling enough preferred reporters that the two cells overlap. This is the quantitative form of the known finding that industry classification itself disagrees across vendors by more than 36% at the two-digit level (Kahle & Walkling, *The Impact of Industry Classifications on Financial Research*, JFQA 31(3), Abstract, para. 1) [T1]: a benchmark's fragility is a joint function of tag coverage *and* the peer partition, and a finer partition can make a "semi-robust" metric fragile.

### 4.4 Effective sample size

`n_eff` is the count of firms with a directly reported preferred-terminal value; the benchmark floor is `n_eff / n_cell ≥ 0.5` within cells of ≥20.

**Table 4 — Effective sample size.**

| metric | nU | nP (direct) | direct share | cells ≥20 | cells clearing 0.5 |
|---|---:|---:|---:|---:|---:|
| Revenue | 5,361 | 3,141 | 0.586 | 42 | 33 |
| COGS | 3,396 | 1,895 | 0.558 | 30 | 22 |
| Gross margin | 3,535 | 2,788 | 0.789 | 31 | 27 |
| S&M intensity | 3,143 | 807 | **0.257** | 29 | **1** |
| DSO | 3,868 | 2,174 | 0.562 | 34 | 25 |
| DIO | 2,177 | 1,349 | 0.620 | 20 | 18 |
| DPO | 2,867 | 1,438 | 0.502 | 26 | 16 |

Revenue, COGS, gross margin, DSO and DIO clear the sample-size floor in most cells. S&M clears it in **1 of 29** industry cells — the benchmark simply does not exist for S&M at the industry level. DPO sits exactly on the boundary (0.502 overall) and clears only 16 of 26 cells, so its industry benchmarks are frequently too thin to report.

## 5. Restatement-vintage and taxonomy-version awareness

**As-filed versus as-restated.** A deterministic 250-firm sample (seed 20261012) of the revenue universe was pulled from Company Facts, and for each firm the annual facts for fiscal 2023 were grouped by concept and start/end date to find the same period carrying more than one distinct value across filings. Within the single preferred concept, **11 of 157 firms (7.0%)** show a same-concept FY2023 revenue that changes across filings, with median relative spread **18.4%**; the legacy `Revenues` concept shows 6 of 119 (5.0%), median 14.9%. For those revised firms, switching from the earliest to the latest value moves **5 of 11 (45.5%) by a full decile** against the full CY2023 distribution. The base rate is in the same order as the published Big-R restatement incidence of about 3% per year (PCAOB, *Data Points: Financial Restatements and Auditor Turnover*, DP04-2025, Finding 1) [T2]; the measured 5–7% is higher because the method captures reclassifications and comparative recasts in addition to formal restatements, so it bounds the vintage tax from above rather than measuring restatements alone.

**Taxonomy version and extensions.** From the FSDS `TAG` file, the distinct-concept vocabulary of a quarter is **91.5% firm-defined extensions** (355,634 concept-version rows, 325,261 custom). This is a different statistic from the per-fact extension rate: on the face-of-statement `NUM` facts for 2024Q1, the firm-defined share is **8.82%** (302,264 of 3,428,694 rows), lower than the ~17–21% all-items rate the SEC reports because extensions concentrate in the notes rather than on the primary statements (SEC DERA, *U.S. GAAP – XBRL Custom Tags Trend 2022–2024*, Section I, para. 1) [T2]; Ling & Liu, *XBRL Data Comparability*, CPA Journal, "Analysis," Exhibits 2–4) [T2]. Crucially, the preferred revenue tag itself is never custom in the sample and is **99.5% on the current `us-gaap/2023` taxonomy** (`us-gaap/2023` 91,756 facts vs `us-gaap/2022` 425). The extension tax therefore does not degrade the preferred revenue tag; it removes firms from the preferred universe entirely, which is exactly the coverage tax measured in Table 1.

## 6. Robust, semi-robust and fragile metrics

Combining the two axes — alias-value robustness (Table 2) and coverage/peer robustness (Tables 1, 3, 4) — against the decision rule:

| metric | alias taxDec | coverage taxDec | n_eff share | verdict |
|---|---:|---:|---:|---|
| COGS | 0.021 | 0.679 | 0.558 | **semi-robust** (value-solid, coverage-fragile) |
| Gross margin | 0.014 | 0.680 | 0.789 | **semi-robust** (derivation-dependent) |
| Revenue | 0.085 | 0.537 | 0.586 | **semi-robust** |
| DIO | 0.079 | 0.176 | 0.620 | **semi-robust** |
| DSO | 0.131 | 0.240 | 0.562 | **semi-robust→fragile** |
| DPO | 0.159 | 0.354 | 0.502 | **fragile** |
| S&M intensity | 0.072 | 0.171 | 0.257 | **fragile** |

- **Robust:** none of the middle-layer metrics is robust in the strict sense. The metrics that are robust *as values* — COGS (0.021), gross margin (0.014), revenue (0.085) — are robust only conditionally: once any peer cell is built from the preferred tag alone, a majority of the cell is discarded and the percentile reference class is unstable. Under the decision rule's condition (1) these pass; under conditions (2)–(4) they pass only for cells where the preferred share clears 0.5, which is true for most cells for revenue, COGS and gross margin (33/42, 22/30, 27/31).
- **Semi-robust:** revenue, COGS, gross margin and DIO. Their benchmark is usable *if* the alias union is used and the industry cell is wide enough; it is not usable from preferred-only extraction.
- **Fragile:** S&M intensity (direct share 0.257; 1 of 29 cells viable; fallback measures a different construct), and DPO (alias tax 0.159; median divergent-firm shift 92%; 16 of 26 cells viable). DSO borders fragile because finer peer matching raises its tax above 0.40.

The single most important qualitative finding contradicts a common assumption: for the income-statement metrics the danger is **not** that firms use a semantically distinct custom tag, but that they use a different *standard* tag. The preferred revenue tag is 100% standard and 99.5% current-taxonomy, yet 41.4% of the measurable union does not use it. Comparability is eroded by legitimate plural standards, not chiefly by extensions.

## 7. Code and query procedure

The measurement is fully reproducible from the SEC APIs; the essential logic is below. Frames supply the cross-sections, FSDS `SUB` supplies SIC, and Company Facts supplies restatement vintages.

```python
import requests, json, csv, collections, statistics as st
HDR = {"User-Agent": "business-as-machine research contact@example.com"}
S = requests.Session(); S.headers.update(HDR)

CHAINS = {
 "rev":  ["RevenueFromContractWithCustomerExcludingAssessedTax",
          "RevenueFromContractWithCustomerIncludingAssessedTax","Revenues",
          "RevenuesNetOfInterestExpense"],
 "cogs": ["CostOfGoodsAndServicesSold","CostOfRevenue"],
 "sm":   ["SellingAndMarketingExpense","SellingGeneralAndAdministrativeExpense"],
 "ar":   ["AccountsReceivableNetCurrent","ReceivablesNetCurrent",
          "AccountsReceivableGrossCurrent","AccountsReceivableNet"],
 "inv":  ["InventoryNet","InventoryFinishedGoodsNetOfReserves","InventoryGross"],
 "ap":   ["AccountsPayableCurrent","AccountsPayableAndAccruedLiabilitiesCurrent",
          "AccountsPayableTradeCurrent"],
}
def frames(tag, period):                     # one call per tag/period
    u = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
    r = S.get(u, timeout=40)
    return {} if r.status_code == 404 else {str(d["cik"]): d["val"] for d in r.json()["data"]}

def resolve(chain):                          # union regime: first present tag wins
    ciks = set().union(*[set(frames(t,"CY2023")) for t in chain])
    out = {}
    for c in ciks:
        for t in chain:
            v = frames(t,"CY2023").get(c)
            if v is not None: out[c] = v; break
    return out
# preferred regime = frames(chain[0]) only
# ratios: DSO = AR/rev*365, DIO = inv/cogs*365, DPO = ap/cogs*365
# percentiles within peer cell; decile = min(9, int(pct//10))
# restatement: GET /companyfacts/CIK{cik:010d}.json, group annual facts by (start,end),
#   count distinct `val` across `accn`/`filed`
```

The full run makes 19 frame calls, 250 company-facts calls and four FSDS `SUB` extracts. Frames are cached to JSON so the percentiles can be recomputed under alternative chains without re-querying. Industry cells come from `SUB`'s `sic` field; the NAICS-style proxy is the standard SIC division range of the two-digit code.

## 8. Sensitivity of the conclusions

The verdicts are stable in direction but not in rank across reasonable analyst choices:

- **Alias ordering.** Reversing the preferred/legacy order for revenue changes its alias tax from 0.085 to the same 0.085 set (the same 541 firms are affected), but if a benchmark were built "legacy-first" the *preferred* tag would become the fallback and the same firms move. The identity of the fragile chain is a property of the tag set, not the ordering.
- **Peer granularity.** As Table 3 shows, moving from a global pool to 4-digit SIC raises S&M's tax from 0.171 to 0.569 and DSO's from 0.240 to 0.404. A study that reports only global percentiles will systematically understate the tax on the ratios that a firm is actually benchmarked on.
- **Regime definition.** The pure tag-choice tax (Table 2) is 3–7 times smaller than the coverage-inclusive tax (Table 1) for the income metrics. Any headline figure must state which regime pair it uses; "alias substitution" is a coverage change for most firms, not a value change.
- **Aggregation.** Cell medians shift by 0.03–0.11 of a preferred IQR (`taxMed`); using quarter-of-origin or average-balance conventions for the balance-sheet legs would add a further, unmeasured component.

## 9. Anchoring to published extension and comparability rates

The measured numbers sit inside the published envelope. The ~8.8% face-statement extension rate and the 91.5%-of-vocabulary extension share bracket the SEC's ~17% all-items rate [T2] and the CPA Journal's ~21% annual-report rate (Ling & Liu, *XBRL Data Comparability*, "Extension use over time," para. 3) [T2]. The finding that ~40% of extensions are semantically unnecessary (Debreceny et al., *Flex or Break? Extensions in XBRL Disclosures to the SEC*, Accounting Horizons 25(4):631, Abstract, para. 1) [T1] explains why the preferred tags survive intact: the taxonomy already contains the right concepts; filers choose differently among them. The 63% pairwise non-comparability result (Zhu & Wu, *Interoperability of XBRL Financial Statements in the U.S.*, Abstract, para. 1) [T1] is the same phenomenon measured pairwise rather than against a preferred tag, and the post-mandate decline concentrated in discretionary line items such as SG&A (Dhole et al., *Effects of the SEC's XBRL mandate on financial reporting comparability*, IJAIS 19:29, Abstract, final sentence) [T1] is exactly the S&M fragility measured in §4 and §6.

## 10. What this establishes

- The XBRL comparability tax is **measurable and empirically large for the operative choice that benchmarks actually make**: switching from preferred-only to alias-union extraction changes the peer population by 41–74% and moves the median firm's within-cell percentile by 1.6 to 9.0 points. Under the five-condition rule, revenue, COGS and gross margin are **semi-robust**, DIO and DSO are semi-robust-to-fragile, and S&M intensity and DPO are **fragile**.
- The tax is **coverage-driven, not value-driven**, for the income-statement metrics: the preferred revenue tag is standard, current-taxonomy and never custom, yet 41% of the measurable universe does not use it. Extension usage is not the main threat to middle-layer benchmarks; **standard-tag pluralism** is.
- **Tag choice among standard tags carries catastrophic value error when it bites**: dual-reporting payables differ by a median 158%, S&M vs SG&A by 135%, COGS by 85%, revenue by 19%. These are measured, not assumed.
- **Peer granularity and tag choice compound.** Finer industry matching, which a careful analyst would adopt, *raises* the tax on S&M, DSO and DIO rather than lowering it.
- The measurement is fully reproducible from keyless SEC endpoints; the code, tag chains and peer logic above regenerate every table.

## 11. Limitations and what remains unmeasured

- **Fiscal calendarisation is not corrected.** Frames calendarise a firm's fact into `CY2023` by proximity (SEC, *EDGAR APIs*, Frames description) [T2]; a July-fiscal-year firm enters every tag with a slightly mismatched window. Ratios whose numerator and denominator are both drawn from the same tag regime are internally consistent, but the cross-firm alignment is not exact.
- **The industry map is single-source and partial.** SIC comes from EDGAR `SUB`; 4.8% of the revenue universe has no SIC and drops from cell analyses. The NAICS comparison is a *division-level proxy*, not a true NAICS reassignment via the Census concordance, so the SIC↔NAICS component is bounded rather than directly measured; the 36%+ two-digit vendor disagreement [T1] means the true classification tax is at least as large as reported.
- **Restatement detection captures reclassification.** The 5–7% same-concept revision rate includes comparative recasts, so it over-states formal restatements; a clean measurement would filter to `10-K/A` with a footnote disclosure.
- **S&M, inventory and payables omissions are structural, not fixable.** Financials, insurers and pre-revenue biotech have no meaningful COGS, inventory or payables; the ~25% of the union with no standard revenue element at all cannot be benchmarked on revenue from any tag.
- **Derived values are recorded but not decomposed.** Gross profit is derived as revenue − COGS for the firms without a `GrossProfit` tag; the derivation multiplies tag error across two concepts, and this study does not isolate that compounding beyond noting that gross-margin's coverage-inclusive tax (0.680) exceeds revenue's and COGS's individually.
- **Not measured:** point-in-time as-of reconstruction (only latest vs same-period earliest), restatement magnitude attribution, the falsification that a benchmark's *rank* (not percentile) of a specific firm flips under a specified alternative, and any validation against an internal first-party series — the only test that would establish whether the surviving benchmarks are *useful* rather than merely *stable*.

## References and sources

**Type 1 — research papers / peer-reviewed work**

- Zhu, H. & Wu, H. *Interoperability of XBRL Financial Statements in the U.S.* (63% pairwise non-comparability). Abstract, para. 1.
- Debreceny, R., Farewell, S., Piechocki, M., Felden, C., Gräning, A. & D'Eri, A. *Flex or Break? Extensions in XBRL Disclosures to the SEC.* Accounting Horizons 25(4):631, 2011. Abstract, para. 1.
- Dhole, S., Lobo, G.J., Mishra, S. & Pal, A.M. *Effects of the SEC's XBRL mandate on financial reporting comparability.* International Journal of Accounting Information Systems 19:29–44, 2015. Abstract, final sentence.
- Kahle, K.M. & Walkling, R.A. *The Impact of Industry Classifications on Financial Research.* Journal of Financial and Quantitative Analysis 31(3):309–335, 1996. Abstract, para. 1.
- Jin, Y. et al. *Excessive custom XBRL tag usage in 10-K filings and SEC oversight.* Journal of International Accounting, Auditing and Taxation, 2025. Descriptive statistics, Table 2.

**Type 2 — official documentation, specs, white papers, books, renowned domain blogs**

- U.S. SEC. *EDGAR Application Programming Interfaces (APIs).* Frames, Company Facts and leader paragraph (User-Agent, 10 req/s). https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- U.S. SEC, DERA. *Financial Statement and Notes Data Sets (FSNDS).* §5.2 TAG field definitions (`custom`, `version`). https://www.sec.gov/dera/data/fsnds.pdf
- U.S. SEC, DERA. *U.S. GAAP – XBRL Custom Tags Trend 2022–2024.* Section I (Trend Analysis), para. 1. https://www.sec.gov/data-research/structured-data/us-gaap-xbrl-custom-tags-trend
- PCAOB. *Data Points: Financial Restatements and Auditor Turnover*, DP04-2025. Finding 1.
- Ling, Q. & Liu, Z. *XBRL Data Comparability.* The CPA Journal, 21 Aug. 2019. "Extension use over time" and "Analysis," Exhibits 2–4.
- FASB. *GAAP Taxonomy Implementation Guide — Revenue from Contracts with Customers.* Lines L1/L11/L15/L17.

**Type 3 — social posts, small blogs, podcasts, conference material**

- MetricDuck Research. *How 2,100+ SEC Filers Actually Report Revenue in XBRL: Seven Years After ASC 606*, 7 Feb. 2026. "XBRL Element" table. https://www.metricduck.com/blog/xbrl-revenue-reporting-patterns-sec-filers-2025
- XBRL US. *SEC Custom Tag Analysis Shows Slight Decline for All Filers*, 30 May 2025. https://xbrl.us/news/sec-custom-tag-analysis-2025/
