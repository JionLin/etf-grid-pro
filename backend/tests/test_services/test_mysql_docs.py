"""启动文档必须写明 MySQL，容器要带上连接环境变量。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_readme_documents_sqlite_default_and_mysql_switch():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DB_TYPE" in readme
    assert "SQLITE_PATH" in example
    assert "DB_TYPE=sqlite" in example
    assert "MYSQL_PASSWORD" in readme
    assert "不会改回 SQLite" in readme


def test_compose_passes_mysql_settings():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for key in ("DB_TYPE", "SQLITE_PATH", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
        assert key in compose
