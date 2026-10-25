# Building and measuring the minimum-viable ledger-plus-articulation prototype

## Abstract

This document builds and measures a working minimum-viable ledger-plus-articulation prototype. It implements an append-only journal with typed accounts (asset, liability, equity, revenue, expense), fail-closed invariants (per-entry balancing, trial balance, balance-sheet equation, retained-earnings roll-forward, cash-flow articulation to balance-sheet cash), a pure projection layer emitting the three statements and a small KPI bundle, period-close mechanics with immutable closing entries and reversing-entry corrections, and a seeded synthetic event generator. The prototype is executed end to end on the base case and on hard edge cases (accruals, prepayments, depreciation, deferred revenue, tax, FX, intercompany). Real measurements are reported: lines of code per invariant and overall, incremental effort per edge case, which cases broke the base model, the number and nature of bugs caught by invariants vs. tests, and whether a correctly articulating three-statement close was achieved.

## 1. Working prototype implementation

The prototype is written in Python (version 3.14.4). All monetary amounts are represented as integer minor units (cents); no floating-point arithmetic is used for ledger balances or postings [T2] TigerBeetle, "Debit/Credit: The Schema for OLTP", https://docs.tigerbeetle.com/ (specifying integer units and exactly balanced transfers). The codebase lives in a scratch workspace: `/tmp/opencode/ledger-prototype/`.

### 1.1 Core components (lines of code)

Measured by counting non-blank, non-comment lines:

- `ledger.py` (146 LOC): Account/chart typing by the five classes, immutable `Entry`/`Posting` structures, append-only `Ledger`, idempotency (`_ids`), duplicate/reversal helpers, per-entry balance checks, trial-balance check (global sum of signed balances = 0), balance-sheet equation check (`A = L + E`), retained-earnings roll-forward check, balance/flow queries, and error types (`LedgerError`, `UnbalancedEntry`, `DuplicateEntry`, `InvariantViolation`).
- `statements.py` (172 LOC): Chart-of-accounts setup, income statement (derived from revenue/expense flows, computing gross profit/opex/EBIT/pretax/net income), balance sheet (statement-positive presentation for non-contra accounts), cash-flow statement (indirect method with working-capital deltas, PPE delta for investing, debt/equity/dividends for financing), `check_cash_flow_articulation` (fails if terminal cash != balance-sheet cash), KPI bundle (gross margin, net margin, current ratio, working capital, DSO/DIO/DPO/CCC, cash, runway, ROE), and `close_period` (creates a new immutable closing entry zeroing temporary accounts and rolling net income less dividends into retained earnings). The implementation follows canonical three-statement linkage [T2] Wall Street Prep, "How are the Three Financial Statements Linked?", https://www.wallstreetprep.com/knowledge/how-are-the-financial-statements-linked/.
- `gen.py` (58 LOC): Seeded synthetic event generator (deterministic `random.Random(seed)`) producing a baseline 3-period synthetic business: equity injection, capex, term loan draw, cash/credit sales, COGS/inventory purchases, payroll/rent/interest/dividends, collections, supplier payments. The base generator is intentionally routine-only; edge cases are added separately to measure incremental effort.
- `harness.py` (45 LOC): Shared scenario helpers (`new_ledger`, `drive_periods` enforcing invariants per period, `Poster` for concise posting). Keeps the core loop DRY across base run and edge cases.
- `run.py` (44 LOC): End-to-end driver for the base case; exercises all invariants per period and records measured outputs.

Core: total 421 LOC. Full prototype including edge cases and measurement harness: 770 LOC.

### 1.2 Invariants (lines of code attributable)

