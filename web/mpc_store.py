"""
MPC Store - persistent store untuk validasi & notifikasi.

State disimpan ke config/mpc_data.json (pola sama dengan users.json /
app_settings.json) supaya bertahan lintas restart. Lazy-load sekali saat
akses pertama, lalu ditulis ulang setiap mutasi.
Pure-Python, testable di laptop.

Entitas:
- validations  : hasil validasi Mitra vs MPC per paket (ringkasan terakhir).
- attempts     : RIWAYAT setiap percobaan validasi MPC per paket (audit trail).
                 Tidak pernah ditimpa; setiap ukur ulang = attempt baru. Inilah
                 yang membedakan sistem audit dari demo biasa.
- notifications: peringatan dari MPC ke Mitra (paket tidak sesuai / perlu review).
"""

import json
import os
import threading
from datetime import datetime, timedelta

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_PATH = os.path.join(_BASE_DIR, "config", "mpc_data.json")

_lock = threading.Lock()
_validations = {}
_attempts = {}
_notifications = []
_notif_counter = [0]
_loaded = [False]

# Single-slot state: pengukuran tahap18 berikutnya dialihkan jadi re-measure MPC
# untuk paket terpilih. Dikonsumsi box_poller._ingest_once().
ARM_DEFAULT_TIMEOUT_SECONDS = 300
_armed = [None]

# Form draft per-mitra: dashboard auto-save sender/recipient sebelum PB ON.
# Dikonsumsi box_poller._ingest_once() saat paket box_tahap18 masuk.
# Key: str(mitra_id) -> {"sender": {...}, "recipient": {...}, "saved_at": iso, "expires_at": iso}
FORM_DRAFT_DEFAULT_TTL_SECONDS = 300
_form_drafts = {}


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
    _attempts.clear()
    _attempts.update(data.get("attempts", {}))
    _notifications.clear()
    _notifications.extend(data.get("notifications", []))
    _notif_counter[0] = int(data.get("notif_counter", 0))
    _armed[0] = data.get("mpc_arm") or None
    _form_drafts.clear()
    _form_drafts.update(data.get("form_drafts", {}) or {})
    _migrate_legacy_attempts_locked()


def _migrate_legacy_attempts_locked():
    """Bungkus validasi lama (format tunggal, sebelum fitur attempt) jadi
    attempt #1 supaya riwayat tetap utuh. Pemegang _lock."""
    changed = False
    for pid, record in _validations.items():
        if pid not in _attempts or not _attempts[pid]:
            attempt = dict(record)
            attempt.setdefault("attempt_no", 1)
            attempt.setdefault("data_source", "manual")
            attempt.setdefault("mitra_snapshot", None)
            _attempts[pid] = [attempt]
            changed = True
    if changed:
        _save_locked()


def _save_locked():
    """Tulis state ke disk. Pemanggil HARUS sudah memegang _lock."""
    os.makedirs(os.path.dirname(_DATA_PATH), exist_ok=True)
    data = {
        "validations": _validations,
        "attempts": _attempts,
        "notifications": _notifications,
        "notif_counter": _notif_counter[0],
        "mpc_arm": _armed[0],
        "form_drafts": _form_drafts,
    }
    # Atomic write: tulis ke temp dulu lalu rename. Mencegah file korup kalau
    # poller + Flask write bersamaan.
    tmp_path = _DATA_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, _DATA_PATH)


def reset():
    """Kosongkan semua data (untuk test / reset demo)."""
    with _lock:
        _validations.clear()
        _attempts.clear()
        _notifications.clear()
        _notif_counter[0] = 0
        _armed[0] = None
        _form_drafts.clear()
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


