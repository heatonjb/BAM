# Designing a Prospective Inception-Cohort Study of Business-Graph Survival

---

## 1. The Problem the Study Must Fix

A "business graph" — an enterprise knowledge graph, digital twin, ontology, or semantic layer that models a business as assets, liabilities, and transformations — is a long-lived *capability*, not a deliverable. Yet almost all evidence about them is drawn from still-visible projects: the sample is assembled by looking back, so only artifacts that lasted enter it, and cancelled, descoped, or quietly archived ones never reach the denominator [T3 — CASRAI, "Survivorship Bias," §"What makes it dangerous"]. This is Wald's bomber problem: damage on returning aircraft describes planes that could afford it, the engines and cockpit unmarked because hits there did not return [T3 — Al-basir, "Project Reporting Without Survivorship Bias," §"Cancelled Projects"].

Adjacent base rates suggest the missing denominator is large. Ait et al. tracked all 1,127 GitHub repositories from four ecosystems created in 2016 and found more than half dead within four years [T1 — Ait et al., MSR 2022, §5.2]. Avelino et al. found 315 of 1,932 (16%) popular GitHub projects abandoned by core developers, with only 128 (41%) recovering under new maintainers [T1 — Avelino et al., ESEM 2019, §IV]. Miller et al. found 15% of widely-used npm packages abandoned within six years, and an explicit end-of-life notice raised the downstream removal hazard 1.58× (95% CI 1.26–1.98) [T1 — Miller et al., ICSE 2025, §V.B]. Gartner predicts 60% of AI projects unsupported by AI-ready data will be abandoned through 2026, and ≥50% of generative-AI projects were abandoned after proof-of-concept [T2 — Gartner, "Lack of AI-Ready Data Puts AI Projects at Risk"; "Why Half of GenAI Projects Fail"]. Practitioner accounts converge on the same arc [T3 — The Data Praxis, "Why Most Enterprise Knowledge Graph Projects Die in Year Two"; Enterprise Knowledge, "Why Graph Implementations Fail"].

These figures are *not* a validated benchmark. Gartner's are forecasts from surveys of self-selected leaders, and the MIT NANDA "95% of GenAI pilots show no measurable return" figure rests on a narrow P&L-within-six-months read [T3 — Trew Knowledge, "Why So Few AI Pilots Reach Production"]. The field's most-cited failure statistic — Standish CHAOS's claim that 16% of IT projects succeed — is unsound: Standish recruited respondents by asking them to "share failure stories," sampling on the outcome [T1 — Glass, *CACM* 49(8), 2006; Jørgensen & Moløkken-Østvold, *Inf. Softw. Technol.* 48(4), 2006; Eveleens & Verhoef, *IEEE Software*, 2010]. The fix is not to swap one biased convenience sample for another but to *define the cohort at inception and keep the dead in it*. This document specifies that study.

---

## 2. Methodological Templates

### 2.1 Open-source repository survival studies

OSS research supplies a definition of survival: Ait et al. call a project alive if it shows any human activity in the last six months of the window, dead otherwise, computing survivor functions with confidence intervals and explicit censoring [T1 — Ait et al., 2022, §5.2]. Avelino et al. use a threshold-based "abandoner" rule and count a project as surviving only if it returns to Active after abandonment [T1 — Avelino et al., 2019, §II.C]. Valiev's PyPI/npm study defines dormancy as fewer than one commit per month on a twelve-month trailing average and models it with Cox proportional hazards, noting false positives from "completed" projects and revivals [T1 — Valiev, "External Factors in Sustainability of OSS," §2.3–2.4.3].

### 2.2 The Apache Attic as a retirement registry

