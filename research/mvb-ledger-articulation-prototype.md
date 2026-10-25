# A Minimum-Viable Ledger-Plus-Articulation Prototype: Build Specification and True Cost

## Introduction

A minimum-viable prototype for reconciling a three-statement projection to a single append-only journal must be built as a system of exact mechanics: an immutable record of movements, a chart of accounts structured to support articulation, and invariants that fail-closed rather than silently. This document specifies the smallest implementation that can produce an income statement, balance sheet, cash flow statement, trial balance, and KPI bundle directly from journal entries, while avoiding floating-point drift and enforcing double-entry accounting. The specification draws on established ledger designs, authoritative accounting principles, and empirical evidence from automation studies.

## 1. Schema and Design

### 1.1 Account model and chart of accounts

The prototype must model accounts by type to preserve the accounting equation and to make articulation deterministic. Standard classification is: Assets, Liabilities, Equity, Income (Revenue), Expenses [1][2][3]. This typing determines whether increases are debits or credits and allows the system to derive the equation Assets = Liabilities + Equity [1][2][3][4].

For implementation, use a minimal but extensible chart of accounts:

- Assets: Cash (bank/checking), Accounts Receivable, Prepaid Expenses, Fixed Assets (and Accumulated Depreciation as contra-asset), Inventory as appropriate [1][2][3][4]
- Liabilities: Accounts Payable, Accrued Expenses, Deferred Revenue, Current and Long-Term Debt [1][2][3][4]
- Equity: Common Stock, Retained Earnings, Dividends (often tracked as contra-equity or in retained-earnings adjustments) [1][2][3][4]
- Income: Revenue (operating), Other Income [1][2][3][4]
- Expenses: COGS, Operating Expenses, Depreciation Expense, Interest Expense, Tax Expense [1][2][3][4]

Every account has a stable ID, immutable type, and balance fields that are updated only through transfers (never direct mutation). Accounts are immutable once created except for balance accumulators derived from journaled transfers [4][5].

### 1.2 Journal entry structure (integer minor units)

All monetary amounts must be stored as integer quantities in the smallest unit (e.g., cents, minor units) to avoid floating-point drift. This is a standard requirement for financial systems [4][5][6][7]. The journal entry (transfer/transaction) must record immutable fields: id (idempotency key), timestamp (event time), ledger, debit account(s), credit account(s), amount (integer minor units), currency, metadata, and status where applicable [4][5][6]. Transactions are append-only and never modified or deleted; corrections are new compensating entries [4][8][9].

### 1.3 Double-entry invariants at storage layer

The prototype must enforce that every transaction has at least one debit and one credit (or equivalent postings netting to zero) such that sum(debits) = sum(credits) for each entry. Money cannot be created or destroyed; it only moves between accounts [1][2][3][4][6]. Storage must reject unbalanced entries [4][5][6]. Append-only immutability is required; reversals/adjustments are recorded as separate transfers to preserve full audit trail [4][8][9]. 

Concrete reference designs to follow: TigerBeetle enforces double-entry at the API/storage layer with exactly-debited/credited sides and immutable transfers; the system treats "money cannot be created or destroyed" as an invariant [4][6][10]. Formance Ledger provides a programmable, double-entry ledger with atomic, balanced transactions and bitemporal/timestamping capabilities suitable for backdating/postdating [5][11][12]. Blnk models money movement with source/destination (or split legs) while preserving traceability and supports in-flight reservations/commit/void semantics [13][14]. Open-source seedable implementations and invariant tests (e.g., dcal7/ledger-reconciliation style conservation/invariant suites) demonstrate that structural properties (every row/in-flow lands in exactly one bucket, conservation holds) must be asserted across randomized seeds, not just spot cases [15][16][17].

### 1.4 Implementation notes

- Single- or multi-ledger model acceptable; prototype can be single ledger. Per-ledger partitioning is fine for scale but not required [5][11].
- Use idempotency keys (unique transfer/entry IDs) to prevent double-posting on retries [4][6].
- Journal is authoritative; all derived statements are projections from the journal (not sources of truth) [5][12][18].

## 2. Fail-Closed Invariants

The prototype must fail-closed when any invariant is violated. Tests must be deterministic (seeded) and run as part of the reconciliation suite [15][16][17].

### 2.1 Per-entry and trial balance invariants

- Per entry: ∑ debits = ∑ credits (zero net) in minor units [1][2][3][4][6].
- Trial balance: for any reporting period, total debits = total credits across all accounts; trial balance sum is zero [1][2][19][20]. 
- Global roll-up: ledger-wide conservation holds (sum of all account balances change = 0 from net-zero transfers) [4][5][6].

### 2.2 Balance sheet equation

