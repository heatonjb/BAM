# Re-scoring the Evidence Register: What the Executed Measurements Changed

## 1. Purpose and method

This document re-scores the load-bearing claims of the business-as-machine corpus now that several of its central constructed artifacts have been built, run, and measured. It reuses the corpus's five-dimension scheme and tier boundaries unchanged: each claim is scored on **(a)** evidence type, **(b)** directness of observation, **(c)** independence, **(d)** sample/replication, and **(e)** bias/motive pressure, each 1–5; combined as the geometric mean `C = (Π dᵢ)^(1/5) / 5`; mapped to **High** 0.80–1.00, **Moderate** 0.65–0.79, **Low** 0.45–0.64, **Very low** 0.00–0.44. The guardrails hold: a claim resting solely on a constructed artifact cannot exceed Low; one supported only by a single interested self-report caps at `C ≤ 0.5`; repeated non-independent citation counts as one source.

The re-score draws on four executed measurements:

1. **The GAAP/throughput reconciliation identity**, run end to end on the public OCEL 2.0 inventory-management event log plus a declared synthetic cost layer, with falsification controls [T1: Horngren, *Cost Accounting*, ch. 8–9; T2: OCEL 2.0, "Inventory Management Database and OCELs"].
2. **The minimum-viable ledger-plus-articulation prototype**, built, run, and measured per edge case [T2: TigerBeetle; T2: Formance; T2: Beancount].
3. **The XBRL comparability tax**, measured on a live SEC EDGAR sample via the Frames, Company Facts and FSDS surfaces [T2: SEC EDGAR APIs; T1: Zhu & Wu; T1: Debreceny et al.].
4. **The abandoned-graph retirement registry**, specified and piloted on 38 sourced artifact deaths [T2: Apache Attic; T2: endoflife.date; T2: Depr.dev].

The deliverable is the re-scored register, the tier delta, and a re-priced measurement agenda — not new external research. In total **50 original claims are re-scored and 12 new claims added**, for a register of 62.

## 2. The re-scored register

### 2.1 Directly observed stratum (A)

| ID | Claim | Before (vec → C, tier) | After (vec → C, tier) | Driver of change |
|----|-------|------------------------|------------------------|------------------|
| A1 | >50% of GitHub repos from four 2016 ecosystems dead in ~4–5 yrs | (5,5,4,5,5) → 0.96, High | unchanged | — |
| A2 | ~15% of npm packages abandoned within six yrs; EOL notice raises removal hazard 1.58× | (5,5,4,5,5) → 0.96, High | unchanged | — |
| A3 | SEC XBRL custom-tag rate ~17–18% of tags, 2023–24 | (4,5,5,5,4) → 0.92, High | (4,5,5,5,4) → 0.92, High | Corroborated and decomposed: face-statement extension rate 8.8%, distinct-concept vocabulary 91.5% custom |
| A4 | ~63% of XBRL elements non-comparable between a firm pair | (4,4,4,4,5) → 0.84, High | (4,5,5,4,5) → 0.92, High | Independent operational replication: coverage-inclusive tax drops 41–74% of each peer cell |
| A5 | ~40% of XBRL extensions are "unnecessary" | (3,4,3,3,4) → 0.67, Moderate | (3,4,3,3,4) → 0.67, Moderate | Corroborated [T1: Debreceny et al.]; relevance reduced (standard-tag pluralism dominates) |
| A6 | 78% of developed-market firms restate audited annual revenue within 400 days | (3,4,3,4,3) → 0.67, Moderate | (2,3,2,3,2) → 0.47, Low | **Disconfirmed in magnitude**: measured same-concept FY2023 revenue revision is 7.0%, anchored to PCAOB ~3%/yr |
| A7 | 18,797 restatements by 10,581 firms, 1995–2020 | (4,5,4,5,4) → 0.88, High | unchanged | — |
| A8 | Process-discovery benchmarked on 12 public + 12 proprietary logs | (5,4,5,4,5) → 0.92, High | unchanged; caveat appended | The measured OCEL bundle is 187/200 events with an empty duality table |
| A9 | OCEL 2.0 spec exists and is tool-supported | (5,5,4,3,5) → 0.86, High | unchanged | Existence remains High; representativeness now measured rather than assumed |
| A10 | Standish CHAOS "16% success" is unsound | (4,4,5,4,5) → 0.88, High | unchanged | — |
| A11 | Aggregate ESG rating correlations 0.38–0.71 | (4,4,5,4,5) → 0.88, High | unchanged | — |
| A12 | No correlation between published values and perceived culture | (3,4,4,5,4) → 0.79, Moderate | unchanged | — |
| A13 | 80% of Fortune 500 do not quantify environmental impact via LCA | (4,4,4,4,5) → 0.84, High | unchanged | — |
| A14 | EU AI Act Art. 14 requires effective human oversight | (4,5,5,5,5) → 0.96, High | unchanged | — |
| A15 | New-product delays reduced market value ~5.25% | (4,4,4,3,5) → 0.79, Moderate | unchanged | — |

