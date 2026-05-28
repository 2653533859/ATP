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
    # Dashboard alert suppression default; individual rules can override.
    DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN: int = 60

    # Rate limiting
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_WEBHOOK: str = "30/minute"

    # Logging
    LOG_LEVEL: str = ""  # DEBUG/INFO/WARNING/ERROR; 留空按 APP_ENV 自动选择

    # Slow query / Celery timeout 告警
    SLOW_QUERY_LOG_ENABLED: bool = True
    SLOW_QUERY_THRESHOLD_MS: int = 1000

    # Case snapshot retention
    CASE_SNAPSHOT_MAX_PER_CASE: int = 50

    # Mock standalone port (>0 启用独立 FastAPI 子应用监听独立端口，仅含 /mock 路由)
    # 当前实现保留为部署形态预留，启用方式见 docs/mock-standalone.md（待编写）
    MOCK_STANDALONE_PORT: int = 0

    # PostgreSQL 自动备份（F.2）
    DB_BACKUP_ENABLED: bool = False  # 默认关闭，运维侧按需启用
    DB_BACKUP_RETAIN_DAILY: int = 7  # 日备保留天数
    DB_BACKUP_RETAIN_WEEKLY: int = 4  # 周备保留份数
    DB_BACKUP_PREFIX: str = "pg-backups"  # MinIO 对象前缀

    # P3.A AI 用例自愈：失败 step 异步诊断（依赖项目 ai_llm_config 已配置）
    AI_HEALING_ENABLED: bool = False  # 默认关闭，启用后失败 step 自动入队 LLM 诊断
    AI_HEALING_TIMEOUT_SECONDS: int = 60  # LLM 调用超时，避免诊断任务长时间挂起
    AI_HEALING_DAILY_LIMIT: int = 100  # 每日 LLM 调用上限（0 = 不限）；超限走 skipped
    AI_HEALING_CACHE_TTL_SECONDS: int = 3600  # 相同错误特征缓存复用 TTL（0 = 关闭缓存）
    AI_HEALING_FEW_SHOT_ENABLED: bool = True  # 高质量历史示例注入 prompt
    AI_HEALING_FEW_SHOT_TOP_N: int = 3  # 同错误特征最多注入的示例数
    AI_HEALING_VISION_ENABLED: bool = False  # 多模态截图诊断总开关
    AI_HEALING_VISION_DAILY_LIMIT: int = 50  # 每日带图 LLM 调用上限（0 = 不限）

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
