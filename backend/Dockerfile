# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

WORKDIR /app

# 先安装 monorepo 内的 lark-im SDK（审核飞书通知依赖）
COPY mcp-lark /mcp-lark
RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -e /mcp-lark

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

# Playwright 商品页抓取需要 Chromium 及系统库
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && python -m playwright install-deps chromium \
    && python -m playwright install chromium

COPY backend .

RUN chmod +x docker-entrypoint.sh

ENV TIKTOKEN_CACHE_DIR=/app/app/data/tiktoken
ENV PYTHONUNBUFFERED=1
ENV X_PUBLISH_HEADLESS=true

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
