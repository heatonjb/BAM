# Business as a Machine — MVP

> Model any business as a transformation graph: assets → processes → revenue → costs → profit.
> Use the model for agentic optimisation experiments and growth strategy.

## Overview

JonCo Coffee Limited is the test instance: a fictional indie coffee shop in Handcross, West Sussex.
The MVP ingests 9,432 granular transactions (Oct–Dec 2024), builds a transformation graph of 23 nodes,
computes KPIs against 9 industry benchmarks, and runs "what if" experiments through a Flask web UI.

**Key finding:** JonCo barely breaks even at 0.4% operating margin. Labour costs are 53% of revenue
(benchmark: 30%) — the single biggest optimisation lever.

## Architecture

```
data/jonco/              ← Raw data (transactions, payroll, COGS, overheads)
  ├── transactions.json       9,432 individual till receipts
  ├── staff_roster.json       5 employees
  ├── staff_schedules.json    315 shift records
  ├── menu.json               17 items with COGS
  ├── cogs_purchases.json     Monthly ingredient purchases
  ├── payroll.json            Biweekly payroll with NI/pension
  ├── overheads.json          17 overhead categories
  ├── bottom_up_pl.json       Aggregated P&L
  ├── balance_sheet.json      Full balance sheet
  └── company_profile.json    Companies House registration

mvp/                     ← Core pipeline
  ├── loader.py               Loads all data into BusinessGraph
  ├── transform.py            Transformation graph engine (23 nodes)
  ├── kpi.py                  KPI tree with 9 benchmarks
  ├── agent.py                Query engine + experiment simulator
  └── ui/                     ← Flask web dashboard
      ├── app.py              Flask routes
      └── templates/dashboard.html
```

## Quick Start

```bash
cd /root/code/personal/research/business-as-machine

# Run full CLI pipeline
python -m mvp --all

# Start web UI
python mvp/ui/app.py
# → http://localhost:8080

# One-shot queries
python -m mvp --query "How profitable is the business?"
python -m mvp --kpi
python -m mvp --graph
```

## Data Model

### Transaction Layer
- **9,432 receipts** over 92 days (Oct–Dec 2024)
- Each receipt: timestamp, items (with category + price), serving staff, payment method
- Revenue: £62,290 over 3 months (~£20,763/mo)

### Staff Layer
- 5 employees: 3 baristas, 1 supervisor, 1 manager
- Contract hours, overtime, absence tracking
- Full employer costs: gross + NI (13.8%) + pension (3%)
- Total labour: £33,186/quarter (53.3% of revenue)

### Supply Chain
- 24 COGS line items across 6 categories (beans, milk, pastries, packaging, consumables, cleaning)
- Supplier tracking, per-unit costs
- Total COGS: £14,810/quarter (23.8% of revenue)

### Overheads
- 17 categories grouped: premises, operations, technology, professional, marketing, depreciation
- Total overheads: £14,022/quarter (22.5% of revenue)

## KPI Results (vs Benchmarks)

| KPI | Actual | Benchmark | Status |
|---|---|---|---|
| Gross Margin | 76.2% | 75.0% | ✅ OK |
| Labour % of Revenue | 53.3% | 30.0% | 🔴 Critical |
| Overhead % of Revenue | 22.5% | 20.0% | 🟡 Poor |
| Operating Margin | 0.4% | 10.0% | 🔴 Critical |
| Revenue/Labour Hour | £31.35 | £25.00 | ✅ Good |
| COGS % of Revenue | 23.8% | 25.0% | ✅ Good |
| Transactions/Day | 103 | 120 | 🟡 Poor |
| Food Attachment Rate | 38.8% | 35.0% | ✅ OK |

## Experiment Results

| Experiment | Monthly Profit Delta |
|---|---|
| Increase volume 20% | +£2,502 |
| Cut staff costs 10% | +£1,106 |
| Raise prices 10% | +£1,181 |
| Raise prices 5% | +£617 |
| Negotiate rent 10% | +£220 |

## Web UI

Dark-themed dashboard with:
- **Overview stats** — revenue, profit, transactions
- **Revenue & profit charts** — monthly trends (bar + line)
- **Cost structure** — doughnut breakdown + category pie
- **Hourly patterns** — revenue + transaction volume by hour
- **KPI dashboard** — benchmarked with status indicators
- **Optimisation opportunities** — ranked by gap
- **Staff productivity table** — revenue per hour by role
- **Product performance table** — 17 items ranked by revenue
- **Transformation graph** — all 23 nodes with efficiency
- **Natural language query** — ask questions about the business
- **Experiment simulator** — price, staff, volume, rent changes

## Transformation Graph

The business is modelled as a directed graph:

```
[Raw Materials] → [Processes] → [Revenue]
       ↓               ↓            ↓
   Coffee Beans    Coffee Products  Total Revenue
   Milk            Pastry Products     ↓
   Pastries        Hot Drinks     Gross Profit
   Packaging       Cold Drinks        ↓
                                    [Costs]
                               ┌──────┼──────┐
                               ↓      ↓      ↓
                           Labour  Overheads  Profit
```

Each node carries:
- **value** — monthly monetary value
- **efficiency** — output/input ratio
- **constraint** — what limits throughput
- **lever** — what can be pulled to optimise

## Research Context

This MVP implements the research from 37 files in `research/`:
- Transformation algebra and graph theory
- Business ontologies (XBRL, value chains, KPI trees)
- Constraints modelling (cashflow, legal, brand)
- Agentic harness design and evaluation protocols
- Financial statement base layers and ledger prototypes

See `brief.md` for the full research brief.

## Tests

The suites are written as runnable scripts that record each assertion as it runs,
plus a `conftest.py` bridge that turns every recorded assertion into its own
pytest test. Both invocation styles work, and both fail loudly:

```bash
python -m pytest -q            # 285 tests, one per assertion, named individually
python test_montecarlo.py      # standalone: prints a report, exits non-zero on failure
```

| File | Checks | Covers |
| --- | --- | --- |
| `test_montecarlo.py` | 65 | sampler integrity, bands, copula marginals, risk ranking |
| `test_interop.py` | 45 | agent dispatch, envelope caps, protocol, reconciliation |
| `test_tenancy.py` | 30 | cross-tenant isolation, leak checks on every route |
| `test_benchmarking.py` | 26 | metric extraction, cohort widening, intervention ledger |
| `test_campaign.py` | 22 | public-data pipeline, provenance, no-send guarantee |
| `test_types.py` | 17 | template inheritance, overrides, sibling isolation |
| `test_capabilities.py` | 41 | tenant-scoped mechanisms, break-even inversion, cross-tenant refusal |
| `test_specialists.py` | 39 | lens retrieval, honest caveats, advisory-only guarantee |

Failure output names the individual check, e.g.
`FAILED test_types.py::test_checks[00 café inherits retail lineage]`.

## Tech Stack

- **Python 3.11** — data pipeline, analysis engine
- **Flask** — web framework
- **Chart.js** — client-side visualisations
- **No database** — all data is JSON files, loaded in-memory
