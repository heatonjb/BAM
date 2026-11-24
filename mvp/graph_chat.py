"""Turning talk into graph changes.

Why this exists
---------------
The mutation ledger (``mvp.multiagent.mutations``) already knows how a change is
proposed, authorised, released and committed. What was missing is the layer that
turns something a person *says* — an onboarding answer, or a typed instruction —
into one of those changes, and reports back what happened. That is the whole of
this module's job, and it deliberately owns no graph logic of its own: every
change goes through ``authorise``/``release``/``commit``, so the trust rules
(evidence required, structural changes need a release, value drift has a band)
apply identically whether the change came from a specialist agent or from the
owner typing a sentence.

Two entry points
----------------
``submit`` — an owner instruction. Value changes inside the policy band apply
immediately; structural changes are staged and returned for explicit
confirmation, because a new or deleted node changes every metric downstream.
``confirm`` — the owner accepts a staged change. Authorisation is re-checked at
confirm time, not just at propose time, so a decision cannot go stale.

Nothing here talks to a model. A bad value is a bad number; a bad structural
change is a wrong business, and a graph is not a good place to be creative. The
parser understands a small, explicit instruction grammar and *says so* when it
does not understand, rather than guessing.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .multiagent.mutations import (
    GraphMutation,
    MutationQueue,
    MutationRefused,
    authorise,
)
from .provisioning import slugify

#: Node types a new node may be given. Mirrors ``NodeType``.
_NODE_TYPES = ("revenue", "cost", "process", "input", "asset", "liability",
               "metric", "aggregate", "equity")

HELP = (
    "I understand these instructions:\n"
    "  • add cost node Packaging under Groceries value 250\n"
    "  • set Coffee to 4200\n"
    "  • rename Milk to Dairy\n"
    "  • link Revenue to Marketing\n"
    "  • unlink Revenue from Marketing\n"
    "  • remove Packaging\n"
    "Node names can be an id or a label."
)


# ---------------------------------------------------------------------------
# Node resolution
# ---------------------------------------------------------------------------

def resolve_node(graph, token: str) -> Optional[str]:
    """Find a node id from an id or a label, exact matches first."""
    if not token:
        return None
    want = token.strip().lower()
    if graph.get(token.strip()):
        return token.strip()
    exact = [n.id for n in graph.nodes.values() if (n.label or "").lower() == want]
    if exact:
        return sorted(exact)[0]
    partial = [n.id for n in graph.nodes.values()
               if want in (n.label or "").lower() or want in n.id.lower()]
    return sorted(partial)[0] if partial else None


def _unknown(graph, token: str) -> str:
    sample = ", ".join(sorted(graph.nodes)[:8])
    return f"I can't find a node called {token!r}. Some ids I have: {sample}…"


# ---------------------------------------------------------------------------
# Instruction -> mutation spec
# ---------------------------------------------------------------------------

def interpret(graph, text: str) -> Dict[str, Any]:
    """Parse one instruction into a mutation spec, or explain why it can't."""
    t = (text or "").strip()
    if not t:
        return {"ok": False, "error": "Say what to change.\n" + HELP}
    rationale = f'owner instruction: "{t}"'
    ev = [f"instruction:{t[:120]}"]

    def fail(msg):
        return {"ok": False, "error": msg}

    # unlink before link — "unlink a from b" would otherwise also match the link rule
    m = re.match(r"^(?:unlink|disconnect)\s+(.+?)\s+(?:from|and)\s+(.+)$", t, re.I)
    if m:
        parent, child = resolve_node(graph, m.group(1)), resolve_node(graph, m.group(2))
        if not parent or not child:
            return fail(_unknown(graph, m.group(1) if not parent else m.group(2)))
        return {"ok": True, "kind": "remove_edge", "node_id": parent,
                "payload": {"parent": parent, "child": child},
                "rationale": rationale, "evidence_ids": ev}

    m = re.match(r"^(?:link|connect|attach)\s+(.+?)\s+(?:to|and)\s+(.+)$", t, re.I)
    if m:
        parent, child = resolve_node(graph, m.group(1)), resolve_node(graph, m.group(2))
        if not parent or not child:
            return fail(_unknown(graph, m.group(1) if not parent else m.group(2)))
        return {"ok": True, "kind": "add_edge", "node_id": parent,
                "payload": {"parent": parent, "child": child},
                "rationale": rationale, "evidence_ids": ev}

    m = (re.match(r"^(?:set|update|change)\s+(.+?)\s+(?:value\s+)?to\s+(-?\d+(?:\.\d+)?)\s*$", t, re.I)
         or re.match(r"^(.+?)\s*=\s*(-?\d+(?:\.\d+)?)\s*$", t))
    if m:
        node = resolve_node(graph, m.group(1))
        if not node:
            return fail(_unknown(graph, m.group(1)))
        return {"ok": True, "kind": "update_value", "node_id": node,
                "payload": {"value": float(m.group(2))},
                "rationale": rationale, "evidence_ids": ev}

    m = re.match(r"^(?:rename|relabel)\s+(.+?)\s+(?:to|as)\s+(.+)$", t, re.I)
    if m:
        node = resolve_node(graph, m.group(1))
        if not node:
            return fail(_unknown(graph, m.group(1)))
        return {"ok": True, "kind": "relabel_node", "node_id": node,
                "payload": {"label": m.group(2).strip()},
                "rationale": rationale, "evidence_ids": ev}

    m = re.match(r"^(?:remove|delete|drop)\s+(.+)$", t, re.I)
    if m:
        node = resolve_node(graph, m.group(1))
        if not node:
            return fail(_unknown(graph, m.group(1)))
        return {"ok": True, "kind": "remove_node", "node_id": node,
                "payload": {}, "rationale": rationale, "evidence_ids": ev}

    if t.lower().startswith("add "):
        rest = t[4:].strip()
        value = None
        mv = re.search(r"\s+value\s+(-?\d+(?:\.\d+)?)\s*$", rest, re.I)
        if mv:
            value = float(mv.group(1))
            rest = rest[:mv.start()].strip()
        parent_token = None
        mp = re.search(r"\s+under\s+(.+)$", rest, re.I)
        if mp:
            parent_token = mp.group(1).strip()
            rest = rest[:mp.start()].strip()
        node_type = "process"
        mt = re.match(r"^(?:a\s+|an\s+)?(%s)\s+(?:node\s+)?(.+)$" % "|".join(_NODE_TYPES), rest, re.I)
        if mt:
            node_type, label = mt.group(1).lower(), mt.group(2).strip()
        else:
            label = re.sub(r"^(?:a\s+|an\s+)?node\s+", "", rest, flags=re.I).strip()
        if not label:
            return fail("An added node needs a name, e.g. 'add cost node Packaging'.")
        payload: Dict[str, Any] = {"node_type": node_type, "label": label,
                                   "value": value if value is not None else 0.0}
        if parent_token:
            parent = resolve_node(graph, parent_token)
            if not parent:
                return fail(_unknown(graph, parent_token))
            payload["parent"] = parent
        else:
            # An unattached node is unreachable by traversal, so it is declared root.
            payload["root"] = True
        return {"ok": True, "kind": "add_node", "node_id": slugify(label),
                "payload": payload, "rationale": rationale, "evidence_ids": ev}

    return fail("I didn't understand that.\n" + HELP)


