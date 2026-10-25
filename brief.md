# Business as a Machine — Research Brief

**Domain**: `business-as-machine`
**Output dir**: `/root/code/personal/research/business-as-machine`
**Created**: 2026-10-09

## Goal

Build a model of any business that can be used as an agentic harness to optimise and grow a business: start from a P&L and balance sheet, then consider different layers of abstraction, comparative benchmarking at each level, so that ultimately a human or agentic business-strategy advisor can create experiments or initiatives to grow the business by optimising different layers or nodes on the graph. Treat the business as a transformation machine — a connected graph of assets, liabilities, and means to transform assets into other assets to sell — that operates under constraints (cashflow, legal, intention/mission, values, brand), all of which must be modelled.

## Inspirations & references

- Financial statement modelling: DuPont analysis, driver-based planning, unit economics, activity-based costing
- Systems dynamics and theory of constraints: Beer's STORM, stock-and-flow business models, throughput accounting
- Value chain and capability graphs: Porter's value chain, resource-based view, capability maps, business model canvas
- Agent/AI operating frameworks: OS-level harnesses, MCP, tool-use agents, automated experiment loops (Bayesian optimisation, growth experimentation)
- Enterprise architecture and ontologies: ArchiMate, BPMN, REA (Resources-Events-Agents) accounting ontology, TOGAF
- Benchmarking datasets: XBRL/fundamentals APIs, Compustat, IBES, public-company peer benchmarks
- Modern software architecture: agile, team topologies, flow — the faster a business can change its product and receive customer feedback, the higher its chance of success

## Constraints & scope

- None stated — broad coverage. The model should aim to generalise across business types (SaaS, e-commerce, services, physical goods) unless a topic is justified by a narrower scope.

## Source types

For this project, source preference is: All three balanced.

The three types are defined below regardless of priority. Cover whichever types the topic actually justifies, weighted by the priority above. No quotas.

- **Type 1** — published research papers, peer-reviewed work, conference proceedings. Cite as: source + page + paragraph. Example: `[T1] Smith et al. 2024, p. 12, ¶3`.
- **Type 2** — official documentation, technical specs, design system docs, white papers, books, renowned domain blogs. Cite as: source + subsection (if any) + line number. Example: `[T2] ESP32 Reference Manual, GPIO chapter, line 42`.
- **Type 3** — social posts, Hacker News, small blogs, podcasts, conference videos. Cite as: source + URL. Example: `[T3] @username, https://...`.

Tag every inline citation with its type (`[T1]`, `[T2]`, `[T3]`) so the synthesis can spot coverage gaps against the stated preference.

## Conventions

- Each topic is researched by a parallel agent and saved to `{output_dir}/research/{topic-slug}.md`.
- Each topic agent's primary mode is external web research — fresh sources, not training data.
- The whole-corpus synthesis lives at `{output_dir}/synthesis/general.md` and is fully rewritten after each round.
- Rounds are appended below as `## Round 2`, `## Round 3`, etc. Earlier rounds and their topic files are never rewritten.
- **No research-process mechanics in the output.** Topic files and the synthesis must read as standalone research, not as a log of a process. Never write "in round 1 we found X", "this round added coverage of Z", "a previous agent missed…". The only structural leak allowed is the topic/synthesis split itself.

## Round 1

### Financial statements as the base layer of the business model

File: `research/financial-statements-base-layer.md`

Establish how the three financial statements decompose into a driver graph. Cover DuPont decomposition (3-step and 5-step), driver-based planning and integrated financial models, unit economics (CAC, LTV, contribution margin, payback), activity-based costing, and how each line item (revenue, COGS, opex, working capital, capex, debt) can be expressed as a function of operational drivers. Emphasise the causal links between P&L, balance sheet, and cash-flow statement, and identify which drivers are actionable levers versus accounting artefacts. Conclude with a concrete decomposition of a generic P&L and balance sheet into nodes and edges.

### Existing ontologies of a business as a system

File: `research/business-ontologies.md`

Compare the formal models that already represent a business as a structured system: REA (Resources-Events-Agents) accounting ontology, ArchiMate, BPMN, TOGAF, the Business Model Canvas and its variants, and the Value Delivery Modeling Language (VDML). For each, state what it represents well, its level of formality and machine-readability, coverage of resources/flows/actors/constraints, tooling and active maintenance, and where it breaks as a unified "business machine" graph. Identify which parts could be reused or composed into a single transformation-graph ontology and what would have to be built new.

### Systems dynamics, stock-and-flow, and theory of constraints

File: `research/systems-dynamics-toc.md`

