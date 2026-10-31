"""Checks for graph mutation: propose, authorise, stage, release, commit.

The boundary under test is write access. An agent that can move the graph is an
agent that can redefine the business, so every check here is about the graph
being provably unchanged until an owner releases a change — and being provably
consistent afterwards.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

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


from mvp.model.core import BaseNode, BusinessGraph, NodeType
from mvp.multiagent.mutations import (
    Authorisation,
    GraphMutation,
    MutationKind,
    MutationPolicy,
    MutationQueue,
    MutationRefused,
    MutationStatus,
    STRUCTURAL_KINDS,
    authorise,
)


def build_graph():
    """A two-level P&L fragment: revenue -> cogs."""
    g = BusinessGraph()
    rev = BaseNode(id="revenue", label="Revenue", node_type=NodeType.REVENUE,
                   value=20000.0, level=0)
    cogs = BaseNode(id="cogs", label="Cost of sales", node_type=NodeType.COST,
                    value=4800.0, level=1)
    g.add(rev)
    g.add(cogs)
    rev.children.append("cogs")
    cogs.parents.append("revenue")
    g._adjacency["revenue"] = ["cogs"]
    g._reverse_adj["cogs"] = ["revenue"]
    g.edges.append({"source": "revenue", "target": "cogs", "kind": "composes"})
    return g


def mut(**kw):
    base = dict(tenant_id="jonco", rationale="because the numbers say so",
                proposed_by="test-agent")
    base.update(kw)
    return GraphMutation(**base)


def fresh_queue():
    return MutationQueue("jonco", data_root=pathlib.Path(tempfile.mkdtemp()))


print("== proposing does not move the graph ==")
if True:
    g = build_graph()
    q = fresh_queue()
    m = mut(kind=MutationKind.ADD_NODE.value, node_id="wastage",
            evidence_ids=["ev_1"],
            payload={"node_type": "cost", "label": "Wastage", "value": 300.0,
                     "parent": "cogs"})
    q.propose(m)
    check("graph unchanged after propose", "wastage" not in g.nodes,
          f"nodes={sorted(g.nodes)}")
    check("proposal is staged", [x.id for x in q.staged()] == [m.id])
    check("proposal status is proposed", q.staged()[0].status == "proposed")
    check("nothing in the ledger yet", q.history() == [])

print("== authorisation is decided before any work ==")
if True:
    g = build_graph()
    q = fresh_queue()
    pol = q.load_policy()

    a = authorise(mut(kind=MutationKind.ADD_NODE.value, node_id="wastage",
                      evidence_ids=["ev_1"],
                      payload={"node_type": "cost", "label": "Wastage",
                               "parent": "cogs"}), g, pol)
    check("structural change allowed but needs release",
          a.allowed and a.requires_release and not a.auto_apply, a.reason)

    # A node that already exists cannot be added twice.
    a = authorise(mut(kind=MutationKind.ADD_NODE.value, node_id="cogs",
                      evidence_ids=["ev_1"], payload={"parent": "revenue"}), g, pol)
    check("adding an existing node refused", not a.allowed, a.reason)

    # A value update on a missing node.
    a = authorise(mut(kind=MutationKind.UPDATE_VALUE.value, node_id="ghost",
                      payload={"value": 1.0}), g, pol)
    check("updating a missing node refused", not a.allowed, a.reason)

    # No rationale means no accountability.
    a = authorise(GraphMutation(kind="update_value", tenant_id="jonco",
                                node_id="cogs", rationale="  ",
                                payload={"value": 4900.0}), g, pol)
    check("blank rationale refused", not a.allowed, a.reason)

    # No tenant means no tenancy boundary.
    a = authorise(GraphMutation(kind="update_value", tenant_id="",
                                node_id="cogs", rationale="x",
                                payload={"value": 4900.0}), g, pol)
    check("missing tenant refused", not a.allowed, a.reason)

    # Structural add with no evidence is an unsourced claim.
    a = authorise(mut(kind=MutationKind.ADD_NODE.value, node_id="newline",
                      payload={"parent": "cogs"}), g, pol)
    check("add without evidence refused", not a.allowed, a.reason)

    # A node attached to nothing is invisible to traversal.
    a = authorise(mut(kind=MutationKind.ADD_NODE.value, node_id="floater",
                      evidence_ids=["ev_1"], payload={"label": "Floater"}), g, pol)
    check("floating node refused without root=true", not a.allowed, a.reason)

    a = authorise(mut(kind=MutationKind.ADD_NODE.value, node_id="rootnode",
                      evidence_ids=["ev_1"],
                      payload={"label": "Root", "root": True}), g, pol)
    check("declared root node allowed", a.allowed, a.reason)

    # Quota is enforced at authorisation, not after the run.
    pol_small = MutationPolicy(max_proposals_per_period=2)
    a = authorise(mut(kind=MutationKind.UPDATE_VALUE.value, node_id="cogs",
                      payload={"value": 4900.0}), g, pol_small, proposals_this_period=2)
    check("quota exhausted refused", not a.allowed, a.reason)

    # Kinds outside policy are refused outright.
    pol_narrow = MutationPolicy(allowed_kinds=["update_value"])
    a = authorise(mut(kind=MutationKind.REMOVE_NODE.value, node_id="cogs",
                      evidence_ids=["ev_1"]), g, pol_narrow)
    check("kind outside policy refused", not a.allowed, a.reason)

print("== the value band separates routine drift from restatement ==")
if True:
    g = build_graph()
    q = fresh_queue()

    a = authorise(mut(kind="update_value", node_id="cogs",
                      payload={"value": 5100.0}), g, q.load_policy())
    check("6.25% change auto-applies", a.allowed and a.auto_apply and not a.requires_release,
          a.reason)

    a = authorise(mut(kind="update_value", node_id="cogs",
                      payload={"value": 5300.0}), g, q.load_policy())
    check("10.42% change exceeds the band", a.allowed and not a.auto_apply
          and a.requires_release, a.reason)

    a = authorise(mut(kind="update_value", node_id="cogs",
                      payload={"value": 9000.0}), g, q.load_policy())
    check("87.5% change needs release", a.allowed and a.requires_release, a.reason)

    # From a zero baseline there is no meaningful percentage, so no band applies.
    g.get("cogs").value = 0.0
    a = authorise(mut(kind="update_value", node_id="cogs",
                      payload={"value": 500.0}), g, q.load_policy())
    check("change from zero baseline needs release",
          a.allowed and a.requires_release, a.reason)

    a = authorise(mut(kind="update_value", node_id="cogs",
                      payload={"value": 0.0}), g, q.load_policy())
    check("zero to zero is a no-op", a.allowed and not a.auto_apply
          and not a.requires_release, a.reason)

    a = authorise(mut(kind="update_value", node_id="cogs",
                      payload={"value": "not-a-number"}), g, q.load_policy())
    check("non-numeric value refused", not a.allowed, a.reason)

print("== commit requires a release ==")
if True:
    g = build_graph()
    q = fresh_queue()
    m = mut(kind="update_value", node_id="cogs", payload={"value": 9000.0},
            evidence_ids=["ev_2"])
    q.propose(m)
    refused = False
    try:
        q.commit(m.id, g)
    except MutationRefused:
        refused = True
    check("commit before release refused", refused)
    check("graph still holds the old value", g.get("cogs").value == 4800.0)

    q.release(m.id, "jon")
    q.commit(m.id, g, committed_by="jon")
    check("released mutation commits", g.get("cogs").value == 9000.0)
    check("previous value recorded in the ledger",
          q.history()[-1]["previous"]["value"] == 4800.0)
    check("releaser recorded", q.history()[-1]["released_by"] == "jon")

    # A second commit of the same id would make previous_value a lie.
    refused = False
    try:
        q.commit(m.id, g)
    except MutationRefused:
        refused = True
    check("double commit refused", refused)
    check("value not applied twice", g.get("cogs").value == 9000.0)

print("== value updates carry provenance ==")
if True:
    g = build_graph()
    q = fresh_queue()
    m = mut(kind="update_value", node_id="cogs", payload={"value": 4900.0},
            evidence_ids=["ev_9"], rationale="reconciled to the ledger")
    q.propose(m)
    q.release(m.id, "jon")
    q.commit(m.id, g)
    prov = g.get("cogs").metadata.get("provenance", {})
    check("provenance written to the node", prov.get("mutation_id") == m.id)
    check("evidence ids preserved", prov.get("evidence_ids") == ["ev_9"])
    check("rationale preserved", prov.get("rationale") == "reconciled to the ledger")

print("== add_edge and remove_edge keep both directions true ==")
if True:
    g = build_graph()
    q = fresh_queue()
    g.add(BaseNode(id="marketing", label="Marketing", node_type=NodeType.COST,
                   value=900.0, level=1))

    m = mut(kind="add_edge", node_id="marketing",
            payload={"parent": "revenue", "child": "marketing"})
    a = authorise(m, g, q.load_policy())
    check("add_edge authorised as structural", a.allowed and a.requires_release, a.reason)
    q.propose(m)
    q.release(m.id, "jon")
    q.commit(m.id, g)
    check("child appears in parent.children", "marketing" in g.get("revenue").children)
    check("parent appears in child.parents", "revenue" in g.get("marketing").parents)
    check("adjacency updated", "marketing" in g._adjacency.get("revenue", []))
    check("reverse adjacency updated", "revenue" in g._reverse_adj.get("marketing", []))
    check("edge list updated", any(e["source"] == "revenue" and e["target"] == "marketing"
                                   for e in g.edges))

    # Duplicate edges would double-count in every rollup.
    a = authorise(mut(kind="add_edge", node_id="marketing",
                      payload={"parent": "revenue", "child": "marketing"}), g, q.load_policy())
    check("duplicate edge refused", not a.allowed, a.reason)

    # Missing endpoints.
    a = authorise(mut(kind="add_edge", node_id="x",
                      payload={"parent": "revenue", "child": "nowhere"}), g, q.load_policy())
    check("edge to a missing child refused", not a.allowed, a.reason)

    m2 = mut(kind="remove_edge", node_id="marketing",
             payload={"parent": "revenue", "child": "marketing"})
    q.propose(m2)
    q.release(m2.id, "jon")
    q.commit(m2.id, g)
    check("edge removed from both sides",
          "marketing" not in g.get("revenue").children
          and "revenue" not in g.get("marketing").parents)
    check("edge removed from the edge list",
          not any(e["source"] == "revenue" and e["target"] == "marketing"
                  for e in g.edges))

print("== removing a node cascades its edges ==")
if True:
    g = build_graph()
    q = fresh_queue()

    # cogs has no children, so removal is clean.
    m = mut(kind="remove_node", node_id="cogs", evidence_ids=["ev_4"],
            rationale="merged into overheads")
    a = authorise(m, g, q.load_policy())
    check("leaf removal authorised", a.allowed, a.reason)
    q.propose(m)
    q.release(m.id, "jon")
    q.commit(m.id, g)
    check("node gone", "cogs" not in g.nodes)
    check("parent no longer references it", "cogs" not in g.get("revenue").children)
    check("edge list purged",
          not any("cogs" in (e.get("source"), e.get("target")) for e in g.edges))
    check("adjacency purged", "cogs" not in g._adjacency)

print("== removing a parent that would orphan children is refused ==")
if True:
    g = build_graph()
    q = fresh_queue()

    a = authorise(mut(kind="remove_node", node_id="revenue", evidence_ids=["ev_5"]),
                  g, q.load_policy())
    check("orphaning removal refused", not a.allowed, a.reason)
    check("refusal names the children", "cogs" in a.reason, a.reason)

    a = authorise(mut(kind="remove_node", node_id="revenue", evidence_ids=["ev_5"],
                      payload={"detach_children": True}), g, q.load_policy())
    check("explicit orphaning allowed", a.allowed, a.reason)

    m = mut(kind="remove_node", node_id="revenue", evidence_ids=["ev_5"],
            payload={"detach_children": True})
    q.propose(m)
    q.release(m.id, "jon")
    q.commit(m.id, g)
    check("child survives as an orphan", "cogs" in g.nodes)
    check("orphan's parent link cleared", g.get("cogs").parents == [])
    check("ledger records what was orphaned",
          q.history()[-1]["previous"]["orphaned_children"] == ["cogs"])

print("== tenancy is enforced on the queue ==")
if True:
    q = MutationQueue("acme", data_root=pathlib.Path(tempfile.mkdtemp()))
    refused = False
    try:
        q.propose(mut(kind="update_value", node_id="revenue",
                      payload={"value": 1.0}))
    except MutationRefused:
        refused = True
    check("cross-tenant propose refused", refused)

print("== policy is persisted per tenant ==")
if True:
    q = fresh_queue()
    pol = MutationPolicy(auto_apply_max_pct=2.5, max_proposals_per_period=7)
    q.save_policy(pol)
    loaded = q.load_policy()
    check("policy round-trips", loaded.auto_apply_max_pct == 2.5
          and loaded.max_proposals_per_period == 7)
    check("policy file exists", q.policy_path.exists())
    g = build_graph()
    a = authorise(mut(kind="update_value", node_id="cogs", payload={"value": 5100.0}),
                  g, loaded)
    check("tightened band now requires release",
          a.allowed and a.requires_release, a.reason)

print("== reject removes the proposal without touching the graph ==")
if True:
    g = build_graph()
    q = fresh_queue()
    m = mut(kind="update_value", node_id="cogs", payload={"value": 9000.0})
    q.propose(m)
    q.reject(m.id, "restatement not evidenced")
    check("proposal cleared", q.staged() == [])
    check("graph untouched", g.get("cogs").value == 4800.0)
    events = [h["event"] for h in q.history()]
    check("rejection recorded", "rejected" in events, str(events))
    refused = False
    try:
        q.commit(m.id, g)
    except KeyError:
        refused = True
    check("rejected proposal cannot be committed", refused)

print("== unsupported kinds fail loudly ==")
if True:
    g = build_graph()
    q = fresh_queue()
    pol = MutationPolicy(allowed_kinds=["update_value", "teleport_node"])
    a = authorise(mut(kind="teleport_node", node_id="cogs"), g, pol)
    check("unknown kind refused at authorisation even when policy allows it",
          not a.allowed, a.reason)
    # _apply's fallback still raises if a bad kind reaches it by another route.
    m = mut(kind="teleport_node", node_id="cogs")
    q.propose(m)
    q.release(m.id, "jon")
    raised = False
    try:
        q.commit(m.id, g)
    except MutationRefused:
        raised = True
    check("unknown kind raises on apply", raised)
    events = [h["event"] for h in q.history()]
    check("failed commit recorded", "failed" in events, str(events))

print("== structural kinds are classified correctly ==")
if True:
    kinds = {k.value for k in STRUCTURAL_KINDS}
    check("add_node is structural", "add_node" in kinds)
    check("remove_node is structural", "remove_node" in kinds)
    check("add_edge is structural", "add_edge" in kinds)
    check("remove_edge is structural", "remove_edge" in kinds)
    check("update_value is not structural", "update_value" not in kinds)

if __name__ == "__main__":
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print(f"All {len(RECORDS)} mutation checks passed.")
    sys.exit(0)


def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"
