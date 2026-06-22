"""
Unit Tests for Web API Endpoints
Tests untuk modul web/routes.py
Uses Mock Storage (not Firebase) for isolated testing
"""

import pytest
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force routes to use MockStorage for testing
import web.routes as routes
routes._storage = None  # Will reinitialize with InMemory

from web import create_app


class TestWebAPI:
    """Test suite for Flask API endpoints"""
    
    @pytest.fixture(autouse=True)
    def reset_storage(self):
        """Reset storage before each test"""
        routes._storage = routes.InMemoryStorage()
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    # =========================================================================
    # Status Endpoint Tests
    # =========================================================================
    
    def test_status_endpoint(self, client):
        """Test GET /api/status"""
        response = client.get('/api/status')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
    
    def test_status_contains_mode(self, client):
        """Test status contains mode field"""
        response = client.get('/api/status')
        data = json.loads(response.data)
        
        assert 'mode' in data['data']
        assert data['data']['mode'] in ['mock', 'real', 'file', 'unknown']
    
    def test_status_contains_statistics(self, client):
        """Test status contains statistics"""
        response = client.get('/api/status')
        data = json.loads(response.data)
        
        assert 'statistics' in data['data']
        stats = data['data']['statistics']
        assert 'REGULER' in stats
        assert 'EXPRESS' in stats
        assert 'KARGO' in stats
    
    def test_status_contains_timestamp(self, client):
        """Test status contains timestamp"""
        response = client.get('/api/status')
        data = json.loads(response.data)
        
        assert 'timestamp' in data['data']
    
    # =========================================================================
    # Measure Endpoint Tests
    # =========================================================================
    
    def test_measure_endpoint(self, client):
        """Test POST /api/measure"""
        response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_measure_rejects_missing_sender(self, client):
        response = client.post('/api/measure', json={
            'recipient': {'nama': 'Siti'},
        })
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error_type'] == 'missing_sender'

    def test_measure_rejects_missing_recipient(self, client):
        response = client.post('/api/measure', json={
            'sender': {'nama': 'Budi'},
        })
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error_type'] == 'missing_recipient'

    def test_measure_rejects_empty_body(self, client):
        response = client.post('/api/measure')
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error_type'] == 'missing_sender'

    def test_measure_persists_sender_and_recipient(self, client):
        response = client.post('/api/measure', json={
            'sender': {'nama': 'Budi', 'telepon': '08123', 'alamat': 'Jl A'},
            'recipient': {'nama': 'Siti', 'telepon': '08456', 'alamat': 'Jl B'},
        })
        assert response.status_code == 200
        package = json.loads(response.data)['data']
        assert package['sender']['nama'] == 'Budi'
        assert package['sender']['telepon'] == '08123'
        assert package['recipient']['nama'] == 'Siti'
        assert package['recipient']['alamat'] == 'Jl B'
    
    def test_measure_returns_package_data(self, client):
        """Test measure returns complete package data"""
        response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        data = json.loads(response.data)
        
        package = data['data']
        assert 'id' in package
        assert 'timestamp' in package
        assert 'dimensions' in package
        assert 'weight' in package
        assert 'service_type' in package
        assert 'price' in package
    
    def test_measure_dimensions_structure(self, client):
        """Test dimensions structure"""
        response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        data = json.loads(response.data)
        
        dims = data['data']['dimensions']
        assert 'panjang' in dims
        assert 'lebar' in dims
        assert 'tinggi' in dims
        
        # Check values are positive
        assert dims['panjang'] > 0
        assert dims['lebar'] > 0
        assert dims['tinggi'] > 0
    
    def test_measure_weight_structure(self, client):
        """Test weight structure"""
        response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        data = json.loads(response.data)
        
        weight = data['data']['weight']
        assert 'aktual' in weight
        assert 'volumetrik' in weight
        assert 'chargeable' in weight
        
        # Chargeable should be max of aktual and volumetrik
        assert weight['chargeable'] == max(weight['aktual'], weight['volumetrik'])
    
    def test_measure_valid_service_type(self, client):
        """Test service type is valid"""
        response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        data = json.loads(response.data)
        
        service_type = data['data']['service_type']
        assert service_type in ['REGULER', 'EXPRESS', 'KARGO']
    
    def test_measure_valid_price(self, client):
        """Test price matches service type"""
        response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        data = json.loads(response.data)
        
        service_type = data['data']['service_type']
        price = data['data']['price']
        
        expected_prices = {
            'REGULER': 6000,
            'EXPRESS': 12000,
            'KARGO': 5000
        }
        assert price == expected_prices[service_type]
    
    def test_measure_increments_id(self, client):
        """Test package ID increments"""
        # Reset first
        client.post('/api/reset')
        
        response1 = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        response2 = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        
        # InMemoryStorage uses integer IDs
        id1 = data1['data']['id']
        id2 = data2['data']['id']
        
        # Handle both string and int IDs
        if isinstance(id1, str) and id1.isdigit():
            id1 = int(id1)
            id2 = int(id2)
        elif isinstance(id1, int):
            pass  # Already int
        else:
            # String IDs (Firebase-style) - just check they're different
            assert id1 != id2
            return
        
        assert id2 == id1 + 1
    
    # =========================================================================
    # History Endpoint Tests
    # =========================================================================
    
    def test_history_endpoint(self, client):
        """Test GET /api/history"""
        response = client.get('/api/history')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_history_structure(self, client):
        """Test history response structure"""
        response = client.get('/api/history')
        data = json.loads(response.data)
        
        assert 'packages' in data['data']
        assert 'total' in data['data']
        assert 'limit' in data['data']
        assert 'offset' in data['data']
    
    def test_history_after_measure(self, client):
        """Test history contains measured packages"""
        # Reset and measure
        client.post('/api/reset')
        client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        response = client.get('/api/history')
        data = json.loads(response.data)
        
        assert data['data']['total'] == 1
        assert len(data['data']['packages']) == 1
    
    def test_history_limit_parameter(self, client):
        """Test history limit parameter"""
        # Create multiple packages
        client.post('/api/reset')
        for _ in range(5):
            client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        response = client.get('/api/history?limit=3')
        data = json.loads(response.data)
        
        assert len(data['data']['packages']) == 3
    
    def test_history_filter_by_type(self, client):
        """Test history filter by service type"""
        response = client.get('/api/history?type=REGULER')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # All packages should be REGULER (or empty)
        for pkg in data['data']['packages']:
            assert pkg['service_type'] == 'REGULER'
    
    def test_history_single_package(self, client):
        """Test GET /api/history/<id>"""
        client.post('/api/reset')
        measure_response = client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        pkg_id = json.loads(measure_response.data)['data']['id']
        
        response = client.get(f'/api/history/{pkg_id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        # Compare as strings to handle both int and string IDs
        assert str(data['data']['id']) == str(pkg_id)
    
    def test_history_package_not_found(self, client):
        """Test GET /api/history/<id> with invalid ID"""
        response = client.get('/api/history/99999')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
    
    # =========================================================================
    # Statistics Endpoint Tests
    # =========================================================================
    
    def test_statistics_endpoint(self, client):
        """Test GET /api/statistics"""
        response = client.get('/api/statistics')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_statistics_structure(self, client):
        """Test statistics response structure"""
        response = client.get('/api/statistics')
        data = json.loads(response.data)
        
        assert 'total_packages' in data['data']
        assert 'total_revenue' in data['data']
        assert 'by_service_type' in data['data']
    
    def test_statistics_by_type_structure(self, client):
        """Test by_service_type structure"""
        response = client.get('/api/statistics')
        data = json.loads(response.data)
        
        by_type = data['data']['by_service_type']
        for service in ['REGULER', 'EXPRESS', 'KARGO']:
            assert service in by_type
            assert 'count' in by_type[service]
            assert 'revenue' in by_type[service]
    
    def test_statistics_after_measure(self, client):
        """Test statistics updates after measure"""
        client.post('/api/reset')
        
        # Get initial stats
        initial = client.get('/api/statistics')
        initial_data = json.loads(initial.data)['data']
        
        # Measure
        client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        # Get updated stats
        updated = client.get('/api/statistics')
        updated_data = json.loads(updated.data)['data']
        
        assert updated_data['total_packages'] == initial_data['total_packages'] + 1
    
    # =========================================================================
    # Reset Endpoint Tests
    # =========================================================================
    
    def test_reset_endpoint(self, client):
        """Test POST /api/reset"""
        response = client.post('/api/reset')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_reset_clears_history(self, client):
        """Test reset clears all history"""
        # Create some packages
        for _ in range(3):
            client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        # Reset
        client.post('/api/reset')
        
        # Check history is empty
        response = client.get('/api/history')
        data = json.loads(response.data)
        
        assert data['data']['total'] == 0
        assert len(data['data']['packages']) == 0
    
    def test_reset_clears_statistics(self, client):
        """Test reset clears statistics"""
        # Create some packages
        for _ in range(3):
            client.post('/api/measure', json={'sender': {'nama': 'Budi'}, 'recipient': {'nama': 'Siti'}})
        
        # Reset
        client.post('/api/reset')
        
        # Check statistics
        response = client.get('/api/statistics')
        data = json.loads(response.data)
        
        assert data['data']['total_packages'] == 0
        assert data['data']['total_revenue'] == 0
    
    # =========================================================================
    # Page Endpoints Tests
    # =========================================================================
    
    def test_dashboard_page(self, client):
        """Test GET /dashboard"""
        response = client.get('/dashboard')
        
        assert response.status_code == 200
        assert b'Dashboard' in response.data or b'dashboard' in response.data
    
    def test_history_page(self, client):
        """Test GET /history"""
        response = client.get('/history')
        
        assert response.status_code == 200
    
    def test_manual_page(self, client):
        """Test GET /manual"""
        response = client.get('/manual')
        
        assert response.status_code == 200
    
    def test_root_redirect(self, client):
        """Test GET / renders dashboard"""
        response = client.get('/')
        
        assert response.status_code == 200


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in API"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app = create_app()
        app.config['TESTING'] = True
        return app.test_client()
    
    def test_invalid_method_measure(self, client):
        """Test GET /api/measure returns error"""
        response = client.get('/api/measure')
        
        assert response.status_code == 405  # Method Not Allowed
    
    def test_invalid_endpoint(self, client):
        """Test invalid endpoint returns 404"""
        response = client.get('/api/invalid')
        
        assert response.status_code == 404


class TestServerSentEvents:
    """Test SSE (Server-Sent Events) endpoints"""
    
    @pytest.fixture(autouse=True)
    def reset_storage(self):
        """Reset storage before each test"""
        routes._storage = routes.InMemoryStorage()
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_sse_endpoint_exists(self, client):
        """Test SSE endpoint returns correct content type"""
        response = client.get('/api/events')
        
        assert response.status_code == 200
        assert 'text/event-stream' in response.content_type
    
    def test_sse_test_endpoint(self, client):
        """Test SSE test broadcast endpoint"""
        response = client.post('/api/events/test')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'connected_clients' in data
    
    def test_sync_endpoint(self, client):
        """Test sync endpoint"""
        response = client.post('/api/sync')
        
        # Without Firebase, should fail gracefully
        assert response.status_code in [200, 400]


class TestFormDraftAPI:
    """Tests for /api/form/draft endpoints (auto-save sender/recipient)."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        routes._storage = routes.InMemoryStorage()
        from web import mpc_store
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        mpc_store._DATA_PATH = tmp.name
        mpc_store._loaded[0] = False
        mpc_store.reset()
        yield
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    @pytest.fixture
    def app(self):
        app = routes.create_app() if hasattr(routes, 'create_app') else None
        if app is None:
            from web import create_app
            app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        c = app.test_client()
        with c.session_transaction() as sess:
            sess['user'] = {
                'username': 'mitra_test',
                'role': 'mitra',
                'mitra_id': 'MITRA-001',
                'name': 'Test Mitra',
            }
        return c

    def test_save_draft_returns_persisted_payload(self, client):
        r = client.post('/api/form/draft', json={
            'sender': {'nama': 'Budi', 'telepon': '081', 'alamat': 'Jl A'},
            'recipient': {'nama': 'Sari', 'telepon': '082', 'alamat': 'Jl B'},
        })
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        draft = body['data']['draft']
        assert draft['sender']['nama'] == 'Budi'
        assert draft['recipient']['nama'] == 'Sari'
        assert draft['mitra_id'] == 'MITRA-001'

    def test_get_draft_after_save(self, client):
        client.post('/api/form/draft', json={
            'sender': {'nama': 'Budi'},
            'recipient': {'nama': 'Sari'},
        })
        r = client.get('/api/form/draft')
        assert r.status_code == 200
        draft = r.get_json()['data']['draft']
        assert draft['sender']['nama'] == 'Budi'

    def test_get_draft_empty_returns_none(self, client):
        r = client.get('/api/form/draft')
        assert r.status_code == 200
        assert r.get_json()['data']['draft'] is None

    def test_save_empty_clears_draft(self, client):
        client.post('/api/form/draft', json={
            'sender': {'nama': 'Budi'},
        })
        r = client.post('/api/form/draft', json={
            'sender': {'nama': '', 'telepon': '', 'alamat': ''},
            'recipient': {'nama': '', 'telepon': '', 'alamat': ''},
        })
        assert r.status_code == 200
        assert r.get_json()['data']['draft'] is None
        g = client.get('/api/form/draft')
        assert g.get_json()['data']['draft'] is None

    def test_delete_clears_draft(self, client):
        client.post('/api/form/draft', json={'sender': {'nama': 'Budi'}})
        r = client.delete('/api/form/draft')
        assert r.status_code == 200
        assert client.get('/api/form/draft').get_json()['data']['draft'] is None

    def test_draft_scoped_per_mitra(self, app):
        c1 = app.test_client()
        with c1.session_transaction() as s:
            s['user'] = {'username': 'm1', 'role': 'mitra', 'mitra_id': 'MITRA-001'}
        c2 = app.test_client()
        with c2.session_transaction() as s:
            s['user'] = {'username': 'm2', 'role': 'mitra', 'mitra_id': 'MITRA-002'}
        c1.post('/api/form/draft', json={'sender': {'nama': 'A'}})
        c2.post('/api/form/draft', json={'sender': {'nama': 'B'}})
        d1 = c1.get('/api/form/draft').get_json()['data']['draft']
        d2 = c2.get('/api/form/draft').get_json()['data']['draft']
        assert d1['sender']['nama'] == 'A'
        assert d2['sender']['nama'] == 'B'

    def test_non_mitra_user_rejected_on_save(self, app):
        c = app.test_client()
        with c.session_transaction() as s:
            s['user'] = {'username': 'admin', 'role': 'admin'}
        r = c.post('/api/form/draft', json={'sender': {'nama': 'X'}})
        assert r.status_code == 403
        assert r.get_json()['error_type'] == 'not_a_mitra'


class TestPackagePartiesPatch:
    """Tests for PATCH /api/packages/<id>/parties (backfill legacy packages)."""

    @pytest.fixture(autouse=True)
    def reset_storage(self):
        routes._storage = routes.InMemoryStorage()
        yield

    @pytest.fixture
    def app(self):
        from web import create_app
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        c = app.test_client()
        with c.session_transaction() as s:
            s['user'] = {
                'username': 'mitra_test',
                'role': 'mitra',
                'mitra_id': 'MITRA-001',
                'name': 'Test Mitra',
            }
        return c

    def _seed_legacy(self, mitra_id='MITRA-001'):
        pid = routes._storage.save_package({
            'mitra_id': mitra_id,
            'mitra_name': 'Mitra A',
            'dimensions': {'panjang': 10, 'lebar': 10, 'tinggi': 10},
            'weight': {'aktual': 100, 'volumetrik': 100, 'chargeable': 100,
                       'source': 'volumetric'},
            'service_type': 'REGULER',
            'price': 10000,
            'data_source': 'box_tahap18',
        })
        return pid

    def test_patch_sets_sender_only(self, client):
        pid = self._seed_legacy()
        r = client.patch(f'/api/packages/{pid}/parties', json={
            'sender': {'nama': 'Budi', 'telepon': '081', 'alamat': 'Jl A'},
        })
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        pkg = body['data']['package']
        assert pkg['sender']['nama'] == 'Budi'
        assert 'recipient' not in pkg

    def test_patch_sets_both(self, client):
        pid = self._seed_legacy()
        r = client.patch(f'/api/packages/{pid}/parties', json={
            'sender': {'nama': 'Budi'},
            'recipient': {'nama': 'Sari'},
        })
        assert r.status_code == 200
        pkg = r.get_json()['data']['package']
        assert pkg['sender']['nama'] == 'Budi'
        assert pkg['recipient']['nama'] == 'Sari'

    def test_patch_missing_package_returns_404(self, client):
        r = client.patch('/api/packages/9999/parties', json={
            'sender': {'nama': 'Budi'},
        })
        assert r.status_code == 404
        assert r.get_json()['error_type'] == 'not_found'

    def test_patch_empty_payload_rejected(self, client):
        pid = self._seed_legacy()
        r = client.patch(f'/api/packages/{pid}/parties', json={})
        assert r.status_code == 422
        assert r.get_json()['error_type'] == 'empty_payload'

    def test_patch_blank_sender_name_rejected(self, client):
        pid = self._seed_legacy()
        r = client.patch(f'/api/packages/{pid}/parties', json={
            'sender': {'nama': '', 'telepon': '081', 'alamat': ''},
        })
        assert r.status_code == 422
        assert r.get_json()['error_type'] == 'missing_sender_name'

    def test_patch_blank_recipient_name_rejected(self, client):
        pid = self._seed_legacy()
        r = client.patch(f'/api/packages/{pid}/parties', json={
            'recipient': {'nama': '', 'telepon': '081', 'alamat': ''},
        })
        assert r.status_code == 422
        assert r.get_json()['error_type'] == 'missing_recipient_name'

    def test_patch_other_mitra_package_returns_404(self, app):
        c1 = app.test_client()
        with c1.session_transaction() as s:
            s['user'] = {'username': 'm1', 'role': 'mitra', 'mitra_id': 'MITRA-001'}
        pid = self._seed_legacy(mitra_id='MITRA-002')

        r = c1.patch(f'/api/packages/{pid}/parties', json={
            'sender': {'nama': 'Hacker'},
        })
        assert r.status_code == 404
        pkg = routes._storage.get_package(pid)
        assert pkg.get('sender') is None or pkg.get('sender', {}).get('nama') != 'Hacker'


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
