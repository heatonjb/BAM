"""Owner interview: understand the business before asking for its data.

The design constraint (inverted onboarding)
------------------------------------------
Connecting "everything you've ever got" is a big, hard-to-undo-feeling step, and
a new owner has no reason to take it before they trust what the product will do.
The old flow made connection the *price* of seeing anything. This module moves
the interrogation first: the AI asks a short, fixed set of questions about how
the business actually works, derives what the *agent structure* should look like
from the answers, and plays that plan back — **without implementing anything and
without connecting anything**. Only once the owner has seen the plan is data
connection asked for, and by then the reason is already established.

Shape is deterministic: a fixed question set the owner answers in their own
words. The derivation keys on which axis an answer covers, not on parsing prose,
so it cannot silently misread a business. Voice is a future transport over this
same transcript — the transport today is text.

Where things come from (nothing is invented here)
-------------------------------------------------
* which agents to propose  -> ``TypeSpec.specialists`` on the tenant's type
* what each agent owns     -> ``mvp.multiagent.specialist`` roster
* what data it will need   -> ``mvp.multiagent.data_gaps.DEFAULT_REQUIREMENTS``
* the owner's own words    -> the stored transcript
State is derived from what is stored for the tenant, so progress survives
logout and a half-finished signup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import types as type_registry

# ---------------------------------------------------------------------------
# The question set
# ---------------------------------------------------------------------------

#: Questions target one axis each. The axis — not the prose — is what the
#: derivation keys on, so an owner can answer in any depth or wording.
QUESTIONS: List[Dict[str, str]] = [
    {"id": "product", "axis": "offering",
     "prompt": "What's the product, and how does it work?"},
    {"id": "leads", "axis": "demand",
     "prompt": "How do you get leads in?"},
    {"id": "convert", "axis": "conversion",
     "prompt": "How do you turn a lead into a sale?"},
    {"id": "retain", "axis": "retention",
     "prompt": "How do you keep customers, and how does that drive loyalty?"},
    {"id": "measure", "axis": "measurement",
     "prompt": "How do you measure success?"},
    {"id": "growth", "axis": "growth",
     "prompt": "What are your growth plans?"},
]

QUESTION_IDS = [q["id"] for q in QUESTIONS]

#: Axes that must be covered before the plan is offered by default. The rest of
#: the question set stays available as refinement once the plan exists.
CORE_AXES: tuple = ("demand", "conversion")
_BY_ID = {q["id"]: q for q in QUESTIONS}

#: Which specialists an answer on a given axis is evidence *for*. The type
#: template says which agents run; the answers say which ones this owner cares
#: about, and in their own words.
_AXIS_SPECIALISTS: Dict[str, List[str]] = {
    "offering": ["operations", "cost"],
    "demand": ["marketing", "revenue"],
    "conversion": ["revenue", "marketing"],
    "retention": ["marketing", "revenue"],
    "measurement": ["revenue", "cost"],
    "growth": ["revenue", "marketing", "operations"],
}

#: Order agents are presented in. Stable and intentional, not alphabetical.
_AGENT_ORDER = ["revenue", "marketing", "cost", "operations", "staffing"]

#: How two agents in the team depend on each other, keyed by the pair.
_THREADS: Dict[frozenset, str] = {
    frozenset({"marketing", "revenue"}):
        "Marketing brings demand in; Revenue turns it into price, mix and repeat business.",
    frozenset({"cost", "staffing"}):
        "Cost Controller and Staffing Agent both guard margin — procurement and waste "
        "on one side, rota and productivity on the other.",
    frozenset({"operations", "revenue"}):
        "Operations keeps throughput honest, so revenue is delivered rather than forecast.",
    frozenset({"cost", "revenue"}):
        "Revenue and Cost Controller share one question: grow the top line without "
        "letting unit cost drift.",
    frozenset({"marketing", "operations"}):
        "Marketing promises what Operations has to deliver — capacity has to keep up with demand.",
    frozenset({"revenue", "staffing"}):
        "Revenue sets the target; Staffing Agent says what labour it actually takes to hit it.",
    frozenset({"cost", "operations"}):
        "Operations surfaces where work is wasted; Cost Controller prices the fix.",
    frozenset({"marketing", "staffing"}):
        "Marketing moves demand; Staffing Agent keeps the rota able to serve it.",
    frozenset({"operations", "staffing"}):
        "Operations and Staffing Agent split the same constraint — process versus people.",
    frozenset({"cost", "marketing"}):
        "Marketing spends; Cost Controller measures whether the spend earned its keep.",
}

#: A first, illustrative initiative per agent. Grounded in the metric the agent
#: owns — no promises about numbers that have not been measured yet.
_EXAMPLE_LEVER = {
    "revenue": "pricing and mix",
    "marketing": "demand generation and retention",
    "cost": "supplier terms and waste",
    "operations": "process and capacity",
    "staffing": "rota and productivity",
}

#: What each answer adds to the *model*, if the template does not already have
#: it. The template models the P&L; it does not model how demand arrives, how a
#: lead becomes a sale, or what "success" means to this owner. These nodes carry
#: the owner's description as structure — deliberately with no invented numbers,
#: and only ever process/metric nodes, so no financial total moves.
_SEEDS: Dict[str, Dict[str, str]] = {
    "product": {"node_id": "ob_product", "label": "Product & delivery", "node_type": "process"},
    "leads": {"node_id": "ob_leads", "label": "Lead generation", "node_type": "process"},
    "convert": {"node_id": "ob_convert", "label": "Sales conversion", "node_type": "process"},
    "retain": {"node_id": "ob_retain", "label": "Customer retention", "node_type": "process"},
    "measure": {"node_id": "ob_measure", "label": "Success measures", "node_type": "metric"},
    "growth": {"node_id": "ob_growth", "label": "Growth plan", "node_type": "process"},
}


def _seed_model(tenant_id: str, qid: str, text: str) -> str:
    """Fold one answer into the graph, returning a line to show the owner.

    Returns "" when there is nothing to say (no graph yet, or no seed for this
    question). A failure to seed is reported honestly and never aborts the
    interview — the conversation is the product here, not the mutation.
    """
    seed = _SEEDS.get(qid)
    if not seed:
        return ""
    try:
        from . import graph_chat, tenancy
        graph = tenancy.registry.graph(tenant_id)
    except Exception:
        return ""  # no graph yet (business step not finished) — nothing to seed

    if graph.get(seed["node_id"]) is not None:
        return f"({seed['label']} is already in your model — left as it was.)"

    spec = {
        "ok": True, "kind": "add_node", "node_id": seed["node_id"],
        "payload": {"node_type": seed["node_type"], "label": seed["label"],
                    "root": True, "value": 0.0,
                    "description": text.strip()[:280]},
        "rationale": f"onboarding answer to {qid!r}: {text.strip()[:120]}",
        "evidence_ids": [f"interview:{qid}"],
    }
    result = graph_chat.apply_authorised(tenant_id, graph, spec,
                                         by="owner (onboarding)")
    if result.get("applied"):
        try:
            tenancy.registry.invalidate(tenant_id)  # derived caches must not go stale
        except Exception:
            pass
        return (f"Model updated — {result['summary']}. No numbers invented: it "
                f"records the structure you described, and the figures come when "
                f"you connect data.")
    return f"(Couldn't add {seed['label']}: {result.get('error', 'unknown reason')})"


# ---------------------------------------------------------------------------
# Persistence — the tenant record is the single source of truth
# ---------------------------------------------------------------------------

def _meta(tenant_id: str) -> Dict[str, Any]:
    from . import provisioning
    try:
        return provisioning._read_tenants().get(tenant_id, {}) or {}
    except Exception:
        return {}


def _write_meta(tenant_id: str, patch: Dict[str, Any]) -> bool:
    """Merge ``patch`` into the tenant entry. False if the tenant is unknown."""
    from . import provisioning
    try:
        return provisioning.update_tenant_meta(tenant_id, patch)
    except Exception:
        return False


def _type_of(meta: Dict[str, Any]) -> str:
    for key in ("type_template", "business_type", "type"):
        val = (meta or {}).get(key)
        if val:
            return str(val)
    return ""


def load(tenant_id: str) -> Dict[str, Any]:
    """The stored interview session, with a stable shape even when empty."""
    session = dict(_meta(tenant_id).get("interview") or {})
    session.setdefault("answers", {})
    session.setdefault("transcript", [])
    session.setdefault("completed_at", None)
    return session


def _save(tenant_id: str, session: Dict[str, Any]) -> None:
    _write_meta(tenant_id, {"interview": session})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# The conversation
# ---------------------------------------------------------------------------

def _opener() -> str:
    return (
        "Before you connect anything, tell me how the business actually works. "
        "A few questions — answer as briefly or as fully as you like.\n\n"
        + QUESTIONS[0]["prompt"]
    )


def next_question(tenant_id: str) -> Optional[Dict[str, str]]:
    """First question the owner has not answered yet, or None when finished."""
    answers = load(tenant_id)["answers"]
    for q in QUESTIONS:
        if not (answers.get(q["id"]) or "").strip():
            return q
    return None


def core_answered(tenant_id: str) -> bool:
    """True once the axes the plan is built on are covered.

    Measured evidence: the derived plan (agents, threads, examples, data needs)
    is identical after answer 1 and after answer 6 — the remaining questions
    sharpen the transcript, not the proposal. So the plan unlocks when the two
    axes that carry its narrative are answered, and the rest stay optional.
    """
    answers = load(tenant_id)["answers"]
    covered = {
        _BY_ID[qid].get("axis")
        for qid, text in (answers or {}).items()
        if qid in _BY_ID and (text or "").strip()
    }
    return all(axis in covered for axis in CORE_AXES)


def is_complete(tenant_id: str) -> bool:
    if load(tenant_id)["completed_at"] is not None:
        return True
    return core_answered(tenant_id)


def _reflect(qid: str, text: str) -> str:
    """A short, honest acknowledgement. Deterministic — no model, no pretence."""
    axis = _BY_ID.get(qid, {}).get("axis", "")
    lead = {
        "offering": "Good — that tells me where value is actually created.",
        "demand": "Noted. Demand is the first thing an agent can measure rather than guess.",
        "conversion": "That's the bit most businesses can't see clearly. Useful.",
        "retention": "Retention is where the cheapest growth usually is.",
        "measurement": "Knowing what you already track tells me what's missing.",
        "growth": "That gives the team a direction to work towards.",
    }.get(axis, "Noted.")
    snippet = text.strip()
    if len(snippet) > 140:
        snippet = snippet[:137].rstrip() + "…"
    return f'{lead} You said: “{snippet}”'


def start(tenant_id: str) -> Dict[str, Any]:
    """Begin (or resume) the interview. Idempotent."""
    session = load(tenant_id)
    if not session["transcript"]:
        session["transcript"] = [{"role": "agent", "qid": QUESTIONS[0]["id"],
                                  "text": _opener()}]
        _save(tenant_id, session)
        session = load(tenant_id)
    return session


def answer(tenant_id: str, text: str,
           reflector: Optional[Callable[[str, str], str]] = None) -> Dict[str, Any]:
    """Record one answer and return progress plus the next question.

    ``reflector`` is the seam for a richer (or spoken) reply later; the default
    is deterministic so the flow never depends on a model being reachable.
    """
    text = (text or "").strip()
    q = next_question(tenant_id)
    if q is None or not text:
        return {"ok": False, "reason": "no pending question" if q is None else "empty answer",
                "done": is_complete(tenant_id), "next_question": None}

    session = load(tenant_id)
    session["answers"][q["id"]] = text
    session["transcript"].append({"role": "owner", "qid": q["id"], "text": text})
    session["transcript"].append({
        "role": "agent", "qid": q["id"],
        "text": (reflector or _reflect)(q["id"], text),
    })

    # Fold the answer into the model and show what changed, in the same breath
    # as the question that produced it.
    note = _seed_model(tenant_id, q["id"], text)
    if note:
        session["transcript"].append({"role": "model", "qid": q["id"], "text": note})

    nxt = None
    for cand in QUESTIONS:
        if not (session["answers"].get(cand["id"]) or "").strip():
            nxt = cand
            break

    if nxt is None:
        session["completed_at"] = _now()
        session["transcript"].append({
            "role": "agent", "qid": None,
            "text": "That's everything I need. Let me show you the team I'd build for you — "
                    "nothing gets connected until you've seen it.",
        })
    else:
        session["transcript"].append({"role": "agent", "qid": nxt["id"],
                                      "text": nxt["prompt"]})

    _save(tenant_id, session)
    return {"ok": True, "done": nxt is None, "next_question": nxt,
            "answered": len(session["answers"]), "total": len(QUESTIONS)}


def finish(tenant_id: str) -> Dict[str, Any]:
    """Close the interview early; the plan is built from whatever was said."""
    session = load(tenant_id)
    if not session["completed_at"]:
        session["completed_at"] = _now()
        session["transcript"].append({
            "role": "agent", "qid": None,
            "text": "No problem — I'll work with what you've given me.",
        })
        _save(tenant_id, session)
    return {"ok": True, "answered": len(session["answers"]), "total": len(QUESTIONS)}


# ---------------------------------------------------------------------------
# Deriving the proposed agent structure
# ---------------------------------------------------------------------------

def _resolved(tenant_id: str):
    type_id = _type_of(_meta(tenant_id))
    for candidate in (type_id, "business"):
        if not candidate:
            continue
        try:
            return type_registry.resolve(candidate)
        except Exception:
            continue
    raise type_registry.TypeRegistryError(f"no resolvable type for {type_id!r}")


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _agent_order(keys: set) -> List[str]:
    ordered = [k for k in _AGENT_ORDER if k in keys]
    return ordered or ["revenue", "cost"]


def derive_plan(tenant_id: str) -> Dict[str, Any]:
    """Map the interview onto a proposed agent team. Implements nothing.

    The team is the type template's declared specialists (given runtime meaning
    by the roster); the *why* comes from the owner's own answers, so the playback
    is recognisably about their business and not a generic brochure.
    """
    from .multiagent.data_gaps import DEFAULT_REQUIREMENTS
    from .multiagent.specialist import specialist_for

    resolved = _resolved(tenant_id)
    session = load(tenant_id)
    answers = session["answers"]

    by_axis: Dict[str, str] = {}
    for qid, text in answers.items():
        axis = _BY_ID.get(qid, {}).get("axis")
        if axis and (text or "").strip():
            by_axis[axis] = text.strip()

    keys = _agent_order(set(resolved.specialists))

    agents: List[Dict[str, Any]] = []
    for key in keys:
        agent = specialist_for(key)
        if agent is None:
            continue
        axes = [ax for ax in _AXIS_SPECIALISTS if key in _AXIS_SPECIALISTS[ax] and ax in by_axis]
        evidence = (by_axis.get(axes[0]) or "") if axes else ""
        snippet = evidence[:160].rstrip() + ("…" if len(evidence) > 160 else "")
        agents.append({
            "key": key,
            "id": agent.agent_id,
            "name": agent.name,
            "remit": agent.description,
            "owns": [_enum_value(t) for t in agent.owned_types],
            "levers": [_enum_value(l) for l in agent.relevant_levers()],
            "why": (f'You said: “{snippet}”' if snippet
                    else "Part of how this kind of business is run, based on its shape."),
        })

    present = {a["key"] for a in agents}
    threads = [text for pair, text in _THREADS.items() if pair <= present]

    examples = [
        f"{a['name']}: if its metrics trail the {resolved.benchmark_cohort or resolved.id} "
        f"peer set, {_EXAMPLE_LEVER.get(a['key'], a['key'])} is the first lever it tests."
        for a in agents
    ]

    wanted = set(resolved.canonical_fields or set())
    order = {"critical": 0, "important": 1, "nice": 2}
    data_needed = sorted(
        [
            {"field": r.key, "why": r.description, "severity": r.severity,
             "if_missing": r.fallback}
            for r in DEFAULT_REQUIREMENTS if not wanted or r.key in wanted
        ],
        key=lambda d: order.get(d["severity"], 3),
    )

    plan = {
        "tenant_id": tenant_id,
        "business_type": resolved.id,
        "business_label": resolved.label,
        "business_name": _meta(tenant_id).get("name", ""),
        "generated_at": _now(),
        "acknowledged_at": None,
        "implemented": False,
        "note": ("This is a proposal. Nothing has been built and nothing has been "
                 "connected — connect data only when you're happy with the plan."),
        "answers_used": len(answers),
        "questions_total": len(QUESTIONS),
        "agents": agents,
        "threads": threads,
        "benefits": [
            "Every number on the dashboard gets a named owner instead of a shared shrug.",
            "Recommendations are ranked by your measured gap against similar businesses, "
            "not generic advice.",
            "Agents propose; you authorise. Nothing changes behind your back.",
            "You can see the whole plan before connecting anything — and stop here if "
            "you don't like it.",
        ],
        "examples": examples,
        "data_needed": data_needed,
        "node_families": sorted(resolved.node_families or set()),
    }
    _write_meta(tenant_id, {"agent_plan": plan})
    return plan


def plan(tenant_id: str) -> Optional[Dict[str, Any]]:
    return _meta(tenant_id).get("agent_plan") or None


def is_plan_acknowledged(tenant_id: str) -> bool:
    stored = plan(tenant_id) or {}
    return bool(stored.get("acknowledged_at"))


def acknowledge_plan(tenant_id: str) -> Dict[str, Any]:
    """Mark the plan as reviewed. This is what unlocks the connect step."""
    stored = plan(tenant_id) or derive_plan(tenant_id)
    stored["acknowledged_at"] = _now()
    _write_meta(tenant_id, {"agent_plan": stored})
    return stored


__all__ = [
    "QUESTIONS", "QUESTION_IDS",
    "load", "start", "answer", "finish", "next_question", "is_complete",
    "derive_plan", "plan", "is_plan_acknowledged", "acknowledge_plan",
]
