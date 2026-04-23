#!/usr/bin/env bash
# 从任意目录调用均可：切到 blivechat 仓库根再执行 PyInstaller（与 BUILD.md 方式 A 一致）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
exec python -m PyInstaller -y plugins/douyin-relay/douyin-relay.spec
