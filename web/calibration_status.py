"""
Status Kalibrasi - baca file kalibrasi program-python (read-only).

TIDAK menjalankan kalibrasi; hanya menampilkan status file kalibrasi yang
sudah dibuat oleh script tahap* di program-python. Path dikurung ke
PROGRAM_PYTHON_BASE supaya tidak bisa membaca file di luar folder itu.
"""

import json
import os
from datetime import datetime


_CALIBRATIONS = [
    {
        'name': 'Kalibrasi Kamera (Undistort)',
        'file': 'hasil_tahap4/undistort_info.json',
        'fields': [('Perangkat', 'camera_device'),
                   ('Lebar frame', 'frame_width'),
                   ('Tinggi frame', 'frame_height')],
    },
    {
        'name': 'Titik Sudut Workspace',
        'file': 'hasil_tahap4/points_4_corners_undistorted.json',
        'fields': [],
        'note': 'Empat titik sudut area kerja (hasil pemilihan manual).',
    },
    {
        'name': 'Warp Perspektif (Top-Down)',
        'file': 'hasil_tahap5_undistorted/warp_info.json',
        'fields': [],
    },
    {
        'name': 'Skala Piksel ke cm',
        'file': 'hasil_tahap6/pixel_scale.json',
        'fields': [('Panjang workspace (cm)', 'workspace_panjang_cm'),
                   ('Lebar workspace (cm)', 'workspace_lebar_cm')],
    },
    {
        'name': 'Tinggi Dasar Ultrasonik',
        'file': 'hasil_tahap9/ultrasonic_calibration.json',
        'fields': [('Jarak dasar (cm)', 'base_distance_cm'),
                   ('Jumlah sampel', 'filtered_sample_count')],
    },
    {
        'name': 'Titik Sensor Ultrasonik',
        'file': 'hasil_tahap10/sensor_point.json',
        'fields': [('Koordinat X', 'x'), ('Koordinat Y', 'y')],
    },
    {
        'name': 'Kalibrasi Loadcell (Timbangan)',
        'file': 'hasil_tahap11/loadcell_calibration.json',
        'fields': [('Faktor kalibrasi', 'calibration_factor'),
                   ('Berat referensi (g)', 'reference_weight_g'),
                   ('Offset', 'offset_final')],
    },
]

_NPZ = {
    'name': 'Matriks Kalibrasi Kamera (.npz)',
    'file': 'camera_calibration.npz',
}


def _safe_path(base, rel):
    base_real = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_real, rel))
    if target == base_real or target.startswith(base_real + os.sep):
        return target
    return None


def _format_age(epoch):
    days = int((datetime.now().timestamp() - epoch) // 86400)
    if days <= 0:
        return 'hari ini'
    if days == 1:
        return '1 hari lalu'
    return str(days) + ' hari lalu'


def _timestamp_info(raw, path):
    ts_str = None
    epoch = None
    if isinstance(raw, dict) and raw.get('timestamp'):
        ts_str = str(raw['timestamp'])
        try:
            epoch = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S').timestamp()
        except ValueError:
            epoch = None
    if epoch is None:
        try:
            epoch = os.path.getmtime(path)
            ts_str = datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M')
        except OSError:
            ts_str = None
    return ts_str, epoch


def _fmt_value(v):
    if isinstance(v, float):
        return ('%.3f' % v).rstrip('0').rstrip('.')
    return str(v)


def _build_item(base, spec):
    item = {'name': spec['name'], 'file': spec['file'],
            'exists': False, 'timestamp': None, 'age': None,
            'details': [], 'note': spec.get('note', '')}
    path = _safe_path(base, spec['file'])
    if not path or not os.path.isfile(path):
        return item
    item['exists'] = True
    raw = _read_json(path) if spec['file'].endswith('.json') else None
    ts_str, epoch = _timestamp_info(raw, path)
    item['timestamp'] = ts_str
    if epoch is not None:
        item['age'] = _format_age(epoch)
    if isinstance(raw, dict):
        for label, key in spec.get('fields', []):
            if key in raw:
                item['details'].append((label, _fmt_value(raw[key])))
    elif isinstance(raw, list):
        item['details'].append(('Jumlah titik', str(len(raw))))
    return item


def _read_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def get_calibration_status():
    """Kembalikan ringkasan + daftar status tiap kalibrasi (read-only)."""
    from config.settings import PROGRAM_PYTHON_BASE

    if not PROGRAM_PYTHON_BASE or not os.path.isdir(PROGRAM_PYTHON_BASE):
        return {'available': False, 'entries': [], 'ready': 0, 'total': 0,
                'base': PROGRAM_PYTHON_BASE or ''}

    items = [_build_item(PROGRAM_PYTHON_BASE, s) for s in _CALIBRATIONS]
    items.append(_build_item(PROGRAM_PYTHON_BASE, _NPZ))
    ready = sum(1 for it in items if it['exists'])
    return {'available': True, 'entries': items, 'ready': ready,
            'total': len(items), 'base': PROGRAM_PYTHON_BASE}
