import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_blank_token_can_build_settings_and_blocks_only_tushare(monkeypatch):
    from backend.config.settings import Settings
    from backend.services.data.tushare_client import TushareClient

    settings = Settings(tushare_token="")
    assert settings.tushare_token == ""
    monkeypatch.setenv("TUSHARE_TOKEN", "")
    with pytest.raises(ValueError, match="TUSHARE_TOKEN"):
        TushareClient()


def test_launcher_writes_sqlite_env_without_a_token(tmp_path):
    env_file = tmp_path / ".env"
    script = f"""
    source "{ROOT}/scripts/mac_launcher.sh"
    write_sqlite_env "{env_file}"
    """
    subprocess.run(["bash", "-lc", script], check=True)
    text = env_file.read_text()
    assert "DB_TYPE=sqlite" in text
    assert "TUSHARE_TOKEN=\n" in text or text.endswith("TUSHARE_TOKEN=\n") or "TUSHARE_TOKEN=\n" in text


def test_launcher_reports_missing_uv_and_node():
    script = f"""
    source "{ROOT}/scripts/mac_launcher.sh"
    export PATH="/usr/bin:/bin"
    require_uv_and_node
    """
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True)
    assert result.returncode != 0
    assert "uv" in result.stdout
    assert "Node" in result.stdout
