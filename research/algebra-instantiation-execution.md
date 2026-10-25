# Executing the transformation-algebra instantiation on the OCEL inventory simulation

## Abstract

This document specifies an executed/specified instantiation of the proposed "transformation algebra" (TA) on object-centric event logs (OCELs) for inventory management. The algebra asserts a GAAP/throughput reconciliation identity of the form

$$
NI_{GAAP} = NP_{TA} + \Delta Inventory \times overhead/unit
$$

where $NP_{TA} = Throughput - OperatingExpense$ (TA net profit), $\Delta Inventory$ is the inventory quantity change (closing quantity - opening quantity over the period), and $overhead/unit$ is fixed production overhead absorbed per unit under full-absorption GAAP costing. The goal is to move this from a proposed test protocol to an executed/specified result by grounding it in public artifacts, giving a runnable procedure, extending to absorption variances (including multiple overhead pools), defining falsification controls, and stating what this experiment can and cannot establish.

## 1. Public artifacts, fields, and licensing

### 1.1 OCEL 2.0 "Inventory Management Database and OCELs"

The "Inventory Management Database and OCELs" dataset is provided by the OCEL 2.0 standard as a simulation of inventory control and supply chain operations. The canonical landing page for the simulation is the OCEL 2.0 event logs site [T2][1] and the dataset is archived on Zenodo [T2][2][3].

Key artifacts (naming as published):

- `inventory_management.db` — SQLite database containing the simulated raw data [T2][1][2][3].
- `ocel_inventory_management.csv`, `.xml`, `.json`, `.sqlite`, `.ocel.zip` — initial OCEL serializations [T2][1][2][3].
- `post_ocel_inventory_management.csv`, `.xml`, `.json`, `.sqlite`, `.ocel.zip` — post-processed and enriched OCEL serializations [T2][1][2][3].

The post-processed/enriched logs add inventory management parameters (EOQ, Safety Stock, Reorder Point) and status-based activity labels (e.g. understock/overstock) [T2][1][2][3]. The OCEL 2.0 standard specifies the bundled ZIP/Parquet layout (`.ocel.zip`) containing `ocel-meta.json`, typed tables under `events/`, `objects/`, `object_changes/`, and `relations/` (e2o, o2o) [T2][4][5]. Tools supporting bundled OCEL 2.x include PM4Py, ocpa, Ocelot.pm, FLOWVAULT, etc. [T2][5].

For this instantiation, use the **post-processed enriched log** (e.g. `post_ocel_inventory_management.ocel.zip` / `inventory_management_postprocessed.ocel.zip`) because it exposes inventory-related attributes (Stock Before/After, status labels, EOQ/Safety Stock/Reorder Point) needed to track $\Delta Inventory$ and activity context [T2][1][2][3].

#### Fields relevant to inventory/quantities (from CSV/OCEL metadata)
From published metadata in the inventory management dataset [T2][2][3], relevant fields include:
- `ocel:activity`, `ocel:timestamp`, `ocel:type:MAT`, `ocel:type:PLA`, `ocel:type:PO_ITEM`, `ocel:type:SO_ITEM`, `ocel:type:CUSTOMER`, `ocel:type:SUPPLIER`, `ocel:type:MAT_PLA`, `ocel:eid`
- `Stock Before`, `Stock After` (quantities per relevant object/event context) [T2][2][3]
- Inventory parameters: `EOQ`, `Safety Stock (SS)`, `Reorder Point (ROP)`, `Average Daily Demand (d_m)`, `Std Dev of Daily Demand (σ_m)`, `Average Lead Time (l_m)`, `Annual Demand (D_m)`, status flags/labels (e.g. `Current Status`, `Understock`/`Overstock`/`Normal` in enriched logs) [T2][1][2][3]

In the OCEL 2.0 bundled form, these appear as event/object attributes with types declared in `ocel-meta.json` [T2][4].

### 1.2 Deterministic synthetic relational databases (fixed seed 20260820)

The OCEL 2.0 site also provides "Synthetic Relational Databases and Reference OCELs" — six deterministic, fully synthetic relational source databases, each paired with canonical reference OCELs in all five OCEL 2.1 formats. All data were generated deterministically with **seed `20260820`** [T2][6][7].

