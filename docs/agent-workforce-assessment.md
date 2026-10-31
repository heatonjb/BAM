# Assessment: ai-employees and similar agent-workforce repos

Status: assessed 2026-02. Purpose: decide what BAM should integrate, what it should
borrow, and where it must not follow.

**Verdict.** `markfulton/ai-employees` is the most useful prior art we have found for
the *execution* layer, and it independently arrived at BAM's capability/tenant split.
It has no economic model and no business graph — which is exactly the gap BAM fills.
It should be treated as a source of routines and operating discipline, not as an
architecture to copy wholesale.

---

## 1. What it actually is (verified, not from the README)

| Fact | Value |
| --- | --- |
| Licence | MIT |
| Stars | ~821 |
| Language | Node 18+, no dependencies |
| Employees | 8 |
| Routines | 60 |
| Capability maps | 8 (`CAPABILITIES.md`, one per employee) |
| Schedules | 8 (`SCHEDULE.md`, one per employee) |

The eight roles: `ad-manager`, `chief-of-staff`, `customer-satisfaction`,
`gtm-engineer`, `sales`, `seo`, `social-media`, `web-dev`.

An "employee" is **a folder of scheduled routines**, not a chat window and not a
skill. Each folder holds:

```
work-profile.json          per-employee authority and budget profile
CONTRACT.md  ROLE.md       the standing brief
CAPABILITIES.md            capability -> concrete route per harness
SCHEDULE.md                fire times
routines/<id>/SKILL.md     one routine, YAML frontmatter + prompt body
scripts/guard.mjs          the cheap gate, run before anything else
scripts/runlog.mjs         append-only run records
run/<id>.cmd.example       launcher per routine
```

Routines run on a cron-like schedule, drive a real browser, stage their output, and
reconcile into one brief the owner reads with their first coffee. Nothing is hosted;
the files are the product.

### The two ideas worth the licence fee

**The cheap gate.** `guard.mjs` is run *before the skill file is read*. It checks
paused state, day, time window and a once-per-period key from three small JSON files,
writes the run record itself, and lets the routine exit without loading the prompt.
The comment states the motive plainly: a skipped fire used to cost "about a dollar
and a minute or two per skip on a large model" because it read the whole contract
first. This is a real cost insight — **authorisation should be checked before
context is assembled**, not after. BAM's envelope currently checks on the way *back*;
it should also check on the way *in*, before an agent's context is built.

**Capabilities, never tools.** Routine bodies say `page.read`, `file.write`,
`image.compress` — never `playwright.click` or `puppeteer.goto`. One file per kit
maps each capability to a concrete route per harness, with a confidence column. That
is what makes a kit portable across 12+ harnesses. This is the same principle as the
capability/tenant split we adopted, applied to *tooling* rather than to *mechanisms*,
and it is the strongest validation yet that the split is the right axis.

### What it gets right about restraint

Its five laws map almost one-to-one onto decisions already made in BAM:

| ai-employees law | BAM equivalent |
| --- | --- |
| Maximum self reliance — decides, records one assumption line, carries on | agent autonomy inside an envelope |
| Two guardrails, the first is yours — every outbound action ships *held*; `RELEASES.md` is written only by the owner | irreversible actions require approval regardless of size |
| Capabilities, never tools | generic capabilities in core, tenant declares the rest |
| No global skills bloat | no cross-tenant contamination of mechanism declarations |
| Every hard-won rule carries its date and lives in a file | versioned protocol + evidence ledger |

The convergence is not superficial. Two projects, built independently, both concluded
that the safe design is **stage the artefact, hand the last click to the human**. That
is worth noting in the marketing copy, because it is the opposite of how agent
products are usually sold.

### Where it is genuinely weaker than BAM

- **No economic model.** No P&L, no projection, no pricing of a decision. A routine
  can send an email; nothing knows whether the email was worth sending. There is no
  `delta_operating_profit` anywhere in the repo.
- **No graph.** Flat files. No causal structure, so no way to ask "if this routine
  succeeds, which cost line moves?" The word "graph" appears only in web-dev charting.
- **No cross-tenant tenancy.** Single-operator by design. Fine for its purpose; not a
  SaaS foundation.
- **No evidence weighting.** `runlog.jsonl` records that a run happened. It does not
  distinguish a filed fact from an assumption, which BAM's ledger does.

---

## 2. Comparables

| Repo | Stars | What it is | BAM relevance |
| --- | --- | --- | --- |
| `Bennettxai/FounderOS` | ~1.3k | Next.js "business command center": clients, comms, finances, knowledge, roster of AI agents, demo mode | Closest product ambition. Departments + agents + deliverables. UI-first; no economic graph |
| `opsrobot-ai/opsrobot` | ~136 | Observability for "digital employees": tracing, run telemetry | Relevant to evidence/observability. Borrow the tracing vocabulary |
| `1596941391qq/ai-openclaw-skeletons` | ~74 | Pluggable digital-employee skeleton system | Skeleton/portability patterns |
| `rayyagari2-create/agentic-workforce-framework` | ~11 | Operating model for autonomous agent teams: identity, task contracts | Task-contract language; low maturity |

