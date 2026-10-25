# Empirically Sizing the XBRL Comparability Tax on Middle-Layer Benchmarks

The corpus treats a business as a transformation machine whose observable surface is a stack: transactions feed a general ledger, which becomes financial statements, and a middle layer of capability, process, and unit-economics benchmarks sits between raw disclosures and the statements themselves. Those middle-layer benchmarks (peer percentiles for gross margin, S&M intensity, DSO/DPO/DIO, and the like) are bootstrapped from public data, chiefly the SEC's XBRL corpus. This document turns the frequently asserted "comparability erosion" of XBRL into a measurable quantity with a reproducible method. It defines a **comparability tax** as an observable loss, per metric and per peer cell, caused by tag-choice, industry-matching, and restatement-vintage ambiguity, and then specifies a study that measures it, anchors its expected magnitude to published figures, and states exactly which middle-layer metrics survive the tax and which do not.

## 1. Defining the comparability tax operationally

The comparability tax is not a survey opinion; it is a divergence between two extraction regimes applied to the same filings. Let a benchmark statistic `S` (e.g., the peer-cell median of a metric, or an individual firm's within-peer percentile) be computed under a **preferred-tag regime** and a **fallback-alias regime**, with all other choices held fixed. Define the tax for a metric `m` and peer cell `c` as the vector:

- **`tax_median(c,m)`** = |median_preferred − median_fallback| normalized by the preferred interquartile range;
- **`tax_decile(c,m)`** = share of firms whose within-cell percentile moves by at least one decile (10 percentile points) when union aliases replace preferred-only tags;
- **`tax_coverage(c,m)`** = share of peer-cell firms that are unmeasurable under the preferred tag but measurable under the alias union (the extraction loss);
- **`tax_nE(c,m)`** = proportional loss in effective sample size when extension-only and derived values are discarded.

A metric is **robust for a firm** when its percentile moves by less than one decile under alias substitution and its peer cell retains adequate effective sample size; otherwise the benchmark is **fragile** for that firm. The next sections justify expected magnitudes, give the measurement recipe, and state the decision rule precisely.

## 2. Anchor magnitudes: what the literature actually measures

### 2.1 Custom-tag and extension rates

The most authoritative public series is the SEC's Division of Economic and Risk Analysis (DERA) annual "U.S. GAAP — XBRL Custom Tags Trend" analysis of Forms 10-K and 10-K/A. DERA's own framing is explicit: filers may create custom tags "when the standard taxonomy does not provide an appropriate element," and the Commission has "acknowledged that the use of custom tags could potentially reduce the comparability of inter-company data" (SEC DERA, *U.S. GAAP – XBRL Custom Tags Trend*, Introduction, para. 2) [T2]. The 2022–2024 release documents a decline in average custom-tag rate from 2023 to 2024 "across all filer status except the large accelerated filer category, for which the rate remains flat" (SEC DERA, *XBRL Custom Tags Trend 2022–2024*, Section I "Trend Analysis," para. 1) [T2]. Summarizing that release, XBRL US reports the aggregate rate moving "from 18% in 2023 to 17% in 2024," with accelerated and large-accelerated filers at "the lowest percent of custom tags at 16%" (XBRL US, *SEC Custom Tag Analysis Shows Slight Decline for All Filers*, para. 1) [T3].

Other estimates bracket this. The *CPA Journal*'s independent tabulation of extensions from XBRL Cloud found that "on average, 21% of the tags in an annual report are not selected from the taxonomy," rising to 25% in 2013 and stabilizing near 21% (Ling & Liu, *XBRL Data Comparability*, CPA Journal, "Extension use over time," para. 3) [T2]. Academic estimates run lower: a large-sample study reports that "on average, 13.5 percent of the total number of XBRL tags in a 10-K filing are custom XBRL tags, with a range from 1.9 percent to 42.7 percent across our sample firms," and that after adjusting for industry and size decile the abnormal range spans −13.7% to 26.6% (Dhole et al.-adjacent custom-tag study as cited in *Excessive custom XBRL tag usage in 10-K filings and SEC oversight*, Section 5 "Descriptive statistics," para. 2) [T1]. The spread — roughly 13–21% central tendency with a 1.9–42.7% firm-level range — is itself the first-order estimate of the comparability tax's upper bound: at the high end, one in four line items is a filer-defined concept that no peer can share.

### 2.2 Pairwise non-comparability

The strongest direct measurement remains Zhu & Wu's interoperability study of every annual XBRL statement filed to the SEC as of 26 February 2010: "On average, 63% of data elements are not comparable between a pair of statements," attributed partly to taxonomy issues and partly to "misuse of the taxonomy by companies" (Zhu & Wu, *Interoperability of XBRL Financial Statements in the U.S.*, Abstract, para. 1) [T1]. Their companion AMCIS study quantifies the mechanism: over 1,231 filings by 478 companies, the average filing used 109.5 standard elements and 15.6 custom elements, and the user community introduced 10,168 custom elements against only 2,558 distinct GAAP elements used — a completeness/relevancy F-measure of 0.22 at the community level (Zhu & Wu, *Quality of XBRL US GAAP Taxonomy*, AMCIS 2010, Tables 1–2, para. 1) [T1]. Two years later the same project notes that "40.5% of the companies (195 out of 481) used deprecated elements in 19.82% of the filings" (Zhu & Wu, AMCIS 2010, Section "element usage," para. 1) [T1]. Deprecated-tag reuse is a second, orthogonal source of the tax: even a standard tag can be the wrong vintage.

### 2.3 What extensions are made of

Debreceny et al.'s *Flex or Break?* classified extensions in filings from April 2009 to June 2010: "Forty percent of these extensions were unnecessary, as semantically equivalent elements were already in the U.S. GAAP taxonomy. Extensions that aggregated or disaggregated existing elements comprised 21 percent … New concepts accounted for 30 percent of the extensions, although many were variants of existing elements" (Debreceny et al., *Flex or Break? Extensions in XBRL Disclosures to the SEC*, Accounting Horizons 25(4):631, Abstract, para. 1) [T1]. The 40% "unnecessary" share is the cleanest available estimate of pure, avoidable tax: those are concepts a peer set could have shared but did not. The 2021 academic replication of around 50% unnecessary extensions (Goodwin, *Extension Analysis*, Summary, para. 3) [T1] suggests the avoidable share has not improved much. Managerial-strategy studies add that extension use rises when performance is poor, consistent with extensions being used to obfuscate (Huang, No & Vasarhelyi, *Do Managers Use Extension Elements Strategically…*, Abstract, para. 1) [T1] — evidence that the tax is not random noise but partly endogenous to the very firm characteristics benchmarks aim to score.

### 2.4 Industry-matching tax

Peer sets are usually matched on a classification, and the classification itself carries a tax. Kahle & Walkling find that across ~10,000 firms jointly covered by Compustat and CRSP, "more than 36 percent of the classifications disagree at the two-digit level and nearly 80 percent disagree at the four-digit level" (Kahle & Walkling, *The Impact of Industry Classifications on Financial Research*, J. Financial and Quantitative Analysis 31(3):309, Abstract, para. 1) [T1]. Guenther & Rosman put two-digit agreement between the same vendors at only 62% (as summarized in the *Potential Misinterpretation Problem of Residual Based Models*, Section 2, para. 3) [T1]. When classification is self-assigned, error rises further: in tax-return data compared against Statistics of Income validation, "over a third of codes are wrong" (Larsen et al., *Accuracy and errors in self-assigned NAICS codes in tax return data*, Abstract, para. 1) [T1]. For EDGAR specifically, filing entities carry a single SIC code assigned in EDGAR, while NAICS/GICS are vendor-derived; the 36%+ two-digit disagreement is a floor, not a ceiling, on peer-matching error. This matters directly because middle-layer benchmarks such as S&M intensity and gross margin are strongly sector-dependent; a one-decile misassignment moves a firm's percentile roughly as much as an entire standard deviation of the metric.

### 2.5 Restatement-vintage tax

The as-filed versus as-restated divergence is bounded by the incidence of restatement. The PCAOB, using Audit Analytics data, reports that "From 2005 to 2024, Big R financial restatements occurred at a rate of around 3% per year" (PCAOB, *Data Points: Financial Restatements and Auditor Turnover*, Finding 1, para. 1) [T2]. But the *composition* of restatements shifts the tax: in 2023, "the total number of Big R or reissuance restatements increased to 209 from 191 in 2022, representing 52 percent of all domestic filer restatements," up from 44% in 2022 (Ideagen Audit Analytics, as summarized in *Two Studies Find that Restatement Rates Remain Low*, para. 4) [T1]. Because Big-R restatements rewrite the numbers that flow into benchmarks, roughly a 3%/yr base rate with a rising material share implies that a multi-year benchmark panel accumulates a low-single-digit percentage of firms whose historical metrics silently change when vintages are switched — enough to move decile cut-points in small peer cells.

### 2.6 Revenue-tag heterogeneity: a concrete case

Revenue illustrates why the preferred/fallback distinction creates real movement. FASB's implementation guide specifies `RevenueFromContractWithCustomerExcludingAssessedTax` (or the Including variant) as the ASC 606 revenue element and permits `Revenues` for the total of contract and non-contract revenue (FASB, *GAAP Taxonomy Implementation Guide — Revenue from Contracts with Customers*, Lines L1/L15/L17, para. 1) [T2]. Empirically, one 2025–2026 survey of 2,100+ filers finds "46% of filers use the ASC 606 revenue element … exclusively, 25% still use the legacy `Revenues` element with no sign of switching, 14% report both elements simultaneously (dual reporting), and 11% have no standard revenue element at all" (MetricDuck Research, *How 2,100+ SEC Filers Actually Report Revenue in XBRL*, Table "XBRL Element," row 1–5) [T3]. A separate normalization project over a 102-firm large-cap sample reports the answering tag split as 55× `Revenues`, 37× `RevenueFromContractWithCustomerExcludingAssessedTax`, 4× `…IncludingAssessedTax`, concluding "No single tag covers even 55% of a large-cap sample" (asp53826/xbrl-normalize, README "Which tag answered 'revenue'," para. 1) [T3]. These figures convert directly into `tax_coverage`: preferred-only extraction on a large-cap universe is a coin-flip on coverage before any other adjustment.

## 3. A reproducible study

### 3.1 Data sources and access

Three SEC surfaces are sufficient, and they should be cross-validated against one another.

- **XBRL Frames API** — `https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json` aggregates one fact per entity per period, supporting annual (`CY2023`), quarterly (`CY2023Q1`) and instantaneous (`CY2023Q1I`) frames (SEC, *EDGAR Application Programming Interfaces*, "data.sec.gov/api/xbrl/frames/," para. 1) [T2]. This is the workhorse for building a peer cross-section in a single call per tag.
- **Company Facts API** — `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` returns every concept for one firm, including fiscal-year/period metadata (`fy`, `fp`, `form`, `start`, `end`, `frame`) needed for calendarization and restatement detection (SEC, *EDGAR APIs*, "data.sec.gov/api/xbrl/companyfacts/"; and the OpenAPI `XBRLFact` schema, properties `fy`, `fp`, `form`, `start`, `end`) [T2].
- **Financial Statement Data Sets (FSDS)** — the quarterly flattened TSV extracts. The TAG file "contains all standard taxonomy tags … and also includes all custom taxonomy tags defined in the submissions," with a `custom` flag ("1 if tag is custom (version=adsh), 0 if it is standard") and a `version` field that carries "the taxonomy of origin" for standard tags (SEC, *Financial Statement and Notes Data Sets*, §5.2 TAG, field descriptions, lines 1–6) [T2]. The NUM file keys on `adsh, tag, version, ddate, qtrs, uom, dimh, iprx` and contains only facts "presented on the primary financial statements" as rendered, which is what a benchmark wants (SEC, *FSNDS*, §5.4 NUM, key list, lines 1–8) [T2]. FSDS is the only source that natively exposes `custom` and `version`, so taxonomy-version-aware and extension-aware views must use it.

Requirement: set a descriptive `User-Agent` header for all `data.sec.gov` and `www.sec.gov` requests, per SEC fair-access policy (SEC, *EDGAR APIs*, lead paragraph) [T2].

### 3.2 Preferred tags and fallback alias chains

For each middle-layer metric, define an ordered preferred tag and a fallback alias chain that terminates in a total concept. The chains below are derived from FASB implementation guidance and XBRL US data-quality rules.

**Revenue.** Preferred: `RevenueFromContractWithCustomerExcludingAssessedTax`. Fallbacks, in order: `RevenueFromContractWithCustomerIncludingAssessedTax` → `Revenues` → `SalesRevenueNet` → `SalesRevenueGoodsNet` → `SalesRevenueServicesNet` → `TotalRevenuesAndOtherIncome` → `Revenue` (IFRS filers). Guard against double counting by de-duplicating facts whose values are equal within tolerance (the dual-reporting case described above) (MetricDuck, "dual reporting" paragraph) [T3].

**COGS.** Preferred: `CostOfGoodsAndServicesSold`. Fallbacks: `CostOfRevenue` → `CostOfGoodsSold` → `CostOfSales`. FASB's guide lists `CostOfGoodsAndServicesSold` as the standard income-statement line (FASB, Implementation Guide, Line L11, table row) [T2].

**Gross margin.** Preferred: reported `GrossProfit` where present; otherwise derive as Revenue − COGS under the *same* alias tier for both legs. Note the fragility: in the 102-firm sample gross profit was reported directly for only 51% of firms and derived for the rest (asp53826/xbrl-normalize, coverage table "Gross profit" row) [T3] — a derivation dependency that multiplies tag-choice error across two tags.

**S&M intensity.** Preferred: `SellingAndMarketingExpense`. Fallbacks: `SellingGeneralAndAdministrativeExpense` → `MarketingExpense` → (`GeneralAndAdministrativeExpense` + `SellingExpense`). This is the most fragile chain in the set because most filers do not disaggregate S&M from SG&A at all; the preferred tag frequently does not exist, and the fallback measures a *different construct*. Comparability is structurally poor here, consistent with Dhole et al.'s finding that "selling, general and administrative expense (SG&A) comparability declined after the mandate, while depreciation comparability did not change" (Dhole et al., *Effects of the SEC's XBRL mandate on financial reporting comparability*, Int. J. Accounting Information Systems 19:29, Abstract, final sentence) [T1].

