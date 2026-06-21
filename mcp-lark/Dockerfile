FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir --timeout=120 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -e ".[mcp]"

ENV PYTHONUNBUFFERED=1

EXPOSE 3101

CMD ["python", "-m", "server"]
