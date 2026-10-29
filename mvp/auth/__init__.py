"""Authentication and tenant scoping for the BAM web app.

Open-source stack, no paid identity provider:
  * Flask-Login (BSD-3)      session management
  * werkzeug.security        scrypt/pbkdf2 password hashing (ships with Flask)
  * sqlite3                  user + membership storage

Design rule enforced here: **the tenant is never taken from user input.**
It is resolved from the authenticated session. A query-string ?tenant= is only
honoured when that tenant appears in the caller's memberships, so a logged-in
user cannot read another business's financials by editing a URL.
"""

from __future__ import annotations

import hmac
import os
import secrets
from functools import wraps
from typing import Any, Dict, Optional

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

from . import store

login_manager = LoginManager()
login_manager.login_view = "auth.login"  # type: ignore[assignment]
login_manager.session_protection = "strong"

# Endpoints reachable without a session. Everything else is guarded globally.
PUBLIC_ENDPOINTS = {"auth.login", "auth.health", "static"}

auth_bp = Blueprint(
    "auth", __name__,
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "templates"),
)


class User(UserMixin):
    """Thin adapter over the users row so Flask-Login can work with it."""

    def __init__(self, record: Dict[str, Any]):
        self.record = record
        self.id = str(record["id"])
        self.email = record["email"]
        self.display_name = record.get("display_name") or record["email"].split("@")[0]
        self.role = record.get("role", "member")
        self._tenants: Optional[list] = None

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        """Flask-Login consults this to refuse disabled accounts."""
        return bool(self.record.get("is_active", True))

    @property
    def tenants(self) -> list:
        if self._tenants is None:
            self._tenants = store.tenants_for_user(int(self.id))
        return self._tenants

    def can_access(self, tenant_id: str) -> bool:
        return tenant_id in self.tenants

    def __repr__(self) -> str:
        return f"<User {self.email}>"


@login_manager.user_loader
def _load_user(user_id: str) -> Optional[User]:
    try:
        record = store.get_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None
    return User(record) if record else None


# --- CSRF (lightweight, no extra dependency) --------------------------------

def _csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def _csrf_ok() -> bool:
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("_csrf", "")
    return bool(sent and expected and hmac.compare_digest(sent, expected))


# --- tenant resolution ------------------------------------------------------

def current_tenant(default: str = "jonco") -> str:
    """The active tenant for this request, always derived from the session.

    ``default`` only ever applies to an anonymous request. For a signed-in user
    the tenant must come from their memberships; returning a hardcoded tenant id
    here would be the original bug all over again.
    """
    if not current_user.is_authenticated:
        return default
    allowed = current_user.tenants
    if not allowed:
        # Signed in but not attached to any business: do not invent one.
        return ""
    requested = request.args.get("tenant")
    if requested and requested in allowed:
        return requested
    preferred = session.get("tenant_id")
    if preferred in allowed:
        return preferred
    return allowed[0]


def visible_tenants() -> Dict[str, Any]:
    """Tenant configs the current user is entitled to see."""
    from mvp.loader import load_tenant_config, list_tenants

    allowed = current_user.tenants if current_user.is_authenticated else []
    out: Dict[str, Any] = {}
    for tid in allowed:
        try:
            out[tid] = load_tenant_config(tid)
        except Exception:
            continue
    if not out and not current_user.is_authenticated:
        # Bootstrap only: an anonymous visitor may see the tenant registry so
        # the login page renders. A *signed-in* user with no memberships must
        # see nothing — falling back to every tenant here was a cross-tenant
        # data leak.
        for tid in list_tenants():
            try:
                out[tid] = load_tenant_config(tid)
            except Exception:
                continue
    return out