**DSO/DPO/DIO.** These are ratios, so each carries a numerator and a denominator. DSO numerator preferred `AccountsReceivableNetCurrent`, fallbacks `ReceivablesNetCurrent` → `AccountsReceivableGrossCurrent` → `AccountsAndOtherReceivablesNetCurrent` → `AccountsReceivableNet`; denominator = Revenue tier. DIO numerator preferred `InventoryNet`, fallbacks `InventoryFinishedGoodsNetOfReserves` → `InventoryGross` → `InventoryFinishedGoods`; denominator = COGS tier. DPO numerator preferred `AccountsPayableCurrent`, fallbacks `AccountsPayableTradeCurrent` → `AccountsPayableAndAccruedLiabilitiesCurrent` → `AccountsPayableCurrentAndNoncurrent`; denominator = COGS tier. Formulas: DSO = AR/Revenue × 365; DIO = Inventory/COGS × 365; DPO = AP/COGS × 365; CCC = DSO + DIO − DPO (standard definitions as in any treasury reference, e.g. JPMorgan, *DSO & DPO: How They Can Improve Your Cash Flow*, "How to calculate DPO," formula line) [T3]. Following XBRL US's mutual-exclusivity rule, never combine ASC 606 and pre-606 revenue concepts in the same firm-period when building the denominator (XBRL US, *Mutually Exclusive Elements*, DQC rule 0067, "rule assumes … if any of the new revenue recognition elements are used … then the new standard has been adopted," para. 1) [T2].

