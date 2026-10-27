"""Historical knowledge base for BAM initiatives.

Records every initiative's predicted vs actual outcome so specialist agents can
calibrate future hypotheses: "price increases on this node over-delivered by 20%
last time; staffing changes under-delivered by 40%."

Backed by SQLite at data/initiatives.db. Deliberately simple so it is portable
and inspectable — the multi-tenant version can swap in Postgres without changing
the interface.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .hypothesis import Initiative, InitiativeStatus, LeverType

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "initiatives.db",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS initiatives (
    id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    agent_id TEXT,
    node_id TEXT,
    node_label TEXT,
    title TEXT,
    description TEXT,
    lever_type TEXT,
    status TEXT,
    predicted_impact_gbp REAL,
    actual_impact_gbp REAL,
    accuracy_ratio REAL,
    absolute_error_pct REAL,
    predictions_json TEXT,
    actual_metrics_json TEXT,
    created_at TEXT,
    approved_at TEXT,
    started_at TEXT,
    measured_at TEXT,
    owner TEXT,
    external_ref TEXT,
    notes_json TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_init_lever ON initiatives(lever_type);
CREATE INDEX IF NOT EXISTS idx_init_node ON initiatives(node_id);
CREATE INDEX IF NOT EXISTS idx_init_status ON initiatives(status);

CREATE TABLE IF NOT EXISTS hypotheses (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    node_id TEXT,
    node_label TEXT,
    title TEXT,
    description TEXT,
    lever_type TEXT,
    expected_impact_gbp REAL,
    effort REAL,
    risk REAL,
    confidence REAL,
    score REAL,
    constraints_ok INTEGER,
    rationale TEXT,
    payload_json TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_hyp_node ON hypotheses(node_id);
CREATE INDEX IF NOT EXISTS idx_hyp_lever ON hypotheses(lever_type);
"""


