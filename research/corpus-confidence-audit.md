# Corpus Confidence Audit: Applying the Calibration Scheme to Every Load-Bearing Claim

## 1. What this audit does

This document applies the five-dimension confidence-calibration scheme to the load-bearing claims of the business-as-machine corpus. The scheme scores each claim on evidence type (a), directness of observation (b), independence (c), sample size / replication (d), and bias / motive pressure (e), each 1–5; combines them by geometric mean, `C = (Π d_i)^(1/5) / 5`; and maps `C` to GRADE-style tiers — **High** 0.80–1.00, **Moderate** 0.65–0.79, **Low** 0.45–0.64, **Very low** 0.00–0.44.

Three guardrails override the arithmetic. A claim resting solely on a constructed artifact scores 1 on directness and cannot exceed Low. A claim whose only support is one interested self-report caps at C ≤ 0.5. Repeated non-independent citation counts as one source. Constructed coherence is not external validity.

The register below records, for each claim: its dimension vector, tier, weakest link, and the single measurement that would most raise its confidence. Dimension vectors are the primary output; `C` is a communication device and ranking key, not a precision measurement. Claims are grouped into four strata — directly observed, vendor/analyst-adjacent, constructed/proposed, and structural/conceptual — because these strata measure different quantities and must not be pooled into a single "evidence score." The register is followed by explicit flag lists, a stratum summary, a value-of-information measurement agenda, the corpus's overall posture, and the load-bearing claims whose honest status is "insufficient evidence."

## 2. The claims register

### 2.1 Directly observed stratum

| ID | Claim | (a,b,c,d,e) | C | Tier | Weakest link | Measurement that would most raise confidence |
|----|-------|-------------|---|------|--------------|----------------------------------------------|
| A1 | More than half of GitHub repositories from four 2016 ecosystems are dead within ~4–5 years | (5,5,4,5,5) | 0.96 | High | External validity — GitHub survival ≠ enterprise-graph survival | None for the claim; the *transfer* is the weak part and needs an enterprise inception cohort |
| A2 | ~15% of widely-used npm packages are abandoned within six years; an EOL notice raises downstream removal hazard 1.58× (95% CI 1.26–1.98) | (5,5,4,5,5) | 0.96 | High | Ecosystem-specific; hazard is conditional on a published notice | Replication in a non-npm ecosystem |
| A3 | SEC XBRL custom-tag (extension) rate is ~17–18% of tags, full filing population, 2023–24 | (4,5,5,5,4) | 0.92 | High | Definition-dependence (line-item vs. all tags) | Fix one tag-classification convention and recompute the census |
| A4 | On average ~63% of XBRL data elements are non-comparable between a pair of firms | (4,4,4,4,5) | 0.84 | High | Single study and a definitional comparability criterion | Independent replication across EDGAR frames with a pre-registered criterion |
| A5 | ~40% of XBRL extensions are "unnecessary" | (3,4,3,3,4) | 0.67 | Moderate | The judgement "unnecessary" is coder-dependent | Re-code a sample with explicit, pre-registered necessity criteria |
| A6 | 78% of developed-market companies restate audited annual revenue at least once within 400 days | (3,4,3,4,3) | 0.67 | Moderate | Opaque vendor data product | Independent reconstruction from EDGAR as-filed vs. as-restated |
| A7 | 18,797 restatements by 10,581 firms, 1995–2020, peaking at 1,935 in 2006 | (4,5,4,5,4) | 0.88 | High | Coverage skew to certain filer classes | None material |
| A8 | Automated process-discovery is benchmarked on 12 public and 12 proprietary real-life event logs | (5,4,5,4,5) | 0.92 | High | Representativeness of the benchmark population | Domain-coverage audit against enterprise process mix |
| A9 | The OCEL 2.0 specification exists and is tool-supported | (5,5,4,3,5) | 0.86 | High | Existence of the spec says nothing about benchmark representativeness | Coverage study of OCEL logs vs. real enterprise processes |
| A10 | The Standish CHAOS "16% success" figure is unsound (outcome-sampled, undisclosed data) | (4,4,5,4,5) | 0.88 | High | None material | None |
| A11 | Aggregate ESG rating correlations range 0.38–0.71, governance only ~0.30 | (4,4,5,4,5) | 0.88 | High | Raters disagree more at firm level than in aggregate | Firm-level replication |
| A12 | There is no correlation between a firm's published values and employee-perceived culture (500+ firms, 1.2M reviews) | (3,4,4,5,4) | 0.79 | Moderate | Measures perception, not enacted behaviour | Pair survey with behavioural/guardrail records |
| A13 | 80% of Global Fortune 500 do not quantify environmental impacts via life-cycle assessment | (4,4,4,4,5) | 0.84 | High | Large-firm sample only | Extend to mid-cap filers |
| A14 | EU AI Act Article 14 requires effective human oversight of high-risk systems | (4,5,5,5,5) | 0.96 | High | Applicability thresholds and phase-in dates | None |
| A15 | Announced new-product delays reduced market value ~5.25% on average (101 firms) | (4,4,4,3,5) | 0.79 | Moderate | 1991 data; transfer to current markets | Modern replication |