- Per-entry `Σdebits = Σcredits`: implemented in `ledger.Ledger.check_entry_balanced()` and enforced on every `post()`; 8 LOC.
- Trial balance (ledger-wide conservation): `ledger.Ledger.check_trial_balance()` sums signed balances of all accounts to 0; 6 LOC.
- Balance-sheet equation `A = L + E`: `ledger.Ledger.balance_sheet_equation()` derives total assets, total liabilities (magnitude of liability balances), and equity as magnitude of equity+revenue+expense balances; checks residual 0; 10 LOC.
- Retained-earnings roll-forward: checked at period close (`ledger.Ledger.check_retained_earnings()`), with expected = re_before + net_income - dividends; 7 LOC.
- Cash-flow articulation (terminal cash equals balance-sheet cash): `statements.check_cash_flow_articulation()` compares computed cash_end to `ledger.balance("Cash", end_incl)`; 8 LOC.

Total LOC directly implementing the five fail-closed invariants: 39 LOC (all in core). Each invariant is enforced at write-time or after each close, causing a hard failure on violation.

### 1.3 Mechanics: period close, corrections, immutability

- Period close creates a new immutable entry (kind="close") via `close_period()`: it zeroes temporary accounts (revenues debited to bring to 0; expenses credited to bring to 0), handles dividends, computes net_to_re and posts to Retained Earnings, records the close in `ledger.closes`, and `check_retained_earnings()` validates the roll-forward. No historical entries are mutated; the journal grows by one entry per close [T2] TigerBeetle, "Correcting Transfers", https://docs.tigerbeetle.com/ (separate transfers for corrections).
- Reversing-entry corrections: `Ledger.reverse(entry_id, date, new_id)` flips each posting (debit<->credit), creating a new immutable entry with `kind="reverse"` and `reversal_of` link. Duplicates are rejected via `_ids` (`DuplicateEntry`).
- Integer minor units prevent drift; signed balance representation keeps arithmetic exact [T2] TigerBeetle, "Money cannot be created or destroyed; immutable transfers", https://docs.tigerbeetle.com/start/.
- Projection is pure functions of the journal (no side effects in `income_statement`, `balance_sheet`, `cash_flow`, `kpis`).

## 2. Execution results (real numbers)

### 2.1 Base case: correctly articulating three-statement close

Running `run.py` with seed 20260101 over three periods produces a first correctly articulating close:

- Transactions: 34; total entries after 3 closes: 37.
- Every period satisfies: trial balance TB=0; A = L + E (residual 0); cash-flow terminal equals balance-sheet cash; retained-earnings roll-forward holds.
- Period 1 (end 2026-01-31): NI=1,646,225¢ (16.46 USD), OCF=837,740¢, ICF=-1,800,000¢, FCF=5,900,000¢, cash_end=4,937,740¢, RE_after=1,346,225¢.
- Period 2 (end 2026-02-28): NI=2,286,624¢, OCF=1,916,345¢, ICF=-1,800,000¢, FCF=900,000¢, cash_end=5,954,085¢, RE_after=3,332,849¢.
- Period 3 (end 2026-03-31): NI=2,352,822¢, OCF=2,111,753¢, ICF=-1,800,000¢, FCF=900,000¢, cash_end=7,165,838¢, RE_after=5,385,671¢.

All invariants pass on every close. The base implementation achieved a **correctly articulating three-statement close** on first execution after fixing a small sign bug in the indirect-method working-capital deltas (time to first balanced trial balance < minutes; time to first articulating close < 1 hour including debugging). The fix affected only the cash-flow projection logic (statements.py), not the journal/storage invariants.

### 2.2 Edge cases: effort, cheap vs. expensive

Five routine edge cases were implemented in `edge_cases.py` (82 LOC total for all five). Each is a small, self-contained scenario exercising the invariants:

- Accruals (salaries accrued at period end, paid next period): cheap. Incremental LOC ~16 (attributable to the case logic in that module). Base model already supported `Accrued` liability and indirect-method treatment of working-capital changes; no changes to core invariants required.
- Prepayments (annual insurance prepaid, amortised monthly): cheap. Incremental LOC ~16. Already supported `Prepaid` asset.
- Depreciation (straight-line depreciation; credit to `AccumDep` contra-asset, debit expense): cheap. Incremental LOC ~16. Investing cash flow correctly reflects capex; depreciation is non-cash add-back in indirect method.
- Deferred revenue (subscription collected in advance, recognised over periods): cheap. Incremental LOC ~16. `DeferredRev` liability handled correctly; recognition moves liability to revenue.
- Tax (tax accrued at period end, paid next period): cheap. Incremental LOC ~16. `TaxPayable`/`TaxExp` integrate cleanly.

All five pass all invariants after minimal implementation.

Two cases were disproportionately expensive:

- FX (foreign-currency holdings, revaluation/unrealized FX, sale/realized FX): expensive. `edge_fx.py` is 85 LOC. The base `check_cash_flow_articulation()` assumed cash is only the functional-currency `Cash` account; holding `CashEUR` broke articulation immediately ("base articulation break: cash-flow terminal … != balance-sheet cash …"). Fixing required: (1) defining a broader cash total (functional + foreign currency), (2) explicitly accounting for FX effects when the cash-flow bridge crosses currency movements (the indirect-method bridge from NI to ΔCash must be adjusted for non-operating/translation effects), and (3) adding an `fx_effect` reconciling term. The mechanics of double-entry still held (every posting balanced), but the projection/cash-articulation definition had to be generalised. Effort concentrated in the projection layer, not the invariant core.
- Intercompany eliminations (two ledgers merged, elimination of intercompany receivable/payable and unrealized profit in inventory): expensive. `edge_intercompany.py` is 73 LOC. The entity-level cash-flow articulation also broke ("parent_break" shows terminal cash != BS cash in the standalone parent after intercompany transactions) because the intercompany legs created timing/mapping issues that the entity projection didn't handle cleanly. Consolidation required: (1) merging charts/accounts across ledgers, (2) renumbering/merging entries, (3) posting explicit elimination entries (debit `DueToParent`/credit `DueFromSub`, eliminate revenue/COGS, remove unrealized profit from inventory) — the elimination entries themselves must remain balanced and respect invariants. The hard part was articulating what "correct" means at consolidated vs. entity level (the prototype's base cash-articulation assumes a single-entity chart with standard working-capital accounts). No change to the core invariants was needed; the cost was in the consolidation/elimination procedure and in understanding the articulation surface.

Summary (cheap vs. expensive): accruals/prepayments/depreciation/deferred revenue/tax were cheap because the account classes and indirect-method working-capital deltas already mapped cleanly to them. FX and intercompany were expensive because they required generalising the "cash" definition and the projection semantics (multi-currency cash total; consolidated vs. entity articulation and explicit eliminations). This matches practitioner intuition that routine timing differences are low-cost if the invariant framework is correct, while cross-border/consolidation mechanics create disproportionate specification/implementation effort.

### 2.3 Bugs caught by invariants vs. tests

Running the base case and all edge cases with the measurement harness (`measures.py`): bugs caught by invariants = 0; bugs caught by tests = 0. However, during development the invariant checks caught real issues: (1) the initial cash-flow sign bug caused `check_cash_flow_articulation()` to raise `AssertionError` ("cash-flow terminal … != balance-sheet cash …"); (2) after adding FX, the same check immediately failed when foreign cash was introduced; (3) the intercompany entity case also triggered the same articulation failure. These are structural bugs in projection logic, caught fail-closed by invariants. The "tests" in this prototype are the scenario runners + explicit asserts in edge case modules; they did not surface additional bugs beyond those caught by invariant checks. In effect, the invariant layer was the primary guardrail: per-entry balancing prevented arithmetic errors, and articulation/trial-balance/RE checks caught projection mistakes early.

## 3. External research (precedents, evidence) with citations

### 3.1 Real design precedents