### 2.2 Vendor/analyst-adjacent stratum (B)

| ID | Claim | Before | After | Driver |
|----|-------|--------|-------|--------|
| B1 | <15% of enterprise KG projects move past pilot | (2,2,2,2,2) → 0.40, Very low | unchanged | No independent denominator yet |
| B2 | 13% of IoT orgs used digital twins, 62% planning (2019) | (3,2,2,3,2) → 0.47, Low | unchanged | — |
| B3 | 29% of manufacturers had digital-twin strategy (2023) | (3,2,2,3,2) → 0.47, Low | unchanged | — |
| B4 | ~54% of AI projects move pilot→production (Gartner) | (2,3,3,3,2) → 0.51, Low | unchanged | — |
| B5 | 95% of genAI pilots deliver no measurable P&L impact | (2,2,2,3,2) → 0.43, Very low | unchanged | — |
| B6 | 60% of AI projects will be abandoned through 2026 | (2,2,2,2,2) → 0.40, Very low | unchanged | — |
| B7 | Digital-twin artifacts died young (Predix ~3 yrs, IoT Core ~5 yrs) | (4,5,2,2,4) → 0.63, Low | (4,5,3,2,4) → 0.69, Moderate | Registry pilot sources and dates both deaths from multiple feed classes |
| B8 | Named owner, consuming product, budget, narrow scope, change process predict survival | (3,2,2,2,3) → 0.47, Low | unchanged | Predictors remain associational; registry flags hazards but tests no hazard |
| B9 | Most enterprise graphs die by year two to three | (3,2,2,3,3) → 0.51, Low | unchanged | Registry bounds digital-twin lifespan but supplies no denominator |
| B10 | System-dynamics programmes delivered >$800M across 100+ projects | (2,2,2,2,2) → 0.40, Very low | unchanged | — |
| B11 | Warehouse storage ~$20–23/TB/month; micro-partitions amplify ~25× | (2,3,3,2,2) → 0.47, Low | unchanged | — |
| B12 | Poor data quality costs ~$12.9M per large enterprise/yr | (2,2,2,3,2) → 0.43, Very low | unchanged | — |

### 2.3 Constructed/proposed stratum (C)

