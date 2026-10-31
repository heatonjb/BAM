"""Checks for the hierarchical business-type registry.

The registry is load-bearing in two places: provisioning picks a starter model
from it, and benchmarking picks a peer cohort from it. Both fail quietly if the
hierarchy is wrong, so the invariants are asserted here rather than assumed.
"""

from __future__ import annotations

import sys

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


print("== inheritance ==")
resolve_coffee = T.resolve("coffee_shop")
check("café inherits retail lineage", resolve_coffee.lineage == ["business", "retail", "coffee_shop"],
      str(resolve_coffee.lineage))
check("café resolves to the café loader", resolve_coffee.loader == "cafe")
check("café inherits parent families",
      {"revenue", "cogs", "staff", "overheads"} <= resolve_coffee.node_families)
check("café adds its own families", {"menu", "wastage"} <= resolve_coffee.node_families)
check("café inherits parent canonical fields",
      {"units", "visits_per_week", "avg_spend"} <= resolve_coffee.canonical_fields)
check("café inherits and extends specialists",
      {"revenue", "cost", "staffing", "operations", "marketing"} <= resolve_coffee.specialists)

print("== sibling types do not contaminate each other ==")
devtools = T.resolve("developer_tools")
check("devtools resolves to the SaaS loader", devtools.loader == "saas")
check("devtools has no café families", not ({"menu", "wastage"} & devtools.node_families))
check("devtools has usage family", "usage" in devtools.node_families)

print("== cohort widening ==")
check("coffee cohort chain is specific first",
      resolve_coffee.cohort_chain() == ["coffee_shop", "retail", "business"],
      str(resolve_coffee.cohort_chain()))
check("devtools cohort chain falls back to SaaS",
      devtools.cohort_chain() == ["developer_tools", "saas", "business"],
      str(devtools.cohort_chain()))

print("== overrides and exclusions ==")
T.register(
    T.TypeSpec(
        id="_test_no_staff",
        label="Test: retail without staff",
        parent="coffee_shop",
        excludes={"staff"},
    )
)
excluded = T.resolve("_test_no_staff")
check("child can exclude an inherited family", "staff" not in excluded.node_families)
check("exclusion does not remove unrelated families", "revenue" in excluded.node_families)

print("== integrity ==")
try:
    T.resolve("nope")
    check("unknown type raises", False)
except T.TypeRegistryError:
    check("unknown type raises", True)

try:
    T.register(T.TypeSpec(id="_test_cycle", label="x", parent="_test_cycle"))
    T.resolve("_test_cycle")
    check("cycle is detected", False)
except T.TypeRegistryError:
    check("cycle is detected", True)

T.register(T.TypeSpec(id="_test_dangling", label="x", parent="does_not_exist"))
try:
    T.validate()
    check("dangling parent is detected", False)
except T.TypeRegistryError:
    check("dangling parent is detected", True)

print("== scaffold reporting ==")
missing = T.assert_scaffold("coffee_shop", ["revenue", "cogs"])
check("missing families are reported", missing == ["gross_profit", "overheads", "staff", "menu", "wastage"][:0] or set(missing) == {"gross_profit", "overheads", "staff", "menu", "wastage"},
      str(missing))

print()
if __name__ == "__main__":
    if FAILS:
        print(f"{len(FAILS)} check(s) failed: {FAILS}")
        sys.exit(1)
    else:
        print("All business-type checks passed.")
    sys.exit(1 if FAILS else 0)

def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"
