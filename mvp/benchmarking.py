"""Cross-type benchmarking and the intervention evidence ledger.

Two questions this module answers, and the discipline it keeps in answering them:

1. *Is this number normal for a business like mine?* Every metric is compared
   against a peer cohort taken from the type hierarchy. If the specific cohort
   is too thin to be meaningful, the peer group widens one ancestor at a time
   (coffee_shop → retail → business). The widened cohort is always reported, so
   a comparison is never quietly made against an unrelated population.

2. *Has this intervention worked before, for businesses like mine?* Every
   initiative that is activated is recorded against its type template and lever.
   When it is measured, the outcome is stored. ``evidence_for`` then reports
   what actually happened historically rather than what a prompt claims will
   happen.

Honesty rules
-------------
* Below ``MIN_COHORT`` observations a cohort reports ``insufficient_data``
  instead of a percentile. A percentile computed from three businesses is noise
  wearing a number's clothes.
* Percentiles use linear interpolation on sorted values; medians are used in
  preference to means because business ratios are skewed.
* Outcome verdicts require a baseline and a measured value. A missing
  measurement is ``unmeasured``, never a default success.

Storage lives in ``data/benchmarks.db``, separate from tenant data so a
benchmark query can never read another tenant's raw figures — only aggregates.
"""

from __future__ import annotations

import json
import os
import sqlite3
import statistics
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "benchmarks.db"
)

# A peer group smaller than this is not a distribution.
MIN_COHORT = 5

_lock = threading.Lock()


# ── Metric definitions ───────────────────────────────────────────────────────
# Each metric names the node ids that carry it, per graph family. `kind` says
# whether a higher value is better ("higher"), worse ("lower") or neither.
@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    kind: str
    unit: str
    node_ids: Tuple[str, ...]
    ratio_over: Optional[str] = None


REVENUE_NODES = ("pnl_revenue", "saas_revenue", "rev_total", "revenue")
COGS_NODES = ("pnl_cogs", "saas_cogs", "cogs_total", "cogs")
GP_NODES = ("pnl_gross_profit", "saas_gross_profit", "gross_profit")
STAFF_NODES = ("pnl_staff", "staff_total", "staff")
OH_NODES = ("pnl_overheads", "saas_opex", "opex", "overheads")
OP_NODES = ("pnl_operating_profit", "saas_op_profit", "operating_profit")

METRICS: Dict[str, MetricSpec] = {
    m.key: m
    for m in [
        MetricSpec("gross_margin_pct", "Gross margin", "higher", "%", GP_NODES, "revenue"),
        MetricSpec("staff_cost_pct", "Staff cost / revenue", "lower", "%", STAFF_NODES, "revenue"),
        MetricSpec("overhead_pct", "Overhead / revenue", "lower", "%", OH_NODES, "revenue"),
        MetricSpec("operating_margin_pct", "Operating margin", "higher", "%", OP_NODES, "revenue"),
        MetricSpec("revenue", "Monthly revenue", "higher", "currency", REVENUE_NODES),
        MetricSpec("cogs_pct", "COGS / revenue", "lower", "%", COGS_NODES, "revenue"),
    ]
}


def _find(graph: Any, ids: Sequence[str]) -> Optional[float]:
    for nid in ids:
        node = graph.get(nid) if hasattr(graph, "get") else None
        if node is not None and getattr(node, "value", None) is not None:
            return float(node.value)
    return None


def extract_metrics(graph: Any) -> Dict[str, float]:
    """Derive comparable ratios from a tenant graph.

    Ratios are over revenue so a coffee shop and a SaaS company can sit in the
    same table without the comparison being meaningless in scale.
    """
    revenue = _find(graph, REVENUE_NODES)
    out: Dict[str, float] = {}
    for spec in METRICS.values():
        value = _find(graph, spec.node_ids)
        if value is None:
            continue
        if spec.ratio_over:
            if not revenue:
                continue
            out[spec.key] = round(value / revenue * 100.0, 4)
        else:
            out[spec.key] = round(value, 4)
    return out


# ── Storage ──────────────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS observations (
                tenant_id     TEXT NOT NULL,
                type_template TEXT NOT NULL,
                metric        TEXT NOT NULL,
                value         REAL NOT NULL,
                period        TEXT NOT NULL,
                recorded_at   TEXT NOT NULL,
                PRIMARY KEY (tenant_id, metric, period)
            );
            CREATE INDEX IF NOT EXISTS idx_obs_cohort
                ON observations (type_template, metric, period);

            CREATE TABLE IF NOT EXISTS interventions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id      TEXT NOT NULL,
                initiative_id  TEXT,
                type_template  TEXT NOT NULL,
                lever          TEXT NOT NULL,
                node_family    TEXT,
                hypothesis     TEXT,
                baseline_metric TEXT,
                baseline_value REAL,
                started_at     TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_int_type
                ON interventions (type_template, lever);

            CREATE TABLE IF NOT EXISTS outcomes (
                intervention_id INTEGER PRIMARY KEY
                    REFERENCES interventions(id) ON DELETE CASCADE,
                metric          TEXT NOT NULL,
                measured_value  REAL NOT NULL,
                change_pct      REAL NOT NULL,
                verdict         TEXT NOT NULL,
                measured_at     TEXT NOT NULL
            );
            """
        )


def period_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def record_observation(
    tenant_id: str,
    type_template: str,
    metrics: Dict[str, float],
    period: Optional[str] = None,
) -> int:
    """Upsert one tenant's metrics for a period. Returns rows written."""
    if not metrics:
        return 0
    init_db()
    p = period or period_now()
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        for metric, value in metrics.items():
            conn.execute(
                """INSERT INTO observations
                     (tenant_id, type_template, metric, value, period, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, metric, period) DO UPDATE SET
                     value = excluded.value,
                     type_template = excluded.type_template,
                     recorded_at = excluded.recorded_at""",
                (tenant_id, type_template, metric, float(value), p, now),
            )
    return len(metrics)


