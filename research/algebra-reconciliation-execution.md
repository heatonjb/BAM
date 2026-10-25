# Executing the Reconciliation Identity: GAAP Net Income vs Throughput Profit on the OCEL 2.0 Inventory Management Simulation

## 1. Question and claim under test

The transformation-algebra programme proposes a quantitative bridge between a throughput-accounting (TOC) view of a firm and a GAAP full-absorption view. The bridge is the reconciliation identity

$$NI_{GAAP} = NP_{TA} + \Delta Inv \times \frac{\text{overhead}}{\text{unit}} \quad [\text{T2][19][20][21]]$$

where $NP_{TA} = Throughput - Operating\ Expense$, $\Delta Inv$ is the change in inventory *quantity* over the period, and the multiplier is the fixed production overhead absorbed per unit under full-absorption costing [T1][18]. The accounting content is standard: throughput accounting charges fixed overhead to the period as incurred, whereas absorption costing capitalises a slice of it into unsold inventory, so the two profit figures differ by exactly the inventory delta valued at the absorption rate [T2][19][20][21][T3][14][15][16][22].

This document *executes* that identity on a real, public event log and reports the residual, rather than asserting it as algebra. It does four things: (1) states the identity precisely with its two accounting views; (2) gives a fully runnable procedure that derives every input from pinned artifacts plus one declared synthetic cost layer; (3) reports the actual numbers, including the under/over-absorption variance and three falsification controls; (4) states what the exercise establishes and what it does not.

One refinement emerges from the execution and is worth stating up front, because it corrects a natural misreading of the identity. It is tempting to write the "extended" form

$$NI_{GAAP} = NP_{TA} + \Delta Inv \cdot oh_u + (AFOH - AbsorbedFOH),$$

i.e. to add the absorption variance $V = ActualFixedOverhead - AbsorbedFixedOverhead$ as a third additive term. That form is *double-counting* if the ledger closes the variance to the profit-and-loss account, as GAAP requires. When closed, $V$ is internal to both profit figures, and the base identity already holds exactly even when actual production runs far off normal capacity. The additive-$V$ form is correct only for a ledger that leaves the overhead pool open (unclosed). Section 5.4 demonstrates both regimes numerically: the base identity holds to the last decimal, and a ledger that omits the variance close produces a residual equal to $V$ *exactly*.

## 2. Artifacts and provenance

Every input is pinned by SHA-256 so the run is reproducible byte-for-byte.

| Artifact | Path | SHA-256 |
|---|---|---|
| OCEL 2.0 bundle (postprocessed) | `data/inventory_management_postprocessed.ocel.zip` | `2e450961e208d13ed1d161f9a0a76871b679264d24a3dc3b80c62a7b95433f6b` |
| Archived generator database | `data/inventory_management.db` | `c86daa9cd5d598567b1018ab27b50ed188c1f3bc52684c547c73e8a00a7c2899` |

Both derive from the OCEL 2.0 "Inventory Management Database and OCELs" simulation [T2][1], published on Zenodo under CC BY 4.0 [T2][3]. The bundle is a bundled Parquet/OCEL 2.0 archive [T2][4] readable with standard tool support [T2][5].

Loaded with PM4Py, the bundle contains **2,301 events** and **1,701 objects** across 7 object types (`CUSTOMER`, `MAT`, `MAT_PLA`, `PLA`, `PO_ITEM`, `SO_ITEM`, `SUPPLIER`), spanning 2023-09-28 to 2024-09-25 (UTC). Of the 30 event types, five are economic activities (Create Purchase Suggestion Item, Create Purchase Order Item, Goods Receipt, Create Sales Order Item, Goods Issue); the remaining types are synthetic status/annotation copies. The object-to-object relation table has **zero rows** — the sellable-output edge set is empty — so duality between inputs and outputs cannot be read off the graph and must be reconstructed from the material/plant objects and the archived database. The event-to-object relation has 10,956 rows.

The single most important discovery for reproducing the identity is that the published `Stock Before`/`Stock After` attributes are **not** the raw database stock; they are a *floored* series produced by the builder scripts and then subjected to an intra-day timestamp permutation by the postprocessor. Section 5.2 verifies this against the generator source rather than assuming it.

## 3. The two accounting views

