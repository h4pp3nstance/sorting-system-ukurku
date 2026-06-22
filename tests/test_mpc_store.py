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


class TestFormDraft:
    def setup_method(self):
        self._path = _use_temp_store()

    def teardown_method(self):
        if os.path.exists(self._path):
            os.unlink(self._path)

    def _party(self, nama="Budi", telepon="08123", alamat="Jl Mawar"):
        return {"nama": nama, "telepon": telepon, "alamat": alamat}

    def test_set_and_get_draft(self):
        draft = store.set_form_draft(
            "MITRA-001",
            sender=self._party("Budi"),
            recipient=self._party("Sari"),
        )
        assert draft is not None
        assert draft["sender"]["nama"] == "Budi"
        assert draft["recipient"]["nama"] == "Sari"
        got = store.get_form_draft("MITRA-001")
        assert got is not None
        assert got["sender"]["nama"] == "Budi"

    def test_set_draft_scoped_per_mitra(self):
        store.set_form_draft("MITRA-001", sender=self._party("A"))
        store.set_form_draft("MITRA-002", sender=self._party("B"))
        a = store.get_form_draft("MITRA-001")
        b = store.get_form_draft("MITRA-002")
        assert a["sender"]["nama"] == "A"
        assert b["sender"]["nama"] == "B"

    def test_set_empty_payload_clears_draft(self):
        store.set_form_draft("MITRA-001", sender=self._party("Budi"))
        store.set_form_draft("MITRA-001", sender=None, recipient=None)
        assert store.get_form_draft("MITRA-001") is None

    def test_set_blank_strings_treated_as_none(self):
        empty = {"nama": "  ", "telepon": "", "alamat": ""}
        result = store.set_form_draft(
            "MITRA-001",
            sender=empty,
            recipient=empty,
        )
        assert result is None
        assert store.get_form_draft("MITRA-001") is None

    def test_set_strips_whitespace(self):
        store.set_form_draft(
            "MITRA-001",
            sender={"nama": "  Budi  ", "telepon": " 08123 ", "alamat": ""},
        )
        draft = store.get_form_draft("MITRA-001")
        assert draft["sender"]["nama"] == "Budi"
        assert draft["sender"]["telepon"] == "08123"
        assert draft["sender"]["alamat"] == ""

    def test_consume_returns_and_clears(self):
        store.set_form_draft(
            "MITRA-001",
            sender=self._party("Budi"),
            recipient=self._party("Sari"),
        )
        consumed = store.consume_form_draft("MITRA-001")
        assert consumed is not None
        assert consumed["sender"]["nama"] == "Budi"
        assert consumed["recipient"]["nama"] == "Sari"
        assert store.get_form_draft("MITRA-001") is None

    def test_consume_missing_returns_none(self):
        assert store.consume_form_draft("MITRA-001") is None

    def test_consume_does_not_affect_other_mitra(self):
        store.set_form_draft("MITRA-001", sender=self._party("A"))
        store.set_form_draft("MITRA-002", sender=self._party("B"))
        store.consume_form_draft("MITRA-001")
        assert store.get_form_draft("MITRA-001") is None
        b = store.get_form_draft("MITRA-002")
        assert b is not None and b["sender"]["nama"] == "B"

    def test_clear_form_draft(self):
        store.set_form_draft("MITRA-001", sender=self._party("Budi"))
        removed = store.clear_form_draft("MITRA-001")
        assert removed is not None
        assert store.get_form_draft("MITRA-001") is None

    def test_expired_draft_auto_cleared_on_get(self):
        store.set_form_draft(
            "MITRA-001",
            sender=self._party("Budi"),
            ttl_seconds=1,
        )
        import time
        time.sleep(1.1)
        assert store.get_form_draft("MITRA-001") is None

    def test_expired_draft_not_consumed(self):
        store.set_form_draft(
            "MITRA-001",
            sender=self._party("Budi"),
            ttl_seconds=1,
        )
        import time
        time.sleep(1.1)
        assert store.consume_form_draft("MITRA-001") is None

    def test_draft_survives_reload(self):
        store.set_form_draft(
            "MITRA-001",
            sender=self._party("Budi"),
            recipient=self._party("Sari"),
        )
        store._loaded[0] = False
        store._form_drafts.clear()
        got = store.get_form_draft("MITRA-001")
        assert got is not None
        assert got["sender"]["nama"] == "Budi"
        assert got["recipient"]["nama"] == "Sari"

    def test_none_mitra_id_safe(self):
        assert store.set_form_draft(None, sender=self._party("X")) is None
        assert store.get_form_draft(None) is None
        assert store.consume_form_draft(None) is None
        assert store.clear_form_draft(None) is None

    def test_reset_clears_drafts(self):
        store.set_form_draft("MITRA-001", sender=self._party("Budi"))
        store.reset()
        assert store.get_form_draft("MITRA-001") is None