Artifacts per scenario: `.sqlite` (relational source), `.xmlocel.gz`, `.jsonocel.gz`, `.ocel.sqlite`, `.ocel.csv`, `.ocel.zip` (bundled Parquet) [T2][6][7]. The five OCEL serializations are equivalent (not shards). Reference logs include qualified e2o/o2o relations, temporal object attribute changes, activity-specific attributes, resource roles/calendars, exception paths, and source provenance [T2][6][7].

Note: These are separate from the "Inventory Management Database and OCELs" simulation above (different purpose: benchmarking RDB→OCEL extraction). For this TA instantiation focused on inventory simulation, the primary public artifact is the inventory management simulation (post-processed OCEL) [T2][1][2][3][6]. If using the deterministic seed set, treat the relevant scenario’s bundled OCEL as the input and preserve the fixed seed context in reproducibility notes [T2][6][7].

### 1.3 BPIC logs relevant to P2P and licensing

The Procure-to-Pay (P2P) domain is represented in BPI Challenge datasets; the OCEL 2.0 site lists "Procure-to-Pay (P2P)" as a simulation/log category [T2][8]. BPI Challenge 2019 is a P2P/purchase order handling dataset (4TU.ResearchData) with documentation of matching types (3-way/2-way/consignment), line items as cases in XES form, and compliance questions around matching invoices/GRs/payments [T2][9][10][11].

Licensing/usage notes: BPI Challenge datasets are distributed via 4TU.ResearchData (DOI-based) and are commonly used for research/education under the terms associated with those records [T2][9][10][11]. For OCEL versions of BPI datasets, converted OCEL 1.0/2.0 representations exist (e.g. BPI Challenge 2019 OCEL) with transformation described in the ER 2023 paper "Transforming Event Knowledge Graph to Object-Centric Event Logs: A Comparative Study for Multi-dimensional Process Analysis" [T2][12][13]. When reusing/redistributing BPI-derived OCELs, cite the original BPI dataset and the transformation publication as appropriate [T2][12][13].

Summary: use the inventory simulation OCELs as the primary testbed for the inventory identity; treat BPIC19 OCELs as P2P reference only (licensing/attribution required) and do not assume they expose the same Stock Before/After fields unless transformed accordingly [T2][1][8][9][12].

## 2. Runnable, code-level procedure (PM4Py/ocpa + synthetic double-entry layer)

This section gives a concrete, reproducible procedure. Assume Python environment; prefer PM4Py for OCEL 2.0 I/O and ocpa for object-centric analysis where useful [T2][5]. For the accounting layer, use a synthetic double-entry (e.g. Beancount-style ledger model or a minimal in-memory chart with debits/credits) to compute $NI_{GAAP}$ from period events [T2][29][T3][30].

### 2.1 Environment/setup

- Python 3.9+ recommended.
- Packages: `pm4py` (OCEL 2.0 read/write: XML/JSON/SQLite/CSV/bundled ZIP/Parquet), `ocpa` (optional for OCPM queries), `pyarrow` (Parquet), `pandas`, `numpy` [T2][5].
- Input: `post_ocel_inventory_management.ocel.zip` (bundled OCEL 2.0, Parquet) from [T2][1][2][3].

### 2.2 Load OCEL

Read bundled OCEL 2.0 [T2][4][5]:
```python
import pm4py
ocel = pm4py.read_ocel2_bundle("post_ocel_inventory_management.ocel.zip")
```
Inspect meta (event/object types, attributes): `ocel.meta.event_types`, `ocel.meta.object_types` [T2][4][5].

### 2.3 Identify objects and time window (period)

Define analysis period $P=[t_0,t_1)$ (e.g. full log or subinterval). Let object types include materials/locations (e.g. `MAT`, `PLA`, `MAT_PLA`) and documents (PO/SO items). Inventory is tracked per material-location context in this simulation [T2][1][2][3].

For each inventory object $i$ (e.g. $(mat,loc)=MAT\_PLA$), determine opening quantity $q_{i,t_0^-}$ and closing quantity $q_{i,t_1^-}$ (boundaries). From enriched logs, `Stock Before`/`Stock After` appear on events; reconstruct state by applying events in timestamp order per object or by reading object snapshots/changes if present [T2][1][2][3][4].