The Apache Software Foundation's Attic is the closest existing *mandatory retirement registry* and the most transferable template [T2 — Apache Attic, homepage; "Process," §1–6]. A project enters when its PMC cannot muster three votes for a release, has no active committers, or fails reporting duties; entry requires a board resolution, and retirement is logged with a tracked date, DOAP metadata update, and read-only lock-down [T2 — Apache Attic, "Process," §1; "Data Reference (YAML)," §retirement_date]. Crucially, the Attic *records departures as first-class events* — the timeline and per-year statistics enumerate retirements (18 in 2020 alone), so exits cannot silently vanish [T2 — Apache Attic, "Statistics"; "Timeline"]. It also defines a path *out* — forking, Incubator re-entry, or transfer — distinguishing permanent death from dormancy [T2 — Apache Attic, homepage].

### 2.3 Clinical-trial registration and its biases

Clinical registries (ClinicalTrials.gov, WHO ICTRP) are the template for *prospective registration before enrollment*: the ICMJE policy made registration before first patient enrollment a precondition for publication, and the WHO Trial Registration Data Set standardized the minimum fields to prevent selective reporting [T1 — Zarin et al., *NEJM*, 2016, §introduction; T2 — WHO ICTRP data set]. Registries track amendments and archive prior versions, which makes reporting bias detectable [T1 — Ross et al., *PLoS Medicine* 6(9), 2009].

This literature is also a catalogue of failure modes to avoid: registration alone does not prevent bias. Among prospectively registered trials, only 41% were free of selective outcome-reporting bias and 80% of high-risk trials favored a significant result; only 46% of completed registered trials were published, and vague outcome fields permitted post-hoc selection [T1 — Müschenich et al., *BMC Anesthesiology* 21, 2021, §Results; Ross et al., 2009]. Industry funding correlated with outcome changes [T1 — Mitra-Majumdar & Kesselheim, *PLoS Medicine* 19(1), 2022]. Implication: the registry must capture *specific, machine-readable* covariates and outcomes, archive every amendment, and be independent of the sponsors whose graphs it tracks.

### 2.4 Prospective inception cohorts in epidemiology

The prognosis gold standard is the prospective inception cohort: follow-up starts at a common, earliest point, the sample is population-based rather than clinic-based, outcomes are objective, assessment is blinded, follow-up is ≥80% complete, and extraneous prognostic factors are adjusted for [T1 — Viazis et al., "Methodology for high-quality studies on… IBD," §introduction; Setia, "Cohort Studies," §"cohort design"]. Dominant threats are referral-centre selection bias, prevalence–incidence bias, and loss to follow-up (a common rule caps attrition at 20% and requires comparing completers to dropouts) [T1 — Wang & Kattan, *CHEST* 158(1S), 2020, §"Bias"; "Observational Studies," §"Advantages and disadvantages"]. The institution-based cohort paper adds "time zero" discipline — enroll within a restricted post-exposure window and define every covariate and outcome in a data glossary — and target-trial emulation warns time zero must avoid immortal-time and prevalent-user bias [T1 — "Institution-Based Prospective Inception Cohort Study," §design; Hernán & Robins, cited in ENCePP, §4.2.1, §4.2.6].

### 2.5 Panel designs and their limits

The enterprise survey tradition — DORA/Accelerate, the NewVantage/Wavestone Data & AI Leadership Survey, and the EKGF/KGC benchmark — is the closest thing to tracking the enterprise population, but each is cross-sectional and self-selected. DORA describes "a cross-sectional, theory-based design" with snowball sampling via email lists and social sharing [T2 — DORA, *2018 State of DevOps Report*, §Methodology; *2021*, §"Target population and sampling"]. NewVantage/Wavestone is invitation-only (~100 Fortune 1000 organizations, 89.8% CDO/CDAO respondents) [T2 — Wavestone, *2024 Data and AI Leadership Survey*]. EKGF/KGC drew 150+ companies, most in pilot stage, citing lack of executive support and difficulty evidencing value [T2 — EKGF & KGC, *Knowledge Graph Industry Benchmarking Survey 2022*]. These are useful for covariates and trend context but cannot produce survival estimates: no inception date, no denominator, and no way to observe non-respondents. Attrition compounds — in the IAB Establishment Panel, cumulative non-response bias rose from ~3–6% in wave 1 to 40–50% by later waves, with larger establishments dropping out faster [T1 — Sakshaug et al., *J. Labour Market Research* 57, 2023, §Results].

