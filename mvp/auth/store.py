"""SQLite-backed user and membership store for BAM.

Kept deliberately dependency-free (stdlib sqlite3 + werkzeug hashing) so the
auth layer works on a bare Flask install. One file, one database, no ORM.

Schema
------
users        one row per human. email is the unique identity.
memberships  many-to-many between users and tenants. A user may own or work
             across several businesses, so tenancy cannot live on the user row.
audit_log    append-only record of security-relevant events. Cheap to keep and
             the first thing you want when a customer asks "who saw my P&L?".
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

# Reuse the project's existing data directory so backups pick auth up for free.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.environ.get("BAM_AUTH_DB", os.path.join(_PROJECT_ROOT, "data", "auth.db"))

# Failed-login throttling: in-process, deliberately simple. A single gunicorn
# worker is the current deployment shape; if this scales to multiple workers the
# counters move to the database or Redis.
_FAILED: Dict[str, List[float]] = {}
MAX_ATTEMPTS = 8
WINDOW_SECONDS = 900


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                display_name  TEXT,
                role          TEXT NOT NULL DEFAULT 'member',
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL,
                last_login    TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memberships (
                user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tenant_id TEXT NOT NULL,
                role      TEXT NOT NULL DEFAULT 'owner',
                PRIMARY KEY (user_id, tenant_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email   TEXT,
                action  TEXT NOT NULL,
                detail  TEXT,
                ip      TEXT,
                at      TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_tenant ON memberships(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at)")


# --- users -----------------------------------------------------------------

def _row_to_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "display_name": row["display_name"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "last_login": row["last_login"],
    }


def create_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    role: str = "member",
    tenant_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a user. Raises ValueError on duplicate email or weak password."""
    email = (email or "").strip().lower()
    if "@" not in email or len(email) < 5:
        raise ValueError("a valid email address is required")
    if not password or len(password) < 12:
        raise ValueError("password must be at least 12 characters")

    init_db()
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, display_name, role, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (email, generate_password_hash(password), display_name, role, _now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("an account with that email already exists") from exc
        uid = cur.lastrowid
        for tid in tenant_ids or []:
            conn.execute(
                "INSERT OR IGNORE INTO memberships (user_id, tenant_id, role) VALUES (?, ?, 'owner')",
                (uid, tid),
            )
    return get_user_by_id(uid)  # type: ignore[return-value]


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", ((email or "").strip(),)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def verify_password(email: str, password: str, ip: str = "") -> Optional[Dict[str, Any]]:
    """Return the user on success, None on failure. Throttles repeated failures."""
    key = f"{(email or '').strip().lower()}|{ip}"
    now = time.time()
    hits = [t for t in _FAILED.get(key, []) if now - t < WINDOW_SECONDS]
    _FAILED[key] = hits
    if len(hits) >= MAX_ATTEMPTS:
        raise PermissionError("too many failed attempts; try again in 15 minutes")

    user = get_user_by_email(email)
    if not user or not user["is_active"]:
        _FAILED[key].append(now)
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        _FAILED[key].append(now)
        return None

    _FAILED.pop(key, None)
    return user


def verify_user_password(user_id: int, password: str) -> bool:
    """Check the password for an already-authenticated user (re-auth prompt)."""
    user = get_user_by_id(user_id)
    if not user:
        return False
    return check_password_hash(user["password_hash"], password or "")


def set_password(user_id: int, password: str) -> None:
    if not password or len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )


def record_login(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user_id))


def list_users() -> List[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_row_to_user(r) for r in rows]


# --- memberships -----------------------------------------------------------

def add_membership(user_id: int, tenant_id: str, role: str = "owner") -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO memberships (user_id, tenant_id, role) VALUES (?, ?, ?)"
            " ON CONFLICT(user_id, tenant_id) DO UPDATE SET role = excluded.role",
            (user_id, tenant_id, role),
        )


def tenants_for_user(user_id: int) -> List[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT tenant_id FROM memberships WHERE user_id = ? ORDER BY tenant_id", (user_id,)
        ).fetchall()
    return [r["tenant_id"] for r in rows]


def users_for_tenant(tenant_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT u.* FROM users u JOIN memberships m ON m.user_id = u.id"
            " WHERE m.tenant_id = ? ORDER BY u.id",
            (tenant_id,),
        ).fetchall()
    return [_row_to_user(r) for r in rows]


# --- audit -----------------------------------------------------------------

def audit(action: str, user: Optional[Dict[str, Any]] = None, detail: str = "", ip: str = "") -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (user_id, email, action, detail, ip, at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    (user or {}).get("id"),
                    (user or {}).get("email"),
                    action,
                    detail[:500],
                    ip,
                    _now(),
                ),
            )
    except Exception:
        # Auditing must never break the request path.
        pass


def recent_audit(limit: int = 100) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# --- bootstrap -------------------------------------------------------------

def ensure_admin(default_tenants: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Create the first owner account if the user table is empty.

    Credentials come from BAM_ADMIN_EMAIL / BAM_ADMIN_PASSWORD. If the password
    is absent a random one is generated and written to data/initial_admin_password.txt
    (mode 0600) so the operator can retrieve it without it appearing in logs.
    """
    init_db()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count:
        return None

    email = os.environ.get("BAM_ADMIN_EMAIL", "jon@jonco.local").strip().lower()
    password = os.environ.get("BAM_ADMIN_PASSWORD", "").strip()
    generated = False
    if not password:
        password = secrets.token_urlsafe(18)
        generated = True

    user = create_user(email, password, display_name="Jon", role="owner",
                       tenant_ids=default_tenants or [])
    if generated:
        path = os.path.join(_PROJECT_ROOT, "data", "initial_admin_password.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(f"email: {email}\npassword: {password}\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    audit("bootstrap_admin", user, f"initial owner account created ({'generated' if generated else 'env'} password)")
    return user
