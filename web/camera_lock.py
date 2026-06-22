"""
Camera Coordinator antara ukurku-web (Flask) dan tahap18 (CLI legacy).

Kontrak:
- Tahap18 = pemilik kamera saat aktif (kebijakan asli mahasiswa, lihat
  komentar di tahap18 baris ~1755: "Web/dashboard tidak boleh membuka
  webcam langsung agar tidak bentrok.").
- Web HANYA boleh buka kamera bila tahap18 TIDAK aktif.
- Kalau tahap18 aktif lalu web mau ukur -> tolak dengan pesan jelas.

Deteksi tahap18 aktif memakai detektor yang sudah ada di
`web/system_control.find_tahap18_pids()` -- tidak butuh modif tahap18 dan
tidak butuh file lock manual.

Modul ini sengaja ringan dan import-safe di laptop tanpa hardware.
"""

from __future__ import annotations

from typing import Tuple


class CameraBusyError(RuntimeError):
    """Kamera dipakai oleh tahap18 (CLI). Web tidak boleh buka sekarang."""

    def __init__(self, message: str, pids: list[int] | None = None):
        super().__init__(message)
        self.pids = list(pids or [])


def tahap18_pids() -> list[int]:
    """Daftar PID tahap18 yang sedang jalan (kosong kalau tidak aktif)."""
    try:
        from web.system_control import find_tahap18_pids
        return list(find_tahap18_pids())
    except Exception:
        return []


def is_tahap18_active() -> bool:
    """True bila ada proses tahap18 yang sedang jalan di mesin ini."""
    return bool(tahap18_pids())


def ensure_web_can_use_camera() -> Tuple[bool, str, list[int]]:
    """
    Cek izin web untuk pakai kamera.

    Returns:
        (ok, message, pids):
            ok=True  -> aman, tahap18 tidak aktif
            ok=False -> tahap18 aktif, message berisi alasan untuk UI/log
    """
    pids = tahap18_pids()
    if not pids:
        return True, "", []
    msg = (
        "Kamera sedang dipakai pengukuran fisik (tahap18 via PB ON). "
        "Tekan PB OFF dulu di alat sebelum mengukur dari web."
    )
    return False, msg, pids


def status_payload() -> dict:
    """Payload ringkas untuk dipakai endpoint status / UI banner."""
    pids = tahap18_pids()
    active = bool(pids)
    return {
        "tahap18_active": active,
        "tahap18_pids": pids,
        "web_can_use_camera": not active,
        "message": (
            "Tahap18 aktif - kamera dipegang CLI"
            if active
            else "Kamera bebas dipakai web"
        ),
    }