def add_validation_attempt(package_id, mpc_measurement, result,
                           mpc_username=None, catatan=None,
                           data_source="mpc_in_process",
                           mitra_snapshot=None, sensor_status=None,
                           tare_timestamp=None):
    """Catat SATU percobaan validasi MPC (audit trail, tidak menimpa).

    Berbeda dari save_validation: setiap panggilan menambah attempt baru ke
    riwayat paket. Ringkasan terakhir tetap disinkron ke _validations supaya
    dashboard/stat lama tetap jalan.

    mitra_snapshot: pengukuran Mitra yang dibekukan saat compare (konsistensi).
    sensor_status : status sensor granular (mis. 'ok', 'sensor_error',
                    'needs_remeasure', 'paket_tidak_terdeteksi').
    """
    with _lock:
        _ensure_loaded_locked()
        prev = _attempts.get(str(package_id), [])
        attempt_no = len(prev) + 1
        record = {
            "package_id": str(package_id),
            "attempt_no": attempt_no,
            "status": result.get("status"),
            "status_label": result.get("status_label"),
            "selisih": result.get("selisih", {}),
            "breaches": result.get("breaches", []),
            "mpc_measurement": mpc_measurement,
            "mitra_snapshot": mitra_snapshot,
            "sensor_status": sensor_status or "ok",
            "data_source": data_source,
            "mpc_username": mpc_username,
            "catatan": catatan or "",
            "tare_timestamp": tare_timestamp,
            "validated_at": datetime.now().isoformat(),
        }
        _attempts.setdefault(str(package_id), []).append(record)
        # Sinkron ringkasan terakhir ke _validations (kompat dashboard lama).
        _validations[str(package_id)] = record
        _save_locked()
        return record


def list_attempts(package_id):
    """Riwayat semua percobaan validasi sebuah paket (urut: lama -> baru)."""
    with _lock:
        _ensure_loaded_locked()
        return list(_attempts.get(str(package_id), []))


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


def _is_arm_expired_locked(arm):
    if not arm:
        return True
    exp = arm.get("expires_at")
    if not exp:
        return True
    try:
        return datetime.fromisoformat(exp) <= datetime.now()
    except (ValueError, TypeError):
        return True


def _clear_armed_locked(reason=None):
    prev = _armed[0]
    if prev is None:
        return None
    _armed[0] = None
    _save_locked()
    if reason:
        prev = dict(prev)
        prev["cleared_reason"] = reason
    return prev


def arm_mpc(package_id, armed_by=None, timeout_seconds=None):
    """Arm sistem untuk pengukuran ulang MPC paket #package_id.

    Hanya satu paket bisa armed sekaligus. Kalau sudah ada armed aktif yang
    belum expired untuk paket lain, return (False, existing_arm).
    Kalau armed yang ada untuk paket yang sama, refresh timeout.
    Return (True, arm_dict) saat sukses.
    """
    timeout = int(timeout_seconds or ARM_DEFAULT_TIMEOUT_SECONDS)
    with _lock:
        _ensure_loaded_locked()
        existing = _armed[0]
        if existing and not _is_arm_expired_locked(existing):
            if str(existing.get("package_id")) != str(package_id):
                return False, dict(existing)
        now = datetime.now()
        arm = {
            "package_id": str(package_id),
            "armed_by": armed_by,
            "armed_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=timeout)).isoformat(),
            "timeout_seconds": timeout,
            "status": "armed",
        }
        _armed[0] = arm
        _save_locked()
        return True, dict(arm)


def get_armed():
    """Return armed state aktif (dict) atau None. Auto-clear kalau expired."""
    with _lock:
        _ensure_loaded_locked()
        arm = _armed[0]
        if arm and _is_arm_expired_locked(arm):
            _clear_armed_locked(reason="expired")
            return None
        return dict(arm) if arm else None


def cancel_armed(by_user=None):
    """Bersihkan armed state secara eksplisit (MPC klik cancel).

    Return arm yang dibersihkan (dict) atau None kalau memang tidak ada.
    """
    with _lock:
        _ensure_loaded_locked()
        arm = _armed[0]
        if not arm:
            return None
        cleared = _clear_armed_locked(reason="cancelled")
        if cleared and by_user:
            cleared["cancelled_by"] = by_user
        return cleared


