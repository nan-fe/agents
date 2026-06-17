# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt 文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --timeout=120 --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Playwright 商品页抓取需要 Chromium 及系统库（pip install playwright 不会自动装浏览器）
RUN python -m playwright install-deps chromium \
    && python -m playwright install chromium

# 复制项目代码
COPY . .

# 预下载 tiktoken 编码文件，避免运行时访问 openaipublic.blob.core.windows.net
RUN mkdir -p /app/app/data/tiktoken && \
    python -c "import urllib.request; urllib.request.urlretrieve('https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken', '/app/app/data/tiktoken/cl100k_base.tiktoken')"

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]