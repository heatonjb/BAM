# BAM running on BAM

The strongest demo of a business-optimisation engine is its own P&L. This
document describes how BAM is represented as a tenant inside itself, what that
makes possible, and where the arrangement is circular.

## The tenant

`data/bam/company.json` holds BAM's operating assumptions. `mvp/bam_loader.py`
turns them into a graph with nineteen nodes. The tenant id is `bam`, its loader
is `bam`, and it sits alongside any customer tenant.

Because it is an ordinary tenant, everything already built works on it without
special cases: drill-down, benchmark cohorts, constraint checks, the arbiter,
projections and Monte Carlo. That is the point — if BAM needed a bespoke path to
analyse itself, the tenancy model would be wrong.

## The graph, and why it is not a generic SaaS template

BAM's cost structure has one feature a generic template would hide: **usage
drives cost, and the free tier is deliberately loss-making**.

```
bam_mrr ──┬── bam_pro_mrr      (£99 × accounts)
          ├── bam_scale_mrr    (£499 × accounts)
          └── bam_free_users   (non-paying, consumes inference)

bam_cogs ─┬── bam_inference_cost  ←── bam_arbiter_runs   (the coupling)
          ├── bam_infra_cost
          └── bam_payment_fees

bam_gross_profit = mrr − cogs
bam_op_profit    = gross − staff − overheads
```

The edge from `bam_arbiter_runs` into `bam_inference_cost` is the defining line.
Every free-tier run costs real money. Growth therefore has a price, and the
conversion funnel (`signups → activations → paid`) has to clear it.

At the seeded numbers: £5,956 MRR, £1,289 cost of revenue (72% of it inference),
£4,667 gross profit, £717 operating profit on 900 runs a month.

## Using BAM to optimise BAM

The loop is the normal one, pointed inward:

1. **Diagnose.** Drill `bam_op_profit` → `bam_gross_profit` → `bam_inference_cost`.
   The graph attributes cost to usage, so the constraint is visible.
2. **Propose.** Specialists generate hypotheses on whichever node is binding.
   With a 72% inference share of COGS, the obvious levers are cost-per-run and
   free-tier quota — not price.
3. **Simulate.** Monte Carlo over each hypothesis, with drivers pulled from the
   graph's own dispersion. The fan chart answers "if conversion is worse than
   I think, does this still work".
4. **Execute.** Dispatch to a counterpart agent inside an envelope
   (`mvp/multiagent/interop.py`). See below.
5. **Measure.** Reconciliation writes the variance into the evidence ledger, so
   BAM's priors about *its own* business calibrate the same way they do for a
   café.

The self-referential advantage: BAM's actual metrics are exact, not estimated.
There is no integration gap. Every forecast can be checked against truth within
one month, which makes it the best calibration corpus available.

## Automating the business

`interop.py` splits decision from execution. BAM decides magnitude and risk;
the counterpart agent executes inside an envelope that caps spend, change size,
duration and reversibility, and that treats irreversible actions as
approval-required regardless of size.

For BAM's own machine the routing looks like:

| Bottleneck | Lever | Counterpart | Action |
|---|---|---|---|
| CAC too high | demand_generation | marketing agent | `launch_email_campaign` |
| Free→paid too low | retention | product agent | `ship_experiment` |
| Inference cost per run | cost_reduction | ops agent | `adjust_rota` (model capacity) |
| Churn | retention | marketing agent | `launch_email_campaign` |

A result outside the envelope is rejected with the specific violation, not
renegotiated. That is what makes it safe to let an accounting system spend
money on your behalf.

## The circularity, stated plainly

**BAM evaluating BAM is not independent evidence.** The same model, priors and
benchmark population drive both the recommendation and its assessment. A
systematic bias — say, over-optimism about adoption — appears on both sides of
the comparison and cancels out, making the loop look calibrated when it is not.

Three mitigations, in increasing order of strength:

1. Pre-register the prediction, with a timestamp, before execution. The
   evidence ledger already records the baseline at initiative start; that is
   only honest if it is written before the outcome is known.
2. Hold out. Calibrate on customer tenants, then score BAM. Do not fit and
   evaluate on the same graph.
3. Use BAM's own P&L as the acceptance test, not the sales pitch. If the
   engine cannot find a real lever on a business whose every number it knows
   exactly, the engine is the problem.

## Operating notes

- The tenant is `plan: internal`, excluded from quota enforcement and from
  benchmark cohorts (it would otherwise pollute the `saas` population).
- `data/bam/company.json` is the single place to update assumptions. Edit it and
  the graph follows; nothing is hardcoded in the loader beyond defaults.
- Changing pricing means editing both `company.json` and `mvp/plans.py`, which
  is a duplication worth fixing when pricing settles.
