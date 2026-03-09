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

# 启动时先做当前模型建表兜底，再将 Alembic 版本对齐到最新。
CMD ["sh", "-c", "python -m app.bootstrap_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