### 2.2 Vendor/analyst-adjacent stratum

| ID | Claim | (a,b,c,d,e) | C | Tier | Weakest link | Measurement that would most raise confidence |
|----|-------|-------------|---|------|--------------|----------------------------------------------|
| B1 | Fewer than 15% of enterprise knowledge-graph projects move past pilot | (2,2,2,2,2) | 0.40 | Very low | Single interested vendor synthesis | Independently instrumented pilot-to-production census |
| B2 | 13% of IoT-implementing organisations used digital twins and 62% planned/establishing (2019) | (3,2,2,3,2) | 0.47 | Low | "Planning" inflates adoption; vendor survey | Objective deployment instrumentation |
| B3 | 29% of manufacturers had implemented a digital-twin strategy in 2023 | (3,2,2,3,2) | 0.47 | Low | Vendor-adjacent, self-classification | Independent deployment census |
| B4 | On average 54% of AI projects move from pilot to production (Gartner survey) | (2,3,3,3,2) | 0.51 | Low | Self-report of what counts as "production" | Instrumented deployment census |
| B5 | 95% of generative-AI pilots deliver no measurable P&L impact (MIT NANDA) | (2,2,2,3,2) | 0.43 | Very low | Method undisclosed; narrow success definition | Pre-registered P&L-impact measurement |
| B6 | 60% of AI projects will be abandoned through 2026 (Gartner forecast) | (2,2,2,2,2) | 0.40 | Very low | Forecast from self-selected leaders | Retrospective survival audit |
| B7 | Digital-twin artifacts died young (Predix ~3 yrs, Google Cloud IoT Core ~5 yrs) | (4,5,2,2,4) | 0.63 | Low | Single coder, N = 2 within a 38-record pilot | Independent coding and a larger harvest |
| B8 | Named owner, consuming product, budget line, narrow scope, enforced change process predict survival | (3,2,2,2,3) | 0.47 | Low | Practitioner anecdote, not measurement | The prospective inception cohort |
| B9 | Most enterprise graphs die by year two to three | (3,2,2,3,3) | 0.51 | Low | Anecdotes are drawn from visible cases | Inception cohort with the dead retained |
| B10 | System-dynamics programmes delivered >$800M quantified benefit across 100+ projects | (2,2,2,2,2) | 0.40 | Very low | Self-reported consultancy figure | Independent programme audit |
| B11 | Cloud warehouse storage clusters at ~$20–23/TB/month; immutable micro-partitions can amplify a frequently-updated table ~25× | (2,3,3,2,2) | 0.47 | Low | Vendor pricing pages and practitioner blogs | Vendor-neutral instrumented cost study |
| B12 | Poor data quality costs ~$12.9M per large enterprise per year | (2,2,2,3,2) | 0.43 | Very low | Analyst estimate, method not reproducible | First-party instrumented data-quality costing |

### 2.3 Constructed/proposed stratum

