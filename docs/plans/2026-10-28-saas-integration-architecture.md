# Connecting SaaS Tools & Analytics to BAM

**Status:** research complete, no code written yet
**Date:** 2026-10-28
**Scope:** how to replace BAM's static JSON graph inputs with live pulls from
accounting / commerce / analytics / CRM tools, and how to keep the initiative
loop fed with fresh data.

---

## 1. What "completing the graph" actually means in this codebase

### Current state

| Tenant | Type | Nodes | Source |
|---|---|---|---|
| `jonco` | cafe | 76 | 13 JSON files in `data/jonco/` (transactions, payroll, cogs_purchases, menu, overheads, staff_schedules, …) |
| `joncrm` | saas | 35 | **one** file, `data/joncrm/company.json` |

Node classes (`mvp/model/core.py`): `RevenueNode`, `CostNode`, `ProcessNode`,
`InputNode`, `AssetNode`, `LiabilityNode`, `MetricNode`, `AggregateNode`.
Every node carries `value`, `unit`, `trend`, `sparkline` (last 30 daily values),
`change_7d_pct`, `change_30d_pct`, `benchmark`, `constraint`, `lever`, `metadata`.

The graph is rebuilt from JSON on every request (`mvp/loader.load_graph(tenant)`),
which dispatches to `_load_cafe_graph()` or `saas_loader.build_saas_graph()`.

### The canonical field registry already exists

`mvp/multiagent/data_gaps.py` defines 10 canonical requirement keys that
consumers read:

```
revenue, cogs, units, gross_margin, visits_per_week, avg_spend,
customer_segments, adoption_rate, volume_lift, reward_value
```

This is the natural mapping target: **vendor API → canonical field → graph node.**
The `DataGapAnalyzer` already reports which requirements are unmet — so once a
node records *where* its value came from, gap reports can say "revenue is stale
because the Xero sync failed" rather than "revenue is missing".

### The asymmetry that matters

**Write path (initiatives → action): EXISTS.**
`mvp/multiagent/orchestrator.py::execute_via_connector(initiative_id,
connector_name, action, params)` routes an approved initiative to a connector and
records `external_ref` on the initiative. Connectors in
`mvp/multiagent/external.py`:

- `ClaudeCodeConnector` — headless Claude Code (build/change things)
- `XeroConnector` — read-only GETs against `api.xero.com/api.xro/2.0`
- `LovableConnector` — stub; documents the shape (no public API)
- `CRMConnector` — generic CRM webhook adapter
- `WebhookConnector` — generic POST for Zapier / Make / n8n

**Read path (tool → graph): MISSING.**
There is no scheduler, no per-tenant credential store (only env vars), no adapter
that maps vendor payloads into canonical fields, and no node refresh. That is the
entire gap this document addresses.

---

## 2. Integration landscape

### 2.1 Accounting & finance

| Tool | Auth | Endpoints needed | Documented limits | Webhooks | Sandbox | API cost | Mapping quirks |
|---|---|---|---|---|---|---|---|
| **Xero** | OAuth2 auth-code + PKCE; access **30 min**, refresh **60 days**, id **5 min** | `/Organisation`, `/Reports/ProfitAndLoss`, `/Reports/BalanceSheet`, `/Invoices`, `/Contacts`, `/BankTransactions` | **5 concurrent**, **60/min**, **1,000/day** (starter), **5,000/day** (higher tiers) | Yes — HTTPS endpoint, HMAC-SHA256 signature header; Invoice & Contact events | Free developer account + demo company | Free; app tiers: starter **5 connections**, Core **50**, Plus to list on App Store | **Report API returns rendered `Rows`/`Cells` layout**, not typed fields — brittle to parse. Prefer `BankTransactions` + `Invoices` with your own GL mapping, or Xero Tracking categories |
| **QuickBooks Online** | OAuth2; access **~60 min**, refresh **~100 days**, rotates | `/v3/company/{realmId}/reports/ProfitAndLoss`, `/reports/BalanceSheet`, `/query?query=select * from Invoice` | **~500 requests/min per realm** (verify) | Yes — Change Data Capture + webhooks | Free sandbox | Free with QBO subscription | Realm-scoped; `query` language (SQL-like); report shapes also layout-ish |
| **FreeAgent** (UK) | OAuth2 | `/v2/company`, `/v2/invoices`, `/v2/bank_transactions`, `/v2/expenses`, `/v2/categories` | **120/min**, **3,600/hour**, **15 token refreshes/min** (verified) | Limited | Free dev account | Free for accounting firms / paid product | UK-native; MTD-friendly; good fit for a UK SMB |
| **Sage Business Cloud** | OAuth2 | `/accounts/v3/…`, `/business/v3/…` | ~200/min (verify) | Yes | Free trial | Paid | Needs `X-Site` header; two APIs (Accounting vs Business) |
| **Stripe** (revenue) | API key (secret); OAuth2 only for Connect | `/v1/charges`, `/v1/invoices`, `/v1/subscriptions`, `/v1/balance_transactions`, `/v1/payouts` | **100 req/s live**, **25 req/s sandbox**, **25 req/s per endpoint** (verified) | Yes — `invoice.paid`, `payment_intent.succeeded`, `customer.subscription.updated`, `charge.refunded` | Test mode free | Free | Not multi-tenant in the Xero sense — one key per Stripe account |

