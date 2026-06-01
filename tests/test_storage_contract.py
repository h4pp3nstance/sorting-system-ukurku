"""
Contract Tests: parity antara InMemoryStorage dan SQLiteHandler (Fase 1).

Membuktikan SQLiteHandler berperilaku identik dengan InMemoryStorage
(kontrak yang dipakai 333 test existing), termasuk round-trip LOSSLESS
field nested (sender/recipient/mitra_id) yang dulu hilang di FirebaseHandler.
Laptop-safe.
"""

import sys
import os
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web.routes as routes
from storage.sqlite_handler import SQLiteHandler


def _make_inmemory():
    return routes.InMemoryStorage(), None


def _make_sqlite():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    h = SQLiteHandler(db_path=tmp.name)
    h.connect()
    return h, tmp.name


def _cleanup(path):
    if not path:
        return
    for suffix in ("", "-wal", "-shm"):
        p = path + suffix
        if os.path.exists(p):
            os.unlink(p)


def _pkg(**overrides):
    pkg = {
        "dimensions": {"panjang": 10.1, "lebar": 8.2, "tinggi": 5.0},
        "weight": {"aktual": 500, "volumetrik": 167, "chargeable": 500},
        "service_type": "REGULER",
        "price": 6000,
        "mitra_id": "MITRA-001",
        "sender": {"nama": "Budi"},
        "recipient": {"nama": "Siti"},
        "measurement_id": "integrated_x",
    }
    pkg.update(overrides)
    return pkg


@pytest.fixture(params=["inmemory", "sqlite"])
def handler(request):
    if request.param == "inmemory":
        h, path = _make_inmemory()
    else:
        h, path = _make_sqlite()
    yield h
    _cleanup(path)


class TestStorageContract:
    def test_save_returns_string_id(self, handler):
        pid = handler.save_package(_pkg())
        assert isinstance(pid, str)

    def test_roundtrip_preserves_core(self, handler):
        pid = handler.save_package(_pkg())
        got = handler.get_package(pid)
        assert got is not None
        assert str(got["id"]) == pid
        assert got["service_type"] == "REGULER"
        assert got["price"] == 6000

    def test_roundtrip_lossless_nested(self, handler):
        pid = handler.save_package(_pkg())
        got = handler.get_package(pid)
        assert got["dimensions"]["panjang"] == 10.1
        assert got["weight"]["chargeable"] == 500
        assert got["sender"]["nama"] == "Budi"
        assert got["recipient"]["nama"] == "Siti"
        assert got["mitra_id"] == "MITRA-001"
        assert got["measurement_id"] == "integrated_x"

    def test_get_missing_returns_none(self, handler):
        assert handler.get_package("99999") is None

    def test_get_all_newest_first(self, handler):
        a = handler.save_package(_pkg(service_type="REGULER"))
        b = handler.save_package(_pkg(service_type="EXPRESS"))
        allp = handler.get_all_packages()
        assert str(allp[0]["id"]) == b
        assert str(allp[1]["id"]) == a

    def test_get_all_limit(self, handler):
        for _ in range(5):
            handler.save_package(_pkg())
        assert len(handler.get_all_packages(limit=3)) == 3

    def test_statistics_shape_and_values(self, handler):
        handler.save_package(_pkg(service_type="REGULER", price=6000))
        handler.save_package(_pkg(service_type="EXPRESS", price=12000))
        handler.save_package(_pkg(service_type="EXPRESS", price=12000))
        stats = handler.get_statistics()
        assert stats["total_packages"] == 3
        assert stats["total_revenue"] == 30000
        bst = stats["by_service_type"]
        assert bst["EXPRESS"]["count"] == 2
        assert bst["EXPRESS"]["revenue"] == 24000
        assert bst["REGULER"]["count"] == 1

    def test_unique_ids(self, handler):
        ids = {handler.save_package(_pkg()) for _ in range(5)}
        assert len(ids) == 5

    def test_reset_clears(self, handler):
        handler.save_package(_pkg())
        handler.reset_data()
        assert handler.get_all_packages() == []
        assert handler.get_statistics()["total_packages"] == 0


class TestFactorySqliteMode:
    def test_factory_creates_sqlite(self):
        from storage.factory import create_storage_handler
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        try:
            h = create_storage_handler("sqlite", db_path=tmp.name)
            h.connect()
            assert isinstance(h, SQLiteHandler)
            pid = h.save_package(_pkg())
            assert h.get_package(pid)["sender"]["nama"] == "Budi"
        finally:
            _cleanup(tmp.name)
