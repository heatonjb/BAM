"""Checks for seeding the graph from the interview and mutating it by chat.

Two invariants are load-bearing here and easy to lose:

* **Durability.** The graph is rebuilt from files on every read, so a committed
  change is only real if it replays. These checks reload through the app's own
  accessor (``tenancy.registry``) and confirm the change is still there.
* **No invented numbers.** Seeding from an answer records *structure*. It must
  never move a financial total — a zero-value cost line would silently change
  every margin downstream.
"""

from __future__ import annotations

import os
import shutil
import sys

from mvp import graph_chat as GC
from mvp import interview as I
from mvp import provisioning as P
from mvp import tenancy
from mvp.loader import load_graph
from mvp.multiagent.mutations import MutationQueue

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


TENANT = "zz-graphchat-scratch"
BACKUP = P.TENANTS_PATH + ".graphchat-test-backup"
MUT_DIR = P.DATA_ROOT + "/" + TENANT


def _install_scratch() -> None:
    shutil.copy(P.TENANTS_PATH, BACKUP)
    tenants = P._read_tenants()
    tenants[TENANT] = {"id": TENANT, "name": "Scratch Coffee", "number": "STARTER",
                       "data_dir": "jonco", "type": "cafe",
                       "type_template": "coffee_shop"}
    P._write_tenants(tenants)


def _cleanup() -> None:
    shutil.rmtree(MUT_DIR, ignore_errors=True)
    if os.path.exists(BACKUP):
        shutil.move(BACKUP, P.TENANTS_PATH)
    # The scratch tenant no longer exists, but the registry above still caches its
    # graph (the reload assertion re-warms it). Drop it, or every later test that
    # inspects the cache sees a tenant that isn't in tenants.json any more.
    tenancy.registry.invalidate(TENANT)


def _base_graph():
    """A clean graph with no replayed mutations — the reload-free starting point."""
    return load_graph(TENANT)


def _financials(g):
    """Revenue and cost totals only: seeding must leave these untouched."""
    rev = sum(n.value for n in g.nodes.values() if n.node_type.value == "revenue")
    cost = sum(n.value for n in g.nodes.values() if n.node_type.value == "cost")
    return (round(rev, 6), round(cost, 6))