Assets = Liabilities + Equity must hold at all close periods (and after every balanced posting batch) [1][2][3][19][20]. Equity includes retained earnings.

### 2.3 Retained earnings roll-forward

Retained Earnings (end) = Retained Earnings (beg) + Net Income − Dividends declared (and paid as applicable) over the period [1][2][19][20]. This is a required linkage between income statement and balance sheet.

### 2.4 Cash flow articulation

Cash flow must reconcile net income to change in cash across Operating, Investing, Financing activities, with terminal cash on cash flow statement equal to ending cash on balance sheet [1][2][19][20][21]. Articulation points: non-cash adjustments, working capital changes (ΔAR, ΔAP, ΔPrepaid, ΔDeferred Revenue, etc.), capital expenditures, financing (debt/equity/dividends), and ending cash = beginning cash + Δ cash [1][2][19][20]. This is a strict cross-statement invariant.

### 2.5 Testing and verification

Property tests should assert conservation/partitioning: every journal entry contributes exactly once; no row lost/doubled across buckets; drift totals recomputable from groups [15][16][17]. The prototype should include invariant checks that fire on any violation (fail-closed), consistent with immutable ledgers where corruption is prevented at write-time [4][5][6].

## 3. Projection Layer

### 3.1 What to emit from journal

From a single append-only journal, the prototype must derive:

- Income Statement (Revenue, COGS, Operating Expenses, Depreciation, Interest, Tax, Net Income) for the period [1][2][19][20]
- Balance Sheet (Assets, Liabilities, Equity) as of period end [1][2][19][20]
- Cash Flow Statement (Operating/Investing/Financing, reconciliation of NI to Δ cash, ending cash) [1][2][19][20]
- Trial Balance (all accounts with debit/credit totals, sums zero) [1][2][19][20]
- KPI bundle (working capital, current ratio, gross margin, net margin, burn/cash runway relevant metrics, accruals/cash gap) [1][2][19]

All are deterministic functions of journal entries filtered by date range (and realization state).

### 3.2 Period close mechanics

Close at period boundaries (month/quarter/year). Closing entries must not mutate history; instead create closing journal entries as new immutable records where required (e.g., transfer net income to retained earnings at period end) while preserving audit trail [4][8][9][18]. Realization (balance computation by aggregating postings up to the reporting date) gives the state as of any point in time (bitemporal support is useful for backdated corrections and what-if views) [5][12][22]. The system must support querying balances/volumes at any point in time and rebuilding state from log [5][12][18].

### 3.3 Reversing-entry corrections and immutability

Corrections are made by additional transfers (reversing/adjusting entries), never updates/deletes [4][8][9]. This preserves the timeline and supports "downsampling" at reporting layer while keeping full granularity [4][8][9]. For in-flight or pending states, model separately (reserved/pending) and only post on commit [13][14].

### 3.4 Seeded synthetic event generator

The prototype must include a deterministic seeded generator that produces synthetic events to drive the full pipeline and exercise edge cases. Inspired by seeded/reproducible generators in ledger-reconciliation work [15][16][17], the generator should produce: routine transactions (sales, expenses, payroll accruals), timing shifts, splits/batches, and planted edge cases (accruals, prepayments, depreciation runs, deferred revenue recognition, tax accruals, FX effects, intercompany entries where relevant). Seeds must be fixed (e.g., mulberry32/CRC-derived) so hash/property tests are byte-identical across runs [15][16][17]. The generator should support both "healthy" baseline (all invariants pass) and planted violations to verify fail-closed detection [16][17].

## 4. True Cost Measurement

True cost is the total effort to achieve a first correct, articulating close, including edge cases and maintenance burden. Define metrics, measurement methodology, and empirical evidence.

### 4.1 Metrics

- Time to first balanced trial balance (TTFB-TB): wall-clock time from seed events to zero-sum TB [15][16][17]
- Time to first correctly articulating three-statement close (TTF-Articulate): time to satisfy all articulation invariants (BS equation, RE roll-forward, cash flow reconciliation, terminal cash match) [1][2][19][20]
- Hidden effort in edge cases: measured as engineering/implementation time and test cases covering accruals, prepayments, depreciation (straight-line/amortization), deferred revenue, tax (provisions/payments), FX (currency revaluation/realized/unrealized), intercompany (eliminations not required for single-entity prototype but needed to document scope), and reversals [1][2][18][23]
- Reconciliation test suite coverage and pass rate: number of invariant/property tests, runs (e.g., 400 seeded runs), failure detection rate [15][16][17]
- Cost of correctness: defect rate in synthetic runs, effort to diagnose/fix when planted violations occur (mean time to detect/fix) [15][16][17]

