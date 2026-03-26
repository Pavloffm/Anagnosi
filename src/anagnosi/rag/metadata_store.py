import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, List, Set
from datetime import datetime

from loguru import logger

from anagnosi.config import paths


DB_PATH = paths.project_path / ".vector_db" / "index_metadata.db"

@contextmanager
def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
    finally:
        conn.close()


def init_metadata_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                source TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                last_modified REAL NOT NULL,
                last_synced REAL NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON file_index(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_last_synced ON file_index(last_synced)")
        conn.commit()
    logger.debug("Metadata DB initialized")


def compute_file_hash(file_path: Path) -> Optional[str]:
    try:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception as e:
        logger.error(f"Error hashing {file_path}: {e}")
        return None


def get_file_metadata(source: str) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM file_index WHERE source = ?", (source,))
        row = cursor.fetchone()
        return dict(row) if row else None


def upsert_file_metadata(source: str, file_path: Path, file_hash: str, chunk_count: int) -> bool:
    now = datetime.now().timestamp()
    mtime = file_path.stat().st_mtime

    with get_db_connection() as conn:
        existing = conn.execute("SELECT file_hash FROM file_index WHERE source = ?", (source,)).fetchone()

        is_update = existing and existing["file_hash"] != file_hash

        conn.execute("""
            INSERT OR REPLACE INTO file_index 
            (source, file_path, file_hash, chunk_count, last_modified, last_synced, created_at)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE( (SELECT created_at FROM file_index WHERE source = ?), ? ))
        """, (source, str(file_path), file_hash, chunk_count, mtime, now, source, now))
        conn.commit()

        if is_update:
            logger.debug(f"Updated metadata for {source} (hash changed)")
        elif not existing:
            logger.debug(f"Inserted new metadata for {source}")
        else:
            logger.debug(f"Refreshed sync timestamp for {source}")

        return is_update or not existing


def delete_file_metadata(source: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM file_index WHERE source = ?", (source,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"Removed metadata for deleted file: {source}")
        return deleted


def get_all_tracked_sources() -> Set[str]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT source FROM file_index")
        return {row["source"] for row in cursor.fetchall()}

def get_files_needing_sync(current_files: Dict[str, Path], force: bool = False) -> List[str]:
    to_sync = []

    for source, file_path in current_files.items():
        meta = get_file_metadata(source)

        if force:
            to_sync.append(source)
            continue

        if not meta:
            to_sync.append(source)
            continue

        current_hash = compute_file_hash(file_path)
        if not current_hash:
            continue

        if has_file_changed(meta, file_path, current_hash):
            to_sync.append(source)
            logger.debug(f"File changed: {source}")

    return to_sync


def has_file_changed(meta: Dict, file_path: Path, current_hash: str) -> bool:
    if meta["last_modified"] != file_path.stat().st_mtime: return True
    if meta["file_path"] != str(file_path): return True
    if meta["file_hash"] != current_hash: return True

    return False

def get_orphaned_sources(current_sources: Set[str]) -> List[str]:
    tracked = get_all_tracked_sources()
    orphans = tracked - current_sources
    if orphans:
        logger.debug(f"Found orphaned sources: {orphans}")
    return list(orphans)