Cover how businesses are modelled as dynamic systems: system dynamics and stock-and-flow modelling (Forrester, Sterman), causal loop diagrams, Beer's Viable System Model and STORM, Senge's archetypes (limits to growth, shifting the burden), and the theory of constraints / throughput accounting (Goldratt). Explain feedback loops, delays, bottlenecks, and leverage points, and how these map to optimisation targets on a business graph. Include evidence on where system-dynamics models of firms have actually improved decisions versus where they failed, and note the data requirements.

### Value chain, capabilities, and layers of abstraction

File: `research/value-chain-capabilities-layers.md`

Define hierarchical layers of abstraction over one business graph. Cover Porter's value chain and value system, the resource-based view and dynamic capabilities, capability maps and business capability modelling, and the strategy-to-execution ladder (vision → strategy → objectives → capabilities → activities → transactions). Compare how each framework defines and links layers, and propose a concrete stacked-layer scheme (transactions → activities → processes → capabilities → assets/liabilities → financial statements → strategy) showing which edges cross layers and which metrics attach to each level.

### KPI trees and comparative benchmarking at each layer

File: `research/kpi-trees-benchmarking.md`

Cover metric hierarchies and benchmarking. Compare north-star frameworks, KPI trees, OKRs, the Balanced Scorecard, and growth accounting decompositions, and how each attaches metrics to a layer of the business graph. Then survey comparative benchmarking: XBRL and SEC EDGAR financial statement data, Compustat/CRSP, IBES, Companies House/Companies Register APIs, industry benchmark reports (SaaS benchmarks, RMA/NAICS ratios, public comparables), and peer-matching methods (SIC/NAICS, size/age/geography). State what is benchmarkable at each abstraction level (financial ratios, unit economics, operational metrics), the cost and licensing of each data source, and the pitfalls of naive peer comparison.

### Modelling constraints: cash, legal, mission, values, brand

File: `research/constraints-modelling.md`

Define how to represent the constraints a business operates under so an optimiser respects them. Contrast hard constraints (liquidity and runway, debt covenants, minimum cash, regulatory and legal limits, tax, capacity) with soft/preference constraints (mission, values, brand promise, ESG commitments, reputational risk). Survey formal representations — constrained optimisation, constraint programming, business rules engines (DMN), policy-as-code, guardrails for AI agents — and how to attach a constraint to specific nodes/edges of the graph. Include how mission/values/brand can be operationalised into checkable predicates rather than vague aspiration, and how constraint violations and trade-offs are surfaced to a strategy advisor.

### The business as a transformation graph

File: `research/transformation-graph.md`

Treat the business as a graph of assets, liabilities, and transformations that convert inputs into sellable outputs. Survey approaches to enterprise knowledge graphs, digital twins of organisations, process graphs, and REA-style resource-flow networks. Define node types (assets, liabilities, inventories, capabilities, actors, contracts, products, customers, channels) and edge types (flows, transformations, conversions, ownership, obligations, influences), and how value, cost, and cash move along edges over time. Address how to represent transformation yields/losses, throughput, cycle time, and capacity, and how the graph stays consistent with the financial statements. Note the practical questions of graph schema, temporal/versioned edges, and granularity.

### Agentic harnesses and AI strategy advisors

File: `research/agentic-harnesses-strategy-advisors.md`

Survey the design of agentic harnesses that could operate on a business model to optimise it. Cover tool-use agent architectures, MCP-style tool ecosystems, planner-executor loops, memory and state, human-in-the-loop approval, and safe action-taking under constraints. Then survey existing "AI CFO / AI strategist / autonomous business operations" products and research: autonomous experimentation platforms, LLM agents for finance and operations, and any systems that read live business data and propose or execute changes. For each, document architecture, what actions they can take, safeguards, evidence of effectiveness, and failure modes; end with the design requirements for an agent that optimises nodes of this graph without violating constraints.

### Experiment and initiative design systems

File: `research/experiment-initiative-design.md`

Cover how strategists — human or agentic — generate, choose, sequence, and evaluate interventions. Include growth loops and growth-model frameworks (acquisition, activation, retention, referral, monetisation; loops vs funnels), hypothesis-driven experimentation and A/B/n testing, causal inference for business decisions (difference-in-differences, synthetic control, uplift modelling), initiative portfolio management and prioritisation (ICE/RICE, cost of delay, theory of constraints), and the build-measure-learn / lean-startup cycle. Map each method to the graph node or layer it typically optimises, note sample-size and measurement pitfalls, and describe how a portfolio of initiatives is tracked against the constraints and benchmarks from the earlier layers.

### Iteration speed as a first-class variable

File: `research/iteration-speed.md`