---

## 3. Cohort Design

### 3.1 Inception definition and time zero

Recruit each asset at **inception**, defined as the earlier of (a) the first commit to the graph's repository or ontology store, and (b) the first dedicated spend — a budget-line allocation, purchase order, cloud-provisioning event, or API-key issuance for the capability. The dual trigger is deliberate: funded initiatives often precede code, and OSS-adjacent graphs precede funding. Whichever occurs first sets **time zero**, per the inception-cohort and target-trial requirement that follow-up start at a common, earliest, non-immortal point [T1 — Viazis et al., §introduction; ENCePP §4.2.6].

### 3.2 Sampling frame and recruitment-bias controls

The target population is **all business-graph assets initiated within a fixed 12-month window** across organizations above a revenue/employee threshold. Because no single frame covers it, use multiple overlapping frames, documented like referral patterns [T1 — Viazis et al., §"referral pattern"]:

1. **Vendor provisioning records** from graph-database, semantic-layer, and digital-twin platforms [T2 — cf. Apache Attic data reference, §established_date/retirement_date].
2. **Cloud-marketplace and infrastructure logs** capturing first resource allocation.
3. **Internal enterprise-architecture registries** (the ADR corpus in §3.7).
4. **Public OSS repositories** tagged knowledge-graph/ontology/digital-twin, screened for an enterprise sponsor.

Bias controls, per the survey and registry literature:

- **Register before enrollment**, the provisioning or first-commit event, analogous to ICMJE pre-enrollment registration [T1 — Zarin et al., 2016, §introduction].
- **Keep a documented denominator** — aggregate *administrative* records of non-consented units (counts by source, sector, size) [T1 — Sakshaug et al., 2023].
- **Measure representativeness** via R-indicators and response-propensity models against frame covariates [T1 — Bańkowska, Osiewicz & Pérez-Duarte, ECB Statistics Paper No. 12, 2015, §4].
- **Over-sample likely leavers** and run refusal conversion on a *random* refusal subsample (not just "soft" refusals) [T1 — ESS, *Guidelines for Enhancing Response Rates*, §2.2, §5].
- **Compare consenters and non-consenters** on every frame covariate, a differential-attrition check [T1 — Wang & Kattan, 2020, §"Bias"].

### 3.3 Pre-registered covariates

Register at time zero, before outcomes are observed, so they cannot be selected post hoc (mirroring the requirement that registered outcomes be specific [T1 — Müschenich et al., 2021, §Results]):

| Covariate | Operationalization |
|---|---|
| **Named owner** | Binary: a single named accountable owner (person, not team) at inception? |
| **Intended consuming decision** | Categorical: which decision the graph informs (pricing, supply, risk, planning, reporting, none). |
| **Budget line** | Categorical: dedicated multi-year vs. shared project vs. innovation/discretionary. |
| **Scope breadth** | Count of modeled domains and named decision use cases at inception. |
| **Enforced change process** | Binary: schema/ontology change routed through a versioned, reviewed process (PR-gated, ADR-linked)? |
| **Technology choice** | Categorical: RDF/OWL, property graph, bespoke/relational, vendor semantic layer. |
| **Team size** | Full-time equivalents assigned at inception. |

These map onto the failure anecdotes: named owner and enforced change process are the "survival past year three" traits practitioners describe [T3 — The Data Praxis, §"KGs that survive past year three"]; broad scope and shared budget map onto "infrastructure, not a deliverable" [T3 — J. Kim, §"Failure Cause 2"]; technology maps onto digital-twin interoperability failures [T1 — "Current trends in digital twin development…," §"Incompatibility and integration issues"; T1 — Zhu et al., *J. Constr. Eng. Manage.* 150(10), 2024].

### 3.4 Three outcome definitions

Register three outcomes rather than one "survival" number, each with a time-zero-aligned event and censoring rule [T1 — cf. Ait et al., 2022, §5.2; Miller et al., 2025, §IV–V]:

1. **Artifact survival.** Event = no human commit/edit to the graph in a trailing 6–12 months, following Ait et al. and Valiev [T1 — Ait et al., §5.2; T1 — Valiev, §2.3]; censored at last observation if still active.
2. **Active consumption.** Event = query volume, API calls, or reads falling below a pre-registered threshold (e.g., a percentile of the graph's own first-90-day baseline) for a sustained window. Most vulnerable to survey bias, so it must be instrumented (§3.5).
3. **Decision impact.** Event = first documented material decision changed on graph-derived evidence. This is a competing risk: a retired graph can no longer produce impact.

### 3.5 Objective consumption instruments

Instrument the primary outcomes instead:

- **Query and API logs** — server-side telemetry of queries, requests, and active users, the standard feature-adoption instrumentation, defining adoption as repeated meaningful use rather than a single click [T2 — GitHub, "Copilot usage metrics"; T3 — SpiderHunts, "SaaS Feature Adoption"]. OpenTelemetry-style counters carry tenant and role attributes for segmentation [T3 — OneUptime, "Feature Usage Analytics with OpenTelemetry"].
- **Lineage dependency graphs** — which downstream models, dashboards, reports, and agents depend on the graph, a structural measure that survives absent clickstream.
- **Revenue/decision weighting** — optionally weight consumption by the revenue or decision-criticality of consuming accounts [T3 — Fivetran, "Measuring product success with revenue-weighted feature usage"].

Surveys are retained **only for covariates and context**, never primary outcomes [T2 — DORA 2021, §Methodology; T3 — SpiderHunts, §"vanity dashboards"].

### 3.6 Mandatory retirement registry

Adopt an Apache-Attic-style registry as a condition of participation and, where possible, procurement: every graph must, on decommissioning, file a structured record — date, reason category (cancelled, descoped, superseded, absorbed, no owner, budget cut), superseding artifact, and final consumption snapshot [T2 — Apache Attic, "Process," §1; "Data Reference (YAML)," §retirement_date]. Mirror the Attic's re-entry paths to distinguish death from dormancy and revival [T2 — Apache Attic, homepage]. This is the most important anti-survivorship device: the invisible exit becomes a recorded event, populating the denominator success stories omit.

### 3.7 Blinded coding of decision impact

Code decision impact from **decision records**, not interviews. Enterprise architecture already produces a candidate corpus: Architecture Decision Records (ADRs) capture a single significant decision, its context, alternatives, and consequences, are immutable once accepted, and let superseding decisions reference predecessors [T2 — Nygard, "Documenting Architecture Decisions"; T2 — Fowler, "Architecture Decision Record"; T2 — AWS Prescriptive Guidance, "Using architectural decision records"]. Two trained coders, **blinded to all covariates**, independently read the log and mark whether a decision was materially changed on graph-derived evidence; disagreements are adjudicated and Cohen's κ reported, following the blind-outcome-assessment requirement [T1 — Viazis et al., §"blind outcome assessment"] and the two-coder procedure in registry-outcome audits [T1 — "Prevalence of primary outcome changes in clinical trials…," §Methods].

### 3.8 Follow-up schedule and stopping rules

- **Quarterly:** automated telemetry pull (artifact and consumption outcomes).
- **Semi-annually:** covariate refresh (owner, budget, team, scope).
- **Annually:** blinded decision-record audit.
- **Administrative censoring:** at 60 months for units not yet failed; earlier if a unit exits the frame.

Stop only on pre-registered rules: (a) when the target event count is reached; (b) futility-style early stop if the minimum detectable effect is bounded away at a pre-specified interim analysis with α-spending. No outcome-dependent extension of follow-up.

---

## 4. Analytic Plan

### 4.1 Estimands and models

The primary estimand is the **hazard ratio** for each pre-registered predictor on each outcome [T1 — Cox, *JRSS-B* 34(2), 1972]. Analysis proceeds in stages: (1) **Kaplan–Meier** survivor functions by covariate stratum with 95% bands and log-rank tests [T1 — Ait et al., §5.2; T1 — Valiev, §2.4.3]; (2) **Cox proportional-hazards** multivariable model, no stepwise selection [T1 — Cox 1972; T1 — Valiev]; (3) **diagnostics** via Schoenfeld residuals, with time-varying coefficients or stratified baselines if violated, and a time-interaction term for the first six months because early shutdowns differ qualitatively [T1 — Valiev, §"Modeling Considerations"]; (4) **competing risks** — cause-specific hazards and Fine–Gray subdistribution models, with power adjusted for the competing event [T1 — Latouche, Porcher & Chevret, *Stat. Med.* 23(21), 2004; T2 — *powerSurvEpi*, §numDEpi]; (5) **recurrences** — a frailty or Andersen–Gill model for die-and-revive graphs [T1 — cf. Avelino et al., §II.C].

### 4.2 Power and sample size

Power for Cox models is driven by the **number of events**, not subjects [T2 — Stata, *stpower cox* manual, §Description]. Schoenfeld's formula gives required events for a binary covariate with allocation proportion *p*: **E = (z₁₋α/₂ + z₁₋β)² / [ p(1−p) (ln HR)² ]**, and Hsieh–Lavori generalizes it to continuous covariates, inflating for correlation with other predictors by 1/(1−R²) [T1 — Schoenfeld, *Biometrics* 39(2), 1983; T1 — Hsieh & Lavori, *Control. Clin. Trials* 21(6), 2000; T2 — Stata *stpower cox*, §Methods]. At α = 0.05 (two-sided) and 80% power, (z₁₋α/₂ + z₁₋β)² = 7.85:

| Predictor / effect | Required events (E) | N at incidence 0.50 | N at incidence 0.35 |
|---|---|---|---|
| Binary, HR = 2.0, 50/50 | ≈ 66 | ≈ 132 | ≈ 189 |
| Binary, HR = 1.5, 50/50 | ≈ 192 | ≈ 384 | ≈ 549 |
| Binary, HR = 1.5, 30/70 | ≈ 227 | ≈ 454 | ≈ 649 |
| Continuous, HR = 1.5 per SD | ≈ 48 | ≈ 96 | ≈ 137 |
| Continuous, HR = 1.25 per SD | ≈ 158 | ≈ 316 | ≈ 451 |
| Continuous, HR = 1.15 per SD | ≈ 402 | ≈ 804 | ≈ 1,149 |

These reproduce the standard calculators [T2 — Stata *power cox*, §Examples; MRC-CBU FAQ]. Two constraints bind: **events per variable (EPV)** — with ten predictors and the conventional floor of ten EPV, the model needs ≥100 events [T1 — Vittinghoff & McCulloch, *Am. J. Epidemiol.* 165(6), 2007; T1 — Koçak & Onar-Thomas, 2012]; and **variance inflation** E_c = E/(1−R²), e.g. ×1.43 at R² = 0.3 [T1 — Hsieh & Lavori, 2000].

**Recommendation.** Recruit **N = 400 business-graph assets** at inception (~130/year across four frames) with **48–60 months of follow-up**. At a conservative 50% cumulative failure incidence by 48 months — consistent with OSS [T1 — Ait et al., §5.2] — this yields ≈200 events, clearing the EPV floor: >80% power for binary HR ≤ 1.5 and continuous HR ≈ 1.25 per SD, retaining HR ≈ 1.35 after variance inflation. Decision impact is rarer: at 20–25% incidence, ~80–100 events suffice for 2–3 predictors at HR ≈ 1.75–2.0 but not small effects, so pre-register it as **secondary**, with longer follow-up or consortium replication.

### 4.3 Sensitivity, heterogeneity, and falsifiability

Pre-register sensitivity analyses: (a) alternate death definitions (6 vs 12 months); (b) revived graphs censored vs. recurrent; (c) E-value-style bounding of unmeasured confounding; (d) a survivorship-bound analysis assuming non-consented units failed at the frame's *worst* vs *best* observed rate [T3 — MASEconomics]. Falsifiable predictions: named owner and enforced change process reduce the retirement hazard (HR < 1); shared/discretionary budget and broad scope increase it (HR > 1); and explicit end-of-life registration accelerates consumption death but not artifact survival — importing the 1.58× npm finding [T1 — Miller et al., §V.B].

---

## 5. Governance

### 5.1 Pre-registration

Register the full protocol — hypotheses, time zero, covariates, the three outcomes, instruments, model, power, stopping rules — on a domain-general registry such as OSF before outcomes are collected [T1 — Nosek, Ebersole, DeHaven & Mellor, "The Preregistration Revolution," *PNAS* 115(11), 2018, §main text; T2 — OSF, "Registrations & Preregistrations"]. Use the *structured* format with substantive independent review, since it better restricts researcher degrees of freedom [T1 — Bakker et al., *PLoS Biology* 18(12), 2020, §Results]. Publish as a **Registered Report**, accepted in principle before outcomes are known, neutralizing publication bias [T1 — Nosek et al., 2018, §"Registered Reports"; T2 — OSF]. Archive every protocol amendment, as ClinicalTrials.gov does [T1 — Ross et al., 2009, §"strengths and weaknesses"].

### 5.2 Ethics and consent

- **IRB/ethics review** with a data-management plan and a data glossary defining every covariate and outcome before enrollment [T1 — "Institution-Based Prospective Inception Cohort Study," §design].
- **Two-tier consent:** firms volunteering rich telemetry and decision records sign a research agreement; those allowing only aggregate administrative linkage are tracked at unit level for survival without covariate exposure [T1 — Bańkowska et al., 2015, §4].
- **Data minimization and non-attribution:** publish only aggregate or de-identified results; never name a firm's failure publicly. Adapt the Attic's public retirement pages to pseudonymous cohort IDs, naming firms only on their election [T2 — Apache Attic, "Process," §3 "Inform users"].
- **Prospective registration of the whole cohort** is an ethical commitment to register *all* enrolled units, including later failures, mirroring AllTrials' exhaustiveness principle [T1 — Mitra-Majumdar & Kesselheim, 2022, §main text].

### 5.3 Data sharing

Release data under FAIR principles — findable, accessible, interoperable, reusable — with persistent identifiers, metadata, provenance, and licensing [T1 — Wilkinson et al., "The FAIR Guiding Principles," *Scientific Data* 3, 2016, §Box 2]. Concretely: a public aggregate **survival table** (like the Attic's per-year counts) [T2 — Apache Attic, "Statistics"]; a controlled-access microdata repository; and a synthetic public release without firm identity. Every retirement record is a citable, persistent artifact.

### 5.4 Keeping the study alive

The study faces its own survival problem. Three mechanisms: (1) **Consortium governance, not a single PI** — govern through research institutions plus participating enterprises to survive sponsor turnover [T3 — J. Kim, §"Failure Cause 2"]. (2) **Embed the registry in operating governance** — make the retirement record a required architecture/procurement artifact with an immediate owner-benefit (an internal benchmark), as the Attic survives as a standing ASF function [T2 — Apache Attic, homepage]; and name a data steward with a documented succession plan, preventing the knowledge loss documented for digital twins [T1 — "Current trends in digital twin development," §"loss of knowledge"]. (3) **Publish periodic updates** — annual survival reports keep the denominator alive and give funders a track record [T2 — DORA 2024 report, §abstract].

---

## 6. What the Study Would and Would Not Establish

**Would establish:** unbiased **base rates** of survival — cumulative incidence of artifact death, consumption death, and decision impact at each time point, failed and silent units retained in the denominator; the **distribution of time-to-failure** and any first-year dominance [T1 — Ait et al., §5.2]; **relative hazards of the pre-registered predictors** with confidence intervals; a **corrective to enterprise-survey optimism** — whether DORA/NewVantage-style trend lines overstate durability because their samples exclude the dead [T2 — DORA 2021, §Methodology; T2 — Wavestone 2024]; and a **durable, reusable registry**.

**Would not establish:** **causal proof** — hazard ratios are associations, not effects [T1 — Wang & Kattan, 2020, §"Causality cannot be established definitively"]; **generalizability** beyond the four frames; **decision *quality*** — impact means the graph changed a decision, not that the decision was right; or **freedom from measurement error** — both errors are quantified and bounded, not eliminated [T1 — Ross et al., 2009, §Discussion].

The value of the design is not to make graphs look good or bad, but to answer, without sampling the survivors, *what fraction of business graphs survive, for how long, and what predicts it*.

---

## References and Sources

**Type 1 — Research papers and peer-reviewed work**

1. Ait, A., Cánovas Izquierdo, J. L., & Cabot, J. (2022). "An Empirical Study on the Survival Rate of GitHub Projects." *MSR '22*, pp. 365–375.
2. Avelino, G., Constantinou, E., Valente, M. T., & Serebrenik, A. (2019). "On the abandonment and survival of open source projects." *ESEM 2019*.
3. Miller, C., Jahanshahi, M., Mockus, A., Vasilescu, B., & Kästner, C. (2025). "Understanding the Response to Open-Source Dependency Abandonment in the npm Ecosystem." *ICSE '25*, pp. 2355–2367.
4. Valiev, M. (2021). "External Factors in Sustainability of Open Source Software."
5. Cox, D. R. (1972). "Regression Models and Life-Tables." *JRSS-B* 34(2), 187–220.
6. Schoenfeld, D. A. (1983). "Sample-Size Formula for the Proportional-Hazards Regression Model." *Biometrics* 39(2), 499–503.
7. Hsieh, F. Y., & Lavori, P. W. (2000). "Sample-Size Calculations for the Cox Proportional Hazards Regression Model with Nonbinary Covariates." *Controlled Clinical Trials* 21(6), 552–560.
8. Latouche, A., Porcher, R., & Chevret, S. (2004). "Sample size formula for proportional hazards modelling of competing risks." *Statistics in Medicine* 23(21), 3263–3274.
9. Vittinghoff, E., & McCulloch, C. E. (2007). "Relaxing the Rule of Ten Events per Variable in Logistic and Cox Regression." *Am. J. Epidemiol.* 165(6), 710–718.
10. Koçak, M., & Onar-Thomas, A. (2012). "A Simulation Based Evaluation of the Asymptotic Power Formulae for Cox Models in Small Sample Cases."
11. Glass, R. L. (2006). "The Standish report: does it really describe a software crisis?" *CACM* 49(8).
12. Jørgensen, M., & Moløkken-Østvold, K. (2006). "How large are software cost overruns? A review of the 1994 CHAOS Report." *Inf. Softw. Technol.* 48(4).
13. Eveleens, J. L., & Verhoef, C. (2010). "The Rise and Fall of the Chaos Report Figures." *IEEE Software*.
14. Viazis, N., et al. "Methodology for high-quality studies on course and prognosis of inflammatory bowel disease." PMC3413050.
15. Setia, M. S. (2016). "Methodology Series Module 1: Cohort Studies." PMC4763690.
16. Wang, X., & Kattan, M. W. (2020). "Cohort Studies." *CHEST* 158(1S).
17. "Observational Studies: Cohort and Case-Control Studies." PMC2998589.
18. "The Institution-Based Prospective Inception Cohort Study." PMC4115646.
19. ENCePP. "Chapter 4: Study design."
20. Zarin, D. A., et al. (2016). "Update on Trial Registration 11 Years after the ICMJE Policy." *NEJM*.
21. Ross, J. S., et al. (2009). "Trial Publication after Registration in ClinicalTrials.gov." *PLoS Medicine* 6(9):e1000144.
22. Mitra-Majumdar, M., & Kesselheim, A. S. (2022). "Reporting bias in clinical trials." *PLoS Medicine* 19(1).
23. Müschenich, F. S., et al. (2021). "Trial registration and selective outcome reporting in 585 clinical trials." *BMC Anesthesiology* 21, 249.
24. "Prevalence of primary outcome changes in clinical trials registered on ClinicalTrials.gov." PMC4032105.
25. Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). "The Preregistration Revolution." *PNAS* 115(11).
26. Bakker, M., et al. (2020). "Ensuring the quality and specificity of preregistrations." *PLoS Biology* 18(12):e3000937.
27. Wilkinson, M. D., et al. (2016). "The FAIR Guiding Principles for scientific data management and stewardship." *Scientific Data* 3:160018.
28. Sakshaug, J., et al. (2023). "Nonresponse trends in establishment panel surveys: the 2001–2017 IAB establishment panel." *J. Labour Market Research* 57.
29. Bańkowska, K., Osiewicz, M., & Pérez-Duarte, S. (2015). "Measuring non-response bias in a cross-country enterprise survey." ECB Statistics Paper No. 12.
30. "Current trends in digital twin development, maintenance, and operation: an interview study." *Software and Systems Modeling* (2024).
31. Zhu, H., Hwang, B.-G., Tan, Y. Z., & Wei, F. (2024). "Building on Digital Twin…" *J. Constr. Eng. Manage.* 150(10).
32. MRC-CBU Statistics Wiki. "FAQ/power/haz."

**Type 2 — Official documentation, specifications, white papers, renowned domain references**

33. The Apache Attic. "The Apache Attic" homepage; "Process"; "Data Reference (YAML)"; "Statistics"; "Timeline"; "Retired Projects." attic.apache.org.
34. StataCorp. *stpower cox* and *power cox* manuals.
35. *powerSurvEpi* R package documentation (Qiu et al.).
36. DORA / Google Cloud. *Accelerate State of DevOps Report* (2018, 2021, 2024).
37. Wavestone (formerly NewVantage). *Data and AI Leadership Executive Survey* (2012–2024).
38. EKGF & KGC. *Knowledge Graph Industry Benchmarking Survey 2022*.
39. Gartner. "Lack of AI-Ready Data Puts AI Projects at Risk" (2025); "Why Half of GenAI Projects Fail" (2026).
40. Nygard, M. (2011). "Documenting Architecture Decisions." cognitect.com.
41. Fowler, M. "Architecture Decision Record." martinfowler.com.
42. AWS Prescriptive Guidance. "Using architectural decision records."
43. GitHub Docs. "Copilot usage metrics."
44. WHO ICTRP Trial Registration Data Set.
45. European Social Survey. *Guidelines for Enhancing Response Rates and Minimising Nonresponse Bias*.
46. OSF. "Welcome to Registrations & Preregistrations." help.osf.io.

**Type 3 — Blogs, practitioner posts, smaller sources**

47. The Data Praxis (V. P. Singh). "Why Most Enterprise Knowledge Graph Projects Die in Year Two" (2026). https://thedatapraxis.com/blog/why-knowledge-graphs-fail/
48. Enterprise Knowledge (L. Tesfaye). "Why Graph Implementations Fail" (2025). https://enterprise-knowledge.com/why-graph-implementations-fail-early-signs-successes/
49. J. Kim. "Why Enterprise Knowledge Graph Implementations Fail" (2026). https://jkim101.github.io/blog/why-enterprise-knowledge-graph-implementations-fail_en/
50. Trew Knowledge (V. Viana). "Why So Few AI Pilots Reach Production" (2026). https://trewknowledge.com
51. CASRAI. "Survivorship Bias: When Only the Winners Get Studied." https://casrai.org/guides/survivorship-bias
52. Z. Al-basir. "Project Reporting Without Survivorship Bias" (2026). https://zalbasireppm.com
53. MASEconomics. "Survivorship Bias in Economic Evidence" (2026). https://maseconomics.com
54. Fivetran (A. Peterson). "Measuring product success with revenue-weighted feature usage" (2025). https://5tran.co/42GnxfK
55. OneUptime. "How to Instrument Feature Usage Analytics with OpenTelemetry" (2026). https://oneuptime.com
56. SpiderHunts. "SaaS Feature Adoption: Using Product Analytics Right" (2026). https://spiderhunts.com