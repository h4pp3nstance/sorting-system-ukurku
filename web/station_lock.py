"""
Station Lock - kunci eksklusif untuk satu stasiun ukur fisik.

Hanya ada SATU alat ukur (kamera + loadcell + ultrasonik), dipakai bergantian
oleh dua mode: pengukuran MITRA (paket baru) dan pengukuran MPC (validasi/ukur
ulang). `_session_lock` di measurement_engine hanya mencegah crash thread; ia
TIDAK mencegah dua orang memicu pengukuran fisik bersamaan di alat yang sama.

Modul ini menambahkan kunci di level aplikasi: hanya satu sesi pengukuran aktif
pada satu waktu. UI kedua mode bisa menampilkan "alat sedang dipakai oleh X".

Stale-session guard: jika sebuah sesi menggantung (operator pergi, request
crash sebelum release), sesi otomatis dianggap kedaluwarsa setelah _TIMEOUT
detik supaya alat tidak terkunci selamanya.

Pure-Python, thread-safe, testable di laptop (tanpa hardware/Flask).
"""

import threading
import time

MODE_IDLE = "idle"
MODE_MITRA = "mitra_measuring"
MODE_MPC = "mpc_measuring"

# Sesi dianggap kedaluwarsa setelah ini (detik). Pengukuran normal < 30s
# (timeout measure_real default), jadi 90s memberi margin aman.
_TIMEOUT = 90.0

_lock = threading.Lock()
_state = {
    "mode": MODE_IDLE,
    "owner": None,
    "started_at": 0.0,
}


def _is_stale_locked(now):
    """True jika ada sesi aktif yang sudah melewati _TIMEOUT. Pemegang _lock."""
    if _state["mode"] == MODE_IDLE:
        return False
    return (now - _state["started_at"]) > _TIMEOUT


def acquire(mode, owner=None):
    """Coba kunci stasiun untuk `mode`. Return (ok, info).

    ok=True  -> stasiun berhasil dikunci untuk pemanggil; WAJIB release().
    ok=False -> stasiun sedang dipakai; info berisi status sesi aktif.

    Sesi kedaluwarsa (stale) otomatis direbut: alat tidak terkunci selamanya
    bila request sebelumnya crash tanpa release.
    """
    now = time.time()
    with _lock:
        if _state["mode"] != MODE_IDLE and not _is_stale_locked(now):
            return False, _status_locked(now)
        _state["mode"] = mode
        _state["owner"] = owner
        _state["started_at"] = now
        return True, _status_locked(now)


def release():
    """Lepas kunci stasiun (idempotent)."""
    with _lock:
        _state["mode"] = MODE_IDLE
        _state["owner"] = None
        _state["started_at"] = 0.0


def _status_locked(now):
    """Snapshot status. Pemegang _lock."""
    busy = _state["mode"] != MODE_IDLE and not _is_stale_locked(now)
    elapsed = (now - _state["started_at"]) if busy else 0.0
    return {
        "mode": _state["mode"] if busy else MODE_IDLE,
        "owner": _state["owner"] if busy else None,
        "busy": busy,
        "elapsed_seconds": round(elapsed, 1),
    }


def status():
    """Status stasiun saat ini (idle/busy + owner)."""
    now = time.time()
    with _lock:
        return _status_locked(now)


def reset():
    """Reset paksa ke idle (untuk test / pemulihan startup)."""
    release()