**UK-specific:** VAT and Making Tax Digital matter for the cafe tenant. Xero and
FreeAgent both handle MTD; Xero's report API defaults to amounts *excluding* VAT,
so store a `tax_basis` per tenant or P&L mapping will silently differ.

### 2.2 Analytics, commerce, CRM, ads

| Tool | Auth | Key endpoints | Documented limits | Webhooks | Pirate metrics it can supply | Gotchas |
|---|---|---|---|---|---|---|
| **GA4** (Data API v1beta) | OAuth2 or service account | `runReport` (dimensions/metrics) | **200,000 core tokens/property/day**, **40,000/hour**, **10 concurrent requests**, **14,000/project/property/hour** (verified) | **No** | Acquisition (sessions, users, source/medium), Activation (events, conversions), Retention (cohorts) | Sampling on big ranges; 24–48 h latency on some dimensions; GDPR consent → undercount |
| **Plausible** | Bearer stats API key | `POST https://plausible.io/api/v2/query` | **600 requests/hour** per key (verified) | No | Acquisition (visitors, sources), top pages, goals/conversions | Cookieless → GDPR-simple, no consent banner needed; **paid product** (no free API tier) |
| **PostHog** | Personal API key (Bearer) for query; project key for ingestion | `/api/projects/{id}/query` (HogQL), `/api/events`, `/api/persons`, `/api/insights`, `/api/funnels` | Varies by endpoint (verify) | Yes — destinations/webhooks | Full funnel: activation, retention, referral, feature usage | Generous free tier; self-host option; HogQL learning curve |
| **Mixpanel** | Service account + project token | Export API, Query API | ~60 queries/hour (verify) | Yes | Activation, retention, funnels | Export API is batch-oriented |
| **Amplitude** | API key | Dashboard REST API | Varies (verify) | Yes | Retention, funnels, cohorts | Chart API deprecated in favour of Dashboard API |
| **Shopify** | OAuth app or Admin API token | Admin GraphQL, REST `/admin/api/…/orders.json` | **Leaky bucket**; REST ~2 req/s bucket 40 (standard), GraphQL ~50 cost points/s bucket 1000 (verify) | Yes — HMAC-verified: `orders/create`, `orders/paid`, `customers/create` | Revenue, AOV, units, repeat rate | Multi-currency; order edits/refunds complicate revenue; development stores free |
| **HubSpot** | OAuth2 or private app token | CRM v3 objects, `/crm/v3/objects/deals`, analytics | **100 req/10 s per app**, **250,000/day per account** (free/starter); 190/10 s pro/ent (verified) | Yes — app subscriptions | Pipeline, deal stages → activation; churn proxies | Daily limit shared across all apps in an account |
| **Pipedrive** | API token / OAuth | `/v1/deals`, `/v1/persons`, `/v1/activities` | ~80 req/2 s (verify) | Yes — v1 webhooks | Pipeline conversion, sales cycle | Simpler than HubSpot; good for small sales teams |
| **Meta Marketing API** | OAuth2 (system user) | `/insights` on ad account | Per-account tiers (verify) | No (poll) | Acquisition cost, ROAS, CAC by campaign | 90-day insight retention; attribution windows shift |
| **Google Ads API** | OAuth2 + developer token | `GoogleAdsService.SearchStream` (GAQL) | Basic access ~15,000 operations/day (verify) | No (poll) | CAC, ROAS, conversion value | Developer token approval required; GAQL syntax |

### 2.3 Minimum viable metric set

**SaaS CRM tenant (`joncrm`) — 3 connectors, ~12 metrics:**

- Stripe → `revenue`, MRR, ARR, new/churned MRR, ARPU
- GA4 or Plausible → visitors, signups, traffic→signup %, CAC inputs
- PostHog (or HubSpot) → activation %, time-to-value, retention/churn, NPS

