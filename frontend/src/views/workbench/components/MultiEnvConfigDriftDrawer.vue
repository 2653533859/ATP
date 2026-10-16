<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="跨环境配置漂移自动探测与敏感密钥泄漏告警控制台"
    destroy-on-close
    class="drift-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制介绍 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <SafetyCertificateOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">多环境微服务配置与环境变量深度差分比对引擎 (T2.1)</div>
          <div class="banner-desc">
            自动比对基准环境（Production/Staging）与目标环境（Testing/Dev）的配置快照，精准识别配置缺失、多余调试项、取值不一致与生产核心鉴权密钥外泄等高危风险，防止配置漂移引发线上故障。
          </div>
        </div>
      </div>

      <!-- 环境选择与服务场景配置 -->
      <div class="config-section">
        <div class="section-title">对比环境与微服务场景选择</div>
        <div class="config-row">
          <div class="env-selectors">
            <span class="label">基准环境:</span>
            <a-select v-model:value="baseEnv" class="w-32" size="small">
              <a-select-option value="production">production (生产)</a-select-option>
              <a-select-option value="staging">staging (预发)</a-select-option>
            </a-select>
            <span class="arrow-sep">➔</span>
            <span class="label">目标环境:</span>
            <a-select v-model:value="targetEnv" class="w-32" size="small">
              <a-select-option value="testing">testing (测试)</a-select-option>
              <a-select-option value="development">development (开发)</a-select-option>
            </a-select>
          </div>

          <div class="preset-selectors">
            <span class="label">微服务场景:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="order_service">订单微服务 (超时与中间件)</a-radio-button>
              <a-radio-button value="payment_service">支付微服务 (敏感密钥)</a-radio-button>
              <a-radio-button value="auth_service">认证微服务 (Token凭证)</a-radio-button>
            </a-radio-group>
            <a-button type="primary" size="small" :loading="comparing" @click="handleCompare">
              <ThunderboltOutlined /> 执行配置深度差分
            </a-button>
          </div>
        </div>
      </div>

      <!-- 高危严重敏感泄漏报警大横幅 -->
      <a-alert
        v-if="latestReport?.highest_severity === 'CRITICAL'"
        type="error"
        show-icon
        message="警告：检测到 CRITICAL 级别的高危敏感密钥泄露或核心鉴权项缺失！"
        description="目标测试环境与生产基准之间存在私钥、Token 或支付密钥未脱敏或关键凭据缺失，请立即核对并隔离安全凭证！"
        class="mb-3"
      />

      <!-- 4 大 KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">检查配置项总数</div>
            <div class="stat-value text-primary">{{ latestReport?.total_keys_checked ?? 0 }} <span class="unit">项</span></div>
            <div class="stat-trend">两环境全量键集合</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">配置一致性达标率</div>
            <div class="stat-value" :class="getScoreColorClass(latestReport?.consistency_score_pct ?? 100)">
              {{ latestReport?.consistency_score_pct ?? 100 }}%
            </div>
            <div class="stat-trend">两环境完全对齐比例</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">检测到漂移配置数</div>
            <div class="stat-value text-warning">{{ latestReport?.drift_count ?? 0 }} <span class="unit">项</span></div>
            <div class="stat-trend">缺失/多余/取值不一致</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">最高风险等级</div>
            <div class="stat-value" :class="getSeverityColorClass(latestReport?.highest_severity ?? 'IDENTICAL')">
              {{ latestReport?.highest_severity ?? 'IDENTICAL' }}
            </div>
            <div class="stat-trend">基线防护评定级别</div>
          </div>
        </a-col>
      </a-row>

      <!-- 配置差分明细表格 -->
      <div class="table-section">
        <div class="table-header">
          <div class="section-title">微服务环境变量与配置项漂移差分清单</div>
          <span class="text-xs text-muted">微服务: {{ latestReport?.service_name ?? 'service' }}</span>
        </div>

        <a-table
          :data-source="latestReport?.drifts ?? []"
          :columns="columns"
          :row-key="(r: any) => r.key"
          size="small"
          :pagination="{ pageSize: 6 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'key'">
              <code class="config-key-tag">{{ record.key }}</code>
            </template>

            <template v-else-if="column.key === 'drift_type'">
              <a-tag :color="getDriftTypeColor(record.drift_type)">
                {{ record.drift_type }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'severity'">
              <a-tag :color="getSeverityTagColor(record.severity)">
                {{ record.severity }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'diff_val'">
              <div class="diff-val-box">
                <div class="val-line"><span class="val-tag base">基准:</span> <code>{{ record.base_value ?? '<缺失>' }}</code></div>
                <div class="val-line"><span class="val-tag target">目标:</span> <code>{{ record.target_value ?? '<缺失>' }}</code></div>
              </div>
            </template>

            <template v-else-if="column.key === 'advice'">
              <div class="advice-box">
                <div class="risk-exp">{{ record.risk_explanation }}</div>
                <div class="sug-exp">{{ record.remediation_suggestion }}</div>
              </div>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  multiEnvConfigDriftApi,
  type ConfigDriftReport,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const comparing = ref(false)
const baseEnv = ref('production')
const targetEnv = ref('testing')
const selectedPreset = ref<'order_service' | 'payment_service' | 'auth_service'>('order_service')
const latestReport = ref<ConfigDriftReport | null>(null)

const PRESET_CONFIGS = {
  order_service: {
    service_name: 'order-service',
    base: {
      DATABASE_URL: 'postgresql://prod-db.internal:5432/orders',
      TIMEOUT_MS: 3000,
      MAX_CONNECTIONS: 100,
      ENABLE_TRACE: true,
      LOG_LEVEL: 'WARN',
    },
    target: {
      DATABASE_URL: 'postgresql://test-db.internal:5432/orders',
      TIMEOUT_MS: 30000, // 差异悬殊
      MAX_CONNECTIONS: 20,
      ENABLE_TRACE: true,
      DEBUG_VERBOSE: true, // 目标冗余项
    },
  },
  payment_service: {
    service_name: 'payment-service',
    base: {
      PAYMENT_GATEWAY_URL: 'https://api.alipay.com/gateway',
      PAYMENT_PRIVATE_KEY: 'RSA_PROD_SEC_KEY_888999',
      ENABLE_MOCK_PAY: false,
      WEBHOOK_SECRET: 'PROD_WH_SECRET_ABC',
    },
    target: {
      PAYMENT_GATEWAY_URL: 'https://sandbox.alipay.com/gateway',
      PAYMENT_PRIVATE_KEY: 'RSA_PROD_SEC_KEY_888999', // 生产私钥意外外泄至测试环境
      ENABLE_MOCK_PAY: true,
    },
  },
  auth_service: {
    service_name: 'auth-service',
    base: {
      JWT_SECRET_KEY: 'PROD_JWT_SIGN_SECRET_999',
      TOKEN_EXPIRE_SECONDS: 7200,
      REDIS_HOST: 'prod-redis.internal',
    },
    target: {
      TOKEN_EXPIRE_SECONDS: 86400,
      REDIS_HOST: 'test-redis.internal',
      LOCAL_MOCK_UID: 'test_dev_user',
    },
  },
}

const columns = [
  { title: '配置项 (Key)', key: 'key', width: 200 },
  { title: '差异模式', key: 'drift_type', width: 140 },
  { title: '风险等级', key: 'severity', width: 100 },
  { title: '基准值 vs 目标值', key: 'diff_val', width: 260 },
  { title: '风险解释与修复指引', key: 'advice' },
]

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  handleCompare()
}

function getDriftTypeColor(type: string) {
  switch (type) {
    case 'MISSING_IN_TARGET': return 'orange'
    case 'EXTRA_IN_TARGET': return 'blue'
    case 'VALUE_MISMATCH': return 'purple'
    case 'SECURITY_SENSITIVE_LEAK': return 'red'
    default: return 'default'
  }
}

function getSeverityTagColor(sev: string) {
  switch (sev) {
    case 'CRITICAL': return 'red'
    case 'HIGH': return 'orange'
    case 'MEDIUM': return 'gold'
    case 'LOW': return 'default'
    case 'IDENTICAL': return 'green'
    default: return 'default'
  }
}

function getSeverityColorClass(sev: string) {
  switch (sev) {
    case 'CRITICAL': return 'text-danger'
    case 'HIGH': return 'text-warning'
    case 'MEDIUM': return 'text-gold'
    default: return 'text-success'
  }
}

function getScoreColorClass(score: number) {
  if (score >= 90) return 'text-success'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

async function handleCompare() {
  comparing.value = true
  try {
    const p = PRESET_CONFIGS[selectedPreset.value]
    const res = await multiEnvConfigDriftApi.compare({
      service_name: p.service_name,
      base_env: baseEnv.value,
      target_env: targetEnv.value,
      base_configs: p.base,
      target_configs: p.target,
    })
    latestReport.value = res.report
    message.success(res.message || '配置差分比对完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '配置比对失败')
  } finally {
    comparing.value = false
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleCompare()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleCompare()
  }
})
</script>

<style scoped>
.drift-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #dc2626;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #991b1b;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.5;
}

.config-section,
.table-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 12px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.env-selectors,
.preset-selectors {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.arrow-sep {
  color: #94a3b8;
  font-weight: bold;
}

.w-32 {
  width: 130px;
}

.kpi-row {
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
}

.stat-value {
  font-size: 22px;
  font-weight: 800;
  margin: 4px 0;
}

.stat-value .unit {
  font-size: 12px;
  font-weight: normal;
  color: #94a3b8;
}

.stat-trend {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-danger { color: #dc2626; }
.text-gold { color: #ca8a04; }
.text-muted { color: #94a3b8; }

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.config-key-tag {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #0f172a;
}

.diff-val-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.val-line {
  display: flex;
  align-items: center;
  gap: 4px;
}

.val-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 2px;
}

.val-tag.base { background: #e0f2fe; color: #0369a1; }
.val-tag.target { background: #fef3c7; color: #b45309; }

.advice-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.risk-exp {
  font-size: 11px;
  font-weight: 600;
  color: #b91c1c;
}

.sug-exp {
  font-size: 11px;
  color: #475569;
}

.mb-3 {
  margin-bottom: 12px;
}

.text-xs {
  font-size: 11px;
}
</style>
