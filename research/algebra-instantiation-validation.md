# Instantiating and Validating the Transformation Algebra on Real Event Logs

## Scope and framing

The transformation-algebra programme treats a business as a graph of stocks, transformations, and constraints that convert inputs into sellable outputs. The algebra proposes quantitative links between stocks, transformation yields, cycle times, capacity, unit economics, and cash, plus a reconciliation identity relating GAAP net income to throughput-accounting profit:

> **NI_GAAP = NP_TA + ΔInventory × overhead/unit**

where `NP_TA = Throughput − Operating Expense`, `ΔInventory` is the change in inventory quantity, and `overhead/unit` is the fixed production overhead absorbed per unit under full-absorption (GAAP) costing. This identity is exactly the classic absorption-vs-variable-costing reconciliation: the only reason the two profit figures differ is that absorption costing capitalises a slice of fixed overhead into inventory, so the difference equals the change in inventory units multiplied by the fixed overhead rate per unit [T2] (CPA Ireland, F2 Management Accounting, "Reconciliation of profit figures", worked example) [T3] (Reference for Business, "Absorption Accounting", Tables 2–3).

The task of this document is to move that identity from construction to test. It surveys (1) the object-centric event-log machinery that can supply the algebra's primitives, (2) which public data actually exist and are usable, (3) a concrete instantiation mapping one log onto the algebra with runnable equations, (4) where the mapping breaks, and (5) what cannot be validated at all.

## 1. State of the art: object-centric event logs and process mining

### 1.1 From XES to OCEL 2.0

Classical process mining assumes one case notion per event ("each event refers to precisely one object") [T1] (van der Aalst, *Object-Centric Process Mining: An Introduction*, Springer 2021, §1). Real ERP data violate this: forcing a single case produces convergence (event duplication) and divergence (inability to separate events within a case) [T1] (van der Aalst, *Dealing with Divergence and Convergence*, Springer 2019, abstract).

Object-centric event logs (OCEL) resolve this. OCEL 1.0 was released in 2020 and enabled a family of OCPM techniques; OCEL 2.0, dated 16 October 2023, is the current standard and adds object-to-object relations, qualified relations, and evolving object attribute values [T2] (OCEL 2.0 Specification, "Abstract" and §1, lines 1–20). Formally an OCEL is the tuple

`L = (E, O, EA, OA, evtype, time, objtype, eatype, oatype, eaval, oaval, E2O, O2O)`

with events `E`, objects `O`, a timestamp function `time`, event/object type maps, event- and object-attribute values, event-to-object relations `E2O`, and object-to-object relations `O2O` [T1] (Berti et al., "OCEL (Object-Centric Event Log) 2.0 Specification," arXiv:2403.01975, §4 "Formal Definitions," Definition 2). The standard ships three normative exchange serialisations — relational SQLite, XML, and JSON — plus a bundled typed-Parquet ZIP in the 2.1 revision [T2] (OCEL 2.0 Specification, validation schemes block, and ocel-standard.org event-logs).

For the algebra this matters directly. `O2O` is the graph edge set; `E2O` is the incidence relation between transformations (events) and the assets/objects they act on; evolving object attributes (`oaval`) are precisely how **stock levels** can be tracked over time [T1] (arXiv:2403.01975, §4–5, Tables 1–2).

### 1.2 Performance measures: the timing primitives

Process mining supplies the timing vocabulary the algebra needs. Standard definitions distinguish **waiting time** (time in queues before an activity), **service time** (execution duration), and **sojourn time** (waiting + service) [T1] (Park, Adams & van der Aalst, "OPerA: Object-Centric Performance Analysis," arXiv:2204.10662, §1 and §4.2). Lean/manufacturing uses a partially overlapping vocabulary — **processing time**, **wait time**, **cycle time**, and **takt time** (available time ÷ customer demand) — and warns that these are locally defined and often confused [T2] (MIT OpenCourseWare 16.660J, *Lean Thinking Part II*, slides 2–12).

