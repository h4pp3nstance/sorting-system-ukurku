"""
Storage factory - pilih backend penyimpanan.

Default offline-first: SQLite. Mode lain: memory/mock (test).
Firebase sudah dihapus dari sistem (lihat .omo/plans/sqlite-migration.md).
"""

from typing import Optional

from storage.base import IStorageHandler


def create_storage_handler(mode: str = "auto",
                           db_path: Optional[str] = None) -> IStorageHandler:
    """Buat storage handler.

    Args:
        mode: "sqlite", "memory"/"mock", atau "auto" (-> sqlite).
        db_path: path SQLite opsional (mode sqlite).
    """
    if mode in ("memory", "mock"):
        from storage.memory_handler import MemoryStorageHandler
        return MemoryStorageHandler()

    if mode in ("sqlite", "auto"):
        from storage.sqlite_handler import SQLiteHandler
        return SQLiteHandler(db_path=db_path)

    raise ValueError(f"Unknown storage mode: {mode}")
