"""没配 MySQL 时给出跳过原因，并且不去连接。"""
from backend.tests.mysql_gate import mysql_skip_reason


def test_missing_account_does_not_open_a_connection(monkeypatch):
    monkeypatch.setenv("DB_TYPE", "mysql")
    monkeypatch.delenv("MYSQL_USER", raising=False)
    monkeypatch.delenv("MYSQL_PASSWORD", raising=False)

    def reject_connection(*_args, **_kwargs):
        raise AssertionError("未配置账号时不应连接 MySQL")

    monkeypatch.setattr("backend.repositories.mysql_connection.connect", reject_connection)
    assert mysql_skip_reason() == "未配置 MYSQL_USER / MYSQL_PASSWORD"


def test_storage_label_follows_db_type(monkeypatch):
    from backend.repositories.db_config import storage_label

    monkeypatch.setenv("DB_TYPE", "sqlite")
    assert storage_label() == "本机 SQLite"
    monkeypatch.setenv("DB_TYPE", "mysql")
    assert storage_label() == "本机 MySQL"