The key OCPM contribution is that flattening a multi-object log yields **misleading waiting times** [T1] (OPerA, §1: "may yield misleading or even incorrect insights on performance metrics such as waiting time"). OPerA therefore introduces object-interaction measures: **synchronization time** (time to bring interacting objects together), decomposed into **pooling time** (time to collect all objects of one type) and **lagging time** (delay caused by one type arriving late), and defines **flow time = sojourn time + synchronization time** [T1] (OPerA, §1 and §4.2, equations for `synch`, `pool`, `lag`, `flow`). This is the correct substrate for a transformation's **cycle time** when the transformation consumes multiple input objects.

Finally, the throughput/WIP/cycle-time relation at the algebra's heart is **Little's Law**: `WIP = Throughput × Cycle Time`, valid under steady state for a station, line, or plant [T1] (Little, "Little's Law as Viewed on Its 50th Anniversary," *Operations Research* 59(3), 2011, p. 540, eq. TH = WIP/CT) [T2] (MIT OCW 16.660J, slide 13). Hopp & Spearman's *Factory Physics* add the bottleneck rate `r_b`, raw process time `T_0`, and critical WIP `W_0 = r_b·T_0`, which is what "capacity" must mean in the algebra [T2] (Hopp & Spearman, *Factory Physics*, lecture handout, "Basic Factory Dynamics", Laws 1–3).

### 1.3 Conformance checking: is the graph the one that ran?

Conformance checking compares observed behaviour to a model and is the tool that decides whether an instantiated graph is faithful [T1] (Carmona, van Dongen, Solti & Weidlich, *Conformance Checking*, Springer 2018). The state of the art is **alignments**, which compute an optimal sequence of synchronous/log/model-only moves and yield a fitness/rework diagnosis rather than a bare yes/no [T2] (van der Aalst, *Process Mining: Data Science in Action*, 2nd ed., 2016, Ch. 7, pp. 243–274). Object-centric **alignments** generalise this to graphs of moves across interacting sub-processes [T1] (Liß, Adams & van der Aalst, "Object-Centric Alignments," RWTH 2023, abstract, §8). Replay-based fitness and precision for OCELs are implemented via token-based replay on object-centric Petri nets [T1] (Berti & van der Aalst, *ToPNoC* 15, 2021) [T2] (ocpa README, "Object-centric conformance checking").

### 1.4 Tooling

- **PM4Py** (Python) supports OCEL import/export across XML/JSON/SQLite, `discover_ocpn` (object-centric Petri nets), `discover_ocdfg` (object-centric directly-follows graphs), and object-centric conformance and performance routines [T2] (PM4Py docs, `pm4py.objects.ocel` and `pm4py.discovery.discover_ocpn`, ref. van der Aalst & Berti, "Discovering Object-Centric Petri Nets," *Fundamenta Informaticae* 175, 2020). The release notes fix a previously "incorrectly calculating cycle time and waiting time" bug, a caution for anyone building on timing measures [T2] (PM4Py GitHub releases, changelog line "Incorrectly calculating cycle time and waiting time").
- **ocpa** (Python) provides OCEL management, discovery, conformance, and explicitly the OPerA metrics — lagging, pooling, synchronization, and flow time [T2] (ocpa GitHub README, "Performance Analysis").
- **OPerA** is a standalone interactive tool for object-centric performance analysis (token replay + OCPN visualisation) [T1] (OPerA, arXiv:2204.10662) [T2] (github.com/gyunamister/OPerA, README).
- **Celonis** is the dominant commercial platform. Its Process Sphere product (Celosphere 2022) was "the first commercially available solution that fully embraces object-centric process mining," including measuring average throughput time *between two selected event types* [T1] (van der Aalst, vdaalst.com p1353, Fig. 9) [T2] (Celonis press release, "New Process Mining Innovations," Object-Centric Data Model). Celonis also ships an object-centric Accounts Payable Starter Kit with working-capital KPIs such as Days Payable Outstanding and Cash Discount Ratio [T2] (Celonis docs, "Accounts Payable Starter Kit – object-centric").

## 2. Usable datasets for instantiation

### 2.1 BPI Challenge logs

The IEEE Task Force and 4TU.ResearchData publish the canonical BPI Challenge logs:

| Log | Domain | Size (traces / events) | Licence |
|---|---|---|---|
| BPIC12 | Loan application, Dutch bank | 13,087 / 262,200 | 4TU terms [T2] |
| BPIC13a/b/c | Incident / problem mgmt | 1,487 / 6,660 etc. | 4TU terms [T2] |
| BPIC14 | ITIL change mgmt (Rabobank) | CSV case files | 4TU terms [T2] |
| BPIC15 (1–5) | Municipality permits | ~832–1,409 cases each | 4TU terms [T2] |
| BPIC16 | Customer clicks / messages | CSV | 4TU terms [T2] |
| BPIC17 | Loan application (offers) | 31,509 / 1,202,267 | 4TU terms [T2] |
| BPIC18 | Agricultural CAP payments | XES | 4TU terms [T2] |
| BPIC19 | Purchase-order handling | 251,734 cases / 1,595,923 events, 42 activities, 627 users | **CC BY 4.0** [T2] |
| BPIC20 | Travel permits (4 sub-logs) | 6,886–10,500 cases per sub-log | 4TU terms [T2] |

Sources: IEEE Task Force "Real-life logs" page (trace/event counts for BPIC12–17) [T2]; 4TU.ResearchData dataset pages for BPIC17, BPIC19, and the BPIC2014 collection [T2]; the ICPM 2020 BPI Challenge page for BPIC20 sub-log statistics (RequestForPayment 6,886 cases/36,796 events; Domestic 10,500/56,437; Prepaid 2,099/18,246; International 6,449/72,151) [T2].

Practical usability: BPIC19 is the friendliest for the algebra because it is CC BY 4.0 and is a genuine three-way-match P2P process with monetary amounts (invoices, goods receipts, payments) [T2] (4TU BPI Challenge 2019, "Interoperability" and licence fields). BPIC17 is the largest event-wise but is loan-oriented and has no inventory. Crucially, **none of the BPI logs carries inventory stock levels or a general ledger**; they carry time-stamped activities and some monetary attributes. They can instantiate the algebra's *time* and *flow* primitives but not its *stock valuation* primitives without an attached financial layer.

### 2.2 The OCEL 2.0 curated repository

The ocel-standard.org "Event Logs" catalogue is the highest-value resource for this specific task. It classifies logs as **Simulations** and **Real-World** [T2] (ocel-standard.org/event-logs/overview). Two are tailor-made for the algebra:

- **Inventory Management Database and OCELs** — a Python-generated SQLite database plus OCELs in CSV, XML, JSON, SQLite, and Parquet ZIP. It tracks `Materials`, `PurchaseOrderItems`, `SalesOrderItems`, `GoodsReceiptsAndIssues`, `MaterialStocks`, and `OrderSuggestions`; emits `Stock Before`/`Stock After` per event; and enriches events with EOQ `√(2DS/H)`, Safety Stock `z·σ·√l`, Reorder Point `d·l + SS`, and status transitions (Understock/Normal/Overstock) [T2] (ocel-standard.org, "Inventory Management Database and OCELs," *Abstract*, *Contents* `04_postprocess_activities.py`, equations). This log supplies genuine **stocks, inflows (Goods Receipt), and outflows (Goods Issue)** — the core of the algebra.
- **Synthetic Relational Databases and Reference OCELs** — six deterministic synthetic source databases (ForgeFlow engineer-to-order, TrialVersion, ProcureChange, ClaimStream, PermitFlow, BatteryVault), each with a reference OCEL in all five serialisations, generated with fixed seed `20260820`, plus `validation.json` and `SHA256SUMS` [T2] (ocel-standard.org, "Synthetic Relational Databases and Reference OCELs," *Description*, *Scenarios*, *Files*). Because they are deterministic and come with machine-readable validation results, they are the best substrate for **reproducible** reconciliation experiments.
- **Procure-to-Pay (P2P)** and **Order Management** simulations, and real-world **Angular GitHub Commits**, **Ethereum Blockchain**, **Enron Email**, and **German Bundestag** logs round out the set [T2] (ocel-standard.org/event-logs/overview).

### 2.3 ERP / financial extract and ledger datasets