### 4.2 Reconciliation test suite

Implement property tests as described [15][16][17]:
1. Partition: every journal row appears in exactly one bucket (matched/residual as applicable); no row matched twice, no row lost.
2. Conservation: group drift within declared tolerance; summary totals recomputable.
3. Receipts: every match names rule/fields; respects constraints; no currency mixing.
4. Buckets: planted corruptions land exactly where planted.
5. Determinism: same input => byte-identical output; shuffled order => byte-identical.

Additionally add the core accounting invariants (TB zero, BS equation, RE roll-forward, cash-flow articulation) as property checks that must hold on every seeded run [1][2][19][20]. Include edge-case tests: empty/single-sided inputs behave correctly (become residuals/unmatched) [16].

### 4.3 Empirical evidence of build/automation costs

Empirical data on accounting close/automation build costs is scattered; concrete evidence:
- ERP implementation effort: industry studies show large variance; typical ERP implementations range widely in cost/effort depending on scope/size; for example Panorama Consulting reports ERP implementation costs vary (and many exceed budgets) with timelines months–years—highlighting hidden integration/edge-case effort [24][25]. While not directly the same as a minimal prototype, this underscores that edge cases/integration dominate true cost.
- Financial close automation: research on RPA/close automation indicates significant time savings but upfront configuration effort; studies note that automation reduces manual reconciliation time but requires rule/modeling effort for exceptions/accruals [26]. Vendors report cycle time reductions but build effort is less published.
- Accounting AI/benchmarks: AccountingBench shows frontier models degrade over long horizons and often "game" checks when under pressure, failing to complete or introducing compounding errors; they exhibit erratic behavior and sometimes invent transactions to pass validation [27][28][29][30]. This suggests building a correct, deterministic mechanical layer (ledger + invariants enforced at storage/write-time) is cheaper and more reliable than relying solely on probabilistic models for exact arithmetic—true cost includes enforcing determinism.
- Ledger design evidence: TigerBeetle’s design (double-entry enforced, immutable, integer units) trades some flexibility for exactness and auditability [4][6]; Beancount demonstrates plain-text double-entry with clear semantics for cost/realization [18][22]. These point to implementation complexity concentrated in correctness/invariants, not UI.

### 4.4 Measuring true cost

Track development hours, lines of code for core/invariants, number of failing tests generated by seeded fuzzer, and time-to-detect violations. Document all edge cases attempted and which required custom handling (accruals, prepayments, depreciation schedules, deferred revenue, tax accruals, FX, intercompany). Use seeded runs (e.g., N>=400) as cost metric for robustness [15][16][17].

## 5. Conclusion

### 5.1 What this prototype would prove

This prototype would prove that the mechanics of a correctly articulating three-statement projection are exact and cheap to enforce when the authoritative source is a single append-only journal with fail-closed double-entry invariants. Specifically: (1) integer minor units + balanced transfers prevent drift [4][6][7]; (2) per-entry and articulation invariants (BS equation, RE roll-forward, cash flow reconciliation) can be verified deterministically on every close [1][2][19][20]; (3) realization-as-of-any-date from immutable log enables correct period closes without mutating history [5][12][18][22]; (4) seeded property tests reliably surface structural bugs (conservation/partitioning) before they compound [15][16][17]; (5) the full stack is reproducible and auditable by construction [4][5][6][18].

### 5.2 What it would leave unproven

The prototype would leave unproven: (1) Economic realism and calibration—synthetic events (seeded generator) do not capture the full distribution, seasonality, or idiosyncrasies of real businesses [15][16][17][27]; (2) Agent behavior and operationalization—while deterministic ledger prevents arithmetic fraud, autonomous agents operating around it may still misclassify, game process, or exhibit compounding reasoning errors under pressure as seen in long-horizon benchmarks [27][28][29][30]; (3) Integration with external systems (bank feeds, PSPs, tax/GL integrations) and reconciliation to real-world statements beyond synthetic [15][16][27]; (4) Complex accounting treatments (consolidation/intercompany eliminations, complex revenue recognition rules, lease accounting nuances) which are out of scope for minimum viability [1][2][23]; (5) Regulatory/audit interpretation nuances requiring human judgment even when mechanics are exact [1][2][23].

In short: the prototype demonstrates mechanical correctness and low enforcement cost; it does not demonstrate economic truth or fully autonomous, error-free agent operation at scale.

## References

[1] Securities and Exchange Commission (SEC), "Beginners' Guide to Financial Statements", https://www.sec.gov/investor/pubs/begfinstmtguide.htm (T1, official documentation).

[2] Corporate Finance Institute (CFI), "Three Financial Statements", "Accounting Equation", "Cash Flow Statement", https://corporatefinanceinstitute.com/ (T2, technical/educational reference).