### 3.3 Peer-set construction and the classification tax

Build three peer matchers and compare benchmark stability across them:

1. **EDGAR SIC** — the `sic` field in FSDS SUB / the company's submissions JSON (2-, 3-, and 4-digit levels).
2. **NAICS** — via a published SIC→NAICS crosswalk or a vendor mapping, at 2- and 4-digit levels.
3. **Self-classification** — industry text from the DEF 14A / 10-K "peer group" disclosures, or the `ProductOrService` axis disaggregation.

Because two-digit SIC vs. NAICS disagreement exceeds 36% (Kahle & Walkling, Abstract, para. 1) [T1], the study should report each benchmark statistic three times, once per matcher, and treat the spread as an additional component of the tax. Where peer cells are small, prefer 3-digit SIC or GICS-style groupings and report cell size; the *Potential Misinterpretation* paper shows SIC's explanatory power is robust only down to broad sectors and degrades at finer partitions (Table 1, F-statistics discussion, para. 2) [T1].

### 3.4 Preferred vs. fallback: percentile movement and decile churn

For a chosen metric and year:

1. Extract firm values under the preferred tag only (regime P) and under the alias union with de-duplication (regime U).
2. Compute each firm's within-cell percentile in P and in U: `pct_P = rank(v_P)/n_P`, likewise `pct_U`.
3. `Δpct = |pct_U − pct_P|`; a firm "changes decile" when `floor(10·pct_P) ≠ floor(10·pct_U)`.
4. Report `tax_decile(c,m) = mean(1[changes decile])` and the distribution of `Δpct`.
5. Report `tax_median` as the standardized shift of the cell median, and `tax_coverage` as the fraction measurable only in U.