Maps directly onto existing nodes: `kpi_mrr`, `kpi_arr`, `kpi_cac`, `kpi_ltv`,
`kpi_churn`, `kpi_nrr`, `kpi_nps`, `pm_acquisition`, `pm_visitors`, `pm_activation`,
`pm_time_to_value`, `pm_churn`, `pm_nrr`, `pm_arpu`, `pm_ltv_cac`, `pm_free_to_paid`.

**Coffee shop tenant (`jonco`) — 2–3 connectors, ~8 metrics:**

- Xero (or FreeAgent) → revenue, cogs, gross margin, operating profit, VAT
- Square / SumUp / Stripe (POS) → units, transactions, avg spend, hourly pattern
- Google Business Profile (optional) → footfall proxy, reviews, local search

Maps onto `pnl_revenue`, `pnl_cogs`, `pnl_gross_profit`, `pnl_staff`,
`pnl_overheads`, `pnl_operating_profit`, `rev_*`, `cog_*`, `prod_*`.

---

## 3. Recommended architecture

Six components, all inside BAM (no separate data platform):

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Credential vault      per-tenant encrypted tokens        │
│ 2. Integration registry   which provider per tenant, config │
│ 3. Adapters               vendor payload → canonical fields │
│ 4. Graph updater          canonical fields → node values    │
│ 5. Scheduler              cron per integration, cursors     │
│ 6. Gap attribution        node.metadata.source → data_gaps  │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Credential vault

New table `integrations` (SQLite, one file per tenant to match the existing
`initiatives_<tenant>.db` pattern):

```sql
id, tenant_id, provider, status, access_token_enc, refresh_token_enc,
expires_at, scopes, external_account_id, config_json,
cursor_json, last_sync_at, last_error, created_at
```

Encrypt with `cryptography.fernet`; master key from `BAM_SECRET_KEY` env var.
Never log token values. One row per provider per tenant. `status` ∈
`disconnected | connected | needs_reauth | error`.

### 3.2 Adapters

One module per provider, all implementing the same protocol:

```python
class Adapter(Protocol):
    provider: str
    def auth_url(self, state: str) -> str: ...
    def exchange_code(self, code: str) -> TokenSet: ...
    def refresh(self, tokens: TokenSet) -> TokenSet: ...
    def pull(self, tokens, cursor, since) -> PullResult: ...
    def canonical(self, payload) -> dict[str, float]  # canonical field → value
```

`PullResult` carries `records`, `next_cursor`, `warnings`, `rate_limit_remaining`.
This mirrors the existing `BaseConnector` contract (health/capabilities/execute),
so both directions share one registry concept — but keep them separate classes:
read adapters vs write connectors have different failure semantics.

### 3.3 Graph updater

Maps canonical fields onto node IDs via a per-tenant mapping table
(`data/<tenant>/mapping.json`), then writes `value`, `trend`, `sparkline`,
`change_7d_pct`, `change_30d_pct`, and `metadata.source = {provider, fetched_at,
external_ref, confidence}`. Recompute aggregates bottom-up afterwards
(`pnl_gross_profit = revenue - cogs`, etc.) rather than trusting vendor totals —
this is what makes the graph *yours* and lets you reconcile against the accounts.

Cache the built graph to `data/<tenant>/graph_cache.json` keyed by
`(tenant, max(last_sync_at))` so requests don't re-derive 76 nodes every time.

### 3.4 Scheduler

For a single Hetzner box: **APScheduler in-process** with a `jobs` table for
idempotency, or a tiny cron loop. Celery+Redis only if you later need multi-worker
reliability. Every sync job must be idempotent and record `(tenant, provider,
window_start, window_end)` as a natural key.

Cadence (chosen to stay far inside limits):

| Provider | Cadence | Calls/day | Limit headroom |
|---|---|---|---|
| Xero P&L | daily 06:00 | ~4 | 1,000/day cap |
| Xero invoices | every 6 h | ~4 | trivial |
| QBO | daily | ~4 | 500/min cap |
| Stripe | hourly + webhooks | ~24 | 100/s cap |
| GA4 | every 6 h | ~4 | 200k tokens/day |
| Plausible | hourly | ~24 | 600/h |
| HubSpot | hourly | ~24 | 250k/day |
| Shopify | webhooks + daily backfill | ~2 | leaky bucket |

### 3.5 Write path — reuse what exists

Initiatives already execute via `execute_via_connector`. Add an approval gate so
nothing fires without a human click (`controller.approve` already models this).
For actions with no native connector, `WebhookConnector` → n8n/Zapier/Make is the
right escape hatch. Record `external_ref` and later reconcile with
`measure_initiative()`.

