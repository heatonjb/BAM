# Cross-Corpus Confidence Calibration: Weighting Observed, Directional, and Constructed Evidence

## 1. The calibration problem

A corpus that models "any business as a transformation machine" necessarily mixes evidence of very different strength. At one end sit direct measurements — instrumented repository histories, regulator-published tag rates, public event-log benchmarks. At the other sit claims that are true-by-construction: a transformation algebra, a seeded enterprise simulator, a reference ontology. In between sit vendor and analyst estimates whose motive is entangled with the number. Treating these as interchangeable, or averaging them into a single "evidence score," produces confident nonsense: a constructed claim that is internally coherent can out-score a messy but real measurement, and a vendor statistic repeated by fifty blogs can look like independent corroboration.

This document builds a calibration scheme. Section 2 surveys the formal machinery that already exists for exactly this problem in medicine, forecasting, and machine learning. Section 3 adapts it into a five-dimension scoring rubric. Section 4 applies the rubric to the three corpus strata. Section 5 specifies how to combine — or decline to combine — incompatible evidence and how to propagate uncertainty into a decision. Section 6 works eight representative claims end to end.

The governing principle throughout: **confidence attaches to a claim, not to a source.** A single trustworthy laboratory can produce a low-confidence claim, and a self-interested vendor can produce a high-confidence one if its measurement is independently checkable.

## 2. How other fields appraise evidence

### 2.1 GRADE and certainty of evidence

GRADE is the most widely adopted framework for grading a *body of evidence* for a specific question. It rates certainty as high, moderate, low, or very low, and defines the levels by closeness of the estimate to the true effect rather than by study design alone [T2: GRADE Working Group, *GRADE Book*, "Overview of the GRADE approach," Table 2, para. 1–2]. Randomised trials start high; observational studies start low. Five domains then rate the evidence *down*: risk of bias, inconsistency, indirectness, imprecision, and publication bias. Two domains can rate up: large magnitude of effect and dose-response [T2: Nhmrc, "Assessing certainty of evidence using GRADE," Table 1 and domain list]. Crucially, GRADE explicitly expects recommendations to be made "even when only very low certainty evidence is available" [T2: GRADE Book, "Overview," advantages list item 5] — the framework does not demand high certainty before issuing a directional judgement.

Two features transfer directly. First, certainty is assessed at the level of the *question*, aggregating across studies, not for each study in isolation [T2: GRADE Book, "Overview," para. 2]. Second, downgrading is domain-specific and quantifiable; GRADE's imprecision domain is defined operationally through confidence intervals crossing decision thresholds [T2: GRADE Book, "Overview," imprecision paragraph].

### 2.2 Risk-of-bias tools and review-quality instruments

Cochrane operationalises bias assessment through RoB 2 for randomised trials and ROBINS-I for non-randomised studies [T2: Cochrane, "Risk of bias" collection page]. Review-quality instruments assess the appraiser rather than the primary study: AMSTAR-2 (16 items) and ROBIS (24 items) both target systematic reviews, and a 2025 comparative study of 200 reviews found they are "complementary rather than interchangeable," agreeing on direction in all but 9% of cases [T1: *Research Synthesis Methods*, 2026, 17(1):63–92, Results and Abstract]. The lesson for a heterogeneous corpus is that **appraisal instruments can disagree, and the disagreement is informative** — a claim whose quality verdict flips depending on the rubric is itself low-confidence.

### 2.3 Qualitative and constructed evidence: GRADE-CERQual

GRADE assumes effectiveness evidence, but constructed and interpretive claims need a different instrument. CERQual (Confidence in the Evidence from Reviews of Qualitative research) rates confidence in a *finding* using four components: methodological limitations, coherence, adequacy, and relevance [T2: GRADE-CERQual, "Overall confidence in the evidence"]. "Confidence" is defined as "the extent to which the review finding is a reasonable representation of the phenomenon of interest" [T2: GRADE-CERQual, "What is GRADE-CERQual?"]. CERQual deliberately accommodates the interpretive nature of qualitative synthesis and is used by WHO and NICE [T2: WHO EMRO, "A new tool developed by WHO and academic partners," para. 4 and closing]. This is the closest existing analogue for scoring a proposed-by-construction artifact: constructed coherence is a *component* (coherence), not a substitute for relevance or adequacy.

