"""
In-memory storage handler (testing / fallback).

Menyimpan data di memori. Dipakai untuk test dan sebagai fallback bila
SQLite gagal diinisialisasi. Tidak persisten.
"""

import random
import string
from datetime import datetime
from typing import Dict, List, Optional

from storage.base import IStorageHandler


class MemoryStorageHandler(IStorageHandler):
    """In-memory storage (test double / fallback)."""

    def __init__(self):
        self._packages: Dict[str, Dict] = {}
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def save_package(self, package_data: Dict) -> str:
        timestamp = datetime.now()
        random_suffix = ''.join(
            random.choices(string.ascii_lowercase + string.digits, k=4)
        )
        package_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{random_suffix}"

        self._packages[package_id] = {
            'id': package_id,
            'timestamp': timestamp.isoformat(),
            **package_data,
        }
        return package_id

    def get_package(self, package_id: str) -> Optional[Dict]:
        return self._packages.get(str(package_id))

    def get_all_packages(self, limit: int = 100) -> List[Dict]:
        packages = list(self._packages.values())
        packages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return packages[:limit]

    def get_statistics(self) -> Dict:
        by_type = {
            'REGULER': {'count': 0, 'revenue': 0},
            'EXPRESS': {'count': 0, 'revenue': 0},
            'KARGO': {'count': 0, 'revenue': 0},
        }
        total_revenue = 0
        for p in self._packages.values():
            price = p.get('price', 0)
            total_revenue += price
            stype = p.get('service_type', 'UNKNOWN')
            if stype in by_type:
                by_type[stype]['count'] += 1
                by_type[stype]['revenue'] += price

        return {
            'total_packages': len(self._packages),
            'total_revenue': total_revenue,
            'by_service_type': by_type,
        }

    def reset_data(self) -> bool:
        self._packages = {}
        return True

    def update_package_parties(self, package_id, sender=None, recipient=None):
        pkg = self._packages.get(str(package_id))
        if not pkg:
            return False
        if sender is not None:
            pkg["sender"] = sender
        if recipient is not None:
            pkg["recipient"] = recipient
        return True

    def update_system_status(self, status: str) -> None:
        return None
