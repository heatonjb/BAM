"""Checks for cross-type benchmarking and the intervention evidence ledger.

Runs against a temporary database so a test run never pollutes the real peer
cohorts. The behaviours under test are the ones that would otherwise fail
silently: cohort widening, refusal to compare against a thin group, and the
difference between a measured outcome and an assumed one.
"""

from __future__ import annotations

import os
import sys
import tempfile

from mvp import benchmarking as B

FAILS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}{' — ' + detail if detail else ''}")
        FAILS.append(label)


tmpdir = tempfile.mkdtemp(prefix="bam_bench_")
B.DB_PATH = os.path.join(tmpdir, "bench.db")
B.init_db()
print(f"temp db: {B.DB_PATH}")

PERIOD = "2026-10"

print("== metric extraction from a real graph ==")
from mvp.loader import load_graph

cafe = load_graph("jonco")
saas = load_graph("joncrm")
cm = B.extract_metrics(cafe)
sm = B.extract_metrics(saas)
print(f"  café metrics: {cm}")
print(f"  saas metrics: {sm}")
check("café ratios extracted", {"gross_margin_pct", "staff_cost_pct", "overhead_pct"} <= set(cm))
check("gross margin is a percentage",
      0 < cm.get("gross_margin_pct", -1) < 100, str(cm.get("gross_margin_pct")))
check("saas ratios extracted", {"gross_margin_pct", "operating_margin_pct"} <= set(sm))

print("== insufficient cohort is refused ==")
B.record_observation("jonco", "coffee_shop", cm, PERIOD)
thin = B.benchmark_tenant("jonco", "coffee_shop", ["coffee_shop", "retail", "business"], cm, PERIOD)
gm = thin["metrics"]["gross_margin_pct"]
check("thin cohort reports insufficient_data", gm["status"] == "insufficient_data", str(gm))
check("thin cohort reports peer count", gm["peers"] == 0, str(gm.get("peers")))

print("== cohort widening ==")
# Six retail peers, no coffee_shop peers: the narrow cohort is too thin, so the
# comparison must widen to retail and say that it did.
for i, margin in enumerate([40.0, 45.0, 50.0, 55.0, 60.0, 65.0]):
    B.record_observation(f"peer-{i}", "retail", {"gross_margin_pct": margin}, PERIOD)
wide = B.benchmark_tenant("jonco", "coffee_shop", ["coffee_shop", "retail", "business"], cm, PERIOD)
w = wide["metrics"]["gross_margin_pct"]
check("widened to retail", w.get("cohort") == "retail", str(w.get("cohort")))
check("widening is flagged", w.get("widened") is True)
check("peer count reflects retail", w["peers"] == 6, str(w["peers"]))
check("median is the retail median", w["median"] == 52.5, str(w["median"]))
check("percentile is computed", 0 <= w["percentile"] <= 100, str(w["percentile"]))

print("== specific cohort wins when it is big enough ==")
# Peers are healthier than the tenant, so the tenant lands below the median and
# the hypothesis engine has a gap to work with.
for i, margin in enumerate([82.0, 84.0, 86.0, 88.0, 90.0]):
    B.record_observation(f"cafe-peer-{i}", "coffee_shop", {"gross_margin_pct": margin}, PERIOD)
narrow = B.benchmark_tenant("jonco", "coffee_shop", ["coffee_shop", "retail", "business"], cm, PERIOD)
n = narrow["metrics"]["gross_margin_pct"]
check("uses the specific cohort", n.get("cohort") == "coffee_shop", str(n.get("cohort")))
check("not flagged as widened", n.get("widened") is False)
check("peer count is the specific cohort", n["peers"] == 5, str(n["peers"]))

print("== intervention ledger ==")
iid = B.record_intervention(
    "jonco", "coffee_shop", "supplier_terms_and_waste",
    hypothesis="Renegotiate bean contract and cut pastry waste",
    node_family="cogs", baseline_metric="cogs_pct", baseline_value=40.0,
)
res = B.record_outcome(iid, 36.0)
check("lower-is-better metric improving gives 'improved'", res["verdict"] == "improved", str(res))
check("change is recorded as a percentage", res["change_pct"] == -10.0, str(res["change_pct"]))

iid2 = B.record_intervention(
    "jonco", "coffee_shop", "supplier_terms_and_waste",
    node_family="cogs", baseline_metric="cogs_pct", baseline_value=40.0,
)
res2 = B.record_outcome(iid2, 44.0)
check("worsening is recorded", res2["verdict"] == "worsened", str(res2))

ev = B.evidence_for("coffee_shop", "supplier_terms_and_waste")
check("evidence counts both trials", ev["trials"] == 2, str(ev["trials"]))
check("evidence counts one improvement", ev["improved"] == 1, str(ev["improved"]))
check("success rate is measured", ev["success_rate"] == 0.5, str(ev["success_rate"]))
check("small samples report low confidence", ev["confidence"] == "low", str(ev["confidence"]))

empty = B.evidence_for("coffee_shop", "pricing_and_mix")
check("no evidence reports none, not a guess", empty["confidence"] == "none" and empty["success_rate"] is None, str(empty))

print("== hypotheses ranked by gap x evidence ==")
hyps = B.hypotheses_for("jonco", "coffee_shop", ["coffee_shop", "retail", "business"], cm)
for h in hyps[:3]:
    print(f"  {h['score']:>7}  {h['lever']:<28} {h['statement'][:80]}")
check("hypotheses are produced for behind-median metrics", len(hyps) > 0)
check("hypotheses are sorted by score",
      all(hyps[i]["score"] >= hyps[i + 1]["score"] for i in range(len(hyps) - 1)))
check("every hypothesis carries evidence", all("evidence" in h for h in hyps))
check("untested levers say so", all(
    "no measured precedent" in h["statement"] or "improved" in h["statement"] for h in hyps))

print("== persistence ==")
B.init_db()
count = B.cohort_values("retail", "gross_margin_pct", PERIOD)
check("observations persist", len(count) == 6, str(len(count)))

print()
if FAILS:
    print(f"{len(FAILS)} check(s) failed: {FAILS}")
    sys.exit(1)
print("All benchmarking checks passed.")
