"""
Regression test for cross-Mitra IDOR guard (review fix #3).

Memastikan Mitra A tidak bisa mengakses paket milik Mitra B lewat tebak ID
pada /receipt/<id>, /receipt/<id>.pdf, dan /api/history/<id>.
Dijalankan dengan auth NYATA (TESTING=False) supaya scoping benar-benar aktif.
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
    # User store sementara dengan dua Mitra berbeda cabang.
    tmp_users = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_users.close()
    os.unlink(tmp_users.name)
    monkeypatch.setattr(auth, "_USERS_PATH", tmp_users.name)
    auth.create_user("mitraA", "passa", auth.ROLE_MITRA, name="Cabang A",
                     mitra_id="MITRA-A")
    auth.create_user("mitraB", "passb", auth.ROLE_MITRA, name="Cabang B",
                     mitra_id="MITRA-B")

    # Storage in-memory; satu paket milik MITRA-B.
    routes._storage = routes.InMemoryStorage()
    routes._storage_backend = "memory"
    pkg_id = routes._storage.save_package({
        "dimensions": {"panjang": 10, "lebar": 10, "tinggi": 10},
        "weight": {"aktual": 500, "volumetrik": 167, "chargeable": 500},
        "service_type": "REGULER", "price": 6000,
        "mitra_id": "MITRA-B",
        "sender": {"nama": "Rahasia B"},
    })

    app = create_app()  # TESTING tetap False -> auth & scoping aktif
    client = app.test_client()
    yield client, pkg_id

    routes._storage = None
    for p in (tmp_users.name,):
        if os.path.exists(p):
            os.unlink(p)


def _login(client, username, password):
    return client.post("/login", data={
        "role": "mitra", "username": username, "password": password,
    })


class TestCrossMitraIDOR:
    def test_owner_can_access_own_receipt(self, env):
        client, pkg_id = env
        _login(client, "mitraB", "passb")
        assert client.get("/receipt/" + pkg_id).status_code == 200

    def test_other_mitra_blocked_from_receipt(self, env):
        client, pkg_id = env
        _login(client, "mitraA", "passa")
        # Bukan paket MITRA-A -> harus 404 (tidak bocor), bukan 200.
        r = client.get("/receipt/" + pkg_id)
        assert r.status_code == 404
        assert b"Rahasia B" not in r.data

    def test_other_mitra_blocked_from_pdf(self, env):
        client, pkg_id = env
        _login(client, "mitraA", "passa")
        r = client.get("/receipt/" + pkg_id + ".pdf")
        assert r.status_code == 404

    def test_other_mitra_blocked_from_api_detail(self, env):
        client, pkg_id = env
        _login(client, "mitraA", "passa")
        r = client.get("/api/history/" + pkg_id)
        assert r.status_code == 404

    def test_owner_can_access_api_detail(self, env):
        client, pkg_id = env
        _login(client, "mitraB", "passb")
        assert client.get("/api/history/" + pkg_id).status_code == 200
