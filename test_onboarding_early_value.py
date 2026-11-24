"""Checks that a new tenant gets value before it hands over any data.

The funnel used to withhold everything until six essay answers had been typed.
The three template readings need none of that: they are computable from the
provisioned graph. These checks pin that invariant so a later "gate the value"
refactor fails loudly instead of quietly costing every sign-up a questionnaire.
"""

from __future__ import annotations

import sys

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


from mvp import onboarding as O
from mvp import interview as I
from mvp import provisioning as P
from mvp import types as T

BUSINESS = "Early Value Test Roastery"
entry = P.provision_tenant(BUSINESS, "coffee_shop")
TENANT = entry["id"]

ANSWERS = {
    "product": "We roast beans and sell them wholesale and through two coffee bars.",
    "leads": "Farmers markets and Instagram bring wholesale enquiries in.",
    "convert": "Sample, then a call, then a paid three-month trial.",
}

try:
    print("== a fresh tenant has readings before anything is answered ==")
    check("no interview answers yet", I.load(TENANT)["answers"] in ({}, None),
          str(I.load(TENANT)["answers"]))
    check("interview is not complete", not I.is_complete(TENANT))
    check("nothing is connected", O.state(TENANT)["connections"] == 0)

    fv = O.first_value(TENANT)
    check("a first reading exists anyway", len(fv["findings"]) >= 1, str(len(fv["findings"])))
    check("readings carry a value and a reading",
          all(f.get("value") and f.get("reading") for f in fv["findings"]))
    check("gross margin is the template's, not a placeholder",
          any(f["title"] == "Gross margin" and f["value"].endswith("%") for f in fv["findings"]),
          str([(f["title"], f["value"]) for f in fv["findings"]]))

    print("== the funnel order is unchanged ==")
    st = O.state(TENANT)
    check("the interview is the current step", st["current"] == "interview", st["current"])
    check("sign-ups are handed to the first incomplete step",
          O.next_step_url(TENANT) == "/onboarding/interview", O.next_step_url(TENANT))
    cur = {s["id"]: s["status"] for s in st["steps"]}
    check("connecting is still gated behind the plan", cur.get("connect") != "current", str(cur))
    check("value has not jumped the queue in the step list",
          [s["id"] for s in st["steps"]].index("value") == len(st["steps"]) - 1)

    print("== the plan unlocks once the core axes are covered ==")
    for qid in ("product", "leads", "convert"):
        I.answer(TENANT, ANSWERS[qid])
    check("three answers are enough to plan", I.is_complete(TENANT))
    check("the remaining questions stay available as refinement",
          I.next_question(TENANT) is not None, str(I.next_question(TENANT)))
    plan = I.derive_plan(TENANT)
    check("the plan records how much of the interview it used",
          plan["answers_used"] == 3 and plan["questions_total"] == len(I.QUESTIONS),
          f"{plan['answers_used']}/{plan['questions_total']}")
    check("the proposed team is complete regardless of answer count",
          len(plan["agents"]) == len(T.resolve("coffee_shop").specialists),
          str(len(plan["agents"])))

    print("== the delivered reading closes the funnel ==")
    before = {s["id"]: s["status"] for s in O.state(TENANT)["steps"]}
    check("the reading is not recorded until it is shown", before.get("value") != "done",
          str(before))
    I.acknowledge_plan(TENANT)      # in the app, the reading is only reachable after this
    O.mark_value_seen(TENANT)
    after = {s["id"]: s for s in O.state(TENANT)["steps"]}
    check("the reading reads as delivered", after["value"]["status"] == "done",
          after["value"]["status"])
    check("skipping connect is stated, not hidden",
          "Skipped" in after["connect"]["detail"], after["connect"]["detail"])
    check("a finished funnel hands the owner to the dashboard",
          O.next_step_url(TENANT) == "/dashboard", O.next_step_url(TENANT))
finally:
    P.discard_tenant(TENANT)

print()
if __name__ == "__main__":
    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("All early-value checks passed.")
    sys.exit(0)


def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"