Aggregate across cells with a size-weighted mean and a bootstrap CI (see §3.7).

### 3.5 Restatement-aware and taxonomy-version-aware views

Two orthogonal vintages must be toggled:

- **As-filed vs. as-restated.** FSDS is "quarterly and annual uncorrected and 'as filed' EDGAR document submissions," and NUM rows are keyed by accession, so the same firm-period can appear in multiple accessions (SEC, *FSNDS*, §3 Organization, para. 1) [T2]. Build the panel twice: (a) earliest accession per firm-period (as originally filed), and (b) latest accession on or before a fixed cutoff (as-restated). Recompute percentiles in both and report the decile churn. Expected trigger: ~3%/yr Big-R incidence with a rising material share (PCAOB, Finding 1) [T2] and rising Big-R share (Audit Analytics summary, para. 4) [T1].
- **Taxonomy-version-aware.** Use the TAG `version` field and the `custom` flag. Recompute the metric using only the modal taxonomy version among peers versus allowing the full 2–3-year version window the SEC permits. The Extension Analysis study finds extension ratio is the one variable tied to taxonomy version — newer taxonomy, lower extension rate — so version stratification directly shifts coverage (Goodwin, *Extension Analysis*, "The only factor … is taxonomy," para. 2) [T1].

### 3.6 Effective sample size per metric

