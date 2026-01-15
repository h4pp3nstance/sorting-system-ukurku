"""
Storage Module
Provides data persistence for the sorting system
"""

from storage.firebase_handler import (
    IStorageHandler,
    FirebaseHandler,
    MockFirebaseHandler,
    create_storage_handler,
    get_storage,
    FIREBASE_AVAILABLE
)

__all__ = [
    'IStorageHandler',
    'FirebaseHandler',
    'MockFirebaseHandler',
    'create_storage_handler',
    'get_storage',
    'FIREBASE_AVAILABLE'
]
