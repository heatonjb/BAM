"""Checks for the generic-capability / tenant-configuration split.

BAM's core should code generic capabilities only. Tenant agents supply the
commercial choices. These checks assert that boundary holds, because the
failure mode is subtle: a tenant-specific mechanism leaking into core looks
harmless until the second tenant arrives and needs different economics.

They also pin the cross-tenant isolation of mechanism declarations. Mechanism
parameters disclose commercial terms — give-away rate, adoption, discount
depth — so resolving one tenant's mechanism through another is a data leak,
not a convenience.

Run:  python3 test_capabilities.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

from mvp.multiagent import capabilities as C
from mvp.multiagent.breakeven import break_even_lift, clearing_probability
from mvp.multiagent.mechanisms import MECHANISM_REGISTRY
from mvp.multiagent.projection import baseline_from_business

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


# A flat stand-in so these checks do not depend on JonCo's fixture files.
BASE = {
    "revenue": 20_000.0,
    "cogs": 4_800.0,
    "labour": 11_000.0,
    "overheads": 4_000.0,
    "units": 6_000.0,
}

print("== core provides families, not tenants' choices ==")
check("core registers at least one mechanism family", len(MECHANISM_REGISTRY) >= 1)
families = C.list_core_families()
check("families are advertised for tenant discovery", len(families) >= 1,
      str([f["family"] for f in families]))
check("family listing carries a summary",
      all(f["summary"] for f in families), str(families))

print("== tenant declarations ==")
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)

    # No capabilities file: a valid state for a new signup, not an error.
    check("tenant with no declarations resolves to empty",
          C.load_tenant_mechanisms("brand-new", data_root=root) == {})

    spec = C.MechanismSpec(
        name="stamp_9",
        family="loyalty_card",
        params={"n_paid": 9, "adoption_rate": 1.0},
        label="9+1 stamp card",
        lever_type="retention",
        tenant_id="tenant-a",
    )
    C.save_tenant_mechanisms("tenant-a", [spec], data_root=root)

    loaded = C.load_tenant_mechanisms("tenant-a", data_root=root)
    check("declaration round-trips", "stamp_9" in loaded)
    check("declaration keeps tenant's own label",
          loaded["stamp_9"].label == "9+1 stamp card")
    check("declaration keeps parameters",
          loaded["stamp_9"].params["n_paid"] == 9)

    mech = C.get_tenant_mechanism("tenant-a", "stamp_9", data_root=root)
    check("instantiation uses the tenant's name", mech.name == "stamp_9")
    check("instantiation carries the label",
          getattr(mech, "label", "") == "9+1 stamp card")
    check("instantiation applies tenant parameters",
          getattr(mech, "n_paid", None) == 9)
    check("give-away rate follows from the tenant's N",
          abs(mech.giveaway_rate - 0.10) < 1e-9)

    # A second tenant declaring the same family with different terms must not
    # contaminate the first.
    spec_b = C.MechanismSpec(
        name="stamp_19", family="loyalty_card",
        params={"n_paid": 19, "adoption_rate": 1.0},
        label="19+1 card", tenant_id="tenant-b",
    )
    C.save_tenant_mechanisms("tenant-b", [spec_b], data_root=root)
    mb = C.get_tenant_mechanism("tenant-b", "stamp_19", data_root=root)
    check("sibling tenant gets its own parameters",
          abs(mb.giveaway_rate - 0.05) < 1e-9)

    # Cross-tenant access is refused, not silently resolved.
    try:
        C.get_tenant_mechanism("tenant-b", "stamp_9", data_root=root)
        check("cross-tenant instantiation refused", False, "no error raised")
    except C.CrossTenantCapabilityError:
        check("cross-tenant instantiation refused", True)
    except Exception as exc:  # wrong exception type is still a failure
        check("cross-tenant instantiation refused", False, type(exc).__name__)

    try:
        C.get_tenant_mechanism("tenant-a", "does_not_exist", data_root=root)
        check("unknown mechanism raises", False, "no error raised")
    except C.UnknownCapabilityError:
        check("unknown mechanism raises", True)

    # An undeclared family must be reported against the family list, not crash.
    bad = C.MechanismSpec(name="x", family="not_a_family", tenant_id="tenant-a")
    try:
        bad.instantiate()
        check("unknown family raises clearly", False, "no error")
    except C.UnknownCapabilityError as exc:
        check("unknown family names the available families", "loyalty_card" in str(exc))

    # Overrides let an agent retune without rewriting the declaration file.
    tuned = C.get_tenant_mechanism(
        "tenant-a", "stamp_9", data_root=root, overrides={"n_paid": 19}
    )
    check("override retunes without persisting", abs(tuned.giveaway_rate - 0.05) < 1e-9)

print("== break-even inversion is generic ==")
m9 = C.get_tenant_mechanism(
    "jonco", "stamp_card_9", data_root=C.DATA_ROOT
) if (C.DATA_ROOT / "jonco" / "capabilities.json").exists() else None

mech = m9 or MECHANISM_REGISTRY["loyalty_card"](n_paid=9, adoption_rate=1.0)
be = break_even_lift(mech, BASE, months=12)
check("break-even returns a threshold", be.required_lift is not None)
check("threshold is positive for a give-away", be.required_lift > 0)
check("threshold is below the search ceiling", not be.beyond_bound)
check("zero-lift delta is negative", be.zero_lift_delta < 0)
check("extra units are reported when units are known",
      be.required_extra_units is not None and be.required_extra_units > 0)
check("statement is human readable",
      "break even" in be.as_statement().lower())
check("to_dict exposes a percentage",
      isinstance(be.to_dict()["required_lift_pct"], float))

# Thinner give-away must need less lift — this is the whole trade-off, and if
# it ever inverts the model is wrong.
mech19 = MECHANISM_REGISTRY["loyalty_card"](n_paid=19, adoption_rate=1.0)
be19 = break_even_lift(mech19, BASE, months=12)
check("thinner give-away needs less lift", be19.required_lift < be.required_lift,
      f"{be19.required_lift:.3f} vs {be.required_lift:.3f}")

# Already-profitable path needs a genuinely zero-cost mechanism. Note that
# loyalty_card(adoption_rate=0) is NOT zero-cost: the projection engine
# overwrites adoption_rate with the curve's adoption each month, so the
# give-away still happens. A "no-op" mechanism is the honest stand-in.
from mvp.multiagent.mechanisms import Mechanism, MechanismEffect


class _NoOpMechanism(Mechanism):
    """A mechanism with no financial effect — the already-profitable case."""

    name = "no_op"
    lever_type = "other"

    def apply(self, baseline):
        return MechanismEffect(note="no effect")


be_free = break_even_lift(_NoOpMechanism(), BASE, months=12)
check("zero-cost mechanism is already profitable", be_free.already_profitable)
check("already-profitable threshold is zero", be_free.required_lift == 0.0)

# Pin the behaviour that surprised me: the curve owns adoption, not the param.
zero_param = MECHANISM_REGISTRY["loyalty_card"](n_paid=9, adoption_rate=0.0)
be_zero = break_even_lift(zero_param, BASE, months=12)
check("adoption_rate=0 is still not free (curve overrides it)",
      not be_zero.already_profitable and be_zero.required_lift > 0,
      f"required {be_zero.required_lift}")

# Beyond-bound path: an absurd give-away never pays back.
greedy = MECHANISM_REGISTRY["loyalty_card"](n_paid=1, adoption_rate=1.0)
be_greedy = break_even_lift(greedy, BASE, months=12, upper_bound=0.5)
check("absurd give-away reports beyond_bound", be_greedy.beyond_bound)
check("beyond_bound has no threshold", be_greedy.required_lift is None)
check("beyond_bound statement explains why",
      "structurally" in be_greedy.as_statement().lower()
      or "not" in be_greedy.as_statement().lower())

print("== clearing probability ==")
check("probability is undefined without a threshold",
      clearing_probability(be_free, [0.1, 0.2]) is None)
check("probability is undefined for out-of-range mechanisms",
      clearing_probability(be_greedy, [0.1]) is None)
check("probability is undefined without draws",
      clearing_probability(be, []) is None)
check("all draws clearing gives 1.0",
      abs(clearing_probability(be, [1.0, 2.0]) - 1.0) < 1e-9)
check("no draws clearing gives 0.0",
      abs(clearing_probability(be, [0.0, 0.001]) - 0.0) < 1e-9)
half = clearing_probability(be, [be.required_lift * 2, be.required_lift * 0.5])
check("half the draws clearing gives 0.5", abs(half - 0.5) < 1e-9, str(half))

print("== simulation surfaces the threshold ==")
try:
    from mvp.multiagent.montecarlo import simulate
    import mvp.loader as L

    biz = L.load_all("jonco")
    biz = biz[0] if isinstance(biz, tuple) else biz
    res = simulate(
        biz, mechanism_name="stamp_card_9", tenant_id="jonco",
        draws=120, seed=7, months=12,
    )
    stats = res.stats
    check("simulate resolves the tenant's mechanism", "break_even" in stats)
    if "break_even" in stats:
        check("simulation carries a required lift",
              stats["break_even"]["required_lift_pct"] > 0)
        check("simulation explains the zero response assumption",
              stats.get("volume_response_assumed") is False,
              str(stats.get("volume_response_assumed")))
        check("simulation provides an interpretation note",
              "break-even" in stats.get("interpretation", "").lower())
    # The old flat-zero result must still be available, just labelled honestly.
    check("probability of profit still reported", "probability_of_profit" in stats
          or "p_profit" in stats or "mean_delta_profit" in stats)
except Exception as exc:
    check(f"simulate integration failed: {type(exc).__name__}: {exc}", False)

def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"


if __name__ == "__main__":
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print(" -", f)
        sys.exit(1)
    print("All capability checks passed.")
