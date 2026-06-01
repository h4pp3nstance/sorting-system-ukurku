"""
Unit Tests for web/settings_store.py (Fitur B - Admin settings)
Laptop-safe: pure JSON store, no hardware.
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import settings_store as store


class TestSettingsStore:
    def setup_method(self):
        # Redirect store ke file sementara per test
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        self._tmp.close()
        os.unlink(self._tmp.name)  # mulai dari "belum ada" agar seed jalan
        self._orig_path = store._SETTINGS_PATH
        store._SETTINGS_PATH = self._tmp.name

    def teardown_method(self):
        store._SETTINGS_PATH = self._orig_path
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_seeds_defaults_when_missing(self):
        settings = store.load_settings()
        assert "toleransi" in settings
        assert "tarif" in settings
        assert settings["toleransi"]["dimensi_cm"] == 1.0
        assert settings["tarif"]["REGULER"] == 6000

    def test_seed_writes_file(self):
        store.load_settings()
        assert os.path.exists(self._tmp.name)

    def test_update_tolerances_partial(self):
        store.load_settings()
        result = store.update_tolerances(dimensi_cm=2.5)
        assert result["toleransi"]["dimensi_cm"] == 2.5
        # field lain tidak berubah
        assert result["toleransi"]["berat_aktual_g"] == 50.0

    def test_update_tolerances_persists(self):
        store.update_tolerances(berat_tagihan_g=200)
        reloaded = store.load_settings()
        assert reloaded["toleransi"]["berat_tagihan_g"] == 200.0

    def test_update_tariffs_partial(self):
        store.update_tariffs(express=15000)
        tarif = store.get_tariffs()
        assert tarif["EXPRESS"] == 15000
        assert tarif["REGULER"] == 6000

    def test_invalid_number_keeps_old_value(self):
        result = store.update_tolerances(dimensi_cm="bukan-angka")
        assert result["toleransi"]["dimensi_cm"] == 1.0

    def test_corrupted_file_reseeds(self):
        with open(self._tmp.name, "w") as f:
            f.write("{ rusak json")
        settings = store.load_settings()
        assert settings["tarif"]["KARGO"] == 5000

    def test_merge_defaults_fills_missing_keys(self):
        with open(self._tmp.name, "w") as f:
            json.dump({"tarif": {"REGULER": 7000}}, f)
        settings = store.load_settings()
        assert settings["tarif"]["REGULER"] == 7000
        assert "toleransi" in settings
        assert settings["toleransi"]["dimensi_cm"] == 1.0

    def test_get_tolerances_and_tariffs(self):
        assert "dimensi_cm" in store.get_tolerances()
        assert "REGULER" in store.get_tariffs()
