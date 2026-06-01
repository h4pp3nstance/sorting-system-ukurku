"""
Storage Module
Provides data persistence for the sorting system (SQLite default).
"""

from storage.base import IStorageHandler
from storage.sqlite_handler import SQLiteHandler
from storage.memory_handler import MemoryStorageHandler
from storage.factory import create_storage_handler

__all__ = [
    'IStorageHandler',
    'SQLiteHandler',
    'MemoryStorageHandler',
    'create_storage_handler',
]