### 3.6 Gap attribution

When an adapter is `disconnected`, mark affected nodes
`metadata.source = {provider, status: "missing"}`. `DataGapAnalyzer` then reports
*why* a field is absent, and the insights prompt can say "revenue is stale by 3
days" instead of silently using an old number. This is a small change with a large
effect on initiative quality.

---

## 4. Build vs buy

| Option | Cost at small scale | Time to first connector | Ops burden | Security | Lock-in | Fit for BAM |
|---|---|---|---|---|---|---|
| **Native adapters** (Python + httpx + APScheduler) | £0 licence | 2–4 days/provider | You own refresh, backoff, schema drift | Full control; tokens stay on your box | None | **Best.** Graph needs custom canonical mapping anyway |
| **Nango** (OAuth + sync infra) | Free tier; **$50/mo** PAYG incl. $50 credits; **$0.29/connection**, $0.72/compute-hour, $0.50/GB; self-host on Enterprise | ~1 day | Low — they handle refresh/rotation | SOC2 (verify); cloud or self-host | Medium | **Good add-on** if provider count grows past ~5 |
| **Merge.dev** (unified APIs) | 3 linked accounts free; **$650/mo** for 10; **$65/account** after | ~1 day | Very low | SOC2 | High — normalized schema is theirs | **Overpriced** for one-business-per-tenant; built for SaaS vendors embedding integrations |
| **Airbyte / Fivetran / Meltano** | Fivetran from ~$500/mo; Airbyte OSS free self-host | 2–5 days | High (warehouse + dbt) | Varies | High | **Overkill.** BAM needs small frequent pulls into its own model, not a warehouse |
| **n8n** (self-host) | Free self-host; cloud from **$20/mo** | Hours | Medium | Self-host = your box | Low | **Good for write path**, weak as primary read path (no backfill, opaque failures) |
| **Zapier / Make** | ~$20–30/mo | Hours | Low | Their cloud | High | Fine for one-off write actions; poor for structured data sync |
| **Replit** (Agent) | **$20/mo** Core ($18 annual) | Hours | Low | Their cloud | Medium | **Not connector infra** — good for a throwaway OAuth callback host or internal admin UI |
| **Lovable / Bolt / v0** | ~$20–30/mo | Hours | Low | Their cloud | High | Same — app builders, not integration infrastructure. `LovableConnector` stub already notes no public API |
| **Retool** | Free ≤5 users; paid ~$10/user/mo | Hours | Low | Their cloud | Medium | **Best of the builders** for an internal integration-admin screen |

### Verdict

**Build the read path natively; buy only the OAuth plumbing if provider count grows.**

Reasoning:

1. BAM's value is the *canonical mapping* — vendor → field → node → initiative.
   No aggregator knows that mapping, so you write it either way. Buying Merge.dev
   means paying £650/mo for a normalized schema you then have to re-map anyway.
2. The read volume is tiny (4–24 calls/day per provider). Rate limits are a
   non-issue; the real cost is OAuth token lifecycle and schema drift.
3. `external.py` already establishes the connector pattern and graceful
   degradation. Extending it is cheaper than integrating a vendor.
4. Replit/Lovable/Bolt are the wrong category. They build *apps*, not *connector
   infrastructure*. Using them would add a second deployment surface and a second
   place credentials live — worse security for no gain. The one genuine use is
   spinning up an HTTPS OAuth callback endpoint in minutes, or a Retool admin page
   to connect/disconnect integrations without a redeploy.

**When to revisit:** if you exceed ~8–10 providers or need certified integrations
for customers, Nango's $50/mo PAYG is the cheapest credible step up. Merge.dev
only makes sense if you become a multi-tenant SaaS selling to *other* businesses.

---

## 5. Phased plan (≈2 weeks of focused work)

**Phase 0 — foundation (1 day)**
`integrations` table + Fernet vault + `IntegrationRegistry` + `GraphUpdater`
skeleton + `mapping.json` for both tenants. No network calls yet. Unit tests for
encrypt/decrypt and canonical mapping.

**Phase 1 — first real connector (2–3 days)**
Xero read adapter: OAuth flow, token refresh with rotation lock, P&L + balance
sheet + bank transactions → canonical `revenue`, `cogs`, `gross_margin`. Wire into
`jonco` graph. Reconcile against existing JSON to prove the mapping. Surface
`metadata.source` and freshness in the drill view.

**Phase 2 — SaaS tenant (2–3 days)**
Stripe (revenue/MRR/churn) + GA4 or Plausible (acquisition) + PostHog (activation/
retention) → `joncrm` graph. This is where pirate metrics become live rather than
hardcoded in `company.json`.

