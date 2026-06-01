"""
Unit Tests for In-Memory Storage Handler
Tests untuk storage/memory_handler.py
"""

import pytest
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.memory_handler import MemoryStorageHandler
from storage.factory import create_storage_handler
from storage.base import IStorageHandler


# =============================================================================
# In-Memory Storage Handler Tests
# =============================================================================

class TestMemoryStorageHandler:
    """Test suite for MemoryStorageHandler"""
    
    @pytest.fixture
    def handler(self):
        """Create MemoryStorageHandler instance"""
        h = MemoryStorageHandler()
        h.connect()
        return h
    
    @pytest.fixture
    def sample_package(self):
        """Sample package data"""
        return {
            'panjang': 15.0,
            'lebar': 10.0,
            'tinggi': 8.0,
            'berat_aktual': 500.0,
            'berat_volumetrik': 200.0,
            'chargeable_weight': 500.0,
            'service_type': 'REGULER',
            'price': 6000
        }
    
    def test_connect(self, handler):
        """Test connect returns True"""
        # Already connected in fixture
        assert handler._connected is True
    
    def test_disconnect(self, handler):
        """Test disconnect"""
        handler.disconnect()
        assert handler._connected is False
    
    def test_save_package_returns_id(self, handler, sample_package):
        """Test save_package returns package ID"""
        package_id = handler.save_package(sample_package)
        
        assert package_id is not None
        assert len(package_id) > 0
    
    def test_save_package_stores_data(self, handler, sample_package):
        """Test saved package can be retrieved"""
        package_id = handler.save_package(sample_package)
        
        retrieved = handler.get_package(package_id)
        
        assert retrieved is not None
        assert retrieved['panjang'] == 15.0
        assert retrieved['service_type'] == 'REGULER'
        assert retrieved['price'] == 6000
    
    def test_get_package_not_found(self, handler):
        """Test get_package returns None for unknown ID"""
        result = handler.get_package('nonexistent_id')
        
        assert result is None
    
    def test_get_all_packages_empty(self, handler):
        """Test get_all_packages returns empty list initially"""
        packages = handler.get_all_packages()
        
        assert packages == []
    
    def test_get_all_packages_with_data(self, handler, sample_package):
        """Test get_all_packages returns saved packages"""
        handler.save_package(sample_package)
        handler.save_package({**sample_package, 'service_type': 'EXPRESS', 'price': 12000})
        
        packages = handler.get_all_packages()
        
        assert len(packages) == 2
    
    def test_get_all_packages_limit(self, handler, sample_package):
        """Test get_all_packages respects limit"""
        for _ in range(10):
            handler.save_package(sample_package)
        
        packages = handler.get_all_packages(limit=5)
        
        assert len(packages) == 5
    
    def test_statistics_initial(self, handler):
        """Test initial statistics"""
        stats = handler.get_statistics()
        
        assert stats['total_packages'] == 0
        assert stats['total_revenue'] == 0
        assert stats['by_service_type']['REGULER']['count'] == 0
    
    def test_statistics_after_save(self, handler, sample_package):
        """Test statistics update after save"""
        handler.save_package(sample_package)
        
        stats = handler.get_statistics()
        
        assert stats['total_packages'] == 1
        assert stats['total_revenue'] == 6000
        assert stats['by_service_type']['REGULER']['count'] == 1
    
    def test_statistics_multiple_types(self, handler):
        """Test statistics with multiple service types"""
        handler.save_package({'service_type': 'REGULER', 'price': 6000})
        handler.save_package({'service_type': 'EXPRESS', 'price': 12000})
        handler.save_package({'service_type': 'KARGO', 'price': 5000})
        handler.save_package({'service_type': 'REGULER', 'price': 6000})
        
        stats = handler.get_statistics()
        
        assert stats['total_packages'] == 4
        assert stats['total_revenue'] == 29000
        assert stats['by_service_type']['REGULER']['count'] == 2
        assert stats['by_service_type']['EXPRESS']['count'] == 1
        assert stats['by_service_type']['KARGO']['count'] == 1
    
    def test_reset_data(self, handler, sample_package):
        """Test reset clears all data"""
        handler.save_package(sample_package)
        handler.save_package(sample_package)
        
        handler.reset_data()
        
        packages = handler.get_all_packages()
        stats = handler.get_statistics()
        
        assert len(packages) == 0
        assert stats['total_packages'] == 0
        assert stats['total_revenue'] == 0


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestStorageFactory:
    """Test factory functions"""
    
    def test_create_mock_handler(self):
        """Test creating mock handler"""
        handler = create_storage_handler("mock")
        
        assert handler is not None
        assert isinstance(handler, MemoryStorageHandler)
    
    def test_mock_handler_interface(self):
        """Test mock handler implements interface"""
        handler = create_storage_handler("mock")
        
        # Should have all interface methods
        assert hasattr(handler, 'connect')
        assert hasattr(handler, 'disconnect')
        assert hasattr(handler, 'save_package')
        assert hasattr(handler, 'get_package')
        assert hasattr(handler, 'get_all_packages')
        assert hasattr(handler, 'get_statistics')
    
    def test_invalid_mode_raises_error(self):
        """Test invalid mode raises ValueError"""
        with pytest.raises(ValueError):
            create_storage_handler("invalid_mode")