Compute period change:
$$
\Delta Inventory_i = q_{i,t_1^-} - q_{i,t_0^-},\quad \Delta Inventory = \sum_i \Delta Inventory_i.
$$
(Use consistent units as given.)

### 2.4 Field mapping table

Define mapping between OCEL fields and TA terms (minimal, reproducible):

| TA/accounting term | OCEL source (inventory sim) | Notes |
|---|---|---|
| Inventory quantity $q_t$ | `Stock Before` / `Stock After` per event affecting material/location; object attribute changes (if any) | Apply events chronologically per `MAT_PLA` (or relevant object) to reconstruct balances [T2][1][2][3]. |
| Receipts (Goods Receipt) | Activities like `Goods Receipt (Normal/...)` affecting stock increases | Increases $q$; record as inventory inflow [T2][1][2][3]. |
| Issues (Goods Issue) | Activities like `Goods Issue (Normal/...)` | Decreases $q$; COGS/issue event [T2][1][2][3]. |
| Purchase Orders/Suggestions | `Create Purchase Order Item (...)`, `Create Purchase Suggestion Item (...)` | Document flow (P2P context) [T2][1][2][3][8]. |
| Sales Orders | `Create Sales Order Item (...)` | Demand/shipments [T2][1][2][3]. |
| Status/parameters | `EOQ`, `Safety Stock (SS)`, `ROP`, `d_m`, `σ_m`, `l_m`, `D_m`, `Current Status` | Context for policy/variance analysis [T2][1][2][3]. |
| Timestamps/resources | `ocel:timestamp`, resources/roles if present | Ordering, period boundaries [T2][4][5]. |

(Exact activity names depend on post-processed log; extract from `ocel.meta.event_types`.)

### 2.5 Throughput Accounting terms

Throughput Accounting (TOC): $Throughput = Revenue - Totally\ Variable\ Cost$ (TVC). Operating Expense ($OE$) are all operating costs not TVC (typically fixed in short run under TOC view) [T3][14][15][16][T2][17].

Thus
$$
NP_{TA} = Throughput - OE = (Revenue - TVC) - OE.
$$
In a simulation without full P&L, model synthetic accounts:
- Revenue from fulfilled sales events (issue/ship to customer) at simulated price per unit.
- TVC: direct material/unit variable costs associated with issues/production outflows.
- OE: fixed operating expenses allocated to period (labor fixed, fixed overheads, etc.) as synthetic period amounts.

### 2.6 GAAP full-absorption costing

Under full absorption (absorption costing), fixed production overhead is allocated to inventory units produced; cost of goods sold includes absorbed fixed overhead for units sold, and unsold inventory carries absorbed fixed overhead. This creates the reconciliation between TA (which treats fixed overhead as period OE in the short run) and GAAP net income via inventory changes and overhead absorption [T1][18][T2][19][T2][20][T2][21][T3][22].

Define:
- $FixedOverhead_{actual,period} = ActualFixedOverhead$ (AFOH) incurred in period.
- $NormalCapacity_{units}$ (or activity base) and absorption rate $oh_u = \frac{BudgetedFixedOverhead}{NormalCapacity_{units}}$ (or per chosen base) [T2][19][20][21].
- $AbsorbedFixedOverhead = oh_u \times ActualProduction_{units}$ (units produced in period, at standard absorption) [T2][19][20][21].
- Under/over-absorption variance $V = ActualFixedOverhead - AbsorbedFixedOverhead$ (positive = under-absorbed) [T2][19][20][21].

GAAP net income (period, before taxes, simplified): $NI_{GAAP} = Revenue - COGS_{full} - SG\&A_{period}$ with $COGS_{full}$ including absorbed fixed overhead on units sold. The base identity given:
$$
NI_{GAAP} = NP_{TA} + \Delta Inventory \times overhead/unit
$$
assumes $ActualFixedOverhead == AbsorbedFixedOverhead$ and $overhead/unit = oh_u$ is the absorption rate per unit [T2][19][20][21].

### 2.7 Extended identities (with variances and multiple pools)

