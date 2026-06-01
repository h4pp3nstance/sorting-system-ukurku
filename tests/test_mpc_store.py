"""
Unit Tests for web/mpc_store.py (Fitur C - validations + notifications)
Laptop-safe: persistent JSON store redirected to a temp file.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import mpc_store as store


def _use_temp_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    store._DATA_PATH = tmp.name
    store._loaded[0] = False
    store.reset()
    return tmp.name


class TestValidations:
    def setup_method(self):
        self._path = _use_temp_store()

    def teardown_method(self):
        if os.path.exists(self._path):
            os.unlink(self._path)

    def _result(self, status="valid"):
        return {
            "status": status,
            "status_label": status.replace("_", " ").title(),
            "selisih": {"panjang": 0.1},
            "breaches": [] if status == "valid" else ["chargeable_weight"],
        }

    def test_save_and_get(self):
        store.save_validation("PKG1", {"panjang": 10}, self._result("valid"),
                              mpc_username="mpc")
        v = store.get_validation("PKG1")
        assert v is not None
        assert v["status"] == "valid"
        assert v["mpc_username"] == "mpc"

    def test_save_overwrites_same_package(self):
        store.save_validation("PKG1", {}, self._result("valid"))
        store.save_validation("PKG1", {}, self._result("tidak_sesuai"))
        assert store.get_validation("PKG1")["status"] == "tidak_sesuai"
        assert len(store.list_validations()) == 1

    def test_list_validations(self):
        store.save_validation("A", {}, self._result("valid"))
        store.save_validation("B", {}, self._result("perlu_review"))
        assert len(store.list_validations()) == 2

    def test_validation_stats(self):
        store.save_validation("A", {}, self._result("valid"))
        store.save_validation("B", {}, self._result("tidak_sesuai"))
        store.save_validation("C", {}, self._result("tidak_sesuai"))
        stats = store.validation_stats()
        assert stats["valid"] == 1
        assert stats["tidak_sesuai"] == 2
        assert stats["total"] == 3

    def test_get_missing_returns_none(self):
        assert store.get_validation("ghost") is None


class TestNotifications:
    def setup_method(self):
        self._path = _use_temp_store()

    def teardown_method(self):
        if os.path.exists(self._path):
            os.unlink(self._path)

    def test_create_and_list(self):
        store.create_notification("PKG1", "MITRA-001", "Peringatan",
                                  "Tidak sesuai", status="tidak_sesuai")
        notifs = store.list_notifications()
        assert len(notifs) == 1
        assert notifs[0]["to_mitra_id"] == "MITRA-001"
        assert notifs[0]["is_read"] is False

    def test_filter_by_mitra(self):
        store.create_notification("A", "MITRA-001", "t", "m")
        store.create_notification("B", "MITRA-002", "t", "m")
        assert len(store.list_notifications(to_mitra_id="MITRA-001")) == 1

    def test_unread_filter_and_count(self):
        n1 = store.create_notification("A", "MITRA-001", "t", "m")
        store.create_notification("B", "MITRA-001", "t", "m")
        assert store.unread_count("MITRA-001") == 2
        store.mark_read(n1["id"])
        assert store.unread_count("MITRA-001") == 1
        assert len(store.list_notifications(to_mitra_id="MITRA-001",
                                            unread_only=True)) == 1

    def test_mark_read_missing_returns_false(self):
        assert store.mark_read(9999) is False

    def test_incrementing_ids(self):
        a = store.create_notification("A", "M", "t", "m")
        b = store.create_notification("B", "M", "t", "m")
        assert b["id"] == a["id"] + 1

    def test_reset_clears_all(self):
        store.save_validation("A", {}, {"status": "valid"})
        store.create_notification("A", "M", "t", "m")
        store.reset()
        assert store.list_validations() == []
        assert store.list_notifications() == []


class TestPersistence:
    def setup_method(self):
        self._path = _use_temp_store()

    def teardown_method(self):
        if os.path.exists(self._path):
            os.unlink(self._path)

    def _reload(self):
        """Simulate process restart: drop in-memory state, force reload."""
        store._validations.clear()
        store._notifications.clear()
        store._notif_counter[0] = 0
        store._loaded[0] = False

    def test_validation_survives_reload(self):
        store.save_validation("PKG1", {"panjang": 10},
                              {"status": "tidak_sesuai",
                               "status_label": "Tidak Sesuai"})
        self._reload()
        v = store.get_validation("PKG1")
        assert v is not None
        assert v["status"] == "tidak_sesuai"

    def test_notification_survives_reload(self):
        store.create_notification("PKG1", "MITRA-001", "Peringatan", "pesan",
                                  status="tidak_sesuai")
        self._reload()
        notifs = store.list_notifications(to_mitra_id="MITRA-001")
        assert len(notifs) == 1
        assert notifs[0]["package_id"] == "PKG1"

    def test_counter_survives_reload(self):
        a = store.create_notification("A", "M", "t", "m")
        self._reload()
        b = store.create_notification("B", "M", "t", "m")
        assert b["id"] == a["id"] + 1

    def test_read_state_survives_reload(self):
        n = store.create_notification("A", "MITRA-001", "t", "m")
        store.mark_read(n["id"])
        self._reload()
        assert store.unread_count("MITRA-001") == 0

    def test_data_file_created(self):
        store.create_notification("A", "M", "t", "m")
        assert os.path.exists(self._path)
