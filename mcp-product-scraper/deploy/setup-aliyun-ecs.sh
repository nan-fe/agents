#!/usr/bin/env bash
set -euo pipefail

# 首次在阿里云 ECS 上准备 MCP 运行目录（数据卷、env 模板）
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$ROOT_DIR/data/chroma"
mkdir -p "$ROOT_DIR/backend/app/agents/product_rag_system/data"

if [[ ! -f "$ROOT_DIR/mcp-product-scraper/.env" ]]; then
  cp "$ROOT_DIR/mcp-product-scraper/.env.example" "$ROOT_DIR/mcp-product-scraper/.env"
  echo "Created mcp-product-scraper/.env — set MCP_BEARER_TOKEN before deploy."
fi

chmod +x "$ROOT_DIR/mcp-product-scraper/deploy/deploy-aliyun.sh"
echo "Setup complete."