Throughput accounting, in the TOC sense, values inventory at totally-variable cost only. Define $Throughput = Revenue - TVC$ and $NP_{TA} = Throughput - OE$, where $OE$ is operating expense, treated as a period cost in the short run [T3][14][15][16][T2][17].

Full-absorption costing absorbs fixed production overhead into units produced at the rate

$$oh_u = \frac{BudgetedFixedOverhead}{NormalCapacity_{units}}, \qquad AbsorbedFOH = oh_u \times ActualProduction_{units}\ [\text{T2}][19][20][21].$$

Cost of goods sold carries absorbed fixed overhead for units sold; unsold inventory carries absorbed fixed overhead for units still on hand. The difference between the two income figures is therefore exactly the fixed overhead capitalised into (or released from) inventory:

$$NI_{GAAP} = NP_{TA} + \Delta Inv \times oh_u.$$

The under/over-absorption variance is $V = ActualFixedOverhead - AbsorbedFixedOverhead$ (positive = under-absorbed) [T2][19][20][21]. Under GAAP, $V$ is closed to the P&L each period. Once closed, $V$ affects $NI_{GAAP}$ and (because the actual fixed overhead was already charged in $NP_{TA}$) is embedded in both figures; it is not a separate term of the identity. Section 5.3–5.4 shows this directly.

Because real systems use multiple overhead pools, the identity generalises to a sum over pools, $\sum_p \Delta Inv_p \times oh_p$, provided each inventory movement is attributed to a pool [T2][19][20][21]. The simulation supplies exactly three valuation classes, so this generalisation is testable here even though the scalar form is the primary claim.

## 4. A runnable procedure

The full pipeline is `code/reconcile_inventory.py` (540 lines) with the ledger engine `code/bamledger.py` (129 lines), run under Python 3.11 with `pandas`, `pyarrow`, and `pm4py`. It is deterministic and uses `decimal.Decimal` for all money so no floating-point drift can inflate a residual. The steps below mirror the script's sections; the key fragments are reproduced so the procedure is executable from the document.

### 4.1 Load the bundle and the ground-truth database

```python
import pm4py, sqlite3, hashlib
ocel = pm4py.read_ocel2_bundle("data/inventory_management_postprocessed.ocel.zip")
con  = sqlite3.connect("data/inventory_management.db")
# GoodsReceiptsAndIssues has one row per stock transaction
# (columns include Material_ID, Plant_ID, Timestamp, Quantity, and the
#  valuation class), 200 rows in the full period.
```

### 4.2 Identify stock flows and the economic subset

Stock-changing events are Goods Receipt (increase) and Goods Issue (decrease). The 16 synthetic status/annotation event types are **excluded** from flows because the postprocessor duplicates the receipt/issue rows into them, which would double-count quantities. Filtering to the two economic stock activities leaves **90 Goods Receipt + 97 Goods Issue = 187** stock events, against 200 rows in the database: the bundle omits 13 transactions (4 receipts = 131 units; 9 issues = 394 units), and introduces none of its own. This completeness gap is computed, not assumed, in §5.

### 4.3 Verify the stock semantics against the generator source

The builder's `Stock Before`/`Stock After` are SQL window values partitioned by material only:

```sql
SUM(CASE sign) OVER (PARTITION BY Material_ID ORDER BY Timestamp
                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
```

and then floored *per (material, plant)* by adding `max(0, -min(Stock Before, Stock After))` so no balance goes negative within a plant, with the first event per material dropped (its `Stock` is null). The postprocessor copies rows (with their `Stock` values) into synthetic status events and reassigns intra-day sub-second times by row index.

The script reproduces this floor directly from the archived database and compares with the published events:

- generator rows reproduced from archived DB: **1210**; published ORIG events: **1210**
- (material, plant) groups compared: **445**; `Stock After` multiset identical in **445 / 445**

So the published bundle embeds the generator's floored `Stock` series *exactly*; only within-day ordering is permuted. Any reconciliation that reads snapshots must use the floored series, not raw running sums.

### 4.4 Period definition and ΔInventory

Two period cuts are used. The full period $P_{full} = [2023\text{-}09\text{-}26,\ 2024\text{-}09\text{-}26)$ and a first half $P_{h1} = [2023\text{-}09\text{-}26,\ 2024\text{-}03\text{-}26)$. $\Delta Inv$ is computed two ways: as net flow (receipts $-$ issues) and as snapshot change (closing $-$ opening using the floored series). Because the floor is a *constant shift* over a period, the two agree exactly; that agreement is itself a check (Section 5.2).

