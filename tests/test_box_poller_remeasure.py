"""Test integrasi: box_poller._handle_mpc_remeasure ambil alih measurement
saat armed state aktif (tidak save_package, tapi compare + add_validation_attempt).
"""
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def fresh_store(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    config_dir = os.path.join(tmpdir, "config")
    os.makedirs(config_dir, exist_ok=True)
    from web import mpc_store
    monkeypatch.setattr(mpc_store, "_DATA_PATH",
                        os.path.join(config_dir, "mpc_data.json"))
    mpc_store._validations.clear()
    mpc_store._attempts.clear()
    mpc_store._notifications.clear()
    mpc_store._notif_counter[0] = 0
    mpc_store._armed[0] = None
    mpc_store._loaded[0] = True
    yield mpc_store
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def fake_storage():
    class FakeStorage:
        def __init__(self):
            self._db = {}
        def add(self, pkg):
            self._db[str(pkg["id"])] = pkg
        def get_package(self, pid):
            return self._db.get(str(pid))
        def get_all_packages(self, n=100):
            return list(self._db.values())[:n]
        def save_package(self, data):
            new_id = str(len(self._db) + 1000)
            self._db[new_id] = dict(data, id=new_id)
            return new_id
    return FakeStorage()


def _make_mapped(panjang, lebar, tinggi, chargeable, aktual=None):
    return {
        "panjang": panjang,
        "lebar": lebar,
        "tinggi": tinggi,
        "berat_aktual": aktual if aktual is not None else chargeable,
        "berat_volumetrik": chargeable,
        "chargeable_weight": chargeable,
        "chargeable_source": "volumetric",
        "timestamp": "2026-06-23 12:00:00",
        "detection_image": None,
    }


def test_handler_returns_false_when_no_arm(fresh_store, fake_storage):
    from web import box_poller
    events = []
    result = box_poller._handle_mpc_remeasure(
        fake_storage, "mid_1", _make_mapped(10, 10, 10, 100),
        lambda name, data: events.append((name, data)))
    assert result is False
    assert events == []


def test_handler_consumes_armed_and_validates(fresh_store, fake_storage):
    from web import box_poller
    fake_storage.add({
        "id": "500",
        "mitra_id": "MITRA-001",
        "mitra_name": "Mitra A",
        "dimensions": {"panjang": 10, "lebar": 10, "tinggi": 10},
        "weight": {"aktual": 100, "volumetrik": 100, "chargeable": 100,
                   "source": "volumetric"},
    })
    fresh_store.arm_mpc("500", armed_by="mpc_user")

    events = []
    result = box_poller._handle_mpc_remeasure(
        fake_storage, "mid_2", _make_mapped(10.05, 10.0, 10.0, 100.5),
        lambda name, data: events.append((name, data)))

    assert result is True
    assert fresh_store.get_armed() is None
    attempts = fresh_store.list_attempts("500")
    assert len(attempts) == 1
    assert attempts[0]["status"] in ("valid", "perlu_review", "tidak_sesuai")
    assert attempts[0]["data_source"] == "mpc_pb_remeasure"

    names = [e[0] for e in events]
    assert "mpc_validated" in names


def test_handler_creates_notification_when_not_valid(fresh_store, fake_storage):
    from web import box_poller
    fake_storage.add({
        "id": "500",
        "mitra_id": "MITRA-001",
        "dimensions": {"panjang": 10, "lebar": 10, "tinggi": 10},
        "weight": {"aktual": 100, "volumetrik": 100, "chargeable": 100,
                   "source": "volumetric"},
    })
    fresh_store.arm_mpc("500", armed_by="mpc_user")

    events = []
    box_poller._handle_mpc_remeasure(
        fake_storage, "mid_3", _make_mapped(15, 15, 15, 500),
        lambda name, data: events.append((name, data)))

    attempts = fresh_store.list_attempts("500")
    assert attempts[0]["status"] == "tidak_sesuai"
    notifs = fresh_store.list_notifications(to_mitra_id="MITRA-001")
    assert len(notifs) == 1
    assert "MPC" in notifs[0]["title"] or "Validasi" in notifs[0]["title"]


def test_handler_sends_success_notification_when_valid(fresh_store, fake_storage):
    """Mitra sekarang menerima notif untuk SEMUA 3 status (valid/perlu_review/
    tidak_sesuai) supaya tahu hasil validasi tiap paketnya."""
    from web import box_poller
    fake_storage.add({
        "id": "500",
        "mitra_id": "MITRA-001",
        "dimensions": {"panjang": 10, "lebar": 10, "tinggi": 10},
        "weight": {"aktual": 100, "volumetrik": 100, "chargeable": 100,
                   "source": "volumetric"},
    })
    fresh_store.arm_mpc("500", armed_by="mpc_user")

    events = []
    box_poller._handle_mpc_remeasure(
        fake_storage, "mid_4", _make_mapped(10.0, 10.0, 10.0, 100.0),
        lambda name, data: events.append((name, data)))

    attempts = fresh_store.list_attempts("500")
    assert attempts[0]["status"] == "valid"
    notifs = fresh_store.list_notifications(to_mitra_id="MITRA-001")
    assert len(notifs) == 1
    assert notifs[0]["status"] == "valid"
    assert "Sesuai" in notifs[0]["title"]


def test_handler_handles_missing_original_package(fresh_store, fake_storage):
    from web import box_poller
    fresh_store.arm_mpc("999", armed_by="mpc_user")

    events = []
    result = box_poller._handle_mpc_remeasure(
        fake_storage, "mid_5", _make_mapped(10, 10, 10, 100),
        lambda name, data: events.append((name, data)))
    assert result is True
    assert fresh_store.get_armed() is None
    names = [e[0] for e in events]
    assert "mpc_arm_failed" in names


def test_handler_idempotent_same_armed_consumed_only_once(fresh_store, fake_storage):
    from web import box_poller
    fake_storage.add({
        "id": "500",
        "mitra_id": "MITRA-001",
        "dimensions": {"panjang": 10, "lebar": 10, "tinggi": 10},
        "weight": {"aktual": 100, "volumetrik": 100, "chargeable": 100,
                   "source": "volumetric"},
    })
    fresh_store.arm_mpc("500", armed_by="mpc_user")
    events = []
    cb = lambda name, data: events.append((name, data))

    first = box_poller._handle_mpc_remeasure(fake_storage, "mid_6",
                                              _make_mapped(10, 10, 10, 100), cb)
    second = box_poller._handle_mpc_remeasure(fake_storage, "mid_7",
                                               _make_mapped(10, 10, 10, 100), cb)
    assert first is True
    assert second is False


# =============================================================================
# Form draft integration: box_poller._ingest_once() merge sender/recipient
# dari draft yang disimpan dashboard auto-save sebelum PB ON.
# =============================================================================

@pytest.fixture
def patched_ingest(fresh_store, fake_storage, monkeypatch):
    """Patch dependencies _ingest_once() supaya bisa di-test tanpa file IO."""
    from web import box_poller, routes

    class _SysStatus(dict):
        pass

    system_status = {"last_package": None, "total_today": {"reguler": 0, "express": 0}}

    raw_holder = [None]

    def fake_read_raw(_path):
        return raw_holder[0]

    monkeypatch.setattr(box_poller, "_read_raw", fake_read_raw)
    monkeypatch.setattr(box_poller, "_box_source_path", lambda: "/fake")
    monkeypatch.setattr(box_poller, "_box_mitra",
                        lambda: ("MITRA-001", "Mitra A"))
    monkeypatch.setattr(box_poller, "_seen_measurement_id", None,
                        raising=False)

    monkeypatch.setattr(routes, "get_storage", lambda: fake_storage)
    monkeypatch.setattr(routes, "broadcast_event",
                        lambda name, data: None)
    monkeypatch.setattr(routes, "system_status", system_status)
    monkeypatch.setattr(routes, "is_measurement_claimed", lambda mid: False)

    from web import measurement_bridge
    monkeypatch.setattr(
        measurement_bridge, "map_to_package_format",
        lambda raw: _make_mapped(
            raw.get("panjang_cm", 10),
            raw.get("lebar_cm", 10),
            raw.get("tinggi_cm", 10),
            raw.get("chargeable_weight_g", 100) / 1000.0,
        ),
    )
    monkeypatch.setattr(measurement_bridge, "classify_package",
                        lambda cw: ("reguler", 10000))

    def set_raw(measurement_id="MID_FORM_1"):
        raw_holder[0] = {
            "measurement_id": measurement_id,
            "panjang_cm": 10,
            "lebar_cm": 10,
            "tinggi_cm": 10,
            "chargeable_weight_g": 100,
        }

    box_poller._seen_measurement_id = None
    return {
        "box_poller": box_poller,
        "storage": fake_storage,
        "store": fresh_store,
        "set_raw": set_raw,
        "system_status": system_status,
    }


def test_ingest_merges_form_draft_into_package(patched_ingest):
    box_poller = patched_ingest["box_poller"]
    storage = patched_ingest["storage"]
    store = patched_ingest["store"]
    set_raw = patched_ingest["set_raw"]

    store.set_form_draft(
        "MITRA-001",
        sender={"nama": "Budi", "telepon": "081", "alamat": "Jl A"},
        recipient={"nama": "Sari", "telepon": "082", "alamat": "Jl B"},
    )
    set_raw("MID_FORM_1")

    box_poller._ingest_once()

    saved = list(storage._db.values())
    assert len(saved) == 1
    pkg = saved[0]
    assert pkg.get("sender") == {"nama": "Budi", "telepon": "081", "alamat": "Jl A"}
    assert pkg.get("recipient") == {"nama": "Sari", "telepon": "082", "alamat": "Jl B"}
    assert pkg.get("mitra_id") == "MITRA-001"
    assert pkg.get("data_source") == "box_tahap18"

    assert store.get_form_draft("MITRA-001") is None


def test_ingest_without_draft_keeps_legacy_behavior(patched_ingest):
    box_poller = patched_ingest["box_poller"]
    storage = patched_ingest["storage"]
    set_raw = patched_ingest["set_raw"]

    set_raw("MID_FORM_2")
    box_poller._ingest_once()

    saved = list(storage._db.values())
    assert len(saved) == 1
    pkg = saved[0]
    assert "sender" not in pkg
    assert "recipient" not in pkg
    assert pkg.get("mitra_id") == "MITRA-001"


def test_ingest_draft_only_sender_partial(patched_ingest):
    box_poller = patched_ingest["box_poller"]
    storage = patched_ingest["storage"]
    store = patched_ingest["store"]
    set_raw = patched_ingest["set_raw"]

    store.set_form_draft(
        "MITRA-001",
        sender={"nama": "Budi", "telepon": "", "alamat": ""},
        recipient=None,
    )
    set_raw("MID_FORM_3")
    box_poller._ingest_once()

    pkg = list(storage._db.values())[0]
    assert pkg.get("sender", {}).get("nama") == "Budi"
    assert "recipient" not in pkg


def test_ingest_consumes_draft_only_once(patched_ingest):
    box_poller = patched_ingest["box_poller"]
    storage = patched_ingest["storage"]
    store = patched_ingest["store"]
    set_raw = patched_ingest["set_raw"]

    store.set_form_draft(
        "MITRA-001",
        sender={"nama": "Budi"},
        recipient={"nama": "Sari"},
    )

    set_raw("MID_FIRST")
    box_poller._ingest_once()

    box_poller._seen_measurement_id = None
    set_raw("MID_SECOND")
    box_poller._ingest_once()

    saved = list(storage._db.values())
    assert len(saved) == 2
    first = saved[0]
    second = saved[1]
    assert first.get("sender", {}).get("nama") == "Budi"
    assert "sender" not in second
