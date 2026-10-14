"""没有 MySQL 时跳过依赖数据库的测试，而不是报连接错误。"""
import os

import pytest


def mysql_skip_reason() -> str:
    """返回跳过原因。配置齐全且能连上测试库时返回空字符串。"""
    if not os.environ.get("MYSQL_USER") or "MYSQL_PASSWORD" not in os.environ:
        return "未配置 MYSQL_USER / MYSQL_PASSWORD"
    try:
        from backend.repositories.mysql_connection import TEST_DATABASE, connect

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