| ID | Claim | Before | After | Driver |
|----|-------|--------|-------|--------|
| C1 | A minimal ~16-equation transformation algebra exists over one graph | (1,1,3,3,5) → 0.43, Very low | (1,1,3,3,5) → 0.43, Very low | One load-bearing equation is now executed; the composition remains constructed |
| C2 | `NI_GAAP = NP_TA + ΔInv × overhead/unit` holds exactly | (1,1,3,3,5) → 0.43, Very low | (5,5,5,4,5) → 0.96, High (definitional-validated) | Reconciliation run: residual 0.0000 across three periods; variance shown internal, not additive |
| C3 | A seeded enterprise simulator is the required validation testbed | (1,1,3,2,5) → 0.40, Very low | unchanged | No simulator built; the ledger prototype is not the simulator |
| C4 | An REA core plus a small driver set reproduces three-statement projections | (1,1,3,2,4) → 0.38, Very low | (2,3,3,3,4) → 0.59, Low | Prototype projects three statements from one journal; the REA-core half unmeasured |
| C5 | A seven-layer stack projects from one typed graph | (1,1,3,2,5) → 0.40, Very low | unchanged | Untouched |
| C6 | Fail-closed double-entry invariants yield an exact three-statement articulation | (1,1,3,2,5) → 0.40, Very low | (5,5,5,3,5) → 0.90, High | Prototype built and run: correctly articulating close on every period and edge case |
| C7 | Build-cost brackets: thin ~1–3 pm; multi-entity ~4–9 pm; full REA ~9–18 pm | (3,3,2,2,3) → 0.51, Low | (4,3,2,3,4) → 0.62, Low | Prototype supplies bottom-up LOC/time; thin bracket corroborated, person-months still unmeasured |
| C8 | Prospective inception cohort (N=400, 48–60 mo) detects HR ≤ 1.5 | (1,1,3,3,5) → 0.43, Very low | unchanged | Design, not launch |
| C9 | Compound event "graph maintained, consumed, decision-improved at 3 yrs" is ~5% (1–20%) | (1,2,1,2,2) → 0.30, Very low | unchanged | Registry supplies numerator only; denominator still absent |
| C10 | An abandoned-graph registry is designable and cheap to pilot (38 records) | (2,3,2,2,4) → 0.50, Low | (4,4,3,3,4) → 0.71, Moderate | Registry pilot executed: 38 schema-conformant, source-linked records |

### 2.4 Structural/definitional stratum (D)

| ID | Claim | Before | After | Driver |
|----|-------|--------|-------|--------|
| D1 | Little's law (WIP = throughput × cycle time) | (5,5,4,5,5) → 0.96, High | unchanged | — |
| D2 | Double-entry identity `A = L + E` | (5,5,5,5,5) → 1.00, High | unchanged | — |
| D3 | Stock–flow conservation | (5,5,5,5,5) → 1.00, High | unchanged | — |
| D4 | GAAP/throughput gap decomposes into the absorption-variance term | (4,5,4,4,5) → 0.88, High | (5,5,4,4,5) → 0.91, High (definitional) | Executed: gap equals `ΔInv × oh_u` and the variance is internal |
| D5 | Conway's law | (3,3,4,3,4) → 0.67, Moderate | unchanged | — |
| D6 | Team cognitive load bounds service size | (2,2,3,2,3) → 0.47, Low | unchanged | — |
| D7 | An hour saved on a non-constraint is a mirage (TOC) | (2,2,3,2,3) → 0.47, Low | unchanged | — |
| D8 | Local exploitation is self-destructive over the long run | (2,2,4,2,5) → 0.55, Low | unchanged | — |
| D9 | Development speed relates curvilinearly to success | (4,3,4,4,5) → 0.79, Moderate | unchanged | — |
| D10 | Goodhart's law | (2,3,3,3,4) → 0.59, Low | unchanged | — |
| D11 | Reward hacking persists as models scale | (4,3,3,3,5) → 0.70, Moderate | unchanged | — |
| D12 | Runtime enforcement prevented unsafe execution in >90% of cases | (4,3,3,3,4) → 0.67, Moderate | unchanged | — |
| D13 | "A wholly explicit knowledge is unthinkable" (tacit knowledge) | (1,2,2,1,4) → 0.35, Very low | unchanged | — |

## 3. Claims that changed tier, and why