- **Compustat / CRSP / CRSP-Compustat Merged** provide fundamental income-statement, balance-sheet, and cash-flow items plus market data, but are subscription-gated and licence-restricted: data is for the subscriber's internal/academic use only, may not be installed on personal systems, and cannot be redistributed [T2] (CRSP "Policies & Statements"; CRSP-Compustat Merged Database product page; UCSD CRSP licence agreement, Article 1.2/1.9). They are excellent for *validating the financial side at firm-period granularity* but cannot be joined to any public event log and cannot be republished in a paper's appendix.
- **SAP SALT** (Sales Autocompletion Linked Business Tables, 2025) is described as the "first real ERP dataset," anonymised interconnected sales tables released on Hugging Face and GitHub for research [T2]/[T3] (SAP News Center, 14 Apr 2025). It is permissively usable but sales-order-centric and ships no full double-entry ledger.
- **OECD** and national statistical datasets are open but report aggregates, not transactions.
- **Synthetic double-entry generators**: Beancount is a plain-text double-entry language whose core model is `Assets + Expenses + Liabilities + Income + Equity = 0`, with `realization.py` computing per-account balances [T2] (Beancount `core/docs.md`; beancount.io docs). `double-entry-generator` converts bank statements to balanced entries [T2] (deb-sig/double-entry-generator repo). A peer-reviewed **synthetic journal-entry dataset** (two fiscal years, probabilistic, seeded with problematic entries) exists for audit experiments [T1] (Gronewald et al., SSRN 7211804, abstract).

The practical conclusion: **no single public dataset contains both an OCEL and a full general ledger.** Instantiation therefore requires either (a) the inventory-simulation OCEL augmented with a synthetic cost layer, or (b) a synthetic double-entry ledger with an appended event layer.

## 3. Concrete instantiation exercise

### 3.1 Target

Instantiate the algebra on the **OCEL 2.0 Inventory Management log** (supplemented, for the identity test only, by a synthetic fixed-overhead layer), because it is the only public OCEL that emits stocks *and* flows *and* carries lead-time and order-cost parameters [T2] (ocel-standard.org, Inventory Management page). Treat one `MAT_PLA` (material-plant) as the transformation node.

### 3.2 Mapping table

| Algebra quantity | OCEL element / field | Computation from the log |
|---|---|---|
| Asset (stock) | object type `MAT`/`MAT_PLA`; attribute `Stock After` | `S_t = Stock After` at event `t`; balance-sheet stock = last value in period |
| Flow in | event `Goods Receipt` on `PO_ITEM` | `in_qty = Σ quantity`, per period |
| Flow out (sold) | event `Goods Issue` on `SO_ITEM` | `out_qty = Σ quantity`, per period |
| Transformation yield | ratio of `SO_ITEM` completed to inputs consumed | `yield = Σ out / Σ in` |
| Cycle time | `SO_ITEM`: first `Create Sales Order Item` → `Goods Issue` | sojourn time via PM4Py/OPerA; add synchronization time if inputs pooled [T1] |
| Lead time (PO) | `PO_ITEM`: `Create PO Item` → `Goods Receipt` | `l_m` used in EOQ/ROP [T2] |
| Capacity | bottleneck rate `r_b` at `PLA` | `max observed outflow/day`; else `r_b` from `W_0 = r_b·T_0` [T2] |
| WIP | `PO_ITEM`/`SO_ITEM` open (created but not completed) | Little's Law `WIP = TH × CT` [T1] |
| Unit economics | `OrderSuggestions`/item attributes: price, order cost `S`, holding cost `H` | gross margin `= p − m` (TVC); EOQ `√(2DS/H)` [T2] |
| Cash | **absent** — attach synthetic GL | `cash_t = cash_{t-1} + receipts − payments` |
| Overhead/unit | **absent** — attach synthetic period overhead | `oh_u = FixedOverhead / NormalCapacityUnits` [T2] |

### 3.3 Equations (runnable form, per period `[t_0, t_1]`)

Throughput (TOC/throughput-accounting definition, where throughput is sales minus totally-variable cost): [T2] (Wikipedia, "Theory of constraints," Throughput accounting section) [T3] (CPA Journal, "the cpa in industry", Throughput Accounting)

