from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPOSITORY_ENV_FILE = (
    _BACKEND_ROOT.parent / ".env" if (_BACKEND_ROOT.parent / "backend").is_dir() else _BACKEND_ROOT / ".env"
)


class Settings(BaseSettings):
    # Pydantic loads dotenv files in order, so the working directory must be last
    # to keep its values authoritative. The absolute fallback handles both the
    # source checkout (repo/.env) and the backend container (/app/.env).
    model_config = SettingsConfigDict(env_file=(str(_REPOSITORY_ENV_FILE), ".env"), extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    APP_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    APP_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    APP_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:80"
    APP_AUTH_COOKIE_SECURE: bool = False
    APP_AUTH_COOKIE_SAMESITE: str = "lax"
    APP_AUTO_CREATE_TABLES: bool = False

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "atp"
    POSTGRES_USER: str = "atp"
    POSTGRES_PASSWORD: str = "atp_password_change_me"
    POSTGRES_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=120)

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=120)

    # MinIO
    MINIO_HOST: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minio_password_change_me"
    MINIO_BUCKET: str = "atp"
    MINIO_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=120)
    # Large APK/video multipart uploads may need more than the short connect timeout.
    MINIO_READ_TIMEOUT_SECONDS: int = Field(default=60, ge=1, le=3600)
    # Lifecycle is reconciled only by the explicit ops command/Helm hook, never
    # during normal API startup. Expiration rules must use a scoped prefix.
    MINIO_LIFECYCLE_ABORT_INCOMPLETE_DAYS: int = Field(default=1, ge=1, le=3650)
    MINIO_LIFECYCLE_EXPIRATION_RULES_JSON: str = "[]"

    # First admin
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "Admin@123456"
    FIRST_ADMIN_EMAIL: str = "admin@example.com"

    # ADB
    ADB_SCAN_ENABLED: bool = True  # 设为 False 可关闭定时扫描（纯 Web 测试环境）
    ADB_SCAN_INTERVAL: int = 15  # 设备扫描间隔（秒）
    ADB_SCAN_MODE: str = "local"  # local=当前进程扫描；worker=投递到 mobile_special 队列
    # Windows Android Worker 注册信息；留空时普通 Worker 不会伪装成 Android Agent
    ANDROID_WORKER_ID: str = ""
    ANDROID_WORKER_QUEUE: str = "mobile_special"
    ANDROID_WORKER_REGISTRY_PREFIX: str = "atp:android-worker"
    ANDROID_WORKER_HEARTBEAT_SECONDS: int = 15
    ANDROID_WORKER_TTL_SECONDS: int = 45
    # ADB 自愈：执行器检测设备不可达时是否自动 disconnect/connect 重试（仅对 ip:port serial 生效）
    ADB_RECONNECT_ENABLED: bool = True
    ADB_RECONNECT_MAX_ATTEMPTS: int = 3  # ensure_reachable 总尝试次数（含首次）
    ADB_RECONNECT_BACKOFF_MS: str = "200,800,2000"  # 每次重试前退避（逗号分隔毫秒）
    # ADB 心跳监控：长任务（perf/stability/fluency/pytest）执行期间周期探测设备
    ADB_HEARTBEAT_ENABLED: bool = True
    ADB_HEARTBEAT_INTERVAL_SEC: int = 15
    ADB_HEARTBEAT_FAILURE_THRESHOLD: int = 2  # 连续 N 次失败后判定掉线并触发回调

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
    # Notification delivery history retention
    NOTIFICATION_DELIVERY_CLEANUP_ENABLED: bool = True
    NOTIFICATION_DELIVERY_RETENTION_DAYS: int = Field(default=30, ge=1, le=3650)
    # Audit log retention is opt-in because audit records may be subject to compliance retention.
    AUDIT_LOG_CLEANUP_ENABLED: bool = False
    AUDIT_LOG_RETENTION_DAYS: int = Field(default=365, ge=1, le=3650)
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

    # Worker 进程 Prometheus 指标端点（0 = 关闭；默认 9091）
    # backend 进程通过 /metrics 暴露指标；Celery worker 是独立进程，
    # 通过 prometheus_client.start_http_server(WORKER_METRICS_PORT) 暴露指标
    WORKER_METRICS_PORT: int = 9091
    # 当前 worker 实例监听的 Celery 队列，逗号分隔。默认监听全部队列，生产可按队列拆分 worker。
    CELERY_QUEUES: str = "default,android,mobile_special,ios,ai,maintenance,performance"
    SUITE_CHILD_TASK_TIMEOUT_SECONDS: int = 3600

    # Performance Center guardrails
    PERFORMANCE_TARGET_ALLOWLIST: str = ""  # comma-separated hostnames; empty = allow all
    PERFORMANCE_MAX_VUS: int = 50
    PERFORMANCE_MAX_DURATION_SECONDS: int = 900
    PERFORMANCE_METRICS_ENABLED: bool = True
    PERFORMANCE_METRICS_INTERVAL_SECONDS: float = 5.0
    PERFORMANCE_METRICS_MAX_SAMPLES: int = 7200
    PERFORMANCE_MINIO_INVENTORY_INTERVAL_SECONDS: int = 30
    # Performance load-injector node identity and local guardrails.
    PERFORMANCE_NODE_ENABLED: bool = True
    PERFORMANCE_NODE_ID: str = ""
    PERFORMANCE_NODE_NAME: str = ""
    PERFORMANCE_NODE_QUEUE: str = "performance"
    PERFORMANCE_NODE_MAX_VUS: int = 0
    PERFORMANCE_NODE_MAX_CONCURRENCY: int = 0
    PERFORMANCE_NODE_EGRESS_ALLOWLIST: str = ""
    PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS: int = 90
    # Comma-separated load injectors advertised by an explicit performance worker.
    PERFORMANCE_EXECUTORS: str = "k6,locust,grpc"

    # Web recorder. local keeps the existing in-process Windows development path;
    # worker routes browser commands through Redis to an independent recorder process.
    WEB_RECORDER_MODE: str = "local"
    WEB_RECORDER_WORKER_QUEUE_PREFIX: str = "atp:web-recording:commands"
    WEB_RECORDER_WORKER_ID: str = ""
    WEB_RECORDER_WORKER_MAX_SESSIONS: int = 2
    WEB_RECORDER_WORKER_HEARTBEAT_SECONDS: int = 5
    WEB_RECORDER_WORKER_TTL_SECONDS: int = 20
    WEB_RECORDER_COMMAND_TIMEOUT_SECONDS: int = 45
    WEB_RECORDER_REPLY_TTL_SECONDS: int = 60
    WEB_RECORDER_SESSION_TTL_SECONDS: int = 3600
    # Web recorder display (Linux remote deployments need an accessible X display)
    WEB_RECORDER_DISPLAY: str = ""

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
    # iter5 phase 2：人审通过的结构化 patch 写回用例（快照+审计+可选回归）。
    # 默认关闭——这是唯一会修改用例数据的自愈路径，须显式开启后 apply 接口才生效。
    AI_HEALING_APPLY_ENABLED: bool = False

    # OpenTelemetry / Jaeger
    # OTEL_EXPORTER_OTLP_ENDPOINT 留空时跳过 OTel 初始化（向后兼容纯 trace_id 模式）
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "atp-backend"
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: float = 0.1
    # Jaeger UI 基础 URL，前端展示"在 Jaeger 中打开"链接时使用；为空则不显示按钮
    JAEGER_UI_URL: str = ""

    @model_validator(mode="after")
    def validate_auth_cookie_settings(self) -> Self:
        samesite = self.APP_AUTH_COOKIE_SAMESITE.strip().lower()
        if samesite not in {"lax", "strict", "none"}:
            raise ValueError("APP_AUTH_COOKIE_SAMESITE must be one of lax, strict, none")
        if samesite == "none" and not self.APP_AUTH_COOKIE_SECURE:
            raise ValueError("APP_AUTH_COOKIE_SECURE must be true when APP_AUTH_COOKIE_SAMESITE=none")
        self.APP_AUTH_COOKIE_SAMESITE = samesite
        return self

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
