# Sign-up funnel: time-to-value and data burden

**Date:** 2026-11-18 · **Actor:** simulated new tenant ("Harbour Light Coffee", `coffee_shop`)
**Method:** 30-step HTTP walk of the live service (127.0.0.1:8080), every request logged
(status, redirect, latency, form fields, payloads). Script: `/tmp/simulate_signup.py`.
Raw trace: `/tmp/signup_trace.jsonl` (before), `/tmp/signup_trace_after.jsonl` (after).

## What the funnel actually did (baseline)

| # | phase | request | status | time | note |
|---|-------|---------|--------|------|------|
| 1 | landing | `GET /signup` | 200 | 2 ms | |
| 2 | redirect | `GET /signup` | 302 | 0 ms | → /onboarding/connect |
| 3 | redirect | `GET /onboarding/connect` | 302 | 0 ms | → /onboarding/interview |
| 4 | signup | `POST /signup` | 200 | 171 ms | |
| 5 | interview | `GET /onboarding/interview` | 200 | 60 ms | |
| 6 | redirect | `GET /onboarding/interview` | 302 | 0 ms | → /onboarding/interview |
| 7 | answer | `POST /onboarding/interview` | 200 | 37 ms | [product, 309 chars] |
| 8 | interview | `GET /onboarding/interview` | 200 | 64 ms | |
| 9 | redirect | `GET /onboarding/interview` | 302 | 0 ms | → /onboarding/interview |
| 10 | answer | `POST /onboarding/interview` | 200 | 37 ms | [leads, 252 chars] |
| 11 | interview | `GET /onboarding/interview` | 200 | 35 ms | |
| 12 | redirect | `GET /onboarding/interview` | 302 | 0 ms | → /onboarding/interview |
| 13 | answer | `POST /onboarding/interview` | 200 | 59 ms | [convert, 303 chars] |
| 14 | interview | `GET /onboarding/interview` | 200 | 32 ms | |
| 15 | redirect | `GET /onboarding/interview` | 302 | 0 ms | → /onboarding/interview |
| 16 | answer | `POST /onboarding/interview` | 200 | 59 ms | [retain, 260 chars] |
| 17 | interview | `GET /onboarding/interview` | 200 | 33 ms | |
| 18 | redirect | `GET /onboarding/interview` | 302 | 0 ms | → /onboarding/interview |
| 19 | answer | `POST /onboarding/interview` | 200 | 37 ms | [measure, 231 chars] |
| 20 | interview | `GET /onboarding/interview` | 200 | 55 ms | |
| 21 | redirect | `GET /onboarding/interview` | 302 | 0 ms | → /onboarding/plan |
| 22 | answer | `POST /onboarding/interview` | 200 | 38 ms | [growth, 260 chars] |
| 23 | plan_get | `GET /onboarding/plan` | 200 | 58 ms | |
| 24 | redirect | `GET /onboarding/plan` | 302 | 0 ms | → /onboarding/connect |
| 25 | plan_ack | `POST /onboarding/plan` | 200 | 42 ms | |
| 26 | connect_get | `GET /onboarding/connect` | 200 | 65 ms | 8 providers offered |
| 27 | value_get | `GET /onboarding/value` | 200 | 62 ms | **first value: 3 findings** |
| 28 | connect_api | `POST /api/onboarding/connect` | 200 | 679 ms | ok:false — Nango 400 "Integration does not exist" |
| 29 | state_api | `GET /api/onboarding/state` | 200 | 56 ms | 4/6 steps, 67% |
| 30 | dashboard | `GET /dashboard` | 200 | 16 ms | |

Totals: 30 requests (9 redirects), 6 free-text answers, **1,615 characters typed**, 1.71 s of
server time before the first reading appeared at step 27.

The reading itself (`onboarding.first_value`) is computed from the provisioned template graph —
it needs no interview answers and no connections. It returned Gross margin 76%, staff 53% of
revenue, operating margin 0.4% for this tenant.

## Findings

1. **Value was gated behind data it did not need.** The three readings exist at provisioning
   (step 4). They were first shown at step 27, after 1,615 characters of essay answers. Nothing
   in the reading's inputs depends on those answers.
2. **The hand-off target was hardcoded to the last step.** Sign-up redirected to
   `/onboarding/connect` (step 5 of 6); the connect guard bounced it to the interview — two
   redirect hops that only exist because the handler did not ask the state machine where the
   tenant actually is. `/onboarding/business` had the same hardcoded target.
3. **The escape hatch is buried.** The interview page has a "That's enough — show me the plan"
   button, and `derive_plan` works from a single answer (`test_interview.py` proves it), but the
   default path is six questions.