# =============================================================================
# Integration Tests with Mock
# =============================================================================

class TestStorageIntegration:
    """Integration tests using mock handler"""
    
    @pytest.fixture
    def storage(self):
        """Create and connect storage handler"""
        handler = create_storage_handler("mock")
        handler.connect()
        yield handler
        handler.disconnect()
    
    def test_full_workflow(self, storage):
        """Test complete save-retrieve-statistics workflow"""
        # Save packages
        packages_to_save = [
            {'panjang': 10, 'lebar': 10, 'tinggi': 10, 'berat_aktual': 300,
             'berat_volumetrik': 166.7, 'chargeable_weight': 300,
             'service_type': 'REGULER', 'price': 6000},
            {'panjang': 15, 'lebar': 12, 'tinggi': 10, 'berat_aktual': 900,
             'berat_volumetrik': 300, 'chargeable_weight': 900,
             'service_type': 'EXPRESS', 'price': 12000},
            {'panjang': 20, 'lebar': 18, 'tinggi': 15, 'berat_aktual': 1500,
             'berat_volumetrik': 900, 'chargeable_weight': 1500,
             'service_type': 'KARGO', 'price': 5000},
        ]
        
        saved_ids = []
        for pkg in packages_to_save:
            pkg_id = storage.save_package(pkg)
            saved_ids.append(pkg_id)
        
        # Verify saved
        assert len(saved_ids) == 3
        
        # Retrieve all
        all_packages = storage.get_all_packages()
        assert len(all_packages) == 3
        
        # Retrieve single
        first_pkg = storage.get_package(saved_ids[0])
        assert first_pkg is not None
        assert first_pkg['service_type'] == 'REGULER'
        
        # Check statistics
        stats = storage.get_statistics()
        assert stats['total_packages'] == 3
        assert stats['total_revenue'] == 23000  # 6000 + 12000 + 5000
    
    def test_package_ordering(self, storage):
        """Test packages are returned in order"""
        import time
        
        # Save with small delays
        storage.save_package({'service_type': 'REGULER', 'price': 6000})
        time.sleep(0.01)
        storage.save_package({'service_type': 'EXPRESS', 'price': 12000})
        time.sleep(0.01)
        storage.save_package({'service_type': 'KARGO', 'price': 5000})
        
        packages = storage.get_all_packages()
        
        # Should be in reverse chronological order (newest first)
        assert packages[0]['service_type'] == 'KARGO'
        assert packages[1]['service_type'] == 'EXPRESS'
        assert packages[2]['service_type'] == 'REGULER'


# =============================================================================
# Data Validation Tests
# =============================================================================

class TestDataValidation:
    """Test data integrity and validation"""
    
    @pytest.fixture
    def storage(self):
        handler = create_storage_handler("mock")
        handler.connect()
        return handler
    
    def test_package_has_id(self, storage):
        """Test saved package has ID field"""
        pkg_id = storage.save_package({'service_type': 'REGULER', 'price': 6000})
        pkg = storage.get_package(pkg_id)
        
        assert 'id' in pkg
        assert pkg['id'] == pkg_id
    
    def test_package_has_timestamp(self, storage):
        """Test saved package has timestamp"""
        pkg_id = storage.save_package({'service_type': 'REGULER', 'price': 6000})
        pkg = storage.get_package(pkg_id)
        
        assert 'timestamp' in pkg
        # Should be ISO format
        datetime.fromisoformat(pkg['timestamp'])
    
    def test_statistics_isolation(self, storage):
        """Test statistics are isolated (copy, not reference)"""
        storage.save_package({'service_type': 'REGULER', 'price': 6000})
        
        stats1 = storage.get_statistics()
        stats1['total_packages'] = 999  # Modify
        
        stats2 = storage.get_statistics()
        assert stats2['total_packages'] == 1  # Should be unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
