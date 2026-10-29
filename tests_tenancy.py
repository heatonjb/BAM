"""Cross-tenant isolation tests.

Every route that reads or writes business data is exercised twice: once as a
café-only user and once as a SaaS-only user. The assertions check that no
tenant's data appears in another tenant's responses.

Run:  python3 tests_tenancy.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("BAM_DEBUG", "0")

from mvp.auth import store as auth_store  # noqa: E402
from mvp.ui.app import app  # noqa: E402

CAFE = "jonco"
SAAS = "joncrm"

# Strings that only exist in the café tenant's data.
CAFE_MARKERS = ["JONCO COFFEE", "15999847", "Coffee Beans", "barista", "Pain au Chocolat", "pastry"]
# Strings that only exist in the SaaS tenant's data.
SAAS_MARKERS = ["JonCRM", "SAAS-2024", "Enterprise Tier", "Pro Tier", "MRR"]

failures = []
checks = 0


def check(label, condition, detail=""):
    global checks
    checks += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        failures.append(label)


def _ensure_user(email, password, tenant_ids):
    u = auth_store.get_user_by_email(email)
    if u:
        for t in tenant_ids:
            auth_store.add_membership(u["id"], t)
        return u, password
    return auth_store.create_user(email, password, email.split("@")[0], tenant_ids=tenant_ids), password


def login(client, email, password):
    html = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    token = m.group(1) if m else ""
    r = client.post("/login", data={"_csrf": token, "email": email, "password": password})
    assert r.status_code in (200, 302), f"login failed for {email}: {r.status_code}"
    return client


def leak_check(label, body, forbidden):
    hits = [m for m in forbidden if m.lower() in body.lower()]
    check(label, not hits, f"-> leaked: {hits}")


def main():
    cafe_user, cafe_pw = _ensure_user("cafe-test@bam.local", "CafeTestPassword123!", [CAFE])
    saas_user, saas_pw = _ensure_user("saas-test@bam.local", "SaasTestPassword123!", [SAAS])

    cafe = login(app.test_client(), "cafe-test@bam.local", cafe_pw)
    saas = login(app.test_client(), "saas-test@bam.local", saas_pw)

    print("\n== tenant resolution ==")
    # Compare parsed JSON: jsonify() appends a trailing newline, so raw string
    # comparison produced false failures.
    check("cafe user sees only jonco", cafe.get("/api/tenants").get_json() == ["jonco"])
    check("saas user sees only joncrm", saas.get("/api/tenants").get_json() == ["joncrm"])

    print("\n== dashboard ==")
    cafe_dash = cafe.get("/dashboard").get_data(as_text=True)
    saas_dash = saas.get("/dashboard").get_data(as_text=True)
    leak_check("café dashboard has no SaaS data", cafe_dash, SAAS_MARKERS)
    leak_check("SaaS dashboard has NO café products/staff", saas_dash, CAFE_MARKERS)
    check("café dashboard shows café name", "JONCO COFFEE" in cafe_dash)
    check("SaaS dashboard shows SaaS name", "JonCRM" in saas_dash)
    check("SaaS dashboard revenue is SaaS MRR-shaped", "47,990" in saas_dash or "47990" in saas_dash,
          "expected SaaS revenue figure")

    print("\n== URL tampering (query parameter) ==")
    r = saas.get(f"/dashboard?tenant={CAFE}")
    body = r.get_data(as_text=True)
    leak_check("SaaS user cannot read café dashboard via ?tenant=", body, CAFE_MARKERS)
    r = cafe.get(f"/dashboard?tenant={SAAS}")
    leak_check("café user cannot read SaaS dashboard via ?tenant=", r.get_data(as_text=True), SAAS_MARKERS)

    print("\n== index / drill ==")
    leak_check("café index has no SaaS data", cafe.get("/").get_data(as_text=True), SAAS_MARKERS)
    leak_check("SaaS index has no café data", saas.get("/").get_data(as_text=True), CAFE_MARKERS)

    # drill into a café-only node as the SaaS user -> must 404, not render
    r = saas.get("/drill/pnl_revenue")
    check("SaaS user drilling a café node is refused", r.status_code == 404, f"got {r.status_code}")
    r = cafe.get("/drill/saas_revenue")
    check("café user drilling a SaaS node is refused", r.status_code == 404, f"got {r.status_code}")

    print("\n== API reads ==")
    for path in ["/api/node/pnl_revenue", "/api/subgraph/pnl_revenue", "/api/constraints/pnl_revenue"]:
        r = saas.get(path)
        check(f"SaaS user GET {path} refused", r.status_code == 404, f"got {r.status_code}")

    r = cafe.get("/api/constraints")
    cafe_constraints = r.get_data(as_text=True)
    check("café constraints non-empty", len(cafe_constraints) > 10)
    r = saas.get("/api/constraints")
    saas_constraints = r.get_data(as_text=True)
    check("SaaS constraints do not contain café node ids",
          "staff_barista" not in saas_constraints and "cap_espresso" not in saas_constraints)

    print("\n== integration endpoints ==")
    r = saas.get(f"/api/integrations/connections?tenant={CAFE}")
    check("SaaS user cannot list café connections", r.status_code == 403, f"got {r.status_code}")
    r = saas.get("/api/integrations/connections")
    check("SaaS user's own connections list is empty", '"connections":[]' in r.get_data(as_text=True).replace(" ", ""))
    r = saas.post("/api/integrations/sync", json={"tenant": CAFE})
    check("SaaS user cannot trigger café sync", r.status_code == 403, f"got {r.status_code}")
    r = saas.post("/api/integrations/connect", json={"tenant": CAFE, "provider": "stripe"})
    check("SaaS user cannot connect café provider", r.status_code == 403, f"got {r.status_code}")

    print("\n== write paths ==")
    r = saas.post(f"/switch-tenant/{CAFE}")
    check("SaaS user cannot switch to café tenant", r.status_code == 403, f"got {r.status_code}")

    print("\n== background jobs ==")
    r = cafe.post("/api/insights/pnl_revenue", json={})
    job_id = r.get_json().get("job_id") if r.status_code == 202 else None
    check("café insight job created", bool(job_id))
    if job_id:
        r = saas.get(f"/api/insights/jobs/{job_id}")
        check("SaaS user cannot poll café job", r.status_code == 404, f"got {r.status_code}")

    print("\n== registry has no shared singletons ==")
    from mvp.tenancy import registry
    cached = registry.cached_tenants()
    for key, tenants in cached.items():
        check(f"{key} caches are per-tenant only", set(tenants) <= {CAFE, SAAS}, f"{key}={tenants}")

    # cleanup test users
    for u in (cafe_user, saas_user):
        with auth_store._connect() as conn:
            conn.execute("DELETE FROM memberships WHERE user_id = ?", (u["id"],))
            conn.execute("DELETE FROM users WHERE id = ?", (u["id"],))

    print(f"\n{checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("All tenant-isolation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