def cohort_values(cohort: str, metric: str, period: Optional[str] = None,
                  exclude_tenant: Optional[str] = None) -> List[float]:
    init_db()
    p = period or period_now()
    sql = "SELECT tenant_id, value FROM observations WHERE type_template = ? AND metric = ? AND period = ?"
    params: List[Any] = [cohort, metric, p]
    if exclude_tenant:
        sql += " AND tenant_id != ?"
        params.append(exclude_tenant)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [float(r["value"]) for r in rows]


def percentile_of(value: float, population: Sequence[float]) -> float:
    """Percentile rank of ``value`` within ``population`` (0-100)."""
    if not population:
        return float("nan")
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return round((below + 0.5 * equal) / len(population) * 100.0, 1)


def _quartiles(values: Sequence[float]) -> Dict[str, float]:
    ordered = sorted(values)
    if len(ordered) == 1:
        v = ordered[0]
        return {"p25": v, "median": v, "p75": v, "mean": v}
    q = statistics.quantiles(ordered, n=4, method="inclusive")
    return {
        "p25": round(q[0], 2),
        "median": round(statistics.median(ordered), 2),
        "p75": round(q[2], 2),
        "mean": round(statistics.fmean(ordered), 2),
    }


def benchmark_tenant(
    tenant_id: str,
    type_template: str,
    cohort_chain: Sequence[str],
    metrics: Optional[Dict[str, float]] = None,
    period: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare one tenant's metrics against the narrowest cohort that is big enough.

    ``cohort_chain`` must be ordered most-specific first. The first cohort with at
    least ``MIN_COHORT`` peers is used; if none qualifies the result is reported
    as insufficient rather than compared against a handful of businesses.
    """
    init_db()
    p = period or period_now()
    if metrics is None:
        metrics = {}
        with _connect() as conn:
            rows = conn.execute(
                "SELECT metric, value FROM observations WHERE tenant_id = ? AND period = ?",
                (tenant_id, p),
            ).fetchall()
        metrics = {r["metric"]: float(r["value"]) for r in rows}

    results: Dict[str, Any] = {}
    for key, value in metrics.items():
        spec = METRICS.get(key)
        if spec is None:
            continue
        chosen = None
        for cohort in cohort_chain:
            values = cohort_values(cohort, key, p, exclude_tenant=tenant_id)
            if len(values) >= MIN_COHORT:
                chosen = (cohort, values)
                break
        if chosen is None:
            results[key] = {
                "metric": key,
                "label": spec.label,
                "value": value,
                "status": "insufficient_data",
                "peers": max(
                    (len(cohort_values(c, key, p, exclude_tenant=tenant_id))
                     for c in cohort_chain), default=0
                ),
            }
            continue
        cohort, values = chosen
        q = _quartiles(values)
        pct = percentile_of(value, values)
        better = pct >= 50 if spec.kind == "higher" else pct <= 50
        results[key] = {
            "metric": key,
            "label": spec.label,
            "value": value,
            "cohort": cohort,
            "peers": len(values),
            "percentile": pct,
            "median": q["median"],
            "p25": q["p25"],
            "p75": q["p75"],
            "kind": spec.kind,
            "status": "above_median" if better else "below_median",
            "widened": cohort != cohort_chain[0],
            "gap_to_median": round(value - q["median"], 2),
        }
    return {"tenant_id": tenant_id, "period": p, "metrics": results}


# ── Intervention ledger ──────────────────────────────────────────────────────
def record_intervention(
    tenant_id: str,
    type_template: str,
    lever: str,
    hypothesis: str = "",
    node_family: Optional[str] = None,
    initiative_id: Optional[str] = None,
    baseline_metric: Optional[str] = None,
    baseline_value: Optional[float] = None,
) -> int:
    """Log an initiative at the moment it starts, with its baseline.

    The baseline is captured now because it cannot be recovered honestly later.
    """
    init_db()
    with _lock, _connect() as conn:
        cur = conn.execute(
            """INSERT INTO interventions
                 (tenant_id, initiative_id, type_template, lever, node_family,
                  hypothesis, baseline_metric, baseline_value, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tenant_id, initiative_id, type_template, lever, node_family,
                hypothesis, baseline_metric,
                None if baseline_value is None else float(baseline_value),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return int(cur.lastrowid)


def record_outcome(
    intervention_id: int, measured_value: float, metric: Optional[str] = None
) -> Dict[str, Any]:
    """Attach a measured outcome and judge it against the recorded baseline."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM interventions WHERE id = ?", (intervention_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown intervention {intervention_id}")
        metric = metric or row["baseline_metric"]
        baseline = row["baseline_value"]
        if metric is None or baseline is None:
            verdict, change = "unmeasured", 0.0
        elif baseline == 0:
            verdict, change = "unmeasured", 0.0
        else:
            change = round((measured_value - baseline) / abs(baseline) * 100.0, 2)
            spec = METRICS.get(metric)
            improved = change > 0 if (spec is None or spec.kind == "higher") else change < 0
            verdict = "improved" if improved and abs(change) >= 1.0 else (
                "no_change" if abs(change) < 1.0 else "worsened"
            )
        conn.execute(
            """INSERT INTO outcomes
                 (intervention_id, metric, measured_value, change_pct, verdict, measured_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(intervention_id) DO UPDATE SET
                 measured_value = excluded.measured_value,
                 change_pct = excluded.change_pct,
                 verdict = excluded.verdict,
                 measured_at = excluded.measured_at""",
            (
                intervention_id, metric or "unknown", float(measured_value),
                change, verdict, datetime.now(timezone.utc).isoformat(),
            ),
        )
    return {"intervention_id": intervention_id, "verdict": verdict, "change_pct": change}


def evidence_for(type_template: str, lever: Optional[str] = None) -> Dict[str, Any]:
    """Historical success of interventions of this type (and lever).

    This is what separates a hypothesis from a guess: the arbiter can cite a
    measured base rate instead of asserting that a lever usually works.
    """
    init_db()
    sql = """SELECT i.id, i.lever, i.type_template, o.verdict, o.change_pct
               FROM interventions i JOIN outcomes o ON o.intervention_id = i.id
              WHERE i.type_template = ?"""
    params: List[Any] = [type_template]
    if lever:
        sql += " AND i.lever = ?"
        params.append(lever)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    verdicts = [r["verdict"] for r in rows]
    changes = [float(r["change_pct"]) for r in rows]
    n = len(rows)
    improved = verdicts.count("improved")
    return {
        "type_template": type_template,
        "lever": lever,
        "trials": n,
        "improved": improved,
        "worsened": verdicts.count("worsened"),
        "no_change": verdicts.count("no_change"),
        "success_rate": round(improved / n, 3) if n else None,
        "median_change_pct": round(statistics.median(changes), 2) if changes else None,
        "confidence": (
            "none" if n == 0 else "low" if n < 5 else "moderate" if n < 20 else "high"
        ),
    }


def hypotheses_for(tenant_id: str, type_template: str, cohort_chain: Sequence[str],
                   metrics: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """Rank candidate levers by measured cohort gap and historical evidence.

    A hypothesis is only emitted for a metric that is behind its peer median and
    that has a known lever. Confidence is capped by the number of historical
    trials, so a large gap with no evidence is not presented as a sure thing.
    """
    from . import types as type_registry

    bench = benchmark_tenant(tenant_id, type_template, cohort_chain, metrics)
    lever_for_metric = {
        "gross_margin_pct": ("pricing_and_mix", "revenue"),
        "cogs_pct": ("supplier_terms_and_waste", "cogs"),
        "staff_cost_pct": ("rota_and_productivity", "staff"),
        "overhead_pct": ("overhead_reduction", "overheads"),
        "operating_margin_pct": ("margin_recovery", "gross_profit"),
        "revenue": ("acquisition_and_retention", "revenue"),
    }

    out: List[Dict[str, Any]] = []
    for key, row in bench["metrics"].items():
        if row.get("status") != "below_median":
            continue
        lever = lever_for_metric.get(key)
        if not lever:
            continue
        ev = evidence_for(type_template, lever[0])
        gap = abs(row.get("gap_to_median") or 0.0)
        # Gap is the size of the opportunity; evidence is the chance of realising
        # it. Multiplying keeps a big untested gap below a modest proven one.
        score = gap * (ev["success_rate"] if ev["success_rate"] is not None else 0.35)
        out.append({
            "metric": key,
            "lever": lever[0],
            "node_family": lever[1],
            "gap_to_median": row.get("gap_to_median"),
            "cohort": row.get("cohort"),
            "peers": row.get("peers"),
            "evidence": ev,
            "score": round(score, 2),
            "statement": (
                f"{row['label']} is {gap:.1f} points off the {row['cohort']} median; "
                f"lever {lever[0]!r} has "
                + (f"improved {ev['improved']} of {ev['trials']} similar attempts"
                   if ev["trials"] else "no measured precedent yet")
            ),
        })
    return sorted(out, key=lambda h: h["score"], reverse=True)
