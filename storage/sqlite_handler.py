"""
SQLite Storage Handler (offline-first)

Implementasi IStorageHandler berbasis SQLite. Menyimpan paket secara
lossless: kolom khusus (service_type/price/mitra_id/timestamp) untuk
query cepat, plus data_json yang memuat SELURUH package_data sehingga
round-trip identik dengan InMemoryStorage (memperbaiki bug field-drop
FirebaseHandler).

Connection-per-operation + WAL + busy_timeout supaya aman di Raspberry Pi
(Flask threaded + MeasurementSession in-process).
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from storage.base import IStorageHandler


_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "ukurku.db",
)

_SERVICE_TYPES = ("REGULER", "EXPRESS", "KARGO")


class SQLiteHandler(IStorageHandler):
    """Storage backend berbasis SQLite (default offline-first)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._connected = False

    def _connect_raw(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def connect(self) -> bool:
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = self._connect_raw()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS packages (
                    pk           INTEGER PRIMARY KEY AUTOINCREMENT,
                    id           TEXT UNIQUE,
                    timestamp    TEXT,
                    service_type TEXT,
                    price        INTEGER,
                    mitra_id     TEXT,
                    data_json    TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_packages_service "
                "ON packages(service_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_packages_mitra "
                "ON packages(mitra_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_packages_ts "
                "ON packages(timestamp)"
            )
            conn.commit()
        finally:
            conn.close()
        self._connected = True
        print(f"[SQLite] Connected: {self.db_path}")
        return True

    def disconnect(self) -> None:
        self._connected = False

    def _row_to_package(self, row) -> Dict:
        """Rekonstruksi flat dict: {id, timestamp, **package_data}."""
        data = json.loads(row["data_json"]) if row["data_json"] else {}
        result = dict(data)
        result["id"] = row["id"]
        result["timestamp"] = row["timestamp"]
        return result

    def save_package(self, package_data: Dict) -> str:
        timestamp = package_data.get("timestamp") or datetime.now().isoformat()
        service_type = package_data.get("service_type", "UNKNOWN")
        price = package_data.get("price", 0)
        mitra_id = package_data.get("mitra_id")

        # Buang timestamp dari payload agar tidak dobel; disimpan via kolom.
        payload = {k: v for k, v in package_data.items() if k != "timestamp"}

        conn = self._connect_raw()
        try:
            cur = conn.execute(
                "INSERT INTO packages "
                "(timestamp, service_type, price, mitra_id, data_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (timestamp, service_type, price, mitra_id,
                 json.dumps(payload, ensure_ascii=False)),
            )
            package_id = str(cur.lastrowid)
            conn.execute(
                "UPDATE packages SET id = ? WHERE pk = ?",
                (package_id, cur.lastrowid),
            )
            conn.commit()
        finally:
            conn.close()

        print(f"[SQLite] Package saved: {package_id}")
        return package_id

    def get_package(self, package_id: str) -> Optional[Dict]:
        conn = self._connect_raw()
        try:
            row = conn.execute(
                "SELECT * FROM packages WHERE id = ?", (str(package_id),)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_package(row) if row else None

    def get_all_packages(self, limit: int = 100) -> List[Dict]:
        conn = self._connect_raw()
        try:
            rows = conn.execute(
                "SELECT * FROM packages ORDER BY pk DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_package(r) for r in rows]

    def update_statistics(self, package_data: Dict) -> bool:
        # Statistik dihitung on-the-fly di get_statistics (hindari dual-write).
        return True

    def get_statistics(self) -> Dict:
        by_type = {st: {"count": 0, "revenue": 0} for st in _SERVICE_TYPES}
        total_packages = 0
        total_revenue = 0

        conn = self._connect_raw()
        try:
            rows = conn.execute(
                "SELECT service_type, COUNT(*) AS c, "
                "COALESCE(SUM(price), 0) AS r "
                "FROM packages GROUP BY service_type"
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            count = row["c"]
            revenue = row["r"]
            total_packages += count
            total_revenue += revenue
            st = row["service_type"]
            if st in by_type:
                by_type[st]["count"] = count
                by_type[st]["revenue"] = revenue

        return {
            "total_packages": total_packages,
            "total_revenue": total_revenue,
            "by_service_type": by_type,
        }

    def reset_data(self) -> bool:
        conn = self._connect_raw()
        try:
            conn.execute("DELETE FROM packages")
            conn.commit()
        finally:
            conn.close()
        print("[SQLite] Data reset")
        return True

    def update_system_status(self, status: str) -> None:
        # Status sistem tidak dipersist di SQLite (no-op, kompat interface).
        return None
