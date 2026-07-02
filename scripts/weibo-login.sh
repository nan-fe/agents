#!/usr/bin/env bash
# 本地用 open 打开 Playwright Chromium（与线上一致），登录态写入 data/weibo-profile。
# 用法：bash scripts/weibo-login.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

resolve_profile_dir() {
  local configured="${BROWSER_USE_PROFILE_PATH:-data/weibo-profile}"
  local path="$configured"
  if [[ "$path" != /* ]]; then
    path="$ROOT/$path"
  fi
  mkdir -p "$path"
  cd "$path" && pwd
}

PROFILE_DIR="$(resolve_profile_dir)"

find_playwright_chromium_app() {
  cd "$ROOT/backend"
  python3 - <<'PY'
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(1)

with sync_playwright() as p:
    exe = Path(p.chromium.executable_path)
    for parent in exe.parents:
        if parent.suffix == ".app":
            print(parent)
            sys.exit(0)
    print(exe)
PY
}

echo "== 微博登录 =="
echo "Profile: $PROFILE_DIR"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "此脚本仅支持 macOS（open 指令）。Linux 请手动："
  echo "  chromium --user-data-dir=\"$PROFILE_DIR\" https://weibo.com/"
  exit 1
fi

CHROMIUM_APP="$(find_playwright_chromium_app)" || true

if [[ -z "${CHROMIUM_APP:-}" ]]; then
  echo "未找到 Playwright Chromium，尝试安装："
  echo "  cd backend && python3 -m playwright install chromium"
  echo ""
  echo "或使用系统 Google Chrome："
  CHROMIUM_APP="Google Chrome"
fi

echo "打开浏览器，请完成微博登录/安全验证。"
echo "登录成功后关闭浏览器窗口，再同步到线上："
echo "  bash scripts/sync-weibo-profile.sh <user@host>"
echo ""

open -na "$CHROMIUM_APP" --args \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  --disable-blink-features=AutomationControlled \
  "https://weibo.com/"

echo "浏览器已启动。"