```
T          = Σ_{Goods Issue events} (price_per_unit − TVC_per_unit)
OE         = fixed period costs (labour, SG&A, rent)
NP_TA      = T − OE
ΔInv_units = StockAfter(t_1) − StockAfter(t_0)          # from the log
oh_u       = FixedProductionOverhead / NormalCapacityUnits   # PwC normal-capacity rule [T2]
ΔInv_val   = ΔInv_units × oh_u                          # overhead capitalised into stock
NI_GAAP    = NP_TA + ΔInv_val                           # the identity to test
```

Fixed overhead must be allocated on **normal capacity** for GAAP full-absorption costing, not on actual output [T2] (PwC Viewpoint, "1.4 Full absorption costing": fixed overhead "based on the 'normal capacity' of the production facilities").

### 3.4 End-to-end test protocol

1. **Extract.** Load `post_ocel_inventory_management.ocel.zip` with PM4Py; recover `Stock After` per `MAT_PLA` event and the `Goods Receipt`/`Goods Issue` events [T2] (PM4Py Ocel importer).
2. **Reconstruct stocks independently.** Recompute `S_t` from flows only: `S_t = S_{t_0} + Σ in − Σ out`, and assert equality with the logged `Stock After` for every event. This is a *conformance test on the stock equation*; any mismatch means the log is incomplete.
3. **Compute throughput and cycle time.** Use `ocpa`/OPerA for sojourn and synchronization times on `SO_ITEM`; aggregate to the period [T1] (OPerA §4.2) [T2] (ocpa README).
4. **Attach a minimal GL.** Generate a synthetic double-entry layer (Beancount) that books: material purchases (Dr Inventory / Cr Cash), cost of goods sold at TVC, fixed overhead to a production-cost pool, and absorption of `oh_u` per produced unit into Inventory [T2] (Beancount docs).
5. **Compute both profits.** `NP_TA` from the event layer; `NI_GAAP` from the Beancount realisation (which nets the absorbed overhead).
6. **Test.** Compute `residual = NI_GAAP − (NP_TA + ΔInv_units × oh_u)`. The identity holds iff `|residual| < ε` where `ε` covers rounding and any capacity variance. Report the residual, not a pass/fail.
7. **Falsification controls.** Repeat with (a) inventory held flat across the boundary (ΔInv = 0 ⇒ the two profits must be equal) and (b) deliberately injected opening-balance truncation (identity must break). If the identity survives (b), the test is not sensitive.

### 3.5 Required fields

Minimum: (i) per-event timestamp; (ii) an object id + type for each stock (`MAT_PLA`); (iii) signed quantity per stock-changing event; (iv) initial stock balance; (v) price and TVC per unit; (vi) fixed overhead and normal capacity; (vii) opening and closing period boundaries. (i)–(iv) exist in the inventory OCEL; (v)–(vii) must be attached.

## 4. What breaks

**4.1 Valuation: GAAP absorption vs throughput valuation.** Throughput accounting carries inventory at totally-variable cost only; absorption costing carries a slice of fixed overhead [T2] (TOCICO, "Back to Basics: Throughput Accounting," Inventory valuation slides) [T3] (CPA Journal). The clean identity holds **only when inventory is valued at exactly `oh_u` and there is no capacity variance**. If actual output ≠ normal capacity, GAAP books an under/over-absorption variance and the identity gains a term: `NI_GAAP = NP_TA + ΔInv·oh_u + (ActualFixedOverhead − AbsorbedFixedOverhead)` [T2] (CPA Ireland F2, "Working 3: Under/over absorbed fixed production overhead"). The residual is therefore not noise; it is the variance.

**4.2 Allocation vs driver rates.** `oh_u` presupposes a single overhead pool. Real systems use multiple pools and activity-based rates, so no scalar `overhead/unit` exists; the identity must become a **sum over pools**, `Σ_p ΔInv_p × oh_p`, requiring per-stock overhead attribution that the event log does not carry.

**4.3 Time semantics: takt vs cycle vs lead.** "Cycle time" in lean means processing + wait time, "lead time" is the total product traversal, and "takt time" is demand-driven; the same word means different things in different shops [T2] (MIT OCW 16.660J, slides 3–12; Lean Enterprise Institute lexicon). OPerA shows flattening produces *misleading* waiting times, so a naive `Create→Complete` duration is not the object-centric cycle time [T1] (OPerA §1). Little's Law is only valid in steady state [T1] (Little 2011, p. 540) [T2] (Factory Physics handout). Any yield-per-cycle coefficient is thus period- and regime-dependent; the algebra's cycle-time parameter is not a constant.

