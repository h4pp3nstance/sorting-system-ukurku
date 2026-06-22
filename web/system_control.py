"""
System Control Bridge untuk web dashboard.

REVISI AMAN v2:
- Dipakai saat logout / switch account agar alat kembali STANDBY.
- Web TIDAK mematikan semua proses Python.
- Web hanya mengirim sinyal ke proses Tahap 18 yang benar-benar cocok.
- Tidak memakai kill process group, karena pada kondisi tertentu SIGINT ke group bisa ikut
  mematikan run_web.py / Flask server.

Alur:
logout/switch account -> request_standby() -> SIGINT hanya ke PID Tahap 18 ->
Tahap 18 cleanup kamera/servo/GPIO -> Tahap 17 mendeteksi Tahap 18 berhenti ->
Tahap 17 kembali STOP/STANDBY dan mematikan motor/lampu hijau.
"""

import os
import signal
import time
import threading
from datetime import datetime
from pathlib import Path

# Nama file Tahap 18 yang benar-benar boleh dihentikan oleh web.
# Jangan isi dengan "python", karena itu bisa mematikan run_web.py.
TAHAP18_SCRIPT_BASENAME = os.getenv(
    "TAHAP18_SCRIPT_BASENAME",
    "tahap18_integrated_chargeable_kardus_filter.py",
)

# Jika struktur folder berbeda, boleh diisi path absolut dari environment.
PROGRAM_PYTHON_DIR = os.getenv(
    "PROGRAM_PYTHON_DIR",
    "/home/dani12/Backup-Lama/home/dninugrha/Tugas-Akhir/program-python",
)

TAHAP18_ABS_PATH = os.getenv(
    "TAHAP18_ABS_PATH",
    str(Path(PROGRAM_PYTHON_DIR) / TAHAP18_SCRIPT_BASENAME),
)

_STANDBY_LOCK = threading.Lock()


def _read_cmdline(pid: int):
    """Baca /proc/<pid>/cmdline sebagai list argument."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except Exception:
        return []

    parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\x00") if p]
    return parts


def _is_python_process(parts):
    if not parts:
        return False
    exe = os.path.basename(parts[0]).lower()
    return "python" in exe


def _looks_like_tahap18(pid: int):
    """
    Filter ketat agar yang dihentikan hanya proses Tahap 18.

    Syarat:
    - proses Python
    - argumen command line memuat file Tahap 18
    - bukan proses web/run_web/flask/gunicorn
    - bukan PID proses web saat ini
    """
    if pid == os.getpid():
        return False

    parts = _read_cmdline(pid)
    if not parts:
        return False

    joined = " ".join(parts)
    joined_lower = joined.lower()

    # Proteksi: jangan pernah hentikan web server.
    forbidden = ["run_web.py", "flask", "gunicorn", "uwsgi"]
    if any(x in joined_lower for x in forbidden):
        return False

    if not _is_python_process(parts):
        return False

    # Cocokkan nama file tahap18 sebagai argumen Python.
    for arg in parts[1:]:
        base = os.path.basename(arg)
        if base == TAHAP18_SCRIPT_BASENAME:
            return True

    # Fallback path absolut jika command line berupa path lengkap.
    if TAHAP18_ABS_PATH and TAHAP18_ABS_PATH in joined:
        return True

    return False


def find_tahap18_pids():
    """Cari PID Tahap 18 dari /proc, tanpa pgrep agar tidak salah match."""
    pids = []

    try:
        proc_dir = Path("/proc")
        for item in proc_dir.iterdir():
            if not item.name.isdigit():
                continue
            pid = int(item.name)
            if _looks_like_tahap18(pid):
                pids.append(pid)
    except Exception:
        return []

    return sorted(set(pids))


def _is_alive(pid: int):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Ada proses tetapi user web tidak punya izin penuh.
        return True
    except Exception:
        return False


def _signal_pid(pid: int, sig):
    """
    Kirim sinyal hanya ke PID, bukan process group.
    Ini mencegah web server ikut mati.
    """
    try:
        os.kill(pid, sig)
        return True, f"signal pid {pid}"
    except ProcessLookupError:
        return True, "process already stopped"
    except PermissionError as exc:
        return False, f"permission denied: {exc}"
    except Exception as exc:
        return False, str(exc)


def request_standby(reason="web_request", wait_seconds=4.0, allow_sigterm=True):
    """
    Minta sistem kembali standby dengan menghentikan Tahap 18 saja.

    Return dict aman untuk JSON.
    """
    with _STANDBY_LOCK:
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pids = find_tahap18_pids()

        result = {
            "ok": True,
            "reason": reason,
            "timestamp": started_at,
            "script": TAHAP18_SCRIPT_BASENAME,
            "tahap18_abs_path": TAHAP18_ABS_PATH,
            "pids_found": pids,
            "actions": [],
            "message": "Tidak ada proses Tahap 18 yang sedang berjalan.",
        }

        if not pids:
            return result

        # Tahap 18 menangani KeyboardInterrupt dan cleanup kamera/servo/GPIO.
        for pid in pids:
            ok, msg = _signal_pid(pid, signal.SIGINT)
            result["actions"].append({
                "pid": pid,
                "signal": "SIGINT",
                "ok": ok,
                "message": msg,
                "cmdline": " ".join(_read_cmdline(pid)),
            })
            if not ok:
                result["ok"] = False

        deadline = time.time() + max(0.5, float(wait_seconds))
        while time.time() < deadline:
            alive = [pid for pid in pids if _is_alive(pid)]
            if not alive:
                result["message"] = "Tahap 18 berhenti. Tahap 17 akan kembali ke STOP/STANDBY."
                return result
            time.sleep(0.15)

        alive = [pid for pid in pids if _is_alive(pid)]

        # Fallback opsional. Tetap hanya ke PID, bukan group.
        if allow_sigterm and alive:
            for pid in alive:
                ok, msg = _signal_pid(pid, signal.SIGTERM)
                result["actions"].append({
                    "pid": pid,
                    "signal": "SIGTERM",
                    "ok": ok,
                    "message": msg,
                    "cmdline": " ".join(_read_cmdline(pid)),
                })
                if not ok:
                    result["ok"] = False

        result["message"] = "Perintah standby dikirim hanya ke PID Tahap 18. Tahap 17 akan mematikan motor saat Tahap 18 berhenti."
        return result
