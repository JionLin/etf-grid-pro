"""数据库后端选择。默认 SQLite，DB_TYPE=mysql 时才走 MySQL。"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env", override=False)

DEFAULT_DATABASE = "etf_grid"
TEST_DATABASE = "etf_grid_test"


def db_type() -> str:
    """sqlite 或 mysql。未设置时用 sqlite。"""
    raw = os.environ.get("DB_TYPE", "sqlite").strip().lower()
    if raw in ("sqlite", "mysql"):
        return raw
    raise ValueError("DB_TYPE 只能是 sqlite 或 mysql")


def is_sqlite() -> bool:
    return db_type() == "sqlite"


def sqlite_path(database: Optional[str] = None) -> Path:
    """业务库用 SQLITE_PATH。测试库放在同一目录，文件名带测试库名。"""
    configured = os.environ.get("SQLITE_PATH", "").strip()
    base = Path(configured) if configured else _ROOT / "data" / "etf_grid.sqlite"
    if not base.is_absolute():
        base = _ROOT / base
    logical = database or os.environ.get("MYSQL_DATABASE", DEFAULT_DATABASE)
    if logical in (None, "", DEFAULT_DATABASE, base.stem):
        return base
    return base.with_name(f"{logical}.sqlite")
