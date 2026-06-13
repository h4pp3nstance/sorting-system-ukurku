"""
Measurement Bridge - Membaca data pengukuran dari file JSON tahap14
tanpa import hardware/GPIO/camera.
"""

import json
import os
import time


class MeasurementBridgeError(Exception):
    pass


class MeasurementResult:
    """Hasil pengukuran yang sudah di-map ke format UI"""

    def __init__(self, data: dict):
        self.panjang = data['panjang']
        self.lebar = data['lebar']
        self.tinggi = data['tinggi']
        self.berat_aktual = data['berat_aktual']
        self.berat_volumetrik = data['berat_volumetrik']
        self.chargeable_weight = data['chargeable_weight']
        self.chargeable_source = data['chargeable_source']
        self.measurement_id = data['measurement_id']
        self.timestamp = data['timestamp']
        self.detection_image = data.get('detection_image')
        self.raw = data

    def to_dict(self):
        return self.raw


def read_measurement_file(file_path: str, max_age_seconds: int = 300) -> dict:
    """
    Baca file JSON pengukuran dan validasi.

    Raises MeasurementBridgeError dengan pesan Indonesian jika gagal.
    """
    if not os.path.isfile(file_path):
        raise MeasurementBridgeError(
            "File pengukuran tidak ditemukan. "
            "Pastikan sistem pengukuran (tahap14) sudah dijalankan minimal sekali."
        )

    file_age = time.time() - os.path.getmtime(file_path)
    if file_age > max_age_seconds:
        minutes = int(file_age // 60)
        raise MeasurementBridgeError(
            f"Data pengukuran sudah kadaluarsa ({minutes} menit lalu). "
            "Jalankan pengukuran baru pada sistem hardware terlebih dahulu."
        )

    try:
        with open(file_path, 'r') as f:
            raw = json.load(f)
    except json.JSONDecodeError:
        raise MeasurementBridgeError(
            "File pengukuran rusak (format JSON tidak valid). "
            "Jalankan ulang pengukuran pada sistem hardware."
        )
    except PermissionError:
        raise MeasurementBridgeError(
            "Tidak dapat membaca file pengukuran (izin akses ditolak)."
        )

    return raw


def map_to_package_format(raw: dict, program_python_base: str = "") -> dict:
    """
    Map field dari JSON tahap14 ke format package UI.

    Field mapping:
      panjang_cm -> panjang
      lebar_cm -> lebar
      tinggi_cm -> tinggi
      berat_aktual_g -> berat_aktual
      berat_volumetrik_g -> berat_volumetrik
      chargeable_weight_g -> chargeable_weight
      chargeable_source -> chargeable_source
      measurement_id -> measurement_id
      timestamp -> timestamp
      detection_image -> detection_image (relative path from source JSON)
    """
    required_fields = [
        'panjang_cm', 'lebar_cm', 'tinggi_cm',
        'berat_aktual_g', 'berat_volumetrik_g', 'chargeable_weight_g',
        'measurement_id', 'timestamp'
    ]

    missing = [f for f in required_fields if f not in raw]
    if missing:
        raise MeasurementBridgeError(
            f"Data pengukuran tidak lengkap (field hilang: {', '.join(missing)}). "
            "Pastikan menggunakan versi terbaru sistem pengukuran."
        )

    if float(raw['berat_aktual_g']) < 50 or float(raw['tinggi_cm']) <= 0:
        raise MeasurementBridgeError(
            "Paket belum terbaca oleh mesin. "
            "Pastikan paket berada di atas timbangan dan beratnya minimal 50 gram."
        )

    detection_image = raw.get('detection_image', '')
    if detection_image:
        detection_image = detection_image.lstrip(os.sep)

    return {
        'panjang': round(raw['panjang_cm'], 2),
        'lebar': round(raw['lebar_cm'], 2),
        'tinggi': round(raw['tinggi_cm'], 2),
        'berat_aktual': round(raw['berat_aktual_g'], 1),
        'berat_volumetrik': round(raw['berat_volumetrik_g'], 1),
        'chargeable_weight': round(raw['chargeable_weight_g'], 1),
        'chargeable_source': raw.get('chargeable_source', 'unknown'),
        'measurement_id': raw['measurement_id'],
        'timestamp': raw['timestamp'],
        'detection_image': detection_image,
    }


def classify_package(chargeable_weight_g: float) -> tuple:
    """
    Klasifikasi paket berdasarkan chargeable weight.
    Ambang & tarif dibaca dari settings_store (dinamis); fallback ke
    konstanta config bila settings tak tersedia.
    Returns (service_type, price).
    """
    try:
        from web.settings_store import get_classification, get_tariffs
        kls = get_classification()
        tarif = get_tariffs()
        reguler_max = kls["reguler_max_g"]
        express_max = kls["express_max_g"]
        price_reguler = tarif["REGULER"]
        price_express = tarif["EXPRESS"]
        price_kargo = tarif["KARGO"]
    except Exception:
        from config.settings import (
            WEIGHT_REGULER_MAX, WEIGHT_EXPRESS_MAX,
            PRICE_REGULER, PRICE_EXPRESS, PRICE_KARGO
        )
        reguler_max, express_max = WEIGHT_REGULER_MAX, WEIGHT_EXPRESS_MAX
        price_reguler, price_express, price_kargo = PRICE_REGULER, PRICE_EXPRESS, PRICE_KARGO

    if chargeable_weight_g <= reguler_max:
        return 'REGULER', price_reguler
    elif chargeable_weight_g <= express_max:
        return 'EXPRESS', price_express
    else:
        return 'KARGO', price_kargo


def get_measurement_from_file(
    file_path: str,
    program_python_base: str = "",
    max_age_seconds: int = 300
) -> MeasurementResult:
    """
    Entry point utama: baca file -> validasi -> map -> return MeasurementResult.
    """
    raw = read_measurement_file(file_path, max_age_seconds)
    mapped = map_to_package_format(raw, program_python_base)
    return MeasurementResult(mapped)


def should_use_file_bridge(hardware_mode: str, measurement_mode: str) -> bool:
    """
    Tentukan apakah harus pakai file bridge berdasarkan config.

    Logic:
    - measurement_mode == "file" -> selalu pakai file bridge
    - measurement_mode == "mock" -> selalu pakai mock
    - measurement_mode == "auto" -> pakai file bridge jika hardware_mode == "real"
    """
    if measurement_mode == "file":
        return True
    if measurement_mode == "mock":
        return False
    return hardware_mode == "real"
