"""启动备份和日志只留一份，并且写到仓库约定的目录。"""
import logging
import sqlite3
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask

from backend.api.middleware import setup_logging
from backend.services.data.sqlite_backup import backup_sqlite_database


def test_sqlite_backup_keeps_the_newest_copies(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    database = tmp_path / "etf_grid.sqlite"
    monkeypatch.setenv("SQLITE_PATH", str(database))
    with sqlite3.connect(database) as conn:
        conn.execute("create table marks (id integer)")
        conn.execute("insert into marks values (1)")
    first = backup_sqlite_database(keep=2)
    with sqlite3.connect(database) as conn:
        conn.execute("insert into marks values (2)")
    second = backup_sqlite_database(keep=2)
    with sqlite3.connect(database) as conn:
        conn.execute("insert into marks values (3)")
    third = backup_sqlite_database(keep=2)

    snapshots = sorted((tmp_path / "backups").glob("etf_grid-*.sqlite"))
    assert snapshots == sorted([second, third])
    assert first not in snapshots
    with sqlite3.connect(third) as conn:
        assert conn.execute("select count(*) from marks").fetchone()[0] == 3


def test_mysql_and_empty_sqlite_are_not_copied(tmp_path, monkeypatch):
    empty = tmp_path / "empty.sqlite"
    empty.write_bytes(b"")
    monkeypatch.setenv("DB_TYPE", "sqlite")
    assert backup_sqlite_database(source=empty) is None
    monkeypatch.setenv("DB_TYPE", "mysql")
    database = tmp_path / "etf_grid.sqlite"
    database.write_bytes(b"not-empty")
    assert backup_sqlite_database(source=database) is None


def test_logging_rotates_under_repo_logs_without_a_second_handler(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    root = logging.getLogger()
    previous = list(root.handlers)
    stale_dir = tmp_path / "cwd"
    stale_dir.mkdir()
    stale = logging.FileHandler(stale_dir / "app.log")
    root.addHandler(stale)
    app = Flask("ops-log-test")
    app.debug = False
    app.logger.addHandler(logging.StreamHandler())
    try:
        setup_logging(app)
        setup_logging(app)
        app.logger.info("backup-line")
        text = (tmp_path / "app.log").read_text(encoding="utf-8")
        assert text.count("backup-line") == 1
        assert "backup-line" not in (stale_dir / "app.log").read_text(encoding="utf-8")
        matches = [
            handler for handler in root.handlers
            if getattr(handler, "baseFilename", None)
            and Path(handler.baseFilename).resolve() == (tmp_path / "app.log").resolve()
        ]
        assert len(matches) == 1
        assert isinstance(matches[0], RotatingFileHandler)
        assert matches[0].maxBytes == 10 * 1024 * 1024
        assert app.logger.handlers == []
    finally:
        for handler in list(root.handlers):
            if handler not in previous:
                root.removeHandler(handler)
                handler.close()
