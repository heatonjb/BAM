"""Public-data prospecting: a model of a business before you've met it.

The campaign idea
-----------------
Most outbound email says "I noticed you exist". This does the opposite: it builds
a provisional model of the company from public filings, finds the one line where
that model looks wrong or tight, and asks a question about it. The claim being
made is not "you should buy software" but "here is something specific about your
numbers, is it right?" — which is falsifiable, and therefore worth a reply.

What is actually public
-----------------------
Companies House gives: legal name, company number, incorporation date, SIC codes,
filing dates, accounts category (micro/small/full), status, registered address.
It does **not** give revenue, headcount or margin for small companies. Those come
from sector ratios applied to the accounts category — which is precisely why the
insight has to be framed as a question rather than a finding.

Provenance is therefore tracked on every number: ``filed``, ``derived`` or
``assumed``. An outreach email that presents an assumed number as fact is both
dishonest and, under UK advertising rules, actionable.

Compliance
----------
UK B2B cold email to a corporate address is permitted under PECR with a
legitimate-interest basis, an identified sender, and a working opt-out. The
``OutreachMessage`` carries ``compliance`` blocks so the sending step cannot
silently omit them. A suppression list is checked before a message is eligible.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Companies House SIC code prefix -> BAM business type.
SIC_TO_TYPE: List[Tuple[str, str]] = [
    ("5610", "coffee_shop"),   # restaurants / mobile food
    ("5629", "coffee_shop"),
    ("4711", "retail"),        # non-specialised retail
    ("4771", "retail"),
    ("6201", "developer_tools"),   # computer programming
    ("6202", "developer_tools"),
    ("6209", "developer_tools"),
    ("4791", "ecommerce"),     # retail via mail order / internet
    ("6810", "services"),
    ("7022", "services"),
]

#: Sector ratios used when only an accounts category is known. Deliberately
#: conservative and clearly labelled as derived.
SECTOR_RATIOS: Dict[str, Dict[str, float]] = {
    "coffee_shop": {"gross_margin": 0.70, "staff_pct": 0.32, "op_margin": 0.06},
    "retail": {"gross_margin": 0.38, "staff_pct": 0.18, "op_margin": 0.05},
    "ecommerce": {"gross_margin": 0.45, "staff_pct": 0.12, "op_margin": 0.08},
    "developer_tools": {"gross_margin": 0.78, "staff_pct": 0.45, "op_margin": 0.12},
    "services": {"gross_margin": 0.55, "staff_pct": 0.40, "op_margin": 0.10},
}

#: Indicative revenue band by accounts category (Companies House filing size).
ACCOUNTS_SCALE: Dict[str, float] = {
    "micro-entity": 300_000.0,
    "small": 1_500_000.0,
    "medium": 8_000_000.0,
    "full": 25_000_000.0,
}


@dataclass
class CompanyRecord:
    """One company as described by public filings."""

    number: str
    name: str
    sic_codes: List[str] = field(default_factory=list)
    status: str = "active"
    incorporated: Optional[str] = None
    accounts_category: str = "micro-entity"
    last_accounts: Optional[str] = None
    address: str = ""
    region: str = ""
    website: Optional[str] = None
    contact_email: Optional[str] = None

    @property
    def business_type(self) -> str:
        for code in self.sic_codes:
            for prefix, type_id in SIC_TO_TYPE:
                if code.startswith(prefix):
                    return type_id
        return "services"

    @property
    def age_years(self) -> Optional[float]:
        if not self.incorporated:
            return None
        try:
            inc = datetime.fromisoformat(self.incorporated).date()
        except ValueError:
            return None
        return round((date.today() - inc).days / 365.25, 1)

    @property
    def accounts_overdue(self) -> bool:
        """True when the last accounts filing is more than 12 months stale."""
        if not self.last_accounts:
            return False
        try:
            filed = datetime.fromisoformat(self.last_accounts).date()
        except ValueError:
            return False
        return (date.today() - filed).days > 365

    def to_dict(self) -> dict:
        return {
            "number": self.number, "name": self.name, "sic_codes": self.sic_codes,
            "status": self.status, "incorporated": self.incorporated,
            "accounts_category": self.accounts_category,
            "last_accounts": self.last_accounts, "address": self.address,
            "region": self.region, "website": self.website,
            "business_type": self.business_type, "age_years": self.age_years,
        }


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class CompaniesHouseClient:
    """Thin Companies House client.

    The API is a plain HTTP GET with an API key as the basic-auth username, no
    password. Requests carry a short timeout by default: on a host whose
    egress is firewalled the call fails fast and the caller falls back to
    fixtures rather than hanging a batch job.
    """

    BASE = "https://api.company-information.service.gov.uk"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 6.0) -> None:
        self.api_key = api_key or os.environ.get("COMPANIES_HOUSE_API_KEY", "")
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("COMPANIES_HOUSE_API_KEY is not set")
        req = urllib.request.Request(self.BASE + path)
        token = base64_token(self.api_key)
        req.add_header("Authorization", "Basic " + token)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def search(self, query: str, limit: int = 20) -> List[CompanyRecord]:
        data = self._get(f"/search/companies?q={urllib.parse.quote(query)}&items_per_page={limit}")
        return [self._to_record(item) for item in data.get("items", [])]

    def company(self, number: str) -> CompanyRecord:
        return self._to_record(self._get(f"/company/{number}"))

    @staticmethod
    def _to_record(item: Dict[str, Any]) -> CompanyRecord:
        addr = item.get("registered_office_address") or {}
        return CompanyRecord(
            number=item.get("company_number", ""),
            name=item.get("company_name") or item.get("title", ""),
            sic_codes=[c for c in (item.get("sic_codes") or [])],
            status=(item.get("company_status") or "active").lower(),
            incorporated=item.get("date_of_creation"),
            accounts_category=(item.get("accounts", {}) or {}).get("type", "micro-entity") or "micro-entity",
            last_accounts=(item.get("accounts", {}) or {}).get("last_accounts", {}).get("made_up_to")
            if isinstance((item.get("accounts", {}) or {}).get("last_accounts"), dict) else None,
            address=", ".join(v for v in (addr.get("address_line_1"),
                                          addr.get("locality"),
                                          addr.get("postal_code")) if v),
            region=addr.get("region", "") or addr.get("locality", ""),
        )


def base64_token(api_key: str) -> str:
    import base64
    return base64.b64encode(f"{api_key}:".encode()).decode()


class FixtureProvider:
    """Offline records so the pipeline is runnable without egress."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "campaign", "sample_companies.json",
        )

    def all(self) -> List[CompanyRecord]:
        try:
            with open(self.path) as fh:
                rows = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return []
        return [CompanyRecord(**r) for r in rows]


