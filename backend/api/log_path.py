"""日志目录固定在仓库 logs/，不跟当前工作目录走。"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_log_dir(explicit: str | None = None) -> Path:
    """LOG_DIR 或配置里的相对路径都相对仓库根目录。"""
    raw = explicit if explicit is not None else os.environ.get("LOG_DIR", "logs")
    path = Path(str(raw).strip() or "logs")
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path