### 4.5 Declare the synthetic cost layer

The event log carries no valuation, so one cost layer is declared and held fixed for every experiment:

| Parameter | Value |
|---|---|
| Price / unit | 10.00 |
| TVC / unit | 4.00 |
| Actual fixed overhead $AFOH$ | 4,500.00 |
| Normal capacity | 4,000 units |
| Absorption rate $oh_u$ | $4500/4000 = 1.125$ /unit |
| SG&A | 6,000.00 |

For the multi-pool variant, three pools are declared (one per valuation class): $AFOH_p = \{1300, 1500, 1700\}$, $Normal_p = \{1200, 1500, 1300\}$ for ValClass1/2/3, giving $oh_p = \{1.0833\ldots, 1.0, 1.3077\ldots\}$.

### 4.6 Build the two ledgers and post the entries

`BAMLedger` is a minimal balanced double-entry engine using `Decimal`. A critical implementation detail: `post` must be **type-aware**. Debit-normal accounts (Asset, Expense) accumulate `debit - credit`; credit-normal accounts (Liability, Equity, Income) accumulate `credit - debit`. A naive engine that accumulates `debit - credit` for every account reports Revenue as negative, which silently breaks the close. Each entry still satisfies $\sum debit = \sum credit$.

The single-pool GAAP ledger posts, per period: purchases at variable cost, sales, variable COGS, fixed overhead incurred to a cost pool, absorption ($oh_u \times$ produced) from pool to inventory, release of absorbed overhead to COGS for units sold ($oh_u \times$ sold), SG&A, and then a conventional-sign `close_period` that zeroes every P&L account (Revenue, COGS:TVC, COGS:FOH, SG&A, and the variance pool) into retained earnings.

### 4.7 Compute both profits and the residual

```python
NP_TA  = (PRICE - TVC) * sold - (AFOH + SGNA)      # throughput profit
NI_GAAP = revenue - COGS_tvc - COGS_foh - SGNA      # from the ledger
oh_u   = AFOH / normal_capacity
residual = NI_GAAP - (NP_TA + delta_inv * oh_u)
V = AFOH - oh_u * produced                          # under(+) / over(-) absorbed
```

The identity holds iff $|residual|$ is at rounding scale. The residual is *reported*, never coerced to zero, and the trial balance is checked on every run.

### 4.8 Falsification controls

Three controls make the test sensitive rather than tautological: (a) a constructed **flat-inventory** window ($\Delta Inv = 0$) where the two profits must coincide despite a large variance; (b) **opening-balance truncation**, which must break the identity if $\Delta Inv$ is read from snapshots but must leave it invariant when read as net flows; (c) a ledger that **fails to close the variance pool**, which must produce a residual equal to $V$.

## 5. Results

All figures below are the actual output of `reconcile_inventory.py`, saved verbatim in `code/reconcile_output.txt`.

### 5.1 Completeness of the event log

The database records **200** stock transactions; the bundle publishes **187** stock events. The 13 omitted transactions are 4 Goods Receipt (131 units) and 9 Goods Issue (394 units); the bundle contains **zero** events not present in the database. The database ground-truth totals are 4,225 receipt units and 5,178 issue units, net $\Delta Inv = -953$ units. The published OCEL flows total 4,094 receipts and 4,784 issues, net $-690$ units. The gap is therefore a pure *coverage* deficit — the log is a strict subset of the archive — and it propagates into every OCEL-based figure.

### 5.2 Stock semantics and ΔInventory consistency

| Period / source | produced (receipts) | sold (issues) | $\Delta Inv$ (flow) | opening | closing | $\Delta Inv$ (snapshot) |
|---|---|---|---|---|---|---|
| $P_{full}$, DB complete | 4,225.0 | 5,178.0 | $-953.0$ | 5,011.0 | 4,058.0 | $-953.0$ |
| $P_{full}$, OCEL published | 4,094.0 | 4,784.0 | $-690.0$ | 4,617.0 | 3,927.0 | $-690.0$ |
| $P_{h1}$, DB | 2,185.0 | 2,358.0 | $-173.0$ | 5,011.0 | — | — |

