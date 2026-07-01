# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

WORKDIR /app

# 先安装 monorepo 内的 lark-im SDK（审核飞书通知依赖）
COPY mcp-lark /mcp-lark
RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -e /mcp-lark

COPY backend/requirements.txt backend/requirements-social.txt ./
RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt \
    && pip install --no-cache-dir --timeout=120 \
    "browser-use>=0.12.0" -i https://pypi.org/simple

# Playwright 商品页抓取需要 Chromium 及系统库
RUN python -m playwright install-deps chromium \
    && python -m playwright install chromium

COPY backend .

RUN mkdir -p /app/app/data/tiktoken && \
    python -c "import urllib.request; urllib.request.urlretrieve('https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken', '/app/app/data/tiktoken/cl100k_base.tiktoken')"

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
