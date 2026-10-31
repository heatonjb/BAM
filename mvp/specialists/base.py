"""Specialist lenses — a generic BAM capability.

A specialist is not an agent that acts. It is a *lens*: a body of condensed
thinking that a tenant can consult for a second viewpoint on a decision.

Why this is a core capability and not a tenant agent
----------------------------------------------------
The directive is that core codes generic capabilities and tenant agents do the
rest. A lens qualifies as generic on a specific test: **its content does not
depend on any tenant's data.** Paul Graham's essays are the same essays for a
café and a SaaS company. What changes per tenant is which principle applies and
what it implies for that business — and that judgement is made at call time
against the tenant's own situation text.

So core owns the lens, its condensed principles and its honest limits. The
tenant supplies the situation and decides whether to act.

Advisory only
-------------
A specialist returns a ``Viewpoint``. It cannot mutate a graph, dispatch an
agent or spend money. Any change that follows from its advice goes through the
same ``GraphMutation`` propose/stage/release path as any other agent. This
matters: an opinion that can act on its own is indistinguishable from a policy.

The limits are part of the product
----------------------------------
Every lens ships with a ``limits`` list stating where its author's experience
does not transfer. An agent that only returns supporting arguments is a
persuasion device. The viewpoint always includes the caveats and the
counter-reading, because a founder should be told when the lens is the wrong
tool, not only when it agrees.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SPECIALISTS_ROOT = pathlib.Path(__file__).resolve().parents[2] / "data" / "specialists"

#: Words that carry no retrieval signal. Kept small deliberately: an aggressive
#: stoplist would strip the business vocabulary that matters.
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this",
    "these", "those", "is", "are", "was", "were", "be", "been", "being", "to",
    "of", "in", "on", "at", "for", "with", "by", "from", "as", "it", "its",
    "we", "our", "us", "i", "you", "your", "they", "them", "their", "he", "she",
    "do", "does", "did", "can", "could", "should", "would", "will", "may",
    "have", "has", "had", "not", "no", "so", "about", "into", "over", "more",
    "most", "very", "just", "also", "how", "what", "when", "where", "which",
    "who", "why", "there", "here", "now", "new", "get", "got", "make", "made",
}

#: Domain hints let a tenant's phrasing route to a principle even when the words
#: differ. Deliberately coarse: false positives are cheap to filter by reading.
DOMAIN_HINTS: Dict[str, List[str]] = {
    "growth": ["growth", "grow", "acquisition", "acquir", "users", "customers",
               "traction", "scale", "viral", "referral", "marketing", "campaign",
               "loyalty", "repeat", "retention", "churn", "promotion", "offer",
               "volume", "frequency", "visits", "footfall"],
    "product": ["product", "feature", "build", "ship", "roadmap", "mvp", "launch",
                "usability", "ux", "scope", "quality"],
    "hiring": ["hire", "hiring", "recruit", "team", "manager", "management",
               "delegat", "headcount", "staff", "founder mode", "head of",
               "sales team", "pipeline", "account executive", "commission",
               "salesperson", "sales rep"],
    "pricing": ["price", "pricing", "margin", "revenue", "cost", "profit",
                "unit economics", "discount", "wealth", "value capture",
                "give away", "giveaway", "free", "cogs", "gross margin"],
    "focus": ["focus", "distract", "priorit", "calendar", "meeting", "time",
              "procrastinat", "attention", "bandwidth", "busy"],
    "culture": ["culture", "values", "conflict", "argument", "identity", "mean",
                "hiring bar", "team dynamics", "morale"],
    "founder": ["founder", "commitment", "determination", "persist", "risk",
                "burnout", "quit", "motivation", "ambition"],
    "strategy": ["strategy", "competit", "market", "moat", "positioning",
                 "differentiat", "opportunity", "consensus", "industry"],
}


@dataclass
class RetrievedPrinciple:
    """A principle that fired for a situation, with why it fired."""

    id: str
    gist: str
    essay: str
    url: str
    implication: str
    domain: str
    verbatim: str = ""
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "gist": self.gist,
            "essay": self.essay,
            "url": self.url,
            "implication": self.implication,
            "domain": self.domain,
            "quote": self.verbatim,
            "match_score": round(self.score, 3),
            "matched_because": self.reasons,
        }


@dataclass
class Viewpoint:
    """What a lens says about a situation. Advice, never action."""

    specialist: str
    lens: str
    situation: str
    principles: List[RetrievedPrinciple]
    questions: List[str]
    caveats: List[str]
    reading: str = ""
    advisory_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "specialist": self.specialist,
            "lens": self.lens,
            "situation": self.situation,
            "reading": self.reading,
            "principles": [p.to_dict() for p in self.principles],
            "questions_to_answer": self.questions,
            "caveats": self.caveats,
            "advisory_only": self.advisory_only,
            "note": (
                "This is a viewpoint, not a recommendation and not an action. "
                "Any change to the business graph must go through the mutation "
                "path: propose, authorise, stage, release, commit."
            ),
        }

    def as_brief(self) -> str:
        """Short text form for an agent envelope or a UI card."""
        lines = [f"{self.specialist} — {self.lens}", ""]
        if self.reading:
            lines += [self.reading, ""]
        for i, p in enumerate(self.principles, 1):
            lines.append(f"{i}. {p.gist}")
            lines.append(f"   -> {p.implication}")
            lines.append(f"   ({p.essay}, {p.url})")
        if self.questions:
            lines.append("")
            lines.append("Questions this raises:")
            lines += [f" - {q}" for q in self.questions]
        if self.caveats:
            lines.append("")
            lines.append("Where this lens does not apply:")
            lines += [f" - {c}" for c in self.caveats]
        return "\n".join(lines)


def _tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower())
            if w not in STOPWORDS]


def _domains_for(text: str) -> Dict[str, int]:
    low = text.lower()
    hits: Dict[str, int] = {}
    for domain, hints in DOMAIN_HINTS.items():
        n = sum(1 for h in hints if h in low)
        if n:
            hits[domain] = n
    return hits


class Specialist:
    """A condensed body of thinking, retrievable by situation."""

    def __init__(self, spec: Dict[str, Any]) -> None:
        self.spec = spec
        self.id: str = spec["id"]
        self.name: str = spec["name"]
        self.lens: str = spec["lens"]
        self.limits: List[str] = spec.get("limits", [])
        self._principles: List[Dict[str, Any]] = spec.get("principles", [])

    @classmethod
    def load(cls, specialist_id: str, root: Optional[pathlib.Path] = None) -> "Specialist":
        base = pathlib.Path(root) if root else SPECIALISTS_ROOT
        path = base / f"{specialist_id}.json"
        if not path.exists():
            available = ", ".join(sorted(p.stem for p in base.glob("*.json"))) or "(none)"
            raise KeyError(f"unknown specialist {specialist_id!r}. Available: {available}")
        return cls(json.loads(path.read_text()))

    def retrieve(self, situation: str, k: int = 4) -> List[RetrievedPrinciple]:
        """Rank principles against a free-text situation.

        Lexical overlap plus domain hints. No embedding model: a lens with ~30
        principles does not need one, and a deterministic ranking is auditable —
        you can see exactly why a principle fired.
        """
        sit_tokens = set(_tokens(situation))
        dom = _domains_for(situation)
        scored: List[RetrievedPrinciple] = []

        for p in self._principles:
            reasons: List[str] = []
            score = 0.0

            p_tokens = set(_tokens(" ".join([
                p.get("gist", ""), p.get("implication", ""), p.get("domain", ""),
            ])))
            overlap = sit_tokens & p_tokens
            if overlap:
                score += len(overlap)
                reasons.append("shared terms: " + ", ".join(sorted(overlap)[:5]))

            d = p.get("domain", "")
            if d in dom:
                score += 2 * dom[d]
                reasons.append(f"domain match: {d}")

            # Exact verbatim phrase appearing in the situation is a strong signal.
            v = (p.get("verbatim") or "").lower()
            if v and len(v) > 20 and v in situation.lower():
                score += 5
                reasons.append("quoted the essay directly")

            if score <= 0:
                continue
            scored.append(RetrievedPrinciple(
                id=p["id"], gist=p["gist"], essay=p["essay"], url=p["url"],
                implication=p["implication"], domain=d,
                verbatim=p.get("verbatim", ""), score=score, reasons=reasons,
            ))

        scored.sort(key=lambda r: (-r.score, r.id))
        return scored[:k]

    def advise(self, situation: str, k: int = 4,
               tenant_context: Optional[Dict[str, Any]] = None) -> Viewpoint:
        """Return a viewpoint on ``situation`` through this lens.

        ``tenant_context`` is optional metadata (business type, stage, margin).
        It tunes the reading sentence and the caveats; it never changes the
        principles, because those are not tenant data.
        """
        principles = self.retrieve(situation, k=k)
        ctx = tenant_context or {}
        caveats = list(self.limits)

        # Targeted caveat: growth-maximising advice is a poor fit for a business
        # whose constraint is margin or cash, and saying so is more useful than a
        # generic disclaimer.
        margin = ctx.get("operating_margin_pct")
        if isinstance(margin, (int, float)) and margin < 5:
            caveats.insert(0,
                f"This lens optimises for growth; the business is running at "
                f"{margin:.1f}% operating margin. Growth advice applied at thin "
                f"margins can convert a small profit into a large loss — check "
                f"what each principle costs before acting on it.")
        if ctx.get("business_type"):
            caveats.append(
                f"The situation is a {ctx['business_type']} business. Graham's "
                f"sample is venture-backed startups; the base rates differ."
            )

        reading = self._reading(situation, principles, ctx)
        return Viewpoint(
            specialist=self.name,
            lens=self.lens,
            situation=situation,
            principles=principles,
            questions=self._questions(principles),
            caveats=caveats,
            reading=reading,
        )

    # -- composition -------------------------------------------------------

    def _reading(self, situation: str, principles: List[RetrievedPrinciple],
                 ctx: Dict[str, Any]) -> str:
        if not principles:
            return (
                "No principle in this lens speaks to the situation as written. "
                "Either the question is outside Graham's subject — he writes "
                "about early-stage growth companies — or it needs restating in "
                "terms of users, growth, or what the founder is spending "
                "attention on."
            )
        top = principles[0]
        return (
            f"Read through this lens, the situation is mainly a question about "
            f"{top.domain}. The principle that speaks to it most directly is "
            f"\"{top.gist}\" ({top.essay})."
        )

    def _questions(self, principles: List[RetrievedPrinciple]) -> List[str]:
        """Questions generated from the principles that fired.

        Questions rather than recommendations, because the lens does not know the
        tenant's constraints. A question transfers the judgement back to the
        person who has the data.
        """
        bank = {
            "growth": "What is the current growth rate, and would this initiative move it?",
            "product": "What problem does this solve for a specific person who has it?",
            "hiring": "Who owns this decision, and do they talk to customers?",
            "pricing": "What does the customer get, and is the price a fraction of that value?",
            "focus": "What would you stop doing to do this properly?",
            "culture": "Would the best person on the team defend this decision?",
            "founder": "Is this a commitment you can sustain, or a hedge you are calling a plan?",
            "strategy": "Is this the industry's consensus, or a genuine difference?",
        }
        seen, out = set(), []
        for p in principles:
            q = bank.get(p.domain)
            if q and q not in seen:
                seen.add(q)
                out.append(q)
        return out


def available_specialists(root: Optional[pathlib.Path] = None) -> List[Dict[str, str]]:
    base = pathlib.Path(root) if root else SPECIALISTS_ROOT
    out = []
    for p in sorted(base.glob("*.json")):
        try:
            spec = json.loads(p.read_text())
        except ValueError:
            continue
        out.append({
            "id": spec.get("id", p.stem),
            "name": spec.get("name", p.stem),
            "lens": spec.get("lens", ""),
            "principles": str(len(spec.get("principles", []))),
        })
    return out


__all__ = [
    "Specialist",
    "Viewpoint",
    "RetrievedPrinciple",
    "available_specialists",
    "SPECIALISTS_ROOT",
]