Model how fast a business can change its product/operations and receive customer feedback as an explicit factor in growth and survival. Cover agile and lean/DevOps flow, team topologies and Conway's law, lead-time/DORA/cycle-time metrics, feedback latency and deployment frequency, and organisational learning (organizational ambidexterity, OODA, PDCA). Gather evidence linking iteration/feedback speed to business outcomes (survival, growth, product-market fit, innovation), and show how "rate of change" and "feedback delay" could be represented as parameters or nodes on the transformation graph — including how agility trades off against stability, cost, and constraint violations.

## Round 2

### Minimal viable graph and the cost of instantiating a live business graph

File: `research/minimal-viable-graph-instance-cost.md`

Determine the smallest node/edge schema that still supports real optimisation decisions, and what it costs to instantiate and maintain it from real systems. Identify the fewest node types, edge types, and parameters needed to reproduce the financial statements as projections and to support one concrete optimisation (e.g. a price or spend experiment), then survey how such graphs are actually built: ERP/finance/CRM integrations, ETL/ELT and dbt-style modelling, event sourcing, XBRL ingestion, and commercial digital-twin/enterprise-knowledge-graph platforms. Find first-person and case-study evidence of build cost — person-months, integration effort, data-quality remediation, maintenance — rather than vendor claims, and state where a full graph is over-engineering versus where a smaller model fails.

### Towards a transformation algebra

File: `research/transformation-algebra.md`

Establish whether a coherent quantitative algebra linking stocks, transformation yields, cycle times, capacity, unit economics, and cash exists, or must be constructed. Compare the candidate ingredients — TOC throughput accounting, value-stream mapping metrics (takt, lead/cycle time, %CA), TDABC/ABC cost-driver rates, Little's law and queueing relations, object-centric process mining performance measures, and stock-and-flow system dynamics — and test whether they compose into one consistent parameter set over a graph. Document contradictions and double-counting risks (e.g. GAAP vs. throughput valuation, cost allocation vs. driver rates), propose a minimal consistent set of equations and their units, and state what empirical data each equation requires.

### A reproducible evaluation protocol for a business-graph harness

File: `research/harness-evaluation-protocol.md`

Specify how to evaluate an agentic harness that optimises a business graph. Synthesise the scoring schemes of CEO-Bench, Vending-Bench, Back Bay Battery, and "AI Playing Business Games" into a proposed composite scorecard (profit, growth, future position, constraint-respect) with deterministic graders where possible and judge-model fallbacks where not. Define the isolated, reproducible environment, the sample sizes and seeds, the baseline set (rule-based and human cohorts), the constraint-violation tests (insolvency, covenant breach, legal/brand violation, privilege escalation), the long-horizon coherence measures that Vending-Bench shows separate models, and the held-out validation that guards against algorithmic mode collapse. Be specific and falsifiable.

### Real business-as-graph projects: build narratives and failures

File: `research/business-graph-projects-failures.md`

Counter the vendor and standards literature with first-person evidence of real attempts to model a specific business as a graph or digital twin: enterprise knowledge-graph and digital-twin programs, driver-based/three-statement model builds, REA/Valueflows implementations, data-mesh/semantic-layer projects, and "single source of truth" finance/ERP initiatives. Extract what was actually built, the cost and timeline, where decay started or the project died, what the last commit/retrospective said, and whether anyone shipped a maintained instance graph that improved decisions. Prioritise engineering blogs, conference talks, Hacker News/Reddit threads, post-mortems, and abandoned repositories over product marketing, and contrast survivors with failures.

### How far can mission, values, and brand be formalised?

File: `research/values-brand-formalisation-depth.md`

Test the limits of operationalising mission, values, and brand into machine-checkable predicates. Survey how organisations actually convert values into measurable behaviours and guardrail metrics, where this succeeds and where it degrades into Goodhart-style gaming or performative compliance, and what literature says about the irreducible or tacit elements. Cover value-measurement frameworks, ESG/CSRD disclosure operability, brand-safety and reputation-risk models, culture-measurement tools, and the role of human judgement and approval in AI systems that must respect values. End with a clear boundary: which values/brand constraints can be predicates, which can only be weighted soft terms, and which must remain human-authorised, with evidence for the line. Give balanced coverage across all three source types, including practitioner and social-discourse evidence ([T3]) on performative compliance and greenwashing alongside the formal literature.

## Round 3

### Instantiating and validating the transformation algebra on real event logs

File: `research/algebra-instantiation-validation.md`