Define `n_eff` for a metric in a peer cell as the count of firms with a **directly reported total** (not derived, not extension-only, not dual-counted) for that metric's terminal tag. Track four losses:

1. Firms whose terminal value is extension-only (`custom=1`) — excluded from P and from the modal-tag count, retained only as a coverage query.
2. Firms measurable only via derivation (e.g., gross profit = revenue − COGS) — recorded separately because derivation compounds tag error.
3. Firms with zero or missing denominators (financials have no COGS; banks have no inventory) — the "11% have no standard revenue element at all" case (MetricDuck, Table row 7) [T3].
4. Dual reporters — de-duplicated by value equality to avoid double counting.

Report `n_eff`/`n_cell` per metric; a cell is *benchmarkable* only if this ratio clears a floor (suggested ≥0.5) and `n_eff` ≥ a small-sample threshold (suggested ≥20).

### 3.7 Bootstrap confidence intervals

Percentile movement and decile churn are order statistics with heavy tails, so CIs should be non-parametric. Resample firms with replacement within each cell (stratified by filer-status class to preserve the large/non-accelerated split), recompute `tax_decile` and `tax_median` in each of 2,000 replicates, and report the 2.5/97.5 percentiles. Use a bootstrap because the ratio statistics are finite-sample biased and non-normal: ratio estimators "tend to exhibit large finite-sample bias and variance, leading to overcoverage of the percentile bootstrap CI," which the bootstrap is explicitly designed to quantify (He, Feng & Song, *Efficient Input Uncertainty Quantification for Ratio Estimator*, Abstract, para. 3) [T1].

## 4. Which metrics are robust, which are fragile

**Robust (expected `tax_decile` < ~0.10):** net income, total assets, total liabilities, total equity, operating/investing/financing cash flows, and cash and equivalents. These have near-universal single-tag coverage (the 102-firm sample reports 100.0% coverage for net income, total assets, total equity, and the three cash-flow lines) (asp53826/xbrl-normalize, coverage table rows 1–5) [T3]. Their tag choice is effectively forced, so alias substitution barely moves percentiles. They are suitable as *anchor* benchmarks even though they sit at the base layer.

**Semi-robust (`tax_decile` ~0.10–0.20):** revenue, COGS, and gross margin. Revenue tag heterogeneity is severe at the firm level (46/25/14/11 split) (MetricDuck, Table) [T3], and gross profit is derived for ~half of firms, so both warrant the full preferred/fallback machinery. Coverage is high enough (revenue 94.1%, gross profit 51.0%) that with alias union and de-duplication the tax is measurable and often survivable (asp53826/xbrl-normalize, table) [T3].

**Fragile (`tax_decile` ≳ 0.20 or `n_eff`-starved):** S&M intensity, DIO (and therefore CCC), and any ratio requiring a balance-sheet tag that many industries do not report. S&M is frequently not disaggregated (Dhole et al. report SG&A comparability declined, depreciation did not) [T1]; inventory is absent for most service and financial firms; the preferred tags for these metrics often do not exist for a large share of any broad peer cell.