_install_scratch()
try:
    print("== interpreting instructions ==")
    g = _base_graph()
    spec = GC.interpret(g, "set rev_coffee to 4200")
    check("a value set parses", spec.get("ok") and spec["kind"] == "update_value"
          and spec["payload"]["value"] == 4200.0, str(spec)[:120])
    spec = GC.interpret(g, "rename rev_coffee to Coffee beans")
    check("a rename parses", spec.get("ok") and spec["kind"] == "relabel_node"
          and spec["payload"]["label"] == "Coffee beans", str(spec)[:120])
    spec = GC.interpret(g, "link pnl_revenue to cog_beans")
    check("a link parses", spec.get("ok") and spec["kind"] == "add_edge"
          and spec["payload"]["parent"] == "pnl_revenue", str(spec)[:120])
    spec = GC.interpret(g, "unlink pnl_gross_profit from pnl_revenue")
    check("an unlink parses", spec.get("ok") and spec["kind"] == "remove_edge")
    spec = GC.interpret(g, "add cost node Packaging under pnl_overheads value 120")
    check("an add parses type, parent and value",
          spec.get("ok") and spec["kind"] == "add_node"
          and spec["payload"]["node_type"] == "cost"
          and spec["payload"]["parent"] == "pnl_overheads"
          and spec["payload"]["value"] == 120.0, str(spec.get("payload")))
    spec = GC.interpret(g, "add process node Lead gen")
    check("an add with no parent is declared a root",
          spec.get("ok") and spec["payload"].get("root") is True)
    spec = GC.interpret(g, "flibbertigibbet the revenue")
    check("an unrecognised instruction is refused, not guessed",
          not spec.get("ok") and "understand" in spec["error"])
    spec = GC.interpret(g, "set nosuchnode to 5")
    check("an unknown node is refused with a helpful list",
          not spec.get("ok") and "can't find a node" in spec["error"])

    print("== value changes inside the band apply at once ==")
    before = g.get("rev_coffee").value
    res = GC.submit(TENANT, g, f"set rev_coffee to {before * 1.05:.2f}")
    check("a small value change applies", res.get("applied") is True, str(res)[:140])
    check("the graph actually changed",
          abs(g.get("rev_coffee").value - before * 1.05) < 0.01, str(g.get("rev_coffee").value))

    print("== structural changes wait for the owner ==")
    res = GC.submit(TENANT, g, "add cost node Packaging under pnl_overheads value 300")
    check("a new node is staged, not applied",
          res.get("applied") is False and res.get("awaiting_confirmation") is True, str(res)[:140])
    check("nothing was added yet", g.get("packaging") is None)
    check("it is listed as pending", any(p["id"] == res["mutation_id"] for p in GC.pending(TENANT)))

    confirmed = GC.confirm(TENANT, g, res["mutation_id"], by="owner@test")
    check("confirming applies it", confirmed.get("applied") is True, str(confirmed)[:140])
    check("the node now exists", g.get("packaging") is not None)
    check("it is no longer pending", GC.pending(TENANT) == [])

    print("== authorisation still refuses what it should ==")
    dup = GC.submit(TENANT, g, "add cost node Packaging under pnl_overheads")
    check("re-adding an existing node is refused",
          dup.get("applied") is False and "already exists" in dup.get("error", ""), str(dup)[:140])

    print("== durability: a committed change survives a reload ==")
    tenancy.registry.invalidate(TENANT)
    reloaded = tenancy.registry.graph(TENANT)
    check("the added node is there after a fresh load", reloaded.get("packaging") is not None)
    check("the value change is there after a fresh load",
          abs(reloaded.get("rev_coffee").value - before * 1.05) < 0.01,
          str(reloaded.get("rev_coffee").value))

    events = [e for e in MutationQueue(TENANT).history(limit=1000)
              if e.get("event") == "committed"]
    check("the ledger records what to replay", events and all("payload" in e for e in events),
          str(events[:1])[:140])

    print("== seeding the graph from the interview ==")
    shutil.rmtree(MUT_DIR, ignore_errors=True)   # clear the ledger for a clean seed
    tenancy.registry.invalidate(TENANT)
    clean = _base_graph()
    financials_before = _financials(clean)

    I.start(TENANT)
    I.answer(TENANT, "We roast and sell coffee, mostly takeaway.")
    roles = [m["role"] for m in I.load(TENANT)["transcript"]]
    check("the model change is shown in the conversation itself", "model" in roles, str(roles))

    tenancy.registry.invalidate(TENANT)
    g2 = tenancy.registry.graph(TENANT)
    check("answering seeded a node into the graph", g2.get("ob_product") is not None)
    check("the seeded node carries the owner's words",
          "roast" in (g2.get("ob_product").description or "").lower(),
          str(g2.get("ob_product").description)[:80])

    for text in ["Instagram and local flyers.", "We close on the phone.",
                 "A stamp card and an email list.", "Weekly revenue and margin.",
                 "A second site in Haywards Heath."]:
        I.answer(TENANT, text)
    tenancy.registry.invalidate(TENANT)
    g3 = tenancy.registry.graph(TENANT)
    seeded = ["ob_product", "ob_leads", "ob_convert", "ob_retain", "ob_measure", "ob_growth"]
    check("every answered question added its structure",
          all(g3.get(i) is not None for i in seeded),
          str([i for i in seeded if g3.get(i) is None]))
    check("seeded nodes are structural, never financial",
          all(g3.get(i).node_type.value in ("process", "metric") for i in seeded))
    check("seeding moved no financial total",
          _financials(g3) == financials_before,
          f"{_financials(g3)} vs {financials_before}")

    print("== the interview seeds survive a reload too ==")
    tenancy.registry.invalidate(TENANT)
    g4 = tenancy.registry.graph(TENANT)
    check("seeded nodes are still there after a fresh load",
          all(g4.get(i) is not None for i in seeded))
finally:
    _cleanup()

print()
if __name__ == "__main__":
    if FAILS:
        print(f"{len(FAILS)} check(s) failed: {FAILS}")
        sys.exit(1)
    else:
        print("All graph-chat checks passed.")
    sys.exit(1 if FAILS else 0)


def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"