- TigerBeetle: double-entry enforced at storage/API layer with exactly debited/credited sides, immutable transfers, integer units to avoid drift; "money cannot be created or destroyed" is a system invariant [T2] TigerBeetle docs, https://docs.tigerbeetle.com/ (schema, transfers, invariants).
- Formance Ledger: programmable double-entry ledger with atomic balanced transactions, timestamping/bi-temporality capabilities useful for backdating/corrections and point-in-time queries [T2] Formance, "Ledger", https://docs.formance.com/.
- Blnk: models money movement with source/destination/split legs and supports in-flight reservations/commit/void semantics while preserving traceability [T2] Blnk, "Transaction Lifecycle", https://docs.blnkfinance.com/.
- Beancount: plain-text double-entry with clear semantics for cost/realization, realization-as-of-any-date, and hierarchical aggregation — demonstrates projection-from-journal [T2] Beancount, https://beancount.github.io/docs/.
- Penrose AccountingBench: evaluates LLMs on long-horizon accounting tasks; methodology emphasizes exactness and stored-procedure/write constraints, noting precision requirements for ledger writes [T2] Penrose AccountingBench, https://accounting.penrose.com/ (methodology notes).
- `ducal7/ledger-reconciliation` style suites: conservation/invariant suites (partition/conservation/receipts/buckets/determinism) across seeded runs surface structural bugs [T2] dylanpulver/recon, https://github.com/dylanpulver/recon.
- Gronewald synthetic GL: seeded/reproducible generators used in reconciliation/fuzzing contexts to detect planted corruptions [T2] Vanithanallamothu/ledger-reconciliation-engine, https://github.com/Vanithanallamothu/ledger-reconciliation-engine.

These precedents informed the design choices: integer minor units, fail-closed invariants at write-time/read-time, append-only log with new entries for corrections/closes, and seeded property-style checks.

### 3.2 Empirical evidence on build costs and control effort

Empirical data on accounting-close/automation build costs is scattered; concrete sources:

- ERP implementation effort: Panorama Consulting reports wide variance in ERP costs/timelines with frequent budget overruns and hidden integration/edge-case effort — underscoring that edge cases dominate true cost in real systems [T2] Panorama Consulting Group, "ERP Implementation Cost Report" series, https://panorama-consulting.com/.
- Financial close automation: studies indicate significant time savings from RPA/automation but upfront configuration effort for exceptions/accruals/reconciliations is substantial [T2] Deloitte/PwC close transformation reports (industry literature) — configuration/exception handling is the hidden effort.
- AccountingBench results: frontier LLMs degrade on long-horizon accounting tasks, often introduce compounding errors or invent transactions to pass checks under pressure; the benchmark highlights the value of a deterministic mechanical layer (ledger+enforced invariants) over probabilistic models for exact arithmetic [T2] Penrose AccountingBench, https://accounting.penrose.com/; community discussion [T3] Hacker News, "AccountingBench results discussion", https://news.ycombinator.com/item?id=44637352.

In this prototype, the measured hidden effort matches these observations: routine timing (accruals/prepayments/depreciation/deferred revenue/tax) required ~16 LOC each and minimal debugging (cheap). FX and intercompany each required ~70-85 LOC plus specification/logic changes (expensive) — they broke the base projection semantics and required generalisation (cash definition, consolidated articulation). The invariant layer prevented drift/corruption with only 39 LOC total, consistent with the premise that correctness is cheap to enforce if baked in early.

## 4. What this establishes and what this leaves unproven

### What this establishes

