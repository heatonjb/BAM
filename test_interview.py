"""Checks for the owner interview and the derived agent-structure proposal.

The product decision under test is the *order*: interrogate the owner, show a
proposed agent team, and only then ask for data. These assertions pin that order,
the derivation it rests on, and the guarantee that nothing is connected — or
implemented — before the owner has seen the plan.
"""

from __future__ import annotations

import os
import shutil
import sys

from mvp import interview as I
from mvp import onboarding as O
from mvp import provisioning as P
from mvp import types as T

FAILS: list[str] = []

RECORDS: list = []


def check(label, cond, detail=""):
    ok = bool(cond)
    RECORDS.append((str(label), ok, str(detail)))
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}{' — ' + detail if detail else ''}")
        FAILS.append(str(label))


#: A scratch tenant so the real tenants.json is never the thing under test.
TENANT = "zz-interview-scratch"
BACKUP = P.TENANTS_PATH + ".interview-test-backup"


def _install_scratch() -> None:
    shutil.copy(P.TENANTS_PATH, BACKUP)
    tenants = P._read_tenants()
    tenants[TENANT] = {
        "id": TENANT, "name": "Scratch Coffee", "number": "STARTER",
        "data_dir": "jonco",              # reuse a real graph dir; not connecting anything
        "type": "cafe", "type_template": "coffee_shop",
    }
    P._write_tenants(tenants)


def _restore() -> None:
    # The interview now seeds the graph, which writes a mutation ledger under
    # each scratch tenant; remove it so the test leaves nothing in data/.
    for tid in (TENANT, TENANT + "-2"):
        shutil.rmtree(os.path.join(P.DATA_ROOT, tid), ignore_errors=True)
    if os.path.exists(BACKUP):
        shutil.move(BACKUP, P.TENANTS_PATH)


_install_scratch()
try:
    print("== the question set ==")
    check("six questions, in the order the owner asked for",
          I.QUESTION_IDS == ["product", "leads", "convert", "retain", "measure", "growth"],
          str(I.QUESTION_IDS))
    check("questions interrogate the business, not the data",
          not any("connect" in q["prompt"].lower() for q in I.QUESTIONS))

    print("== the interview starts before anything is connected ==")
    I.start(TENANT)
    check("a fresh tenant is not complete", not I.is_complete(TENANT))
    check("opening message is stored", len(I.load(TENANT)["transcript"]) >= 1)
    q = I.next_question(TENANT)
    check("the first question is the product one", bool(q) and q["id"] == "product", str(q))
    check("no data is required to start", O.state(TENANT)["connections"] == 0)

    print("== answering ==")
    r = I.answer(TENANT, "We roast and sell coffee, mostly takeaway.")
    check("the answer is recorded", I.load(TENANT)["answers"].get("product", "").startswith("We roast"))
    check("progress advances to the next question",
          bool(r["next_question"]) and r["next_question"]["id"] == "leads", str(r.get("next_question")))
    roles = [m["role"] for m in I.load(TENANT)["transcript"]]
    check("the transcript records both sides", "owner" in roles and "agent" in roles, str(roles[:4]))

    print("== the reply seam (voice later) ==")
    I.answer(TENANT, "Instagram and local flyers.", reflector=lambda qid, text: "SPOKEN-ACK")
    check("a reflector can replace the agent reply",
          any(m["text"] == "SPOKEN-ACK" for m in I.load(TENANT)["transcript"]))

    print("== completing the interview ==")
    for text in ["We close on the phone.", "A stamp card and an email list.",
                 "Weekly revenue and margin.", "A second site in Haywards Heath."]:
        I.answer(TENANT, text)
    check("interview completes once every question is answered", I.is_complete(TENANT))
    check("no question remains", I.next_question(TENANT) is None)
    check("answering every question records all six",
          len(I.load(TENANT)["answers"]) == len(I.QUESTIONS))

    print("== the plan is derived, not implemented ==")
    plan = I.derive_plan(TENANT)
    check("the plan is a proposal, not a build", plan["implemented"] is False)
    check("nothing was connected to produce it", O.state(TENANT)["connections"] == 0)
    check("the proposed team is exactly the type template's specialists",
          {a["key"] for a in plan["agents"]} == set(T.resolve("coffee_shop").specialists),
          f"plan={sorted(a['key'] for a in plan['agents'])} "
          f"template={sorted(T.resolve('coffee_shop').specialists)}")
    check("each agent states its remit", all(a.get("remit") for a in plan["agents"]))
    check("the plan quotes the owner's own words back",
          any("You said" in a["why"] for a in plan["agents"]),
          str([a["why"] for a in plan["agents"]][:1]))
    check("agents are described working together", len(plan["threads"]) > 0, str(len(plan["threads"])))
    check("the plan names the data that would sharpen it",
          any(d["field"] == "revenue" for d in plan["data_needed"]),
          str([d["field"] for d in plan["data_needed"]][:4]))
    check("data needs are ranked, criticals first",
          [d["severity"] for d in plan["data_needed"]][:1] == ["critical"])
    check("the plan is stored against the tenant",
          (I.plan(TENANT) or {}).get("tenant_id") == TENANT)

    print("== connecting is gated behind reviewing the plan ==")
    check("connect is locked until the plan is reviewed", not I.is_plan_acknowledged(TENANT))
    cur = {s["id"]: s["status"] for s in O.state(TENANT)["steps"]}
    check("the interview reads as done", cur.get("interview") == "done", str(cur))
    check("the plan is the current step", cur.get("plan") == "current", str(cur))
    check("connecting is not the current step", cur.get("connect") != "current", str(cur))
    check("the next step the app sends you to is the plan",
          O.next_step_url(TENANT) == "/onboarding/plan", O.next_step_url(TENANT))

    I.acknowledge_plan(TENANT)
    cur2 = {s["id"]: s["status"] for s in O.state(TENANT)["steps"]}
    check("reviewing the plan marks it done", cur2.get("plan") == "done", str(cur2))
    check("reviewing the plan unlocks connecting", cur2.get("connect") == "current", str(cur2))
    check("the app now sends you to connect",
          O.next_step_url(TENANT) == "/onboarding/connect", O.next_step_url(TENANT))

    print("== finishing early still yields a plan ==")
    OTHER = TENANT + "-2"
    tenants = P._read_tenants()
    tenants[OTHER] = dict(tenants[TENANT], id=OTHER)
    P._write_tenants(tenants)
    I.start(OTHER)
    I.answer(OTHER, "Only answered one thing.")
    I.finish(OTHER)
    check("a partial interview is still complete enough to plan", I.is_complete(OTHER))
    plan2 = I.derive_plan(OTHER)
    check("a partial interview still yields the template's team",
          {a["key"] for a in plan2["agents"]} == set(T.resolve("coffee_shop").specialists))
finally:
    _restore()

print()
if __name__ == "__main__":
    if FAILS:
        print(f"{len(FAILS)} check(s) failed: {FAILS}")
        sys.exit(1)
    else:
        print("All interview checks passed.")
    sys.exit(1 if FAILS else 0)


def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"
