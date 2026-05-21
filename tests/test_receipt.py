"""
Unit Tests for Receipt Route
Tests untuk halaman Cetak Resi (web/routes.py + receipt.html)
Uses Mock InMemoryStorage for isolated testing
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web.routes as routes
routes._use_firebase = False
routes._storage = None

from web import create_app


class TestReceiptRoute:
    """Test suite for GET /receipt/<package_id>"""

    @pytest.fixture(autouse=True)
    def reset_storage(self):
        routes._storage = routes.InMemoryStorage()
        routes._use_firebase = False

    @pytest.fixture
    def app(self):
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def _create_package(self, client):
        client.post('/api/reset')
        response = client.post('/api/measure')
        data = json.loads(response.data)
        assert data['success'] is True
        return data['data']

    # =========================================================================
    # Status / availability
    # =========================================================================

    def test_receipt_returns_200_when_package_exists(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        assert response.status_code == 200

    def test_receipt_returns_404_when_package_missing(self, client):
        response = client.get('/receipt/99999')
        assert response.status_code == 404

    def test_receipt_404_message_in_indonesian(self, client):
        response = client.get('/receipt/99999')
        assert response.status_code == 404
        assert b'Paket tidak ditemukan' in response.data

    # =========================================================================
    # Content rendering
    # =========================================================================

    def test_receipt_contains_package_id(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')
        expected_id = "PKT-" + str(package['id']).zfill(5)
        assert expected_id in body

    def test_receipt_contains_dimensions(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        assert 'Panjang' in body
        assert 'Lebar' in body
        assert 'Tinggi' in body
        assert 'DIMENSI' in body

        assert "{:.2f}".format(package['dimensions']['panjang']) in body
        assert "{:.2f}".format(package['dimensions']['lebar']) in body
        assert "{:.2f}".format(package['dimensions']['tinggi']) in body

    def test_receipt_contains_weight_fields(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        assert 'BERAT' in body
        assert 'Aktual' in body
        assert 'Volumetrik' in body
        assert 'Tagihan' in body

        assert "{:.1f}".format(package['weight']['aktual']) in body
        assert "{:.1f}".format(package['weight']['volumetrik']) in body
        assert "{:.1f}".format(package['weight']['chargeable']) in body

    def test_receipt_contains_service_type(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')
        assert package['service_type'] in body
        assert 'LAYANAN' in body

    def test_receipt_contains_price_indonesian_format(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        expected_price = "Rp {:,.0f}".format(package['price']).replace(",", ".")
        assert expected_price in body

    # =========================================================================
    # Standalone page (no base layout / sidebar / navbar)
    # =========================================================================

    def test_receipt_does_not_include_sidebar(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        assert 'carbon-sidenav' not in body
        assert 'carbon-header__nav' not in body
        assert 'carbon-shell' not in body

    def test_receipt_includes_print_script(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        assert 'window.print()' in body
        assert '@media print' in body

    def test_receipt_has_kembali_and_cetak_controls(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        assert 'Cetak' in body
        assert 'Kembali' in body

    # =========================================================================
    # Optional fields (measurement_id, weight.source)
    # =========================================================================

    def test_receipt_omits_measurement_id_when_absent(self, client):
        package = self._create_package(client)
        response = client.get(f"/receipt/{package['id']}")
        body = response.data.decode('utf-8')

        assert 'ID Ukur' not in body

    def test_receipt_renders_measurement_id_when_present(self, client):
        storage = routes.get_storage()
        package_id = storage.save_package({
            'dimensions': {'panjang': 12.34, 'lebar': 5.67, 'tinggi': 8.9},
            'weight': {
                'aktual': 250.0,
                'volumetrik': 100.0,
                'chargeable': 250.0,
                'source': 'actual',
            },
            'measurement_id': 'meas-test-123',
            'service_type': 'REGULER',
            'price': 6000,
        })

        response = client.get(f"/receipt/{package_id}")
        assert response.status_code == 200
        body = response.data.decode('utf-8')

        assert 'ID Ukur' in body
        assert 'meas-test-123' in body
        assert 'Sumber' in body
        assert 'actual' in body

    # =========================================================================
    # Indonesian timestamp formatting
    # =========================================================================

    def test_receipt_uses_indonesian_month_name(self, client):
        from datetime import datetime

        storage = routes.get_storage()
        storage.packages.append({
            'id': 99,
            'timestamp': datetime(2026, 5, 21, 14, 32, 12).isoformat(),
            'dimensions': {'panjang': 10.0, 'lebar': 8.0, 'tinggi': 5.0},
            'weight': {'aktual': 600.0, 'volumetrik': 75.0, 'chargeable': 600.0},
            'service_type': 'REGULER',
            'price': 6000,
        })

        response = client.get('/receipt/99')
        assert response.status_code == 200
        body = response.data.decode('utf-8')

        assert '21 Mei 2026' in body
        assert '14:32' in body


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