### 2.4 Structured expert elicitation: Delphi and Cooke's classical model

The Delphi method aggregates expert judgement through anonymity, iteration, controlled feedback, and statistical group response [T1: Dalkey & Helmer, RAND RM-5888, Summary, features list]. Face-to-face discussion "tended to make the group estimates less accurate," while anonymous controlled feedback "made the group estimates more accurate" [T1: RAND RM-5888, Summary, second paragraph]. Delphi is designed precisely for settings "where exact knowledge is not available" [T1: RAND RM-5888, Summary, first paragraph].

Cooke's classical model is stricter: it weights experts by their measured performance on *calibration (seed) questions* with known true values, combining a calibration score and an information score into performance weights [T1: Colson & Cooke, *Review of Environmental Economics and Policy*, 2018, 12(1), "The Classical Model" section and Abstract]. Across 33 studies, performance weighting outperformed equal weighting in all but one [T1: Colson & Cooke 2018, citing Flandoli et al. 2011]. In the TU Delft database, performance-weighted combinations beat equal weights in 20 of 26 cases [T1: Cooke, "Validating Expert Judgment with the Classical Model," Section 1 and results]. The transferable idea: **weights should be justified by demonstrated calibration on questions where the answer is already known, not by credentials.**

### 2.5 Judgement under uncertainty: superforecasting and scoring rules