| ID | Before tier | After tier | Measurement that justified the change |
|----|-------------|------------|----------------------------------------|
| C2 | Very low | **High** | The reconciliation was executed on the pinned OCEL log plus a declared ledger: residual `0.0000` for the full-period and OCEL-only sets, `0.0000` on a 144-day real window, and `1×10⁻²³` (rounding) for the multi-pool form. High but **definitional**: it holds on any consistent ledger, constraining admissible models rather than informing us about a firm. |
| C6 | Very low | **High** | The ledger prototype was built and run (~421 core LOC; five invariants in 39 lines) and achieved a correctly articulating three-statement close on every period and routine edge case; the invariants themselves caught structural projection bugs. Scoped to synthetic events and one prototype. |
| C4 | Very low | **Low** | The prototype projects income statement, balance sheet, cash flow and KPIs as pure functions of a single append-only journal — demonstrating the *projection-from-events* half of the claim. The REA resource/event/agent core half remains unbuilt, so the tier rises only to the top of Low. |
| C10 | Low | **Moderate** | The registry pilot was executed: 38 schema-conformant, source-linked records spanning five artifact types and two steward strata, with a precise death date for 38/38. The single-coder harvest and the 39% time-zero gap keep it out of High. |
| B7 | Low | **Moderate** | The same registry pilot dates and sources the Predix and Google Cloud IoT Core deaths from Attic/vendor/news feed classes, adding independence (2→3) though not sample size. |
| A6 | Moderate | **Low** | **Demotion.** The measured vintage tax is ~7.0% same-concept FY2023 revenue revision (median spread 18.4%), bracketed above by PCAOB's ~3%/yr formal-restatement incidence — roughly an order of magnitude below the 78% claim, enough to disconfirm its magnitude. |
| A4 | High | High (0.84→0.92) | The measured coverage tax independently reproduces non-comparability by a different route (41–74% peer-cell exclusion), resolving the "single study" weak link. |
| C7 | Low | Low (0.51→0.62) | Reproducible bottom-up build evidence (core 421 LOC, ~770 total, <1 hour to first close, ~16 LOC per routine edge case, 73–85 LOC each for FX and intercompany) corroborates the thin bracket. |
| D4 | High | High (0.88→0.91) | The decomposition was executed and held; the absorption variance was located *inside* both profit figures rather than as a third term. |

One prior limitation was **refuted outright**: C2 was called "true only in the variance-free, single-pool case." The run holds `V` between −253.12 and +2,041.88 in both single- and three-pool forms, with no residual beyond rounding. The opposite is true: the base identity tolerates large absorption variance, and a ledger that *omits* the variance close produces a residual equal to `V` exactly; the additive form is the error.

## 4. New load-bearing claims created by the measurements

| ID | New claim | Stratum | (a,b,c,d,e) | C | Tier |
|----|-----------|---------|-------------|---|------|
| N1 | The under/over-absorption variance is internal to the reconciliation identity, not an additive third term; omitting the close yields residual `= V` | Structural/definitional | (5,5,5,4,5) | 0.96 | High (definitional) |
| N2 | `ΔInventory` is the identity's only fragile input: snapshot-derived `ΔInv` breaks the identity by exactly `oh_u ×` missing units, while flow-derived `ΔInv` is invariant to opening-balance truncation | Structural/definitional | (5,5,5,3,5) | 0.90 | High |
| N3 | The published OCEL bundle is a strict subset of the archived database (187 of 200 stock events; 13 omitted = 525 units) and its object-to-object duality table is empty | Directly observed | (4,5,5,3,5) | 0.86 | High |
| N4 | The five fail-closed invariants cost ~39 LOC (core ~421, total ~770); routine edge cases ~16 LOC each; FX and intercompany 73–85 LOC each and break base-entity articulation until generalised | Executed prototype | (5,5,5,3,5) | 0.90 | High |
| N5 | The invariant checks themselves surface structural projection bugs (sign errors, multi-currency cash, entity-vs-consolidated mismatch) during development | Executed prototype | (4,4,4,3,4) | 0.76 | Moderate |
| N6 | The XBRL tax is dominated by coverage loss (41–74% of each peer cell), not tag-value disagreement: pure tag-choice `tax_decile` is 0.014–0.159 while coverage-inclusive is 0.171–0.680 | Directly observed | (5,5,5,4,5) | 0.96 | High |
| N7 | No middle-layer metric is strictly robust: revenue/COGS/gross margin/DIO semi-robust; S&M and DPO fragile; DSO borders fragile; finer SIC matching *raises* the tax | Directly observed | (5,5,4,4,5) | 0.92 | High |
| N8 | Standard-tag pluralism, not custom extensions, is the main threat: the preferred revenue tag is 100% standard and 99.5% current, yet 41.4% of the measurable union does not use it | Directly observed | (5,5,4,4,5) | 0.92 | High |
| N9 | Under restatement-vintage awareness, 7.0% of firms show a same-concept FY2023 revenue revision (median spread 18.4%); 45.5% of those change a decile | Directly observed | (4,5,4,3,5) | 0.83 | High |
| N10 | Public archives recover a precise death date for 100% of institutionally-stewarded artifacts but a sourceable time-zero for only 39%; age is computable for under half | Directly observed | (4,5,4,2,4) | 0.73 | Moderate |
| N11 | Death is definition-dependent: a single death-date field generates false positives (revival, supersession, feature deprecation, merger) | Directly observed | (3,4,3,3,4) | 0.67 | Moderate |
| N12 | Digital-twin platforms (Predix ~3 yrs, Google Cloud IoT Core ~5 yrs) died younger than data platforms (8–17 yrs) | Directly observed | (4,5,3,2,4) | 0.69 | Moderate |