def tenant_required(view):
    """Ensure the resolved tenant is one the caller may read."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return _unauthenticated()
        if not current_user.tenants:
            return jsonify({"ok": False, "error": "no tenant assigned to this account"}), 403
        return view(*args, **kwargs)

    return wrapper


def _unauthenticated():
    if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": "authentication required"}), 401
    return redirect(url_for("auth.login", next=request.full_path))


# --- routes -----------------------------------------------------------------

@auth_bp.route("/health")
def health():
    """Unauthenticated liveness probe — deliberately leaks nothing."""
    return jsonify({"ok": True, "service": "bam-auth"})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    nxt = request.args.get("next") or request.form.get("next") or ""
    # Reject absolute URLs so ?next= cannot be used as an open redirect.
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = ""

    if request.method == "POST":
        if not _csrf_ok():
            flash("Session expired, please try again.", "error")
            return render_template("login.html", next=nxt, csrf=_csrf_token()), 400
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        try:
            record = store.verify_password(email, password, ip=ip)
        except PermissionError as exc:
            store.audit("login_throttled", {"email": email}, str(exc), ip)
            flash(str(exc), "error")
            return render_template("login.html", next=nxt, csrf=_csrf_token()), 429
        if not record:
            store.audit("login_failed", {"email": email}, "invalid credentials", ip)
            flash("Incorrect email or password.", "error")
            return render_template("login.html", next=nxt, csrf=_csrf_token()), 401

        user = User(record)
        login_user(user, remember=False)
        store.record_login(int(user.id))
        session["tenant_id"] = user.tenants[0] if user.tenants else None
        store.audit("login_success", user, "", ip)
        return redirect(nxt or url_for("index"))

    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html", next=nxt, csrf=_csrf_token())


@auth_bp.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    store.audit("logout", {"id": current_user.id, "email": current_user.email}, "", ip)
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/switch-tenant/<tenant_id>", methods=["POST"])
@login_required
def switch_tenant(tenant_id: str):
    if not current_user.can_access(tenant_id):
        return jsonify({"ok": False, "error": "not a member of that business"}), 403
    session["tenant_id"] = tenant_id
    return jsonify({"ok": True, "tenant": tenant_id})


@auth_bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    """Rotate the signed-in user's own password."""
    if request.method == "POST":
        if not _csrf_ok():
            flash("Session expired, please try again.", "error")
            return render_template("change_password.html", csrf=_csrf_token()), 400
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not store.verify_user_password(int(current_user.id), current):
            flash("Current password is incorrect.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        elif len(new) < 12:
            flash("New password must be at least 12 characters.", "error")
        else:
            store.set_password(int(current_user.id), new)
            store.audit("password_changed", current_user, "", request.remote_addr or "")
            flash("Password updated.", "message")
            return redirect(url_for("index"))
        return render_template("change_password.html", csrf=_csrf_token()), 400
    return render_template("change_password.html", csrf=_csrf_token())


# --- app wiring -------------------------------------------------------------

def init_app(app) -> None:
    """Attach auth to a Flask app. Call once at startup."""
    app.secret_key = _resolve_secret_key(app)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 60 * 60 * 12)
    # Secure cookies require HTTPS; the dev server is plain HTTP, so this is
    # opt-in via env until TLS terminates in front of the app.
    app.config.setdefault("SESSION_COOKIE_SECURE", os.environ.get("BAM_COOKIE_SECURE") == "1")

    store.init_db()
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)

    @app.before_request
    def _guard():  # noqa: ANN202
        if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
            return None
        if request.path.startswith("/static/"):
            return None
        if not current_user.is_authenticated:
            return _unauthenticated()
        return None

    @app.context_processor
    def _inject_user():  # noqa: ANN202
        if not current_user.is_authenticated:
            return {"auth_user": None}
        return {
            "auth_user": {
                "email": current_user.email,
                "display_name": current_user.display_name,
                "role": current_user.role,
                "tenants": current_user.tenants,
            }
        }


def _resolve_secret_key(app) -> str:
    """Persist a generated secret key so sessions survive restarts."""
    key = os.environ.get("BAM_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if key:
        return key
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "data", ".secret_key")
    try:
        with open(path) as fh:
            existing = fh.read().strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    new_key = secrets.token_urlsafe(48)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(new_key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return new_key


__all__ = [
    "init_app",
    "current_tenant",
    "visible_tenants",
    "tenant_required",
    "login_required",
    "store",
    "User",
]