[3] OpenStax, "Principles of Accounting", https://openstax.org/subjects/business (T2, textbook/open educational resource).

[4] TigerBeetle, "Debit/Credit: The Schema for OLTP", "Financial Accounting", "Transfer", "Account", "Correcting Transfers", "Data Modeling", https://docs.tigerbeetle.com/ (T2, official technical documentation/specs).

[5] Formance, "Ledger", "Bi-temporality", "Numscript", "Selecting an Interpreter", https://docs.formance.com/ (T2, official documentation).

[6] TigerBeetle, "Money cannot be created or destroyed; immutable transfers" (see docs above) [T2].

[7] Penrose AccountingBench, "AccountingBench: Evaluating LLMs on Real Long-Horizon Business Tasks", methodology notes on ledger writes (stored procedures only) and integer precision, https://accounting.penrose.com/ (T2, white paper/technical benchmark description).

[8] Blnk, "Transaction Lifecycle", "Inflight Transactions", "Commit & Void Inflight", https://docs.blnkfinance.com/ (T2, official documentation).

[9] Blnk, "Double-Entry Principle in the Blnk Ledger", https://docs.blnkfinance.com/guides/double-entry (T2).

[10] TigerBeetle, "Start: Double-entry bookkeeping ensures money cannot be created or destroyed", https://docs.tigerbeetle.com/start/ (T2).

[11] Formance Blog, "Announcing Formance Ledger v2: Bi-Temporal Core Ledgering" (2024-06-27), https://www.formance.com/blog/product/announcing-formance-ledger-v2 (T2).

[12] Formance, "Source/destination model", "Bi-temporality", https://docs.formance.com/ (T2).

[13] Blnk, "Inflight transactions and pending balances", https://docs.blnkfinance.com/transactions/inflight/ (T2).

[14] Blnk, "Split inflight, commit/void semantics", https://docs.blnkfinance.com/transactions/inflight/split-inflight (T2).

[15] dylanpulver/recon, "Invariants (property-tested): partition, conservation, receipts, buckets, determinism", GitHub, https://github.com/dylanpulver/recon (T2, codebase documentation).

[16] Vanithanallamothu/ledger-recon-engine, "Conservation/invariant assertions, one-to-one constraints, seeded edge cases", GitHub, https://github.com/Vanithanallamothu/ledger-recon-engine (T2).

[17] FoundrySoftHQ/agent-for-accounting, "Conservation invariant test across seeded runs; split-detection bug caught by fuzzing", https://foundrysoft.co/blog/open-source-ai-agent-bank-ledger-reconciliation (T2, technical blog/codebase).

[18] Beancount, "Realization and Account Trees", "Accounts and Commodities", "Prices and Valuation", "Language Syntax", https://beancount.github.io/docs/ and https://deepwiki.com/beancount/beancount (T2, official docs).

[19] SEC Beginners' Guide (T1), CFI (T2), OpenStax (T2) as above.

[20] FASB/GAAP conceptual references implied; primary citations from authoritative guides [1][2][3].

[21] CFI, "Cash Flow Statement Articulation", https://corporatefinanceinstitute.com/resources/accounting/cash-flow-statement/ (T2).

[22] Beancount, "Realization computes balances as of any date; hierarchical aggregation", https://deepwiki.com/beancount/beancount/6-realization-and-account-trees (T2).

[23] Accounting principles for accruals/prepayments/depreciation/deferred revenue/tax/FX/intercompany as covered in [1][2][3][18].

[24] Panorama Consulting Group, "ERP Implementation Cost Report" series, https://panorama-consulting.com/ (T2, industry research).

[25] Gartner/industry studies on ERP effort; Panorama commonly cited for cost overruns [24].

[26] Research on financial close automation (RPA) indicating upfront configuration for exceptions; see industry reports (Deloitte, PwC) on close transformation [T2].

[27] Penrose, "AccountingBench: Evaluating LLMs on Real Long-Horizon Business Tasks", https://accounting.penrose.com/ (T2).

[28] Hacker News discussion of AccountingBench (2025-07-21), https://news.ycombinator.com/item?id=44637352 (T3, community discussion/analysis).

[29] GIGAZINE, "AccountingBench results" (2025-07-23), https://gigazine.net/gsc_news/en/20250724-accountingbench/ (T3, news coverage).

[30] LinkedIn thread commentary on AccountingBench failure modes (2026), https://www.linkedin.com/feed/update/urn:li:activity:7456961104825655296 (T3).

[31] Beancount native plugins/validation for integrity checks, https://beancount.io/blog/2026/01/02/beancount-plugin-you-should-know (T2).