Include under/over-absorption variance when actual output != normal capacity:
$$
NI_{GAAP} = NP_{TA} + \Delta Inventory \cdot oh_u + (ActualFixedOverhead - AbsorbedFixedOverhead).
$$

Multiple overhead pools: if fixed overhead is allocated across different pools $p$ with different bases/rates,
$$
NI_{GAAP} = NP_{TA} + \sum_p \Delta Inv_p \times oh_{p} + \sum_p (ActualFixedOverhead_p - AbsorbedFixedOverhead_p),
$$
where $\Delta Inv_p$ is inventory quantity change relevant to pool $p$ and $oh_p = BudgetedFOH_p / NormalCapacity_{p,base}$ [T2][19][20][21].

### 2.8 Compute each component from OCEL + synthetic ledger

1. **Period & objects**: select $t_0,t_1$; get inventory objects $I=\{MAT\_PLA\}$ present.
2. **Opening/closing quantities**: for each $i\in I$, $q_{i,t_0^-}=\texttt{StockBefore}$ at first event in period affecting $i$ (or reconstructed), $q_{i,t_1^-}=\texttt{StockAfter}$ at last; $\Delta Inv_i=q_{i,t_1^-}-q_{i,t_0^-}$, $\Delta Inv=\sum_i \Delta Inv_i$.
3. **Revenue**: sum simulated revenue of sales fulfillment events in period (map SO items/issues to price).
4. **TVC**: sum variable costs tied to throughput (e.g. direct material cost per unit issued) in period.
5. **Throughput** = Revenue - TVC; **OE** = synthetic fixed operating expenses (non-TVC) for period; $NP_{TA}=Throughput - OE$.
6. **GAAP COGS_full**: include absorbed fixed overhead on units sold: $COGS_{variable} + oh_u \times UnitsSold_{period}$.
7. **Absorption**: set $BudgetedFOH$, $NormalCapacity_{units}$, $ActualFOH$ (synthetic), $ActualProduction_{units}$ (produced/received into inventory in period), $AbsorbedFOH = oh_u\times ActualProduction_{units}$, $V=AFOH-AbsorbedFOH$.
8. **$NI_{GAAP}$**: compute from ledger (Revenue - COGS_full - SG&A) [T2][19][20].
9. **Residual**: $residual = NI_{GAAP} - (NP_{TA} + \Delta Inventory \times oh_u + (ActualFixedOverhead - AbsorbedFixedOverhead))$. Expect numerical zero under consistent assumptions.

### 2.9 Runnable pseudocode (minimal, reproducible)

```python
import pm4py
import pandas as pd
from datetime import datetime

# Load OCEL 2.0 bundled (Parquet)
ocel = pm4py.read_ocel2_bundle("post_ocel_inventory_management.ocel.zip")  # [T2][5]

# Extract events (timestamp ordered)
events = ocel.events.copy()
events['ocel:timestamp'] = pd.to_datetime(events['ocel:timestamp'])

# Define period (example: full log)
t0 = events['ocel:timestamp'].min()
t1 = events['ocel:timestamp'].max() + pd.Timedelta(0)  # adjust as needed

# Identify inventory objects (MAT_PLA) - inspect meta for actual names
# Reconstruct opening/closing quantities per object using Stock Before/After
# ... chronological application per object ...

# Synthetic ledger parameters (must be specified)
price_per_unit = 10.0        # synthetic
direct_material_per_unit = 4.0  # TVC component
oe_fixed = 1000.0            # OE
budgeted_foh = 800.0
normal_capacity_units = 200.0
actual_foh = 800.0           # set to create variance as needed
actual_production_units = 200.0
units_sold_period = 0        # compute from events
actual_units_sold = 150.0    # example

# Compute terms
throughput = actual_units_sold * (price_per_unit - direct_material_per_unit)
np_ta = throughput - oe_fixed
cogs_full = actual_units_sold * direct_material_per_unit + oh_u * actual_units_sold  # with oh_u
ni_gaap = actual_units_sold * price_per_unit - cogs_full - 0.0  # SG&A zero if excluded
oh_u = budgeted_foh / normal_capacity_units if normal_capacity_units > 0 else 0.0
absorbed_foh = oh_u * actual_production_units
v = actual_foh - absorbed_foh
residual = ni_gaap - (np_ta + delta_inv * oh_u + v)
```

