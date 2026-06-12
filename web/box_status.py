"""
Status Box (tombol + lampu) - baca file status dari tahap17 (read-only).

tahap17 (box controller) menulis hasil_tahap17/box_status.json saat transisi
mode + heartbeat tiap loop. Dashboard membaca file itu. Decoupled: kalau
file tidak ada / basi, box dianggap OFFLINE (tahap17 tidak berjalan).
Path dikurung ke PROGRAM_PYTHON_BASE.
"""

import json
import os
from datetime import datetime


_STATUS_FILE = "hasil_tahap17/box_status.json"
_STALE_SECONDS = 5


def _safe_path(base, rel):
    base_real = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_real, rel))
    if target == base_real or target.startswith(base_real + os.sep):
        return target
    return None


def get_box_status():
    """Status box live: mode, lampu, tahap18, online/offline (read-only)."""
    from config.settings import PROGRAM_PYTHON_BASE

    offline = {'online': False, 'mode': None,
               'lamps': {'hijau': False, 'kuning': False, 'merah': False},
               'tahap18_running': False, 'timestamp': None, 'age_seconds': None}

    if not PROGRAM_PYTHON_BASE or not os.path.isdir(PROGRAM_PYTHON_BASE):
        return offline

    path = _safe_path(PROGRAM_PYTHON_BASE, _STATUS_FILE)
    if not path or not os.path.isfile(path):
        return offline

    try:
        with open(path, 'r') as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return offline

    age = None
    ts = raw.get('timestamp')
    if ts:
        try:
            age = datetime.now().timestamp() - \
                datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').timestamp()
        except ValueError:
            age = None
    if age is None:
        try:
            age = datetime.now().timestamp() - os.path.getmtime(path)
        except OSError:
            age = None

    online = age is not None and age <= _STALE_SECONDS
    lamps = raw.get('lamps') or {}
    return {
        'online': online,
        'mode': raw.get('mode') if online else None,
        'lamps': {
            'hijau': bool(lamps.get('hijau')) if online else False,
            'kuning': bool(lamps.get('kuning')) if online else False,
            'merah': bool(lamps.get('merah')) if online else False,
        },
        'tahap18_running': bool(raw.get('tahap18_running')) if online else False,
        'timestamp': ts,
        'age_seconds': round(age, 1) if age is not None else None,
    }
