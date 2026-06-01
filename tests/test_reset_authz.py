"""
Regression test untuk review fix #2: /api/reset hanya boleh admin.

Sebelumnya endpoint cuma @api_login_required, jadi Mitra mana pun yang login
bisa menghapus SELURUH data semua Mitra. Dijalankan dengan auth NYATA
(TESTING=False) supaya role-gate benar-benar aktif.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import web.routes as routes
from web import create_app
from web import auth


@pytest.fixture
def env(monkeypatch):
    tmp_users = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_users.close()
    os.unlink(tmp_users.name)
    monkeypatch.setattr(auth, "_USERS_PATH", tmp_users.name)
    auth.create_user("mitraA", "passa", auth.ROLE_MITRA, name="Cabang A",
                     mitra_id="MITRA-A")
    auth.create_user("admin1", "passadmin", auth.ROLE_ADMIN, name="Admin")

    routes._storage = routes.InMemoryStorage()
    routes._storage_backend = "memory"

    app = create_app()  # TESTING tetap False -> auth & role-gate aktif
    client = app.test_client()
    yield client

    routes._storage = None
    if os.path.exists(tmp_users.name):
        os.unlink(tmp_users.name)


def _login(client, role, username, password):
    return client.post("/login", data={
        "role": role, "username": username, "password": password,
    })


class TestResetAuthz:
    def test_unauthenticated_blocked(self, env):
        r = env.post("/api/reset")
        assert r.status_code == 401

    def test_mitra_forbidden(self, env):
        _login(env, "mitra", "mitraA", "passa")
        r = env.post("/api/reset")
        assert r.status_code == 403

    def test_admin_allowed(self, env):
        _login(env, "admin", "admin1", "passadmin")
        r = env.post("/api/reset")
        assert r.status_code == 200
        assert r.get_json()["success"] is True