Move the proposed transformation algebra from construction to test. Establish the state of the art in object-centric event logs (OCEL 2.0), process-mining performance measures, and the availability of public business event datasets (BPI Challenge logs, process-mining repositories, ERP/extract datasets), and specify a concrete instantiation exercise: map one object-centric event log (or synthetic double-entry ledger) onto the algebra's stocks, flows, yields, cycle times, capacity, and cash equations, compute each quantity, and test the GAAP/throughput reconciliation identity `NI_GAAP = NP_TA + ΔInventory × overhead/unit` end to end. Report what breaks where units or semantics are ambiguous, whether composition rules (series, parallel, feedback) produce decision-consistent results, and what minimum data each equation actually requires in practice. Be explicit about what could not be validated and why. Prioritise reproducible, runnable evidence over conceptual agreement.

### Designing and building a seeded enterprise simulator as the harness testbed

File: `research/seeded-enterprise-simulator-design.md`

Design the missing evaluation artifact: a mechanistic, seeded, isolated enterprise simulator whose terminals reconcile to a double-entry ledger and which exposes a constrained action surface for an agent. Survey the components that would have to be assembled — system-dynamics stock-and-flow engines (Vensim, PySD, AnyLogic), agent-based modelling frameworks (Mesa, NetLogo, Mesa-Geo), business/ERP simulation games and reference models (Beer game, MIT Beer Game, Littlefield, CESIM/Marketplace simulators, Vending-Bench, Back Bay Battery, CEO-Bench), and synthetic-ledger/double-entry generators — and assess which can be composed versus rebuilt. Specify the ledger reconciliation guarantees, the observation surface (statements, KPIs, event feed), the action surface (price, spend, hiring, inventory, capacity, credit), the seeding and determinism contract, the constraint-enforcement layer, and the held-out scenario generation. State the minimum viable build, its likely cost in person-months, and how it would be validated against historical firm behaviour.

### Benchmarking the middle layers: bootstrapping capability, process, and unit-economics benchmarks

File: `research/middle-layer-benchmarks-xbrl.md`

Address the thin benchmark coverage between the transaction layer and strategy. Assess whether capability-level, process-level, and unit-economics benchmarks can be bootstrapped from public data — SEC EDGAR XBRL, Companies House, Damodaran datasets, and specialised schemas (DORA, SOC/ISO metrics surveys, vendor benchmark reports) — and quantify the comparability erosion caused by XBRL extension-taxonomy usage, restatements, and taxonomy migration. Propose a methodology for constructing layer-aware peer benchmarks: peer-matching (SIC/NAICS/self-classification, size/age/geography), metric normalisation, and confidence intervals, plus how to validate a benchmark against an internal first-party series. Include concrete evidence on the coverage and quality of public capability/process proxies (gross-margin decomposition, revenue-per-employee, CAC/LTV surrogates) and name what remains genuinely unbenchmarkable from public sources.

### Measuring graph survival and adoption: base rates for maintained business graphs

File: `research/graph-survival-adoption-rates.md`

Quantify the survivorship problem. Find and synthesise evidence on the base rate at which enterprise knowledge-graph, digital-twin, semantic-layer, and finance-data-platform projects are still alive and consumed N years after launch — funding, adoption, DAU/query counts, maintenance commits, deprecation notices, and abandonment. Survey longitudinal and empirical studies (enterprise ontology/KG adoption surveys, data-platform failure studies, Standish/CHAOS-style project outcome statistics, OSS repository-lifecycle research and dependency-decay studies), and derive or bound the base rate for "a maintained instance graph that improved a decision". Identify the strongest measured predictors of survival and consumption (named owner, consuming product, enforced change process, narrow scope), distinguish vendor/analyst claims from independent evidence, and state how much the earlier survivor/failure narratives are likely biased by self-report. Give quantitative estimates with explicit uncertainty.

### Temporal granularity, schema evolution, and the maintenance economics of a business graph

File: `research/temporal-granularity-maintenance.md`

Specify the operational practice of keeping a business graph temporally correct and cheap to maintain. Cover bitemporal and event-time modelling, slowly changing dimensions (SCD types, Data Vault 2.0, event sourcing and Kafka/CDC patterns), effective-dated audits, point-in-time reconstruction and as-of reporting, and schema evolution/versioning (Avro/Protobuf, schema registry, graph schema migration, backward/forward compatibility, deprecation). Connect these to maintenance economics: storage and compute cost of history, reconstruction latency, the cost of schema churn, and where the granularity spectrum (per-transaction vs. per-period vs. per-decision) should sit for a given decision so the graph is deep enough to carry the decision without becoming unmaintainable. Provide case evidence (data-vault/event-sourcing implementations, point-in-time reporting recalls, schema-migration post-mortems) on what actually goes wrong and what practices hold.

### Evaluating an agentic harness on real, opaque, irreversible decisions

File: `research/opaque-real-world-harness-eval.md`