**Decision rule — "benchmarkable for a given firm."** A metric `m` is benchmarkable for firm `i` in peer cell `c` if and only if all hold:

1. `|pct_U(i) − pct_P(i)| < 10` (percentile movement under alias substitution is less than one decile);
2. firm `i`'s terminal tag is among the **modal two** tags used by cell `c` for `m`, or is a preferred tag with cell share ≥ 25%;
3. the value is directly reported (or derived from two directly reported totals), not extension-only;
4. `n_eff(c,m) ≥ 20` and `n_eff/n_cell ≥ 0.5`;
5. under the as-filed/as-restated toggle the firm's decile does not change (no material vintage exposure).

Failing (1)–(3), the firm may still receive a benchmark but must be flagged **low-confidence**; failing (4), no peer benchmark is reported at all because the reference class is too thin.

## 5. Code-level procedure

The following is an executable outline (Python-style) against the SEC surfaces named in §3.1.

```python
import requests, statistics, random
HDR = {"User-Agent": "research bench; contact@example.org"}

ALIASES = {
 "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
             "RevenueFromContractWithCustomerIncludingAssessedTax",
             "Revenues","SalesRevenueNet","SalesRevenueGoodsNet",
             "SalesRevenueServicesNet","TotalRevenuesAndOtherIncome","Revenue"],
 "cogs":    ["CostOfGoodsAndServicesSold","CostOfRevenue",
             "CostOfGoodsSold","CostOfSales"],
 "sm":      ["SellingAndMarketingExpense",
             "SellingGeneralAndAdministrativeExpense","MarketingExpense"],
 "ar":      ["AccountsReceivableNetCurrent","ReceivablesNetCurrent",
             "AccountsReceivableGrossCurrent","AccountsAndOtherReceivablesNetCurrent"],
 "inv":     ["InventoryNet","InventoryFinishedGoodsNetOfReserves",
             "InventoryGross","InventoryFinishedGoods"],
 "ap":      ["AccountsPayableCurrent","AccountsPayableTradeCurrent",
             "AccountsPayableAndAccruedLiabilitiesCurrent"],
}

def frame(tag, period="CY2023"):
    u = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
    r = requests.get(u, headers=HDR); r.raise_for_status()
    return {d["cik"]: d["val"] for d in r.json()["data"]}

def firm_facts(cik):
    u = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    return requests.get(u, headers=HDR).json()

def value(cik_cache, aliases, period):
    """First non-null across the alias chain; record which tag answered."""
    for tag in aliases:
        f = frame(tag, period)
        if cik_cache["cik"] in f:
            return f[cik_cache["cik"]], tag
    return None, None  # triggers coverage-loss accounting

def de_dup(vals):
    """Collapse dual reporters: cluster equal values within 1e-6 rel tolerance."""
    out, seen = [], []
    for v in sorted(vals):
        if not seen or abs(v - seen[-1]) / max(abs(v), 1) > 1e-6:
            out.append(v); seen.append(v)
    return out

def percentile(v, cell_vals):
    cell_vals = sorted(cell_vals)
    return 100.0 * sum(x < v for x in cell_vals) / len(cell_vals)

def benchmark(cell, metric):
    rev   = [value(c, ALIASES["revenue"], "CY2023")[0] for c in cell]
    rev   = [v for v in rev if v]
    sm    = [value(c, ALIASES["sm"], "CY2023")[0] for c in cell]
    ratios = [s / r for s, r in zip(sm, rev) if s and r]
    # regime P = preferred only; regime U = alias union (above)
    # pct_P vs pct_U -> tax_decile, tax_median, tax_coverage, n_eff
    ...
```

Operationally: pull Frames for the union and for each preferred-only tag; intersect CIKs with the SIC/NAICS peer cell from FSDS SUB; join fiscal dates from Company Facts `start`/`end` to calendarize (§6); compute percentiles in both regimes; bootstrap; emit the five-field tax vector.

## 6. Methodological pitfalls

**Calendarization (CY vs. fiscal).** Frames selects "the fact for each reporting entity that is last filed that most closely fits the calendrical period requested," covering annual duration "365 days +/- 30 days" (SEC, *EDGAR APIs*, "frames" description) [T2]. A July-fiscal-year firm therefore enters `CY2023` with a value that ends in mid-2023 or mid-2024 depending on filing timing. Always join on `start`/`end` from Company Facts and recompute durations; for ratios, align numerator and denominator to the *same* fiscal window and never mix an instantaneous balance with a mismatched duration.

