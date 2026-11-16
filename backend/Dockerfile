# 构建阶段：编译工具链只留在这里，产出的 wheel 交给运行阶段安装
# （与 Dockerfile.worker 的 python-deps 阶段保持同一做法）。
FROM python:3.12-slim-bookworm AS python-deps

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# 运行阶段
FROM python:3.12-slim-bookworm

WORKDIR /app

# 系统依赖：只装运行时库，不带 gcc / libpq-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-deps /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels \
    && playwright install chromium --with-deps

COPY . .

# 默认启动前应用有界 Alembic 重试；完整 Compose 栈由独立 migrate 服务先行迁移。
RUN chmod 0755 /app/docker-start.sh
ENTRYPOINT ["/app/docker-start.sh"]
CMD ["serve"]