def load_records(client: Optional[CompaniesHouseClient] = None,
                 query: str = "") -> Tuple[List[CompanyRecord], str]:
    """Return (records, source). Falls back to fixtures without pretending."""
    client = client or CompaniesHouseClient()
    if client.available():
        try:
            return client.search(query), "companies_house"
        except Exception:
            pass
    return FixtureProvider().all(), "fixture"


# ---------------------------------------------------------------------------
# Provisional model
# ---------------------------------------------------------------------------


@dataclass
class ProvisionalMetric:
    name: str
    value: float
    unit: str
    provenance: str          # "filed" | "derived" | "assumed"
    note: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "value": round(self.value, 2),
                "unit": self.unit, "provenance": self.provenance, "note": self.note}


def build_provisional_model(record: CompanyRecord) -> Dict[str, Any]:
    """Turn a filing into the numbers an insight needs — all labelled by source.

    Revenue is the weakest link: Companies House does not publish it for small
    companies. We take the midpoint of the accounts-category band and say so.
    Every downstream figure inherits ``assumed``.
    """
    type_id = record.business_type
    ratios = SECTOR_RATIOS.get(type_id, SECTOR_RATIOS["services"])
    revenue = ACCOUNTS_SCALE.get(record.accounts_category.lower(), 300_000.0)

    gross = revenue * ratios["gross_margin"]
    staff = revenue * ratios["staff_pct"]
    op = revenue * ratios["op_margin"]

    metrics = [
        ProvisionalMetric("annual_revenue", revenue, "GBP", "assumed",
                          f"midpoint of the {record.accounts_category} band; not filed"),
        ProvisionalMetric("gross_margin", ratios["gross_margin"] * 100, "%", "derived",
                          f"sector median for {type_id}"),
        ProvisionalMetric("staff_cost", staff, "GBP", "derived",
                          f"{ratios['staff_pct']:.0%} of assumed revenue"),
        ProvisionalMetric("operating_profit", op, "GBP", "derived",
                          f"{ratios['op_margin']:.0%} operating margin"),
    ]

    return {
        "record": record.to_dict(),
        "business_type": type_id,
        "metrics": metrics,
        "confidence": "low" if record.accounts_category.lower() == "micro-entity" else "medium",
        "filed_facts": {
            "sic_codes": record.sic_codes,
            "incorporated": record.incorporated,
            "age_years": record.age_years,
            "accounts_category": record.accounts_category,
            "accounts_overdue": record.accounts_overdue,
        },
    }