The new claims are mostly High-tier but must be read narrowly: each is scoped to the artifact measured — one event log, one EDGAR vintage, one prototype, one 38-record pilot. They measure *specific scaffolding*, not firms.

## 5. Remaining hazards

**(a) Single self-reported / vendor-adjacent support.** Unchanged: B1–B6, B9, B10, B12, each capping at Low–Very low until a non-benefiting party confirms it. B4 and B9 sit at the top of the band only because independent surveys agree on direction.

**(b) Corpus-internal cross-citation.** The two chains that dominated the previous list are broken: C2 and C6 no longer inherit C1's confidence, having been measured directly. Remaining: C3 and C4 chain to the simulator design (C4 now partly excused by the prototype); C9 still composes B1 with A1 and inherits its weakest premise.

**(c) Constructed artifacts near observed evidence.** C1, C3, C5 and C8 remain constructed and sit beside High-tier observations. Two *new* proximity hazards come from the measurements: the executed *mechanics* claims (C2, C6, N4) now sit beside *economic-realism* claims they do not support, and the reconciliation's High tier is **definitional** — like D2–D4 it cannot fail — so it must not be counted as an empirical finding.

**(d) Scoping hazard.** Every new High claim is a single-sample measurement; its tier is correct for the measured quantity and should not be transported to firms, jurisdictions, or cost structures outside the sample.

## 6. Before/after tier distribution by stratum

**Original 50 claims (re-scored).**

| Stratum | Before H/M/L/VL | After H/M/L/VL | Δ |
|---|---|---|---|
| Directly observed (A) | 11 / 4 / 0 / 0 | 11 / 3 / 1 / 0 | 0 / −1 / +1 / 0 |
| Vendor/analyst-adjacent (B) | 0 / 0 / 7 / 5 | 0 / 1 / 6 / 5 | 0 / +1 / −1 / 0 |
| Constructed/proposed (C) | 0 / 0 / 2 / 8 | 2 / 1 / 2 / 5 | +2 / +1 / 0 / −3 |
| Structural/definitional (D) | 4 / 4 / 4 / 1 | 4 / 4 / 4 / 1 | 0 / 0 / 0 / 0 |
| **Total** | **15 / 8 / 13 / 14** | **17 / 9 / 13 / 11** | **+2 / +1 / 0 / −3** |

A gains one Low and B loses one, so the aggregate is unchanged.

**New claims (12).**

| Stratum | H/M/L/VL |
|---|---|
| Directly observed (N3, N6–N12) | 5 / 3 / 0 / 0 |
| Executed prototype (N4–N5) | 1 / 1 / 0 / 0 |
| Structural/definitional (N1–N2) | 2 / 0 / 0 / 0 |
| **Total** | **8 / 4 / 0 / 0** |

**Combined register (62).**

| Stratum | H / M / L / VL |
|---|---|
| Directly observed | 16 / 6 / 1 / 0 |
| Vendor/analyst-adjacent | 0 / 1 / 6 / 5 |
| Constructed/proposed + executed prototype | 3 / 2 / 2 / 5 |
| Structural/definitional | 6 / 4 / 4 / 1 |
| **Total** | **25 / 13 / 13 / 11** |

The delta is small in gross terms — three constructed claims left the Very low band, one vendor claim rose — but decisive in *location*: the reconciliation and the ledger invariants crossed from "proposed" to "measured." The vendor band barely moved, because none of the measurements attacked its missing denominator.

## 7. Re-priced measurement agenda (expected value of information)

For each representative decision: if its sign is stable across the evidence interval, act on the direction; if it flips inside the interval, the resolving measurement is the highest-value next action.