**Aggregated vs. mean-of-ratios.** The peer-cell "average ratio" is ambiguous. Summing numerators and denominators across the cell (value-weighted, "true mean") and averaging firm-level ratios (unweighted) answer different questions and diverge most when ratios are skewed. Bootstrap evidence indicates the geometric mean is generally the least biased aggregator for financial ratios, not the arithmetic or harmonic mean, especially with outliers (Averaging financial ratios, *Finance Research Letters*, Highlights, bullet 3) [T1]. Report both the aggregate ratio and a robust cell central tendency.

**Winsorization.** The most common outlier treatment in accounting, winsorizing at the 1/99 percentiles, has "only a modest impact on parameter estimates" and is "ineffective at mitigating bias induced by influential/outlier observations that are correlated with the variable of interest"; truncation biases coefficients toward zero (Leone et al., *Influential Observations and Inference in Accounting Research*, Abstract, para. 1) [T1]. For benchmark percentiles specifically, percentiles are already robust to tails, so prefer percentile/rank-based statistics and avoid winsorizing the raw inputs before ranking.

**Bootstrap CIs.** Use stratified, within-cell resampling as in §3.7; do not assume normality of percentile or ratio statistics (He et al., Abstract, para. 3) [T1].

**Non-universal disclosure.** Coverage is metric-specific and industry-specific; a benchmark over "all firms" silently omits financials, insurers, and pre-revenue biotech. The 11% of large-caps with no standard revenue element and the 20.6% without current-asset/liability tags are exactly these firms (asp53826/xbrl-normalize, table) [T3]. Restrict the universe explicitly and report the excluded share.

**Restatement vintages.** Because FSDS is as-filed and reprocessed quarterly (SEC, *FSNDS*, §3) [T2], a naive panel mixes vintages. Pin a single extraction date, record the accession used per firm-period, and always report the as-restated toggle separately.

**Taxonomy version.** The `version` field is authoritative for "the taxonomy of origin" (SEC, *FSNDS*, §5.2) [T2]; ignoring it will merge pre- and post-ASC-606 concepts and inflate apparent comparability.

## 7. References and sources

**Type 1 — research papers / peer-reviewed work**

- Zhu, H. & Wu, H. *Interoperability of XBRL Financial Statements in the U.S.* (63% pairwise non-comparability). Abstract, para. 1.
- Zhu, H. & Wu, H. *Quality of XBRL US GAAP Taxonomy: Empirical Evaluation using SEC Filings*, AMCIS 2010, Lima, Peru, p. 579. Tables 1–2; deprecated-elements discussion.
- Debreceny, R., Farewell, S., Piechocki, M., Felden, C., Gräning, A. & D'Eri, A. *Flex or Break? Extensions in XBRL Disclosures to the SEC.* Accounting Horizons 25(4):631, Dec. 2011. Abstract, para. 1.
- Dhole, S., Lobo, G.J., Mishra, S. & Pal, A.M. *Effects of the SEC's XBRL mandate on financial reporting comparability.* International Journal of Accounting Information Systems 19:29–44, 2015. Abstract.
- Kahle, K.M. & Walkling, R.A. *The Impact of Industry Classifications on Financial Research.* Journal of Financial and Quantitative Analysis 31(3):309–335, 1996. Abstract, para. 1.
- Guenther, D. & Rosman, A. SIC comparison (62% two-digit agreement), as summarized in *The Potential Misinterpretation Problem of Residual Based Models Due to Industry Misclassification*, Section 2, para. 3.
- Larsen et al. *Accuracy and errors in self-assigned NAICS codes in tax return data.* Statistical Journal of the IAOS, 2024. Abstract, para. 1.
- Hoitash, R. & Hoitash, U. *Measuring Accounting Reporting Complexity with XBRL.* The Accounting Review 93(1):259–287, 2017. Abstract.
- Hoitash, R., Hoitash, U., Kurt, A.C. & Verdi, R.S. *A Measure of Financial Statement Benchmarking.* SSRN 3208928, rev. 2023. Abstract.
- Huang, F., No, W.G. & Vasarhelyi, M.A. *Do Managers Use Extension Elements Strategically…?* 2018. Abstract, para. 1.
- *Excessive custom XBRL tag usage in 10-K filings and SEC oversight.* Journal of International Accounting, Auditing and Taxation / ScienceDirect S1467089525000181, 2025. Descriptive statistics, para. 2.
- Goodwin, G. *Extension Analysis.* Montana State University writing project, 2015. Summary, para. 3; taxonomy-version discussion.
- Leone, A.J., Minutti-Meza, M. & Wasley, C.E. *Influential Observations and Inference in Accounting Research.* 2013 working paper. Abstract, para. 1.
- *Averaging financial ratios.* Finance Research Letters, 2022. Highlights, bullets.
- He, L., Feng, M. & Song, E. *Efficient Input Uncertainty Quantification for Ratio Estimator.* INFORMS Journal on Computing, 2026. Abstract, para. 3.
- Kuryłek, W. & Kowalewski, O. *What We Know About Accounting Ratios: Methodological Considerations.* 2026. Abstract.

