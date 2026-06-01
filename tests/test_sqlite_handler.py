"""
Unit Tests for storage/sqlite_handler.py (Fase 0 - SQLite migration)
Laptop-safe: temp-file SQLite, no hardware.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.sqlite_handler import SQLiteHandler


def _pkg(**overrides):
    pkg = {
        "dimensions": {"panjang": 10.1, "lebar": 8.2, "tinggi": 5.0},
        "weight": {"aktual": 500, "volumetrik": 167, "chargeable": 500},
        "service_type": "REGULER",
        "price": 6000,
        "mitra_id": "MITRA-001",
        "mitra_name": "Cabang Demo",
        "sender": {"nama": "Budi", "telepon": "0811", "alamat": "Jl. A"},
        "recipient": {"nama": "Siti", "telepon": "0822", "alamat": "Jl. B"},
        "measurement_id": "integrated_x",
        "detection_image": "hasil/det.jpg",
    }
    pkg.update(overrides)
    return pkg


class TestSQLiteHandler:
    def setup_method(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        os.unlink(self._tmp.name)
        self.h = SQLiteHandler(db_path=self._tmp.name)
        self.h.connect()

    def teardown_method(self):
        for suffix in ("", "-wal", "-shm"):
            p = self._tmp.name + suffix
            if os.path.exists(p):
                os.unlink(p)

    def test_save_returns_string_id(self):
        pid = self.h.save_package(_pkg())
        assert isinstance(pid, str)

    def test_save_then_get_roundtrip(self):
        pid = self.h.save_package(_pkg())
        got = self.h.get_package(pid)
        assert got is not None
        assert got["id"] == pid
        assert got["service_type"] == "REGULER"

    def test_lossless_nested_fields(self):
        pid = self.h.save_package(_pkg())
        got = self.h.get_package(pid)
        assert got["dimensions"]["panjang"] == 10.1
        assert got["weight"]["chargeable"] == 500
        assert got["sender"]["nama"] == "Budi"
        assert got["recipient"]["nama"] == "Siti"
        assert got["mitra_id"] == "MITRA-001"
        assert got["measurement_id"] == "integrated_x"
        assert got["detection_image"] == "hasil/det.jpg"

    def test_get_missing_returns_none(self):
        assert self.h.get_package("999") is None

    def test_get_all_newest_first(self):
        a = self.h.save_package(_pkg(service_type="REGULER"))
        b = self.h.save_package(_pkg(service_type="EXPRESS"))
        allp = self.h.get_all_packages()
        assert allp[0]["id"] == b
        assert allp[1]["id"] == a

    def test_get_all_limit(self):
        for _ in range(5):
            self.h.save_package(_pkg())
        assert len(self.h.get_all_packages(limit=3)) == 3

    def test_statistics_aggregate(self):
        self.h.save_package(_pkg(service_type="REGULER", price=6000))
        self.h.save_package(_pkg(service_type="EXPRESS", price=12000))
        self.h.save_package(_pkg(service_type="EXPRESS", price=12000))
        stats = self.h.get_statistics()
        assert stats["total_packages"] == 3
        assert stats["total_revenue"] == 30000
        assert stats["by_service_type"]["EXPRESS"]["count"] == 2
        assert stats["by_service_type"]["EXPRESS"]["revenue"] == 24000
        assert stats["by_service_type"]["REGULER"]["count"] == 1

    def test_unique_ids(self):
        ids = {self.h.save_package(_pkg()) for _ in range(5)}
        assert len(ids) == 5

    def test_reset_clears(self):
        self.h.save_package(_pkg())
        self.h.reset_data()
        assert self.h.get_all_packages() == []
        assert self.h.get_statistics()["total_packages"] == 0

    def test_update_statistics_noop_true(self):
        assert self.h.update_statistics(_pkg()) is True

    def test_persists_across_handler_reopen(self):
        pid = self.h.save_package(_pkg())
        # Simulate restart: new handler, same db file
        h2 = SQLiteHandler(db_path=self._tmp.name)
        h2.connect()
        assert h2.get_package(pid) is not None

    def test_preserves_explicit_timestamp(self):
        pid = self.h.save_package(_pkg(timestamp="2026-05-31T10:00:00"))
        assert self.h.get_package(pid)["timestamp"] == "2026-05-31T10:00:00"
