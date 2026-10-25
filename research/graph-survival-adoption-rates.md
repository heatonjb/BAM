# Measuring Graph Survival and Adoption: Base Rates for Maintained Business Graphs

## 1. Why the survivorship problem is the central measurement question

Any claim that a business graph "improved a decision" is drawn from graphs that survived long enough to be observed making decisions — a set that is not representative of graphs that were attempted. The gap between attempts and observed survivors is the survivorship problem. It is severe enough that the headline failure statistics in this domain are best read as *bounds on a filter chain*, not estimates of a single quantity.

This document assembles evidence on the rate at which enterprise knowledge graphs, digital twins, semantic layers, and finance-data platforms remain alive and consumed N years after launch. It separates three measurements that are routinely conflated: **survival** (the artifact still exists and receives maintenance), **consumption** (humans or systems still query it), and **decision impact** (a specific decision changed because of it), then derives bounded ranges for the compound claim and identifies the strongest *measured* survival predictors. The recurring finding is that the binding constraint is not construction but funding, ownership, and the feeding of maintenance — the "ontology tax" or governance debt.

## 2. Three definitions of "alive," and why base rates differ by an order of magnitude

"Still alive" is definition-dependent. Ait, Cánovas Izquierdo, and Cabot define three states — running, zombie, and dead — and their dataset of 1,127 GitHub repositories created in 2016 yields 80.11% running, 0.39% zombie, and 19.51% dead at a single observation, yet a hazard-rate framing of the same data yields "more than half dead by year four" [T1: Ait et al., MSR '22, p. 370, RQ2 and Table 5]. The same repositories are "80% alive" or "50% dead" depending on snapshot versus survival analysis. A base rate quoted without naming its definition is unfalsifiable.

Gahi formalizes the same problem for enterprise platforms, defining a "data swamp" as a lake exhibiting three or more of six indicators, the most consumption-relevant being *dataset dormancy*: more than 40% of datasets receiving zero queries in 90 days [T1: Gahi, arXiv 2606.08266, Section V]. This is the closest thing in the literature to a consumption-based survival threshold, and it implies a platform can be "alive" by deployment metrics while failing the consumption test for two-fifths of its assets. This document therefore reports three base rates where evidence permits: **artifact survival**, **active consumption**, and **decision impact**.

## 3. The closest thing to objective evidence: instrumented survival and abandonment

### 3.1 Open-source repository survival

The most rigorous base rates mine repositories, where activity is directly observable rather than self-reported. Ait et al. found the prototypical lifespan is "intensive coding-driven active periods followed by long periods of inactivity," with deaths concentrated in year one [T1: Ait et al., MSR '22, p. 368, RQ1]. By year four, 50% were dead; survival probability falls below 50% beyond year five. Ecosystem matters: npm-package repos were 67.50% dead, WordPress plugins 66.57%, Laravel packages 53.70%, and R packages 49.25% [T1: Ait et al., MSR '22, Table 5] — roughly a two-to-one spread attributable to ecosystem, not artifact.

Avelino, Constantinou, Valente, and Serebrenik followed the "truck factor developer detachment" (TFDD): of 1,932 popular GitHub projects, 315 (16%) were abandoned after a TFDD, and only 128 of those (41%) survived because new core developers took over [T1: Avelino et al., ESEM 2019, Abstract and RQ2]. Critically, 59% of detachments occurred within two years [T1: Avelino et al., ESEM 2019, Section IV]. The survey of new maintainers identified "their own usage of the systems" as the main motivation to resurrect a project [T1: Avelino et al., ESEM 2019, Abstract] — the first empirical signal of the consumption–survival link.

Milewicz et al. (2025) sampled 430,469 scientific OSS projects and used Kaplan–Meier estimators to find an average restricted survival time of 6.44 years, with mathematics longest-lived and computer science shortest, and scientific OSS surviving longer than matched non-scientific projects [T1: Milewicz et al., FSE 2025, RQ2]. The correction runs opposite the popular intuition: scientific software "is less likely to become abandoned than one might think" [T1: Milewicz et al., FSE 2025, Title]. Base rates are population-specific.

### 3.2 Package ecosystems: dependency decay

Because dependency graphs are fully recorded, abandonment is measurable. He, Kästner, and Vasilescu found that of 28,100 widely-used npm packages, 4,108 (15%) became abandoned over six years, exposing an estimated 283,207 GitHub projects [T1: He et al., ICSE 2025, Section VIII]. The decision-relevant finding is behavioral: "most of these exposed projects never remove or replace an abandoned dependency," and removal accelerates only when end-of-life status is *explicitly announced* [T1: He et al., ICSE 2025, Abstract; T1: Wessel et al., arXiv 2409.18884, Section 3.10]. Abandonment is common in the most-used strata, and consumers are inert.

### 3.3 Foundation registries: a rare complete retirement census

The Apache Attic is one of the few *complete* public registries of formally retired infrastructure, with established/retire dates per project. Its timeline records retirements in essentially every year from 2004 to 2026, including 18 top-level retirements in 2020 and 12 in 2025 [T2: Apache Attic, "Project Retirements Timeline" and "Statistics"]. In FY2020 the ASF reported 339 top-level projects against 8 retirements that year [T2: Apache Software Foundation, FY2020 Annual Report]. A verified retiral census exists for public infrastructure partly because a governance body enforces it; no equivalent registry exists for internal enterprise graphs — itself a finding about measurement infrastructure. The 2021 Hadoop-ecosystem wave is a natural experiment: projects can be cited as alive while formally dead to their stewards [T3: Brust, ZDNET, 13 April 2021].

### 3.4 Digital twins: adoption measured, survival unmeasured

Digital-twin figures are dominated by adoption, not survival. An Altair survey of 2,007 respondents found 69% claimed their organization leveraged digital twins, and 71% of those began investing within the past year [T2: Altair, 2022 Digital Twin Global Survey, Section 2]. That recency concentration is a red flag: most deployments had not yet had time to fail. A Chalmers survey found the top obstacles were "limited determination of cost-benefit and value proposition" (53%) and "challenges with ownership and responsibilities" (51%) [T2: Chalmers, "A survey on the industry's perception of digital twins," Section 3.2]. The honest reading: digital-twin survival at N≥5 years is essentially unmeasured, and the 69% figure carries strong recency and self-report bias.

## 4. Analyst and vendor base rates versus independent evidence

### 4.1 The CHAOS/Standish lineage and its critiques

The most-cited failure numbers descend from Standish's CHAOS reports: 16.2% success, 52.7% challenged, 31.1% cancelled in 1994 [T1: Standish Group, *The CHAOS Report*, 1995, p. 2], evolving to 32% successful and 24% failed by 2009 [T1: Standish Group, *CHAOS Summary 2009*]. These are the canonical "two-thirds of projects fail" figures.

They are also the most thoroughly critiqued. Glass notes that Standish's own method — calling IT executives to "share failure stories" — biases the sample toward reported failure, and that Standish repeatedly declined to disclose raw data [T1: Glass, CACM 49(8), 2006]. Eveleens and Verhoef show the figures are sensitive to definitional and methodological choices [T1: Eveleens and Verhoef, IEEE Software 27(1), 2010]. Jørgensen and Moløkken found the 1994 overrun distribution implausible against independent estimates [T1: Jørgensen and Moløkken, IST 48(4), 2006]. The lesson is durable: the most-quoted project-failure base rates come from an undisclosed, self-selected, failure-eliciting instrument.

### 4.2 Data platforms: converging but non-comparable estimates

The data-platform literature produces a cluster of high-end estimates that the best independent synthesis refuses to average. Gahi aggregates Gartner's 60–85% big-data failure estimate (2015–2017), the 2014 "data swamp" warning, a VentureBeat-cited 87% data-science-project failure claim, and NewVantage's finding that 98.8% of Fortune 1000 firms invested in data while only 37.8% reported being data-driven [T1: Gahi, arXiv 2606.08266, Section I and Table I], while explicitly stating: "These rates are not comparable, and we do not pretend they are... So we do not average them into one number" [T1: Gahi, arXiv 2606.08266, Section I]. Independent field evidence is firmer: Thoughtworks states traditional enterprise-data-warehouse initiatives have a "higher than 50% failure rate" [T2: Thoughtworks Technology Radar]. A Vanson Bourne survey of 500 IT decision-makers found 83% were "not fully satisfied" with their data-warehousing initiatives [T2: SnapLogic / Vanson Bourne, 2020]. A market-research estimate puts warehouse-modernization failure-or-overrun at up to 70% [T3: Cloud Data Insights, 11 January 2026]. The defensible synthesis is a plateau of roughly 50–70% of large data-platform initiatives failing to deliver intended value, with 85%+ figures directional rather than calibrated.

### 4.3 Knowledge graphs and semantic layers: the pilot-to-production cliff

KG-specific evidence converges on a pilot-to-production cliff, but nearly all of it is vendor-adjacent. A widely-circulated synthesis states that "fewer than 15% of enterprise knowledge graph projects move past the pilot stage," stalling on ontology design, entity resolution, or query performance [T3: Atlan, citing Improvado 2026]. A market-research report claims 65–78% of large enterprises are "actively piloting or using" KGs but "fewer than 15%... have successfully moved into full-scale production" [T2: Astute Analytica, 2026, "Pilot Trap"]. Practitioner accounts stress organizational over technical failure: Enterprise Knowledge documents "stalled implementations, unmet expectations, and, in some cases, complete initiative abandonment," with primary signals being business-case linkage, interdisciplinary teams, and data-model ownership [T2: Enterprise Knowledge (Tesfaye), 9 January 2025]. The "ontology tax" analysis estimates a true enterprise graph costs roughly $10–20M with a 5–15-person capability center, against a "$6.9B market with only 27% production adoption" [T3: Shereshevsky, Graph Praxis, Medium]. A healthcare-technology survey found only 4% of 100 companies were fully prepared to integrate a KG [T3: IMO Health, 9 July 2026]. These point the same way — a steep drop between pilot and production — but are self-reported and non-peer-reviewed, best treated as *directional bounds* (perhaps 10–30% of KG initiatives reaching sustained production).

### 4.4 Generative AI and agentic systems: the newest and least durable figures

MIT's NANDA initiative reported that 95% of generative-AI pilots delivered no measurable P&L impact [T2: MIT Project NANDA, 2025, cited in [T3: Fortune, 18 August 2025]]. That report is a preliminary (v0.1) document whose methodology counts vary across secondary accounts, based on 150 leader interviews, 350 employee surveys, and 300 public deployments [T3: Fortune, 18 August 2025]. Its most robust sub-finding is comparative: purchased solutions succeeded "about 67% of the time, while internal builds succeed only one-third as often" [T3: Fortune, 18 August 2025]. S&P Global found the share of companies abandoning most AI initiatives rose from 17% to 42% in a single year [T2: S&P Global 2025, cited in [T1: Young, arXiv 2608.23617, Section 1]]. Against this, Bain reports 40% of software-development AI pilots moved to production at scale, 20–33% elsewhere [T2: Bain, 24 November 2025]; Gartner measured 54% of AI models reaching production [T2: Gartner via VentureBeat, 22 August 2022]; Deloitte places agentic AI in production at 11% [T2: Deloitte, 2026, via [T3: RIVER Group]]. The responsible range for "AI pilot reaches durable production" is broad, perhaps 10–40% by domain, and the 95% figure is an artifact of mixed scopes.

## 5. Bounding the base rate for "a maintained instance graph that improved a decision"

No study directly measures the compound event. It must be bounded by composing filters, each itself uncertain. For an enterprise-internal graph at three years:

- **Reached a usable artifact** (built past pilot): converging estimates across data platforms, KG, and AI suggest ~15–40% clear the pilot stage [T2/T3: §4.3–4.4]. Confidence: low.
- **Still maintained at 3 years, conditional on production**: OSS analysis suggests 50–70% alive for organization-owned projects [T1: Ait et al., MSR '22; T1: Avelino et al., ESEM 2019]. Confidence: moderate for OSS, low for internal.
- **Still actively consumed**: the swamp threshold implies up to ~40% of datasets dormant [T1: Gahi, arXiv 2606.08266]; adoption telemetry finds only ~2% of AI users reach embedded workflow depth [T2: ActivTrak, cited in [T1: Young, arXiv 2608.23617, Section 1]]. Consumption depth is the steepest filter. Confidence: low.
- **Demonstrably improved a decision**: the causal step is almost never measured — effectively unquantified, plausibly 0.3–0.7 of consumed graphs, with the caveat that "was consulted" ≠ "changed the decision."

Multiplying midpoints yields roughly **3–10% of attempted enterprise graphs at three years** being maintained, consumed, and tied to an improved decision; a generous upper bound is **~15–20%**, a strict lower bound **~1–2%**. At five years the compound rate plausibly halves again to **1–5%**. These are ranges, not points, dominated by the pilot-to-production and consumption filters (both low confidence). The single most defensible number is the OSS artifact-survival rate (~50% dead by year four), because it is directly observed. Two biases push the *observed* rate upward: built-and-abandoned graphs are not catalogued anywhere analogous to the Apache Attic, and internal graphs that never shipped produce no data. A corollary is that observed case-study success overstates attempted success by the inverse of the survival fraction.

## 6. The strongest measured predictors of survival and consumption

Across the empirical datasets, recurring predictors are organizational and relational, not technological.

**Organization/owner identity beats solo maintainers.** Ait et al. found organization-developed projects and larger contributor communities have higher survival probability; 59.25% of projects surviving over five years were organization-tier versus 7.40% solo-tier [T1: Ait et al., MSR '22, p. 370, RQ2]. Enterprise Knowledge names "lack of organizational ownership of data model quality and standards" as a primary failure signal [T2: Enterprise Knowledge, Section 1]. This is the most consistently measured predictor: **a named owner responsible for keeping the graph current.**

**A consuming product beats an abstract graph.** The dominant motivation for resurrecting abandoned projects was the new maintainer's *own usage* [T1: Avelino et al., ESEM 2019]. Enterprise Knowledge warns that applying graphs to "non-optimal use cases (e.g., for single application, not interconnected data)" destroys perceived impact, whereas successes are scoped to specific decisions such as "which dashboards break if a table is deprecated" [T2: Enterprise Knowledge, Section 2]. Sequeda's lesson — answer "which agent uses this knowledge graph" *before* modeling — is the same predictor in design form [T3: Sequeda, via Atlan]. **A concrete consuming product is the second strongest predictor.**

**Champion concentration is fragility, not success.** Adoption-telemetry research defines a "champion dependency" signature as a Gini coefficient above 0.5 over per-user activity, noting the cohort is "one resignation away from collapse," and prescribes de-concentration [T1: Young, arXiv 2608.23617, Sections 4.4–4.5]. This inverts the naive read of usage dashboards.

**Explicit lifecycle governance accelerates replacement.** npm removal of abandoned dependencies was significantly faster when end-of-life status was explicitly announced, correlating with "mature project governance" [T1: He et al., ICSE 2025]. The Apache Attic exists because a governance body enforces retirement [T2: Apache Attic]. **Enforced change/retirement process is a measured, survival-correlated control.**

**Narrow scope and incremental value sustain sponsorship.** Enterprise Knowledge attributes abandonment to the absence of business cases and short-term ROI expectations, while successes show incremental value early [T2: Enterprise Knowledge, Section 2]. The data-lake "Gluttony" sin (ingest without purpose) and the decay definition point to narrow-scope discipline [T1: Gahi, arXiv 2606.08266, Section V-A].

**Budget line and line-manager ownership beat central-lab ownership.** MIT NANDA's finding that internally built AI fails roughly three times as often as purchased solutions, plus its recommendation to empower line managers over central labs, indicates ownership location and integration predict survival [T3: Fortune, 18 August 2025; T2: MIT Project NANDA 2025]. Industry analyses put "a named person owns the system's performance, reliability, and continuous improvement" at the top of production-success traits [T3: RIVER Group].

The common structure: survival tracks *whether the graph is on someone's budgeted, measured critical path*, and consumption tracks *whether a specific downstream artifact resolves it*. Technology choice (property graph vs RDF, cloud vs on-premises) does not appear as a measured survival predictor in any dataset reviewed.

## 7. How much are survivor and failure anecdotes biased, and how to correct it

Anecdotal evidence is biased in two opposite, compounding directions.

**Self-report inflation of success.** Adjacent empirical work shows self-report is unreliable at the margins: developer self-reports of time allocation carried roughly 20% variance against direct observation [T1: Perry, "Evaluating Empirical Studies," lecture notes]. Cognitive-bias research in software engineering found that ~45.72% of observed developer actions carried at least one bias, and biased actions "are significantly more likely to be reversed" [T1: Mohanani et al. / CACM 2024, Sections 5.1–5.2]. Executives who commissioned a graph face sunk-cost and confirmation incentives; successes are drawn from a self-selected pool of survivors most motivated to report success.

**Failure-reporting suppression.** Standish's failure rate is inflated because it deliberately elicited "failure stories" [T1: Glass, CACM 2006]. Conversely, Gahi notes that "failed Data Lakes rarely show up in peer-reviewed work... the incentives run the other way," so failure also *under-reports* to the archival record [T1: Gahi, arXiv 2606.08266, Section III]. The finance-performance literature is the canonical demonstration that conditioning on survival can manufacture apparent persistence when none exists [T1: Brown et al., *Journal of Finance*, 1992]. In business graphs the two biases pull oppositely: reported success is inflated by self-report, while the denominator of attempts is invisible because abandonment is unrecorded.

**A design that corrects both.**

1. **A prospectively defined inception cohort**, not a retrospective sample of deployed graphs — recruit at first commit, register the intended decision use-case and a named owner *before* build, follow regardless of outcome.
2. **A registry of failures with a mandatory retirement path**, analogous to the Apache Attic, making the denominator of attempts observable [T2: Apache Attic, as template].
3. **Objective consumption instruments rather than surveys** — query logs, API-call records, lineage-tool dependency graphs, which already exist because dormancy and lineage assessment are standard governance metrics [T1: Gahi, arXiv 2606.08266, Section V; T1: Young, arXiv 2608.23617, Section 3]. Adoption telemetry from production signals measures depth of use without asking [T1: Young, arXiv 2608.23617, Abstract].
4. **A pre-registered decision-impact outcome** tied to the consuming artifact ("the deprecation decision used the graph" vs "it was made anyway"), extracted from decision records by a blinded coder rather than the sponsor.
5. **Covariate capture at inception** for the predictors in §6 (named owner, consuming product, budget line, scope, change process), enabling hazard-ratio estimation rather than survivor descriptions [T1: Ait et al., MSR '22; T1: Young, arXiv 2608.23617, Section 8].
6. **Report all three metrics separately**, each with its definition, because conflating them is the primary source of order-of-magnitude disagreement.

Until such a cohort exists, treat published case studies as *conditional* success reports (success | survived | chosen for write-up), discount vendor and analyst failure statistics to directional bounds, and anchor compound base-rate claims to the one directly observed stratum — open-source artifact survival.

## 8. Summary of bounded estimates

| Quantity | Best estimate | Range | Confidence | Anchor |
|---|---|---|---|---|
| OSS artifact survival at ~4 years | ~50% dead | 40–70% dead (ecosystem-dependent) | High | Ait et al. 2022; Avelino et al. 2019 |
| Widely-used npm package abandonment over 6 yrs | 15% | 12–18% | High | He et al. 2025 |
| Data-platform initiative fails to deliver value | ~60% | 50–85% | Moderate | Thoughtworks; Gartner; Vanson Bourne |
| KG initiative reaches sustained production | ~15–25% | 10–30% | Low | Improvado/Atlan; Astute; EK |
| AI pilot reaches durable production | ~20–40% | 10–54% | Low | Bain; Gartner; MIT NANDA |
| **Enterprise graph maintained, consumed, and tied to an improved decision at 3 yrs** | **~5%** | **1–20%** | **Very low** | **Derived in §5** |
| Same at 5 yrs | ~2–3% | 1–5% | Very low | Derived in §5 |

The dominant uncertainties are the pilot-to-production and consumption-depth filters, both poorly measured; the one solid anchor is that even in the best-instrumented public domain, roughly half of artifacts are inert within four years. Survival and consumption track named ownership, a real consuming product, a budget line, narrow scope, and an enforced change process far more reliably than any technical design choice.

## References

**Type 1 — Published research / peer-reviewed**

- Ait, A., Cánovas Izquierdo, J. L., & Cabot, J. (2022). "An Empirical Study on the Survival Rate of GitHub Projects." *MSR '22*, pp. 365–375. DOI 10.1145/3524842.3527941.
- Avelino, G., Constantinou, E., Valente, M. T., & Serebrenik, A. (2019). "On the abandonment and survival of open source projects." *ESEM 2019*; arXiv:1906.08058.
- He, H., Kästner, C., & Vasilescu, B. et al. (2025). "Understanding the Response to Open-Source Dependency Abandonment in the npm Ecosystem." *ICSE 2025*.
- Milewicz, R., et al. (2025). "Scientific Open-Source Software Is Less Likely to Become Abandoned Than One Might Think!" *Proc. ACM Softw. Eng.* 2(FSE), FSE099.
- Constantinou, E., & Mens, T. (2017). "An Empirical Comparison of Developer Retention in RubyGems and npm." arXiv:1708.02618.
- Wessel, M., et al. (2024). "An Overview and Catalogue of Dependency Challenges in Open Source Package Registries." arXiv:2409.18884.
- Standish Group (1995). *The CHAOS Report*; (2009). *CHAOS Summary 2009*.
- Glass, R. L. (2006). "The Standish Report: Does It Really Describe a Software Crisis?" *CACM* 49(8).
- Eveleens, J. L., & Verhoef, C. (2010). "The Rise and Fall of the Chaos Report Figures." *IEEE Software* 27(1).
- Jørgensen, M., & Moløkken, K. (2006). "How large are software cost overruns?" *Information and Software Technology* 48(4).
- Gahi, Y. (2026). "What Went Wrong with Data Lakes? A 15-Year Reality Check from the Field." arXiv:2606.08266.
- Young, D. A. (2026). "Adoption Telemetry: Measuring Enterprise AI Adoption from Production Signals." arXiv:2608.23617.
- Brown, S. J., et al. (1992). "Survivorship Bias in Performance Studies." *Journal of Finance* 47(4).
- Mohanani, R., et al. (2020). "Cognitive Biases in Software Engineering." arXiv:1707.03869; CACM 2024.
- Perry, D. E. "Evaluating Empirical Studies." Lecture notes, UT Austin.
- Zech, P., Clark, T., & Breu, R. (2025). "An Empirical Analysis of Digital Twin Adoption." *HICSS 2025*.

**Type 2 — Docs, specs, white papers, analyst reports, renowned domain blogs**

- Apache Software Foundation. *The Apache Attic* — "Project Retirements Timeline," "Statistics," "Process Tracking." https://attic.apache.org/
- Apache Software Foundation. (2020). *Annual Report FY2020*.
- Thoughtworks. *Technology Radar* — "Enterprise Data Warehouse."
- SnapLogic / Vanson Bourne. (2020). "The State of Data Management."
- Altair. (2022). "Digital Twin Global Survey Report."
- Chalmers. "A survey on the industry's perception of digital twins."
- Enterprise Knowledge (L. Tesfaye). (2025). "Why Graph Implementations Fail," 9 January 2025.
- Gartner via VentureBeat. (2022). "Only half of AI models make it into production," 22 August 2022.
- MIT Project NANDA. (2025). *The GenAI Divide: State of AI in Business 2025*.
- Bain & Company. (2025). "Executive Survey: AI Moves from Pilots to Production."
- S&P Global Market Intelligence. (2025), cited in arXiv:2608.23617.
- Deloitte. (2026). *State of AI in the Enterprise*.
- Astute Analytica. (2026). "Enterprise Knowledge Graph Market," "Pilot Trap."
- APQC. (2025). "Why Most Enterprise AI Projects Fail."
- PMI. "Project failure — 12 mistakes to avoid," citing CHAOS 2003.
- dbt Labs. *dbt Semantic Layer* product documentation and developer blog. docs.getdbt.com.

**Type 3 — Social posts, smaller blogs, podcasts, talks**

- Atlan (K. Pasupathy). (2026). "What Are the Pitfalls of Building an Enterprise Knowledge Graph?" atlan.com/know/ai-agent/knowledge-graph/enterprise-knowledge-graph-pitfalls/ (citing Improvado 2026).
- Improvado. (2026). "Enterprise Knowledge Graph." improvado.io/blog/enterprise-knowledge-graph
- Shereshevsky, A. "The Ontology Tax" / "Graph Maintenance at Scale." Medium, medium.com/graph-praxis/.
- Sequeda, J. "The 20 Lessons about Building Ontologies." Substack.
- IMO Health. (2026). "Survey data reveals readiness gap in clinical AI and knowledge graph adoption," 9 July 2026.
- Fortune. (2025). "MIT report: 95% of generative AI pilots at companies are failing," 18 August 2025.
- Brust, A. (2021). "Apache Software Foundation retires slew of Hadoop-related projects." ZDNET, 13 April 2021.
- Cloud Data Insights. (2026). "The Manual Migration Trap," 11 January 2026.
- RIVER Group. (2026). "The Pilot-to-Production Gap That's Costing Billions," 10 February 2026.
- Ontotext / EKGF. "The Current State of Knowledge Graph Adoption — 2022 Benchmarking."
- Atkin, M., et al. (2021). "Panel on KG Adoption in Finance," Knowledge Graph Conference.
- Hacker News. "Agent memory on knowledge graphs" (item 48337689); "Challenges for Enterprise Knowledge Graph Adoption in AI" (item 47017612).