In both full-period cases the snapshot delta equals the flow delta exactly, confirming the floor is a constant additive shift over the window and that the identity's inputs are internally consistent.

### 5.3 Single-pool reconciliation

All money in units of the declared cost layer; residuals to four decimals.

| Run | produced | sold | $\Delta Inv$ | $NP_{TA}$ | $NI_{GAAP}$ | $\Delta Inv \cdot oh_u$ | $V$ | residual |
|---|---|---|---|---|---|---|---|---|
| $P_{full}$ DB complete | 4,225 | 5,178 | $-953$ | 20,568.00 | 19,495.88 | $-1,072.12$ | $-253.12$ (over) | **0.0000** |
| $P_{full}$ OCEL | 4,094 | 4,784 | $-690$ | 18,204.00 | 17,427.75 | $-776.25$ | $-105.75$ (over) | **0.0000** |
| $P_{h1}$ DB | 2,185 | 2,358 | $-173$ | 3,648.00 | 3,453.38 | $-194.62$ | $2,041.88$ (under) | **0.0000** |

Every trial balance closes exactly ($145{,}177.25 = 145{,}177.25$ for $P_{full}$ DB; $141{,}089.8750$ for OCEL; $129{,}134.75$ for $P_{h1}$).

The base identity holds to the last decimal in all three runs **even though** $V$ ranges from $-253.12$ (over-absorbed) to $+2{,}041.88$ (substantially under-absorbed). This is the empirical refutation of the additive-$V$ reading: the variance does not appear as a third term, because the ledger closed it to the P&L where it is already inside both $NP_{TA}$ and $NI_{GAAP}$. Intuitively: $NP_{TA}$ charges all $AFOH$; $NI_{GAAP}$ charges $oh_u \times sold$ in COGS plus the closed variance $V = AFOH - oh_u \times produced$; their difference is $oh_u \times (produced - sold) = oh_u \cdot \Delta Inv$.

### 5.4 The variance is internal, not an extra term (falsification c)

A ledger that omits the variance close is a different, wrong ledger. Running the same period with the pool left open:

- $NI_{GAAP}$ (no variance close) $= 19{,}242.75$ versus the correct $19{,}495.88$
- residual $= -253.1250$, and $V = -253.1250$; **residual $\equiv V$ exactly**.

So the additive form is exactly the statement "I forgot to close the variance." With the close, the base identity holds; without it, the residual equals $V$. The two regimes are mutually consistent and the choice of framing is bookkeeping, not algebra.

### 5.5 Multi-pool reconciliation

Attributing each material to its valuation class and giving each class its own pool:

- $\Delta Inv$ by pool (units): ValClass1 $+468$, ValClass2 $-1{,}123$, ValClass3 $-298$
- $\sum_p oh_p \cdot \Delta Inv_p = -1{,}005.69$
- $NP_{TA} = 20{,}568.00$ (unchanged; TA does not split overhead)
- $NI_{GAAP} = 19{,}562.31$ (multi-pool ledger)
- $NI_{GAAP} - NP_{TA} = -1{,}005.69$, matching the pooled term exactly
- per-pool variances $V_p = \{-552.50, +374.00, -116.38\}$
- residual $= 1\times 10^{-23}$

The multi-pool run introduces a repeating decimal ($oh_{1} = 1300/1200 = 1.08\overline{3}$), so the trial balance is not bit-exact but is balanced within $10^{-18}$: $145{,}206.1538461538461538461538$ vs $145{,}206.1538461538461538461539$, difference $-10^{-22}$. The residual $10^{-23}$ is pure decimal rounding; the identity holds at machine precision. This confirms the pooled generalisation and shows the residual is a diagnostic of allocation error, not noise to be tolerated.

### 5.6 Falsification (a): flat inventory forces equal profits

A window with $\Delta Inv = 0$ must collapse the identity to $NI_{GAAP} = NP_{TA}$, regardless of $V$.

- **Constructed** (opening 200, produced 100, sold 100): $NI_{GAAP} = NP_{TA} = -9{,}900.00$, $V = +4{,}387.50$ (huge under-absorption), residual $0.000$.
- **Real window** $[2023\text{-}10\text{-}31,\ 2024\text{-}03\text{-}23)$ (144 days): receipts $1{,}839.0$ $=$ issues $1{,}839.0$, $NI_{GAAP} = NP_{TA} = 534.00$, $V = +2{,}431.12$, residual $0.0000$, trial balance $126{,}215.3750$ exact.

