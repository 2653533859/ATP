FROM python:3.12-slim-bookworm

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps

COPY . .

# 默认启动前应用有界 Alembic 重试；完整 Compose 栈由独立 migrate 服务先行迁移。
RUN chmod 0755 /app/docker-start.sh
ENTRYPOINT ["/app/docker-start.sh"]
CMD ["serve"]
