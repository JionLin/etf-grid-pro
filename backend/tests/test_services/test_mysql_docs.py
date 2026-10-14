"""启动文档必须写明 MySQL，容器要带上连接环境变量。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_readme_does_not_call_sqlite_the_store():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "SQLite3" not in readme
    assert "本地 SQLite" not in readme
    assert "MYSQL_PASSWORD" in readme
    assert "不会回退到 SQLite" in readme


def test_compose_passes_mysql_settings():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for key in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
        assert key in compose
