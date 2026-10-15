"""没有 MySQL 时跳过依赖数据库的测试，而不是报连接错误。"""
import os

import pytest


def mysql_skip_reason() -> str:
    """SQLite 不跳过。只有选了 MySQL 又连不上时才跳过。"""
    from backend.repositories.db_config import db_type

    if db_type() != "mysql":
        return ""
    if not os.environ.get("MYSQL_USER") or "MYSQL_PASSWORD" not in os.environ:
        return "未配置 MYSQL_USER / MYSQL_PASSWORD"
    try:
        from backend.repositories.mysql_connection import TEST_DATABASE, connect
        from backend.repositories.mysql_schema import ensure_database

        ensure_database(TEST_DATABASE)
        connection = connect(TEST_DATABASE)
        connection.close()
    except Exception:
        return "MySQL 不可用"
    return ""


def skip_without_mysql() -> None:
    """当前进程连不上测试库时跳过。"""
    reason = mysql_skip_reason()
    if reason:
        pytest.skip(reason)
