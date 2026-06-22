"""Test arm/cancel/consume state machine di mpc_store."""
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from unittest import mock

import pytest


@pytest.fixture
def store(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    config_dir = os.path.join(tmpdir, "config")
    os.makedirs(config_dir, exist_ok=True)
    from web import mpc_store
    monkeypatch.setattr(mpc_store, "_DATA_PATH",
                        os.path.join(config_dir, "mpc_data.json"))
    mpc_store._validations.clear()
    mpc_store._attempts.clear()
    mpc_store._notifications.clear()
    mpc_store._notif_counter[0] = 0
    mpc_store._armed[0] = None
    mpc_store._loaded[0] = True
    yield mpc_store
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_arm_starts_empty(store):
    assert store.get_armed() is None


def test_arm_success(store):
    ok, arm = store.arm_mpc(500, armed_by="mpc_user")
    assert ok is True
    assert arm["package_id"] == "500"
    assert arm["armed_by"] == "mpc_user"
    assert arm["status"] == "armed"
    assert store.get_armed() is not None


def test_arm_persists_across_reload(store):
    store.arm_mpc(500, armed_by="mpc_user")
    store._loaded[0] = False
    store._armed[0] = None
    arm = store.get_armed()
    assert arm is not None
    assert arm["package_id"] == "500"


def test_arm_rejects_when_other_package_active(store):
    ok1, _ = store.arm_mpc(500, armed_by="mpc1")
    assert ok1 is True
    ok2, existing = store.arm_mpc(501, armed_by="mpc2")
    assert ok2 is False
    assert existing["package_id"] == "500"


def test_arm_refresh_same_package(store):
    ok, arm1 = store.arm_mpc(500, armed_by="mpc_user", timeout_seconds=10)
    time.sleep(0.01)
    ok2, arm2 = store.arm_mpc(500, armed_by="mpc_user", timeout_seconds=10)
    assert ok2 is True
    assert arm2["expires_at"] >= arm1["expires_at"]


def test_cancel_armed(store):
    store.arm_mpc(500, armed_by="mpc_user")
    cleared = store.cancel_armed(by_user="mpc_user")
    assert cleared is not None
    assert cleared["package_id"] == "500"
    assert cleared["cleared_reason"] == "cancelled"
    assert store.get_armed() is None


def test_cancel_when_no_arm(store):
    assert store.cancel_armed() is None


def test_consume_armed_success(store):
    store.arm_mpc(500, armed_by="mpc_user")
    consumed = store.consume_armed("integrated_20260623_120000")
    assert consumed is not None
    assert consumed["package_id"] == "500"
    assert consumed["consumed_measurement_id"] == "integrated_20260623_120000"
    assert store.get_armed() is None


def test_consume_armed_idempotent(store):
    store.arm_mpc(500, armed_by="mpc_user")
    first = store.consume_armed("mid_1")
    second = store.consume_armed("mid_2")
    assert first is not None
    assert second is None


def test_consume_armed_with_package_filter(store):
    store.arm_mpc(500, armed_by="mpc_user")
    no_match = store.consume_armed("mid_1", expected_package_id=999)
    assert no_match is None
    assert store.get_armed() is not None
    match = store.consume_armed("mid_2", expected_package_id=500)
    assert match is not None


def test_arm_expires_after_timeout(store):
    ok, _ = store.arm_mpc(500, armed_by="mpc_user", timeout_seconds=1)
    assert ok is True
    past = (datetime.now() - timedelta(seconds=5)).isoformat()
    store._armed[0]["expires_at"] = past
    store._save_locked()
    assert store.get_armed() is None
    consumed = store.consume_armed("mid_1")
    assert consumed is None


def test_arm_returns_dict_copy_not_reference(store):
    _, arm = store.arm_mpc(500, armed_by="mpc_user")
    arm["mutated"] = True
    again = store.get_armed()
    assert "mutated" not in again