4. **The real wall is still the connector, not the questionnaire.** `POST /api/onboarding/connect`
   fails for every provider: the Nango project has **zero integrations configured**, so there is
   no data source to connect and no way to replace the template estimates. That is the binding
   constraint on connected value, and it needs provider credentials from outside the system.
5. **Dead-end navigation.** `/onboarding/value` has no interview/plan guard, so it is reachable
   immediately after sign-up, but nothing links to it before the interview and `state()` always
   reports `value` as the last, permanently-`upcoming` step.

## Change shipped

- `mvp/ui/app.py` — sign-up and the business step now hand off to
  `onboarding_mod.next_step_url(...)` instead of a hardcoded `/onboarding/connect`. The state
  machine owns "where next"; handlers stop guessing. Removes one redirect hop per sign-up and
  keeps the funnel correct if the step order ever changes.
- `mvp/ui/app.py` — the interview page computes and passes `first_value`, so the three template
  readings render **before** the first question.
- `mvp/ui/templates/_findings.html` (new) — the finding card extracted from `onboarding.html` so
  the interview preview and the full "first reading" page share one component (`compact` hides
  the follow-up question/gap lines in the preview).
- `mvp/ui/templates/onboarding.html` — preview block on the interview page; value page now
  includes the shared partial.
- `test_onboarding_early_value.py` (new) — pins the invariant: a freshly provisioned tenant has
  ≥1 reading with zero answers and zero connections, the interview is still the current step,
  connect is still gated behind the plan, and `value` has not jumped the step order.

## Result (replayed end to end)

29 requests (8 redirects), first reading at **step 4** instead of step 27, **0 characters typed**
before value. Cost: `first_value` now runs on each interview GET (+~30 ms per request, graph
load). Everything downstream (interview → plan → connect → value) is unchanged and the existing
journey tests still pass (42 tests across `test_interview.py` + `test_onboarding_early_value.py`).

## Correction

The first pass called `/onboarding/value` a dead end. It isn't: the connect page already links to
it ("Next — your first reading") and back to the dashboard ("Skip for now"). The real defect was
narrower — the page had no route guard, so it could be opened before the plan it is supposed to
follow, while `state()` still called it `upcoming`.

## Follow-up (same day): the four open items

Evidence for shortening the interview: `derive_plan` output is **identical** at every answer count
— 5 agents, 10 threads, 5 examples, 7 data needs, 4 benefits — measured at 1, 2, 3, 4, 5 and 6
answers. Only the quoted "why" text changes. The remaining questions sharpen the transcript, not
the proposal.

Shipped:

- **Interview default shortened.** `interview.CORE_AXES = ("demand", "conversion")`;
  `is_complete` is now "completed early" *or* "core axes covered". The default path completes after
  three answers (product, leads, convert) and lands on the plan automatically. The remaining
  questions stay on the page as optional refinement, and the plan page states
  "Built from 3 of 6 answers — add more detail".
- **The reading closes the funnel.** `onboarding.mark_value_seen()` records `value_seen_at` once;
  `state()` reports the value step as done. Passing connect without connecting is recorded as
  `"Skipped — nothing connected yet."` rather than leaving the funnel parked on a step already
  walked past. A finished funnel is 100% and `next_step_url()` returns `/dashboard`.
- **Routing matches the step order.** `/onboarding/value` now requires the plan to be acknowledged,
  like `/onboarding/connect`. No more out-of-order shortcut that disagrees with the step list.
- **Connect page tells the truth per provider.** The route cross-references
  `NangoClient.list_integrations()` and passes `configured_providers`; unconfigured providers are
  disabled, labelled "not set up yet", and an empty project shows a banner instead of eight
  buttons that each fail on click. `None` (lookup failed) keeps the old behaviour — offer the
  button and let the error speak.
- **One write path for tenant flags.** `provisioning.update_tenant_meta()` owns tenants.json
  updates; `interview._write_meta` delegates to it instead of duplicating the lock-free read/write.

**Result (replayed):** 20 requests instead of 30, **3 answers instead of 6, 864 characters typed
instead of 1,615 (−47%)**, plan reached automatically, first reading still on screen 1 (step 4),
funnel terminates at 100%. Connect page renders 8 providers, all marked "not set up yet", 0 dead
clicks. Cost: the connect page now makes one Nango call per load (~570 ms), and `first_value` runs
on each interview GET (~+30 ms).

## Still open

- **Configured providers.** Until at least one Nango integration exists, nothing can be connected
  — the page now says so instead of failing on click. This needs provider OAuth credentials
  entered in Nango; it is not a code problem.
- Shortening below three answers is possible (the plan exists after one) but would drop the
  conversion axis, which is the one most owners cannot see for themselves — a product call, not
  a bug.