def describe(m: GraphMutation) -> str:
    """A one-line, human account of what a mutation does."""
    p = m.payload or {}
    if m.kind == "add_node":
        where = f"under {p['parent']}" if p.get("parent") else "at top level"
        return f"add {p.get('node_type', 'process')} node “{p.get('label', m.node_id)}” ({where})"
    if m.kind == "update_value":
        return f"set {m.node_id} to {p.get('value')}"
    if m.kind == "relabel_node":
        return f"rename {m.node_id} to “{p.get('label')}”"
    if m.kind == "remove_node":
        return f"remove node {m.node_id}"
    if m.kind == "add_edge":
        return f"link {p.get('parent')} → {p.get('child')}"
    if m.kind == "remove_edge":
        return f"unlink {p.get('parent')} → {p.get('child')}"
    return f"{m.kind} on {m.node_id}"


# ---------------------------------------------------------------------------
# Applying — always through the ledger's own gates
# ---------------------------------------------------------------------------

def _finish(q: MutationQueue, m: GraphMutation, graph, by: str,
            decision: Any = None) -> Dict[str, Any]:
    q.release(m.id, by)
    q.commit(m.id, graph, committed_by=by)
    out = {"ok": True, "applied": True, "awaiting_confirmation": False,
           "mutation_id": m.id, "summary": describe(m)}
    if decision is not None:
        out["reason"] = decision.reason
        out["authorisation"] = decision.to_dict()
    return out