The Good Judgment Project found a subset of forecasters ("superforecasters") whose aggregated forecasts outperformed intelligence analysts with classified access by roughly 25–30% on Brier score [T3: AI Impacts, "Evidence on good forecasting practices from the Good Judgment Project," http://aiimpacts.org; T2: Good Judgment Inc., "Superforecasters: A Decade of Stochastic Dominance," p. 1 and Figure 4]. Good Judgment reports well-calibrated aggregate forecasts where assigned probabilities track observed frequencies [T2: Good Judgment Inc., "Superforecaster Accuracy," slide "How Reliable Are Good Judgment's Forecasts?"].

The scoring-rule literature explains why honesty is enforceable. The Brier (quadratic) score and the logarithmic score are *strictly proper*: a forecaster maximises expected score only by reporting their true belief [T1: Gneiting & Raftery, *JASA*, 2007, 102(477):359–378, "Strictly Proper Scoring Rules," Section 2 and Example 1]. This matters for a corpus: if every claim must carry a probability that is later scored, the incentive to inflate confidence disappears.

### 2.6 Engineering and ML analogues

Machine-learning research built checklists after finding that results were frequently unreproducible. The ML Reproducibility Checklist asks for dataset statistics, splits, hyperparameter ranges, number of runs, and central tendency with variation [T2: Pineau, "The Machine Learning Reproducibility Checklist v2.0," items 1–6]. Use at NeurIPS 2019 was reported by 34% of reviewers as useful for judging soundness [T1: Pineau et al., *JMLR* 22(164):1–20, 2021, Section 5]. More recently, benchmark-credibility work proposes explicit checklists covering annotation quality, gameability, data contamination, domain coverage, and representativeness [T1: "In Benchmarks We Trust … Or Not?", *EMNLP 2025*, Table 2]. Construct-validity audits similarly require that a benchmark's claims stay within the scope of its phenomenon definition [T1: "Measuring what Matters: Construct Validity in LLM Benchmarks," arXiv:2511.04703, Appendix B.5].

Analyst reports need heavier discounting. Gartner's Hype Cycle is explicitly an expectations model combining "analyst judgment, client surveys, and vendor briefings" [T2: Gartner, "Hype Cycle for Data, Analytics and AI Programs, 2024," methodology paragraph]. Its veracity is "largely disputed," and an analysis of Hype Cycles since 2000 found "few technologies actually travel through an identifiable hype cycle" and that most important technologies "were not identified early in their adoption cycles" [T3: Wikipedia, "Gartner hype cycle," "Criticisms of the model," citing Dedehayir & Steinert 2016]. Gartner's own Magic Quadrant disclaimer states its documents "consist of the opinions of Gartner's business and technology insights organization, which should not be construed as statements of fact" [T2: Gartner, "Magic Quadrant for Analytics and BI Platforms," disclaimer paragraph]. Vendor-payment conflicts have been litigated: NetScout's "pay-to-play" suit survived a motion to dismiss [T2: *Computing*, "Court allows NetScout accusation of Gartner Magic Quadrant 'pay for play' business model to continue," 17 Dec 2015].

## 3. A concrete calibration scheme

### 3.1 Five dimensions

Each corpus claim is scored on five dimensions, each on a 1–5 integer scale (5 = strongest). The dimensions deliberately separate *what kind of evidence it is* from *how informative it is*.

- **(a) Evidence type / mode.** Direct observation (instrumented, 5) → instrumented measurement (5) → administrative/regulatory record (4) → third-party audit (4) → survey/self-report (3) → vendor/analyst estimate (2) → model or proposed-by-construction (1).
- **(b) Directness of observation.** Is the measured quantity the same as the claimed quantity? A repository's active-commit history directly measures survival (5); a survey asking firms whether they "use" a technology measures self-perception of use (2); a simulator's outputs measure the simulator, not the world (1).
- **(c) Independence.** Independent replication (5) → multiple independent sources (4) → single independent source (3) → single interested source (2) → the claimant is also the beneficiary (1).
- **(d) Sample size / replication.** Large-N with replication (5) → large-N single study (4) → moderate-N (3) → small-N or pilot (2) → single case / n=1 (1).
- **(e) Bias / motive pressure.** Low (5) → mild (4) → moderate (3) → strong, self-interested (2) → adversarial/advocacy (1). This generalises GRADE's risk-of-bias, indirectness, and publication-bias domains and CERQual's methodological-limitations component.

### 3.2 From dimensions to a numeric confidence

A transparent aggregation is the **geometric mean of the five dimension scores**, rescaled to [0, 1]:

> C = ( Π d_i )^(1/5) / 5

The geometric mean punishes a single fatal weakness (a 0-or-1 dimension drags the product down) far more than an arithmetic mean would, which is desirable: a claim with a catastrophic bias problem should not be rescued by a large sample. As a guardrail, any dimension at 1 caps the maximum confidence tier (below). Map C to tiers mirroring GRADE:

| Tier | C range | Meaning |
|------|---------|---------|
| **High** | 0.80–1.00 | estimate close to true value; act on it |
| **Moderate** | 0.65–0.79 | likely directionally right; act with a wide interval |
| **Low** | 0.45–0.64 | direction uncertain; do not use as a decision input alone |
| **Very low** | 0.00–0.44 | insufficient evidence; report as such |

The dimension scores are the primary output; the scalar C is a communication device and a ranking key, not a precision measurement. Reporting it to two decimals would be false precision.

### 3.3 Guardrails

Three rules override the arithmetic:

1. **Constructed coherence is not external validity.** Any claim resting solely on a model artifact (transformation algebra, simulator, ontology) scores 1 on directness and cannot exceed Low confidence regardless of elegance. This follows CERQual, where coherence is one of four components and never sufficient alone [T2: GRADE-CERQual, "Overall confidence"].
2. **Single self-reported source caps at Very low→Low boundary.** A claim whose only support is one party's self-report caps at C ≤ 0.5 (see §5.2).
3. **Repeated non-independent citation is one source.** A vendor number quoted by twenty outlets still scores 1–2 on independence unless an outlet performed independent verification.

## 4. Applying the scheme to the corpus strata

### 4.1 Directly observed stratum

This stratum contains the strongest evidence in the corpus.

- **OSS survival (~50% dead by year four).** Ait et al. mined 1,127 GitHub repositories and report that "the probability of surviving longer than five years is less than 50%" [T1: Ait et al., "An Empirical Study on the Survival Rate of GitHub Projects," MSR '22, pp. 365–375, Abstract]. Avelino et al. separately found 16% of 1,932 popular projects abandoned after a core-developer detachment, with 41% surviving via new maintainers [T1: Avelino et al., ESEM 2019, Abstract]. This is instrumented, direct observation on the survival quantity, with two independent studies in rough agreement. Dimensions: (a)=5, (b)=5, (c)=4, (d)=5, (e)=5 → C = (2500)^(1/5)/5 ≈ 0.95 → **High**. The caveat is external validity: GitHub survival is not the same quantity as enterprise-graph survival. Confidence in the *measured* claim is High; confidence that it *transfers* to a different population is much lower.
- **XBRL extension rates (~13–30%).** The SEC's own Division of Economic and Risk Analysis publishes annual custom-tag rates drawn from the full population of filings: 18% in 2023 declining to 17% in 2024 [T2: XBRL US, "SEC Custom Tag Analysis Shows Slight Decline for All Filers," 30 May 2025, para. 1]. Earlier staff analysis found smaller filers averaged nearly 50% higher custom rates than larger filers, with 96% of high-rate filers being small filers [T2: SEC DERA, "Staff Observations of Custom Tag Rates," Section II]. This is a regulator's administrative census of the actual quantity. Dimensions: (a)=4, (b)=5, (c)=5 (independent regulator), (d)=5, (e)=4 → C ≈ 0.92 → **High**. Note the range 13–30% is definitional (line-item vs. all tags), so the *point estimate* is High-confidence while any particular headline number is definition-dependent.
- **Public OCEL benchmarks.** OCEL 2.0 is a published specification with exchange formats and tool support [T1: Berti et al., "OCEL 2.0 Specification," arXiv:2403.01975, Abstract]. That the specification exists is High-confidence; whether the *benchmark population* is representative of enterprise processes is unmeasured, so corpus claims built on OCEL's representativeness are Low.

### 4.2 Vendor/analyst-adjacent stratum

- **KG pilot-to-production (<15%).** Atlan reports "fewer than 15% of enterprise knowledge graph projects move past the pilot stage," attributing the figure to a 2026 vendor synthesis [T3: Atlan, "Enterprise Knowledge Graph Pitfalls," atlan.com/know/knowledge-graph/enterprise-knowledge-graph-pitfalls]. The number is a secondary vendor citation, not a measurement. Enterprise Knowledge's practitioner account is qualitative and its author is a graph consultancy [T2: Enterprise Knowledge, "Why Graph Implementations Fail," 9 Jan 2025, opening paras.]. Dimensions: (a)=2, (b)=2, (c)=2, (d)=2, (e)=2 → C = (32)^(1/5)/5 ≈ 0.40 → **Very low**. The direction ("most stall") is plausible and consistent with AI-pilot evidence, but the specific 15% is not decision-grade.
- **Digital-twin adoption.** Gartner's 2019 survey found 13% of IoT-implementing organisations already using digital twins and 62% planning or establishing use [T2: Gartner, "Gartner Survey Reveals Digital Twins Are Entering Mainstream Use," 20 Feb 2019, para. 2–3]. IoT Analytics reports 29% of manufacturers had fully or partially implemented digital-twin strategy in 2023, up from 20% in 2020 [T2: IoT Analytics, "Digital twin market: Analyzing growth and emerging trends," 2023, bullet 2]. Both are vendor-adjacent survey estimates; "planning" inflates adoption. Dimensions: (a)=3, (b)=2, (c)=2, (d)=3, (e)=2 → C ≈ 0.48 → **Low**. Directional only.
- **AI pilot-to-production.** Gartner's 700-respondent survey found "on average, 54% of AI projects make it from pilot to production" [T2: GEC Newswire reporting Gartner, 2022 survey of 699 respondents, "Only 54% AI projects move from pilot to production," para. on pilot-to-production]. MIT NANDA's "GenAI Divide" report claims 95% of genAI pilots deliver no measurable P&L impact [T3: Fortune, "MIT report: 95% of generative AI pilots at companies are failing," 18 Aug 2025]. The 95% figure has been heavily criticised: it appears twice in 26 pages "neither time … any data attached," is built on 52–150 interviews the authors call "directionally accurate," and applies a narrow success definition [T3: S. Halder, "The MIT 95% AI Failure Rate Is Not What You Think," Medium, 20 Jul 2026; T3: Marketing AI Institute, "That Viral MIT Study … Don't Believe the Hype," 26 Aug 2025]. The spread of published figures (12% IDC, 54% Gartner, 88% Capgemini, 95% MIT) is itself the finding: definitions dominate. Dimensions for the 95% claim: (a)=2, (b)=2, (c)=2, (d)=3, (e)=2 → C ≈ 0.44 → **Very low** as a point estimate; the *directional* claim "a large fraction of AI pilots do not reach production" is Moderate because multiple independent surveys agree.

### 4.3 Constructed/proposed stratum

- **Transformation algebra, enterprise simulator, reference ontology.** These are internally coherent artifacts. They score 1 on directness (they measure themselves) and 1 on evidence type (proposed-by-construction). Even with perfect coherence and large internal test suites: (a)=1, (b)=1, (c)=3 (reproducible by anyone), (d)=3, (e)=5 → C = (45)^(1/5)/5 ≈ 0.43 → **Very low**. The guardrail in §3.3 caps them regardless. Their role in a decision is to *generate hypotheses and structure measurements*, not to supply evidence of world-states. This mirrors how a simulator is used in decision analysis: as a model whose parameters must be calibrated against external data before its outputs are decision-grade.

## 5. Combining, declining to combine, and propagating uncertainty

### 5.1 When to combine — and when not to

Three strata should **not** be pooled into one "evidence score." Pooling a regulator's census with a vendor estimate and a simulator's output implies they measure the same quantity, which they do not. The honest defaults:

- **Combine within a stratum** where studies address the same question and are independent (methodology: treat each study as a data point; if they disagree, widen the interval, per GRADE's inconsistency domain).
- **Report across strata as a bounded range with attribution**, not a mean. The correct output is "directly observed 13–30%; vendor-adjacent 15–54%; constructed ⇒ n/a," never "≈ 30%."
- **Never let constructed evidence move a decision on its own.** It may set priors or define the decision problem, but the prior must be updated by observed evidence before the decision.

### 5.2 A claim resting on a single self-reported source

Survey evidence suffers **common method bias**: when predictor and outcome come from the same respondent and instrument, correlations inflate, and about 40% of variance in single-source assessments can be method variance [T1: Podsakoff et al., *Annual Review of Organizational Psychology and Organizational Behavior*, 11:17–61, 2024, Abstract; T1: "Method biases in single-source personality assessments," PubMed 29595291, Results]. A single self-report also cannot distinguish perception from fact — respondents answer truthfully yet still exhibit reference bias [T1: "Large studies reveal how reference bias limits policy applications of self-report measures," PMC9649615, para. 5]. The representation rule:

> A claim supported only by one party's self-report is represented as an **interval anchored on "unknown," not on the reported point.** Report "claimed X (single self-reported source; independence 2, type 3), evidence tier Very low–Low." It becomes Low only if a *different, non-benefiting* party independently confirms it.

### 5.3 Propagating uncertainty into a decision

The decision-theoretic container is expected value with intervals, refined by value-of-information. The Expected Value of Perfect Information (EVPI) is "the expected value of learning, with certainty, the 'true' values of all model parameters," i.e. "the expected cost of uncertainty associated with making the decision based on the current evidence" [T1: ISPOR VOI Task Force, *Value in Health*, 2020, 23(3), Report 2, Definitions]. Expected Value of Sample Information (EVSI) values *reducing* rather than eliminating uncertainty [T1: Heath et al., *Medical Decision Making*, 2018, "Calculating the Expected Value of Sample Information," Abstract].

Operationally, for a corpus claim feeding a decision:

1. Assign each input a distribution consistent with its tier: High → narrow interval; Moderate → wide; Low/Very low → do not point-estimate.
2. Compute the decision's expected value across the joint distribution (Monte Carlo). If the sign of the expected value is stable across the interval, the decision is robust; if it flips, the decision is uncertainty-bound.
3. Compute partial EVPI for the load-bearing claim. If EVPI is small, gathering better evidence will not change the decision — act on the direction. If EVPI is large and a measurement is feasible, that measurement is the highest-value next action.

This converts "we are not sure" from a stopping condition into a *priced* input: uncertainty has a value, and the scheme tells you where to spend to reduce it.

### 5.4 Rules for "insufficient evidence"

The honest output is **insufficient evidence** when any of the following holds:

- The claim's only support is constructed/proposed-by-construction (directness = 1).
- The only support is a single self-interested source (independence ≤ 2 and motive ≤ 2), with no independent confirmation.
- Independent sources disagree on the *sign* of the effect, not merely the magnitude.
- The measured quantity is not the claimed quantity and no bridge argument exists (e.g., a simulator's internal consistency offered as evidence about a real firm).
- All evidence shares a single method/channel (one survey vendor, one analyst, one dataset lineage) so common-method and publication bias cannot be separated.
- The estimate's confidence interval crosses the decision threshold that would change the action (the GRADE imprecision trigger [T2: GRADE Book, "Overview," imprecision paragraph]).

Insufficient evidence is a *result*, not a failure. It should be reported with the specific missing measurement that would resolve it, so the corpus can target the gap.

## 6. Worked example: eight claims, scored and ranked

Dimension order is (a) type, (b) directness, (c) independence, (d) sample/replication, (e) motive.

| # | Claim | a | b | c | d | e | C | Tier | Decision use |
|---|-------|---|---|---|---|---|---|------|--------------|
| 1 | SEC XBRL custom-tag rate ≈ 17% (2024) | 4 | 5 | 5 | 5 | 4 | 0.92 | High | Act; point estimate usable |
| 2 | GitHub projects <50% survive past 5 yrs | 5 | 5 | 4 | 5 | 5 | 0.95 | High | Act *for OSS population only* |
| 3 | OCEL 2.0 spec exists & is tool-supported | 5 | 5 | 4 | 3 | 5 | 0.88 | High | Act; spec, not representativeness |
| 4 | Most enterprise KG projects stall before production | 2 | 2 | 2 | 2 | 2 | 0.40 | Very low | Direction only if triangulated |
| 5 | 54% of AI projects reach production (Gartner) | 2 | 3 | 3 | 3 | 2 | 0.55 | Low | Directional range member |
| 6 | 95% of genAI pilots yield no P&L impact (MIT) | 2 | 2 | 2 | 3 | 2 | 0.44 | Very low | Do not cite as point estimate |
| 7 | 29% of manufacturers implemented digital twins (2023) | 3 | 2 | 2 | 3 | 2 | 0.48 | Low | Directional |
| 8 | Transformation algebra composes enterprise transformations | 1 | 1 | 3 | 3 | 5 | 0.43 | Very low | Generates hypotheses only |

**Reading the ranking.** Claims 1–3 form the observed core and are the only ones safe to use as decision inputs directly. Claim 2's High confidence is *scoped* — it licenses an inference about OSS repositories, not about enterprise platforms; transferring it is a separate, lower-confidence bridge. Claims 4–7 cluster in Very low to Low and should be reported as a directional band with attribution. Claim 6 illustrates the point that popularity is not confidence: the 95% figure is one of the most-cited statistics in enterprise technology, yet it scores below the much-less-cited Gartner 54% because its independence, directness, and motive scores are all weak and its own methodology lists its limitations.

**Decision implication (worked).** Suppose a decision turns on whether to fund a multi-year enterprise-graph program on the premise that "pilots rarely reach production." The premise rests on claims 4, 5, and 6. Using the tier intervals: observed tier gives no direct estimate for enterprise graphs; the vendor band is 15–54% reaching production. Run the expected-value model across that band. If the program remains net-positive at the pessimistic end (15% reaching production but high value per success), proceed and skip further research. If the sign flips inside the band, compute partial EVPI on the KG pilot-to-production rate. Because no independent measurement of that rate exists (claims 4–6 are all vendor/analyst/self-report), EVPI is likely large and **the highest-value next action is to commission an instrumented, independently-verifiable measurement of pilot-to-production**, not to argue over the existing numbers.

**What would move claim 8 up.** A constructed artifact rises only by acquiring external calibration: e.g., using the transformation algebra to predict an outcome, then checking the prediction against the SEC or repository data in claims 1–2. Constructed *structure* plus observed *calibration* is the only route from Very low to Moderate; coherence alone never is.

## 7. Limitations and maintenance

The scheme inherits known weaknesses. Dimension scores are judgemental; the AMSTAR/ROBIS comparison shows even trained raters disagree in ~9% of cases and inter-rater agreement is only fair for some instruments [T1: *Research Synthesis Methods*, 2026, 17(1):63–92, Results; T1: Cochrane Colloquium 2018, "A comparison of two assessment tools," Results]. The geometric mean is one defensible aggregation among several and should be published alongside the raw dimension vector so readers can re-aggregate. Tier boundaries are conventions, not measurements. Finally, the scheme is a *ceiling on confidence*, not a substitute for domain reasoning: a High-tier measurement of the wrong quantity is still wrong, which is why directness is scored separately from type. Used as intended — to prevent constructed and vendor-adjacent claims from masquerading as observation, and to name the specific missing measurement when the honest answer is "insufficient evidence" — it makes the corpus's confidence claims auditable rather than rhetorical.

## References

**Type 1 — Research papers, peer-reviewed work, conference proceedings**

- Gneiting, T., & Raftery, A. E. (2007). "Strictly Proper Scoring Rules, Prediction, and Estimation." *Journal of the American Statistical Association* 102(477):359–378.
- Colson, A. R., & Cooke, R. M. (2018). "Expert Elicitation: Using the Classical Model to Validate Experts' Judgments." *Review of Environmental Economics and Policy* 12(1).
- Cooke, R. M. "Validating Expert Judgment with the Classical Model." In *Experts and Consensus in Social Science* (Springer).
- Dalkey, N., & Helmer, O. "The Delphi Method: An Experimental Study of Group Opinion." RAND RM-5888.
- Pineau, J., et al. (2021). "Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility Program)." *JMLR* 22(164):1–20.
- "Exploring the methodological quality and risk of bias in 200 systematic reviews: A comparative study of ROBIS and AMSTAR-2 tools." *Research Synthesis Methods* 2026, 17(1):63–92.
- Lewin, S., et al. (2018). "Applying GRADE-CERQual to qualitative evidence synthesis findings." *Implementation Science* 13(Suppl 1).
- Ait, A., Cánovas Izquierdo, J. L., & Cabot, J. (2022). "An Empirical Study on the Survival Rate of GitHub Projects." *MSR '22*, pp. 365–375.
- Avelino, G., Constantinou, E., Valente, M. T., & Serebrenik, A. (2019). "On the abandonment and survival of open source projects." *ESEM 2019*; arXiv:1906.08058.
- Berti, A., et al. (2024). "OCEL (Object-Centric Event Log) 2.0 Specification." arXiv:2403.01975.
- Ghahfarokhi, A. F., Park, G., Berti, A., & van der Aalst, W. M. P. (2021). "OCEL: A Standard for Object-Centric Event Logs." Springer.
- "In Benchmarks We Trust … Or Not?" *EMNLP 2025*.
- "Measuring what Matters: Construct Validity in Large Language Model Benchmarks." arXiv:2511.04703.
- Podsakoff, P. M., et al. (2024). "Common Method Bias: It's Bad, It's Complex, It's Widespread, and It's Not Easy to Fix." *Annual Review of Organizational Psychology and Organizational Behavior* 11:17–61.
- "Method biases in single-source personality assessments." PubMed 29595291.
- "Large studies reveal how reference bias limits policy applications of self-report measures." PMC9649615.
- ISPOR Value of Information Task Force, Report 2. *Value in Health* 2020, 23(3).
- Heath, A., et al. (2018). "Calculating the Expected Value of Sample Information…" *Medical Decision Making*.
- Guyatt, G. H., Oxman, A. D., Vist, G. E., et al. (2008). "GRADE: an emerging consensus on rating quality of evidence and strength of recommendations." *BMJ* 336(7650):924–926.
- GRADE Working Group (2004). "Grading quality of evidence and strength of recommendations." *BMJ*; PMC428525.
- Shea, B. J., et al. (2017). "AMSTAR 2." *BMJ*.
- Flandoli, F., et al. (2011). "Comparison of a new expert elicitation model with the Classical Model." *Reliability Engineering & System Safety*.

**Type 2 — Official documentation, technical specs, white papers, books, renowned domain sources**

- GRADE Working Group. *GRADE Book*, "Overview of the GRADE approach" (Table 2).
- NHMRC. "Assessing certainty of evidence using GRADE," Attachment D.
- Cochrane. "Risk of bias" collection; RoB 2 and ROBINS-I guidance.
- GRADE-CERQual. "Overall confidence in the evidence"; "What is GRADE-CERQual?"
- 2019 *Cochrane Handbook for Systematic Reviews of Interventions*, version 6, ch. on RoB 2.
- WHO EMRO. "A new tool developed by WHO and academic partners…" (CERQual).
- Pineau, J. "The Machine Learning Reproducibility Checklist v2.0."
- Gartner. "Hype Cycle for Data, Analytics and AI Programs, 2024"; "Hype Cycle Research Methodology"; "Magic Quadrant for Analytics and BI Platforms" (disclaimer).
- Gartner. "Gartner Survey Reveals Digital Twins Are Entering Mainstream Use," 20 Feb 2019; "…Nearly Half of Organizations Implementing IoT…," 13 Mar 2018.
- SEC DERA. "Staff Observations of Custom Tag Rates"; "U.S. GAAP – XBRL Custom Tags Trend."
- XBRL US. "SEC Custom Tag Analysis Shows Slight Decline for All Filers," 30 May 2025.
- XBRL International. "SEC Analyse Extension Use," 12 Jul 2019.
- IoT Analytics. "Digital twin market: Analyzing growth and emerging trends," 2023.
- Capgemini Research Institute. "Digital Twins: Adding Intelligence to the Real World," 2021 (N=1,000).
- Enterprise Knowledge (L. Tesfaye). "Why Graph Implementations Fail," 9 Jan 2025.
- Good Judgment Inc. "Superforecasters: A Decade of Stochastic Dominance," 2021.
- GEC Newswire (reporting Gartner). "Only 54% AI projects move from pilot to production," 2022.
- MIT Project NANDA. *The GenAI Divide: State of AI in Business 2025*.
- *Computing*. "Court allows NetScout accusation of Gartner Magic Quadrant 'pay for play'…," 17 Dec 2015.

**Type 3 — Social posts, blogs, podcasts, talks**

- AI Impacts (Kokotajlo). "Evidence on good forecasting practices from the Good Judgment Project." aiimpacts.org; gwern mirror.
- Wikipedia. "Gartner hype cycle," "Criticisms of the model."
- Atlan (K. Pasupathy). "Enterprise Knowledge Graph Pitfalls," atlan.com/knowledge-graph/enterprise-knowledge-graph-pitfalls.
- Fortune (S. Estrada). "MIT report: 95% of generative AI pilots at companies are failing," 18 Aug 2025.
- S. Halder. "The MIT 95% AI Failure Rate Is Not What You Think," Medium, 20 Jul 2026.
- Marketing AI Institute (M. Kaput). "That Viral MIT Study Claiming 95% of AI Pilots Fail? Don't Believe the Hype," 26 Aug 2025.
- Good Judgment. "See the future sooner with Superforecasting," goodjudgment.com; "About Superforecasting."
- CRN / Network World / InfoWorld coverage of Gartner Magic Quadrant "pay-to-play" litigation (ZL Technologies 2009; NetScout 2014).
