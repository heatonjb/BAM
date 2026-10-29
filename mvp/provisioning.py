"""Tenant provisioning for self-serve sign-up.

A new sign-up needs four things to exist before the app can render a dashboard
for them: a tenant id, a data directory the loader can read, an entry in
``data/tenants.json``, and a user with a membership. This module creates all
four and rolls back if any step fails.

The starter data is cloned from an existing tenant of the same business type.
That is honest rather than clever: the numbers are labelled as a starter model
in the UI, and connecting a real integration replaces them. What the clone buys
is a structurally correct graph — the seven-layer scaffold and the metric tree —
so the arbiter has something real to reason about on day one.

Business types map onto loaders:
  * ``cafe``  → café loader (reads the JSON export in the tenant directory)
  * ``saas``  → SaaS loader (reads ``company.json``)
  * ``services`` / ``ecommerce`` → SaaS loader with a ``company.json`` shaped
    for recurring-revenue businesses. The type is stored as ``saas`` because
    that is the loader contract; the display name is kept separately.

This is the seam where hierarchical business-type templates will land. For now
the parent type is the loader, and the child type is the display label.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from mvp import plans

DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
TENANTS_PATH = os.path.join(DATA_ROOT, "tenants.json")

_write_lock = threading.Lock()

# Display label → (loader type, template tenant to clone)
TYPE_MAP: Dict[str, Dict[str, str]] = {
    "cafe": {
        "loader_type": "cafe",
        "template": "jonco",
        "label": "Café / physical retail",
        "icon": "☕",
        "color": "#8d6e63",
        "period": "Starter model (monthly averages)",
    },
    "saas": {
        "loader_type": "saas",
        "template": "joncrm",
        "label": "SaaS / recurring software",
        "icon": "🧩",
        "color": "#5c6bc0",
        "period": "Starter model (monthly averages)",
    },
    "services": {
        "loader_type": "saas",
        "template": "joncrm",
        "label": "Professional services",
        "icon": "🛠",
        "color": "#4db6ac",
        "period": "Starter model (monthly averages)",
    },
    "ecommerce": {
        "loader_type": "saas",
        "template": "joncrm",
        "label": "E-commerce",
        "icon": "🛒",
        "color": "#ff8a65",
        "period": "Starter model (monthly averages)",
    },
}


class ProvisioningError(Exception):
    """Raised when a tenant cannot be created; callers surface the message."""


def slugify(name: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    s = s[:max_len].strip("-")
    return s or "business"


def _read_tenants() -> Dict[str, Any]:
    with open(TENANTS_PATH) as f:
        return json.load(f)


def _write_tenants(tenants: Dict[str, Any]) -> None:
    tmp = TENANTS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tenants, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, TENANTS_PATH)


def _unique_id(base: str, tenants: Dict[str, Any]) -> str:
    candidate = base
    n = 2
    while candidate in tenants or os.path.isdir(os.path.join(DATA_ROOT, candidate)):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _clone_template(template: str, dest: str, display_name: str) -> None:
    """Copy a starter tenant's data directory and relabel the company."""
    src = os.path.join(DATA_ROOT, template)
    if not os.path.isdir(src):
        raise ProvisioningError(f"starter template {template!r} is missing")
    shutil.copytree(src, dest)

    # Relabel whichever company file the loader reads.
    for fname in ("company_profile.json", "company.json"):
        path = os.path.join(dest, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if fname == "company.json" and isinstance(data.get("company"), dict):
            data["company"]["name"] = display_name
            data["company"]["number"] = "STARTER"
        elif "name" in data:
            data["name"] = display_name
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


def provision_tenant(
    business_name: str,
    business_type: str,
    owner_user_id: Optional[int] = None,
    plan: str = "free",
) -> Dict[str, Any]:
    """Create a tenant from the starter template for its type.

    Returns the tenants.json entry that was written. Raises ``ProvisioningError``
    on failure and leaves no partial directory behind.
    """
    business_name = (business_name or "").strip()
    if not business_name:
        raise ProvisioningError("a business name is required")
    if len(business_name) > 120:
        raise ProvisioningError("business name is too long")

    spec = TYPE_MAP.get((business_type or "").strip().lower())
    if spec is None:
        raise ProvisioningError(
            "choose a supported business type: " + ", ".join(sorted(TYPE_MAP))
        )

    with _write_lock:
        tenants = _read_tenants()
        tenant_id = _unique_id(slugify(business_name), tenants)
        dest = os.path.join(DATA_ROOT, tenant_id)
        if os.path.exists(dest):
            raise ProvisioningError("that business name is already taken")

        _clone_template(spec["template"], dest, business_name)

        entry = {
            "id": tenant_id,
            "name": business_name,
            "number": "STARTER",
            "type": spec["loader_type"],
            "data_dir": tenant_id,
            "period": spec["period"],
            "icon": spec["icon"],
            "color": spec["color"],
            "display_type": spec["label"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "plan": plan,
        }
        tenants[tenant_id] = entry
        _write_tenants(tenants)

    try:
        plans.set_plan(tenant_id, plan)
        if owner_user_id is not None:
            from mvp.auth.store import add_membership
            add_membership(owner_user_id, tenant_id, "owner")
    except Exception:
        # Registry and directory are already written; a failed plan row or
        # membership should not strand the tenant. Surface it and let the
        # caller decide rather than pretending the provisioning was atomic.
        raise

    return entry


def tenant_count() -> int:
    return len(_read_tenants())


def discard_tenant(tenant_id: str) -> None:
    """Undo ``provision_tenant`` for a tenant that never got an owner.

    Registration can fail after the tenant exists (a duplicate email, for
    example). Leaving the directory and registry entry behind would burn the
    name and leave a graph nobody can open, so the failed sign-up is unwound.
    Only tenants with no memberships should ever be discarded.
    """
    with _write_lock:
        tenants = _read_tenants()
        entry = tenants.pop(tenant_id, None)
        if entry is None:
            return
        _write_tenants(tenants)
        dest = os.path.join(DATA_ROOT, entry.get("data_dir", tenant_id))
        if os.path.isdir(dest) and os.path.abspath(dest).startswith(os.path.abspath(DATA_ROOT) + os.sep):
            shutil.rmtree(dest, ignore_errors=True)
