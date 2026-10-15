#!/bin/bash
# 供 启动.command 调用。双击时先回到仓库目录，检查 uv / Node，并补一份 SQLite 配置。

mac_launcher_root() {
  cd "$(dirname "$0")" || exit 1
  if [ -n "${MAC_LAUNCHER_ROOT:-}" ]; then
    cd "$MAC_LAUNCHER_ROOT" || exit 1
  fi
}

_prepend_if_node() {
  local dir="$1"
  if [ -n "$dir" ] && [ -x "$dir/node" ]; then
    export PATH="$dir:$PATH"
  fi
}

prepend_node_from_managers() {
  local nvm_root="${NVM_DIR:-$HOME/.nvm}"
  local versions="$nvm_root/versions/node"
  if [ -d "$versions" ]; then
    local wanted="" candidate=""
    if [ -f "$nvm_root/alias/default" ]; then
      wanted=$(tr -d '[:space:]' < "$nvm_root/alias/default")
    fi
    if [ -n "$wanted" ] && [ -x "$versions/$wanted/bin/node" ]; then
      candidate="$versions/$wanted/bin"
    elif [ -n "$wanted" ] && [ -x "$versions/v${wanted#v}/bin/node" ]; then
      candidate="$versions/v${wanted#v}/bin"
    elif [ -n "$wanted" ] && [ -f "$nvm_root/alias/$wanted" ]; then
      local resolved
      resolved=$(tr -d '[:space:]' < "$nvm_root/alias/$wanted")
      if [ -x "$versions/$resolved/bin/node" ]; then
        candidate="$versions/$resolved/bin"
      fi
    fi
    if [ -z "$candidate" ]; then
      local latest
      latest=$(find "$versions" -mindepth 1 -maxdepth 1 -type d -name 'v*' 2>/dev/null | sort -V 2>/dev/null | tail -n 1)
      if [ -n "$latest" ]; then
        candidate="$latest/bin"
      fi
    fi
    _prepend_if_node "$candidate"
  fi

  local fnm_root="${FNM_DIR:-$HOME/.local/share/fnm}"
  _prepend_if_node "$fnm_root/aliases/default/bin"
  _prepend_if_node "$HOME/Library/Application Support/fnm/aliases/default/bin"
  _prepend_if_node "$HOME/.volta/bin"
}

ensure_tool_path() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
  prepend_node_from_managers
}

require_uv_and_node() {
  local missing=0
  if ! command -v uv >/dev/null 2>&1; then
    echo "未找到 uv。安装后再双击：https://docs.astral.sh/uv/"
    missing=1
  fi
  if ! command -v node >/dev/null 2>&1; then
    echo "未找到 Node。已检查 Homebrew、/usr/local/bin、nvm（~/.nvm 当前默认版本）、fnm 和 volta。"
    echo "若 Node 装在 nvm 里，请先执行 nvm alias default <版本>，或把 node 链接到 /usr/local/bin/node 后再双击。"
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