**FounderOS** shares two BAM principles in its `AGENTS.md`: *"Honest or absent —
nothing in the UI may claim a state the system is not actually in"* and *"Tests before
claims"*. Independent convergence on honest-state discipline. Its structure — department
→ agent → deliverable → decision — is a useful vocabulary, but it models *workflow*,
not *economics*. It would not know a deliverable's margin.

None of the four has a business graph or a P&L-coupled decision layer. That remains
BAM's differentiator and should stay so.

---

## 3. Integration design

### The layering we should adopt

```
routine (ai-employees)  ->  evidence  ->  graph mutation  ->  decision (BAM)
```

ai-employees supplies the **routine** layer: what gets done, when, by which role, with
the guard/held-action discipline. BAM supplies the **model** layer: what the routine's
output implies for the business, whether the action is worth taking, and what changed
in the graph as a result.

The interface should be the capability vocabulary, not the code. A routine declares
`crm.write`, `email.draft`, `page.read`; BAM declares `graph.read`, `graph.propose`,
`evidence.record`. A routine that wants to change the business model calls
`graph.propose`, never `graph.write`.

### The mutation path (the important part)

An agent must never mutate the graph directly. The path is:

1. **Propose** — agent emits a `GraphMutation` (add/remove node, add/remove edge,
   change a value) with a rationale and the evidence ids that justify it.
2. **Authorise before assembling context** — the guard checks the tenant's envelope,
   quota and the mutation's reversibility *before* the agent does more work. This is
   the cheap-gate lesson, applied to graph changes.
3. **Stage** — the mutation lands in a pending queue file the owner can open, exactly
   as ai-employees stages an unsent draft in the mailbox. Never applied on proposal.
4. **Release** — structural changes (new node type, new cost line, removed revenue
   stream) require owner release. Value updates to existing nodes may auto-apply
   inside a bounded band, because they are reversible and cheap to audit.
5. **Commit** — on release, apply to the graph with provenance: who proposed, what
   evidence, what the previous value was. The ledger keeps both states.

This is the same shape as the existing envelope, extended from *spend* to *structure*.
The reason to be strict: a wrong value update is a bad number; a wrong structural
mutation is a wrong business. Adding a cost line that does not exist silently changes
every margin downstream, and nothing in the current model would flag it.

### What to borrow, concretely

1. **`guard.mjs` as the model for pre-context authorisation.** Cheap JSON checks before
   expensive context assembly. Directly applicable to BAM's dispatch path.
2. **Routine-level period keys.** BAM's idempotency keys are per-request; ai-employees
   scopes them per *period* (`skipped-already-ran`). A daily sales sweep needs the
   period semantics, not the request semantics.
3. **The `held` default for every outbound action**, with a single owner-written release
   file. BAM's envelope already requires approval for irreversible actions; adopting
   "ships held by default" as the default rather than the exception is stricter and
   better.
4. **A capability map with an honest confidence column.** BAM should publish which
   capabilities are implemented per integration, with confidence — not a badge that
   says "connected".
5. **Routine decomposition at ~7 per role.** 60 routines across 8 roles is a good
   granularity: small enough to guard individually, large enough to be a job.

### What not to borrow

- **Markdown-as-architecture for the core.** SKILL.md prompt files are excellent for
  routines and terrible for invariants. Anything that must not be skipped belongs in
  code with a test, not in prose an LLM may skim.
- **Single-operator assumptions.** No tenancy in the design; retrofitting it later is
  the expensive path.

---

## 4. Risks

- **Prompt-file drift.** 60 SKILL.md files with no schema mean routine behaviour is
  only as consistent as the prose. BAM should validate routine frontmatter and required
  sections mechanically before accepting a routine.
- **Browser-driving agents are unreproducible.** Their evidence is a screenshot and a
  runlog line. BAM's ledger should record the *claim* and its provenance, not trust the
  screenshot as proof.
- **Capability maps rot.** A confidence column that is never re-measured becomes a lie.
  If we adopt it, it must be regenerated from test runs, not hand-written.

## 5. Status

Assessed. The graph-mutation path described in section 4 is now built
(`mvp/multiagent/mutations.py`, `test_mutations.py`): propose -> authorise ->
stage -> release -> commit, with an append-only ledger and a bounded
auto-apply band for numeric changes. Structural changes always require an owner
release. Still open: adopting the pre-context authorisation guard into the
existing dispatch path (the guard exists, callers are not yet migrated), and
regenerating the comparison table from test runs rather than hand-writing it.