**4.4 Double counting.** In an OCEL one event relates to many objects, so summing "units" across object types massively overcounts. The canonical example: `place order` occurs 2,000 times in the order model but 6,000 times in the item model, and `create package` 6,000 times for items but 3,000 for packages [T1] (van der Aalst, ICPM keynote, "Lifting Process Discovery…", §3, "Check object flows" and Fig. 3–4). Throughput must be counted on a **single primary case notion** (the sellable output object), not by iterating all objects.

**4.5 Rework and feedback loops.** Feedback edges inflate event counts and costs and corrupt yields. Token-based replay and object-centric alignments are the standard detectors of rework and non-conforming paths [T1] (Liß et al., Object-Centric Alignments, §1–2) [T2] (ocpa README, "Constraint monitoring"). Composition under feedback is generally **non-commutative**: series yields multiply, parallel yields add subject to capacity split, and a loop both consumes capacity and re-absorbs overhead, which can change the optimal composition.

**4.6 Decision inconsistency.** TOC product-mix decisions rank on **throughput per unit of the constraint** (e.g. $/bottleneck-minute), whereas GAAP ranks on fully absorbed unit cost; the two give different answers, and mixing them makes composition decision-inconsistent [T2] (CPA Journal, "$5/15 min" example; ACCA F5 throughput notes). The algebra must declare which valuation it composes with.

**4.7 Minimum data per equation.** Little's Law (`WIP = TH × CT`) needs all three, or two plus steady state. Yield needs an input count and an output count on the *same* case notion. The reconciliation additionally needs a monetary layer and a normal-capacity figure — neither exists in any public OCEL.

## 5. What could not be validated, and why

- **The cash leg.** No public event log ships a general ledger, so `Receipts/Payments/Cash` (and therefore a cash-flow or DPO identity) cannot be validated end-to-end on real data; it can only be tested on a synthetic Beancount layer, which proves internal consistency, not empirical validity.
- **Capacity as `r_b`.** BPI logs contain no declared capacity; `r_b` can only be *inferred* as a max-observed rate, which conflates capacity with demand. Synthetic logs declare normal capacity, so the identity is testable there but tautologically so.
- **Exact absorption with real capacity variance.** The simple `NI_GAAP = NP_TA + ΔInv·oh_u` form cannot be validated on any real dataset because real production runs off normal capacity and produces a variance term that must be modelled explicitly [T2] (PwC; CPA Ireland).
- **Mission/values/brand constraints.** The qualitative constraints of the model are not encoded in any event log and have no machine-checkable ground truth; they remain unvalidated by construction.
- **Composition decision-consistency.** No public dataset contains a ground-truth optimal decision against which series/parallel/feedback composition can be scored; only internal consistency (does the algebra reproduce itself under permutation of equivalent graphs) can be tested.
- **Statistical generalisability.** A single OCEL is a single trajectory. Claims that a yield or cycle-time coefficient is stable require replicated runs; deterministic synthetic logs (seed `20260820`) permit replication, but real BPI logs do not [T2] (ocel-standard.org synthetic relational DBs, fixed seed).

The honest state of play: the **timing and flow** half of the algebra is instantiable and partly testable today on public OCELs (the inventory simulation and the deterministic synthetic databases); the **valuation and reconciliation** half is testable only against a synthetic double-entry layer, and even then only its variance-free special case. The identity is best treated as a *diagnostic* that surfaces absorption variances, not as an equality that holds on raw event data.

## References / sources

