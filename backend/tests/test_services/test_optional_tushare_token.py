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


def test_launcher_finds_the_nvm_default_node(tmp_path):
    node_bin = tmp_path / ".nvm" / "versions" / "node" / "v20.11.0" / "bin"
    node_bin.mkdir(parents=True)
    node = node_bin / "node"
    node.write_text("#!/bin/sh\necho nvm-node\n")
    node.chmod(0o755)
    alias = tmp_path / ".nvm" / "alias"
    alias.mkdir()
    (alias / "default").write_text("v20.11.0\n")
    fnm_bin = tmp_path / ".local" / "share" / "fnm" / "aliases" / "default" / "bin"
    fnm_bin.mkdir(parents=True)
    script = f"""
    unset NVM_DIR FNM_DIR
    export HOME="{tmp_path}"
    export PATH="/usr/bin:/bin"
    source "{ROOT}/scripts/mac_launcher.sh"
    ensure_tool_path
    command -v node
    """
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=True)
    assert str(node) in result.stdout


def test_launcher_hints_when_node_managers_are_missing(tmp_path):
    script = f"""
    unset NVM_DIR FNM_DIR
    export HOME="{tmp_path}"
    export PATH="/usr/bin:/bin"
    source "{ROOT}/scripts/mac_launcher.sh"
    ensure_tool_path
    require_uv_and_node
    """
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True)
    assert result.returncode != 0
    assert "nvm" in result.stdout
    assert "/usr/local/bin" in result.stdout


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
