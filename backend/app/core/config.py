from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    APP_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    APP_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    APP_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:80"
    APP_AUTO_CREATE_TABLES: bool = False

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "atp"
    POSTGRES_USER: str = "atp"
    POSTGRES_PASSWORD: str = "atp_password_change_me"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # MinIO
    MINIO_HOST: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minio_password_change_me"
    MINIO_BUCKET: str = "atp"

    # First admin
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "Admin@123456"
    FIRST_ADMIN_EMAIL: str = "admin@example.com"

    # ADB
    ADB_SCAN_ENABLED: bool = True  # 设为 False 可关闭定时扫描（纯 Web 测试环境）
    ADB_SCAN_INTERVAL: int = 15  # 设备扫描间隔（秒）

    # CI/CD Webhook
    WEBHOOK_API_KEY: str = "atp-webhook-key-change-in-production"

    # SMTP 邮件通知
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_SSL: bool = True
    SMTP_TLS: bool = False

    # Encryption
    ENCRYPTION_KEY: str = ""  # Fernet key; leave empty to auto-derive from APP_SECRET_KEY

    # File retention
    FILE_RETENTION_DAYS: int = 30  # MinIO 中截图/报告文件保留天数
    STALE_PENDING_CLEANUP_ENABLED: bool = True
    STALE_PENDING_TIMEOUT_MINUTES: int = 120
    STALE_PENDING_CLEANUP_INTERVAL_SECONDS: int = 600
    # Run retention (终态运行记录清理)
    RUN_CLEANUP_ENABLED: bool = True
    RUN_RETENTION_DAYS: int = 90
    RUN_CLEANUP_BATCH_SIZE: int = 500
    # Storage alert (MinIO 使用率告警)
    STORAGE_ALERT_SIZE_GB: float = 0.0  # 0 表示关闭告警
    STORAGE_ALERT_INTERVAL_SECONDS: int = 3600
    # 单次告警扫描的最大对象数；超过即放弃本次计算（保护 MinIO list_objects 性能）
    STORAGE_ALERT_MAX_SCAN_OBJECTS: int = 100000

    # Rate limiting
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_WEBHOOK: str = "30/minute"

    # Logging
    LOG_LEVEL: str = ""  # DEBUG/INFO/WARNING/ERROR; 留空按 APP_ENV 自动选择

    # OpenTelemetry / Jaeger
    # OTEL_EXPORTER_OTLP_ENDPOINT 留空时跳过 OTel 初始化（向后兼容纯 trace_id 模式）
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "atp-backend"
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: float = 0.1
    # Jaeger UI 基础 URL，前端展示"在 Jaeger 中打开"链接时使用；为空则不显示按钮
    JAEGER_UI_URL: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CELERY_BROKER_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.APP_CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
