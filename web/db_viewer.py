"""
DB Viewer - akses read-only SQLite ukurku.db untuk dashboard (pengganti DBeaver).

Keamanan berlapis:
1. Koneksi dibuka mode=ro (URI) -> kernel tolak semua write, walau query nakal.
2. run_select() hanya mengizinkan satu statement SELECT/WITH; kata kunci
   tulis (INSERT/UPDATE/DELETE/DROP/...) dan multi-statement ditolak.
Dipakai oleh route admin-only. Pure-ish (tanpa Flask) supaya bisa diuji.
"""

import os
import re
import sqlite3


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|"
    r"attach|detach|pragma|vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)

_MAX_ROWS = 500


def _db_path():
    from storage.sqlite_handler import SQLiteHandler
    import os as _os
    env = _os.getenv("DB_PATH")
    if env:
        return env
    base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    return _os.path.join(base, "config", "ukurku.db")


def _connect_ro():
    """Koneksi read-only: write apa pun gagal di level SQLite."""
    path = _db_path()
    if not os.path.isfile(path):
        raise FileNotFoundError("Database tidak ditemukan: " + path)
    uri = "file:" + path + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def list_tables():
    """Daftar tabel + view (dari sqlite_master), beserta jumlah baris."""
    conn = _connect_ro()
    try:
        cur = conn.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name"
        )
        items = []
        for row in cur.fetchall():
            name = row["name"]
            try:
                c = conn.execute(
                    'SELECT COUNT(*) AS n FROM "%s"' % name.replace('"', '""')
                )
                count = c.fetchone()["n"]
            except sqlite3.Error:
                count = None
            items.append({"name": name, "type": row["type"], "rows": count})
        return items
    finally:
        conn.close()


def _table_exists(conn, name):
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type IN ('table','view') AND name = ?",
        (name,),
    )
    return cur.fetchone() is not None


def table_schema(name):
    """Skema kolom tabel (nama, tipe, pk)."""
    conn = _connect_ro()
    try:
        if not _table_exists(conn, name):
            raise ValueError("Tabel tidak ditemukan: " + str(name))
        cur = conn.execute('PRAGMA table_info("%s")' % name.replace('"', '""'))
        return [
            {"name": r["name"], "type": r["type"], "pk": bool(r["pk"])}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def table_rows(name, limit=100, offset=0):
    """Baris tabel (dibatasi). Nama tabel divalidasi via sqlite_master."""
    limit = max(1, min(int(limit), _MAX_ROWS))
    offset = max(0, int(offset))
    conn = _connect_ro()
    try:
        if not _table_exists(conn, name):
            raise ValueError("Tabel tidak ditemukan: " + str(name))
        safe = name.replace('"', '""')
        total = conn.execute(
            'SELECT COUNT(*) AS n FROM "%s"' % safe
        ).fetchone()["n"]
        cur = conn.execute(
            'SELECT * FROM "%s" LIMIT ? OFFSET ?' % safe, (limit, offset)
        )
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        return {"columns": cols, "rows": rows, "total": total,
                "limit": limit, "offset": offset}
    finally:
        conn.close()


def run_select(sql):
    """Jalankan SATU query SELECT/WITH read-only. Tolak write & multi-statement."""
    if not sql or not sql.strip():
        raise ValueError("Query kosong.")
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:
        raise ValueError("Hanya satu statement yang diizinkan.")
    low = stripped.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise ValueError("Hanya query SELECT yang diizinkan.")
    if _FORBIDDEN.search(stripped):
        raise ValueError("Query mengandung kata kunci yang tidak diizinkan (read-only).")

    conn = _connect_ro()
    try:
        cur = conn.execute(stripped)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [list(r) for r in cur.fetchmany(_MAX_ROWS)]
        return {"columns": cols, "rows": rows, "truncated_at": _MAX_ROWS}
    finally:
        conn.close()