**Phase 3 — near-real-time (1–2 days)**
Webhook receivers for Stripe, Shopify and Xero. HMAC verification, replay
protection, idempotent upserts. Fall back to polling when webhooks are absent
(GA4, Plausible, Meta, Google Ads).

**Phase 4 — close the loop (1–2 days)**
Approval-gated `execute_via_connector` from the UI; `external_ref` written back;
`measure_initiative()` pulls actuals from the same adapters to compute real impact
vs projected. This is what turns BAM from a model into a control loop.

**Phase 5 — hardening**
Rate-limit backoff with jitter, sync-failure alerting, gap attribution in the
insights prompt, and a `sync_status` panel in the header next to the tenant
selector.

---

## 6. Risks & gotchas

1. **Xero report layout parsing is brittle.** `Rows`/`Cells` with `RowType`
   Header/Section/Row/SummaryRow — a Xero UI change breaks the parser. Prefer
   `BankTransactions` + `Invoices` + your own GL mapping. *(verified from docs)*
2. **Refresh-token rotation.** Xero rotates refresh tokens (single-use). Two
   concurrent syncs can invalidate each other — enforce a per-tenant lock. *(verify
   the rotation semantics against current docs before relying on it)*
3. **VAT basis.** Xero/QBO report amounts exclude VAT by default. Store
   `tax_basis` per tenant or the P&L mapping silently differs from the accounts.
4. **GA4 is sampled and delayed.** Not a source of truth for revenue; use it for
   acquisition only. UK consent banners mean undercount — Plausible avoids this.
5. **GDPR/PII.** GA4/HubSpot/Shopify payloads contain personal data. Store
   aggregates only, never raw contact records, unless you add a lawful basis.
   Xero contacts are personal data too — pull aggregates, not the contact list.
6. **Multi-tenant token security.** One breach exposes several businesses' books.
   Encrypt at rest, scope tokens minimally, rotate the master key on a schedule,
   and never put tokens in URLs or logs.
7. **Schema drift.** Vendor APIs version constantly (Shopify REST→GraphQL, HubSpot
   v1→v2 specs, Mixpanel deprecations). Pin API versions and alert on parse
   failures rather than silently writing zeros.
8. **Silent staleness is worse than absence.** A graph showing last month's revenue
   as if current will produce confidently wrong initiatives. Always carry
   `fetched_at` and degrade the insight prompt when data is stale.
9. **Don't let the LLM invent numbers.** Feed only adapter-supplied values into the
   insights prompt; keep the `metadata.source` chain auditable.

---

## 7. Open questions for the user

1. Which accounting system does the cafe actually use today — Xero, FreeAgent,
   QuickBooks, or spreadsheets? That decides Phase 1.
2. What is the POS / card processor (Square, SumUp, Stripe, Zettle)? It is the only
   credible source of `units` and `avg_spend`.
3. For JonCRM: is billing in Stripe or a bespoke system? Is product analytics in
   PostHog, Mixpanel, or nowhere yet?
4. Is the intent that BAM serves *your own* businesses only, or eventually other
   businesses as customers? That changes the build-vs-buy verdict (Merge.dev becomes
   viable only in the latter case).
5. How much staleness is acceptable — daily, hourly, or near-real-time? It sets the
   scheduler and webhook scope.

---

## Sources (verified during this research)

- Xero OAuth2 token lifetimes & limits — https://developer.xero.com/documentation/guides/oauth2/auth-flow/ , https://developer.xero.com/documentation/guides/oauth2/limits/
- Xero Reports row/cell layout — https://developer.xero.com/documentation/api/accounting/reports
- Stripe rate limits — https://docs.stripe.com/rate-limits
- GA4 Data API quotas — https://developers.google.com/analytics/devguides/reporting/data/v1/quotas
- HubSpot API usage limits — https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines
- Shopify rate limits — https://shopify.dev/docs/api/usage/limits
- Plausible Stats API — https://plausible.io/docs/stats-api
- PostHog API — https://posthog.com/docs/api
- FreeAgent rate limits — https://dev.freeagent.com/docs/introduction
- Nango pricing — https://nango.dev/pricing
- Merge.dev pricing — https://www.merge.dev/pricing
- n8n pricing — https://n8n.io/pricing/
- Replit pricing — https://replit.com/pricing

Figures marked *(verify)* were not confirmed against live docs during this pass —
the source page was JS-rendered, blocked, or the figure is remembered rather than
read. Confirm before relying on them in code.