def apply_authorised(tenant_id: str, graph, spec: Dict[str, Any],
                     by: str) -> Dict[str, Any]:
    """Apply a change the owner has already authored, keeping every policy gate.

    Used where the owner *is* the source of the change — onboarding answers and
    an explicit confirmation — so their act is the release. The policy is still
    consulted in full: quotas, permitted kinds, and every existence rule apply,
    and a refusal is returned rather than worked around.
    """
    if not spec.get("ok"):
        return {"ok": False, "applied": False, "error": spec.get("error", "bad spec")}
    q = MutationQueue(tenant_id)
    m = GraphMutation(
        kind=spec["kind"], tenant_id=tenant_id, node_id=spec["node_id"],
        rationale=spec["rationale"], evidence_ids=list(spec.get("evidence_ids") or []),
        proposed_by=by, payload=spec["payload"],
    )
    q.propose(m)
    decision = authorise(m, graph, q.load_policy(), q.proposals_this_period())
    if not decision.allowed:
        q.reject(m.id, decision.reason)
        return {"ok": False, "applied": False, "error": decision.reason,
                "authorisation": decision.to_dict()}
    return _finish(q, m, graph, by, decision)


def submit(tenant_id: str, graph, text: str, by: str = "owner") -> Dict[str, Any]:
    """Interpret an instruction and either apply it or stage it for confirmation.

    A value change inside the policy band applies now. Anything structural — a
    new or deleted node, an edge — is staged and returned for explicit
    confirmation, because its blast radius is every metric downstream.
    """
    spec = interpret(graph, text)
    if not spec.get("ok"):
        return {"ok": False, "applied": False, "error": spec["error"]}

    q = MutationQueue(tenant_id)
    m = GraphMutation(
        kind=spec["kind"], tenant_id=tenant_id, node_id=spec["node_id"],
        rationale=spec["rationale"], evidence_ids=list(spec.get("evidence_ids") or []),
        proposed_by=by, payload=spec["payload"],
    )
    q.propose(m)
    decision = authorise(m, graph, q.load_policy(), q.proposals_this_period())
    if not decision.allowed:
        q.reject(m.id, decision.reason)
        return {"ok": False, "applied": False, "error": decision.reason,
                "authorisation": decision.to_dict()}

    if not decision.auto_apply:
        return {"ok": True, "applied": False, "awaiting_confirmation": True,
                "mutation_id": m.id, "summary": describe(m),
                "reason": decision.reason, "authorisation": decision.to_dict()}
    return _finish(q, m, graph, by, decision)


def confirm(tenant_id: str, graph, mutation_id: str, by: str = "owner") -> Dict[str, Any]:
    """Accept a staged change. Re-authorised here, so a stale decision can't apply."""
    q = MutationQueue(tenant_id)
    m = next((p for p in q.staged() if p.id == mutation_id), None)
    if m is None:
        return {"ok": False, "applied": False,
                "error": f"no pending change {mutation_id!r} for {tenant_id!r}"}

    decision = authorise(m, graph, q.load_policy(), q.proposals_this_period())
    if not decision.allowed:
        q.reject(m.id, decision.reason)
        return {"ok": False, "applied": False, "error": decision.reason}

    described = describe(m)
    try:
        q.release(m.id, by)
        q.commit(m.id, graph, committed_by=by)
    except MutationRefused as exc:
        return {"ok": False, "applied": False, "error": str(exc)}
    return {"ok": True, "applied": True, "mutation_id": m.id, "summary": described}


def pending(tenant_id: str) -> List[Dict[str, Any]]:
    """Changes awaiting the owner's confirmation."""
    out = []
    for m in MutationQueue(tenant_id).staged():
        out.append({"id": m.id, "kind": m.kind, "node_id": m.node_id,
                    "summary": describe(m), "rationale": m.rationale})
    return out


def recent(tenant_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    """What has actually been committed, newest first — the change history."""
    out = []
    for event in MutationQueue(tenant_id).history(limit=1000):
        if event.get("event") != "committed":
            continue
        out.append({"kind": event.get("kind"), "node_id": event.get("node_id"),
                    "rationale": event.get("rationale", ""),
                    "by": event.get("by", ""), "at": event.get("at", "")})
    return list(reversed(out))[:limit]


__all__ = ["HELP", "interpret", "describe", "resolve_node", "submit",
           "confirm", "apply_authorised", "pending", "recent"]