Extend the evaluation protocol from transparent simulators to real, opaque, delayed-feedback, partly irreversible business decisions. Survey methods for evaluating decision-support and autonomous agents where ground truth is unavailable, feedback arrives over quarters, and actions cannot be cleanly undone or randomised: offline/counterfactual evaluation and off-policy evaluation, synthetic control and difference-in-differences for single-firm interventions, uplift and heterogeneous-treatment-effect validation, pre-registered decision protocols, shadow-mode and champion/challenger deployment, the irreversibility/reversibility ladder for actions, and the literature on evaluating irreversible high-stakes AI decisions (human-oversight and escalation design, Article 14-style oversight, audit trails and decision logs). Adapt the constraint-violation battery and the roll-forward counterfactual to this setting, specify what can and cannot be falsified without a simulator, and define the acceptance tests that would let a real business trust the harness to act. Be explicit about the residual risks that no evaluation can remove.

## Round 4

### Executing the transformation-algebra instantiation on the OCEL inventory simulation

File: `research/algebra-instantiation-execution.md`

Move the reconciliation identity from a proposed test protocol to an executed result. Locate the OCEL 2.0 "Inventory Management Database and OCELs" and the deterministic synthetic relational databases (seed 20260820), and specify — with actual equations, field mappings, and step-by-step code-level procedure using PM4Py/ocpa and a synthetic double-entry layer (Beancount or equivalent) — a runnable experiment that computes `NI_GAAP`, `NP_TA`, `ΔInventory`, and `overhead/unit`, evaluates `residual = NI_GAAP − (NP_TA + ΔInventory × overhead/unit)`, and separately reports the under/over-absorption variance term and the multiple-overhead-pool sum version. Include the falsification controls (flat inventory ⇒ profits equal; deliberately truncated opening balance ⇒ identity must break). Where full execution is impossible without running the code, give the complete specification another engineer could execute verbatim, the exact expected orders of magnitude, and the specific failure signals to look for. State precisely what this experiment would and would not establish. Prioritise reproducibility and runnable detail over conceptual description.

### A minimum-viable ledger-plus-articulation prototype: build specification and true cost

File: `research/mvb-ledger-articulation-prototype.md`

Specify, at build detail, the smallest prototype that demonstrates reconciled three-statement projection from a single append-only journal: the account/schema design (integer minor units, chart of accounts, journal entry structure), the fail-closed invariants (per-entry balance, global roll-up, `A = L + E`, retained-earnings roll-forward, cash-flow articulation, trial balance), the projection code that emits the three statements plus a KPI bundle, period close mechanics, reversing-entry corrections, and a seeded synthetic event generator that drives it. Ground the design in the concrete reference implementations already surveyed (TigerBeetle invariants, Formance storage-layer double-entry, Blnk, `ducal7/ledger-reconciliation`, Penrose AccountingBench stored-procedure writes, Beancount, the Gronewald synthetic GL). Then specify how the true cost would be measured: time to first balanced trial balance, time to first correctly articulating three-statement close, hidden effort in edge cases (accruals, prepayments, depreciation, deferred revenue, tax, FX, intercompany), and the reconciliation test suite. Find any empirical evidence of accounting-close/automation build costs and control effort. Conclude with what this prototype would prove and what it would leave unproven.

### Designing a prospective inception-cohort study of business-graph survival

File: `research/graph-survival-cohort-study-design.md`

Design the study that would correct the survivorship problem in business-graph projects. Specify a prospectively defined inception cohort: recruitment at first commit/first spend, pre-registered covariates (named owner, intended consuming decision, budget line, scope breadth, enforced change process, technology choice, team size), the three separate outcome definitions (artifact survival, active consumption, decision impact), objective consumption instruments (query logs, API calls, lineage dependencies) rather than surveys, a mandatory retirement/failure registry analogous to the Apache Attic, blinded coding of decision impact from decision records, and a hazard-rate/Kaplan–Meier analytic plan with pre-registered predictors and power calculations. Use existing cohort and registry methodologies (OSS repository survival studies, Apache Attic, clinical trial registration, DevOps/State-of-DevOps panel design) as templates, and state sampling frame, recruitment bias controls, follow-up schedule, and stopping rules. Include what N and follow-up duration would be needed to detect the predictors hypothesised from existing evidence, and how the study would be governed and pre-registered. Be concrete and falsifiable.

### Empirically sizing the XBRL comparability tax on middle-layer benchmarks

File: `research/xbrl-comparability-tax-measurement.md`

