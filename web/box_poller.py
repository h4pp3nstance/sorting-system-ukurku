"""
Box Result Poller - jembatan hasil pengukuran tombol fisik (tahap18) ke web.

tahap18 menulis hasil_tahap18/latest_integrated_chargeable.json tiap
pengukuran sukses (dipicu PB ON di box). Poller ini membaca file itu di
thread background; saat measurement_id BARU muncul -> map -> klasifikasi ->
simpan ke storage -> broadcast SSE, sehingga paket hasil box tampil di
dashboard + riwayat. Dedup via measurement_id.

Web-only: TIDAK mengubah tahap18. Paket box diatribusikan ke BOX_MITRA_ID
(default MITRA-001) karena box beroperasi tanpa sesi login mitra.
"""

import json
import os
import threading
import time

_INTERVAL = 3.0
_seen_measurement_id = None
_started = False
_lock = threading.Lock()


def _box_source_path():
    from config.settings import PROGRAM_PYTHON_BASE
    if not PROGRAM_PYTHON_BASE:
        return ""
    return os.path.join(PROGRAM_PYTHON_BASE, "hasil_tahap18",
                        "latest_integrated_chargeable.json")


def _box_mitra():
    mitra_id = os.getenv("BOX_MITRA_ID", "MITRA-001")
    name = None
    try:
        from web.auth import list_users
        for u in list_users():
            if u.get("mitra_id") == mitra_id:
                name = u.get("name")
                break
    except Exception:
        pass
    return mitra_id, name


def _read_raw(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _already_saved(storage, measurement_id):
    try:
        for p in storage.get_all_packages(200):
            if p.get("measurement_id") == measurement_id:
                return True
    except Exception:
        pass
    return False


def _ingest_once():
    global _seen_measurement_id

    raw = _read_raw(_box_source_path())
    if not raw:
        return
    mid = raw.get("measurement_id")
    if not mid or mid == _seen_measurement_id:
        return

    from web.measurement_bridge import map_to_package_format, classify_package
    from web.routes import get_storage, broadcast_event, system_status

    try:
        mapped = map_to_package_format(raw)
    except Exception:
        _seen_measurement_id = mid  # data tak valid, jangan ulang
        return

    storage = get_storage()
    if _already_saved(storage, mid):
        _seen_measurement_id = mid
        return

    service_type, price = classify_package(mapped["chargeable_weight"])
    mitra_id, mitra_name = _box_mitra()

    package_data = {
        "dimensions": {"panjang": mapped["panjang"], "lebar": mapped["lebar"],
                       "tinggi": mapped["tinggi"]},
        "weight": {"aktual": mapped["berat_aktual"],
                   "volumetrik": mapped["berat_volumetrik"],
                   "chargeable": mapped["chargeable_weight"],
                   "source": mapped["chargeable_source"]},
        "measurement_id": mid,
        "service_type": service_type,
        "price": price,
        "data_source": "box_tahap18",
        "mitra_id": mitra_id,
        "mitra_name": mitra_name,
    }

    package_id = storage.save_package(package_data)
    package = {"id": package_id, "timestamp": mapped["timestamp"], **package_data}

    system_status["last_package"] = package
    if service_type in system_status["total_today"]:
        system_status["total_today"][service_type] += 1

    broadcast_event("package_added", {
        "package": package,
        "statistics": {
            "total_today": sum(system_status["total_today"].values()),
            "by_type": dict(system_status["total_today"]),
        },
    })
    _seen_measurement_id = mid


def _loop():
    while True:
        try:
            _ingest_once()
        except Exception:
            pass
        time.sleep(_INTERVAL)


def start_box_poller():
    """Mulai poller (idempotent). Dedup via _already_saved (storage), bukan suppression startup, supaya pengukuran terakhir tetap tampil setelah restart service."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_loop, name="box-poller", daemon=True).start()