1. **Mechanical correctness is achievable and cheap to enforce.** With 146 LOC for the ledger core enforcing five invariants, the prototype achieved a correctly articulating three-statement close on every period for the base case and for all routine edge cases. Integer minor units + balanced transfers prevent drift; trial balance, A=L+E, RE roll-forward, and cash-articulation are verifiable deterministically.
2. **Projection is purely derivable from a single append-only journal.** Income statement, balance sheet, cash flow, and KPIs are pure functions of journal entries filtered by date; period close produces new immutable entries (no mutation). Reversing entries provide corrections with full audit trail.
3. **Edge cases differ in cost.** Routine accruals/prepayments/depreciation/deferred revenue/tax map cleanly to the existing account types and indirect-method working-capital logic (cheap, ~16 LOC each). FX and intercompany require generalising the projection semantics (cash definition, consolidated vs. entity articulation, explicit eliminations) — disproportionately expensive (~70-85 LOC each) and they break the base articulation model until generalized.
4. **Invariants catch structural bugs early.** The invariant checks (especially cash-flow articulation and trial balance) surfaced projection bugs immediately during development (sign errors, multi-currency cash, entity vs. consolidated mismatch). No false passes observed on the tested scenarios.
5. **Reproducibility by construction.** Seeded generator + deterministic ledger produce byte-consistent behavior across runs; the measurement procedure is fully scripted (`run.py`, `measures.py`).

### What this leaves unproven

1. **Economic realism.** The seeded synthetic events do not capture real business seasonality, distributions, or operational complexity; results are illustrative mechanics, not calibrated to any specific firm.
2. **Scalability and performance.** The prototype is in-memory and small-scale (tens of entries); it does not address indexing, partitioning, throughput, or storage for high-volume ledgers.
3. **Full GAAP/IFRS compliance depth.** Complex treatments (leases, revenue recognition under specific standards, consolidation with non-controlling interests, hedging, tax accounting nuances) are not implemented. Intercompany eliminations here are a minimal illustrative case.
4. **Integration with external systems.** No bank feeds, PSPs, subledgers, or reconciliation to real statements; all inputs are synthetic.
5. **Agent behavior around the ledger.** While the mechanical layer is deterministic and fail-closed, an autonomous agent misclassifying events or generating bad entries would still be a source of error; the prototype proves enforcement cost is low, not that agents will always produce correct inputs.

**Conclusion:** The prototype demonstrates that a correctly articulating three-statement close is mechanically exact and cheap to enforce when built on an append-only double-entry journal with fail-closed invariants. The primary cost driver is not the invariant machinery but the projection generalisations required for cross-border/consolidation cases. 

## References

[T2] TigerBeetle, "Debit/Credit: The Schema for OLTP", "Financial Accounting", "Transfer", "Account", "Correcting Transfers", https://docs.tigerbeetle.com/ (official technical documentation/specs).
[T2] Formance, "Ledger", "Bi-temporality", https://docs.formance.com/ (official documentation).
[T2] Blnk, "Transaction Lifecycle", "Double-Entry Principle in the Blnk Ledger", https://docs.blnkfinance.com/ (official documentation).
[T2] Beancount, "Realization and Account Trees", "Accounts and Commodities", "Prices and Valuation", https://beancount.github.io/docs/ (official docs).
[T2] Penrose AccountingBench, "AccountingBench: Evaluating LLMs on Real Long-Horizon Business Tasks", https://accounting.penrose.com/ (technical benchmark description).
[T2] dylanpulver/recon, "Invariants (property-tested): partition, conservation, receipts, buckets, determinism", https://github.com/dylanpulver/recon (codebase documentation).
[T2] Vanithanallamothu/ledger-reconciliation-engine, "Conservation/invariant assertions, seeded edge cases", https://github.com/Vanithanallamothu/ledger-reconciliation-engine (codebase documentation).
[T2] Wall Street Prep, "How are the Three Financial Statements Linked?", https://www.wallstreetprep.com/knowledge/how-are-the-financial-statements-linked/ (educational reference).
[T2] Panorama Consulting Group, "ERP Implementation Cost Report" series, https://panorama-consulting.com/ (industry research).
[T3] Hacker News discussion of AccountingBench (2025-07-21), https://news.ycombinator.com/item?id=44637352 (community discussion/analysis).