def consume_armed(measurement_id, expected_package_id=None):
    """Atomically consume armed state oleh box_poller.

    Return arm dict yang baru saja di-consume kalau armed aktif (dan,
    jika expected_package_id diberikan, package_id-nya cocok). Mengembalikan
    None kalau tidak ada armed valid -- pemanggil lanjut alur normal.

    Setelah consume berhasil, armed state langsung dibersihkan; measurement_id
    yang sama tidak akan ter-consume dua kali.
    """
    with _lock:
        _ensure_loaded_locked()
        arm = _armed[0]
        if not arm:
            return None
        if _is_arm_expired_locked(arm):
            _clear_armed_locked(reason="expired")
            return None
        if expected_package_id is not None \
                and str(arm.get("package_id")) != str(expected_package_id):
            return None
        consumed = dict(arm)
        consumed["consumed_measurement_id"] = measurement_id
        consumed["consumed_at"] = datetime.now().isoformat()
        _armed[0] = None
        _save_locked()
        return consumed


def _is_draft_expired_locked(draft):
    exp = draft.get("expires_at")
    if not exp:
        return True
    try:
        return datetime.fromisoformat(exp) <= datetime.now()
    except (ValueError, TypeError):
        return True


def _sanitize_party(party):
    if not isinstance(party, dict):
        return None
    nama = (party.get("nama") or "").strip()
    telepon = (party.get("telepon") or "").strip()
    alamat = (party.get("alamat") or "").strip()
    if not nama and not telepon and not alamat:
        return None
    return {"nama": nama, "telepon": telepon, "alamat": alamat}


def set_form_draft(mitra_id, sender=None, recipient=None, ttl_seconds=None):
    """Simpan/refresh form draft pengirim+penerima per Mitra.

    Dipanggil dari endpoint /api/form/draft (debounced auto-save dashboard).
    Return draft dict yang baru disimpan. Kalau sender DAN recipient kosong
    semua, draft di-clear (return None).
    """
    if mitra_id is None:
        return None
    key = str(mitra_id)
    ttl = int(ttl_seconds or FORM_DRAFT_DEFAULT_TTL_SECONDS)
    clean_sender = _sanitize_party(sender)
    clean_recipient = _sanitize_party(recipient)
    with _lock:
        _ensure_loaded_locked()
        if clean_sender is None and clean_recipient is None:
            removed = _form_drafts.pop(key, None)
            if removed is not None:
                _save_locked()
            return None
        now = datetime.now()
        draft = {
            "mitra_id": key,
            "sender": clean_sender,
            "recipient": clean_recipient,
            "saved_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "ttl_seconds": ttl,
        }
        _form_drafts[key] = draft
        _save_locked()
        return dict(draft)


def get_form_draft(mitra_id):
    """Return draft aktif untuk Mitra atau None. Auto-clear kalau expired."""
    if mitra_id is None:
        return None
    key = str(mitra_id)
    with _lock:
        _ensure_loaded_locked()
        draft = _form_drafts.get(key)
        if not draft:
            return None
        if _is_draft_expired_locked(draft):
            _form_drafts.pop(key, None)
            _save_locked()
            return None
        return dict(draft)


def consume_form_draft(mitra_id):
    """Atomically consume draft untuk Mitra (dipakai box_poller saat ingest).

    Return dict {sender, recipient} kalau ada draft valid, None kalau tidak.
    Draft langsung dihapus setelah consume supaya tidak attach ke paket lain.
    """
    if mitra_id is None:
        return None
    key = str(mitra_id)
    with _lock:
        _ensure_loaded_locked()
        draft = _form_drafts.pop(key, None)
        if not draft:
            return None
        if _is_draft_expired_locked(draft):
            _save_locked()
            return None
        _save_locked()
        return {
            "sender": draft.get("sender"),
            "recipient": draft.get("recipient"),
            "consumed_at": datetime.now().isoformat(),
            "saved_at": draft.get("saved_at"),
        }


def clear_form_draft(mitra_id):
    """Hapus draft untuk Mitra (dipakai saat user reset form)."""
    if mitra_id is None:
        return None
    key = str(mitra_id)
    with _lock:
        _ensure_loaded_locked()
        removed = _form_drafts.pop(key, None)
        if removed is not None:
            _save_locked()
        return removed
