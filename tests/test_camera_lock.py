"""Tests for web.camera_lock - koordinasi kamera web vs tahap18 CLI."""

import pytest

from web import camera_lock


def _patch_pids(monkeypatch, pids):
    monkeypatch.setattr(camera_lock, 'tahap18_pids', lambda: list(pids))


def test_is_tahap18_active_false_when_no_pids(monkeypatch):
    _patch_pids(monkeypatch, [])
    assert camera_lock.is_tahap18_active() is False


def test_is_tahap18_active_true_when_pid_present(monkeypatch):
    _patch_pids(monkeypatch, [12345])
    assert camera_lock.is_tahap18_active() is True


def test_ensure_web_can_use_camera_ok_when_idle(monkeypatch):
    _patch_pids(monkeypatch, [])
    ok, msg, pids = camera_lock.ensure_web_can_use_camera()
    assert ok is True
    assert msg == ''
    assert pids == []


def test_ensure_web_can_use_camera_blocked_when_tahap18_runs(monkeypatch):
    _patch_pids(monkeypatch, [9999, 10000])
    ok, msg, pids = camera_lock.ensure_web_can_use_camera()
    assert ok is False
    assert 'tahap18' in msg.lower() or 'pb on' in msg.lower()
    assert pids == [9999, 10000]


def test_status_payload_idle(monkeypatch):
    _patch_pids(monkeypatch, [])
    p = camera_lock.status_payload()
    assert p['tahap18_active'] is False
    assert p['tahap18_pids'] == []
    assert p['web_can_use_camera'] is True


def test_status_payload_busy(monkeypatch):
    _patch_pids(monkeypatch, [1111])
    p = camera_lock.status_payload()
    assert p['tahap18_active'] is True
    assert p['tahap18_pids'] == [1111]
    assert p['web_can_use_camera'] is False


def test_camera_busy_error_carries_pids():
    err = camera_lock.CameraBusyError('busy', pids=[42, 43])
    assert err.pids == [42, 43]
    assert str(err) == 'busy'


def test_camera_busy_error_default_pids_empty():
    err = camera_lock.CameraBusyError('busy')
    assert err.pids == []


def test_tahap18_pids_handles_import_failure(monkeypatch):
    """Kalau system_control gagal di-import (env tanpa /proc), kembali list kosong."""
    import sys
    saved = sys.modules.pop('web.system_control', None)
    monkeypatch.setattr(
        'builtins.__import__',
        lambda name, *a, **kw: (_ for _ in ()).throw(ImportError(name))
        if name == 'web.system_control'
        else __import__(name, *a, **kw)
    )
    try:
        assert camera_lock.tahap18_pids() == []
        assert camera_lock.is_tahap18_active() is False
    finally:
        if saved is not None:
            sys.modules['web.system_control'] = saved
