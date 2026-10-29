"""Integration connection store.

Nango holds the actual credentials; BAM only needs to remember which Nango
connection ID belongs to which (tenant, provider) pair. That's cheap metadata,
so it lives in a small SQLite database next to the other BAM state files.

Schema:
    connections(tenant TEXT, provider TEXT, connection_id TEXT,
                integration_id TEXT, created_at TEXT, metadata TEXT,
                PRIMARY KEY (tenant, provider))
    sync_runs(id INTEGER PK, tenant, provider, field, value REAL,
              status TEXT, detail TEXT, run_at TEXT)
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_DB_PATH = os.environ.get(
    "BAM_INTEGRATIONS_DB",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "integrations.db",
    ),
)


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS connections (
                tenant        TEXT NOT NULL,
                provider      TEXT NOT NULL,
                connection_id TEXT NOT NULL,
                integration_id TEXT,
                created_at    TEXT NOT NULL,
                metadata      TEXT,
                PRIMARY KEY (tenant, provider)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_runs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant    TEXT NOT NULL,
                provider  TEXT NOT NULL,
                field     TEXT NOT NULL,
                value     REAL,
                status    TEXT NOT NULL,
                detail    TEXT,
                run_at    TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sync_tenant_field ON sync_runs(tenant, field, run_at)"
        )


@contextmanager
def _cursor():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ── connections ────────────────────────────────────────────────────────────

def save_connection(
    tenant: str,
    provider: str,
    connection_id: str,
    integration_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    init_db()
    with _cursor() as conn:
        conn.execute(
            """
            INSERT INTO connections (tenant, provider, connection_id, integration_id, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant, provider) DO UPDATE SET
                connection_id = excluded.connection_id,
                integration_id = excluded.integration_id,
                metadata = excluded.metadata
            """,
            (
                tenant, provider, connection_id, integration_id or provider,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(metadata) if metadata else None,
            ),
        )


def get_connection_id(tenant: str, provider: str) -> Optional[str]:
    init_db()
    with _cursor() as conn:
        row = conn.execute(
            "SELECT connection_id FROM connections WHERE tenant = ? AND provider = ?",
            (tenant, provider),
        ).fetchone()
        return row["connection_id"] if row else None


def list_connections(tenant: Optional[str] = None) -> List[Dict[str, Any]]:
    init_db()
    with _cursor() as conn:
        if tenant:
            rows = conn.execute(
                "SELECT * FROM connections WHERE tenant = ? ORDER BY provider", (tenant,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM connections ORDER BY tenant, provider").fetchall()
        return [dict(r) for r in rows]


def delete_connection(tenant: str, provider: str) -> bool:
    init_db()
    with _cursor() as conn:
        cur = conn.execute(
            "DELETE FROM connections WHERE tenant = ? AND provider = ?", (tenant, provider)
        )
        return cur.rowcount > 0


# ── sync runs ──────────────────────────────────────────────────────────────

def record_sync(
    tenant: str,
    provider: str,
    field: str,
    value: Optional[float],
    status: str,
    detail: Optional[str] = None,
) -> None:
    init_db()
    with _cursor() as conn:
        conn.execute(
            """
            INSERT INTO sync_runs (tenant, provider, field, value, status, detail, run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant, provider, field, value, status, detail,
             datetime.now(timezone.utc).isoformat()),
        )


def latest_syncs(tenant: str, limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    with _cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM sync_runs WHERE tenant = ? ORDER BY run_at DESC LIMIT ?",
            (tenant, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def latest_value(tenant: str, field: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _cursor() as conn:
        row = conn.execute(
            """
            SELECT * FROM sync_runs WHERE tenant = ? AND field = ? AND status = 'ok'
            ORDER BY run_at DESC LIMIT 1
            """,
            (tenant, field),
        ).fetchone()
        return dict(row) if row else None
