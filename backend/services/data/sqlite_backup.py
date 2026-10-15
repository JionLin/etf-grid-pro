"""启动时把 SQLite 业务库复制到 data/backups，只留最近几份。"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from repositories.db_config import DEFAULT_DATABASE, db_type, sqlite_path

DEFAULT_BACKUP_KEEP = 7


def backup_keep_count() -> int:
    raw = os.environ.get("SQLITE_BACKUP_KEEP", str(DEFAULT_BACKUP_KEEP)).strip()
    try:
        keep = int(raw)
    except ValueError:
        keep = DEFAULT_BACKUP_KEEP
    return max(1, keep)


def backup_sqlite_database(source: Optional[Path] = None, keep: Optional[int] = None) -> Optional[Path]:
    """热备份当前 SQLite。MySQL 或空库不复制。返回新备份路径。"""
    if db_type() != "sqlite":
        return None
    database = source or sqlite_path(DEFAULT_DATABASE)
    if not database.is_file() or database.stat().st_size <= 0:
        return None
    retain = backup_keep_count() if keep is None else max(1, int(keep))
    backup_dir = database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = backup_dir / f"{database.stem}-{stamp}.sqlite"
    with sqlite3.connect(database) as origin, sqlite3.connect(dest) as copy:
        origin.backup(copy)
    snapshots = sorted(backup_dir.glob(f"{database.stem}-*.sqlite"))
    for stale in snapshots[:-retain]:
        stale.unlink(missing_ok=True)
    return dest
