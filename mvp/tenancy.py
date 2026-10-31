"""Single enforcement point for tenant scoping.

Every read or write of business data must come through this module. Nothing
here may be cached or keyed by anything other than a tenant id — that invariant
is what prevents one business's figures appearing in another's dashboard.

Why this module exists
----------------------
The web app originally held module-level singletons: one ``_constraints`` store,
one ``_controller``, one ``_jobs`` dict, and a ``load_all()`` helper with no
tenant argument. Each of those was a cross-tenant leak:

  * ``load_all()`` always read ``data/jonco`` — so the SaaS dashboard rendered
    the café's P&L, staff and products.
  * ``_constraints`` was built from ``build_default_constraints()``, whose
    ``applicable_to`` lists are café node ids — so café constraints appeared
    against SaaS nodes.
  * ``_controller`` carried mutable state (state machine + monitor baselines)
    for whichever tenant touched it first.
  * ``_jobs`` keyed insight results by job id only, so a job started by tenant A
    could be polled by tenant B.

This module replaces all four with tenant-keyed storage and a guard that refuses
to hand out data without an explicit tenant.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from mvp.loader import (
    UnknownTenantError,
    load_all,
    load_graph,
    load_tenant_config,
)

__all__ = [
    "TenantAccessError",
    "UnknownTenantError",
    "require_tenant",
    "registry",
    "JobStore",
]


class TenantAccessError(PermissionError):
    """Raised when a request touches a tenant it has no business touching."""


def require_tenant(tenant_id: Optional[str]) -> str:
    """Validate a tenant id, refusing empty/None values.

    Deliberately strict: no default tenant. A default is a silent fallback and
    silent fallbacks are how this bug happened in the first place.
    """
    if not tenant_id or not str(tenant_id).strip():
        raise TenantAccessError("a tenant id is required for every read and write")
    tid = str(tenant_id).strip()
    load_tenant_config(tid)  # raises UnknownTenantError if absent
    return tid


class TenantRegistry:
    """Per-tenant caches for graphs, business objects, constraints and agents.

    A single instance lives for the process lifetime. Every accessor takes a
    tenant id as its first argument and validates it.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._graphs: Dict[str, Any] = {}
        self._business: Dict[str, Any] = {}
        self._constraints: Dict[str, Any] = {}
        self._orchestrators: Dict[str, Any] = {}
        self._controllers: Dict[str, Any] = {}

    def invalidate(self, tenant_id: str) -> None:
        """Drop every cached object for one tenant.

        Called after a re-template so the process stops serving the previous
        type's graph to a tenant that has just changed type.
        """
        tid = str(tenant_id).strip()
        with self._lock:
            for cache in (self._graphs, self._business, self._constraints,
                          self._orchestrators, self._controllers):
                cache.pop(tid, None)

    # --- graph ------------------------------------------------------------
    def graph(self, tenant_id: str):
        tid = require_tenant(tenant_id)
        with self._lock:
            if tid not in self._graphs:
                self._graphs[tid] = load_graph(tid)
            return self._graphs[tid]

    # --- flat business object --------------------------------------------
    def business(self, tenant_id: str):
        tid = require_tenant(tenant_id)
        with self._lock:
            if tid not in self._business:
                self._business[tid] = load_all(tid)
            return self._business[tid]

    # --- constraints ------------------------------------------------------
    def constraints(self, tenant_id: str):
        """Constraints filtered to this tenant's own nodes.

        The default set is authored against café node ids. Applying it to a SaaS
        graph both leaks café structure and produces meaningless constraint
        counts, so anything whose ``applicable_to`` misses this graph is dropped.
        """
        tid = require_tenant(tenant_id)
        with self._lock:
            if tid not in self._constraints:
                from mvp.model.constraints import ConstraintStore, build_default_constraints
                g = self.graph(tid)
                node_ids = set(g.nodes)
                store = ConstraintStore()
                for c in build_default_constraints():
                    targets = set(getattr(c, "applicable_to", []) or [])
                    if targets & node_ids:
                        store.add(c)
                self._constraints[tid] = store
            return self._constraints[tid]

    # --- agents -----------------------------------------------------------
    def orchestrator(self, tenant_id: str):
        import os
        from mvp.multiagent import MultiAgentOrchestrator, OrchestratorConfig
        from mvp.multiagent.control_models import ControlModel

        tid = require_tenant(tenant_id)
        with self._lock:
            if tid not in self._orchestrators:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(project_root, "data", f"initiatives_{tid}.db")
                orch = MultiAgentOrchestrator(OrchestratorConfig(
                    control_model=ControlModel.HIERARCHICAL,
                    budget_effort=20.0,
                    max_initiatives=6,
                    db_path=db_path,
                ))
                orch.constraint_store = self.constraints(tid)
                if not getattr(orch, "checker", None):
                    from mvp.multiagent.constraint_checker import ConstraintCheckerAgent
                    orch.checker = ConstraintCheckerAgent(orch.constraint_store)
                self._orchestrators[tid] = orch
            return self._orchestrators[tid]

    def controller(self, tenant_id: str):
        from mvp.multiagent.autonomous_controller import AutonomousGraphController

        tid = require_tenant(tenant_id)
        with self._lock:
            if tid not in self._controllers:
                orch = self.orchestrator(tid)
                self._controllers[tid] = AutonomousGraphController(specialists=orch.specialists)
            return self._controllers[tid]

    def reset_controller(self, tenant_id: str) -> None:
        tid = require_tenant(tenant_id)
        with self._lock:
            self._controllers.pop(tid, None)

    # --- introspection ----------------------------------------------------
    def cached_tenants(self) -> Dict[str, List[str]]:
        with self._lock:
            return {
                "graphs": sorted(self._graphs),
                "business": sorted(self._business),
                "constraints": sorted(self._constraints),
                "orchestrators": sorted(self._orchestrators),
                "controllers": sorted(self._controllers),
            }


registry = TenantRegistry()


class JobStore:
    """Background job records that are unreadable outside their tenant.

    ``get`` requires the caller's tenant and raises TenantAccessError on a
    mismatch, so guessing a job id does not expose another business's results.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create(self, tenant_id: str, job_id: str, **fields: Any) -> None:
        tid = require_tenant(tenant_id)
        with self._lock:
            self._jobs[job_id] = {**fields, "tenant": tid}

    def update(self, tenant_id: str, job_id: str, **fields: Any) -> None:
        tid = require_tenant(tenant_id)
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                self._jobs[job_id] = {**fields, "tenant": tid}
                return
            if rec.get("tenant") != tid:
                raise TenantAccessError("job belongs to another tenant")
            rec.update(fields)

    def get(self, tenant_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        tid = require_tenant(tenant_id)
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                return None
            if rec.get("tenant") != tid:
                raise TenantAccessError("job belongs to another tenant")
            return dict(rec)


jobs = JobStore()
