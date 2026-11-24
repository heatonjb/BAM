"""Checks for the Nango integration layer.

The contract that matters: responses from api.nango.dev are normalised at the
client boundary, a connect session binds the tenant as Nango's ``end_user``, and
missing configuration degrades to an explicit answer instead of a crash or a
false "connected".

No test here touches the network. Set ``NANGO_LIVE=1`` to additionally probe the
live API with the configured secret key.
"""

from __future__ import annotations

import os
import sys

FAILS: list[str] = []


RECORDS: list = []


def check(label, cond, detail=""):
    ok = bool(cond)
    RECORDS.append((str(label), ok, str(detail)))
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}{' — ' + detail if detail else ''}")
        FAILS.append(str(label))


from mvp.integrations import nango as N
from mvp.integrations.connector import NangoConnector


class FakeTransport:
    """Stands in for NangoClient._request: records the call, returns a payload."""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls: list = []

    def __call__(self, method, path, body=None, query=None, extra_headers=None):
        self.calls.append({"method": method, "path": path, "body": body,
                           "query": query, "extra_headers": extra_headers})
        if self.error is not None:
            raise self.error
        return self.payload


def client_with(payload=None, error=None):
    client = N.NangoClient(secret_key="test-key")
    transport = FakeTransport(payload, error)
    client._request = transport
    return client, transport


def _raises(fn):
    try:
        fn()
    except N.NangoError:
        return True
    return False


print("== response normalisation ==")

# Live shape verified 2026-11-18: GET /integrations -> {"data": [...]}
client, _ = client_with({"data": [{"uniqueKey": "stripe"}]})
check("list_integrations unwraps {'data': [...]}", client.list_integrations() == [{"uniqueKey": "stripe"}],
      str(client.list_integrations()))

client, _ = client_with({"configs": [{"uniqueKey": "xero"}]})
check("list_integrations accepts legacy {'configs': [...]}", client.list_integrations() == [{"uniqueKey": "xero"}])

client, _ = client_with([{"uniqueKey": "shopify"}])
check("list_integrations accepts a bare list", client.list_integrations() == [{"uniqueKey": "shopify"}])

client, _ = client_with({})
check("list_integrations on an empty body yields []", client.list_integrations() == [])

client, _ = client_with({"connections": [{"id": "c1"}]})
check("list_connections unwraps {'connections': [...]}", client.list_connections() == [{"id": "c1"}])

client, transport = client_with({"data": [{"id": "c2"}]})
check("list_connections also accepts a {'data': [...]} wrapper",
      client.list_connections() == [{"id": "c2"}])

print("== connection filters ==")
client, transport = client_with({"connections": []})
client.list_connections(integration_id="stripe", end_user_id="acme")
sent = transport.calls[0]["query"]
check("filter uses providerConfigKey", sent.get("providerConfigKey") == "stripe", str(sent))
check("filter uses endUserId", sent.get("endUserId") == "acme", str(sent))

print("== connect session payload ==")
client, transport = client_with({"data": {"token": "tok", "connect_link": "https://connect.nango.dev/?x"}})
session = client.create_connect_session(
    "stripe", "acme", end_user_email="ops@acme.test", organization_id="acme-org")
body = transport.calls[0]["body"]
check("session binds the tenant as end_user", body.get("end_user") == {
    "id": "acme", "email": "ops@acme.test"}, str(body))
check("session scopes allowed_integrations", body.get("allowed_integrations") == ["stripe"], str(body))
check("session sends organization as an object", body.get("organization") == {"id": "acme-org"}, str(body))
check("session sends no legacy tags", "tags" not in body, str(body))
check("session response is unwrapped", session.get("connect_link") == "https://connect.nango.dev/?x",
      str(session))

client, transport = client_with({"data": {"token": "tok"}})
client.create_connect_session("xero", "acme")
check("no organization key when unset", "organization" not in transport.calls[0]["body"])

print("== failure behaviour ==")
client, _ = client_with(error=N.NangoError("Nango HTTP 401: bad key", status=401))
check("list_integrations raises NangoError", _raises(lambda: client.list_integrations()))

nango_connector = NangoConnector(client_with(error=None)[0])

_saved_key = os.environ.pop("NANGO_SECRET_KEY", None)
health = nango_connector.health()
check("health without a key is an explicit not-configured answer",
      health.get("ok") is False and "NANGO_SECRET_KEY" in health.get("detail", ""), str(health))
if _saved_key is not None:
    os.environ["NANGO_SECRET_KEY"] = _saved_key

proxy = nango_connector.execute("proxy_call", {"tenant": "acme", "provider": "stripe",
                                              "endpoint": "/v1/charges"})
check("proxy without a stored connection fails without network",
      proxy.get("ok") is False and "create_connect_session" in proxy.get("error", ""), str(proxy))

unknown = nango_connector.execute("create_connect_session", {"tenant": "acme", "provider": "nope"})
check("unknown provider is rejected before any network call",
      unknown.get("ok") is False and "unknown provider" in unknown.get("error", ""), str(unknown))

bad_action = nango_connector.execute("teleport", {})
check("unsupported action is reported", bad_action.get("ok") is False)

print("== live API (opt-in) ==")
if os.environ.get("NANGO_LIVE") == "1" and os.environ.get("NANGO_SECRET_KEY"):
    live = N.NangoClient().health()
    check("live Nango health succeeds with the configured key", live.get("ok") is True, str(live))
else:
    print("  SKIP  live probe (set NANGO_LIVE=1 and NANGO_SECRET_KEY)")

print()
if __name__ == "__main__":
    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    else:
        print("All Nango checks passed.")
    sys.exit(0)


def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"