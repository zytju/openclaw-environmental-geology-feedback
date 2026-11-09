#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ -x "$HOME/.openclaw/tools/node/bin/node" ]; then
  EG_NODE="$HOME/.openclaw/tools/node/bin/node"
elif command -v node >/dev/null 2>&1; then
  EG_NODE="$(command -v node)"
else
  echo "请先按指南安装 OpenClaw，再关闭并重新打开终端。"
  read -r -p "按回车结束" _
  exit 1
fi
"$EG_NODE" course.mjs start
read -r -p "按回车结束" _
