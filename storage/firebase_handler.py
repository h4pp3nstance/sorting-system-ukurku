"""
Firebase Realtime Database Handler
Handles package data synchronization with Firebase
"""

import os
import json
import random
import string
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("[Warning] firebase-admin not installed. Run: pip install firebase-admin")


class IStorageHandler(ABC):
    """Interface for storage handlers"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to storage"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection"""
        pass
    
    @abstractmethod
    def save_package(self, package_data: Dict) -> str:
        """Save package data, return package ID"""
        pass
    
    @abstractmethod
    def get_package(self, package_id: str) -> Optional[Dict]:
        """Get single package by ID"""
        pass
    
    @abstractmethod
    def get_all_packages(self, limit: int = 100) -> List[Dict]:
        """Get all packages with optional limit"""
        pass
    
    @abstractmethod
    def update_statistics(self, package_data: Dict) -> bool:
        """Update aggregated statistics"""
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict:
        """Get current statistics"""
        pass


class FirebaseHandler(IStorageHandler):
    """
    Firebase Realtime Database handler
    Manages package data synchronization
    """
    
    # Database URL - extracted from credentials or set explicitly
    DATABASE_URL = "https://ukurku-c94e7-default-rtdb.asia-southeast1.firebasedatabase.app"
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Firebase handler
        
        Args:
            credentials_path: Path to Firebase credentials JSON file
        """
        self.credentials_path = credentials_path or self._find_credentials()
        self._initialized = False
        self._app = None
        self._listeners = {}  # Track active listeners
        self._callbacks = {}  # Event callbacks
    
    def _find_credentials(self) -> str:
        """Find credentials file in common locations"""
        possible_paths = [
            "config/firebase_credentials.json",
            "../config/firebase_credentials.json",
            os.path.join(os.path.dirname(__file__), "..", "config", "firebase_credentials.json"),
            os.path.expanduser("~/.firebase/credentials.json"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        raise FileNotFoundError(
            "Firebase credentials not found. Please place firebase_credentials.json in config/"
        )
    
    def connect(self) -> bool:
        """
        Initialize Firebase Admin SDK connection
        
        Returns:
            bool: True if connection successful
        """
        if not FIREBASE_AVAILABLE:
            raise ImportError("firebase-admin package not installed")
        
        if self._initialized:
            print("[Firebase] Already connected")
            return True
        
        try:
            # Check if already initialized (in case of multiple instances)
            if firebase_admin._apps:
                self._app = firebase_admin.get_app()
                print("[Firebase] Using existing app instance")
            else:
                cred = credentials.Certificate(self.credentials_path)
                self._app = firebase_admin.initialize_app(cred, {
                    'databaseURL': self.DATABASE_URL
                })
                print(f"[Firebase] Connected to: {self.DATABASE_URL}")
            
            self._initialized = True
            
            # Initialize database structure if needed
            self._ensure_structure()
            
            return True
            
        except Exception as e:
            print(f"[Firebase] Connection failed: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close Firebase connection"""
        if self._app and self._initialized:
            try:
                firebase_admin.delete_app(self._app)
                self._initialized = False
                print("[Firebase] Disconnected")
            except Exception as e:
                print(f"[Firebase] Disconnect error: {e}")
    
    def _ensure_structure(self) -> None:
        """Ensure database has required structure"""
        ref = db.reference('/')
        
        # Check and create base structure
        current = ref.get()
        
        if current is None or 'packages' not in (current or {}):
            print("[Firebase] Initializing database structure...")
            
            # Initialize with empty structure
            ref.update({
                'packages': {},
                'statistics': {
                    'total_packages': 0,
                    'total_revenue': 0,
                    'by_service_type': {
                        'REGULER': {'count': 0, 'revenue': 0},
                        'EXPRESS': {'count': 0, 'revenue': 0},
                        'KARGO': {'count': 0, 'revenue': 0}
                    },
                    'last_updated': datetime.now().isoformat()
                },
                'system': {
                    'status': 'initialized',
                    'version': '1.0.0',
                    'last_sync': datetime.now().isoformat()
                }
            })
            print("[Firebase] Structure initialized")
    
    def save_package(self, package_data: Dict) -> str:
        """
        Save package to Firebase
        
        Args:
            package_data: Package data dictionary
            
        Returns:
            str: Generated package ID
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        # Generate unique ID based on timestamp + random suffix
        timestamp = datetime.now()
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        package_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{random_suffix}"
        
        # Prepare data
        data = {
            'id': package_id,
            'timestamp': timestamp.isoformat(),
            'dimensions': {
                'panjang': package_data.get('panjang', 0),
                'lebar': package_data.get('lebar', 0),
                'tinggi': package_data.get('tinggi', 0)
            },
            'weight': {
                'aktual': package_data.get('berat_aktual', 0),
                'volumetrik': package_data.get('berat_volumetrik', 0),
                'chargeable': package_data.get('chargeable_weight', 0)
            },
            'service_type': package_data.get('service_type', 'UNKNOWN'),
            'price': package_data.get('price', 0),
            'synced_at': datetime.now().isoformat()
        }
        
        # Save to Firebase
        ref = db.reference(f'packages/{package_id}')
        ref.set(data)
        
        # Update statistics
        self.update_statistics(data)
        
        print(f"[Firebase] Package saved: {package_id}")
        return package_id
    
    def get_package(self, package_id: str) -> Optional[Dict]:
        """
        Get single package by ID
        
        Args:
            package_id: Package ID to retrieve
            
        Returns:
            Package data or None if not found
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        ref = db.reference(f'packages/{package_id}')
        return ref.get()
    
    def get_all_packages(self, limit: int = 100) -> List[Dict]:
        """
        Get all packages
        
        Args:
            limit: Maximum number of packages to return
            
        Returns:
            List of package dictionaries
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        ref = db.reference('packages')
        
        # Try to get without ordering first (doesn't require index)
        # Then sort in memory for simplicity
        try:
            packages = ref.get()
        except Exception as e:
            print(f"[Firebase] Error getting packages: {e}")
            return []
        
        if packages:
            # Convert dict to list and sort by timestamp (newest first)
            result = list(packages.values())
            result.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            # Apply limit after sorting
            return result[:limit]
        
        return []
    
    def get_packages_by_type(self, service_type: str, limit: int = 50) -> List[Dict]:
        """
        Get packages filtered by service type
        
        Args:
            service_type: REGULER, EXPRESS, or KARGO
            limit: Maximum number of packages to return
            
        Returns:
            List of filtered packages
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        ref = db.reference('packages')
        packages = ref.order_by_child('service_type').equal_to(service_type).limit_to_last(limit).get()
        
        if packages:
            return list(packages.values())
        
        return []
    
    def update_statistics(self, package_data: Dict) -> bool:
        """
        Update aggregated statistics after saving a package
        
        Args:
            package_data: The saved package data
            
        Returns:
            bool: True if update successful
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        try:
            stats_ref = db.reference('statistics')
            current = stats_ref.get() or {}
            
            service_type = package_data.get('service_type', 'UNKNOWN')
            price = package_data.get('price', 0)
            
            # Update totals
            new_stats = {
                'total_packages': current.get('total_packages', 0) + 1,
                'total_revenue': current.get('total_revenue', 0) + price,
                'last_updated': datetime.now().isoformat()
            }
            
            # Update by service type
            by_type = current.get('by_service_type', {})
            type_stats = by_type.get(service_type, {'count': 0, 'revenue': 0})
            
            new_stats[f'by_service_type/{service_type}'] = {
                'count': type_stats.get('count', 0) + 1,
                'revenue': type_stats.get('revenue', 0) + price
            }
            
            stats_ref.update(new_stats)
            
            return True
            
        except Exception as e:
            print(f"[Firebase] Statistics update failed: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """
        Get current statistics
        
        Returns:
            Statistics dictionary
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        ref = db.reference('statistics')
        return ref.get() or {}
    
    def reset_data(self) -> bool:
        """
        Reset all package data (for testing)
        
        Returns:
            bool: True if reset successful
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected. Call connect() first.")
        
        try:
            # Clear packages
            db.reference('packages').delete()
            
            # Reset statistics
            db.reference('statistics').set({
                'total_packages': 0,
                'total_revenue': 0,
                'by_service_type': {
                    'REGULER': {'count': 0, 'revenue': 0},
                    'EXPRESS': {'count': 0, 'revenue': 0},
                    'KARGO': {'count': 0, 'revenue': 0}
                },
                'last_updated': datetime.now().isoformat()
            })
            
            print("[Firebase] Data reset complete")
            return True
            
        except Exception as e:
            print(f"[Firebase] Reset failed: {e}")
            return False
    
    def update_system_status(self, status: str) -> None:
        """Update system status in Firebase"""
        if self._initialized:
            db.reference('system').update({
                'status': status,
                'last_sync': datetime.now().isoformat()
            })
    
    # =========================================================================
    # Real-time Listener Methods
    # =========================================================================
    
    def add_package_listener(self, callback) -> str:
        """
        Add real-time listener for new packages
        
        Args:
            callback: Function to call when packages change
                     signature: callback(event_type: str, data: Dict)
        
        Returns:
            listener_id: ID to remove listener later
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected")
        
        listener_id = f"pkg_{len(self._listeners)}"
        
        def on_packages_change(event):
            """Internal handler for Firebase events"""
            event_type = event.event_type  # 'put', 'patch', 'cancel'
            data = event.data
            path = event.path
            
            if callback:
                callback(event_type, path, data)
        
        ref = db.reference('packages')
        listener = ref.listen(on_packages_change)
        
        self._listeners[listener_id] = listener
        self._callbacks[listener_id] = callback
        
        print(f"[Firebase] Listener added: {listener_id}")
        return listener_id
    
    def add_statistics_listener(self, callback) -> str:
        """
        Add real-time listener for statistics changes
        
        Args:
            callback: Function(event_type, path, data)
        
        Returns:
            listener_id
        """
        if not self._initialized:
            raise RuntimeError("Firebase not connected")
        
        listener_id = f"stats_{len(self._listeners)}"
        
        def on_stats_change(event):
            if callback:
                callback(event.event_type, event.path, event.data)
        
        ref = db.reference('statistics')
        listener = ref.listen(on_stats_change)
        
        self._listeners[listener_id] = listener
        self._callbacks[listener_id] = callback
        
        print(f"[Firebase] Statistics listener added: {listener_id}")
        return listener_id
    
    def remove_listener(self, listener_id: str) -> bool:
        """
        Remove a real-time listener
        
        Args:
            listener_id: ID returned from add_*_listener
        
        Returns:
            bool: True if removed successfully
        """
        if listener_id in self._listeners:
            listener = self._listeners[listener_id]
            listener.close()
            del self._listeners[listener_id]
            del self._callbacks[listener_id]
            print(f"[Firebase] Listener removed: {listener_id}")
            return True
        return False
    
    def remove_all_listeners(self) -> int:
        """
        Remove all active listeners
        
        Returns:
            count: Number of listeners removed
        """
        count = 0
        for listener_id, listener in list(self._listeners.items()):
            listener.close()
            count += 1
        
        self._listeners.clear()
        self._callbacks.clear()
        
        print(f"[Firebase] Removed {count} listeners")
        return count
    
    def get_active_listeners(self) -> List[str]:
        """Get list of active listener IDs"""
        return list(self._listeners.keys())


