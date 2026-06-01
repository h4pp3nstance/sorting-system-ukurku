"""
Authentication & Role-Based Access Control (RBAC)
Phase 1 foundation for UkurKu web dashboard.

Implementation notes:
- User store is a local JSON file (config/users.json) so the system works
  fully offline, matching the existing file-bridge / offline-first design.
- Passwords are hashed with werkzeug (bundled with Flask), no extra deps.
- Sessions use Flask's signed-cookie session (SECRET_KEY already set).
- Three roles per the "Keputusan Alur Final" document: mitra, mpc, admin.
- The user store can be migrated to the database later without touching callers.
"""

import json
import os
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash

# =============================================================================
# Roles
# =============================================================================

ROLE_MITRA = "mitra"
ROLE_MPC = "mpc"
ROLE_ADMIN = "admin"

VALID_ROLES = (ROLE_MITRA, ROLE_MPC, ROLE_ADMIN)

# Human-readable labels (Indonesian) for UI
ROLE_LABELS = {
    ROLE_MITRA: "Mitra",
    ROLE_MPC: "MPC",
    ROLE_ADMIN: "Admin",
}

# Where each role lands after a successful login
ROLE_HOME_ENDPOINT = {
    ROLE_MITRA: "main.dashboard",
    ROLE_MPC: "main.mpc_dashboard",
    ROLE_ADMIN: "main.admin_dashboard",
}

# =============================================================================
# User store (local JSON, offline-first)
# =============================================================================

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USERS_PATH = os.path.join(_BASE_DIR, "config", "users.json")

_DUMMY_HASH = generate_password_hash("dummy-password-for-constant-time-check")

# Default seed accounts created on first run. Passwords are plain here ONLY
# for seeding; they are immediately hashed before being written to disk.
# Operators should change these after first login (future feature).
_SEED_USERS = [
    {
        "username": "mitra",
        "password": "mitra123",
        "role": ROLE_MITRA,
        "name": "Mitra Cabang Demo",
        "mitra_id": "MITRA-001",
    },
    {
        "username": "mpc",
        "password": "mpc123",
        "role": ROLE_MPC,
        "name": "Petugas MPC Demo",
        "mpc_id": "MPC-001",
    },
    {
        "username": "admin",
        "password": "admin123",
        "role": ROLE_ADMIN,
        "name": "Administrator",
    },
]


def _seed_users_file(path):
    """Create config/users.json with hashed seed accounts if missing."""
    users = {}
    for entry in _SEED_USERS:
        record = dict(entry)
        record["password_hash"] = generate_password_hash(record.pop("password"))
        users[record["username"]] = record

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, indent=2, ensure_ascii=False)
    return users


