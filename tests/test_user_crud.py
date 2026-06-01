"""
Unit Tests for user CRUD helpers in web/auth.py (Fitur B - Admin)
Laptop-safe: redirect user store to a temp file, no hardware.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import auth


class TestUserCrud:
    def setup_method(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        os.unlink(self._tmp.name)
        self._orig = auth._USERS_PATH
        auth._USERS_PATH = self._tmp.name
        auth.load_users()  # seed defaults (mitra/mpc/admin)

    def teardown_method(self):
        auth._USERS_PATH = self._orig
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_seed_has_three_roles(self):
        users = auth.list_users()
        roles = {u["role"] for u in users}
        assert roles == {"mitra", "mpc", "admin"}

    def test_list_users_excludes_password_hash(self):
        for u in auth.list_users():
            assert "password_hash" not in u

    def test_create_user_ok(self):
        ok, err = auth.create_user("mitra2", "pw123", "mitra", name="Cabang 2",
                                   mitra_id="MITRA-002")
        assert ok and err is None
        assert auth.get_user("mitra2") is not None

    def test_create_duplicate_rejected(self):
        ok, err = auth.create_user("mitra", "x", "mitra")
        assert not ok
        assert "sudah dipakai" in err

    def test_create_invalid_role_rejected(self):
        ok, err = auth.create_user("x", "pw", "superadmin")
        assert not ok

    def test_create_requires_username_and_password(self):
        assert not auth.create_user("", "pw", "mitra")[0]
        assert not auth.create_user("u", "", "mitra")[0]

    def test_created_user_can_login(self):
        auth.create_user("mpc2", "rahasia", "mpc", mpc_id="MPC-002")
        assert auth.verify_credentials("mpc2", "rahasia") is not None
        assert auth.verify_credentials("mpc2", "salah") is None

    def test_update_user_name_and_password(self):
        auth.update_user("mitra", name="Nama Baru", password="passbaru")
        assert auth.get_user("mitra")["name"] == "Nama Baru"
        assert auth.verify_credentials("mitra", "passbaru") is not None

    def test_update_missing_user(self):
        ok, err = auth.update_user("ghost", name="x")
        assert not ok

    def test_delete_user_ok(self):
        auth.create_user("temp", "pw", "mitra")
        ok, err = auth.delete_user("temp")
        assert ok
        assert auth.get_user("temp") is None

    def test_cannot_delete_self(self):
        ok, err = auth.delete_user("admin", acting_username="admin")
        assert not ok
        assert "sendiri" in err

    def test_cannot_delete_last_admin(self):
        ok, err = auth.delete_user("admin")
        assert not ok
        assert "admin terakhir" in err

    def test_can_delete_admin_when_another_exists(self):
        auth.create_user("admin2", "pw", "admin")
        ok, err = auth.delete_user("admin")
        assert ok
