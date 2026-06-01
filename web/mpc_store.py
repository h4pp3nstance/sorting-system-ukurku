"""
MPC Store - persistent store untuk validasi & notifikasi.

State disimpan ke config/mpc_data.json (pola sama dengan users.json /
app_settings.json) supaya bertahan lintas restart. Lazy-load sekali saat
akses pertama, lalu ditulis ulang setiap mutasi.
Pure-Python, testable di laptop.

Entitas:
- validations  : hasil validasi Mitra vs MPC per paket.
- notifications: peringatan dari MPC ke Mitra (paket tidak sesuai / perlu review).
"""

import json
import os
import threading
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_PATH = os.path.join(_BASE_DIR, "config", "mpc_data.json")

_lock = threading.Lock()
_validations = {}
_notifications = []
_notif_counter = [0]
_loaded = [False]


def _ensure_loaded_locked():
    """Muat state dari disk sekali. Pemanggil HARUS sudah memegang _lock."""
    if _loaded[0]:
        return
    _loaded[0] = True
    if not os.path.exists(_DATA_PATH):
        return
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    _validations.clear()
    _validations.update(data.get("validations", {}))
    _notifications.clear()
    _notifications.extend(data.get("notifications", []))
    _notif_counter[0] = int(data.get("notif_counter", 0))


def _save_locked():
    """Tulis state ke disk. Pemanggil HARUS sudah memegang _lock."""
    os.makedirs(os.path.dirname(_DATA_PATH), exist_ok=True)
    data = {
        "validations": _validations,
        "notifications": _notifications,
        "notif_counter": _notif_counter[0],
    }
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def reset():
    """Kosongkan semua data (untuk test / reset demo)."""
    with _lock:
        _validations.clear()
        _notifications.clear()
        _notif_counter[0] = 0
        _loaded[0] = True
        _save_locked()


def save_validation(package_id, mpc_measurement, result, mpc_username=None,
                    catatan=None):
    """Simpan hasil validasi sebuah paket.

    result: dict dari validation_engine.compare_measurements.
    """
    with _lock:
        _ensure_loaded_locked()
        record = {
            "package_id": str(package_id),
            "status": result.get("status"),
            "status_label": result.get("status_label"),
            "selisih": result.get("selisih", {}),
            "breaches": result.get("breaches", []),
            "mpc_measurement": mpc_measurement,
            "mpc_username": mpc_username,
            "catatan": catatan or "",
            "validated_at": datetime.now().isoformat(),
        }
        _validations[str(package_id)] = record
        _save_locked()
        return record


def get_validation(package_id):
    with _lock:
        _ensure_loaded_locked()
        return _validations.get(str(package_id))


def list_validations():
    """Semua validasi, terbaru dulu."""
    with _lock:
        _ensure_loaded_locked()
        items = list(_validations.values())
    items.sort(key=lambda v: v.get("validated_at", ""), reverse=True)
    return items


def validation_stats():
    """Hitung jumlah per status."""
    with _lock:
        _ensure_loaded_locked()
        items = list(_validations.values())
    stats = {"valid": 0, "perlu_review": 0, "tidak_sesuai": 0}
    for v in items:
        status = v.get("status")
        if status in stats:
            stats[status] += 1
    stats["total"] = len(items)
    return stats


def create_notification(package_id, to_mitra_id, title, message,
                        status=None):
    """Buat notifikasi/peringatan untuk Mitra."""
    with _lock:
        _ensure_loaded_locked()
        _notif_counter[0] += 1
        notif = {
            "id": _notif_counter[0],
            "package_id": str(package_id),
            "to_mitra_id": to_mitra_id,
            "title": title,
            "message": message,
            "status": status,
            "is_read": False,
            "created_at": datetime.now().isoformat(),
        }
        _notifications.append(notif)
        _save_locked()
        return notif


def list_notifications(to_mitra_id=None, unread_only=False):
    """Daftar notifikasi, opsional difilter per Mitra / belum dibaca."""
    with _lock:
        _ensure_loaded_locked()
        items = list(_notifications)
    if to_mitra_id is not None:
        items = [n for n in items if n.get("to_mitra_id") == to_mitra_id]
    if unread_only:
        items = [n for n in items if not n.get("is_read")]
    items.sort(key=lambda n: n.get("created_at", ""), reverse=True)
    return items


def mark_read(notification_id):
    with _lock:
        _ensure_loaded_locked()
        for n in _notifications:
            if n["id"] == notification_id:
                n["is_read"] = True
                _save_locked()
                return True
    return False


def unread_count(to_mitra_id=None):
    return len(list_notifications(to_mitra_id=to_mitra_id, unread_only=True))
