"""External tool and SaaS connectors for BAM.

Allows the business graph to *do things* in the outside world, not just model
them. Each connector wraps a tool or platform behind a uniform interface so the
orchestrator can route an initiative's execution without knowing the details.

Connector contract:
    health()                  -> {ok, detail}
    capabilities()            -> list of action names
    execute(action, params)   -> {ok, external_ref, detail, error?}

Included in this MVP:
  - ClaudeCodeConnector   — runs Claude Code headlessly to change code / build products
  - XeroConnector         — accounting platform (OAuth skeleton; read-only sync)
  - LovableConnector      — app builder stub (API not public; documents the shape)
  - CRMConnector          — generic CRM webhook adapter
  - WebhookConnector      — generic HTTP POST for Zapier/Make/n8n
  - ConnectorRegistry     — discovery and dispatch

All network connectors degrade gracefully: if credentials are absent, health()
returns ok=False and execute() returns a clear error rather than raising.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class BaseConnector:
    """Abstract connector interface."""

    name: str = "base"
    description: str = ""

    def health(self) -> Dict[str, Any]:
        return {"ok": True, "detail": "not implemented"}

    def capabilities(self) -> List[str]:
        return []

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": False, "error": f"{self.name} does not support action '{action}'"}


# ── Claude Code ────────────────────────────────────────────────────────────

class ClaudeCodeConnector(BaseConnector):
    """Runs Claude Code headlessly to build or change software.

    Use cases:
      - "Build a landing page for the new menu"
      - "Update the online ordering site to add the winter menu"
      - "Fix the booking form on the website"
      - "Generate a promotional email template"

    The connector shells out to `claude -p` with a prompt and an optional
    working directory. It returns the CLI's stdout as the detail and captures
    a session id when available.
    """

    name = "claude_code"
    description = "Build or modify software/products via Claude Code CLI (Pro subscription)."

    def __init__(self, workdir: Optional[str] = None, model: str = "opus",
                 timeout: int = 600, allowed_tools: Optional[str] = None):
        self.workdir = workdir
        self.model = model
        self.timeout = timeout
        self.allowed_tools = allowed_tools

    def health(self) -> Dict[str, Any]:
        exe = shutil.which("claude")
        if not exe:
            return {"ok": False, "detail": "claude CLI not on PATH"}
        try:
            r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=20)
            out = (r.stdout or "") + (r.stderr or "")
            if "authenticated" in out.lower() or "logged in" in out.lower() or "pro" in out.lower():
                return {"ok": True, "detail": "Claude Code authenticated"}
            return {"ok": False, "detail": f"auth status unclear: {out[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"auth check failed: {e}"}

    def capabilities(self) -> List[str]:
        return ["build_product", "modify_code", "generate_copy", "fix_bug", "create_page"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or params.get("description") or ""
        if not prompt:
            return {"ok": False, "error": "No prompt provided"}
        workdir = params.get("workdir") or self.workdir
        cmd = ["claude", "-p", "--model", params.get("model", self.model)]
        if params.get("allowed_tools") or self.allowed_tools:
            cmd += ["--allowedTools", params.get("allowed_tools") or self.allowed_tools]
        cmd.append(prompt)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=params.get("timeout", self.timeout), cwd=workdir)
            ok = r.returncode == 0
            return {
                "ok": ok,
                "detail": (r.stdout or "")[-2000:],
                "error": None if ok else (r.stderr or "")[-1000:],
                "external_ref": f"claude_code:{action}",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Claude Code timed out after {self.timeout}s"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Xero ───────────────────────────────────────────────────────────────────

class XeroConnector(BaseConnector):
    """Xero accounting platform adapter.

    Xero uses OAuth 2.0. The production flow:
      1. Register an app at https://developer.xero.com
      2. Redirect user to https://login.xero.com/identity/connect/authorize
      3. Exchange code at https://identity.xero.com/connect/token
      4. Call APIs at https://api.xero.com/api.xro/2.0/ with Bearer token + Xero-tenant-id

    This MVP supports read-only sync if XERO_ACCESS_TOKEN and XERO_TENANT_ID are
    set. It does not implement the OAuth dance — that belongs in a settings UI.
    """

    name = "xero"
    description = "Sync P&L, balance sheet, invoices, and contacts from Xero."

    API = "https://api.xero.com/api.xro/2.0"

    def __init__(self, access_token: Optional[str] = None, tenant_id: Optional[str] = None):
        self.access_token = access_token or os.environ.get("XERO_ACCESS_TOKEN")
        self.tenant_id = tenant_id or os.environ.get("XERO_TENANT_ID")

    def health(self) -> Dict[str, Any]:
        if not self.access_token:
            return {"ok": False, "detail": "XERO_ACCESS_TOKEN not set"}
        if not self.tenant_id:
            return {"ok": False, "detail": "XERO_TENANT_ID not set"}
        r = self._get("/Organisation")
        return {"ok": r.get("ok", False), "detail": "Xero reachable" if r.get("ok") else r.get("error")}

    def capabilities(self) -> List[str]:
        return ["sync_organisation", "fetch_profit_and_loss", "fetch_balance_sheet",
                "fetch_invoices", "fetch_contacts"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.access_token or not self.tenant_id:
            return {"ok": False, "error": "Xero credentials not configured"}
        endpoints = {
            "sync_organisation": "/Organisation",
            "fetch_profit_and_loss": "/Reports/ProfitAndLoss",
            "fetch_balance_sheet": "/Reports/BalanceSheet",
            "fetch_invoices": "/Invoices",
            "fetch_contacts": "/Contacts",
        }
        path = endpoints.get(action)
        if not path:
            return {"ok": False, "error": f"Unknown Xero action '{action}'"}
        r = self._get(path, params.get("query"))
        if r.get("ok"):
            r["external_ref"] = f"xero:{action}"
        return r

    def _get(self, path: str, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.API}{path}"
        if query:
            qs = "&".join(f"{k}={v}" for k, v in query.items())
            url += f"?{qs}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.access_token}",
            "Xero-tenant-id": self.tenant_id or "",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return {"ok": True, "data": json.loads(body) if body else {}}
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Lovable ────────────────────────────────────────────────────────────────

class LovableConnector(BaseConnector):
    """Lovable app-builder adapter (stub).

    Lovable (lovable.dev) does not publish a public API as of this build. The
    realistic integration paths are:
      1. Browser automation (Playwright) against the Lovable web UI.
      2. Export the generated repo and have ClaudeCodeConnector maintain it.
      3. A future official API.

    This stub documents the intended interface and routes to Claude Code as a
    fallback so BAM can still build products today.
    """

    name = "lovable"
    description = "Build web apps via Lovable (browser/API stub; falls back to Claude Code)."

    def __init__(self, fallback: Optional[BaseConnector] = None):
        self.fallback = fallback

    def health(self) -> Dict[str, Any]:
        return {"ok": False, "detail": "Lovable has no public API; use fallback connector"}

    def capabilities(self) -> List[str]:
        return ["build_app", "modify_app"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.fallback:
            return self.fallback.execute(action, params)
        return {"ok": False, "error": "Lovable connector is a stub and no fallback configured"}


# ── Generic CRM ────────────────────────────────────────────────────────────

class CRMConnector(BaseConnector):
    """Generic CRM adapter via webhook (HubSpot, Pipedrive, Close, etc.)."""

    name = "crm"
    description = "Push/pull CRM records via webhook (configurable endpoint)."

    def __init__(self, webhook_url: Optional[str] = None, api_key: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("CRM_WEBHOOK_URL")
        self.api_key = api_key or os.environ.get("CRM_API_KEY")

    def health(self) -> Dict[str, Any]:
        if not self.webhook_url:
            return {"ok": False, "detail": "CRM_WEBHOOK_URL not set"}
        return {"ok": True, "detail": "Webhook configured"}

    def capabilities(self) -> List[str]:
        return ["upsert_contact", "create_deal", "log_activity", "fetch_pipeline"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.webhook_url:
            return {"ok": False, "error": "CRM not configured"}
        payload = {"action": action, "params": params}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.webhook_url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                return {"ok": True, "detail": body[:500], "external_ref": f"crm:{action}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Generic webhook ────────────────────────────────────────────────────────

class WebhookConnector(BaseConnector):
    """Generic HTTP POST — Zapier / Make / n8n / custom endpoint."""

    name = "webhook"
    description = "Fire a JSON POST at a configured URL (automation platforms)."

    def __init__(self, url: Optional[str] = None, name: str = "webhook"):
        self.url = url or os.environ.get("BAM_WEBHOOK_URL")
        self.name = name

    def health(self) -> Dict[str, Any]:
        if not self.url:
            return {"ok": False, "detail": "No webhook URL configured"}
        return {"ok": True, "detail": "Webhook configured"}

    def capabilities(self) -> List[str]:
        return ["post"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.url:
            return {"ok": False, "error": "Webhook URL not configured"}
        req = urllib.request.Request(
            self.url,
            data=json.dumps({"action": action, "params": params}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return {"ok": True, "detail": resp.read().decode()[:300], "external_ref": f"webhook:{action}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Registry ───────────────────────────────────────────────────────────────

class ConnectorRegistry:
    """Discovery and dispatch for connectors."""

    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Optional[BaseConnector]:
        return self._connectors.get(name)

    def names(self) -> List[str]:
        return list(self._connectors.keys())

    def health_report(self) -> Dict[str, Any]:
        return {name: c.health() for name, c in self._connectors.items()}

    def capabilities_report(self) -> Dict[str, List[str]]:
        return {name: c.capabilities() for name, c in self._connectors.items()}

    def route(self, connector_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        conn = self.get(connector_name)
        if not conn:
            return {"ok": False, "error": f"Connector '{connector_name}' not registered"}
        return conn.execute(action, params)


def build_default_registry() -> ConnectorRegistry:
    """Build the standard connector set."""
    reg = ConnectorRegistry()
    cc = ClaudeCodeConnector()
    reg.register(cc)
    reg.register(LovableConnector(fallback=cc))
    reg.register(XeroConnector())
    reg.register(CRMConnector())
    reg.register(WebhookConnector())
    try:
        from ..integrations.connector import NangoConnector
        reg.register(NangoConnector())
    except Exception:
        pass  # Nango is optional; absence must not break the registry
    return reg