**Decision 1 — Expand from the prototype to a live instance reconciled to a real firm's statements.** The measurements moved this toward "act": mechanics are proven cheap (C6, N4) and the identities hold on consistent data (C2, N1), so the sign (start thin) is stable. But the **valuation and cash-articulation leg on real double-entry data** remains unmeasured; a synthetic ledger proves internal consistency, not a real cost structure. Partial EVPI is concentrated there and is large.

**Decision 2 — Trust and ship a given middle-layer peer benchmark.** No longer uncertainty-bound in aggregate: the tax is measured and the decision rule is operational (N6–N9), with a stable sign (alias unions in wide cells; distrust S&M and DPO). The remaining uncertainty is whether the coverage loss is *repairable* — can an alias union recover the 41–74% of each cell that preferred-only extraction drops, and do the verdicts transfer outside us-gaap? Partial EVPI is large and localised.

**Decision 3 — Let the harness act autonomously on irreversible moves.** Unchanged: no agent was built. The principle-level sign is stable (gate autonomy; deterministic harness, human-authorised top of the reversibility ladder), but runtime enforcement under adversarial business prompts is unmeasured, so partial EVPI stays high. The resolving measurement is an independent agent run against the ledger.

**Ranked remaining measurements.**

1. **Real double-entry reconciliation plus the cash-articulation leg.** Run the articulation invariant on a real public ledger (an open GnuCash-style or municipal/Open Collective export) and on real filers (SEC companyfacts cash-flow statement versus balance-sheet cash, as-filed and as-restated), then attempt the GAAP/throughput identity on a real firm's inventory/income/cost data. This is the single largest remaining load-bearing uncertainty for Decision 1: it tests the valuation validity the synthetic run could not.
2. **Alias-union recovery and non-US transfer.** Build the documented alias-union mapping, re-compute coverage-inclusive `tax_decile` and effective sample size, and extend to EU ESEF and/or UK Companies House. This directly prices whether Decision 2's coverage tax is repairable and whether the robust/semi-robust/fragile verdicts transfer outside us-gaap.
3. **Independent adversarial agent run against the ledger.** Use the working prototype plus a constrained action surface and held-out scenario tiers; measure hard- and soft-constraint violations, spec-gaming, and long-horizon coherence decay against a rule-based baseline. This gates Decision 3.
4. **Simulator realism validation.** Measure real firm-level stylised facts (size/growth distributions, profit persistence, margin dispersion, working-capital cycles) and calibrate the seeded generator against one or two. Necessary but not sufficient for behavioural realism.
5. **Prospective inception cohort plus a governance-linked registry.** Recruit at first commit/first spend with pre-registered covariates and an anonymised internal tier — the only route to an unbiased survival denominator, and the remedy for B1, B5, B6, B8, B9, C8 and C9 at once, but slow and adoption-limited.
6. **Live values/brand boundary test.** Apply the predicate / weighted-term / human-authorised partition to live decisions and measure gaming and escalation at the boundary.

## Overall posture after re-scoring

The re-score confirms the corpus's central methodological claim about itself: when a proposed quantity is computed, the ambiguity narrows but the **load-bearing uncertainty moves rather than disappears**. The reconciliation identity crossed from Very low to a High-tier *definitional* result — it holds exactly, but by construction, so it tells us nothing empirical; its value is the refinement it produced, that the absorption variance is internal and the identity is a conservation check that surfaces what a ledger hides. The ledger invariants crossed to High as genuine *mechanics* results, but the run localises the real cost and risk where external validity begins: FX and intercompany generalisation, and economic realism. The XBRL tax is now measured and *redirected* the problem from tag-value disagreement to coverage loss and standard-tag pluralism. The registry pilot produced a usable numerator and a precise death-date/time-zero asymmetry, but no denominator.

The register is consequently less bimodal: the observed core is larger (23 claims, 16 High) and includes executed mechanics, the constructed band is smaller, the vendor band is untouched, and the structural stratum carries two measured identity refinements. The old hazard — absorbing a constructed artifact as though it had the regulator's confidence — is partly displaced by a subtler one: absorbing a *scoped, definitional, single-sample* measurement as a general fact about firms. The corrective is unchanged: state the scope, separate definitional from empirical High, and never let a mechanics result stand in for the realism result it does not supply.

