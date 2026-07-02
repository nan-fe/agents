#!/usr/bin/env bash
# 将本地微博 Profile 同步到线上服务器，供 Docker 挂载后自动登录。
# 用法：bash scripts/sync-weibo-profile.sh [user@host] [remote_dir]
# 示例：bash scripts/sync-weibo-profile.sh root@your-server /root/agents/data/weibo-profile
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_PROFILE="${LOCAL_WEIBO_PROFILE:-$ROOT/data/weibo-profile}"
REMOTE="${1:-}"
REMOTE_DIR="${2:-/root/agents/data/weibo-profile}"

if [[ -z "$REMOTE" ]]; then
  echo "用法: bash scripts/sync-weibo-profile.sh <user@host> [remote_dir]"
  echo ""
  echo "  本地:  $LOCAL_PROFILE"
  echo "  远端:  <user@host>:$REMOTE_DIR"
  echo ""
  echo "先本地登录: bash scripts/weibo-login.sh"
  exit 1
fi

if [[ ! -d "$LOCAL_PROFILE" ]]; then
  echo "错误: 本地 Profile 不存在: $LOCAL_PROFILE"
  echo "请先运行: bash scripts/weibo-login.sh"
  exit 1
fi

echo "同步微博 Profile → $REMOTE:$REMOTE_DIR"
ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"
rsync -avz --delete \
  --exclude='SingletonLock' \
  --exclude='SingletonCookie' \
  --exclude='SingletonSocket' \
  --exclude='*/Cache/*' \
  --exclude='*/Code Cache/*' \
  --exclude='*/GPUCache/*' \
  --exclude='*/ShaderCache/*' \
  "$LOCAL_PROFILE/" "$REMOTE:$REMOTE_DIR/"

echo ""
echo "完成。线上 backend 容器会通过 /data/weibo-profile 挂载自动复用登录态。"
echo "若容器已在运行，无需重启；下次发布微博时会读取最新 Cookie。"