**Type 1 — research papers / peer-reviewed**
- Berti, A., Koren, I., Adams, J.N., et al. "OCEL (Object-Centric Event Log) 2.0 Specification." arXiv:2403.01975, 2024. §4 Definition 2; §5 Running Example, Tables 1–2. [T1]
- van der Aalst, W.M.P. *Object-Centric Process Mining: An Introduction.* Springer/ICTAC 2021, pp. 73–105, §1. [T1]
- van der Aalst, W.M.P. "Object-Centric Process Mining: Dealing with Divergence and Convergence in Event Data." SEFM 2019, abstract. [T1]
- Park, G., Adams, J.N., van der Aalst, W.M.P. "OPerA: Object-Centric Performance Analysis." arXiv:2204.10662, 2022, §1, §4.2. [T1]
- Little, J.D.C. "Little's Law as Viewed on Its 50th Anniversary." *Operations Research* 59(3), 2011, p. 540. [T1]
- Liß, L., Adams, J.N., van der Aalst, W.M.P. "Object-Centric Alignments." RWTH Aachen, 2023, abstract, §8. [T1]
- Berti, A., van der Aalst, W.M.P. "A Novel Token-Based Replay Technique…" *ToPNoC* 15, 2021, pp. 1–26. [T1]
- van der Aalst, W.M.P., Berti, A. "Discovering Object-Centric Petri Nets." *Fundamenta Informaticae* 175(1–4), 2020. [T1]
- van der Aalst, W.M.P. "Lifting Process Discovery and Conformance Checking…" ICPM keynote, CEUR Vol-3730, 2024, §3, Fig. 3–4. [T1]
- Gronewald, J., Stephan, S., Rombach, A., Fettke, P. "Generating Synthetic Journal Entries for Audit Analytics: Method and Dataset." SSRN 7211804, 2026, abstract. [T1]
- van der Aalst, W.M.P. "Object-Centric Process Mining." vdaalst.com p1353, "Meet Process Sphere", Fig. 9. [T1]

**Type 2 — standards, official docs, white papers, books**
- OCEL 2.0 Specification, v2.0, 16 Oct 2023, ocel-standard.org/2.0/ocel20_specification.pdf, abstract and §1. [T2]
- ocel-standard.org — "Event Logs" overview; "Inventory Management Database and OCELs"; "Synthetic Relational Databases and Reference OCELs." [T2]
- PM4Py documentation — `pm4py.objects.ocel`, `pm4py.discovery.discover_ocpn`, `discover_ocdfg`; GitHub release changelog ("Incorrectly calculating cycle time and waiting time"). [T2]
- ocpa library, github.com/ocpm/ocpa, README ("Performance Analysis"). [T2]
- OPerA tool, github.com/gyunamister/OPerA, README. [T2]
- Celonis docs — "Accounts Payable Starter Kit – object-centric"; Celonis press release "Celonis Launches New Process Mining Innovations" (Object-Centric Data Model); celonis.com/process-mining. [T2]
- IEEE Task Force on Process Mining, "Real-life logs"; "BPI Challenge 2020." [T2]
- 4TU.ResearchData — BPI Challenge 2017, 2019 (CC BY 4.0), 2014 collection. [T2]
- CRSP "Policies & Statements"; CRSP/Compustat Merged Database page; UCSD CRSP licence agreement Art. 1.2/1.9. [T2]
- SAP News Center, "SAP Publishes First Real ERP Dataset…" (SALT), 14 Apr 2025. [T2]
- Beancount, github.com/beancount/beancount, `core/docs.md`; beancount.io "Introduction"; deb-sig/double-entry-generator. [T2]
- van der Aalst, W.M.P. *Process Mining: Data Science in Action*, 2nd ed., Springer 2016, Ch. 7, pp. 243–274. [T2]
- PwC Viewpoint, *Inventory Guide* §1.4 "Full absorption costing," 31 May 2024. [T2]
- CPA Ireland, F2 Management Accounting, "Absorption Costing and Marginal Costing." [T2]
- MIT OpenCourseWare 16.660J, *Lean Thinking Part II*, slides 2–13; Hopp & Spearman, *Factory Physics*, Laws 1–3. [T2]
- TOCICO, "Back to Basics TOC: Throughput Accounting," 2018 webinar; ACCA F5, "Throughput accounting"; Wikipedia, "Theory of constraints." [T2]

**Type 3 — small blogs, magazines, community**
- Reference for Business, "Absorption Accounting," Tables 2–3. [T3]
- The CPA Journal, "the cpa in industry" (throughput accounting), archives.cpajournal.com/1997/0197. [T3]
- Stanwick, "Factory Physics — the laws of nature behind WIP…", stanwick.be, 2026. [T3]