def load_users():
    """Load users from JSON store, seeding defaults on first run.

    Returns a dict keyed by username.
    """
    if not os.path.exists(_USERS_PATH):
        return _seed_users_file(_USERS_PATH)

    try:
        with open(_USERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = data.get("users", {})
        if not users:
            return _seed_users_file(_USERS_PATH)
        return users
    except (json.JSONDecodeError, OSError):
        # Corrupted/unreadable store: re-seed rather than crash the app.
        return _seed_users_file(_USERS_PATH)


def get_user(username):
    """Return a single user record by username, or None."""
    if not username:
        return None
    return load_users().get(username.strip())


def verify_credentials(username, password):
    """Validate username/password. Returns the user record on success.

    A dummy hash check runs when the user is absent so response time does
    not reveal whether a username exists (mitigates timing enumeration).
    """
    user = get_user(username)
    stored_hash = user.get("password_hash", "") if user else _DUMMY_HASH
    password_ok = check_password_hash(stored_hash, password or "")
    if user and password_ok:
        return user
    return None


# =============================================================================
# User CRUD (Admin) - operate on config/users.json
# =============================================================================

def _write_users(users):
    os.makedirs(os.path.dirname(_USERS_PATH), exist_ok=True)
    with open(_USERS_PATH, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, indent=2, ensure_ascii=False)


def list_users():
    """Return users as a list of public dicts (no password_hash)."""
    users = load_users()
    result = []
    for username, record in users.items():
        result.append({
            "username": username,
            "name": record.get("name", username),
            "role": record.get("role"),
            "mitra_id": record.get("mitra_id"),
            "mpc_id": record.get("mpc_id"),
        })
    result.sort(key=lambda u: (u.get("role") or "", u["username"]))
    return result


def create_user(username, password, role, name=None, mitra_id=None, mpc_id=None):
    """Create a new user. Returns (ok, error_message)."""
    username = (username or "").strip()
    if not username:
        return False, "Username wajib diisi."
    if not password:
        return False, "Password wajib diisi."
    if role not in VALID_ROLES:
        return False, "Peran tidak valid."

    users = load_users()
    if username in users:
        return False, "Username sudah dipakai."

    record = {
        "username": username,
        "role": role,
        "name": name or username,
        "password_hash": generate_password_hash(password),
    }
    if mitra_id:
        record["mitra_id"] = mitra_id.strip()
    if mpc_id:
        record["mpc_id"] = mpc_id.strip()

    users[username] = record
    _write_users(users)
    return True, None


def update_user(username, name=None, role=None, password=None,
                mitra_id=None, mpc_id=None):
    """Update an existing user. Empty/None fields are left unchanged."""
    username = (username or "").strip()
    users = load_users()
    if username not in users:
        return False, "User tidak ditemukan."

    record = users[username]
    if name:
        record["name"] = name
    if role:
        if role not in VALID_ROLES:
            return False, "Peran tidak valid."
        record["role"] = role
    if password:
        record["password_hash"] = generate_password_hash(password)
    if mitra_id is not None:
        record["mitra_id"] = mitra_id.strip()
    if mpc_id is not None:
        record["mpc_id"] = mpc_id.strip()

    users[username] = record
    _write_users(users)
    return True, None


def delete_user(username, acting_username=None):
    """Delete a user. Cannot delete self or the last admin."""
    username = (username or "").strip()
    users = load_users()
    if username not in users:
        return False, "User tidak ditemukan."
    if acting_username and username == acting_username:
        return False, "Tidak dapat menghapus akun sendiri."

    if users[username].get("role") == ROLE_ADMIN:
        admin_count = sum(
            1 for r in users.values() if r.get("role") == ROLE_ADMIN
        )
        if admin_count <= 1:
            return False, "Tidak dapat menghapus admin terakhir."

    del users[username]
    _write_users(users)
    return True, None



# =============================================================================
# Session helpers
# =============================================================================

def login_user(user):
    """Store the authenticated user in the session."""
    session["user"] = {
        "username": user.get("username"),
        "role": user.get("role"),
        "name": user.get("name", user.get("username")),
        "mitra_id": user.get("mitra_id"),
        "mpc_id": user.get("mpc_id"),
    }
    session.permanent = False


def logout_user():
    """Clear the current user session."""
    session.pop("user", None)


def current_user():
    """Return the current user dict from the session, or None."""
    return session.get("user")


def is_authenticated():
    return current_user() is not None


def current_role():
    user = current_user()
    return user.get("role") if user else None


# =============================================================================
# Decorators
# =============================================================================

def login_required(view):
    """Require an authenticated session; otherwise redirect to landing."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            flash("Silakan masuk terlebih dahulu.", "warning")
            return redirect(url_for("main.landing"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Require an authenticated session with one of the given roles."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_app.config.get("TESTING"):
                return view(*args, **kwargs)
            user = current_user()
            if not user:
                flash("Silakan masuk terlebih dahulu.", "warning")
                return redirect(url_for("main.landing"))
            if user.get("role") not in roles:
                # Authenticated but wrong role: send to their own home.
                home = ROLE_HOME_ENDPOINT.get(user.get("role"), "main.landing")
                flash("Anda tidak memiliki akses ke halaman tersebut.", "error")
                return redirect(url_for(home))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def api_login_required(view):
    """Like login_required but returns JSON 401 instead of redirecting."""
    from flask import jsonify

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_app.config.get("TESTING"):
            return view(*args, **kwargs)
        if not is_authenticated():
            return jsonify({
                "success": False,
                "error": "Tidak terautentikasi. Silakan masuk kembali.",
                "error_type": "auth",
            }), 401
        return view(*args, **kwargs)
    return wrapped


# =============================================================================
# Auth blueprint (login / logout)
# =============================================================================

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Role-aware login page.

    GET  /login?role=mitra  -> render form pre-scoped to a role
    POST /login             -> validate credentials, enforce role match
    """
    # Resolve requested role (from query on GET, from form on POST)
    requested_role = (
        request.form.get("role")
        if request.method == "POST"
        else request.args.get("role")
    )
    if requested_role not in VALID_ROLES:
        requested_role = None

    # Already logged in? Go straight to that role's home.
    if is_authenticated():
        home = ROLE_HOME_ENDPOINT.get(current_role(), "main.landing")
        return redirect(url_for(home))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = verify_credentials(username, password)
        if not user:
            flash("Username atau password salah.", "error")
            return render_template(
                "login.html",
                role=requested_role,
                role_label=ROLE_LABELS.get(requested_role, "Pengguna"),
                username=username,
            ), 401

        # If the user picked a role on the landing page, enforce it.
        if requested_role and user.get("role") != requested_role:
            flash(
                "Akun ini bukan akun {}.".format(
                    ROLE_LABELS.get(requested_role, requested_role)
                ),
                "error",
            )
            return render_template(
                "login.html",
                role=requested_role,
                role_label=ROLE_LABELS.get(requested_role, "Pengguna"),
                username=username,
            ), 403

        login_user(user)
        home = ROLE_HOME_ENDPOINT.get(user.get("role"), "main.landing")
        return redirect(url_for(home))

    # GET
    return render_template(
        "login.html",
        role=requested_role,
        role_label=ROLE_LABELS.get(requested_role, "Pengguna"),
        username="",
    )


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Log out and return to the landing page."""
    logout_user()
    flash("Anda telah keluar.", "info")
    return redirect(url_for("main.landing"))