Both pass with a large variance present, which is precisely the discriminating power we want: the control separates "$\Delta Inv$ drives the gap" from "the variance drives the gap."

### 5.7 Falsification (b): truncation breaks the identity — but only through snapshots

With the opening balance reported as $0$ instead of the true $5{,}011$:

- flow-based residual stays **0.0000** (net flows do not depend on the opening level)
- snapshot-based $\Delta Inv$ becomes $+4{,}058$, giving residual $= -5{,}637.3750$
- the predicted breach $-oh_u \times 5{,}011 = -5{,}637.375$ matches to the last decimal

A second, *partial* truncation — dropping only material 49 / Plant 4's opening of $129.0$ — leaves the flow-based residual at $0.0000$ and predicts a snapshot breach of $-oh_u \times 129.0 = -145.12$. The identity therefore breaks **only** through a snapshot-derived $\Delta Inv$, and by exactly $oh_u \times$ (opening-balance error). This is the sharpest possible characterisation of the failure mode: the algebra is intact; the *state reconstruction* is what fails, and it fails proportionally to the missing opening units.

## 6. Where the mapping breaks

The execution surfaces five breakage axes, each demonstrated rather than asserted.

**Coverage gap.** The bundle is a strict subset of the archived database (187 of 200 stock events; 13 omitted transactions carrying 525 units). OCEL-derived flows therefore under-count receipts and issues relative to ground truth, and the OCEL net ($-690$) differs from the database net ($-953$) by exactly those omitted transactions. Any log-only reconciliation inherits this bias.

**Empty duality.** The object-to-object relation table is empty, so the REA-style duality between decrement (issue) and increment (production) events is not recoverable from the graph [T2][4][5]; the mapping must fall back on material/plant typing plus the database. This is a modelling gap in the artifact, not a failure of the identity.

**Stock semantics.** Balances are floored per plant by the builder and re-timestamped within a day by the postprocessor. A naive running sum over the published events disagrees with the published `Stock After`; the reconciliation is exact only after reproducing the floor from the database (§5.2). This is the single easiest way to "break" the identity without any accounting error.

**Valuation is synthetic.** The event log carries quantities but no prices or costs, so the entire valuation layer — price, TVC, $AFOH$, normal capacity, pool split — is declared, not observed. The identity is tested against a *consistent* synthetic ledger; it is not evidence that any real firm's cost structure obeys these rates.

**Cash, capacity, and mission are absent.** No general ledger ships with the log, so the cash leg (receipts/payments, DPO) cannot be validated end-to-end [T2][19]. Normal capacity is declared, not observed; the log contains no bottleneck rate $r_b$, so TOC constraint logic is outside the tested algebra. Nothing in the data encodes mission, brand, or non-financial constraints.

## 7. What this establishes

- **The reconciliation identity holds exactly, at decimal precision, on a real public event log plus a declared cost layer.** Residuals of $0.0000$ (single pool), $10^{-23}$ (multi-pool, from a repeating absorption rate), and $0.0000$ on a 144-day real window are not tolerance-passing approximations; they are the arithmetic result of two independently constructed profit figures agreeing.

- **The under/over-absorption variance is internal to the identity, not an additive term.** When the variance is closed to P&L — as GAAP requires — the base form $NI_{GAAP} = NP_{TA} + \Delta Inv \cdot oh_u$ holds even when $V$ is large (here between $-253$ and $+2{,}432$). A ledger that fails to close the variance produces a residual equal to $V$ *exactly* ($-253.1250$), which is the precise accounting meaning of the additive form.

- **The pooled generalisation is exact.** $\sum_p \Delta Inv_p \cdot oh_p = -1{,}005.69$ reproduces $NI_{GAAP} - NP_{TA}$ to machine precision, with only rounding-scale residual from a non-terminating absorption rate.

- **The identity's only fragile input is $\Delta Inventory$, and it fails in a measurable way.** Truncating the opening balance leaves the flow-based residual at $0.0000$ but drives the snapshot-based residual to $oh_u \times$ (missing units): $-5{,}637.375$ for a full truncation, $-145.12$ for a single 129-unit omission. The failure is linear and diagnosable, not mysterious.