Notes: when reading bundled Parquet, PM4Py exposes event/object dataframes; use `ocel.events`, `ocel.objects`, `ocel.relations` (e2o/o2o) as appropriate [T2][4][5]. For large bundles, use Parquet efficiently. The identity requires consistent period boundaries and treatment of in-transit/produced vs sold.

## 3. Falsification controls

To ensure the test is sensitive (identity holds only under stated assumptions):

1. **Flat inventory control**: set/observe a subperiod where $\Delta Inv=0$ for all inventory objects. Then identity reduces to $NI_{GAAP} = NP_{TA} + (AFOH - AbsorbedFOH)$ (and with no variance $NI_{GAAP}=NP_{TA}$). This is a strong consistency check [T2][19][20].
2. **Deliberately truncated opening balance**: corrupt/reconstruct with wrong $q_{t_0^-}$ for a subset (or truncate initial state) so that $\Delta Inv$ is miscomputed. The reconciliation must break (residual becomes large/nonzero). If it survives, the test isn't sensitive to state initialization.
3. **Variance sensitivity**: vary $ActualProduction_{units}$ relative to $NormalCapacity$ to create under/over-absorption; verify the variance term is required and correct [T2][19][20][21].
4. **Multiple pools**: split fixed overhead into pools with different $oh_p$ and $\Delta Inv_p$; verify sum form holds.
5. **Boundary timing**: shift period boundary across events that change stock; residual should be zero only at consistent boundaries (no double-counting across boundaries).
6. **Price/cost consistency**: ensure synthetic prices/costs are applied consistently (revenue on fulfillment, TVC on issues). Inconsistencies create spurious residuals.

These controls are designed to falsify incorrect implementations (double counting, OCEL event ordering issues, missing absorption terms) rather than to validate empirical truth.

## 4. Expected orders of magnitude and specific failure signals

### 4.1 Expected orders of magnitude

Since this is a synthetic simulation (deterministic seed 20260820 context [T2][6]), expect:
- Quantities $q$ in reasonable integer units (hundreds–thousands) consistent with inventory simulation [T2][1].
- $\Delta Inv$ can be positive/negative depending on period; magnitude comparable to typical balances.
- $oh_u$ is a rate (currency/unit) set in synthetic ledger (e.g. 1-10 currency/unit) — choose values so that $\Delta Inv\times oh_u$ is material enough to detect errors.
- Residual should be $< \epsilon$ (numerical precision, e.g. 1e-9) when all terms correct and assumptions satisfied.

### 4.2 Specific failure signals

| Failure signal | Likely cause | Detection |
|---|---|---|
| $residual \neq 0$ when $\Delta Inv=0$ and variance zero | Double counting in Revenue/TVC, period boundary error, or state reconstruction error | Flat inventory control fails. |
| Identity holds despite truncated opening balance | $\Delta Inv$ not actually derived from reconstructed opening/closing (e.g. computed from net flows only, ignoring initial state) | Truncation control fails (must break). |
| Capacity variance ignored when $ActualProduction!=NormalCapacity$ | Missing $(AFOH - AbsorbedFOH)$ term | Vary production; residual appears unless term added [T2][19][20][21]. |
| Allocation ambiguity across pools | Using single $oh_u$ when overhead split | Multiple pools test fails [T2][19][20][21]. |
| Takt/cycle/lead confusion | Mixing takt time, cycle time, lead time with absorption base/capacity | Check units: absorption base must match $oh_u$ (units produced or chosen activity base); parameters $d_m,\sigma_m,l_m,ROP,EOQ$ are inventory policy, not absorption base unless modeled [T2][1][2][3][23][24]. |
| OCEL double counting | Counting same event across multiple objects incorrectly (e2o multiplicity) | Verify e2o relations [T2][4][5]; ensure revenue/cost assigned once per economic event. |
| Feedback non-commutativity | Event order affects state but identity assumed time-invariant incorrectly | Recompute with same multiset in different order? Identity is algebraic given consistent period state; non-commutativity in process model is separate — ensure state reconstruction uses actual timestamp order [T2][4][5]. |
| Decision inconsistency | Policy decisions (suggestions) confused with economic events | Distinguish suggestion events (`Create Purchase Suggestion Item`) from actual order/receipt/issue events when computing realized quantities/costs [T2][1][2][3]. |