class MockFirebaseHandler(IStorageHandler):
    """
    Mock Firebase handler for testing without real connection
    Stores data in memory
    """
    
    def __init__(self):
        self._packages: Dict[str, Dict] = {}
        self._statistics = {
            'total_packages': 0,
            'total_revenue': 0,
            'by_service_type': {
                'REGULER': {'count': 0, 'revenue': 0},
                'EXPRESS': {'count': 0, 'revenue': 0},
                'KARGO': {'count': 0, 'revenue': 0}
            }
        }
        self._connected = False
    
    def connect(self) -> bool:
        print("[MockFirebase] Connected (mock mode)")
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        print("[MockFirebase] Disconnected")
        self._connected = False
    
    def save_package(self, package_data: Dict) -> str:
        # Generate unique ID with random suffix to avoid collisions
        timestamp = datetime.now()
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        package_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{random_suffix}"
        
        self._packages[package_id] = {
            'id': package_id,
            'timestamp': timestamp.isoformat(),
            **package_data
        }
        
        self.update_statistics(package_data)
        print(f"[MockFirebase] Package saved: {package_id}")
        return package_id
    
    def get_package(self, package_id: str) -> Optional[Dict]:
        return self._packages.get(package_id)
    
    def get_all_packages(self, limit: int = 100) -> List[Dict]:
        packages = list(self._packages.values())
        packages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return packages[:limit]
    
    def update_statistics(self, package_data: Dict) -> bool:
        service_type = package_data.get('service_type', 'UNKNOWN')
        price = package_data.get('price', 0)
        
        self._statistics['total_packages'] += 1
        self._statistics['total_revenue'] += price
        
        if service_type in self._statistics['by_service_type']:
            self._statistics['by_service_type'][service_type]['count'] += 1
            self._statistics['by_service_type'][service_type]['revenue'] += price
        
        return True
    
    def get_statistics(self) -> Dict:
        return self._statistics.copy()
    
    def reset_data(self) -> bool:
        self._packages = {}
        self._statistics = {
            'total_packages': 0,
            'total_revenue': 0,
            'by_service_type': {
                'REGULER': {'count': 0, 'revenue': 0},
                'EXPRESS': {'count': 0, 'revenue': 0},
                'KARGO': {'count': 0, 'revenue': 0}
            }
        }
        print("[MockFirebase] Data reset")
        return True


# Factory function
def create_storage_handler(mode: str = "auto") -> IStorageHandler:
    """
    Factory function to create storage handler
    
    Args:
        mode: "firebase", "mock", or "auto" (uses firebase if available)
        
    Returns:
        IStorageHandler implementation
    """
    if mode == "mock":
        return MockFirebaseHandler()
    
    if mode == "firebase" or mode == "auto":
        if FIREBASE_AVAILABLE:
            try:
                return FirebaseHandler()
            except FileNotFoundError as e:
                if mode == "firebase":
                    raise
                print(f"[Warning] {e}. Falling back to mock mode.")
                return MockFirebaseHandler()
        else:
            if mode == "firebase":
                raise ImportError("firebase-admin package not installed")
            return MockFirebaseHandler()
    
    raise ValueError(f"Unknown mode: {mode}")


# Singleton instance
_storage_handler: Optional[IStorageHandler] = None


def get_storage() -> IStorageHandler:
    """Get singleton storage handler instance"""
    global _storage_handler
    
    if _storage_handler is None:
        _storage_handler = create_storage_handler("auto")
        _storage_handler.connect()
    
    return _storage_handler