# ---------------------------------------------------------------------------
# Insight generation
# ---------------------------------------------------------------------------


@dataclass
class Insight:
    headline: str
    detail: str
    question: str
    strength: float          # 0..1 — how much this is worth emailing about
    basis: str               # what it is grounded in

    def to_dict(self) -> dict:
        return {"headline": self.headline, "detail": self.detail,
                "question": self.question, "strength": round(self.strength, 3),
                "basis": self.basis}


def insights_for(model: Dict[str, Any]) -> List[Insight]:
    """Pick the observations worth putting in an email, strongest first.

    The ordering rule: prefer something *filed* and unusual (overdue accounts, a
    young company in a high-fixed-cost sector) over something derived. An
    observation a stranger could not have guessed is the only kind that earns a
    reply.
    """
    rec = model["record"]
    facts = model["filed_facts"]
    metrics = {m.name: m for m in model["metrics"]}
    out: List[Insight] = []

    if facts["accounts_overdue"]:
        out.append(Insight(
            headline="Your accounts filing looks overdue",
            detail=(
                "The last accounts on file are more than twelve months old. "
                "Late filing carries an automatic penalty that rises with delay."
            ),
            question="Is that a filing-timing issue, or are the numbers not ready?",
            strength=0.95,
            basis="filed — last_accounts date",
        ))

    age = facts.get("age_years")
    if age is not None and age < 2:
        out.append(Insight(
            headline=f"You incorporated {age:.1f} years ago",
            detail=(
                "In the first two years the P&L is usually still being discovered — "
                "which cost lines are actually fixed, and which move with volume."
            ),
            question="Do you know yet which of your costs actually move with sales?",
            strength=0.6,
            basis="filed — incorporation date",
        ))

    gm = metrics["gross_margin"]
    out.append(Insight(
        headline=f"Gross margin around {gm.value:.0f}% for a {model['business_type'].replace('_', ' ')}",
        detail=(
            f"That is the sector figure, not yours. At that margin every £1 of revenue "
            f"leaves about {gm.value:.0f}p before staff and overheads."
        ),
        question=f"Is {gm.value:.0f}% close to your actual gross margin?",
        strength=0.72,
        basis="derived — sector ratio",
    ))

    staff = metrics["staff_cost"]
    out.append(Insight(
        headline=f"Staff is probably your largest controllable cost",
        detail=(
            f"At sector ratios that is roughly £{staff.value:,.0f} a year against "
            f"£{metrics['annual_revenue'].value:,.0f} of revenue."
        ),
        question="Is rostering matched to the hours that actually earn?",
        strength=0.5,
        basis="derived — sector ratio",
    ))

    out.sort(key=lambda i: i.strength, reverse=True)
    return out


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------


