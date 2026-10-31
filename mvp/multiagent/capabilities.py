"""Tenant-scoped mechanism resolution — generic capability, tenant configuration.

The architectural rule
----------------------
BAM's core codes **generic capabilities**. Tenant agents supply the rest.

That distinction is easy to state and easy to violate. A ``LoyaltyCardMechanism``
is a generic *family* — "give N, get 1 free" is the same arithmetic whether the
merchant sells coffee, haircuts or SaaS credits. But *whether JonCo runs a 9+1
stamp card, at what adoption rate, and with which liability treatment* is a fact
about JonCo, not about BAM. Hardcoding that into core would mean every tenant's
commercial choices live in BAM's source tree, and adding a tenant would require
a deploy.

So:

* **Core** owns the families: the mechanism protocol, the arithmetic, the
  projection engine, break-even inversion, the evidence ledger. Core knows how
  to price a give-away; it does not know that anyone is running one.
* **Tenant** owns the declarations: which family, which parameters, what it is
  called in that business's own language. A tenant agent can add or retune a
  mechanism without core changing.

Resolution order is deliberate — tenant declarations shadow core families of the
same name, so a tenant may override a default without forking core.

Cross-tenant isolation
----------------------
Mechanisms are tenant data. Tenant A must not be able to instantiate tenant B's
mechanism, because the parameters disclose commercial terms (give-away rate,
adoption, discount depth). ``get_tenant_mechanism`` therefore resolves strictly
within one tenant's declarations and raises on a cross-tenant lookup rather than
falling back to a global registry. A permissive fallback here would be the same
class of bug as serving one tenant's books under another tenant's name.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .mechanisms import MECHANISM_REGISTRY, Mechanism

#: Root of per-tenant data. Overridable for tests.
DATA_ROOT = pathlib.Path(__file__).resolve().parents[2] / "data"


class UnknownCapabilityError(KeyError):
    """Raised when a mechanism is not declared for the requested tenant."""


class CrossTenantCapabilityError(PermissionError):
    """Raised when one tenant's declaration is requested through another."""


@dataclass
class MechanismSpec:
    """A tenant's declaration of a mechanism instance.

    ``family`` names a generic implementation in core; ``params`` are this
    tenant's commercial choices. ``label`` is how the business refers to it.
    """

    name: str
    family: str
    params: Dict[str, Any] = field(default_factory=dict)
    label: str = ""
    lever_type: str = "other"
    tenant_id: str = ""

    def instantiate(self) -> Mechanism:
        try:
            cls = MECHANISM_REGISTRY[self.family]
        except KeyError:
            available = ", ".join(sorted(MECHANISM_REGISTRY)) or "(none)"
            raise UnknownCapabilityError(
                f"tenant {self.tenant_id!r} declares family {self.family!r}, "
                f"which core does not provide. Available families: {available}"
            ) from None
        mech = cls(**self.params)
        # Carry the tenant's own name through so ledger entries and envelopes
        # reference the business's vocabulary, not the generic family name.
        mech.name = self.name
        mech.label = self.label or self.name
        if self.lever_type and self.lever_type != "other":
            mech.lever_type = self.lever_type
        return mech

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "params": dict(self.params),
            "label": self.label,
            "lever_type": self.lever_type,
        }


def _capabilities_path(tenant_id: str, data_root: Optional[pathlib.Path] = None):
    root = pathlib.Path(data_root) if data_root else DATA_ROOT
    return root / tenant_id / "capabilities.json"


def load_tenant_mechanisms(
    tenant_id: str, data_root: Optional[pathlib.Path] = None
) -> Dict[str, MechanismSpec]:
    """Read a tenant's mechanism declarations.

    A tenant with no ``capabilities.json`` gets an empty mapping rather than an
    error: a brand-new signup has not chosen any mechanisms yet, and that is a
    valid state, not a misconfiguration.
    """
    path = _capabilities_path(tenant_id, data_root)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    specs: Dict[str, MechanismSpec] = {}
    for entry in raw.get("mechanisms", []):
        spec = MechanismSpec(
            name=entry["name"],
            family=entry["family"],
            params=dict(entry.get("params", {})),
            label=entry.get("label", ""),
            lever_type=entry.get("lever_type", "other"),
            tenant_id=tenant_id,
        )
        specs[spec.name] = spec
    return specs


def save_tenant_mechanisms(
    tenant_id: str,
    specs: List[MechanismSpec],
    data_root: Optional[pathlib.Path] = None,
) -> pathlib.Path:
    """Persist declarations so a tenant agent can register a mechanism."""
    path = _capabilities_path(tenant_id, data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tenant_id": tenant_id,
        "mechanisms": [s.to_dict() for s in specs],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def get_tenant_mechanism(
    tenant_id: str,
    name: str,
    *,
    data_root: Optional[pathlib.Path] = None,
    overrides: Optional[Dict[str, Any]] = None,
    allow_core_family: bool = True,
) -> Mechanism:
    """Instantiate ``name`` as declared by ``tenant_id``.

    Tenant declarations take precedence. With ``allow_core_family`` a bare core
    family name still resolves — useful for exploring a capability before a
    tenant adopts it — but parameters are never borrowed across tenants.
    """
    specs = load_tenant_mechanisms(tenant_id, data_root)

    if name in specs:
        spec = specs[name]
        if overrides:
            spec = MechanismSpec(
                name=spec.name,
                family=spec.family,
                params={**spec.params, **overrides},
                label=spec.label,
                lever_type=spec.lever_type,
                tenant_id=tenant_id,
            )
        return spec.instantiate()

    # Explicit cross-tenant guard: if another tenant declares this name, say so
    # instead of silently resolving to a core family and leaking the terms.
    other = _find_other_tenant_declaration(name, tenant_id, data_root)
    if other is not None:
        raise CrossTenantCapabilityError(
            f"mechanism {name!r} belongs to tenant {other!r}; "
            f"tenant {tenant_id!r} may not instantiate it"
        )

    if allow_core_family and name in MECHANISM_REGISTRY:
        cls = MECHANISM_REGISTRY[name]
        return cls(**(overrides or {}))

    available = ", ".join(sorted(specs)) or "(none declared)"
    raise UnknownCapabilityError(
        f"tenant {tenant_id!r} has no mechanism {name!r}. "
        f"Declared: {available}"
    )


def _find_other_tenant_declaration(
    name: str, tenant_id: str, data_root: Optional[pathlib.Path]
) -> Optional[str]:
    root = pathlib.Path(data_root) if data_root else DATA_ROOT
    if not root.exists():
        return None
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name == tenant_id:
            continue
        path = child / "capabilities.json"
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        for entry in raw.get("mechanisms", []):
            if entry.get("name") == name:
                return child.name
    return None


def list_core_families() -> List[Dict[str, str]]:
    """The generic mechanism families core provides, for tenant discovery."""
    out = []
    for name, cls in sorted(MECHANISM_REGISTRY.items()):
        doc = (cls.__doc__ or "").strip().splitlines()
        out.append(
            {
                "family": name,
                "lever_type": getattr(cls, "lever_type", "other"),
                "summary": doc[0] if doc else "",
            }
        )
    return out


__all__ = [
    "MechanismSpec",
    "UnknownCapabilityError",
    "CrossTenantCapabilityError",
    "load_tenant_mechanisms",
    "save_tenant_mechanisms",
    "get_tenant_mechanism",
    "list_core_families",
    "DATA_ROOT",
]
