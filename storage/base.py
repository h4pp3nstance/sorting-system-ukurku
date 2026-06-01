"""
Storage interface (backend-agnostic).

IStorageHandler adalah kontrak yang dipakai semua backend penyimpanan
(SQLite default, in-memory untuk test).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IStorageHandler(ABC):
    """Interface for storage handlers."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to storage."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    def save_package(self, package_data: Dict) -> str:
        """Save package data, return package ID."""
        pass

    @abstractmethod
    def get_package(self, package_id: str) -> Optional[Dict]:
        """Get single package by ID."""
        pass

    @abstractmethod
    def get_all_packages(self, limit: int = 100) -> List[Dict]:
        """Get all packages with optional limit."""
        pass

    @abstractmethod
    def get_statistics(self) -> Dict:
        """Get current statistics."""
        pass
