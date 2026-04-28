#!/usr/bin/env bash
# 从任意目录调用均可：切到 blivechat 仓库根再执行 PyInstaller（与 BUILD.md 一致）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
exec "$PY" -m PyInstaller -y plugins/queue-machine/queue-machine.spec
