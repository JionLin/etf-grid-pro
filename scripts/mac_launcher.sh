#!/bin/bash
# 供 启动.command 调用。双击时先回到仓库目录，检查 uv / Node，并补一份 SQLite 配置。

mac_launcher_root() {
  cd "$(dirname "$0")" || exit 1
  if [ -n "${MAC_LAUNCHER_ROOT:-}" ]; then
    cd "$MAC_LAUNCHER_ROOT" || exit 1
  fi
}

ensure_tool_path() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
}

require_uv_and_node() {
  local missing=0
  if ! command -v uv >/dev/null 2>&1; then
    echo "未找到 uv。安装后再双击：https://docs.astral.sh/uv/"
    missing=1
  fi
  if ! command -v node >/dev/null 2>&1; then
    echo "未找到 Node。安装 Node.js 后再双击。"
    missing=1
  fi
  return "$missing"
}

write_sqlite_env() {
  local target="${1:-.env}"
  cat > "$target" <<'EOF'
DB_TYPE=sqlite
SQLITE_PATH=data/etf_grid.sqlite
FLASK_ENV=development
FLASK_DEBUG=0
PORT=5001
LOG_LEVEL=INFO
TUSHARE_TOKEN=
EOF
}

ensure_sqlite_env() {
  local target="${1:-.env}"
  if [ -f "$target" ]; then
    return 0
  fi
  write_sqlite_env "$target"
  echo "已生成 SQLite 配置 $target。Tushare Token 留空即可，只有真正调用 Tushare 时才要填。"
}