Turn the theoretical comparability erosion of public XBRL data into a measurable quantity with a concrete method and expected magnitudes. Specify a study that: (1) builds a peer set from SEC EDGAR frames/companyfacts/FSDS using preferred us-gaap tags vs. documented fallback aliases for a chosen set of middle-layer metrics (revenue, COGS, gross margin, S&M intensity, DSO/DPO/DIO); (2) computes each firm's percentile under preferred vs. fallback tag choices; (3) measures the resulting percentile movement and the share of firms changing decile; (4) repeats under restatement-aware (as-filed vs. as-restated) and taxonomy-version-aware views; (5) quantifies effective sample size per metric and the effect of SIC↔NAICS/self-classification peer matching. Anchor expected magnitudes to the published extension-use rates, the ~63% pairwise non-comparability finding, and Debreceny-type extension classifications. State exactly which metrics are robust and which are fragile, give the decision rule for when a metric is "benchmarkable for a given firm" (e.g. percentile movement < one decile under alias substitution), and provide a code-level procedure referencing the SEC APIs. Prioritise concrete, reproducible measurement over narrative.

### Cross-corpus confidence calibration: weighting observed, directional, and constructed evidence

File: `research/cross-corpus-confidence-calibration.md`

Build a methodology for calibrating confidence across a heterogeneous research corpus whose evidence ranges from directly observed to vendor-adjacent to proposed-by-construction. Survey formal approaches to evidence appraisal and confidence aggregation — GRADE and its software/data analogues, evidence hierarchies, expert elicitation and structured priors (Delphi, calibrated probability elicitation), the Cochrane risk-of-bias framing, forecasting-tournament calibration (Tetlock/Good Judgment) and scoring rules (Brier), Tiered Evidence frameworks, and reproducibility/credibility rubrics (e.g. for ML benchmarks) — and adapt them into a scheme for scoring each claim by evidence type, directness of observation, independence, sample size, and replication. Apply the scheme to the specific corpus strata: directly observed (OSS survival, XBRL extension rates, public OCEL benchmarks), vendor/analyst-adjacent (KG pilot-to-production, digital-twin adoption, AI-pilot-to-production), and constructed/proposed (the transformation algebra, the enterprise simulator, the reference ontology). Recommend how to combine or *decline to combine* incompatible strata, how to represent confidence when a claim rests on one self-reported source, and how to propagate uncertainty into a decision (e.g. expected-value-with-interval framing). Include concrete worked examples scoring a handful of the claims above, and explicit rules for when the honest output is "insufficient evidence."

## Round 5

The open questions across the first four rounds are now predominantly *measurements*, not arguments. Round 5 therefore shifts from specifying to executing: agents may write and run code in the workspace, fetch real public datasets, and record actual results. Where a full run is genuinely infeasible, the deliverable is a complete, executable artifact plus the exact expected output and failure signals — never a conceptual restatement. Every file must still read as standalone research with typed citations.

### Building and measuring the minimum-viable ledger-plus-articulation prototype

File: `research/ledger-prototype-build.md`

Turn the ledger-plus-articulation specification into a working, measured prototype. Implement (in the workspace, in a language with a real double-entry/decimal story — e.g. Python with `decimal`/integer minor units, or an existing reference library) a single append-only journal with typed accounts, the fail-closed invariants (per-entry `Σdebits = Σcredits`, trial balance, `A = L + E`, retained-earnings roll-forward, cash-flow articulation to balance-sheet cash), a projection layer emitting the three statements plus a KPI bundle, period close via new entries, and reversing-entry corrections. Drive it with a seeded synthetic event generator, and then **measure**: time/effort to first balanced trial balance, time to first correctly articulating three-statement close, the hidden effort for each hard edge case (accruals, prepayments, depreciation, deferred revenue, tax, FX, intercompany eliminations), lines of code per invariant, and the test suite that proves each articulation. Report which edge cases were cheap, which were disproportionately expensive, and what the prototype does and does not establish (mechanics exactness vs. economic realism vs. agent behaviour). Prioritise a runnable repo and recorded measurements over prose; cite external sources for any design element borrowed from a reference implementation.

### Executing and reporting the GAAP/throughput reconciliation on the inventory simulation

File: `research/algebra-reconciliation-execution.md`

