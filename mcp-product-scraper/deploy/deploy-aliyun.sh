#!/usr/bin/env bash
set -euo pipefail

# 在 ECS 上拉取并启动 MCP 选品服务（需已配置 docker compose 与 ACR 镜像）
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

docker compose -f docker-compose.mcp.yml pull
docker compose -f docker-compose.mcp.yml up -d --remove-orphans

echo "MCP product-scraper deployed. Health: curl http://127.0.0.1:3100/health"
