# Designing and Building a Seeded Enterprise Simulator as the Evaluation Testbed for a Business-Graph Harness

## Scope and framing

An agentic business-graph harness needs a mechanistic testbed in which every initiative an advisor proposes can be *executed*, *observed*, and *reconciled*. The testbed must do four things at once: (1) advance a deterministic enterprise state through time, (2) post every material event to a double-entry ledger whose terminals close, (3) expose a constrained, typed action surface to an agent, and (4) generate held-out scenarios so that evaluation measures generalisation rather than memorisation. This document surveys the reusable building blocks, separates what can be composed from what must be rebuilt, specifies the design contract in buildable detail, and scopes a minimum viable build with validation strategy.

## 1. Building blocks: what composes vs what must be rebuilt

### 1.1 System-dynamics and stock-and-flow engines

**Vensim (Ventana Systems).** The reference SD tool, with a well-specified equation language and DSS-level scripting. It is proprietary and per-seat: DSS is US$1,995 commercial / $998 public-research / $798 academic, Professional $1,195, and PLE+ $169, with perpetual licenses plus one year of maintenance [T2] (Ventana Systems, "Purchase," pricing table, https://vensim.com/purchase). The license forbids using the software to provide network services to unlicensed parties outside the organisation [T2] (Ventana Systems, "Vensim Software License," §2 Restrictions on Use, https://vensim.com/license). Strength: mature calibration/optimisation and causal tracing. Limitation for our purpose: no native ledger, closed file format, and licensing that blocks embedding in a multi-tenant evaluation harness.

**PySD.** A MIT-licensed Python library (Python ≥3.9) that parses Vensim `.mdl` and XMILE into an intermediate AST and then into runnable Python, using `Parsimonious` as the PEG parser [T1][T2] (Houghton & Siegel, "Advanced data analytics for system dynamics models using PySD," *Proc. 33rd Int. Conf. of the System Dynamics Society* 2:1436–1462; PySD docs, "Structure of the PySD library"). It is community-maintained, ~460 stars, last release March 2025, and is the pragmatic choice when a stock-and-flow core is wanted inside Python [T2] (PySD on PyPI, release history / "Why create a new SD simulation engine?"). Critical caveat: PySD does not implement all Vensim functions; unsupported functions are translated to `not_implemented_function()` and models may run only partially [T2] (PySD docs, "PySD — 3.14.3," *Currently PySD does not implement all the functions*). Any model we depend on must be validated function-by-function against the interpreter's support list.

**AnyLogic.** Commercial multimethod tool (discrete-event, system dynamics, agent-based) built on Java/Eclipse. The free Personal Learning Edition is explicitly for *evaluation and teaching only* and carries hard caps — 10 agent types per model, 200 embedded blocks per agent, 200 SD variables per agent, 50,000 dynamically created agents, and a 5-hour simulation-time limit [T2] (AnyLogic, "Downloads" comparison table; "Free Simulation Software for Education"). Professional licences run from about €5,490 (Advanced) to €13,950 (Professional), and exporting models to standalone Java is a separate paid feature [T2] (AnyLogic price list; Software Licensing Agreement §"Export to standalone Java application"). It is excellent for exploratory design but not redistributable as a testbed engine, and its determinism story is not designed for byte-level replay.

**Insight Maker.** Free, browser-based, open-source (a JS simulation library published on NPM), created by Scott Fortmann-Roe and documented in a peer-reviewed paper [T1][T2] (Fortmann-Roe, "Insight Maker: A general-purpose tool for web-based modeling & simulation," *Simulation Modelling Practice and Theory*, 2014; Insight Maker docs, "Free and Open Source"). It unifies SD, ABM, and imperative scripting, with Euler and Runge-Kutta solvers, an ECMAScript API, and geographic/network agent structure [T1][T2] (ibid.; Insight Maker docs, "System Dynamics" and "Agent Based Modeling"). It is genuinely composable as an engine but has no ledger, no accounting primitives, and a web/JS runtime that complicates reproducibility.

**Stella / iThink (isee systems).** Proprietary; Stella Architect US$3,999 perpetual, Professional $2,999, Enterprise $2,989/yr; educational licences are heavily discounted (faculty from $699, students from $59) [T2] (isee systems store, "Products," "Education"). It reads XMILE and opens Vensim models, supports multimethod modelling with Monte Carlo/sensitivity/calibration, and publishes to a web exchange [T2] (isee systems, "Stella Architect" feature list). Same core objection as Vensim: no accounting engine and awkward embedding.

**Assessment.** SD engines are the wrong *ledger* but the right *momentum model*. The defensible composition is to take a stock-and-flow core (PySD for open licensing, or a hand-written difference-equation integrator) and wrap it in our own transaction layer, rather than adopting Vensim/Stella/AnyLogic as the substrate.

### 1.2 Agent-based modelling frameworks

**Mesa.** Apache-2.0, Python, ~3,868 stars, with a peer-reviewed write-up [T1][T2] (ter Hoeven et al., "Mesa 3: Agent-based modeling with Python in 2025," *JOSS* 10(107):7668, doi:10.21105/joss.07668). Importantly for our determinism contract, the `Model` class ships a **seeded** `random` generator (a `python.random` PRNG) whose seed is stored on the model [T2] (Mesa source, `mesa/model.py`). Mesa 3 requires Python ≥3.12 and decomposes into modular components (AgentSet, schedulers, Solara browser visualisation); Mesa 4 is in pre-release [T2] (Mesa repo, README; PyPI "Mesa 3.5.1"). Mesa is the natural ABM substrate for counterparties, cohorts, and employee agents.

**Mesa-Geo.** Apache-2.0 GIS extension: a `GeoSpace` hosting `GeoAgent`s with a Shapely `geometry` and a `crs`, constructible from shapefiles, GeoJSON, or a GeoPandas `GeoDataFrame` [T1][T2] (mesa-geo repo/first release note; "Mesa-Geo: A GIS Extension for the Mesa Agent-Based Modeling Framework in Python"). Relevant only if geography (footprint, logistics distance, regional pricing) is part of the business graph.

**NetLogo.** Free Java/Lisp-family environment; reproducibility is an explicit core design goal, and the developers adopted Java "strict" math libraries specifically to guarantee identical cross-platform results [T1][T2] (Wilensky, "NetLogo: Design and implementation of a multi-agent modelling environment"). It is a superb teaching/rapid-prototyping tool and a benchmark reference, but embedding it as a service is awkward versus Python.

**MASON / Repast.** Open-source Java ABM toolkits; MASON has emphasised high performance since 2002 (millions of agents) and has a distributed variant, with customisation as its main strength [T1] (Luke et al., "The MASON Simulation Toolkit: Past, Present, and Future"; "Scalability in the MASON Multi-agent Simulation System"). Repast Simphony and Repast HPC cover large-cluster runs in C++ [T1][T3] (Abar et al., "Agent Based Modelling and Simulation tools: A review," *Computer Science Review* 24, Table 1; Repast docs). These are candidates only at very large agent counts; they otherwise impose a Java build/runtime boundary on a Python-first harness.

**Assessment.** Compose **Mesa** (+ Mesa-Geo if spatial) for agents; do not adopt NetLogo/MASON/AnyLogic as the primary engine.

### 1.3 Business/ERP simulation games and reference models

These supply *validated mechanisms* and *scenario shapes* even though none is a ledger testbed.

**MIT Beer Game** (Forrester, early 1960s, MIT System Dynamics Group). Four roles pass orders upstream and shipments downstream with delays; the classic emergent result is the bullwhip effect — order variance amplifying from retailer to factory [T1][T2] (Sterman, "Modeling managerial behavior: Misperceptions of feedback," 1989; MIT OCW 2.008-S25 Lecture 15; Sterman's own retrospective at web.mit.edu/jsterman/www/SDG/beergame.html). Notably, an **accounting sheet was added in 1968 by Dennis Meadows** and the game keeps explicit inventory/backorder records, so it is already a crude double-entry-adjacent transaction log [T1] (OSTI, "History of the Beer Game," §recent-history phase, p. 18). Kimbrough, Wu & Zhong showed artificial agents can eliminate the bullwhip entirely [T1] (HICSS 2001, doi:10.1109/HICSS.2001.927047).

**Littlefield Technologies** (Responsive Learning Technologies). A web discrete-event factory simulator: four steps on three stations, one reentrant; 1 real hour = 1 game day; 35 days pre-run, 203 simulated days total; levers are machine purchase/sale and station-2 scheduling; teams rank by cash position [T1][T2] (Miyaoka, "Making Operations Management Fun: Littlefield Technologies," *INFORMS Transactions on Education* 5(2):80, 2005; MIT OCW 15-760B slides). It has been used by >500,000 students, and Littlefield 2.0 shipped in 2024 [T3] (INFORMS 2023 tutorial abstract). It is the closest analogue to a "factory with a cash terminal," but it is closed, instructor-run, and lacks a general ledger.

**CESIM, Marketplace, ERPsim, Back Bay Battery.** CESIM Firm/Marketing model multi-market firms with production, promotion, pricing, and an ESG module, judged on capacity utilisation, market share, net profit, ROC, and EPS [T2] (Cesim, "Cesim Firm" overview). Marketplace's "Introduction to Business and Strategy" gives seed capital, a factory, distribution, HR, finance, and a balanced-scorecard score over six rounds, playable against computer opponents [T2] (marketplace-simulation.com, "Introduction to Business and Strategy – PC Edition"). ERPsim runs on a *real* SAP S/4HANA system, so its transaction model is authentically ERP-grade but not extractable [T2] (HEC Montréal, ERPsim). Back Bay Battery (Christensen & Shih, HBS) is a single/multiplayer R&D-allocation game over 8 simulated years with a "fired for repeated losses" constraint and an automated LLM benchmark harness already built on top [T1][T2][T3] (HBS faculty page; HBSP product 7015/8873; forio.com catalog; `ryantallen/bbb_benchmark_public`).

**LLM business-agent benchmarks (the direct predecessors).** Vending-Bench (Andon Labs) runs a vending-machine business for a simulated year, >20M tokens per run, with an explicit price-elasticity demand model and net worth as the metric; Vending-Bench 2 adds adversarial suppliers, delayed/failed deliveries, and refund demands [T1] (Backlund & Petersson, arXiv:2502.15840, §2.2.2 "Simulating customer purchases"; Epoch AI, "Vending-Bench 2"). CEO-Bench ("Can Agents Play the Long Game?") simulates a startup for 500 days through a Python interface with **34 tools and a 19-table business database**, $1M starting cash, random seed 42, three runs per model; delays are realistic (billing cycles, multi-day R&D, delayed churn/reputation) [T1] (arXiv:2606.18543, §2 "Designing CEO-BENCH," Table 3). A sibling multi-agent CEO-Bench defines scenario difficulty tiers **Easy / Tension / Fragile** [T1] (arXiv:2606.17459, Table 3). MerchantBench runs 365 days at order level grounded in 98,843 real e-commerce product records with 26 tools and mixed-latency feedback [T1] (arXiv:2607.28956). Business Arena runs a cross-border B2B shop grounded in real sourcing data and uses **mechanism ablations** to prove results are not simulator shortcuts [T1] (arXiv:2608.08621). The spreadsheet-based "AI Playing Business Games" simulator exposes pricing, order size, marketing, hiring/dismissal, loans, training, R&D, and forecasts monthly over a year [T1] (Ovezmyradov, arXiv:2509.26331).

### 1.4 Synthetic ledger and double-entry generators

**Production-grade ledger engines.** TigerBeetle (Apache-2.0) is a financial-transactions database whose schema *is* double-entry: fixed 128-bit account IDs, immutable transfers, and the invariant that the sum of debits and credits stays equal so "money cannot be created or destroyed, but only transferred" [T2] (TigerBeetle docs, "Debit-Credit" and "Double-Entry Bookkeeping"; README). It uses **deterministic simulation testing (DST)** as a first-class methodology [T2] (Formance, "Formance vs TigerBeetle," §"Four properties define TigerBeetle's architecture"). Blnk (open-source, double-entry) adds in-flight transactions, scheduling, overdrafts, and reconciliation against external statements [T2] (Blnk repo, README §"Core capabilities"). Formance's MIT-licensed core ledger enforces double-entry *at the storage layer* (so no service-layer code can bypass it), uses the Numscript transaction language, and is bi-temporal [T2] (formancehq/ledger; Formance comparison blog, §"Double-entry enforcement at the storage layer"). `senecajs/seneca-ledger` (MIT) models books/periods, balanced entries, and close-and-carry-forward [T3] (Seneca repo, README API list).

**Synthetic journal-entry generators.** Gronewald et al. generate a labelled general-ledger dataset for two fiscal years of a fictional company that complies with double-entry rules (each entry ≥2 posting lines) using predefined transaction patterns plus probabilistic frequencies, deliberately injecting audit-problematic entries [T1] (Gronewald, Stephan, Rombach & Fettke, "Generating Synthetic Journal Entries for Audit Analytics: Method and Dataset," SSRN 7211804). A VAE-based method generates journal entries that "reflect the double-entry bookkeeping structure and statistical properties" of real data [T1] (Wiley, "Generating Synthetic Journal-Entry Data Using Variational Autoencoders," 2025). `ducal7/ledger-reconciliation` (MIT) is a small but directly instructive template: a seeded generator emits a balanced internal ledger plus an external settlement feed, validates the double-entry invariant both per-transaction and as a global account roll-up with pydantic, reconciles via a DuckDB `FULL OUTER JOIN`, and its tests assert that the same seed gives byte-identical output while different seeds diverge [T3] (GitHub `ducal7/ledger-reconciliation`, README "Tests" and "Architecture"). Public reference data exists — e.g. a US chart-of-accounts/journal-entry/trial-balance dataset (CC-BY-NC-4.0) — useful for schema calibration [T3] (HuggingFace `mindweave/accounting-ledger-us`).

**Assessment.** The ledger is the **one component that must be rebuilt/reused deliberately**, not improvised. TigerBeetle gives invariants but its fixed numeric schema fights a business-graph's rich account taxonomy; a from-scratch SQL/pydantic ledger modelled on `ducal7` plus double-entry discipline inspired by TigerBeetle/Formance is the pragmatic core. Penrose's AccountingBench reinforces the pattern: a simplified ledger with **modifications only through stored procedures**, i.e. the ledger does not let callers write arbitrary rows [T2] (Penrose, "Can LLMs Do Accounting?," §"Task Architecture").

### 1.5 Compose-vs-rebuild verdict

| Capability | Compose (buy/adopt) | Rebuild | Rationale |
|---|---|---|---|
| Stock-and-flow core | PySD (MIT) or own integrator | ✓ if PySD function coverage insufficient | Open licence; AST path; unsupported ops risk |
| Agent layer | Mesa (+Mesa-Geo) | | Seeded PRNG, Apache-2.0, modular |
| Counterparty/cohort behaviour | Beer Game / Vending-Bench mechanisms | ✓ parametrised | Mechanisms validated, but re-express as code |
| Double-entry ledger | (TigerBeetle invariants as reference) | ✓ | Need rich account taxonomy + agent write API |
| Financial statements | — | ✓ | Articulation rules are simple; must be exact |
| Scenario shapes & difficulty | CEO-Bench tiers, Vending-Bench 2 messiness | ✓ generator | Structure inspires, instances must be held out |
| Determinism harness | Mesa seed, DST ideas | ✓ version-pinned env | Cross-library PRNG drift is real (see §2.4) |

## 2. Design contract

### 2.1 Ledger reconciliation guarantees

The simulator's authoritative state is a **single append-only journal**; everything else (statements, KPIs) is a pure projection. Invariants enforced fail-closed on every commit:

1. **Per-entry balance:** for each journal entry, `Σ debits = Σ credits` (double-entry). Reject any unbalanced entry.
2. **Global roll-up:** for the whole book, `Σ all debits = Σ all credits` at every timestamp [T3] (template in `ducal7/ledger-reconciliation`, "Tests").
3. **Balance-sheet identity:** `Assets = Liabilities + Equity` at every close [T2] (SEC, "Beginners' Guide to Financial Statements").
4. **Articulation of the three statements:** net income from the income statement flows into retained earnings on the balance sheet (net of dividends), and the cash-flow statement reconciles net income to the change in cash whose terminal equals balance-sheet cash [T2] (Corporate Finance Institute, "Three Financial Statements"; OpenStax *Principles of Finance* §5.3; SEC op. cit.).
5. **Immutability:** entries are never mutated; corrections are reversing entries. This mirrors TigerBeetle's "transfer history is immutable" and Penrose's stored-procedure-only writes [T2] (TigerBeetle docs; Penrose AccountingBench).
6. **Trial balance:** per-period trial balance sums to zero across all accounts, emitted at every period close.

Money is modelled as integer minor units to eliminate float drift; every RNG-driven economic event that has a monetary consequence must emit exactly one balanced journal entry, so the ledger doubles as the **event log**.

### 2.2 Observation surface

The agent observes a versioned, read-only snapshot at each decision timestep:

- **Statements:** income statement (period), balance sheet (point-in-time, comparative), cash-flow statement (period, operating/investing/financing) [T2] (SEC op. cit.).
- **KPIs:** capacity utilisation, market share, net profit, return on capital, EPS — the CESIM success-measure set [T2] (Cesim, "Cesim Firm"); plus a KPI tree (CAC, LTV, contribution margin, cash runway, DSO/DPO/DIO).
- **Event feed:** the journal delta since last observation (typed events, not prose), mirroring Littlefield's per-game "history of your moves" and "current cash position" [T2] (MIT OCW 15-760B slides).
- **Counterparty state:** per-supplier/customer balance, open orders, receivables/payables, and trust/reputation signals (YC-Bench's "trust snowball" suggests reputation should be a first-class observable) [T3] (Collinear AI, "YC-Bench").
- **Delayed signals:** some outcomes (churn, R&D completion, billing) must only surface after multi-step latency, as in CEO-Bench and MerchantBench [T1] (arXiv:2606.18543; arXiv:2607.28956).

Observation must be **partitioned** so held-out scenario parameters (demand model, competitor reactions) are not fully inferable from the payload.

### 2.3 Action surface

A small, typed, rate-limited action set, each with explicit range and reversibility class:

| Action | Range / units | Reversibility |
|---|---|---|
| Price change per SKU/channel | bounded ±X% per step | Reversible next step |
| Marketing/spend | non-negative currency, budget-capped | Sunk (irreversible) |
| Hiring / dismissal | integer headcount, wage band | Partly reversible (severance cost) |
| Inventory / order size | non-negative units, supplier MOQ + lead time | Inventory is reversible, cash is not |
| Capacity (buy/sell assets) | integer machines, purchase/sale price | Asset reversible at haircut; capex sunk |
| Credit / financing | loan principal, covenant limits | Reversible at interest cost |
| Product change (R&D launch) | budget + lead time | Irreversible once launched |

This mirrors the validated lever sets: Littlefield's machine buy/sell and scheduling [T2] (MIT OCW 15-760B); Back Bay Battery's price + R&D-allocation trade-off [T1] (Shih & Christensen, "Strategic Innovation Simulation: Back Bay Battery"); and "AI Playing Business Games"' monthly pricing/orders/marketing/hiring/loans/R&D set [T1] (arXiv:2509.26331). Every action is a **proposal** validated by the constraint layer before it can produce a journal entry.

### 2.4 Seeding and determinism contract

- **Named RNG streams, not one global seed.** Each stochastic subsystem (demand arrivals, supplier lead times, churn, defect rate, macro shocks) owns an independent seeded stream, so that changing one subsystem does not perturb others. This is the multi-stream pattern used in discrete-event tooling (`simEd`/`rstream` seeding) [T2] (simEd `set.seed` docs).
- **Seed + full state capture.** Log the seed *and* the RNG state at each commit, mirroring R's `simulate(seed=...)` convention of storing the pre-run `.Random.seed` attribute [T2] (R `stats::simulate` docs).
- **Cross-library caution.** Do not assume identical PRNG state yields identical streams across libraries: Mersenne Twister and Philox differ across Random/NumPy/PyTorch/TensorFlow, and PyTorch's Philox is incompatible with the reference algorithm [T1] ("Reproducible AI Requires Reproducible Randomness," arXiv:2609.26461). Pin the RNG *implementation*, not just the seed.
- **Version pinning.** Freeze interpreter and library versions (e.g. a lockfile) and record them in run metadata; NetLogo's use of Java "strict" math is the model for cross-platform numerical determinism [T1] (Wilensky, NetLogo design paper). Where JS is used, note that `seedrandom` changed sequences between major versions, so seeds are not portable across versions [T2] (`seedrandom` release notes).
- **Replay contract:** given (scenario version, seed set, action log), the simulator must reproduce byte-identical journal and statements. This is the TigerBeetle "deterministic simulation testing" discipline applied at the scenario level [T2] (Formance comparison, §TigerBeetle architecture).

### 2.5 Constraint-enforcement layer

Two classes, checked in a fixed order before any state change:

- **Hard constraints (fail-closed, cannot be violated):** double-entry balance, non-negative cash unless a credit facility is active, covenant limits, MOQ/lead-time feasibility, headcount ≥ 0, ledger immutability. A violating action is **rejected with a typed error and no journal entry** — the default is denial, not best-effort. This inherits the "money cannot be created or destroyed" invariant [T2] (TigerBeetle docs) and stored-procedure-only writes [T2] (Penrose).
- **Soft constraints (penalised, allowed):** brand/mission alignment, ESG thresholds, short-term profitability targets. These emit a cost/score rather than a rejection, matching Back Bay Battery's "meet constraining financial objectives" and CESIM's ESG-in-strategy framing [T1][T2] (Back Bay Battery; Cesim Firm ESG module).

Every verdict (accept/reject + reason) is written to an audit stream distinct from the journal, so evaluation can score both outcomes and *policy compliance*.

### 2.6 Held-out scenario generation

- **Train/eval split by generator seed, not by hand-picking.** A scenario is a tuple (structural template, exogenous parameter draw, seed set). Training seeds and evaluation seeds are drawn from disjoint sets; evaluation templates may also be disjoint.
- **Distribution shift:** hold out (a) shock types (demand collapse, supplier failure, refund wave as in Vending-Bench 2) [T1] (Epoch AI Vending-Bench 2), (b) structural shifts (new competitor, channel change), and (c) parameter regimes (high-margin vs high-turnover).
- **Difficulty ladder:** adopt CEO-Bench's **Easy / Tension / Fragile** tiers — aligned signals; cross-functional trade-offs; high-downside reallocation — and grade on coherence and outcome rather than exact-answer matching [T1] (arXiv:2606.17459, Table 3, §3.4).
- **Contamination control:** mechanism ablations and source-grounding checks, as Business Arena uses, to prove a good score reflects business intelligence rather than a simulator shortcut [T1] (arXiv:2608.08621).

## 3. Minimum viable build, cost, and validation

### 3.1 Minimum viable build (MVB)

A usable testbed needs, in priority order:

1. **Journal + double-entry ledger** (integer minor units, per-entry and roll-up invariants, immutable, reversing-entry corrections).
2. **Projection layer** producing income statement, balance sheet, cash-flow statement, trial balance, and a KPI bundle, with articulation checked each close.
3. **Time engine** with a fixed tick (daily) and a period close (monthly), running a small stock-and-flow core (cash, inventory, receivables/payables, PP&E, retained earnings).
4. **One composed ABM market** (Mesa) with seeded demand, price elasticity, and a competitor or two; supplier lead times with noise.
5. **Action API** covering the seven levers in §2.3 with ranges and reversibility flags, plus the hard/soft constraint checker.
6. **Seeded scenario generator** with train/eval seed split and an Easy-tier scenario set.
7. **Replay harness** that re-runs from (scenario, seed set, action log) and asserts byte-identical journal.

Everything else (Mesa-Geo, multi-entity consolidation, tax, multi-currency, 3D visualisation, ERP integration) is deliberately out of scope for the MVB.

### 3.2 Cost estimate

For a competent small team (1 senior Python/accounting-aware engineer, 1 simulation engineer, part-time accounting review), realistic person-month ranges:

- Ledger + invariants + projections: **3–5** pm (the exactness of articulation and trial balance is where hidden effort lives).
- Time engine + stock-and-flow core: **1–2** pm.
- Mesa market/counterparty layer: **2–3** pm.
- Action + constraint layer: **1–2** pm.
- Scenario generator + difficulty tiers: **1–2** pm.
- Replay/determinism harness + CI: **1–2** pm.
- Calibration & validation: **2–4** pm.

Total **≈ 11–20 person-months** to a defensible v1. The upper bound reflects validation; the ledger/projection work is the pacing item and the place where a domain reviewer (CPA-level) is essential.

### 3.3 Validating against historical firm behaviour

Three complementary methods, drawn from established ABM validation practice, which distinguishes qualitative simulation, **replication of stylized facts** (indirect calibration), empirical/direct calibration, and the **history-friendly** approach [T1] (Gatti et al., "Towards a Validation Methodology for Macroeconomic Agent-Based Models," *Computational Economics*, 2021, §validation approaches):

- **Stylized-fact checks.** Require the simulator to reproduce robust regularities — fat-tailed demand/return distributions, volatility clustering, absence of return autocorrelation, and the bullwhip amplification of order variance up the chain [T1] (Beikirch et al., "Simulation of Stylized Facts in ABCEM Models," 2019; Cont, "Empirical properties of asset returns," 2001; Sterman 1989). ABIDES-Economist shows this is the standard indirect-calibration route for firm/household ABMs [T1] (Dwarakanath et al., arXiv:2402.09563, §on stylized facts and calibration).
- **Calibration to real series.** Fit exogenous parameters to observable US data (cost structures, demand seasonality) and, where possible, calibrate directly at the micro level rather than only matching aggregate moments, using indirect inference or heuristic search (Nelder–Mead + threshold accepting, genetic algorithms) as in the OFR and Fabretti studies [T1] (OFR, "An Agent-based Model for Crisis Liquidity Dynamics," §4; Fabretti, *JEIC* 8(2):277–293). SABCEMM is the reference open, reproducible framework for this [T1] (Trimborn et al., *Computational Economics* 55(2):707–744).
- **Event-log replay.** Feed a real historical event/transaction log into the simulator, execute the recorded actions verbatim, and compare simulated statements/terminals against the firm's actuals; divergence localises model error to specific mechanisms. This is the harness analogue of the "history-friendly" validation tradition and of ERP5's simulation-based planning, where future consequences of decisions are computed from configurable rules [T1][T2] (Malerba et al. history-friendly modelling; ERP5, "Simulation Technology").

Pass criteria: articulation always exact; stylized facts within tolerance; replay terminal cash within an agreed band; and no held-out scenario solvable by exploiting simulator artefacts (verified by mechanism ablation) [T1] (arXiv:2608.08621).

## 4. Existing partial implementations and the gap to a business-graph testbed

| Existing system | What it already gives | Gap to a business-graph testbed |
|---|---|---|
| PySD [T1][T2] | Vensim/XMILE → Python stock-flow | No ledger/KPIs; incomplete Vensim coverage |
| Mesa / Mesa-Geo [T1][T2] | Seeded agents, GIS | No accounting, no business semantics, no constraint layer |
| TigerBeetle [T2] | Hard double-entry invariants, DST | Fixed numeric schema; not a business model; no P&L/KPI |
| Blnk / Formance [T2] | Production double-entry + reconciliation | Fintech-oriented; no firm economics or decisions |
| `ducal7/ledger-reconciliation` [T3] | Seeded generator + invariant tests + rollout | Toy scale; no statements, no agent, no scenarios |
| Gronewald synthetic GL [T1] | Realistic double-entry journal entries | Static dataset; no causal firm model |
| Beer Game / Littlefield [T1][T2] | Validated supply/factory mechanisms, cash terminal | Closed, no general ledger, no action API |
| CESIM / Marketplace / ERPsim [T2] | Rich business decision surfaces | Proprietary/closed; not programmatically seeded |
| Vending-Bench / CEO-Bench / Business Arena [T1] | Long-horizon agent evals, delayed outcomes, difficulty tiers, ablations | Narrow scopes; ledger is implicit, not reconciled |

The synthesis the business-graph testbed needs is a **reconciled journal as the single source of truth**, a **Mesa-based economic layer** whose every monetary event emits balanced entries, a **typed action+constraint API** in the style of AccountingBench's stored procedures, and a **seeded, held-out scenario generator** borrowing difficulty tiers from CEO-Bench and messiness from Vending-Bench 2. Each row above contributes a validated mechanism or invariant; none alone is the testbed, and the ledger-plus-articulation layer — the part no game or ABM framework provides — is precisely the rebuild that must be done first and validated hardest.

## References and sources

- Backlund, A., & Petersson, L. (2025). *Vending-Bench: A Benchmark for Long-Term Coherence of Autonomous Agents.* arXiv:2502.15840. [T1]
- Epoch AI. *Vending-Bench 2.* https://epoch.ai/benchmarks/vending-bench-2 [T2]
- *CEO-Bench: Can Agents Play the Long Game?* arXiv:2606.18543. [T1]
- *Can LLMs Be CEOs? Benchmarking Strategic Resource Reallocation with Multi-Role Agent Simulation.* arXiv:2606.17459. [T1]
- *MerchantBench.* arXiv:2607.28956. [T1]
- *Business Arena: Benchmarking LLM Agents in a Realistic Marketplace.* arXiv:2608.08621. [T1]
- Ovezmyradov, B. (2025). *AI Playing Business Games.* arXiv:2509.26331. [T1]
- Collinear AI. *YC-Bench.* https://huggingface.co/blog/collinear-ai/yc-bench [T3]
- Penrose. *Can LLMs Do Accounting? (AccountingBench).* https://accounting.penrose.com/ [T2]
- Kimbrough, S. O., Wu, D. J., & Zhong, F. (2001). *Computers play the Beer Game.* HICSS. doi:10.1109/HICSS.2001.927047. [T1]
- Sterman, J. D. (1989). *Modeling managerial behavior: Misperceptions of feedback.* [T1]
- MIT OpenCourseWare. *2.008-S25 Beer Game Activity*; *15-760B Littlefield slides.* [T2]
- OSTI. *History of the Beer Game* (2024). [T1]
- Miyaoka, J. (2005). *Making Operations Management Fun: Littlefield Technologies.* INFORMS Transactions on Education 5(2):80. [T1]
- Responsive Learning Technologies. *Littlefield.* https://responsive.net/littlefield.html [T2]
- Cesim. *Cesim Firm* / *Simulations Overview.* [T2]
- Marketplace Simulations. *Introduction to Business and Strategy – PC Edition.* [T2]
- HEC Montréal. *ERPsim.* https://erpsim.hec.ca/en/erpsim [T2]
- Shih, W. C., & Christensen, C. M. *Strategic Innovation Simulation: Back Bay Battery.* HBS. [T1]
- HBSP products 7015/8873; Forio catalog. [T2]
- `ryantallen/bbb_benchmark_public`. [T3]
- Ventana Systems. *Purchase* / *Vensim Software License.* [T2]
- isee systems. *Products* / *Stella Architect* / *Education.* [T2]
- AnyLogic. *Downloads* / *Software Licensing Agreement.* [T2]
- Fortmann-Roe, S. (2014). *Insight Maker.* Simulation Modelling Practice and Theory. [T1]
- Insight Maker docs. *Free and Open Source* / *System Dynamics* / *Agent Based Modeling.* [T2]
- Houghton, J. P., & Siegel, M. (2015). *Advanced data analytics for system dynamics models using PySD.* SD Society. [T1]
- Martin-Martinez et al. (2022). *PySD.* JOSS 7(78):4329. [T1]
- PySD docs. *Structure of the PySD library* / *3.14.3.* [T2]
- ter Hoeven, E., et al. (2025). *Mesa 3.* JOSS 10(107):7668. [T1]
- Mesa repo (`mesa/model.py`); PyPI Mesa. [T2]
- Burge, J., et al. *Mesa-Geo.* (mesa/mesa-geo). [T1][T2]
- Wilensky, U. *NetLogo: Design and implementation of a multi-agent modelling environment.* [T1]
- Luke, S., et al. *The MASON Simulation Toolkit: Past, Present, and Future.* [T1]
- Abar, S., et al. (2017). *Agent Based Modelling and Simulation tools: A review.* Computer Science Review 24. [T1]
- TigerBeetle docs. *Debit-Credit* / *Double-Entry Bookkeeping.* [T2]
- Blnk repo. `blnkfinance/blnk`. [T2]
- Formance. `formancehq/ledger`; *Formance vs TigerBeetle.* [T2]
- Seneca. `senecajs/seneca-ledger`. [T3]
- Gronewald, J., Stephan, S., Rombach, A., & Fettke, P. *Generating Synthetic Journal Entries for Audit Analytics.* SSRN 7211804. [T1]
- *Generating Synthetic Journal-Entry Data Using Variational Autoencoders.* Wiley, 2025. [T1]
- *AuditCopilot: Leveraging LLMs for Fraud Detection in Double-Entry Bookkeeping.* arXiv:2512.02726. [T1]
- `ducal7/ledger-reconciliation`. [T3]
- HuggingFace `mindweave/accounting-ledger-us`. [T3]
- SEC. *Beginners' Guide to Financial Statements.* [T2]
- Corporate Finance Institute. *Three Financial Statements.* [T2]
- OpenStax. *Principles of Finance* §5.3. [T2]
- *Reproducible AI Requires Reproducible Randomness.* arXiv:2609.26461. [T1]
- R `stats::simulate`; `simEd::set.seed`. [T2]
- `seedrandom` release notes. [T2]
- Dwarakanath, K., Balch, T., & Vyetrenko, S. *ABIDES-Economist.* arXiv:2402.09563. [T1]
- Trimborn, T., et al. (2019). *SABCEMM.* Computational Economics 55(2):707–744. [T1]
- Beikirch, M., et al. (2019). *Simulation of Stylized Facts in ABCEM Models.* [T1]
- Gatti, D., et al. (2021). *Towards a Validation Methodology for Macroeconomic Agent-Based Models.* Computational Economics. [T1]
- Fabretti, A. (2013). *On the problem of calibrating an agent based model for financial markets.* JEIC 8(2):277–293. [T1]
- OFR. *An Agent-based Model for Crisis Liquidity Dynamics* (2015), §4. [T1]
- Cont, R. (2001). *Empirical properties of asset returns: stylized facts and statistical issues.* Quantitative Finance. [T1]
- ERP5. *Simulation Technology.* [T2]