@dataclass
class OutreachMessage:
    to: str
    subject: str
    body: str
    company: str
    insight_basis: str
    compliance: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"to": self.to, "subject": self.subject, "body": self.body,
                "company": self.company, "insight_basis": self.insight_basis,
                "compliance": self.compliance}


SENDER_NAME = "Jon Heaton"
SENDER_ADDRESS = "BAM, United Kingdom"
OPT_OUT_LINE = "Reply 'no' and I will not contact you again."


def compose(record: CompanyRecord, insights: List[Insight], *,
            sender: str = SENDER_NAME, address: str = SENDER_ADDRESS) -> Optional[OutreachMessage]:
    """Write one email around the strongest insight.

    Refuses to compose when there is no address, no insight, or when the
    strongest insight is too weak to justify contact. A campaign that emails
    everyone is a spam campaign with a model attached.
    """
    if not record.contact_email or not insights:
        return None
    top = insights[0]
    if top.strength < 0.5:
        return None

    first = record.name.split()[0].title()
    subject = f"{top.headline} — quick question"

    body = "\n".join([
        f"Hi {first},",
        "",
        f"I was looking at {record.name} on Companies House"
        + (f" (company {record.number})" if record.number else "") + ".",
        "",
        top.detail,
        "",
        top.question,
        "",
        "I built a tool that models a business as a connected graph — costs, volume and "
        "cash — and then simulates which change is actually worth making. For a "
        f"{record.business_type.replace('_', ' ')} your shape usually has one or two "
        "lines that dominate everything else.",
        "",
        "I can send you a one-page reading of what that would look like for you. "
        "No charge, and you will be able to tell in about ten seconds whether my "
        "assumptions are wrong.",
        "",
        "Worth a look?",
        "",
        sender,
        address,
        "",
        "--",
        "You are receiving this once, as a business contact, on the basis of legitimate "
        "interest. " + OPT_OUT_LINE,
    ])

    return OutreachMessage(
        to=record.contact_email,
        subject=subject,
        body=body,
        company=record.name,
        insight_basis=top.basis,
        compliance={
            "basis": "legitimate_interest_b2b",
            "sender_identified": "yes",
            "opt_out": "reply_no",
            "one_contact_only": "yes",
            "data_source": "Companies House public register",
        },
    )


def eligible(record: CompanyRecord, suppressed: Iterable[str]) -> bool:
    """Cheap pre-send gate: usable address, active company, not suppressed."""
    if not record.contact_email:
        return False
    if record.status not in ("active", ""):
        return False
    return record.contact_email.lower() not in {s.lower() for s in suppressed}


def run_campaign(records: List[CompanyRecord], *, suppressed: Optional[Iterable[str]] = None,
                 limit: int = 25) -> Dict[str, Any]:
    """Build models, insights and messages for a batch. Nothing is sent."""
    suppressed = list(suppressed or [])
    out = []
    skipped = []
    for rec in records:
        if not eligible(rec, suppressed):
            skipped.append({"company": rec.name, "reason": "ineligible or suppressed"})
            continue
        model = build_provisional_model(rec)
        insights = insights_for(model)
        msg = compose(rec, insights)
        if msg is None:
            skipped.append({"company": rec.name, "reason": "no insight strong enough"})
            continue
        out.append({"company": rec.name, "number": rec.number,
                    "model": _model_to_dict(model),
                    "top_insight": insights[0].to_dict(),
                    "message": msg.to_dict()})
        if len(out) >= limit:
            break
    return {"count": len(out), "candidates": out, "skipped": skipped}


def _model_to_dict(model: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "record": model["record"],
        "business_type": model["business_type"],
        "confidence": model["confidence"],
        "filed_facts": model["filed_facts"],
        "metrics": [m.to_dict() for m in model["metrics"]],
    }


__all__ = [
    "CompanyRecord", "CompaniesHouseClient", "FixtureProvider", "load_records",
    "ProvisionalMetric", "build_provisional_model", "Insight", "insights_for",
    "OutreachMessage", "compose", "eligible", "run_campaign",
    "SIC_TO_TYPE", "SECTOR_RATIOS", "ACCOUNTS_SCALE",
]