All entries here score 1 on evidence type and 1 on directness by construction; the guardrail caps them regardless of internal elegance.

| ID | Claim | (a,b,c,d,e) | C | Tier | Weakest link | Measurement that would most raise confidence |
|----|-------|-------------|---|------|--------------|----------------------------------------------|
| C1 | A minimal, internally consistent ~16-equation transformation algebra exists over one graph | (1,1,3,3,5) | 0.43 | Very low | No external calibration; measures itself | Use it to predict an observable and check against XBRL/repo data |
| C2 | `NI_GAAP = NP_TA + ΔInventory × overhead/unit` holds exactly | (1,1,3,3,5) | 0.43 | Very low | True only in the variance-free, single-pool case | Run the OCEL + synthetic-ledger procedure and report residual + absorption variance |
| C3 | A seeded enterprise simulator is the required validation testbed | (1,1,3,2,5) | 0.40 | Very low | The artifact does not yet exist | Build it and calibrate against historical firm behaviour |
| C4 | An REA core plus a small driver set reproduces three-statement projections | (1,1,3,2,4) | 0.38 | Very low | Untested; schema sufficiency argued, not shown | Build the thin graph and reconcile to real statements |
| C5 | A seven-layer stack (transactions→…→strategy) projects from one typed graph | (1,1,3,2,5) | 0.40 | Very low | Untested cross-layer edge semantics | Instantiate two adjacent layers and validate the typed edges |
| C6 | Fail-closed double-entry invariants yield an exact three-statement articulation | (1,1,3,2,5) | 0.40 | Very low | Not built; hidden edge-case effort unknown | Build it; measure time to first correctly articulating close |
| C7 | Build-cost brackets: thin layer ~1–3 pm; multi-entity ~4–9 pm; full REA ~9–18 pm | (3,3,2,2,3) | 0.51 | Low | Mixed first-person evidence, small N | Standardised, instrumented build-time study |
| C8 | A prospective inception cohort (N = 400, 48–60 mo) detects hazard ratios ≤ 1.5 | (1,1,3,3,5) | 0.43 | Very low | The design is validated (power math) but the world is untested | Launch the cohort |
| C9 | The compound event "graph at three years maintained, consumed, and tied to an improved decision" is ~5% (range 1–20%) | (1,2,1,2,2) | 0.30 | Very low | Chains a vendor figure with observed OSS numbers into an unfalsifiable composition | The prospective cohort plus the retired-artifact registry |
| C10 | An abandoned-graph registry is designable and cheap to pilot (38 sourced records) | (2,3,2,2,4) | 0.50 | Low | Single-coder harvest; time-zero sourceable in only 39% | Independent re-harvest and time-zero capture at inception |

### 2.4 Structural, definitional, and conceptual claims