**Type 2 — official documentation, specs, white papers, books, renowned domain blogs**

- U.S. SEC, Division of Economic and Risk Analysis. *U.S. GAAP – XBRL Custom Tags Trend.* Introduction; and *XBRL Custom Tags Trend 2022–2024*, Section I, para. 1. https://www.sec.gov/data-research/structured-data/us-gaap-xbrl-custom-tags-trend
- U.S. SEC. *EDGAR Application Programming Interfaces (APIs).* Frames / Company Facts / Company Concept endpoint descriptions. https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- U.S. SEC, DERA. *Financial Statement and Notes Data Sets (FSNDS).* §3 Organization; §5.2 TAG field definitions; §5.4 NUM key list. https://www.sec.gov/dera/data/fsnds.pdf
- U.S. SEC. *Financial Statement Data Sets.* Scope note and Dec. 2024 reprocessing note. https://www.sec.gov/dera/data/financial-statement-data-sets.html
- FASB. *GAAP Taxonomy Implementation Guide — Revenue from Contracts with Customers.* Lines L1/L11/L15/L17.
- XBRL US. *Revenue Guidance* (DQC), 2018. ASC 606 tag-selection discussion.
- XBRL US. *Mutually Exclusive Elements*, DQC rule 0067, 2018. Rule description and example.
- XBRL International. *Modelling base taxonomies to work with Entity Specific Disclosures*, guidance (Rohman & Shaw). Section on extensions/extensible enumerations.
- PCAOB. *Data Points: Financial Restatements and Auditor Turnover*, DP04-2025. Finding 1.
- Ling, Q. & Liu, Z. *XBRL Data Comparability.* The CPA Journal, 21 Aug. 2019. Extension-use-over-time section.
- JPMorgan. *DSO & DPO: How They Can Improve Your Cash Flow.* DPO/DSO formula cells.
- GeminIQ. *Cash Conversion Cycle (CCC): Formula & Benchmarks.* TTM/average-balance methodology note.

**Type 3 — social posts, small blogs, podcasts, conference material**

- XBRL US. *SEC Custom Tag Analysis Shows Slight Decline for All Filers*, 30 May 2025. https://xbrl.us/news/sec-custom-tag-analysis-2025/
- MetricDuck Research. *How 2,100+ SEC Filers Actually Report Revenue in XBRL: Seven Years After ASC 606*, 7 Feb. 2026. https://www.metricduck.com/blog/xbrl-revenue-reporting-patterns-sec-filers-2025
- asp53826. *xbrl-normalize* (GitHub README). Revenue tag split; coverage table; accounting-identity oracle. https://github.com/asp53826/xbrl-normalize
- XBRL US forum thread, *How to find a complete list of similar concept*, 4 Jan. 2019. Microsoft tag-history example and FSDS tag-to-common-name mapping. https://xbrl.us/forums/topic/how-to-find-a-complete-list-of-similar-concept/
- Sonia Bobrik. *The Largest Schema Extension Experiment in History Has Been Running Since 2009.* DEV Community, 10 Sep. 2026. https://dev.to/sonia_bobrik_1939cdddd79d/the-largest-schema-extension-experiment-in-history-has-been-running-since-2009-6pb
- Usvyatsky, O. *The resurgence of restatements — is uptick here to stay?* Deep Quarry (Substack), 19 Dec. 2024. https://deepquarry.substack.com/p/the-resurgence-of-restatements-is
- *Audit Update.* *Two Studies Find that Restatement Rates Remain Low, Although Big R Restatements Have Begun to Increase*, 15 Jul. 2024. https://www.auditupdate.com/post/two-studies-find-that-restatements-rates-remain-low-although-big-r-restatements-have-begun-to-incre
