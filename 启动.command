#!/bin/bash
# 在 Finder 里双击即可。终端会停在这个窗口，方便看启动日志。
cd "$(dirname "$0")" || exit 1
export MAC_LAUNCHER_ROOT="$PWD"
# shellcheck disable=SC1091
source "$PWD/scripts/mac_launcher.sh"
ensure_tool_path
if ! require_uv_and_node; then
  echo ""
  read -r -p "按回车关闭..."
  exit 1
fi
ensure_sqlite_env "$PWD/.env"
exec "$PWD/start.sh"
