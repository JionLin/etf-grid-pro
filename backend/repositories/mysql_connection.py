"""数据库连接。DB_TYPE=sqlite 时打开 SQLite 文件；DB_TYPE=mysql 时才连接 MySQL。

选了 MySQL 但连不上时直接失败，不会改去打开 SQLite。
"""
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from .db_config import DEFAULT_DATABASE, TEST_DATABASE, db_type, sqlite_path
from .sqlite_dialect import connect_sqlite

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_ROOT, ".env"), override=False)


class MysqlConfigError(RuntimeError):
    """环境变量缺少连接所需的账号或密码。"""


class MysqlConnectionError(RuntimeError):
    """MySQL 不可达或拒绝登录。"""


def read_settings(
    database: Optional[str] = None,
    *,
    user: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> Dict[str, Any]:
    resolved_user = user if user is not None else os.environ.get("MYSQL_USER")
    if password is None:
        if "MYSQL_PASSWORD" not in os.environ:
            raise MysqlConfigError("缺少环境变量 MYSQL_PASSWORD")
        resolved_password = os.environ["MYSQL_PASSWORD"]
    else:
        resolved_password = password
    if not resolved_user:
        raise MysqlConfigError("缺少环境变量 MYSQL_USER")
    import pymysql
    from pymysql.cursors import DictCursor

    resolved_port = port if port is not None else int(os.environ.get("MYSQL_PORT", "3306"))
    return {
        "host": host or os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": resolved_port,
        "user": resolved_user,
        "password": resolved_password,
        "database": database or os.environ.get("MYSQL_DATABASE", DEFAULT_DATABASE),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def connect(
    database: Optional[str] = None,
    *,
    user: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
):
    """按 DB_TYPE 打开连接。MySQL 固定 utf8mb4 和东八区，失败直接抛出。"""
    if db_type() == "sqlite":
        return connect_sqlite(sqlite_path(database))
    import pymysql

    settings = read_settings(
        database, user=user, password=password, host=host, port=port
    )
    try:
        conn = pymysql.connect(**settings)
    except pymysql.MySQLError as exc:
        raise MysqlConnectionError(f"连接 MySQL 失败: {exc}") from exc
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET NAMES utf8mb4")
            cursor.execute("SET time_zone = '+08:00'")
        conn.commit()
    except pymysql.MySQLError as exc:
        conn.close()
        raise MysqlConnectionError(f"初始化 MySQL 会话失败: {exc}") from exc
    return conn


def connect_server(
    *,
    user: Optional[str] = None,
    password: Optional[str] = None,
):
    """连到 MySQL 实例本身，用于建库。不选择业务库。"""
    if db_type() == "sqlite":
        return connect_sqlite(sqlite_path(DEFAULT_DATABASE))
    import pymysql

    settings = read_settings(user=user, password=password)
    settings.pop("database")
    try:
        return pymysql.connect(**settings)
    except pymysql.MySQLError as exc:
        raise MysqlConnectionError(f"连接 MySQL 失败: {exc}") from exc
