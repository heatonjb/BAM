"""Nango integration layer for BAM.

Nango handles the OAuth dance, token storage, refresh, and rate limiting for
1,000+ external APIs. BAM only needs to hold a Nango secret key and a connection
ID per tenant/provider.

Two primitives are used here:
  1. Proxy  — make a raw API call through Nango's proxy
              https://api.nango.dev/proxy/<endpoint>
  2. Connections — list/inspect connections, create connect sessions

Docs: https://docs.nango.dev
API base: https://api.nango.dev

Environment:
    NANGO_SECRET_KEY      Nango secret key (Project Settings -> Environment)
    NANGO_BASE_URL        Optional override (default https://api.nango.dev)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_BASE_URL = "https://api.nango.dev"


def _as_list(payload: Any, *keys: str) -> List[Dict[str, Any]]:
    """Rows from a Nango list response.

    Nango wraps list payloads in ``{"data": [...]}``; a few endpoints (and older
    deployments) use their own key (``configs``, ``connections``). Accept every
    shape so callers get rows, never a wrapper.
    """
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys + ("data",):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _payload(payload: Any) -> Dict[str, Any]:
    """Object from a Nango response that wraps it in ``{"data": {...}}``."""
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("data")
    return inner if isinstance(inner, dict) else payload


class NangoError(Exception):
    """Raised when Nango returns a non-2xx response."""

    def __init__(self, message: str, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class NangoClient:
    """Minimal REST client for the Nango API.

    Deliberately dependency-free (urllib only) so it drops into the existing
    BAM codebase without adding httpx/requests to the runtime.
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self.secret_key = secret_key or os.environ.get("NANGO_SECRET_KEY")
        self.base_url = (base_url or os.environ.get("NANGO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    # ── internals ──────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        if not self.secret_key:
            raise NangoError("NANGO_SECRET_KEY not set")

        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)

        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if extra_headers:
            headers.update(extra_headers)

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "ignore")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "ignore")
            raise NangoError(f"Nango HTTP {e.code}: {raw[:400]}", status=e.code, body=raw) from e
        except urllib.error.URLError as e:
            raise NangoError(f"Nango unreachable: {e.reason}") from e

    # ── health / discovery ─────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Cheap connectivity check against the integrations list."""
        if not self.secret_key:
            return {"ok": False, "detail": "NANGO_SECRET_KEY not set"}
        try:
            integrations = self.list_integrations()
            return {
                "ok": True,
                "detail": f"Nango reachable ({len(integrations)} integrations configured)",
            }
        except NangoError as e:
            return {"ok": False, "detail": str(e)}

    # ── health / discovery ─────────────────────────────────────────────────

    def list_integrations(self) -> List[Dict[str, Any]]:
        """All integration configs in the Nango environment."""
        return _as_list(self._request("GET", "/integrations"), "configs")

    def list_connections(
        self, integration_id: Optional[str] = None, end_user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Connections, optionally filtered by integration or end user."""
        query: Dict[str, Any] = {}
        if integration_id:
            query["providerConfigKey"] = integration_id
        if end_user_id:
            query["endUserId"] = end_user_id
        return _as_list(self._request("GET", "/connections", query=query or None),
                        "connections")

    def get_connection(self, connection_id: str, integration_id: str) -> Dict[str, Any]:
        return self._request(
            "GET", f"/connections/{urllib.parse.quote(connection_id)}",
            query={"providerConfigKey": integration_id},
        )

    def delete_connection(self, connection_id: str, integration_id: str) -> Dict[str, Any]:
        return self._request(
            "DELETE", f"/connections/{urllib.parse.quote(connection_id)}",
            query={"providerConfigKey": integration_id},
        )

    # ── connect sessions (auth flow) ───────────────────────────────────────

    def create_connect_session(
        self,
        integration_id: str,
        end_user_id: str,
        end_user_email: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a hosted auth session. Returns ``connect_link`` (valid 30 min).

        Nango scopes a session to an ``end_user`` object (the tenant, for BAM) and
        an optional ``organization`` object. Anything else — legacy ``tags``,
        ``metadata`` — is rejected or silently dropped by the API, so a tenant
        bound any other way ends up with unattributable connections.
        """
        end_user: Dict[str, Any] = {"id": end_user_id}
        if end_user_email:
            end_user["email"] = end_user_email
        body: Dict[str, Any] = {
            "end_user": end_user,
            "allowed_integrations": [integration_id],
        }
        if organization_id:
            body["organization"] = {"id": organization_id}
        return _payload(self._request("POST", "/connect/sessions", body=body))

    # ── proxy ──────────────────────────────────────────────────────────────

    def proxy(
        self,
        integration_id: str,
        connection_id: str,
        endpoint: str,
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        base_url_override: Optional[str] = None,
    ) -> Any:
        """Make an API call through Nango's proxy.

        Nango injects and refreshes the provider credentials; BAM never sees the
        access token. Path is the provider API path, e.g. '/api/v1/invoices'.
        """
        path = "/proxy/" + endpoint.lstrip("/")
        extra = {
            "Provider-Config-Key": integration_id,
            "Connection-Id": connection_id,
        }
        if base_url_override:
            extra["Base-Url-Override"] = base_url_override
        return self._request(method, path, body=body, query=query, extra_headers=extra)


def client_from_env() -> NangoClient:
    return NangoClient()


def available() -> bool:
    """True when Nango is configured, for graceful degradation in the UI."""
    return bool(os.environ.get("NANGO_SECRET_KEY"))
