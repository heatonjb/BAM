"""Checks for agent-to-agent dispatch and the execution envelope.

The point of these tests is the boundary: an autonomous agent that can exceed
the limits it was given is not a delegated executor, it is an unaudited one.
Everything here fails loudly if that boundary moves.
"""

from __future__ import annotations

import sys

FAILS: list[str] = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}{' — ' + detail if detail else ''}")
        FAILS.append(label)


from mvp.multiagent import interop as IO
from mvp.multiagent.hypothesis import Initiative, LeverType


def make_initiative(lever, impact=2000.0, title="Test initiative"):
    return Initiative(
        node_id="pnl_revenue", node_label="Revenue",
        title=title, description="Do the thing",
        lever_type=lever, predicted_impact_gbp=impact,
    )


print("== directory ==")
directory = IO.default_directory()
check("directory has five agent archetypes", len(directory) == 5)
domains = {a.domain for a in directory}
for d in (IO.Domain.MARKETING, IO.Domain.SALES, IO.Domain.PRODUCT,
          IO.Domain.OPERATIONS, IO.Domain.FINANCE):
    check(f"{d.value} agent present", d in domains)
ids = [a.id for a in directory]
check("agent ids are unique", len(ids) == len(set(ids)))

print("== routing ==")
dec_ini = make_initiative(LeverType.DEMAND_GEN)
dec = IO.dispatch(dec_ini, directory)
check("demand generation routes", dec.ok, dec.reason)
check("routed to marketing", dec.task is not None and dec.task.agent_id == "marketing_agent")
check("objective carried over", dec.task.objective == "Do the thing")
check("expected impact carried", dec.task.expected_impact_gbp == 2000.0)

dec2 = IO.dispatch(make_initiative(LeverType.STAFFING), directory)
check("staffing routes to operations", dec2.ok and dec2.task.agent_id == "ops_agent",
      dec2.reason)

class Weird:
    id = "x"
    lever_type = "telepathy"
    predicted_impact_gbp = 10.0
    title = "t"
    description = "d"
    node_id = "n"

bad = IO.dispatch(Weird(), directory)
check("unknown lever is refused, not guessed", not bad.ok)
check("refusal explains why", "telepathy" in bad.reason)

empty = IO.dispatch(make_initiative(LeverType.DEMAND_GEN), [])
check("empty directory refuses", not empty.ok)

print("== envelope ==")
cap = directory[0].can("launch_email_campaign")
env = IO.envelope_for(make_initiative(LeverType.DEMAND_GEN, 2000.0), cap)
check("spend cap is a fraction of the claim", abs(env.max_spend_gbp - 200.0) < 0.01,
      str(env.max_spend_gbp))
check("irreversible action demands approval", env.requires_approval)
check("irreversible action gets a tighter change limit", env.max_change_pct == 5.0)
check("envelope lists the single allowed action",
      env.allowed_actions == ["launch_email_campaign"])

big = IO.envelope_for(make_initiative(LeverType.DEMAND_GEN, 9000.0), cap)
check("a large claim forces approval", big.requires_approval)

reversible = directory[0].can("pause_campaign")
env_rev = IO.envelope_for(make_initiative(LeverType.RETENTION, 500.0), reversible)
check("reversible action needs no approval at small size", not env_rev.requires_approval)
check("reversible action allows a wider change", env_rev.max_change_pct == 15.0)

print("== protocol ==")
req = dec.task.to_request()
check("request declares its protocol version", req["protocol"] == IO.PROTOCOL_VERSION)
check("request carries an idempotency key", bool(req["idempotency_key"]))
check("request carries the envelope", "envelope" in req and "max_spend_gbp" in req["envelope"])
check("request states the reply shape", "reply_with" in req)
# Re-dispatch the *same* initiative: a retry must not double-run the campaign.
same_a = IO.dispatch(dec_ini, directory).task.idempotency_key
check("idempotency key is stable across retries of one initiative",
      same_a == dec.task.idempotency_key)
other_ini = make_initiative(LeverType.DEMAND_GEN, title="A different initiative")
other_key = IO.dispatch(other_ini, directory).task.idempotency_key
check("a different initiative gets a different key", other_key != dec.task.idempotency_key)

print("== result validation ==")
good = {"task_id": dec.task.id, "idempotency_key": dec.task.idempotency_key,
        "status": "completed", "action_taken": "launch_email_campaign",
        "spend_gbp": 150.0, "change_pct": 3.0, "duration_days": 14,
        "metric_before": 20000.0, "metric_after": 21200.0, "notes": "sent"}

v = IO.validate_result(dec.task, good)
check("in-envelope result accepted", v.ok, str(v.violations))
check("completed state recorded", v.state == IO.TaskState.COMPLETED)

over_spend = dict(good, spend_gbp=5000.0)
v = IO.validate_result(dec.task, over_spend)
check("overspend rejected", not v.ok)
check("overspend explains itself", any("exceeds cap" in x for x in v.violations), str(v.violations))

over_change = dict(good, change_pct=40.0)
v = IO.validate_result(dec.task, over_change)
check("change beyond limit rejected", not v.ok)

wrong_action = dict(good, action_taken="delete_everything")
v = IO.validate_result(dec.task, wrong_action)
check("action outside envelope rejected", not v.ok)

wrong_key = dict(good, idempotency_key="abc123")
v = IO.validate_result(dec.task, wrong_key)
check("reply for a different dispatch rejected", not v.ok)

long_run = dict(good, duration_days=120)
v = IO.validate_result(dec.task, long_run)
check("overlong duration rejected", not v.ok)

negative = dict(good, spend_gbp=-10.0)
v = IO.validate_result(dec.task, negative)
check("negative spend rejected", not v.ok)

garbage = IO.validate_result(dec.task, "not a dict")
check("non-object reply rejected", not garbage.ok)

declined = dict(good, status="rejected", spend_gbp=0.0)
v = IO.validate_result(dec.task, declined)
check("a rejection is a valid reply", v.ok and v.state == IO.TaskState.REJECTED)

print("== reconciliation ==")
rec = IO.reconcile(dec.task, good)
check("measured impact derived from before/after", rec["measured_impact_gbp"] == 1200.0,
      str(rec["measured_impact_gbp"]))
check("achievement ratio computed", abs(rec["achievement_ratio"] - 0.6) < 1e-6,
      str(rec["achievement_ratio"]))
check("reconciliation names the agent", rec["agent_id"] == "marketing_agent")

print("== protocol document ==")
doc = IO.protocol_document()
check("document declares version", doc["protocol"] == IO.PROTOCOL_VERSION)
check("document lists states", "completed" in doc["states"])
check("document lists domains", "marketing" in doc["domains"])

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES:")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("All interop checks passed.")