## Remaining claims for which the honest answer is "insufficient evidence"

Each meets at least one of the scheme's insufficient-evidence rules — constructed-only support, a single interested source without independent confirmation, disagreement on sign, a measured quantity different from the claimed quantity with no bridge, or an interval crossing the decision threshold. Each is listed with its named missing measurement.

1. **C1 — the algebra's internal consistency implies usefulness.** One equation is validated; the ~16-equation composition remains constructed. Missing: an out-of-sample prediction checked against an observable.
2. **C2 (real-firm half) — the identity holds on real cost structures.** It holds on a declared synthetic ledger; valuation validity is untouched. Missing: the real-ledger/real-filer reconciliation (agenda 1).
3. **C3 — a seeded simulator is *required* to validate the harness.** A design assertion; the prototype is not a simulator. Missing: simulator-based vs. shadow-mode comparison.
4. **C5 — the seven-layer stack projects from one typed graph.** Cross-layer edge semantics untested. Missing: instantiate two adjacent layers and validate the typed edges.
5. **C8 — the cohort detects hazard ratios ≤ 1.5 in practice.** Power is sound; feasibility untested. Missing: launch and first-year retention.
6. **C9 — the "~5% compound survival" estimate.** A constructed composition of a vendor figure with observed OSS rates. Missing: the cohort with the dead retained.
7. **B1 — under 15% of KG projects reach production.** Single interested vendor synthesis. Missing: an independently instrumented pilot-to-production census.
8. **B5 — 95% of genAI pilots yield no P&L impact.** Single self-report, undisclosed method. Missing: a pre-registered P&L-impact study.
9. **B6 — 60% of AI projects will be abandoned through 2026.** Forecast from self-selected respondents. Missing: retrospective survival auditing.
10. **B8 — the survival predictors are causal.** Associational at best. Missing: the cohort that tests them as pre-registered predictors.
11. **B10 — system-dynamics programmes delivered >$800M.** Self-reported consultancy figure. Missing: an independent programme audit.
12. **D13 — the tacit-knowledge remainder cannot be formalised.** A philosophical position. Missing: a falsifiable operationalisation that counts either way.
13. **The three-tier values boundary.** No validation the line tracks real outcomes. Missing: apply it to live decisions and measure gaming/escalation.
14. **Economic realism of the ledger prototype.** Mechanical exactness is not that synthetic events resemble a firm. Missing: simulator-realism calibration (agenda 4).

Naming the missing measurement is the result: it converts each open question from an argument into a priced item on the agenda above.

## References

**Type 1 — Research papers / peer-reviewed work**

- Horngren, Datar & Rajan, *Cost Accounting: A Managerial Emphasis* (15th ed., 2015), ch. 8–9.
- Zhu & Wu, "Interoperability of XBRL Financial Statements in the U.S."; Debreceny et al., "Flex or Break?," *Accounting Horizons* 25(4):631 (2011); Dhole et al., *IJAIS* 19:29 (2015).
- Kahle & Walkling, *JFQA* 31(3):309–335 (1996).
- Ait, Cánovas Izquierdo & Cabot, *MSR '22*, 365–375; Avelino et al., *ESEM 2019*.

**Type 2 — Official documentation / specifications / technical references**

- OCEL 2.0, "Inventory Management Database and OCELs" (ocel-standard.org); Berti, Zenodo record (CC BY 4.0, 2026).
- TigerBeetle, "Debit/Credit" and "Correcting Transfers"; Formance, "Ledger"; Beancount, "Realization."
- U.S. SEC, *EDGAR APIs* (Frames, Company Facts, FSDS TAG); PCAOB, *Data Points: Financial Restatements*, DP04-2025.
- Apache Attic, "Process"/"Process Tracking"; endoflife.date, "API v1"; Depr.dev, "How Detection Works."

**Type 3 — Practitioner / community**

- MetricDuck Research, "How 2,100+ SEC Filers Actually Report Revenue in XBRL," 2026; XBRL US, "SEC Custom Tag Analysis," 2025; Hacker News AccountingBench discussion, 2025.