class HistoricalKnowledgeBase:
    """Query and record historical initiative outcomes."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ── Recording ─────────────────────────────────────────────────────────

    def record_initiative(self, ini: Initiative) -> None:
        d = ini.to_dict()
        self._conn.execute(
            """INSERT OR REPLACE INTO initiatives
               (id, hypothesis_id, agent_id, node_id, node_label, title, description,
                lever_type, status, predicted_impact_gbp, actual_impact_gbp,
                accuracy_ratio, absolute_error_pct, predictions_json, actual_metrics_json,
                created_at, approved_at, started_at, measured_at, owner, external_ref,
                notes_json, metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d["id"], d["hypothesis_id"], d["agent_id"], d["node_id"], d["node_label"],
                d["title"], d["description"], d["lever_type"], d["status"],
                d["predicted_impact_gbp"], d["actual_impact_gbp"], d["accuracy_ratio"],
                d["absolute_error_pct"], json.dumps(d["predictions"]),
                json.dumps(d["actual_metrics"]), d["created_at"], d["approved_at"],
                d["started_at"], d["measured_at"], d["owner"], d["external_ref"],
                json.dumps(d["notes"]), json.dumps(d["metadata"]),
            ),
        )
        self._conn.commit()

    def record_hypothesis(self, hyp) -> None:
        d = hyp.to_dict()
        self._conn.execute(
            """INSERT OR REPLACE INTO hypotheses
               (id, agent_id, node_id, node_label, title, description, lever_type,
                expected_impact_gbp, effort, risk, confidence, score, constraints_ok,
                rationale, payload_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d["id"], d["agent_id"], d["node_id"], d["node_label"], d["title"],
                d["description"], d["lever_type"], d["expected_impact_gbp"], d["effort"],
                d["risk"], d["confidence"], d["score"], int(d["constraints_ok"]),
                d["rationale"], json.dumps(d), d["created_at"],
            ),
        )
        self._conn.commit()

    def measure(self, initiative_id: str, actual_impact_gbp: float,
                actual_metrics: Optional[Dict[str, float]] = None,
                notes: Optional[List[str]] = None) -> Optional[Initiative]:
        """Record the actual outcome of an initiative and compute accuracy."""
        row = self._conn.execute("SELECT * FROM initiatives WHERE id=?", (initiative_id,)).fetchone()
        if not row:
            return None
        ini = self._row_to_initiative(row)
        ini.actual_impact_gbp = actual_impact_gbp
        ini.actual_metrics = actual_metrics or {}
        ini.status = InitiativeStatus.MEASURED
        ini.measured_at = datetime.now(timezone.utc).isoformat()
        if notes:
            ini.notes.extend(notes)
        self.record_initiative(ini)
        return ini

    # ── Queries ───────────────────────────────────────────────────────────

    def get_initiative(self, initiative_id: str) -> Optional[Initiative]:
        row = self._conn.execute("SELECT * FROM initiatives WHERE id=?", (initiative_id,)).fetchone()
        return self._row_to_initiative(row) if row else None

    def list_initiatives(self, status: Optional[str] = None,
                         node_id: Optional[str] = None,
                         lever_type: Optional[str] = None,
                         limit: int = 100) -> List[Initiative]:
        q = "SELECT * FROM initiatives WHERE 1=1"
        params: List[Any] = []
        if status:
            q += " AND status=?"; params.append(status)
        if node_id:
            q += " AND node_id=?"; params.append(node_id)
        if lever_type:
            q += " AND lever_type=?"; params.append(lever_type)
        q += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
        return [self._row_to_initiative(r) for r in self._conn.execute(q, params).fetchall()]

    def history_for_lever(self, lever_type: str, limit: int = 50) -> List[Initiative]:
        return [i for i in self.list_initiatives(lever_type=lever_type, limit=limit)
                if i.actual_impact_gbp is not None]

    def history_for_node(self, node_id: str, limit: int = 50) -> List[Initiative]:
        return [i for i in self.list_initiatives(node_id=node_id, limit=limit)
                if i.actual_impact_gbp is not None]

    # ── Calibration ───────────────────────────────────────────────────────

    def calibration(self, lever_type: Optional[str] = None,
                    node_id: Optional[str] = None) -> Dict[str, Any]:
        """Return calibration statistics for a lever type and/or node.

        - n: number of measured initiatives
        - success_rate: fraction where actual >= 80% of predicted
        - mean_accuracy: mean(actual/predicted)
        - median_accuracy
        - mean_abs_error_pct
        - over_delivery_rate: fraction where actual > predicted
        """
        ini_list = [i for i in self.list_initiatives(lever_type=lever_type, node_id=node_id, limit=200)
                    if i.actual_impact_gbp is not None and i.predicted_impact_gbp != 0]
        ratios: List[float] = []
        errors: List[float] = []
        for i in ini_list:
            r = i.accuracy_ratio
            if r is not None:
                ratios.append(float(r))
            e = i.absolute_error_pct
            if e is not None:
                errors.append(float(e))
        ratios.sort()
        n = len(ratios)
        if n == 0:
            return {"n": 0, "success_rate": None, "mean_accuracy": None,
                    "median_accuracy": None, "mean_abs_error_pct": None,
                    "over_delivery_rate": None}
        mid = ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2
        return {
            "n": n,
            "success_rate": round(sum(1 for r in ratios if r >= 0.8) / n, 3),
            "mean_accuracy": round(sum(ratios) / n, 3),
            "median_accuracy": round(mid, 3),
            "mean_abs_error_pct": round(sum(errors) / len(errors), 1) if errors else None,
            "over_delivery_rate": round(sum(1 for r in ratios if r > 1.0) / n, 3),
        }

    def calibration_summary_text(self, lever_type: str, node_id: Optional[str] = None) -> str:
        """Human/LLM-readable calibration summary for prompt context."""
        c = self.calibration(lever_type=lever_type, node_id=node_id)
        if c["n"] == 0:
            return f"No prior history for lever '{lever_type}'. Assume neutral confidence (0.5) and moderate risk."
        lines = [
            f"Historical outcomes for lever '{lever_type}'" +
            (f" on node {node_id}" if node_id else "") + ":",
            f"  - {c['n']} measured initiatives",
            f"  - success rate (>=80% of prediction): {c['success_rate']*100:.0f}%",
            f"  - mean actual/predicted ratio: {c['mean_accuracy']:.2f}x",
            f"  - median accuracy ratio: {c['median_accuracy']:.2f}x",
            f"  - mean absolute error: {c['mean_abs_error_pct']:.0f}%",
            f"  - over-delivery rate: {c['over_delivery_rate']*100:.0f}%",
        ]
        if c["mean_accuracy"] < 0.7:
            lines.append("  - NOTE: this lever has historically under-delivered. Discount expected impact and raise risk.")
        elif c["mean_accuracy"] > 1.2:
            lines.append("  - NOTE: this lever has historically over-delivered. You may be under-estimating impact.")
        return "\n".join(lines)

    def recent_lessons(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent measured initiatives as compact lessons."""
        rows = self._conn.execute(
            """SELECT title, lever_type, predicted_impact_gbp, actual_impact_gbp,
                      accuracy_ratio, notes_json, measured_at
               FROM initiatives WHERE status='measured'
               ORDER BY measured_at DESC LIMIT ?""", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "title": r["title"],
                "lever_type": r["lever_type"],
                "predicted_gbp": r["predicted_impact_gbp"],
                "actual_gbp": r["actual_impact_gbp"],
                "accuracy": r["accuracy_ratio"],
                "notes": json.loads(r["notes_json"] or "[]"),
                "measured_at": r["measured_at"],
            })
        return out

    def lessons_text(self, limit: int = 8) -> str:
        lessons = self.recent_lessons(limit)
        if not lessons:
            return "No measured initiatives yet — this is the first cycle."
        lines = ["Recent initiative outcomes (predicted vs actual):"]
        for l in lessons:
            lines.append(
                f"  - {l['title']} [{l['lever_type']}]: predicted £{l['predicted_gbp']:,.0f} → "
                f"actual £{l['actual_gbp']:,.0f} ({l['accuracy']:.2f}x)"
            )
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _row_to_initiative(self, row: sqlite3.Row) -> Initiative:
        return Initiative(
            id=row["id"],
            hypothesis_id=row["hypothesis_id"] or "",
            agent_id=row["agent_id"] or "",
            node_id=row["node_id"] or "",
            node_label=row["node_label"] or "",
            title=row["title"] or "",
            description=row["description"] or "",
            lever_type=LeverType(row["lever_type"]) if row["lever_type"] else LeverType.OTHER,
            status=InitiativeStatus(row["status"]) if row["status"] else InitiativeStatus.PROPOSED,
            predicted_impact_gbp=row["predicted_impact_gbp"] or 0.0,
            actual_impact_gbp=row["actual_impact_gbp"],
            created_at=row["created_at"] or "",
            approved_at=row["approved_at"],
            started_at=row["started_at"],
            measured_at=row["measured_at"],
            owner=row["owner"] or "",
            external_ref=row["external_ref"],
            notes=json.loads(row["notes_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def close(self):
        self._conn.close()
