"""NangoConnector — BaseConnector adapter so the orchestrator can route
initiatives through Nango, and read data back through Nango's proxy.

This is the bridge between BAM's existing connector contract and the Nango
client. It supports:

  Write path (initiative execution):
    - create_connect_session : generate a hosted auth link for a provider
    - disconnect              : revoke a tenant's provider connection
    - proxy_call              : arbitrary authenticated provider API call

  Read path:
    - pull_metric             : fetch one canonical field for a tenant

Connections are keyed by (tenant, provider). A tenant's connection IDs live in
the integration store (see store.py) or in NANGO_CONN_<TENANT>_<PROVIDER> env
vars for simple deployments.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..multiagent.external import BaseConnector
from .nango import NangoClient, NangoError, available
from .providers import get_spec, all_specs, coverage_report


class NangoConnector(BaseConnector):
    """Route integration actions through Nango."""

    name = "nango"
    description = (
        "Managed OAuth + proxy for external SaaS tools. Handles token refresh, "
        "rate limits, and credential storage for 1,000+ providers."
    )

    def __init__(self, client: Optional[NangoClient] = None):
        self.client = client or NangoClient()

    # ── health ─────────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        if not available():
            return {
                "ok": False,
                "detail": "NANGO_SECRET_KEY not set — add it to .env to enable integrations",
            }
        return self.client.health()

    def capabilities(self) -> List[str]:
        return [
            "create_connect_session",
            "list_connections",
            "disconnect",
            "proxy_call",
            "pull_metric",
            "coverage_report",
        ]

    # ── connection resolution ──────────────────────────────────────────────

    @staticmethod
    def _conn_id(tenant: str, provider: str) -> Optional[str]:
        """Look up a connection ID for a tenant/provider.

        Precedence: explicit env var, then the integration store. Returns None
        if the tenant hasn't connected that provider yet.
        """
        env_key = f"NANGO_CONN_{tenant.upper()}_{provider.upper()}".replace("-", "_")
        if os.environ.get(env_key):
            return os.environ[env_key]
        try:
            from .store import get_connection_id  # local import to avoid cycles
            return get_connection_id(tenant, provider)
        except Exception:
            return None

    # ── execute ────────────────────────────────────────────────────────────

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            return {"ok": False, "error": f"nango does not support action '{action}'"}
        try:
            return handler(params)
        except NangoError as e:
            return {"ok": False, "error": str(e), "status": e.status}
        except Exception as e:  # never let a connector crash the orchestrator
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def _action_create_connect_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        integration_id = params.get("provider") or params.get("integration_id")
        end_user_id = params.get("tenant") or params.get("end_user_id")
        if not integration_id or not end_user_id:
            return {"ok": False, "error": "provider and tenant are required"}

        spec = get_spec(integration_id)
        if spec is None:
            return {
                "ok": False,
                "error": f"unknown provider '{integration_id}'. Known: "
                         + ", ".join(s.id for s in all_specs()),
            }

        session = self.client.create_connect_session(
            integration_id=integration_id,
            end_user_id=end_user_id,
            end_user_email=params.get("email"),
            organization_id=params.get("organization_id"),
            metadata=params.get("metadata"),
        )
        link = session.get("connect_link") or session.get("data", {}).get("connect_link")
        return {
            "ok": True,
            "detail": f"Auth link generated for {spec.label}",
            "connect_link": link,
            "expires_in": "30 minutes",
            "external_ref": f"nango:session:{session.get('token', 'unknown')}",
        }

    def _action_list_connections(self, params: Dict[str, Any]) -> Dict[str, Any]:
        conns = self.client.list_connections(
            integration_id=params.get("provider"),
            end_user_id=params.get("tenant"),
        )
        return {"ok": True, "detail": f"{len(conns)} connections", "connections": conns}

    def _action_disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tenant = params.get("tenant")
        provider = params.get("provider")
        if not tenant or not provider:
            return {"ok": False, "error": "tenant and provider are required"}
        conn_id = params.get("connection_id") or self._conn_id(tenant, provider)
        if not conn_id:
            return {"ok": False, "error": f"no stored connection for {tenant}/{provider}"}
        self.client.delete_connection(conn_id, provider)
        return {"ok": True, "detail": f"Disconnected {provider} for {tenant}"}

    def _action_proxy_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tenant = params.get("tenant")
        provider = params.get("provider")
        endpoint = params.get("endpoint")
        if not (tenant and provider and endpoint):
            return {"ok": False, "error": "tenant, provider and endpoint are required"}
        conn_id = params.get("connection_id") or self._conn_id(tenant, provider)
        if not conn_id:
            return {
                "ok": False,
                "error": f"no stored connection for {tenant}/{provider} — "
                         "call create_connect_session first",
            }
        result = self.client.proxy(
            integration_id=provider,
            connection_id=conn_id,
            endpoint=endpoint,
            method=params.get("method", "GET"),
            body=params.get("body"),
            query=params.get("query"),
        )
        return {"ok": True, "data": result, "external_ref": f"nango:proxy:{provider}{endpoint}"}

    def _action_pull_metric(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch one canonical field for a tenant via the provider's endpoint."""
        tenant = params.get("tenant")
        provider = params.get("provider")
        field = params.get("field")
        if not (tenant and provider and field):
            return {"ok": False, "error": "tenant, provider and field are required"}

        spec = get_spec(provider)
        if spec is None:
            return {"ok": False, "error": f"unknown provider '{provider}'"}
        if field not in spec.endpoints:
            return {
                "ok": False,
                "error": f"{provider} has no endpoint mapped for '{field}'",
                "available": list(spec.endpoints),
            }

        method, path, extractor = spec.endpoints[field]
        conn_id = params.get("connection_id") or self._conn_id(tenant, provider)
        if not conn_id:
            return {"ok": False, "error": f"no stored connection for {tenant}/{provider}"}

        raw = self.client.proxy(
            integration_id=provider,
            connection_id=conn_id,
            endpoint=path,
            method=method,
            query=params.get("query"),
        )
        value = extractor(raw) if callable(extractor) else None
        return {
            "ok": True,
            "field": field,
            "value": value,
            "provider": provider,
            "external_ref": f"nango:pull:{provider}:{field}",
        }

    def _action_coverage_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "coverage": coverage_report()}


def build_nango_connector() -> NangoConnector:
    return NangoConnector()
