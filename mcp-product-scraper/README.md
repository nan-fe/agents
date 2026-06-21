# 选品池 MCP Server

将选品池能力封装为 MCP（Model Context Protocol）工具，供 Cursor / Claude 等 Agent 调用。

## 架构

薄 MCP 层直接 import backend 的 `ProductInfoService`，与 FastAPI `/product_info/*` 共享同一套 CSV 与 RAG 索引。

```
Cursor → FastMCP HTTP (:3100/mcp) → ProductInfoService → CSV + Chroma
```

## 工具

| 工具 | 说明 |
|------|------|
| `scrape_product_preview` | 识别商品链接，返回预览 + `preview_token` |
| `confirm_product_preview` | 确认入库并更新 RAG |
| `scrape_and_save_product` | 跳过确认直接入库（仅用户明确要求时使用） |
| `list_products` | 列出选品池 |
| `get_product` | 商品详情 |
| `delete_product` | 删除商品 |

默认工作流：`scrape_product_preview` → 用户确认 → `confirm_product_preview`。

## 本地启动

```bash
# 1. 安装 MCP 依赖
cd mcp-product-scraper
pip install -r requirements.txt

# 2. 配置 backend/.env（LLM、Playwright 等）与 MCP Bearer Token
cp .env.example .env
# 编辑 .env 设置 MCP_BEARER_TOKEN

# 3. 启动（需 backend 依赖已安装：pip install -r ../backend/requirements.txt）
export MCP_BEARER_TOKEN="your-long-random-token"
PYTHONPATH=../backend python3 -m server
```

健康检查：`curl http://127.0.0.1:3100/health`

## Cursor 配置

复制 [`.cursor/mcp.json.example`](../.cursor/mcp.json.example) 为 `~/.cursor/mcp.json` 或项目 `.cursor/mcp.json`，填入 Bearer Token：

```json
{
  "mcpServers": {
    "product-scraper": {
      "url": "http://127.0.0.1:3100/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>"
      }
    }
  }
}
```

## Chroma 路径

backend 与 MCP 必须通过 `CHROMA_DB_PATH` 指向同一向量库目录（MCP bootstrap 默认设为 `../backend/chroma_taobao_v1`），否则 MCP 入库后 Studio 对话检索不到新商品。

## Docker

```bash
docker compose -f docker-compose.mcp.yml up -d --build
```

## 测试

```bash
cd mcp-product-scraper
PYTHONPATH=../backend pytest tests/ -q
```
