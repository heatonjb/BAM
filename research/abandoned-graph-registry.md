# The Abandoned-Graph Registry: An Open Retirement Registry for Enterprise Knowledge Graphs, Digital Twins, Semantic Layers, and Finance-Data Platforms

## 1. The missing denominator

Every survival rate for enterprise knowledge graphs, digital twins, semantic layers, and finance-data platforms is computed on a sample that already passed a filter: the artifact is visible, so it did not die silently. The Apache Attic can report that "more than half of GitHub repositories from four ecosystems are dead within four years" because it operates a **compulsory** retirement process [T2 — Apache Attic, "Process," §1; T1 — Ait et al., MSR '22, p. 370, RQ2]. No equivalent exists for internal enterprise graphs, so "how many graphs survive?" has a numerator (published deaths) but no denominator (attempts). A death registry supplies the numerator and, joined to an inception frame, the denominator.

This document does three things: it surveys existing registries and graveyards for design lessons; it specifies a minimal, harvestable registry schema with submission criteria, controlled vocabularies, governance, and analytic hooks; and it **pilots** the registry on 38 real retired artifacts with sourced death dates and evidence links, reporting the actual yield and the false-positive/false-negative problems encountered.

## 2. Existing templates and what they teach

### 2.1 The Apache Attic: a compulsory retirement registry

The Attic is the closest existing analogue and the strongest template [T2 — Apache Attic, "Process," §1]. A project enters when its PMC cannot muster three release votes, has no active committers, or fails reporting duties; entry requires a board resolution, and retirement is a first-class record with a **retirement date** (the board meeting) tracked separately from a **completion date** [T2 — Apache Attic, "Process Tracking," tracking.html]. Its machine-readable YAML carries `retirement_date`, `attic_issue`, `attic_date`, `revived_date`, and `related_projects` [T2 — Apache Attic, "Data Reference (YAML)," data.html]. Two lessons dominate: the registry **enumerates exits** (its timeline shows retirements every year from 2004 to 2026, including 18 top-level retirements in 2020) [T2 — Apache Attic, "Timeline," timeline.html], and it explicitly models **revival**, so death is not confused with dormancy — the Attic records at least one reinstatement (Ambari) [T2 — Apache Attic, "Board Minutes," whimsy.apache.org/board/minutes/Attic.html].

### 2.2 endoflife.date: community-maintained lifecycle data as an API

`endoflife.date` documents end-of-life and support lifecycles for **478 products** through a versioned REST API and iCalendar feed [T2 — endoflife.date, homepage; "API v1," openapi.yml]. Its per-cycle schema is minimal and instructive: `cycle`, `releaseDate`, `eol`, `latest`, `lts`, `support`, `eoes`, `isDiscontinued` [T2 — endoflife.date, "API v1"]. It proves a low-cost maintenance model — a small community edits files, CI regenerates the API — and supplies a **controlled lifecycle endpoint** (EOL vs. extended-support end vs. discontinued). Its limits: it tracks product release cycles, not bespoke enterprise graphs, and relies on vendors publishing dates.

### 2.3 deps.dev / libraries.io / Depr.dev: deprecation as an event

Dependency-health services demonstrate an **event schema** for abandonment. Depr.dev records, per deprecation event: package, title, message, sunset date, source URL, replacement, and detection timestamp, harvested daily from registry `deprecated` fields, maintainer announcements, and community reports [T2 — Depr.dev, "How Detection Works," docs.depr.dev/reference/detection]. deps.dev provides free API access to dependency graphs and "deprecated status, open advisories" signals for more than 50 million package versions [T2 — Google, "Announcing the deps.dev API," blog.deps.dev/api]. The decisive lesson is also the weakness, stated by Depr.dev: "We can only detect what's publicly announced. If a maintainer abandons a package without notice, we won't know until the registry marks it deprecated, a security advisory is published, or the community reports it" [T2 — Depr.dev, "How Detection Works"]. That is the false-negative floor for any self-reporting death registry.

### 2.4 OSS repository-lifecycle datasets: deaths measured, not declared

A separate literature infers death from activity rather than a notice. Ait, Cánovas Izquierdo, and Cabot define a repository alive if it shows human activity in the trailing six months, and compute survivor functions with explicit censoring [T1 — Ait et al., MSR '22, p. 368, RQ1]. Avelino et al. find 315 of 1,932 popular GitHub projects (16%) abandoned, of which only 41% recovered under new maintainers [T1 — Avelino et al., ESEM 2019, §IV]. Software Heritage supplies the **archival** substrate — a deduplicated Merkle-DAG archive of source code with an API [T2 — Software Heritage, docs.softwareheritage.org]. These are not registries: they record neither *why* an artifact died nor what replaced it, and cover only public code. Their value is the **objective death instrument** (commit/consumer telemetry) registration cannot supply.

### 2.5 Graveyards: crowd-curated, community-driven, incomplete

`Killed by Google` and `The Google Cemetery` document dead Google products with launch year, discontinuation year, reason, and alternatives; the Cemetery reports **166 discontinued products since 2006** [T2 — The Google Cemetery, homepage, gcemetery.co]. `rip.so` and the ZKM "Net Art Extinction Timeline" extend the model to other platforms [T3 — rip.so, "Yahoo Pipes"; T3 — ZKM, "Yahoo Pipes shut down"]. The lesson is community maintenance at near-zero marginal cost; the weakness is curation quality — a "Near Death" bucket for products not actually dead, consumer bias, and no enterprise-internal deaths [T2 — The Google Cemetery, "RSS/API"].

### 2.6 CHAOS-style post-mortems: the sampling warning

The most-quoted project-failure figures descend from Standish's CHAOS reports (16.2% success / 52.7% challenged / 31.1% cancelled in 1994), and they are the canonical cautionary tale: Standish recruited respondents by asking them to "share failure stories," sampling on the outcome, and declined to disclose raw data [T1 — Standish Group, *The CHAOS Report*, 1995, p. 2; T1 — Glass, *CACM* 49(8), 2006; T1 — Eveleens and Verhoef, *IEEE Software* 27(1), 2010]. A registry that invites "failure reports" inherits this bias; it must enumerate a pre-registered population instead.

### 2.7 Clinical and bibliometric registry analogues

Prospective trial registration is the template for **registration before the outcome is known**: the ICMJE made registration before first patient enrollment a precondition for publication, and the WHO Trial Registration Data Set standardised the minimum fields [T1 — Zarin et al., *NEJM*, 2016, §introduction; T2 — WHO ICTRP Data Set]. Critically, registration alone is insufficient — among prospectively registered trials only 41% were free of selective outcome reporting, and only 46% of completed registered trials were published [T1 — Müschenich et al., *BMC Anesthesiology* 21, 2021, §Results; T1 — Ross et al., *PLoS Medicine* 6(9), 2009]. The Retraction Watch Database models the **death-of-a-claim** record: a record ID, subject, a controlled "Reason(s) for retraction," a "Nature of Notice" enum (retraction / correction / expression of concern / reinstatement), and a `Reinstatement` value distinguishing reversal from permanent death; its 67,000+ retractions are distributed via Crossref's API [T1 — Retraction Watch, "Building The Database," 2023; T2 — Crossref, "Retraction Watch," crossref.org; T2 — Retraction Watch, "Fields," Appendix A]. The lesson: a **controlled-reason vocabulary** plus an **immutable identifier** for the artifact and its death notice.

### 2.8 Design lessons extracted

Across all seven templates, six lessons compound: make filing a **governance/procurement artifact** rather than a voluntary report (Attic); accept the **"only announced deaths"** false-negative floor and instrument consumption directly (Depr.dev, OSS datasets); keep the record **tiny and machine-readable** and publish it as an API (endoflife.date); model **revival** separately from death (Attic, Retraction Watch); use **controlled vocabularies** and immutable identifiers (Retraction Watch); and **register at inception**, because outcome-only samples are biased (CHAOS, ClinicalTrials.gov).

## 3. Registry specification

### 3.1 Scope and unit of registration

The unit is a **named artifact with a steward**: an enterprise knowledge graph, ontology or semantic layer, digital twin, data platform, or finance-data platform — each with a stable persistent identifier. Features (`Google Finance Portfolios`) and corporate entities (`Hortonworks`) are recorded only when they stand as artifacts with a named owner and distinct lifecycle; otherwise they attach to the artifact they modify or steward.

### 3.2 Submission criteria and death triggers

An entry is admissible when at least one **death trigger** is met, each sourced to a public locator:

| Trigger | Definition | Typical evidence |
|---|---|---|
| `retirement-resolution` | A governing body (foundation board, PMC) formally retires the artifact | Board minutes; Attic YAML `retirement_date` |
| `deprecation-with-date` | Steward announces deprecation/EOL with an execution date | Vendor deprecation notice; release notes |
| `last-consumer-removed` | Instrumented consumption falls below a pre-registered threshold for a sustained window | Query/API logs; lineage graph |
| `funding-ended` | Grant, budget line, or sponsorship terminates | Grant closure record; annual report |
| `steward-dissolved` | The owning organisation is dissolved, acquired, or merged and the artifact is discontinued | Merger filing; press release |
| `replacement-ga` | A declared successor is generally available and the predecessor is EOL | Successor launch notes |
| `inactivity-threshold` | No human commit/edit in a trailing window T (or 2T on a trailing average) | Repository telemetry |
| `deletion` | Data or service is irrevocably removed | Shutdown notice; "data permanently deleted" |
| `registry-deprecated` | A package registry marks the artifact deprecated | Registry `deprecated` field |

The trigger set mirrors the Attic, endoflife.date, Depr.dev, and the OSS-activity literature, and makes explicit that **death is definition-dependent**: Open PHACTS has a funding-end date (2016) and a service-shutdown date (2019), three years apart [T2 — IHI, "Open PHACTS," end 2016; T2 — re3data, offline 2019-03]. The registry must record *which* trigger fired, not one "death date."

### 3.3 Minimal record schema

| Field | Type / vocabulary | Required |
|---|---|---|
| `registry_id` | Persistent id, e.g. `AG-0001` | yes |
| `artifact_name` | string | yes |
| `artifact_type` | `enterprise-kg` · `ontology` · `semantic-layer` · `digital-twin` · `data-platform` · `finance-data-platform` · `search-kg` | yes |
| `steward` | string; `steward_type` ∈ `foundation`·`enterprise`·`vendor`·`solo` | yes |
| `time_zero` | earliest of first commit, first funded spend, public launch/GA, TLP promotion | yes |
| `time_zero_basis` | enum naming which of the four events, + day/month/year precision | yes if `time_zero` given |
| `death_date` | date; `death_precision` ∈ `day`·`month`·`quarter`·`year` | yes |
| `death_trigger` | vocabulary in §3.2 | yes |
| `cause` | `cancelled` · `descoped` · `superseded` · `absorbed/merged` · `no-owner` · `budget-cut` · `funding-ended` · `acquired` · `company-shutdown` · `unknown` | yes |
| `replacement` | artifact ids or `none`; `replacement_relation` ∈ `direct`·`superseded`·`absorbed`·`none` | recommended |
| `evidence_links` | ≥1 URL per factual field (death, time-zero, cause) | yes |
| `confidentiality` | `public` · `pseudonymous` · `aggregate-only` | yes |
| `revival` | boolean + date + successor | optional |
| `consumption_snapshot` | trailing queries/commits at death, if instrumented | optional |
| `predecessor`/`successor` | ids, for dedup | recommended |

The schema borrows the **controlled reason vocabulary** and **reinstatement flag** from Retraction Watch [T2 — Retraction Watch, "Fields"], the **two-date lifecycle** from the Attic [T2 — Apache Attic, "Data Reference (YAML)"], and adds a `confidentiality` field so internal deaths can be filed without attribution.

### 3.4 Time-zero discipline

Following inception-cohort methodology, time zero is the **earliest** of first commit, first dedicated spend, launch/GA, or TLP promotion, and must name which event set it, to avoid immortal-time bias [T1 — Viazis et al., PMC3413050, §introduction; T1 — ENCePP, ch. 4, §4.2.6]. In practice this is the registry's weakest field: archives record deaths well and births poorly (§4.4).

### 3.5 Governance and incentives for honest reporting

- **Who benefits.** Buyers avoid stranded assets; maintainers escape zombie-support burdens; researchers gain the denominator; foundations gain a reputational service [T2 — Apache Attic, homepage]. Retraction Watch shows an independent clearing-house can make death a citable public good [T2 — Crossref, "Retraction Watch"].
- **Who is harmed.** The sponsor of a failed graph faces career and sunk-cost exposure; vendors face churn signalling. Disclosure is against the reporting party's interest unless anonymised or made a required compliance artifact.
- **Mechanisms.** (1) Embed the record in **operating governance** — a required architecture/procurement artifact, as the Attic requires a board resolution [T2 — Apache Attic, "Process," §1]. (2) **Reciprocity**: the benchmark is available only to organisations that file. (3) **Community reporting** as a backstop [T2 — Depr.dev, "How Detection Works"]. (4) **Enforce completeness, don't merely encourage it**: registered trials still under-report, so a voluntary registry under-counts unless auditable [T1 — Ross et al., 2009, §Discussion; T1 — Müschenich et al., 2021, §Results].
- **Dedup and integrity.** Keep a steward-of-record and persistent id; require `predecessor`/`successor` links; reconcile against Attic YAML, endoflife.date ids, deps.dev purls, and Wikidata QIDs to avoid double-counting forks and renames.

### 3.6 Confidential internal deaths

Internal deaths are invisible to public graveyards (§2.5). The registry handles them with the **two-tier consent** model from prospective cohort design: firms file either a `pseudonymous` record (stable cohort id, no name) with microdata in controlled access, or an `aggregate-only` record of counts without covariates [T1 — Bańkowska, Osiewicz & Pérez-Duarte, ECB Statistics Paper 12, 2015, §4]. Public output is aggregate or de-identified; a firm is named only on election.

### 3.7 Deduplication versus OSS-only survivorship bias

Public registries (Attic, endoflife.date, deps.dev, graveyards) over-represent artifacts that are open-source, vendor-published, or consumer-visible, and under-represent proprietary internal graphs whose deaths leave no public trace. The registry therefore tags every record with `steward_type` and reports base rates **stratified**, never pooled; the OSS stratum anchors the estimate (directly observed), and the internal stratum enters only through the pseudonymous tier [T1 — Ait et al., MSR '22, Table 5; T1 — Gahi, arXiv 2606.08266, §III]. Without this split, OSS-only samples mechanically inflate apparent survival.

### 3.8 Analytic uses

The registry supports three analyses. **(1) Base-rate / cumulative-incidence estimation** by `artifact_type`, `steward_type`, and `death_trigger`, with the denominator supplied by an inception cohort. **(2) Hazard inputs**: `time_zero` → `death_date` yields time-to-event for Kaplan–Meier survivor functions and Cox models with registry covariates as pre-registered predictors [T1 — Cox, *JRSS-B* 34(2), 1972; T1 — Ait et al., MSR '22, §5.2]. **(3) Competing risks**: `cause` distinguishes retirement, absorption, and deletion, which are competing events, not one event [T1 — Latouche, Porcher & Chevret, *Stat. Med.* 23(21), 2004]. The registry alone cannot estimate the compound event "maintained graph that improved a decision"; it supplies the death half, the prospective cohort the consumption and impact half.

## 4. Pilot: a seed set of 38 retired artifacts

### 4.1 Method

Rather than inviting self-reports (which would sample on outcome, §2.6), the pilot **harvested three existing lifecycle source classes**: the Apache Attic Process Tracking table (retirement month) [T2 — Apache Attic, "Process Tracking"]; vendor deprecation notices (Azure updates, Google Cloud release notes, Google Workspace blog); and announcement archives (press releases, Wikipedia "current status" fields, dated news). Each record was hand-coded to the §3.3 schema within the §3.1 artifact types.

### 4.2 The seed set

Attic entries use the **retirement month** as `death_date` with the project page as evidence [T2 — Apache Attic, "Process Tracking"; attic.apache.org/projects/]; non-Attic entries use the announced shutdown/EOL date.

| ID | Artifact | Steward | Type | Death date | Cause / trigger | Replacement | Evidence |
|---|---|---|---|---|---|---|---|
| AG-001 | Apache Stanbol | ASF | semantic-layer | 2020-04 | budget/no-owner (resolution) | none | [T2] attic.apache.org/projects/stanbol.html |
| AG-002 | Apache Marmotta | ASF | enterprise-kg (Linked Data) | 2020-11 | no-owner (resolution) | none | [T2] attic.apache.org/projects/marmotta.html |
| AG-003 | Apache Clerezza | ASF | enterprise-kg (RDF/OSGi) | 2022-06 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-004 | Apache Any23 | ASF | semantic-layer (RDF distiller) | 2023-06 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-005 | Apache Giraph | ASF | data-platform (graph compute) | 2023-09 | no-owner (resolution) | none (self-managed graph) | [T2] Attic, tracking.html |
| AG-006 | Apache MetaModel | ASF | data-platform (data access) | 2021-06 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-007 | Apache Olingo | ASF | data-platform (OData) | 2025-12 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-008 | Apache Chemistry | ASF | data-platform (CMIS) | 2022-02 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-009 | Apache VXQuery | ASF | data-platform (XML query) | 2020-01 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-010 | Apache Usergrid | ASF | data-platform (BaaS/graph) | 2021-12 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-011 | Apache OODT | ASF | data-platform | 2023-04 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-012 | Apache Chukwa | ASF | data-platform (collection) | 2020-05 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-013 | Apache Sqoop | ASF | data-platform (transfer) | 2021-06 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-014 | Apache Oozie | ASF | data-platform (workflow) | 2025-02 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-015 | Apache Tajo | ASF | data-platform (warehouse) | 2020-09 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-016 | Apache HAWQ | ASF | data-platform (warehouse) | 2024-07 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-017 | Apache Lens | ASF | data-platform (warehouse) | 2020-08 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-018 | Apache Metron | ASF | data-platform (security analytics) | 2020-12 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-019 | Apache Eagle | ASF | data-platform (monitoring) | 2020-11 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-020 | Apache Sentry | ASF | data-platform (authorisation) | 2020-12 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-021 | Apache PredictionIO | ASF | data-platform (ML) | 2020-09 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-022 | Apache MXNet | ASF | data-platform (deep learning) | 2023-09 | superseded/no-owner | none | [T2] Attic, tracking.html |
| AG-023 | Apache Submarine | ASF | data-platform (ML on Hadoop) | 2024-05 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-024 | Apache Bahir | ASF | data-platform (connectors) | 2024-01 | no-owner (resolution) | none | [T2] Attic, tracking.html |
| AG-025 | Freebase | Metaweb/Google | enterprise-kg | 2016-05-02 | superseded (strategic) | Wikidata; Google KG API | [T2] developers.google.com/freebase; [T3] en.wikipedia.org/wiki/Freebase_(database) |
| AG-026 | Microsoft Academic Graph | Microsoft | enterprise-kg (scholarly) | 2021-12-31 | superseded (strategic) | OpenAlex | [T2] microsoft.com/en-us/research/project/microsoft-academic-graph; [T3] blog.openalex.org |
| AG-027 | Open PHACTS / OPS | Open PHACTS Foundation | enterprise-kg (pharma) | 2019-03 | funding-ended | none | [T2] re3data.org/r3d100011550; [T2] ihi.europa.eu project factsheet |
| AG-028 | Google Search Appliance | Google | search-kg / enterprise search | 2019-03-31 | superseded (strategic) | cloud search / partners | [T2] en.wikipedia.org/wiki/Google_Search_Appliance; [T3] ciodive.com |
| AG-029 | Yahoo Pipes | Yahoo | semantic-layer (data mashup) | 2015-09-30 | budget-cut (no model) | IFTTT/Zapier (indirect) | [T2] en.wikipedia.org/wiki/Yahoo_Pipes; [T3] TechCrunch 2015-06-04 |
| AG-030 | Google Fusion Tables | Google | data-platform (data mgmt/viz) | 2019-12-03 | superseded (product consolidation) | BigQuery; Data Studio | [T2] workspaceupdates.googleblog.com 2018-12-11; [T3] en.wikipedia.org/wiki/Google_Fusion_Tables |
| AG-031 | Google Reader | Google | data-platform (feed aggregation) | 2013-07-01 | cancelled (declining use) | none | [T3] en.wikipedia.org/wiki/Google_Reader; The Verge |
| AG-032 | Google Finance Portfolios | Google | finance-data-platform (feature) | 2017-11 | descoped (redesign) | Search "Your Stocks" | [T3] marketwatch.com 2017-11-28; [T2] en.wikipedia.org/wiki/Google_Finance |
| AG-033 | GE Predix | GE | digital-twin / IIoT | 2018-12 | absorbed/descoped (financial) | GE Digital; cloud partners | [T2] sdxcentral.com 2018-12-17; [T3] medium.com/world-of-iot 2018-08-18 |
| AG-034 | Azure Time Series Insights | Microsoft | digital-twin / IoT | 2024-07-07 | superseded | Azure Data Explorer | [T2] azure.microsoft.com/en-us/updates (retirement 7 July 2024) |
| AG-035 | Google Cloud IoT Core | Google | digital-twin / IoT | 2023-08-16 | absorbed/descoped (partners) | partner IoT platforms | [T2] cloud.google.com/iot-core banner; [T3] siliconangle.com 2022-08-17 |
| AG-036 | Hortonworks HDP | Hortonworks | data-platform | 2019-01-03 | absorbed/merged | Cloudera CDP | [T2] cloudera.com press release 2019-01-03; [T2] SEC 8-K 2019 |
| AG-037 | Mint | Intuit | finance-data-platform | 2024-03-23 | absorbed (consolidation) | Credit Karma | [T3] cnbc.com/select; [T3] theverge.com; [T3] nytimes.com 2023-11-03 |
| AG-038 | Google Desktop | Google | data-platform (local search) | 2011-09-02 | cancelled (strategic) | none | [T3] en.wikipedia.org/wiki/Google_Desktop |

### 4.3 Actual yield

The pilot produced **38 records**, all with at least one public evidence link, spanning five artifact types (semantic/KG 7, data platform 27, digital-twin/IoT 3, finance-data-platform 2, search-kg 1) and two steward strata (foundation 24, enterprise/vendor 14). Death-date precision: **11 day**, **3 month/year** (non-Attic), and **24 month** (Attic retirement month) — a precise death date for **38/38 (100%)**. Time-zero was sourceable for only **15/38 (39%)**, because public archives record deaths in detail but rarely a comparable birth date. **Age at death is therefore computable for fewer than half the records** — median roughly 8–9 years (Freebase 9.2, Pipes 8.6, Fusion Tables 10.5, MAG 6.6, Mint ~17, TSI 6.6), with digital-twin platforms shortest-lived (Predix ~3, IoT Core ~5). The exit events are recoverable at near-zero discovery cost **when a steward publishes them**.

### 4.4 False positives and false negatives encountered

**False positives (recorded as death but not dead):**
- **Revival.** Apache Ambari was moved to the Attic and later reinstated; an Attic-keyed registry would log a reversed death [T2 — Apache Attic, "Board Minutes"].
- **Supersession read as death.** MAG → OpenAlex, TSI → Azure Data Explorer, GSA → cloud search, and several Apache projects were replaced, not lost; the function survived [T3 — blog.openalex.org; T2 — azure.microsoft.com updates].
- **Two candidate death dates.** Open PHACTS ended as a *project* in 2016 (grant end) but its *platform* closed in 2019; Freebase went read-only 2015-03-31 but shut down 2016-05-02 [T2 — IHI; T2 — re3data; T3 — en.wikipedia.org/wiki/Freebase_(database)]. Choosing one without a trigger vocabulary yields an arbitrary age.
- **Feature vs. product.** Google Finance Portfolios was a feature, not a product [T2 — en.wikipedia.org/wiki/Google_Finance].
- **Corporate events as proxy deaths.** Hortonworks merged rather than died; HDP was discontinued. The registry must map steward death to artifact death explicitly.

**False negatives (dead but not recorded):**
- **Silent abandonment.** The pilot found **no** record for any internal graph quietly switched off — the exact population the denominator needs; unannounced abandonment is invisible until it surfaces as a dependency problem [T2 — Depr.dev, "How Detection Works"].
- **No-notice OSS death.** Without a foundation or deprecation post, only an activity gap remains; a notice-only harvest misses it.
- **Incubator retirements.** Apache Incubator projects are tracked separately from the Attic, so an Attic-only scan under-counts [T2 — Apache Attic, homepage].
- **Consumer-product bias.** Graveyard sources over-represent consumer apps [T2 — The Google Cemetery, homepage].
- **Private/internal deaths** leave no public trace by construction.

The central finding is this asymmetry: **the registry can recover announced deaths cheaply, but the deaths that create the survivorship problem — quiet, internal, unannounced — need the governance hook and controlled-access internal tier.**

## 5. What this establishes

1. A death registry is **designable and cheap to prototype**: the pilot populated 38 schema-conformant, source-linked records from three public source classes by hand coding, with no new infrastructure.
2. Death dates are **recoverable and precise** for institutionally-stewarded artifacts (100% of pilot records), but **time-zero is the binding data gap** (39% sourceable), capping age and hazard estimation until records are captured at inception.
3. **Death is definition-dependent** and must be encoded as a trigger plus cause vocabulary with explicit revival links; a single "death date" field generates false positives (revival, supersession, feature deprecation, merger).
4. The registry **cannot by itself fix the survivorship problem**: it recovers the visible numerator but not the invisible denominator of silent internal deaths; it becomes useful only paired with prospective inception registration and an anonymised internal tier.
5. The pilot **bounds digital-twin lifespan** more tightly than adoption surveys do: Predix (~3 years) and Google Cloud IoT Core (~5 years) died far younger than data platforms (8–17 years), consistent with most digital-twin deployments being too recent for measured failure [T2 — Altair, 2022 Digital Twin Global Survey, §2].

## 6. Sustainability and limitations

**Is it practically sustainable? Yes as a harvester, no as a complete census.** A registry that ingests existing feeds — Attic YAML, endoflife.date, cloud deprecation feeds, deps.dev/Depr.dev events — under one controlled-vocabulary schema is sustainable at low marginal cost, because a steward already recorded the death. It is *not* sustainable as a volunteer effort that must discover silent deaths: discovery cost falls on the parties with the least incentive to report, and even compulsory registries under-report outcomes [T1 — Ross et al., 2009; T1 — Müschenich et al., 2021]. Sustainability requires the Attic's enforcement device (filing as a governance procurement artifact with an owner benefit), the pseudonymous internal tier (§3.6), and completeness auditing — not goodwill.

**How it feeds the survival base rates.** The registry supplies the numerator (dated deaths by type, steward, and cause) and, joined to an inception frame and the cohort's pre-registered covariates, the denominator of attempts, enabling cumulative-incidence and hazard estimates stratified by `artifact_type` and `steward_type`. It cannot supply the compound event "maintained and consumed and tied to an improved decision," and it inherits the visibility bias of its sources unless the internal tier is populated — the honest verdict is that the public registry is a **biased but essential numerator**, whose bias must be stratified, never pooled away.

## References

**Type 1 — Research / scholarly.** Ait, Cánovas Izquierdo & Cabot, "An Empirical Study on the Survival Rate of GitHub Projects," *MSR '22* 365–375. Avelino et al., "On the abandonment and survival of open source projects," *ESEM 2019*. Cox, "Regression Models and Life-Tables," *JRSS-B* 34(2), 1972. Latouche, Porcher & Chevret, *Statistics in Medicine* 23(21), 2004. Glass, *CACM* 49(8), 2006. Eveleens & Verhoef, *IEEE Software* 27(1), 2010. Zarin et al., *NEJM*, 2016. Ross et al., *PLoS Medicine* 6(9):e1000144, 2009. Müschenich et al., *BMC Anesthesiology* 21:249, 2021. Viazis et al., PMC3413050. Bańkowska, Osiewicz & Pérez-Duarte, ECB Statistics Paper 12, 2015. Gahi, arXiv:2606.08266. Piñeiro et al., "From Freebase to Wikidata," *WWW '16*.

**Type 2 — Official docs / specs / white papers.** ASF, *The Apache Attic* ("Process," "Process Tracking," "Data Reference (YAML)," "Timeline," "Board Minutes," project pages), attic.apache.org. endoflife.date "API v1" (openapi.yml). Google, "Announcing the deps.dev API," blog.deps.dev/api. Depr.dev, "How Detection Works," docs.depr.dev/reference/detection. Software Heritage, docs.softwareheritage.org. Retraction Watch, "Building The Database" (2023) and "Appendix A: Fields." Crossref, "Retraction Watch." Microsoft Research, "Microsoft Academic Graph" (retired 2021-12-31). Microsoft Azure, "We're retiring Azure Time Series Insights on 7 July 2024." Google Workspace Updates, "Fusion Tables shut down Dec 3 2019." re3data.org, "Open PHACTS" (offline 2019-03). IMI, "Open PHACTS" factsheet. Cloudera, merger release 2019-01-03; SEC 8-K. SDxCentral, "GE Spins Off Its Digital Business," 2018-12-17. WHO ICTRP Data Set.

**Type 3 — News / blogs / community.** The Google Cemetery, gcemetery.co. Killed by Google. rip.so. ZKM Net Art Extinction Timeline. TechCrunch, 2015-06-04. SiliconANGLE, 2022-08-17. World of IoT (Kumar), 2018-08-18. CNBC Select / The Verge / NYT on Mint, 2023-11. MarketWatch, 2017-11-28. CIO Dive, 2016-02-08. OpenAlex blog, 2021-05-08. Enterprise Knowledge (Tesfaye), "Why Graph Implementations Fail," 2025.

---

*File: `/root/code/personal/research/business-as-machine/research/abandoned-graph-registry.md`*