Move the reconciliation identity from protocol to executed result. Obtain or reconstruct the OCEL 2.0 inventory-management event data (or a faithful synthetic equivalent generated from the documented schema/seed), map it to stocks, flows, and `ΔInventory`, pair it with a synthetic double-entry layer (Beancount or an equivalent ledger built in the workspace), and compute `NI_GAAP`, `NP_TA`, `ΔInventory`, and `overhead/unit`. Evaluate `residual = NI_GAAP − (NP_TA + ΔInventory × overhead/unit)`, then separately report the under/over-absorption variance `(ActualFixedOverhead − AbsorbedFixedOverhead)` and the multiple-overhead-pool sum form. Run the falsification controls (flat inventory ⇒ profits equal; deliberately truncated opening balance ⇒ identity must break) and record the observed outputs. Report the actual numbers produced, the orders of magnitude, every place the identity broke and why, and the exact minimum data each equation required in practice. State precisely what the run establishes (timing/flow consistency) and what it cannot (valuation validity without the synthetic ledger; cash leg, capacity, and mission constraints untouched). Runnable code, actual outputs, and reproducible seeds take priority over narrative.

### Executing the XBRL comparability-tax measurement on a real EDGAR sample

File: `research/xbrl-comparability-tax-execution.md`

Run the comparability-tax study on real filings. Using the SEC EDGAR frames/companyfacts/FSDS APIs (respecting rate limits and a declared User-Agent), assemble a peer sample for a chosen set of middle-layer metrics (revenue, COGS, gross margin, S&M intensity, DSO/DPO/DIO), and for each firm compute its percentile under a preferred-us-gaap-tag regime versus a documented fallback-alias regime. Then compute the operational vector (`tax_median`, `tax_decile`, `tax_coverage`, `tax_nE`), the share of firms changing decile, and effective sample size per metric, and repeat under restatement-aware (as-filed vs. as-restated) and taxonomy-version-aware views and under SIC↔NAICS peer matching. Report the actual measured numbers on the sample, which metrics proved robust vs. semi-robust vs. fragile under the five-condition decision rule, the code-level procedure (with the query logic), and the sensitivity of conclusions to the peer-set and alias-choice choices. If API access, licensing, or rate limits block a full run, execute on the largest feasible subset and report exactly how much was measured and what remains. Concrete, reproducible measurement is the deliverable.

### Designing and piloting an open abandoned-graph / retirement registry

File: `research/abandoned-graph-registry.md`

Design the missing denominator for survival measurement: an open registry that records the death/retirement of enterprise knowledge-graph, digital-twin, semantic-layer, and finance-data-platform artifacts, analogous to the Apache Attic and to OSS dependency-decay registries. Specify submission criteria and triggers (deprecation notice, last consumer removed, funding cut, replacement), the minimal record schema (artifact, steward, time-zero definition, death date, cause, replacements, evidence link), governance and incentives for honest reporting (including who benefits from disclosure and how to handle confidential internal deaths), deduplication against the survivorship bias in OSS-only samples, and the analytic uses (base-rate estimation, cohort/hazard inputs for the prospective study). Survey existing templates (Apache Attic, endoflife.date, libraries.io/deps.dev deprecation signals, CHAOS-style post-mortems, academic registry designs) and pilot the registry: define a seed set of a few dozen real retired or abandoned artifacts with sourced death dates, or run a structured scan of public repositories/announcement archives to populate it. Report the pilot's actual yield, the false-positive/false-negative problems encountered, and whether such a registry is practically sustainable. Be concrete and falsifiable.

### Auditing the corpus: applying the confidence rubric to every claim

File: `research/corpus-confidence-audit.md`

Apply the cross-corpus confidence-calibration scheme to the claims of this corpus and produce the audit. Review the prior topic files and extract the load-bearing claims, then score each on the five dimensions (evidence type, directness of observation, independence, sample/replication, bias/motive), record the tier, and flag every claim that (a) rests on a single self-reported or vendor-adjacent source, (b) cites another claim in the corpus rather than an independent source, or (c) is a constructed/proposed artifact presented near observed evidence. Produce a claims register (claim, tier, dimension vector, weakest link, the single measurement that would most raise its confidence) and a summary by corpus stratum. Then compute the highest-value next measurements using an expected-value-of-information / EVSI framing against a small set of representative decisions (e.g. "should we build the graph, and how thin?"). End with the corpus's overall evidence posture and the explicit list of load-bearing claims for which the honest output is "insufficient evidence." The deliverable is the audit itself — a register and a ranked measurement agenda — not new external research.

## Round 6

Round 5 executed measurements on synthetic and public scaffolding and found that the ambiguities narrowed while the load-bearing uncertainty moved. Round 6 pushes each executed artifact one step closer to the world: real double-entry data, non-US XBRL jurisdictions, a running agent, real financial dynamics, and a re-scored register. Agents may write and run code, fetch real public data, and record actual results; where a full run is infeasible, the deliverable is still a complete executable artifact plus exact expected output and failure signals.

### Reconciling the algebra against real double-entry data and adding the cash-articulation leg

File: `research/real-ledger-reconciliation.md`

