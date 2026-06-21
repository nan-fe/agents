FROM python:3.11-slim

WORKDIR /app

# backend 依赖（ProductInfoService、Playwright 等）
COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r /tmp/backend-requirements.txt

# MCP 依赖
COPY mcp-product-scraper/requirements.txt /tmp/mcp-requirements.txt
RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r /tmp/mcp-requirements.txt

RUN python -m playwright install-deps chromium \
    && python -m playwright install chromium

COPY backend /app/backend
COPY mcp-product-scraper /app/mcp-product-scraper

WORKDIR /app/mcp-product-scraper

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend
ENV CHROMA_DB_PATH=/data/chroma_taobao_v1

EXPOSE 3100

CMD ["python", "-m", "server"]