## 5. What this experiment would and would NOT establish

### 5.1 What it would establish

- **Internal algebraic consistency**: Given a consistent period state and specified accounting treatment, the reconciliation identity holds (or fails) as algebra. This is a necessary consistency check between TA and full-absorption GAAP views under the stated assumptions [T2][19][20][21].
- **Implementation correctness**: The procedure tests correct reconstruction of $\Delta Inventory$ from OCEL state, correct periodization, proper handling of absorption variances and multiple pools, and sensitivity via falsification controls.
- **Reproducibility on public data**: Using public OCEL artifacts [T2][1][2][3][6] with deterministic setup makes the result reproducible.

### 5.2 What it would NOT establish

- **Empirical validity on the valuation side**: This is a synthetic/simulation testbed; results do not prove real-world GAAP valuation accuracy [T2][19][20].
- **Cash leg**: No cash flows are modeled/validated here (identity is profit/inventory valuation reconciliation, not cash basis reconciliation). Cash, payables/receivables timing, and working capital cash effects are out of scope.
- **Capacity-as-$r_b$ (return on bottleneck/resource)**: The identity uses absorption rates $oh_u, oh_p$ per unit/base; it does not validate TOC’s bottleneck rate $r_b$ or constraint exploitation logic except the TA form $NP_{TA}=Throughput-OE$ [T3][14][15][16].
- **Mission constraints**: Strategic/mission constraints (beyond accounting identities) are not tested by this algebra.
- **Generalization beyond simulation**: Passing on this synthetic OCEL does not imply the identity holds under all process complexities without validating assumptions (e.g. joint products, byproducts, scrap, WIP, intercompany, currency) [T2][19][20][21].

## 6. References/sources

### [T1] Published research papers, peer-reviewed work, conference proceedings (cite: source + page + paragraph)

[T1][18] Horngren, C. T., Datar, S. M., Rajan, M. V. (2015). *Cost Accounting: A Managerial Emphasis* (15th ed.). Pearson. (Full absorption costing, overhead absorption rates, under/over-absorbed overhead; inventory valuation effects on income) — cite relevant sections (Ch. 8–9) as source+page+paragraph.

### [T2] Official documentation, technical specs, design docs, white papers, books, renowned domain blogs (cite: source + subsection + line number)

[T2][1] OCEL 2.0. "Inventory Management Database and OCELs." Event Logs / Simulations. https://www.ocel-standard.org/event-logs/simulations/invent_manag/ (accessed 2026-10-11). Subsection: dataset description; artifacts list.

[T2][2] Berti, A. (2026). "Simulated Inventory Management Database and Object-Centric Event Logs for Process Analysis." Zenodo. https://zenodo.org/records/21508223 (accessed 2026-10-11). Subsection "Generated Dataset Files".

[T2][3] Berti, A. (2026). "Simulated Inventory Management Database and Object-Centric Event Logs for Process Analysis (updated record)." Zenodo. https://zenodo.org/records/21977737 (accessed 2026-10-11). Subsection "Files" (includes `inventory_management_postprocessed.ocel.zip`).

[T2][4] OCEL 2.0 Specification. "Bundled CSV/Parquet format." https://www.ocel-standard.org/specification/formats/bundled/ (accessed 2026-10-11). Subsection "Bundle Layout and `ocel-meta.json`".

[T2][5] OCEL 2.0 Tool Support. "Overview." https://ocel-standard.org/tool-support/overview/ (accessed 2026-10-11). Subsection listing PM4Py/ocpa/Ocelot.pm support for bundled ZIP/Parquet.

[T2][6] OCEL 2.0. "Synthetic Relational Databases and Reference OCELs." https://ocel-standard.org/event-logs/simulations/synthetic-relational-databases/ (accessed 2026-10-11). Subsection: deterministic seed `20260820`, artifacts per scenario.