| ID | Claim | (a,b,c,d,e) | C | Tier | Weakest link | Measurement that would most raise confidence |
|----|-------|-------------|---|------|--------------|----------------------------------------------|
| D1 | Little's law (WIP = throughput × cycle time) | (5,5,4,5,5) | 0.96 | High | Deductive theorem; holds only for stable systems | None (assumption audit only) |
| D2 | Double-entry identity `A = L + E` | (5,5,5,5,5) | 1.00 | High | Definitional | None |
| D3 | Stock–flow conservation | (5,5,5,5,5) | 1.00 | High | Definitional / theorem | None |
| D4 | The GAAP/throughput gap decomposes into the absorption-variance term (as an accounting definition) | (4,5,4,4,5) | 0.88 | High | Definitional, so it cannot fail — it explains, it does not predict | Apply to real filings and check magnitude |
| D5 | Conway's law: organisational structure constrains system design | (3,3,4,3,4) | 0.67 | Moderate | Foundational claim, modern quantitative support partial | Cross-firm covariance of team graph and system graph |
| D6 | Team cognitive load bounds service size | (2,2,3,2,3) | 0.47 | Low | Practitioner framework | Controlled team-size/product-scope study |
| D7 | An hour saved on a non-constraint is a mirage (TOC) | (2,2,3,2,3) | 0.47 | Low | Assertion from a normative framework | Factory/store experiment isolating the constraint |
| D8 | Optimising exploitation locally is self-destructive over the long run (March 1991) | (2,2,4,2,5) | 0.55 | Low | Formal toy model; real-firm evidence thin | Longitudinal firm panel on exploration/exploitation balance |
| D9 | Development speed relates curvilinearly to success ("too much of a good thing") | (4,3,4,4,5) | 0.79 | Moderate | Meta-analysis heterogeneity; context-dependence | Context-stratified replication |
| D10 | Goodhart's law — a measure used as a target ceases to be a good measure | (2,3,3,3,4) | 0.59 | Low | Widely asserted; the useful variant taxonomy is under-measured | Field experiment measuring proxy–goal divergence |
| D11 | Reward hacking / proxy over-optimisation persists as models scale | (4,3,3,3,5) | 0.70 | Moderate | Lab RLHF settings; transfer to business agents unproven | In-harness gaming audits on held-out tasks |
| D12 | Runtime enforcement (e.g. AgentSpec) prevented unsafe code execution in >90% of cases | (4,3,3,3,4) | 0.67 | Moderate | Single-lab evaluation, narrow task class | Independent adversarial evaluation |
| D13 | "A wholly explicit knowledge is unthinkable" (tacit knowledge) | (1,2,2,1,4) | 0.35 | Very low | Philosophical position, not an empirical measurement | Define a falsifiable operationalisation of the tacit remainder |

## 3. Flags

**(a) Claims resting on a single self-reported or vendor/analyst-adjacent source:** B1, B2, B3, B4, B5, B6, B9, B10, B12. Each is capped at Very low–Low until a non-benefiting party confirms it. B4 and B9 sit at the top of this band only because multiple independent surveys agree on *direction*, not on any point estimate.

