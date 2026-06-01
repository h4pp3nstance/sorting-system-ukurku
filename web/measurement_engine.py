"""
Measurement Engine (Opsi C - in-process, kamera hangat)

Lapisan integrasi antara web Flask dan logika pengukuran program-python.
Memanggil MeasurementSession (tahap14_session.py di program-python) secara
in-process: kamera dibuka sekali lalu tetap hangat, sehingga tiap klik
"Ukur" cepat dan tare bisa di-refresh saat idle.

Import hardware (RPi.GPIO, cv2, tahap14_session) dilakukan LAZY di dalam
fungsi, supaya modul ini tetap import-able dan testable di laptop tanpa
hardware Raspberry Pi.
"""

import os
import sys
import threading
from contextlib import contextmanager


@contextmanager
def _chdir_base():
    """Jalankan blok dengan cwd = PROGRAM_PYTHON_BASE.

    tahap14/tahap10 memakai path RELATIF ke cwd (hasil_tahap9/, hasil_tahap11/,
    hasil_tahap14/archive/). Web service berjalan dari folder lain, jadi cwd
    harus dialihkan sementara saat init sesi & pengukuran, lalu dikembalikan.
    """
    base = _resolve_program_python_base()
    prev = os.getcwd()
    if base and os.path.isdir(base):
        os.chdir(base)
    try:
        yield
    finally:
        os.chdir(prev)



class MeasurementEngineError(Exception):
    """Base error untuk engine pengukuran in-process."""


class MeasurementUnavailableError(MeasurementEngineError):
    """Logika pengukuran hardware tidak tersedia (mis. dijalankan di laptop)."""


class NeedCalibrationError(MeasurementEngineError):
    """File kalibrasi hilang/invalid; perlu kalibrasi attended dulu."""


class MeasurementTimeoutError(MeasurementEngineError):
    """Paket tidak terdeteksi dalam batas waktu."""


# Singleton session + lock (satu pemilik kamera/GPIO)
_session = None
_session_lock = threading.Lock()


def _resolve_program_python_base():
    """Cari folder program-python (sumber MeasurementSession)."""
    from config.settings import PROGRAM_PYTHON_BASE
    return PROGRAM_PYTHON_BASE


def _load_session_class():
    """Lazy import MeasurementSession dari program-python.

    Diisolasi di sini agar ImportError (hardware/modul belum ada) bisa
    diterjemahkan jadi MeasurementUnavailableError yang ramah.
    """
    base = _resolve_program_python_base()
    if not base or not os.path.isdir(base):
        raise MeasurementUnavailableError(
            "Folder program-python tidak ditemukan. "
            "Set PROGRAM_PYTHON_BASE atau jalankan di Raspberry Pi."
        )
    if base not in sys.path:
        sys.path.insert(0, base)
    try:
        from tahap14_session import MeasurementSession
    except ImportError as e:
        raise MeasurementUnavailableError(
            "Modul pengukuran (tahap14_session) belum tersedia di "
            "program-python, atau dependensi hardware tidak terpasang: "
            f"{e}"
        )
    return MeasurementSession


def get_session():
    """Ambil/inisialisasi singleton MeasurementSession (kamera hangat)."""
    global _session
    with _session_lock:
        if _session is None:
            session_cls = _load_session_class()
            with _chdir_base():
                _session = session_cls(headless=True)
        return _session


def reset_session():
    """Tutup & lepaskan session (mis. saat shutdown/test)."""
    global _session
    with _session_lock:
        if _session is not None:
            try:
                _session.close()
            except Exception:
                pass
            _session = None


def map_session_result(raw: dict) -> dict:
    """Map hasil MeasurementSession.measure_once() ke format package UI.

    Pure function (tanpa hardware) supaya bisa diuji di laptop.
    Menerima key gaya tahap14 (panjang_cm, berat_aktual_g, dst).
    """
    required = [
        'panjang_cm', 'lebar_cm', 'tinggi_cm',
        'berat_aktual_g', 'berat_volumetrik_g', 'chargeable_weight_g',
        'measurement_id', 'timestamp',
    ]
    missing = [k for k in required if k not in raw]
    if missing:
        raise MeasurementEngineError(
            "Hasil pengukuran tidak lengkap (field hilang: "
            f"{', '.join(missing)})."
        )

    detection_image = raw.get('detection_image', '') or ''
    if detection_image:
        detection_image = detection_image.lstrip(os.sep)

    return {
        'panjang': round(float(raw['panjang_cm']), 2),
        'lebar': round(float(raw['lebar_cm']), 2),
        'tinggi': round(float(raw['tinggi_cm']), 2),
        'berat_aktual': round(float(raw['berat_aktual_g']), 1),
        'berat_volumetrik': round(float(raw['berat_volumetrik_g']), 1),
        'chargeable_weight': round(float(raw['chargeable_weight_g']), 1),
        'chargeable_source': raw.get('chargeable_source', 'unknown'),
        'measurement_id': raw['measurement_id'],
        'timestamp': raw['timestamp'],
        'detection_image': detection_image,
    }


def measure_real(timeout_seconds: int = 30) -> dict:
    """Picu SATU pengukuran nyata in-process dan kembalikan hasil ter-map.

    Raises:
        MeasurementUnavailableError: hardware/modul tidak tersedia (laptop).
        NeedCalibrationError: file kalibrasi hilang.
        MeasurementTimeoutError: paket tak terdeteksi dalam batas waktu.
    """
    session = get_session()

    with _session_lock:
        try:
            with _chdir_base():
                raw = session.measure_once(timeout=timeout_seconds)
        except MeasurementEngineError:
            raise
        except Exception as e:
            name = type(e).__name__
            if name == 'NeedCalibration':
                raise NeedCalibrationError(str(e))
            if name in ('MeasurementTimeout', 'TimeoutError'):
                raise MeasurementTimeoutError(str(e))
            raise MeasurementEngineError(
                f"Pengukuran gagal: {e}"
            )

    return map_session_result(raw)


def retare():
    """Re-tare loadcell saat idle/platform kosong (lawan drift HX711)."""
    session = get_session()
    with _session_lock:
        session.retare()