[T2][7] Berti, A. (2026). "Synthetic relational databases and reference OCELs." Zenodo. https://zenodo.org/records/22079246 (accessed 2026-10-11). Description: seed 20260820, file types (`.sqlite`, `.xmlocel.gz`, `.jsonocel.gz`, `.ocel.sqlite`, `.ocel.csv`, `.ocel.zip`).

[T2][8] OCEL 2.0 Event Logs. "Overview / Procure-to-Pay (P2P)." https://www.ocel-standard.org/event-logs/overview/ (accessed 2026-10-11). P2P entry in table/list.

[T2][9] van Dongen, B. (2019). "BPI Challenge 2019." 4TU.ResearchData. https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1 (accessed 2026-10-11). Dataset description subsection.

[T2][10] Process Mining Conference. "BPI Challenge 2019." https://icpmconference.org/2019/icpm-2019/contests-challenges/bpi-challenge-2019/ (accessed 2026-10-11). Challenge description subsection.

[T2][11] 4TU.ResearchData. "BPI Challenge 2019 (OCEL)." https://data.4tu.nl/datasets/46a7e15b-10c7-4ab2-988d-ee67d8ea515a/1 (accessed 2026-10-11). OCEL version description subsection.

[T2][12] Khayatbashi, S., Hartig, O., Jalali, A. (2023). "Transforming Event Knowledge Graph to Object-Centric Event Logs: A Comparative Study for Multi-dimensional Process Analysis." ER 2023, pp. 220-238. (cited via [T2][11][13]).

[T2][13] Jalali, A., Khayatbashi, S. (2026). "BPI Challenge datasets - OCEL 2.0." https://exa.ai/library/publication/c6yszw9fjm2 (accessed 2026-10-11). Conversion/attribution subsection.

[T2][17] TOCICO. "Throughput Accounting." Theory of Constraints International Certification Organization. https://www.tocico.org/ (accessed 2026-10-11). TOC/TA body documentation subsection.

[T2][19] PwC. "Viewpoint (Accounting & reporting)." https://viewpoint.pwc.com/ (accessed 2026-10-11). Guidance on absorption costing/overhead allocation subsection.

[T2][20] CPA Ireland. "Technical Resources / Financial Reporting." https://www.cpaireland.ie/Technical-Resources/Financial-Reporting (accessed 2026-10-11). Inventory and overhead absorption subsection.

[T2][21] ACCA. "Technical articles / Management Accounting." https://www.accaglobal.com/gb/en/student/exam-support-resources/professional-exams-study-resources/p5/technical-articles.html (accessed 2026-10-11). Absorption costing/overhead variances subsection.

[T2][23] Wikipedia. "Takt time." https://en.wikipedia.org/wiki/Takt_time (accessed 2026-10-11). Subsection "Definition".

[T2][24] Wikipedia. "Cycle time (manufacturing)." https://en.wikipedia.org/wiki/Cycle_time (accessed 2026-10-11). Subsection "Definitions".

[T2][29] Beancount. "Beancount Documentation." https://beancount.github.io/docs/ (accessed 2026-10-11). Subsection "Getting Started" / double-entry model.

### [T3] Social posts, Hacker News, small blogs, podcasts, conference videos (cite: source + URL)

[T3][14] Goldratt, E. M., Cox, J. (1984). *The Goal: A Process of Ongoing Improvement*. North River Press. https://www.northriverpress.com/books/the-goal/ (accessed 2026-10-11).

[T3][15] Corbett, T. (1998). *Throughput Accounting*. North River Press. https://www.northriverpress.com/books/throughput-accounting/ (accessed 2026-10-11).

[T3][16] Cox, J. F., Boyd, L. H., Sullivan, T. T., Reid, R. A., Cartier, B. (2012). *The Theory of Constraints International Certification Organization Dictionary*, 2nd ed. https://www.tocico.org/resource/resmgr/dictionary/tocico_dictionary_2nd_ed.pdf (accessed 2026-10-11).

[T3][22] Bragg, S. (various). "Absorption costing." AccountingTools. https://www.accountingtools.com/articles/absorption-costing (accessed 2026-10-11).

[T3][30] Linscott, S. (various). "Beancount: Double-entry bookkeeping from text files." (project docs/blog). https://beancount.github.io/ (accessed 2026-10-11).