**(b) Claims that cite another corpus claim rather than an independent source:** C2 and C6 chain to the constructed C1 algebra (the instantiation and ledger work takes the algebra's identity as given); C3 and C4 chain to each other and to the simulator design; C9 composes the vendor figure B1 with the observed A1; the "the ledger-plus-articulation layer must be rebuilt" claim (in the simulator design) cites the ledger prototype rather than an external measurement. These are internally coherent but inherit the confidence of their weakest premise, not of their most confident one.

**(c) Constructed/proposed artifacts presented near observed evidence:** C1 (transformation algebra), C2 (reconciliation identity), C4 (minimum-viable graph), C5 (seven-layer stack), C6 (ledger invariants), and C8 (cohort design) sit in the same documents as, and often adjacent to, High-tier observed claims (A1–A9, D1–D4). The proximity is the hazard: a reader moving down a single file from A3 to C2 crosses from a regulator census to a proposed identity with no change in typography. The register's separation of strata is the corrective, and the guardrail that caps constructed evidence at Low is what keeps the crossing visible.

## 4. Summary by stratum

**Directly observed (A, D1–D4).** The observed core is genuinely strong. Repository-survival, XBRL extension and comparability, process-discovery benchmarks, the OCEL specification, ESG-rating divergence, the cash-flow identity, and Little's law all score High or high-Moderate, on instrumented or regulator-published data with independent corroboration. This stratum is the only one safe to use directly as a decision input, and its main limitation is scope: every High claim is scoped to the population it measured (GitHub, npm, US filers, published logs). The *transfers* to enterprise graphs are separate, lower-confidence bridges and should be labelled as such.

**Vendor/analyst-adjacent (B).** This stratum clusters at Low to Very low. The most-cited numbers in enterprise technology — "under 15% of knowledge graphs reach production," "95% of GenAI pilots fail," "60% of AI projects will be abandoned" — are the weakest in the register, because their independence and directness are both weak and their motives are entangled with the number. The exception is B7, weak only because of its small, hand-coded sample rather than its method. The honest representation is a directional band with attribution ("vendor-adjacent estimates span 15–54% reaching production"), never a point estimate.

**Constructed/proposed (C).** All Very low, capped by guardrail. These claims are not worthless; they generate hypotheses and define what to measure. But they cannot move a decision on their own. C7 and C10 edge into Low only because they rest on (thin) first-person evidence rather than pure construction. C9 is the corpus's single most dangerous claim: it multiplies a vendor figure by observed OSS rates to yield a precise-looking "~5%," and it scores lowest of all.

**Structural/conceptual (D).** Bimodal. The identities that cannot fail (D2, D3, D4, and the theorem D1) are High *by definition*, which means they carry no empirical information about the world; they are constraints, not findings. The explanatory frameworks — Conway's law, TOC, Goodhart, March's ambiguity, tacit knowledge — are Low to Moderate, and the low directness scores correctly signal that they are lenses for interpretation, not measurements.

## 5. Highest-value next measurements (value-of-information framing)

For each representative decision, the question is whether the decision's sign is stable across the evidence interval (act on the direction) or flips inside it (the resolving measurement is the highest-value next action).

**Decision 1 — Should we build the graph, and how thin?** The decision turns on build cost (C7, Low), the claim that a thin graph reproduces statements (C4, Very low), and the survival predictors (B8, Low). The observed-survival core (A1, A2) predicts that most full builds fail, which pushes toward the thinnest artifact. Run the expected-value model across C7's bracket. Because the sign ("start thin, with one real consumer") is stable from the optimistic thin-layer cost to the pessimistic full-REA cost, and no measurement will invert the ordering of thin vs. full, the decision is robust: **act on the direction.** The one measurement that could still change *how thin* is an instrumented, first-party time-to-first-reconciled-close on a real build (C6) — that is, build it and time it. Partial EVPI here is moderate and falling with every build.

**Decision 2 — Should we trust a given XBRL-derived peer benchmark (e.g. gross margin)?** The load-bearing claims are A3 (High), A4 (High), and A5 (Moderate). Because the observed core is High, the decision is *not* uncertainty-bound in the usual sense: the direction (taxonomy-aware, layer-aware benchmarking is possible; some metrics are fragile) is stable. The high-value measurement is not more argument but the comparability-tax study itself — compute, per metric and peer cell, the percentile movement under preferred-tag vs. fallback-alias regimes and apply the "benchmarkable if movement < one decile" rule. EVPI is large for the specific fragile metrics (S&M intensity, DIO, cash-conversion cycle) and small for the robust ones (net income, total assets/equity, cash-flow lines). **Commission the per-metric measurement; do not re-litigate the aggregate.** This is the strongest case in the corpus for "the evidence is good enough to act, and the remaining uncertainty is metric-specific."

**Decision 3 — Should the harness act autonomously on irreversible moves?** The load-bearing claims are D11 (reward hacking, Moderate), D12 (runtime enforcement, Moderate), A14 (Article 14 oversight, High), and the constructed reversibility ladder. Independent sources agree on the *direction* — determinism in the harness, judgement human-authorised at the top of the reversibility ladder — so the sign is stable and the decision is to gate autonomy rather than debate it. EVPI is concentrated in D12's transfer: whether runtime enforcement holds under adversarial, business-context prompts is unmeasured, and a single independent adversarial evaluation would move D12 materially. **The highest-value measurement is an independent red-team of the enforcement layer, not another review of the alignment literature.**

**Ranked agenda.** (1) Run the OCEL + synthetic-ledger reconciliation and report the residual and absorption variance (raises C2 from Very low to a *measured diagnostic*; the single largest constructed-to-observed move available); (2) compute the per-metric XBRL comparability tax (operationalises A3/A4/A5 into a decision rule); (3) build and time the minimum-viable ledger-plus-articulation prototype (raises C4/C6 and supplies Decision 1's timing); (4) launch the prospective inception cohort and the retired-artifact registry (attacks B1, B5, B6, B8, B9, and C9 at once); (5) independently red-team the runtime-enforcement layer (raises D12). Each is a measurement, not an argument.

## Overall posture

The corpus's evidence is **strongly bimodal and honestly labelled at its best, misleading at its worst**. Its directly observed core — repository survival, XBRL extension and comparability rates, process-mining benchmarks, the published OCEL specification, ESG-rating divergence, and the accounting identities — is High-tier and decision-grade within its measured scope. Its vendor/analyst layer is Low to Very low, and its most-quoted statistics are its weakest. Its constructed layer — the transformation algebra, the reconciliation identity, the simulator, the ledger invariants, the seven-layer stack — is Very low by guardrail, and it is the layer that gives the corpus its apparent explanatory completeness.

The central risk is not that any single claim is false, but that the three strata are read as one continuous body of knowledge: a reader moving from the SEC custom-tag census to the reconciliation identity to the simulator design can absorb a constructed artifact as though it had the Regulator's confidence. The register's separation and the guardrail that caps constructed evidence at Low are the corrective. Applied correctly, the corpus's overall posture is defensible: **act on the observed core, treat the vendor band as a directional range with attribution, and use the constructed layer to generate hypotheses and structure measurements — never as evidence about the world.** The accounting identities deserve a special note: their High tier is *definitional*, so they constrain admissible models but tell us nothing empirical, and must not be counted as findings. The corpus is strongest where it stops arguing and specifies a runnable experiment; the five measurements above are where that strength should now be spent.

## Claims for which the honest answer is "insufficient evidence"

The following load-bearing claims meet at least one of the scheme's "insufficient evidence" rules — constructed-only support, a single interested source without independent confirmation, disagreement on sign, a measured quantity different from the claimed quantity with no bridge, or an interval crossing the decision threshold — and should be reported as such, each with the named missing measurement:

1. **C1 — the transformation algebra's internal consistency implies usefulness.** Constructed; measures itself. Missing measurement: an out-of-sample prediction checked against observed data.
2. **C2 — the reconciliation identity holds exactly on raw event data.** Constructed, and true only in the variance-free single-pool special case. Missing measurement: the executed OCEL + synthetic-ledger run reporting residual and variance.
3. **C9 — the "~5% compound survival" estimate.** A constructed composition of a vendor figure (B1) with observed OSS rates (A1); unfalsifiable as stated. Missing measurement: the prospective inception cohort with the dead retained in the denominator.
4. **B1 — under 15% of knowledge-graph projects reach production.** Single interested vendor synthesis, no independent confirmation. Missing measurement: an independently instrumented pilot-to-production census.
5. **B5 — 95% of generative-AI pilots yield no P&L impact.** Single self-reported source with undisclosed method and a narrow success definition. Missing measurement: a pre-registered P&L-impact study.
6. **B6 — 60% of AI projects will be abandoned through 2026.** A forecast from self-selected respondents. Missing measurement: retrospective survival auditing.
7. **B10 — system-dynamics programmes delivered >$800M of benefit.** Self-reported consultancy figure. Missing measurement: an independent programme audit.
8. **D13 — the tacit-knowledge remainder cannot be formalised.** A philosophical position, not a measurement; scored Very low. Missing measurement: a falsifiable operationalisation that would count as evidence either way.
9. **B8 — the survival predictors are *causal*.** The predictors are associational at best and anecdotal at worst; no independent source has shown they reduce the hazard. Missing measurement: the cohort that tests them as pre-registered predictors.
10. **C8 — the cohort design will detect hazard ratios ≤ 1.5 in practice.** The power arithmetic is sound, but feasibility (recruitment, retention, registry compliance) is untested. Missing measurement: the launch and first-year retention report.
11. **C3 — a seeded simulator is *required* to validate the harness.** A design assertion, not a finding; the necessity claim is unfalsified. Missing measurement: a head-to-head comparison of simulator-based and shadow-mode validation.
12. **The three-tier values boundary (predicate / weighted term / human-authorised).** A convincing synthesis, but no independent validation that the proposed line tracks real outcomes. Missing measurement: apply the partition to live decisions and measure gaming and escalation rates at the boundary.

Each of these is a *result*, not a failure: naming the missing measurement is what converts the corpus's open questions from arguments into a priced research agenda.
