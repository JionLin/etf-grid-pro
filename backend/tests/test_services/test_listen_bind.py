"""本机开发默认只监听回环，并且不打开 Flask 调试器。"""
from backend.listen_bind import debug_enabled, resolve_listen_host


def test_listen_host_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    assert resolve_listen_host(None) == "127.0.0.1"
    assert resolve_listen_host("0.0.0.0") == "0.0.0.0"


def test_host_env_is_honored_for_containers(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    assert resolve_listen_host(None) == "0.0.0.0"


def test_debug_stays_off_when_flask_env_is_development(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert debug_enabled() is False
    assert debug_enabled(cli_debug=True) is True


def test_debug_turns_on_only_when_explicit(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert debug_enabled() is True
    monkeypatch.setenv("FLASK_DEBUG", "0")
    assert debug_enabled() is False