- **The falsification suite is discriminating.** A flat-inventory window forces $NI_{GAAP} = NP_{TA}$ despite a variance of $+2{,}431$; omitting the variance close produces residual $= V$; truncation breaks only the snapshot channel. Each control can fail and none did.

## 8. What this does not establish

- **It does not validate real-world GAAP valuation.** The valuation layer is declared, not observed. Passing on a synthetic ledger proves internal consistency of the accounting algebra; it says nothing about whether a real firm's overhead, capacity, or inventory accounting matches these rates [T2][19][20].

- **It does not validate the cash leg.** No ledger ships with the log, so receipts/payments and any cash-flow or DPO identity remain untested end-to-end. Cash articulation would require a separate synthetic journal layer, which would again prove internal consistency, not empirical validity.

- **It does not validate capacity or TOC constraint logic.** Normal capacity is a declared constant, not an inferred bottleneck; the log carries no $r_b$, so throughput per constraint-minute and product-mix ranking are outside scope [T3][14][15][16].

- **It does not generalise beyond the simulated process.** Joint products, byproducts, scrap, WIP valuation, intercompany eliminations, and multi-currency treatment are absent; the identity's behaviour under those complications is unestablished.

- **It does not make the OCEL a financial ledger.** The log supplies quantities and process structure; every monetary figure is an overlay. The exercise shows that *if* the cost layer is declared and the balances are reconstructed correctly, the two accounting views reconcile exactly — which is a statement about the algebra and the event log's fitness as a quantity source, not about the log's completeness or a firm's real profitability.

## 9. References

### [T1] Peer-reviewed / textbook sources
- **[T1][18]** Horngren, C. T., Datar, S. M., Rajan, M. V. (2015). *Cost Accounting: A Managerial Emphasis* (15th ed.). Pearson. (Full-absorption costing, overhead absorption rates, under/over-absorbed overhead; inventory valuation effects on income) — Ch. 8–9.

### [T2] Official documentation / specifications / authoritative guidance
- **[T2][1]** OCEL 2.0. "Inventory Management Database and OCELs." Event Logs / Simulations. https://www.ocel-standard.org/event-logs/simulations/invent_manag/ (accessed 2026-10-11).
- **[T2][3]** Berti, A. (2026). "Simulated Inventory Management Database and Object-Centric Event Logs for Process Analysis (updated record)." Zenodo. https://zenodo.org/records/21977737 (accessed 2026-10-11). CC BY 4.0; includes `inventory_management_postprocessed.ocel.zip`.
- **[T2][4]** OCEL 2.0 Specification. "Bundled CSV/Parquet format." https://www.ocel-standard.org/specification/formats/bundled/ (accessed 2026-10-11).
- **[T2][5]** OCEL 2.0 Tool Support. "Overview." https://ocel-standard.org/tool-support/overview/ (accessed 2026-10-11).
- **[T2][17]** TOCICO. "Throughput Accounting." Theory of Constraints International Certification Organization. https://www.tocico.org/ (accessed 2026-10-11).
- **[T2][19]** PwC. "Viewpoint (Accounting & reporting)." https://viewpoint.pwc.com/ (accessed 2026-10-11). Absorption costing / overhead allocation guidance.
- **[T2][20]** CPA Ireland. "Technical Resources / Financial Reporting." https://www.cpaireland.ie/Technical-Resources/Financial-Reporting (accessed 2026-10-11). Inventory and overhead absorption.
- **[T2][21]** ACCA. "Technical articles / Management Accounting." https://www.accaglobal.com/ (accessed 2026-10-11). Absorption costing / overhead variances.

### [T3] Practitioner / tertiary sources
- **[T3][14]** Goldratt, E. M., Cox, J. (1984). *The Goal: A Process of Ongoing Improvement*. North River Press.
- **[T3][15]** Corbett, T. (1998). *Throughput Accounting*. North River Press.
- **[T3][16]** Cox, J. F., Boyd, L. H., Sullivan, T. T., Reid, R. A., Cartier, B. (2012). *TOCICO Dictionary*, 2nd ed. https://www.tocico.org/resource/resmgr/dictionary/tocico_dictionary_2nd_ed.pdf (accessed 2026-10-11).
- **[T3][22]** Bragg, S. "Absorption costing." AccountingTools. https://www.accountingtools.com/articles/absorption-costing (accessed 2026-10-11).