Move the reconciliation from a synthetic ledger to real double-entry sources, and test the leg the synthetic run left untouched. Locate and obtain a real, public double-entry corpus (open ledgers such as GnuCash/sample accounting datasets, Open Collective or municipal open-books exports, the Gronewald synthetic GL used as a bridge, or an anonymised corporate trial-balance dataset) and, separately, use real filer data (SEC XBRL companyfacts cash-flow statement + balance sheet) to run the **cash-articulation** invariant: terminal cash from the cash-flow statement must equal balance-sheet cash, and the retained-earnings roll-forward must hold under as-filed and as-restated vintages. Then attempt the GAAP/throughput identity on a real firm's inventory, income, and cost data where such data is public, reporting every place the clean identity fails and whether the failure is an absorption variance, a data-availability artefact, or a genuine modelling error. Report the actual residuals and the exact data each leg required. State precisely how much of the identity survives contact with real data and what remains unvalidatable without internal cost accounting. Runnable code and actual outputs take priority over narrative.

### Recovering the comparability tax with alias unions, and extending to EU/UK filings

File: `research/esef-alias-union-coverage.md`

Attack the problem the measured tax exposed: coverage loss, not tag disagreement, dominates, and alias-union peer cells were proposed but not tested. Build a documented alias-union/extended-tag mapping for the middle-layer metrics and measure how much of the 41–74% coverage loss it recovers, re-computing the coverage-inclusive `tax_decile` and effective sample size before and after. Then extend the measurement beyond US filers to at least one non-US jurisdiction — EU ESEF filings (via the ESEF/IFRS taxonomy and an accessible source such as the filings API or a bulk dataset) and/or UK Companies House — and report whether robust/semi-robust/fragile verdicts transfer, where the alias structure differs, and whether the "standard-tag pluralism" finding holds outside us-gaap. Provide the query/procedure code and actual measured numbers on the samples reached, and state how much coverage the alias union can and cannot restore.

### Running an agent against the ledger: constraint violations, spec-gaming, and long-horizon coherence

File: `research/agent-harness-constraint-eval.md`

Turn the evaluation protocol from a design into a run. Using the working ledger prototype (or an equivalent seeded simulator) plus a constrained action surface (price, spend, inventory, capacity, credit, with reversibility flags) and a small set of held-out scenario tiers, run one or more LLM agents (and a rule-based baseline) through repeated decision cycles. Instrument and measure: profit and future position, hard-constraint violations (insolvency, negative inventory, covenant breach), soft-constraint/values violations, and the specific failure modes the literature predicts — spec-gaming (exploiting the acceptance check), collusion or price-fixing when multiple agents interact if feasible, and long-horizon coherence decay. Report actual scores, violation counts, and where the agent found loopholes in the graders. If a full multi-agent run is infeasible, run single-agent against the ledger and specify the multi-agent extension. Conclude with what the graders catch, what they miss, and how the acceptance tests need to change.

### Validating the simulator's economic realism against real financial dynamics

File: `research/simulator-realism-validation.md`

Establish the empirical target the simulator must hit by measuring real stylised facts, then assess a simulator against them. From public data (SEC XBRL / EDGAR companyfacts, Damodaran datasets, Companies House, or accessible CRSP-like panels), measure a small set of robust firm-level regularities a credible enterprise simulator should reproduce — firm size distributions (heavy tails), growth-rate distributions and their variance–size relation, profit persistence/mean reversion, gross-margin dispersion by industry, working-capital-cycle distributions, and the inventory/output dynamics implied by the OCEL data — and report the actual distributions and moments. Then define the validation battery (stylised facts, calibration to real series, event-log replay) and, using the existing seeded generator, assess the simulator's fit to at least one or two measured regularities, reporting where it matches and where it fails. Be explicit that matching stylised facts is necessary but not sufficient for behavioural realism, and state what a simulator cannot be validated against with public data.

### Re-scoring the evidence register and updating the measurement agenda

File: `research/evidence-register-rescore.md`

Maintain the corpus's epistemic discipline as executed measurements replace constructed artifacts. Re-score the load-bearing claims from the existing claims register in light of the Round 5/6 executed results: promote constructed/proposed claims to observed where they have now been measured (the reconciliation identity, the ledger invariants, the measured tax, the registry pilot), demote any claim the measurements disconfirm, and add the new load-bearing claims the measurements created. Keep the same five-dimension scheme and tier boundaries, flag remaining single-source/corpus-internal/constructed-near-observed hazards, and recompute the expected-value-of-information ranking of the *remaining* open measurements. Report the before/after tier distribution by stratum, the claims that changed tier and why (with the specific measurement that justified the change), and the updated ranked agenda. The deliverable is the re-scored register and the delta, not new external research.
