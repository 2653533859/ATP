<template>
  <div class="page-shell startup-config system-page">
    <section class="config-hero">
      <div class="hero-copy">
        <div class="eyebrow"><SettingOutlined /> {{ t('system_pages.startup_config.eyebrow') }}</div>
        <h1>{{ t('system_pages.startup_config.title') }}</h1>
        <p>{{ t('system_pages.startup_config.subtitle') }}</p>
      </div>
      <div class="hero-status">
        <a-tag :color="isReady ? 'success' : 'warning'">
          <CheckCircleFilled v-if="isReady" />
          <WarningFilled v-else />
          {{ isReady ? t('system_pages.startup_config.readiness_ready') : t('system_pages.startup_config.readiness_warn') }}
        </a-tag>
        <span class="draft-state">{{ isDirty ? t('system_pages.startup_config.draft_unsaved') : t('system_pages.startup_config.draft_saved') }}</span>
      </div>
    </section>

    <section class="boot-runway" :aria-label="t('system_pages.startup_config.steps.aria')">
      <div class="runway-step active">
        <span class="runway-index">01</span>
        <span>{{ t('system_pages.startup_config.steps.edit') }}</span>
      </div>
      <span class="runway-line" aria-hidden="true"></span>
      <div class="runway-step">
        <span class="runway-index">02</span>
        <span>{{ t('system_pages.startup_config.steps.export') }}</span>
      </div>
      <span class="runway-line" aria-hidden="true"></span>
      <div class="runway-step">
        <span class="runway-index">03</span>
        <span>{{ t('system_pages.startup_config.steps.restart') }}</span>
      </div>
    </section>

    <a-alert
      class="config-alert"
      type="info"
      show-icon
      :message="t('system_pages.startup_config.warning')"
      :description="t('system_pages.startup_config.storage_note')"
    />

    <section class="config-toolbar">
      <div class="toolbar-groups">
        <div class="profile-picker">
          <div class="toolbar-label">{{ t('system_pages.startup_config.profile_title') }}</div>
          <a-select
            v-model:value="selectedProfile"
            :options="profileOptions"
            :aria-label="t('system_pages.startup_config.profile_title')"
            style="min-width: 260px"
            @update:value="applyProfile"
          />
          <span class="profile-note">{{ t(profileDescriptionKey) }}</span>
        </div>
        <div>
          <div class="toolbar-label">{{ t('system_pages.startup_config.preset_title') }}</div>
          <a-space wrap>
            <a-button @click="applyPreset('docker')">
              <CloudServerOutlined /> {{ t('system_pages.startup_config.preset_docker') }}
            </a-button>
            <a-button @click="applyPreset('remote')">
              <GlobalOutlined /> {{ t('system_pages.startup_config.preset_remote') }}
            </a-button>
            <a-button @click="resetDefaults">
              <UndoOutlined /> {{ t('system_pages.startup_config.preset_reset') }}
            </a-button>
          </a-space>
        </div>
      </div>
      <a-space wrap>
        <a-button @click="saveDraft">
          <SaveOutlined /> {{ t('system_pages.startup_config.action.save') }}
        </a-button>
        <a-button @click="copyEnv">
          <CopyOutlined /> {{ t('system_pages.startup_config.action.copy') }}
        </a-button>
        <a-button type="primary" @click="downloadEnv">
          <DownloadOutlined /> {{ t('system_pages.startup_config.action.download') }}
        </a-button>
      </a-space>
    </section>

    <section class="readiness-strip">
      <div class="readiness-icon" :class="{ ready: isReady }">
        <CheckCircleFilled v-if="isReady" />
        <WarningFilled v-else />
      </div>
      <div class="readiness-copy">
        <strong>{{ t('system_pages.startup_config.readiness_title') }}</strong>
        <span v-if="missingRequired.length === 0">{{ t('system_pages.startup_config.fields_ready', { count: fieldCount }) }}</span>
        <span v-else>{{ t('system_pages.startup_config.required_missing', { fields: missingRequired.join(', ') }) }}</span>
      </div>
      <div class="readiness-meter" aria-hidden="true">
        <span :style="{ width: `${readinessPercent}%` }"></span>
      </div>
      <span class="readiness-percent">{{ readinessPercent }}%</span>
    </section>

    <section class="dependency-check-card">
      <div class="dependency-check-heading">
        <div>
          <h2>{{ t('system_pages.startup_config.dependency_title') }}</h2>
          <p>{{ t('system_pages.startup_config.dependency_description') }}</p>
        </div>
        <a-button :loading="dependencyLoading" @click="checkDependencies">
          {{ t('system_pages.startup_config.action.check_dependencies') }}
        </a-button>
      </div>
      <div v-if="dependencyRows.length" class="dependency-check-list">
        <a-tag v-for="item in dependencyRows" :key="item.key" :color="item.status === 'ok' ? 'success' : 'error'">
          {{ t(`system_pages.startup_config.dependencies.${item.key}`) }} ·
          {{ t(`system_pages.startup_config.dependency_status.${item.status}`) }}
          <span class="dependency-code">{{ t(`system_pages.startup_config.dependency_codes.${item.code}`) }}</span>
          <span class="dependency-latency">{{ item.latency_ms }}ms</span>
        </a-tag>
      </div>
      <span v-else class="dependency-empty">{{ t('system_pages.startup_config.dependency_unchecked') }}</span>
    </section>

    <a-tabs v-model:active-key="activeSection" class="config-tabs" type="card">
      <a-tab-pane v-for="section in sections" :key="section.key">
        <template #tab>
          <span class="tab-label">
            <component :is="section.icon" />
            {{ t(section.titleKey) }}
          </span>
        </template>

        <div class="section-heading">
          <div>
            <h2>{{ t(section.titleKey) }}</h2>
            <p>{{ t(section.subtitleKey) }}</p>
          </div>
          <span class="section-count">{{ section.fields.length }} {{ t('system_pages.startup_config.fields_unit') }}</span>
        </div>

        <div class="field-grid">
          <div
            v-for="field in section.fields"
            :key="field.key"
            class="field-wrap"
            :class="{ 'field-wide': field.kind === 'textarea' }"
          >
            <a-form-item :label="field.key">
              <template #extra>
                <div class="field-meta">
                  <span class="field-purpose">{{ t(fieldPurposeKey(field.key)) }}</span>
                  <span class="field-state" :class="{ required: field.required }">
                    {{ t(field.required ? 'system_pages.startup_config.required' : 'system_pages.startup_config.optional') }}
                  </span>
                </div>
              </template>
              <a-input
                v-if="field.kind === 'text'"
                :value="readValue(field.key)"
                :placeholder="field.placeholder"
                :aria-label="field.key"
                @update:value="updateValue(field.key, $event)"
              />
              <a-input-password
                v-else-if="field.kind === 'password'"
                :value="readValue(field.key)"
                :placeholder="field.placeholder"
                :aria-label="field.key"
                @update:value="updateValue(field.key, $event)"
              />
              <a-input-number
                v-else-if="field.kind === 'number'"
                :value="readNumber(field.key)"
                :min="field.min"
                :max="field.max"
                :step="field.step ?? 1"
                :style="{ width: '100%' }"
                :aria-label="field.key"
                @update:value="updateValue(field.key, $event)"
              />
              <a-textarea
                v-else-if="field.kind === 'textarea'"
                :value="readValue(field.key)"
                :rows="field.rows ?? 2"
                :placeholder="field.placeholder"
                :aria-label="field.key"
                @update:value="updateValue(field.key, $event)"
              />
              <a-select
                v-else-if="field.kind === 'select'"
                :value="readValue(field.key)"
                :options="field.options"
                :aria-label="field.key"
                style="width: 100%"
                @update:value="updateValue(field.key, $event)"
              />
              <div v-else class="switch-field">
                <a-switch
                  :checked="readBoolean(field.key)"
                  :aria-label="field.key"
                  @update:checked="updateValue(field.key, $event)"
                />
                <span>{{ readBoolean(field.key) ? t('common.enabled') : t('common.disabled') }}</span>
              </div>
            </a-form-item>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>

    <div class="config-footer">
      <span><SafetyCertificateOutlined /> {{ t('system_pages.startup_config.security_note') }}</span>
      <a-button type="link" @click="downloadEnv">{{ t('system_pages.startup_config.action.download') }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleFilled,
  CloudServerOutlined,
  CopyOutlined,
  DownloadOutlined,
  GlobalOutlined,
  SafetyCertificateOutlined,
  SaveOutlined,
  SettingOutlined,
  UndoOutlined,
  WarningFilled,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { healthApi, type DependencyHealthResponse } from '@/api'

type FieldKind = 'text' | 'password' | 'number' | 'textarea' | 'switch' | 'select'

interface StartupConfig {
  POSTGRES_HOST: string
  POSTGRES_PORT: number
  POSTGRES_DB: string
  POSTGRES_USER: string
  POSTGRES_PASSWORD: string
  POSTGRES_CONNECT_TIMEOUT_SECONDS: number
  REDIS_HOST: string
  REDIS_PORT: number
  REDIS_PASSWORD: string
  REDIS_CONNECT_TIMEOUT_SECONDS: number
  MINIO_HOST: string
  MINIO_PORT: number
  MINIO_ROOT_USER: string
  MINIO_ROOT_PASSWORD: string
  MINIO_BUCKET: string
  MINIO_CONNECT_TIMEOUT_SECONDS: number
  APP_ENV: string
  APP_SECRET_KEY: string
  APP_ACCESS_TOKEN_EXPIRE_MINUTES: number
  APP_REFRESH_TOKEN_EXPIRE_DAYS: number
  APP_CORS_ORIGINS: string
  APP_AUTH_COOKIE_SECURE: boolean
  APP_AUTH_COOKIE_SAMESITE: string
  APP_AUTO_CREATE_TABLES: boolean
  FIRST_ADMIN_USERNAME: string
  FIRST_ADMIN_PASSWORD: string
  FIRST_ADMIN_EMAIL: string
  WEBHOOK_API_KEY: string
  ENCRYPTION_KEY: string
  CELERY_CONCURRENCY: number
  CELERY_QUEUES: string
  SUITE_CHILD_TASK_TIMEOUT_SECONDS: number
  WORKER_METRICS_PORT: number
  FILE_RETENTION_DAYS: number
  STALE_PENDING_CLEANUP_ENABLED: boolean
  STALE_PENDING_TIMEOUT_MINUTES: number
  STALE_PENDING_CLEANUP_INTERVAL_SECONDS: number
  RUN_CLEANUP_ENABLED: boolean
  RUN_RETENTION_DAYS: number
  RUN_CLEANUP_BATCH_SIZE: number
  NOTIFICATION_DELIVERY_CLEANUP_ENABLED: boolean
  NOTIFICATION_DELIVERY_RETENTION_DAYS: number
  AUDIT_LOG_CLEANUP_ENABLED: boolean
  AUDIT_LOG_RETENTION_DAYS: number
  ADB_SCAN_ENABLED: boolean
  ADB_SCAN_INTERVAL: number
  ADB_SCAN_MODE: string
  ANDROID_WORKER_ID: string
  ANDROID_WORKER_QUEUE: string
  ANDROID_WORKER_REGISTRY_PREFIX: string
  ANDROID_WORKER_HEARTBEAT_SECONDS: number
  ANDROID_WORKER_TTL_SECONDS: number
  ADB_RECONNECT_ENABLED: boolean
  ADB_RECONNECT_MAX_ATTEMPTS: number
  ADB_RECONNECT_BACKOFF_MS: string
  ADB_HEARTBEAT_ENABLED: boolean
  ADB_HEARTBEAT_INTERVAL_SEC: number
  ADB_HEARTBEAT_FAILURE_THRESHOLD: number
  CASE_SNAPSHOT_MAX_PER_CASE: number
  MOCK_STANDALONE_PORT: number
  SMTP_HOST: string
  SMTP_PORT: number
  SMTP_USER: string
  SMTP_PASSWORD: string
  SMTP_FROM: string
  SMTP_SSL: boolean
  SMTP_TLS: boolean
  AI_HEALING_ENABLED: boolean
  AI_HEALING_TIMEOUT_SECONDS: number
  AI_HEALING_DAILY_LIMIT: number
  AI_HEALING_CACHE_TTL_SECONDS: number
  AI_HEALING_FEW_SHOT_ENABLED: boolean
  AI_HEALING_FEW_SHOT_TOP_N: number
  AI_HEALING_VISION_ENABLED: boolean
  AI_HEALING_VISION_DAILY_LIMIT: number
  AI_HEALING_APPLY_ENABLED: boolean
  PERFORMANCE_TARGET_ALLOWLIST: string
  PERFORMANCE_MAX_VUS: number
  PERFORMANCE_MAX_DURATION_SECONDS: number
  PERFORMANCE_METRICS_ENABLED: boolean
  PERFORMANCE_METRICS_INTERVAL_SECONDS: number
  PERFORMANCE_METRICS_MAX_SAMPLES: number
  PERFORMANCE_MINIO_INVENTORY_INTERVAL_SECONDS: number
  PERFORMANCE_NODE_ENABLED: boolean
  PERFORMANCE_NODE_ID: string
  PERFORMANCE_NODE_NAME: string
  PERFORMANCE_NODE_QUEUE: string
  PERFORMANCE_NODE_MAX_VUS: number
  PERFORMANCE_NODE_MAX_CONCURRENCY: number
  PERFORMANCE_NODE_EGRESS_ALLOWLIST: string
  PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS: number
  PERFORMANCE_EXECUTORS: string
  WEB_RECORDER_MODE: string
  WEB_RECORDER_WORKER_QUEUE_PREFIX: string
  WEB_RECORDER_WORKER_ID: string
  WEB_RECORDER_WORKER_MAX_SESSIONS: number
  WEB_RECORDER_WORKER_HEARTBEAT_SECONDS: number
  WEB_RECORDER_WORKER_TTL_SECONDS: number
  WEB_RECORDER_COMMAND_TIMEOUT_SECONDS: number
  WEB_RECORDER_REPLY_TTL_SECONDS: number
  WEB_RECORDER_SESSION_TTL_SECONDS: number
  WEB_RECORDER_DISPLAY: string
  RATE_LIMIT_LOGIN: string
  RATE_LIMIT_WEBHOOK: string
  LOG_LEVEL: string
  SLOW_QUERY_LOG_ENABLED: boolean
  SLOW_QUERY_THRESHOLD_MS: number
  STORAGE_ALERT_SIZE_GB: number
  STORAGE_ALERT_INTERVAL_SECONDS: number
  STORAGE_ALERT_MAX_SCAN_OBJECTS: number
  DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN: number
  DB_BACKUP_ENABLED: boolean
  DB_BACKUP_RETAIN_DAILY: number
  DB_BACKUP_RETAIN_WEEKLY: number
  DB_BACKUP_PREFIX: string
  OTEL_EXPORTER_OTLP_ENDPOINT: string
  OTEL_SERVICE_NAME: string
  OTEL_TRACES_SAMPLER: string
  OTEL_TRACES_SAMPLER_ARG: number
  JAEGER_UI_URL: string
  VITE_BACKEND_ORIGIN: string
}

type StartupProfile = 'local-all' | 'remote-infra' | 'android-agent' | 'performance-agent'

type FieldKey = keyof StartupConfig

interface FieldOption {
  label: string
  value: string
}

interface FieldDef {
  key: FieldKey
  kind: FieldKind
  required?: boolean
  placeholder?: string
  min?: number
  max?: number
  step?: number
  rows?: number
  options?: FieldOption[]
}

interface ConfigSection {
  key: string
  titleKey: string
  subtitleKey: string
  icon: object
  fields: FieldDef[]
}

const { t } = useI18n()
const STORAGE_KEY = 'atp-startup-config-draft-v1'
const PROFILE_STORAGE_KEY = 'atp-startup-profile-v1'
const SENSITIVE_CONFIG_KEYS = new Set<FieldKey>([
  'POSTGRES_PASSWORD',
  'REDIS_PASSWORD',
  'MINIO_ROOT_PASSWORD',
  'APP_SECRET_KEY',
  'FIRST_ADMIN_PASSWORD',
  'WEBHOOK_API_KEY',
  'ENCRYPTION_KEY',
  'SMTP_PASSWORD',
])
const PLACEHOLDER_VALUES: Partial<Record<FieldKey, string>> = {
  POSTGRES_HOST: '<server-host>',
  POSTGRES_USER: '<database-user>',
  REDIS_HOST: '<server-host>',
  MINIO_HOST: '<server-host>',
  MINIO_ROOT_USER: '<minio-user>',
  POSTGRES_PASSWORD: 'atp_password_change_me',
  MINIO_ROOT_PASSWORD: 'minio_password_change_me',
  APP_SECRET_KEY: 'change_this_to_a_random_secret_key_at_least_32_chars',
  FIRST_ADMIN_PASSWORD: 'change_me_before_use',
  WEBHOOK_API_KEY: 'change_this_to_a_random_webhook_key',
}

const defaultConfig: StartupConfig = {
  POSTGRES_HOST: 'postgres', POSTGRES_PORT: 5432, POSTGRES_DB: 'atp', POSTGRES_USER: 'atp', POSTGRES_PASSWORD: 'atp_password_change_me', POSTGRES_CONNECT_TIMEOUT_SECONDS: 5,
  REDIS_HOST: 'redis', REDIS_PORT: 6379, REDIS_PASSWORD: '', REDIS_CONNECT_TIMEOUT_SECONDS: 5,
  MINIO_HOST: 'minio', MINIO_PORT: 9000, MINIO_ROOT_USER: 'minioadmin', MINIO_ROOT_PASSWORD: 'minio_password_change_me', MINIO_BUCKET: 'atp', MINIO_CONNECT_TIMEOUT_SECONDS: 5,
  APP_ENV: 'development', APP_SECRET_KEY: 'change_this_to_a_random_secret_key_at_least_32_chars', APP_ACCESS_TOKEN_EXPIRE_MINUTES: 480,
  APP_REFRESH_TOKEN_EXPIRE_DAYS: 7, APP_CORS_ORIGINS: 'http://localhost,http://localhost:80,http://localhost:5173', APP_AUTH_COOKIE_SECURE: false, APP_AUTH_COOKIE_SAMESITE: 'lax', APP_AUTO_CREATE_TABLES: false,
  FIRST_ADMIN_USERNAME: 'parado', FIRST_ADMIN_PASSWORD: 'change_me_before_use', FIRST_ADMIN_EMAIL: 'admin@example.com', WEBHOOK_API_KEY: 'change_this_to_a_random_webhook_key', ENCRYPTION_KEY: '',
  CELERY_CONCURRENCY: 4, CELERY_QUEUES: 'default,android,mobile_special,ios,ai,maintenance,performance', SUITE_CHILD_TASK_TIMEOUT_SECONDS: 3600, WORKER_METRICS_PORT: 9091,
  FILE_RETENTION_DAYS: 30, STALE_PENDING_CLEANUP_ENABLED: true, STALE_PENDING_TIMEOUT_MINUTES: 120, STALE_PENDING_CLEANUP_INTERVAL_SECONDS: 600,
  RUN_CLEANUP_ENABLED: true, RUN_RETENTION_DAYS: 90, RUN_CLEANUP_BATCH_SIZE: 500,
  NOTIFICATION_DELIVERY_CLEANUP_ENABLED: true, NOTIFICATION_DELIVERY_RETENTION_DAYS: 30,
  AUDIT_LOG_CLEANUP_ENABLED: false, AUDIT_LOG_RETENTION_DAYS: 365,
  ADB_SCAN_ENABLED: true, ADB_SCAN_INTERVAL: 15, ADB_SCAN_MODE: 'local', ANDROID_WORKER_ID: '', ANDROID_WORKER_QUEUE: 'mobile_special', ANDROID_WORKER_REGISTRY_PREFIX: 'atp:android-worker', ANDROID_WORKER_HEARTBEAT_SECONDS: 15, ANDROID_WORKER_TTL_SECONDS: 45,
  ADB_RECONNECT_ENABLED: true, ADB_RECONNECT_MAX_ATTEMPTS: 3, ADB_RECONNECT_BACKOFF_MS: '200,800,2000',
  ADB_HEARTBEAT_ENABLED: true, ADB_HEARTBEAT_INTERVAL_SEC: 15, ADB_HEARTBEAT_FAILURE_THRESHOLD: 2, CASE_SNAPSHOT_MAX_PER_CASE: 50, MOCK_STANDALONE_PORT: 0,
  SMTP_HOST: '', SMTP_PORT: 465, SMTP_USER: '', SMTP_PASSWORD: '', SMTP_FROM: '', SMTP_SSL: true, SMTP_TLS: false,
  AI_HEALING_ENABLED: false, AI_HEALING_TIMEOUT_SECONDS: 60, AI_HEALING_DAILY_LIMIT: 100, AI_HEALING_CACHE_TTL_SECONDS: 3600,
  AI_HEALING_FEW_SHOT_ENABLED: true, AI_HEALING_FEW_SHOT_TOP_N: 3, AI_HEALING_VISION_ENABLED: false, AI_HEALING_VISION_DAILY_LIMIT: 50, AI_HEALING_APPLY_ENABLED: false,
  PERFORMANCE_TARGET_ALLOWLIST: '', PERFORMANCE_MAX_VUS: 50, PERFORMANCE_MAX_DURATION_SECONDS: 900,
  PERFORMANCE_METRICS_ENABLED: true, PERFORMANCE_METRICS_INTERVAL_SECONDS: 5, PERFORMANCE_METRICS_MAX_SAMPLES: 7200, PERFORMANCE_MINIO_INVENTORY_INTERVAL_SECONDS: 30,
  PERFORMANCE_NODE_ENABLED: true, PERFORMANCE_NODE_ID: '', PERFORMANCE_NODE_NAME: '', PERFORMANCE_NODE_QUEUE: 'performance', PERFORMANCE_NODE_MAX_VUS: 0, PERFORMANCE_NODE_MAX_CONCURRENCY: 0, PERFORMANCE_NODE_EGRESS_ALLOWLIST: '', PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS: 90,
  PERFORMANCE_EXECUTORS: 'k6,locust,grpc',
  WEB_RECORDER_MODE: 'local', WEB_RECORDER_WORKER_QUEUE_PREFIX: 'atp:web-recording:commands', WEB_RECORDER_WORKER_ID: '', WEB_RECORDER_WORKER_MAX_SESSIONS: 2,
  WEB_RECORDER_WORKER_HEARTBEAT_SECONDS: 5, WEB_RECORDER_WORKER_TTL_SECONDS: 20, WEB_RECORDER_COMMAND_TIMEOUT_SECONDS: 45, WEB_RECORDER_REPLY_TTL_SECONDS: 60, WEB_RECORDER_SESSION_TTL_SECONDS: 3600,
  WEB_RECORDER_DISPLAY: '',
  RATE_LIMIT_LOGIN: '5/minute', RATE_LIMIT_WEBHOOK: '30/minute', LOG_LEVEL: '', SLOW_QUERY_LOG_ENABLED: true, SLOW_QUERY_THRESHOLD_MS: 1000,
  STORAGE_ALERT_SIZE_GB: 0, STORAGE_ALERT_INTERVAL_SECONDS: 3600, STORAGE_ALERT_MAX_SCAN_OBJECTS: 100000, DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN: 60,
  DB_BACKUP_ENABLED: false, DB_BACKUP_RETAIN_DAILY: 7, DB_BACKUP_RETAIN_WEEKLY: 4, DB_BACKUP_PREFIX: 'pg-backups',
  OTEL_EXPORTER_OTLP_ENDPOINT: '', OTEL_SERVICE_NAME: 'atp-backend', OTEL_TRACES_SAMPLER: 'parentbased_traceidratio', OTEL_TRACES_SAMPLER_ARG: 0.1, JAEGER_UI_URL: '', VITE_BACKEND_ORIGIN: '',
}

const config = ref<StartupConfig>({ ...defaultConfig })
const activeSection = ref('infrastructure')
const selectedProfile = ref<StartupProfile>('local-all')
const initialSnapshot = ref(JSON.stringify(defaultConfig))
const dependencyLoading = ref(false)
const dependencyHealth = ref<DependencyHealthResponse | null>(null)

const text = (key: FieldKey, options: Partial<FieldDef> = {}): FieldDef => ({ key, kind: 'text', ...options })
const password = (key: FieldKey, options: Partial<FieldDef> = {}): FieldDef => ({ key, kind: 'password', ...options })
const number = (key: FieldKey, options: Partial<FieldDef> = {}): FieldDef => ({ key, kind: 'number', min: 0, ...options })
const textarea = (key: FieldKey, options: Partial<FieldDef> = {}): FieldDef => ({ key, kind: 'textarea', rows: 2, ...options })
const toggle = (key: FieldKey): FieldDef => ({ key, kind: 'switch' })
const select = (key: FieldKey, options: FieldOption[]): FieldDef => ({ key, kind: 'select', options })

const sections: ConfigSection[] = [
  {
    key: 'infrastructure', titleKey: 'system_pages.startup_config.sections.infrastructure.title', subtitleKey: 'system_pages.startup_config.sections.infrastructure.subtitle', icon: CloudServerOutlined,
    fields: [
      text('POSTGRES_HOST', { required: true }), number('POSTGRES_PORT', { max: 65535 }), text('POSTGRES_DB', { required: true }), text('POSTGRES_USER', { required: true }), password('POSTGRES_PASSWORD', { required: true }), number('POSTGRES_CONNECT_TIMEOUT_SECONDS', { min: 1, max: 120 }),
      text('REDIS_HOST', { required: true }), number('REDIS_PORT', { max: 65535 }), password('REDIS_PASSWORD'), number('REDIS_CONNECT_TIMEOUT_SECONDS', { min: 1, max: 120 }),
      text('MINIO_HOST', { required: true }), number('MINIO_PORT', { max: 65535 }), text('MINIO_ROOT_USER', { required: true }), password('MINIO_ROOT_PASSWORD', { required: true }), text('MINIO_BUCKET', { required: true }), number('MINIO_CONNECT_TIMEOUT_SECONDS', { min: 1, max: 120 }),
    ],
  },
  {
    key: 'application', titleKey: 'system_pages.startup_config.sections.application.title', subtitleKey: 'system_pages.startup_config.sections.application.subtitle', icon: SafetyCertificateOutlined,
    fields: [
      select('APP_ENV', [{ label: 'development', value: 'development' }, { label: 'test', value: 'test' }, { label: 'production', value: 'production' }]), password('APP_SECRET_KEY', { required: true }),
      number('APP_ACCESS_TOKEN_EXPIRE_MINUTES'), number('APP_REFRESH_TOKEN_EXPIRE_DAYS'), textarea('APP_CORS_ORIGINS', { required: true, rows: 3 }), toggle('APP_AUTH_COOKIE_SECURE'), select('APP_AUTH_COOKIE_SAMESITE', [{ label: 'lax', value: 'lax' }, { label: 'strict', value: 'strict' }, { label: 'none', value: 'none' }]), toggle('APP_AUTO_CREATE_TABLES'),
      text('FIRST_ADMIN_USERNAME', { required: true }), password('FIRST_ADMIN_PASSWORD', { required: true }), text('FIRST_ADMIN_EMAIL', { required: true }), password('WEBHOOK_API_KEY', { required: true }), password('ENCRYPTION_KEY'),
    ],
  },
  {
    key: 'execution', titleKey: 'system_pages.startup_config.sections.execution.title', subtitleKey: 'system_pages.startup_config.sections.execution.subtitle', icon: GlobalOutlined,
    fields: [
      number('CELERY_CONCURRENCY'), textarea('CELERY_QUEUES'), number('SUITE_CHILD_TASK_TIMEOUT_SECONDS'), number('WORKER_METRICS_PORT', { max: 65535 }), number('FILE_RETENTION_DAYS'),
      toggle('STALE_PENDING_CLEANUP_ENABLED'), number('STALE_PENDING_TIMEOUT_MINUTES'), number('STALE_PENDING_CLEANUP_INTERVAL_SECONDS'), toggle('RUN_CLEANUP_ENABLED'), number('RUN_RETENTION_DAYS'), number('RUN_CLEANUP_BATCH_SIZE'), toggle('NOTIFICATION_DELIVERY_CLEANUP_ENABLED'), number('NOTIFICATION_DELIVERY_RETENTION_DAYS', { min: 1, max: 3650 }), toggle('AUDIT_LOG_CLEANUP_ENABLED'), number('AUDIT_LOG_RETENTION_DAYS', { min: 1, max: 3650 }),
      toggle('ADB_SCAN_ENABLED'), number('ADB_SCAN_INTERVAL'), select('ADB_SCAN_MODE', [{ label: 'local', value: 'local' }, { label: 'worker', value: 'worker' }]), text('ANDROID_WORKER_ID'), text('ANDROID_WORKER_QUEUE'), text('ANDROID_WORKER_REGISTRY_PREFIX'), number('ANDROID_WORKER_HEARTBEAT_SECONDS'), number('ANDROID_WORKER_TTL_SECONDS'), toggle('ADB_RECONNECT_ENABLED'), number('ADB_RECONNECT_MAX_ATTEMPTS'), text('ADB_RECONNECT_BACKOFF_MS'), toggle('ADB_HEARTBEAT_ENABLED'), number('ADB_HEARTBEAT_INTERVAL_SEC'), number('ADB_HEARTBEAT_FAILURE_THRESHOLD'),
      number('CASE_SNAPSHOT_MAX_PER_CASE'), number('MOCK_STANDALONE_PORT', { max: 65535 }), select('WEB_RECORDER_MODE', [{ label: 'local', value: 'local' }, { label: 'worker', value: 'worker' }]), textarea('WEB_RECORDER_WORKER_QUEUE_PREFIX'), text('WEB_RECORDER_WORKER_ID'), number('WEB_RECORDER_WORKER_MAX_SESSIONS'), number('WEB_RECORDER_WORKER_HEARTBEAT_SECONDS'), number('WEB_RECORDER_WORKER_TTL_SECONDS'), number('WEB_RECORDER_COMMAND_TIMEOUT_SECONDS'), number('WEB_RECORDER_REPLY_TTL_SECONDS'), number('WEB_RECORDER_SESSION_TTL_SECONDS'), text('WEB_RECORDER_DISPLAY'),
    ],
  },
  {
    key: 'integrations', titleKey: 'system_pages.startup_config.sections.integrations.title', subtitleKey: 'system_pages.startup_config.sections.integrations.subtitle', icon: SettingOutlined,
    fields: [
      text('SMTP_HOST'), number('SMTP_PORT', { max: 65535 }), text('SMTP_USER'), password('SMTP_PASSWORD'), text('SMTP_FROM'), toggle('SMTP_SSL'), toggle('SMTP_TLS'),
      toggle('AI_HEALING_ENABLED'), number('AI_HEALING_TIMEOUT_SECONDS'), number('AI_HEALING_DAILY_LIMIT'), number('AI_HEALING_CACHE_TTL_SECONDS'), toggle('AI_HEALING_FEW_SHOT_ENABLED'), number('AI_HEALING_FEW_SHOT_TOP_N'), toggle('AI_HEALING_VISION_ENABLED'), number('AI_HEALING_VISION_DAILY_LIMIT'), toggle('AI_HEALING_APPLY_ENABLED'),
      textarea('PERFORMANCE_TARGET_ALLOWLIST'), number('PERFORMANCE_MAX_VUS'), number('PERFORMANCE_MAX_DURATION_SECONDS'), toggle('PERFORMANCE_METRICS_ENABLED'), number('PERFORMANCE_METRICS_INTERVAL_SECONDS', { step: 0.1 }), number('PERFORMANCE_METRICS_MAX_SAMPLES'), number('PERFORMANCE_MINIO_INVENTORY_INTERVAL_SECONDS'), toggle('PERFORMANCE_NODE_ENABLED'), text('PERFORMANCE_NODE_ID'), text('PERFORMANCE_NODE_NAME'), text('PERFORMANCE_NODE_QUEUE'), number('PERFORMANCE_NODE_MAX_VUS'), number('PERFORMANCE_NODE_MAX_CONCURRENCY'), textarea('PERFORMANCE_NODE_EGRESS_ALLOWLIST'), number('PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS'), textarea('PERFORMANCE_EXECUTORS'),
      text('RATE_LIMIT_LOGIN'), text('RATE_LIMIT_WEBHOOK'), select('LOG_LEVEL', [{ label: '(auto)', value: '' }, { label: 'DEBUG', value: 'DEBUG' }, { label: 'INFO', value: 'INFO' }, { label: 'WARNING', value: 'WARNING' }, { label: 'ERROR', value: 'ERROR' }]),
      toggle('SLOW_QUERY_LOG_ENABLED'), number('SLOW_QUERY_THRESHOLD_MS'), number('STORAGE_ALERT_SIZE_GB', { step: 0.1 }), number('STORAGE_ALERT_INTERVAL_SECONDS'), number('STORAGE_ALERT_MAX_SCAN_OBJECTS'), number('DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN'),
      toggle('DB_BACKUP_ENABLED'), number('DB_BACKUP_RETAIN_DAILY'), number('DB_BACKUP_RETAIN_WEEKLY'), text('DB_BACKUP_PREFIX'),
      text('OTEL_EXPORTER_OTLP_ENDPOINT'), text('OTEL_SERVICE_NAME'), select('OTEL_TRACES_SAMPLER', [{ label: 'parentbased_traceidratio', value: 'parentbased_traceidratio' }, { label: 'always_on', value: 'always_on' }, { label: 'always_off', value: 'always_off' }]), number('OTEL_TRACES_SAMPLER_ARG', { min: 0, max: 1, step: 0.01 }), text('JAEGER_UI_URL'), text('VITE_BACKEND_ORIGIN'),
    ],
  },
]

const profileOptions = computed<FieldOption[]>(() => ([
  { label: t('system_pages.startup_config.profiles.local_all'), value: 'local-all' },
  { label: t('system_pages.startup_config.profiles.remote_infra'), value: 'remote-infra' },
  { label: t('system_pages.startup_config.profiles.android_agent'), value: 'android-agent' },
  { label: t('system_pages.startup_config.profiles.performance_agent'), value: 'performance-agent' },
]))
const profileDescriptionKey = computed<string>(() => `system_pages.startup_config.profile_descriptions.${selectedProfile.value}`)
const profileMessageKeys: Record<StartupProfile, string> = {
  'local-all': 'system_pages.startup_config.messages.profile_local_all',
  'remote-infra': 'system_pages.startup_config.messages.profile_remote_infra',
  'android-agent': 'system_pages.startup_config.messages.profile_android_agent',
  'performance-agent': 'system_pages.startup_config.messages.profile_performance_agent',
}
const isStartupProfile = (value: unknown): value is StartupProfile => (
  value === 'local-all' || value === 'remote-infra' || value === 'android-agent' || value === 'performance-agent'
)

const allFields = computed(() => sections.flatMap((section) => section.fields))
const fieldCount = computed(() => allFields.value.length)
const missingRequired = computed(() => {
  const missing = new Set<string>(allFields.value
    .filter((field) => field.required && !readValue(field.key).trim())
    .map((field) => field.key))

  for (const [key, placeholder] of Object.entries(PLACEHOLDER_VALUES) as [FieldKey, string][]) {
    if (key !== 'APP_SECRET_KEY' && readValue(key).trim() === placeholder) {
      missing.add(key)
    }
  }

  const appSecretKey = config.value.APP_SECRET_KEY.trim()
  if (appSecretKey && (appSecretKey.length < 32 || appSecretKey === PLACEHOLDER_VALUES.APP_SECRET_KEY)) {
    missing.add('APP_SECRET_KEY (>=32, not the example value)')
  }
  return [...missing]
})
const isReady = computed(() => missingRequired.value.length === 0)
const isDirty = computed(() => JSON.stringify(config.value) !== initialSnapshot.value)
const readinessPercent = computed(() => Math.round(((fieldCount.value - missingRequired.value.length) / fieldCount.value) * 100))
const dependencyRows = computed(() => {
  const dependencies = dependencyHealth.value?.dependencies
  if (!dependencies) return []
  return Object.entries(dependencies).map(([key, item]) => ({ key, ...item }))
})

function readValue(key: FieldKey): string {
  const value = config.value[key]
  return value === undefined || value === null ? '' : String(value)
}

function readNumber(key: FieldKey): number | undefined {
  const value = config.value[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function readBoolean(key: FieldKey): boolean {
  return Boolean(config.value[key])
}

function fieldPurposeKey(key: FieldKey) {
  return `system_pages.startup_config.fields.${key}`
}

function updateValue(key: FieldKey, value: unknown) {
  const current = config.value[key]
  if (typeof current === 'boolean') {
    config.value[key] = Boolean(value) as never
  } else if (typeof current === 'number') {
    config.value[key] = (value === null || value === undefined || value === '' ? 0 : Number(value)) as never
  } else {
    config.value[key] = String(value ?? '') as never
  }
}

function applyPreset(preset: 'docker' | 'remote') {
  const hosts = preset === 'docker'
    ? { postgres: 'postgres', redis: 'redis', minio: 'minio' }
    : { postgres: '<server-host>', redis: '<server-host>', minio: '<server-host>' }
  config.value.POSTGRES_HOST = hosts.postgres
  config.value.REDIS_HOST = hosts.redis
  config.value.MINIO_HOST = hosts.minio
  if (preset === 'remote') {
    config.value.POSTGRES_DB = 'atp'
    config.value.POSTGRES_USER = '<database-user>'
    config.value.MINIO_ROOT_USER = '<minio-user>'
    config.value.MINIO_BUCKET = 'atp'
  }
  config.value.APP_ENV = 'development'
  config.value.APP_CORS_ORIGINS = 'http://localhost,http://localhost:80,http://localhost:5173'
  selectedProfile.value = preset === 'docker' ? 'local-all' : 'remote-infra'
  message.success(t(preset === 'docker' ? 'system_pages.startup_config.messages.preset_docker' : 'system_pages.startup_config.messages.preset_remote'))
}

function applyProfile(value: unknown) {
  if (!isStartupProfile(value)) return
  const profile = value
  selectedProfile.value = profile
  const remoteHosts = { postgres: '<server-host>', redis: '<server-host>', minio: '<server-host>' }
  if (profile === 'local-all') {
    Object.assign(config.value, {
      POSTGRES_HOST: 'postgres', REDIS_HOST: 'redis', MINIO_HOST: 'minio', APP_ENV: 'development',
      CELERY_QUEUES: 'default,android,mobile_special,ios,ai,maintenance,performance', ADB_SCAN_ENABLED: true, ADB_SCAN_MODE: 'local',
      ANDROID_WORKER_ID: '', PERFORMANCE_NODE_ENABLED: false, PERFORMANCE_NODE_ID: '', PERFORMANCE_NODE_NAME: '', PERFORMANCE_NODE_QUEUE: 'performance',
      PERFORMANCE_EXECUTORS: 'k6,locust,grpc', WEB_RECORDER_MODE: 'local',
    })
  } else if (profile === 'remote-infra') {
    Object.assign(config.value, {
      POSTGRES_HOST: remoteHosts.postgres, REDIS_HOST: remoteHosts.redis, MINIO_HOST: remoteHosts.minio, APP_ENV: 'development',
      POSTGRES_DB: 'atp', POSTGRES_USER: '<database-user>', MINIO_ROOT_USER: '<minio-user>', MINIO_BUCKET: 'atp',
      CELERY_QUEUES: 'default,android,mobile_special,ios,ai,maintenance,performance', ADB_SCAN_ENABLED: true, ADB_SCAN_MODE: 'local',
      ANDROID_WORKER_ID: '', PERFORMANCE_NODE_ENABLED: false, PERFORMANCE_NODE_ID: '', PERFORMANCE_NODE_NAME: '', PERFORMANCE_NODE_QUEUE: 'performance',
      PERFORMANCE_EXECUTORS: 'k6,locust,grpc', WEB_RECORDER_MODE: 'local',
    })
  } else if (profile === 'android-agent') {
    Object.assign(config.value, {
      POSTGRES_HOST: remoteHosts.postgres, REDIS_HOST: remoteHosts.redis, MINIO_HOST: remoteHosts.minio, APP_ENV: 'production',
      POSTGRES_DB: 'atp', POSTGRES_USER: '<database-user>', MINIO_ROOT_USER: '<minio-user>', MINIO_BUCKET: 'atp', CELERY_QUEUES: 'android,mobile_special',
      ADB_SCAN_ENABLED: true, ADB_SCAN_MODE: 'local', ANDROID_WORKER_ID: '', PERFORMANCE_NODE_ENABLED: false, PERFORMANCE_NODE_ID: '',
      PERFORMANCE_NODE_NAME: '', PERFORMANCE_NODE_QUEUE: 'performance', PERFORMANCE_EXECUTORS: 'k6,locust,grpc', WEB_RECORDER_MODE: 'local',
    })
  } else {
    Object.assign(config.value, {
      POSTGRES_HOST: remoteHosts.postgres, REDIS_HOST: remoteHosts.redis, MINIO_HOST: remoteHosts.minio, APP_ENV: 'production',
      POSTGRES_DB: 'atp', POSTGRES_USER: '<database-user>', MINIO_ROOT_USER: '<minio-user>', MINIO_BUCKET: 'atp', CELERY_QUEUES: 'performance.worker-a',
      ADB_SCAN_ENABLED: false, ADB_SCAN_MODE: 'local', ANDROID_WORKER_ID: '', PERFORMANCE_NODE_ENABLED: true,
      PERFORMANCE_NODE_ID: 'performance-win-worker-a', PERFORMANCE_NODE_NAME: 'Windows 性能节点 A', PERFORMANCE_NODE_QUEUE: 'performance.worker-a',
      PERFORMANCE_EXECUTORS: 'jmeter,grpc', WEB_RECORDER_MODE: 'local',
    })
  }
  message.success(t(profileMessageKeys[profile]))
}

function resetDefaults() {
  config.value = { ...defaultConfig }
  selectedProfile.value = 'local-all'
  message.success(t('system_pages.startup_config.messages.reset'))
}

async function checkDependencies() {
  dependencyLoading.value = true
  try {
    dependencyHealth.value = await healthApi.dependencies()
    if (dependencyHealth.value.status === 'ok') {
      message.success(t('system_pages.startup_config.messages.dependencies_ready'))
    } else {
      message.warning(t('system_pages.startup_config.messages.dependencies_degraded'))
    }
  } catch (error) {
    message.error(String(error))
  } finally {
    dependencyLoading.value = false
  }
}

function saveDraft() {
  const safeDraft = Object.fromEntries(
    Object.entries(config.value).filter(([key]) => !SENSITIVE_CONFIG_KEYS.has(key as FieldKey)),
  )
  localStorage.setItem(STORAGE_KEY, JSON.stringify(safeDraft))
  localStorage.setItem(PROFILE_STORAGE_KEY, selectedProfile.value)
  initialSnapshot.value = JSON.stringify(config.value)
  message.success(t('system_pages.startup_config.messages.saved'))
}

function loadDraft() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return
  try {
    const saved = JSON.parse(raw) as Partial<StartupConfig>
    const safeSaved = Object.fromEntries(
      Object.entries(saved).filter(([key]) => !SENSITIVE_CONFIG_KEYS.has(key as FieldKey)),
    ) as Partial<StartupConfig>
    if (Object.keys(safeSaved).length !== Object.keys(saved).length) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(safeSaved))
    }
    config.value = { ...defaultConfig, ...safeSaved }
    const savedProfile = localStorage.getItem(PROFILE_STORAGE_KEY)
    if (savedProfile === 'local-all' || savedProfile === 'remote-infra' || savedProfile === 'android-agent' || savedProfile === 'performance-agent') {
      selectedProfile.value = savedProfile
    }
    initialSnapshot.value = JSON.stringify(config.value)
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
}

function envValue(value: unknown): string {
  const raw = typeof value === 'boolean' ? String(value) : String(value ?? '')
  if (!raw || /^[A-Za-z0-9_./:@,+%=-]+$/.test(raw)) return raw
  return `"${raw.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r?\n/g, '\\n')}"`
}

const envContent = computed(() => {
  const header = '# ATP startup configuration — generated by the Startup Config page\n# Replace the repository root .env, then restart backend / worker / beat.\n\n'
  return `${header}${allFields.value.map((field) => `${field.key}=${envValue(config.value[field.key])}`).join('\n')}\n`
})

async function copyEnv() {
  try {
    await navigator.clipboard.writeText(envContent.value)
  } catch {
    const textareaElement = document.createElement('textarea')
    textareaElement.value = envContent.value
    textareaElement.style.position = 'fixed'
    textareaElement.style.opacity = '0'
    document.body.appendChild(textareaElement)
    textareaElement.select()
    document.execCommand('copy')
    textareaElement.remove()
  }
  message.success(t('system_pages.startup_config.messages.copied'))
}

function downloadEnv() {
  const blob = new Blob([envContent.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '.env'
  anchor.click()
  URL.revokeObjectURL(url)
  message.success(t('system_pages.startup_config.messages.downloaded'))
}

onMounted(loadDraft)
</script>

<style scoped>
.startup-config {
  padding-bottom: 20px;
}

.config-hero {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  overflow: hidden;
  padding: 28px 30px;
  border-radius: 18px;
  color: #fff;
  background:
    radial-gradient(circle at 84% 10%, rgba(165, 180, 252, 0.34), transparent 32%),
    linear-gradient(120deg, #111827 0%, #1e1b4b 56%, #4338ca 100%);
  box-shadow: 0 14px 32px rgba(30, 27, 75, 0.2);
}

.config-hero::after {
  position: absolute;
  right: 9%;
  bottom: -48px;
  width: 180px;
  height: 180px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 50%;
  content: '';
}

.hero-copy,
.hero-status {
  position: relative;
  z-index: 1;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #c7d2fe;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.config-hero h1 {
  margin: 10px 0 6px;
  font-size: 30px;
  letter-spacing: -0.035em;
}

.config-hero p {
  max-width: 680px;
  margin: 0;
  color: #dbeafe;
  font-size: 14px;
}

.hero-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.draft-state {
  color: #c7d2fe;
  font-size: 12px;
}

.boot-runway {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 4px 2px;
}

.runway-step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--c-text-tertiary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.runway-step.active {
  color: var(--c-primary);
}

.runway-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid var(--c-border-strong);
  border-radius: 50%;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11px;
}

.active .runway-index {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-primary-soft);
}

.runway-line {
  width: 54px;
  height: 1px;
  background: var(--c-border);
}

.config-alert {
  margin-top: 14px;
}

.config-toolbar,
.readiness-strip,
.config-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.config-toolbar {
  margin-top: 14px;
}

.toolbar-groups {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 24px;
}

.profile-picker {
  display: flex;
  min-width: 320px;
  flex-direction: column;
  gap: 6px;
}

.profile-note {
  max-width: 430px;
  color: var(--c-text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.toolbar-label {
  margin-bottom: 8px;
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.readiness-strip {
  justify-content: flex-start;
  margin-top: 14px;
}

.readiness-icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border-radius: 10px;
  color: var(--c-warning);
  background: var(--c-warning-soft);
}

.readiness-icon.ready {
  color: var(--c-success);
  background: var(--c-success-soft);
}

.readiness-copy {
  display: flex;
  min-width: 220px;
  flex-direction: column;
  gap: 3px;
}

.readiness-copy strong {
  color: var(--c-text);
  font-size: 13px;
}

.readiness-copy span {
  overflow: hidden;
  color: var(--c-text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.readiness-meter {
  height: 6px;
  flex: 1;
  overflow: hidden;
  border-radius: 999px;
  background: var(--c-bg-subtle);
}

.readiness-meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--c-warning), var(--c-primary));
  transition: width 0.3s ease;
}

.readiness-percent {
  min-width: 42px;
  color: var(--c-primary);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
  text-align: right;
}

.dependency-check-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 14px;
  padding: 16px 18px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.dependency-check-heading h2 {
  margin: 0;
  color: var(--c-text);
  font-size: 15px;
}

.dependency-check-heading p {
  margin: 5px 0 0;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.dependency-check-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.dependency-latency {
  margin-left: 4px;
  opacity: 0.72;
}

.dependency-code {
  margin-left: 4px;
  font-weight: 500;
  opacity: 0.82;
}

.dependency-empty {
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.config-tabs {
  margin-top: 14px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin: 6px 0 18px;
}

.section-heading h2 {
  margin: 0;
  color: var(--c-text);
  font-size: 18px;
}

.section-heading p {
  margin: 5px 0 0;
  color: var(--c-text-secondary);
  font-size: 13px;
}

.section-count {
  flex: none;
  padding: 5px 9px;
  border-radius: 999px;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 22px;
  padding: 20px 22px 6px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.field-wide {
  grid-column: 1 / -1;
}

.field-wrap :deep(.ant-form-item-label > label) {
  color: var(--c-text-secondary);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.field-wrap :deep(.ant-form-item-extra) {
  margin-top: 5px;
}

.field-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  line-height: 1.45;
}

.field-purpose {
  min-width: 0;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.field-state {
  flex: 0 0 auto;
  padding: 1px 6px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  color: var(--c-text-tertiary);
  font-size: 10px;
  white-space: nowrap;
}

.field-state.required {
  border-color: rgba(217, 119, 6, 0.3);
  color: var(--c-warning);
  background: var(--c-warning-soft);
}

.switch-field {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 32px;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.config-footer {
  margin-top: 14px;
  padding-top: 12px;
  padding-bottom: 12px;
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.config-footer span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

@media (max-width: 800px) {
  .config-hero,
  .config-toolbar,
  .readiness-strip,
  .dependency-check-card,
  .config-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .config-hero {
    padding: 22px;
  }

  .hero-status {
    align-items: flex-start;
  }

  .config-toolbar :deep(.ant-space) {
    width: 100%;
  }

  .toolbar-groups,
  .profile-picker {
    width: 100%;
  }

  .profile-picker :deep(.ant-select) {
    width: 100%;
  }

  .readiness-meter {
    width: 100%;
    flex: none;
  }

  .readiness-percent {
    text-align: left;
  }

  .dependency-check-list {
    justify-content: flex-start;
  }

  .field-grid {
    grid-template-columns: minmax(0, 1fr);
    padding: 18px 16px 4px;
  }

  .field-wide {
    grid-column: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .readiness-meter span {
    transition: none;
  }
}
</style>
