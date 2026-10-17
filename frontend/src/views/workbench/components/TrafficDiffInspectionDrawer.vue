<template>
  <a-drawer
    :open="open"
    title="生产流量双端响应结构差异透视对比中枢"
    width="88%"
    placement="right"
    :destroy-on-close="true"
    class="traffic-diff-inspection-drawer"
    @close="handleClose"
  >
    <div class="traffic-drawer-container">
      <!-- 顶部综合指标横幅 -->
      <div class="hero-kpi-bar">
        <div class="kpi-left">
          <div class="score-box">
            <span class="score-val" :class="getScoreClass(consistencyScore)">
              {{ consistencyScore.toFixed(1) }}
            </span>
            <span class="score-label">回放一致性评分</span>
          </div>

          <div class="meta-details">
            <div class="title-row">
              <a-tag :color="getMethodColor(recordData?.method)">
                {{ recordData?.method || 'POST' }}
              </a-tag>
              <span class="path-title font-mono font-bold">{{ recordData?.path || '/api/v1/orders' }}</span>
              <a-tag :color="getVerdictColor(verdict)">
                {{ verdict }}
              </a-tag>
            </div>

            <div class="status-pills-row font-mono">
              <span class="pill-item">
                基线状态: <strong class="text-success">{{ recordData?.status_code || 200 }}</strong>
              </span>
              <span class="pill-item">
                回放状态: <strong :class="isStatusCodeMatch ? 'text-success' : 'text-danger'">{{ replayedStatusCode }}</strong>
              </span>
              <span class="pill-item">
                有效差异: <strong :class="effectiveDiffCount > 0 ? 'text-warning' : 'text-success'">{{ effectiveDiffCount }} 项</strong>
              </span>
              <span class="pill-item">
                已平滑噪声: <strong class="text-secondary">{{ suppressedNoiseCount }} 项</strong>
              </span>
            </div>
          </div>
        </div>

        <div class="kpi-right">
          <a-space>
            <a-button
              type="primary"
              :loading="updatingBaseline"
              @click="handleUpdateBaseline"
            >
              <template #icon><CheckOutlined /></template>
              采纳回放为新基线
            </a-button>

            <a-button @click="handleClose">关闭</a-button>
          </a-space>
        </div>
      </div>

      <!-- 核心左右响应体对比 -->
      <div class="response-body-diff-grid">
        <!-- 左栏: 生产基线响应 -->
        <div class="diff-card baseline-card">
          <div class="card-header">
            <span class="card-title text-primary">
              <CloudOutlined /> 生产录制基线响应 (Production Baseline)
            </span>
            <span class="font-mono text-secondary">HTTP {{ recordData?.status_code || 200 }}</span>
          </div>

          <pre class="json-code-pre font-mono">{{ formattedBaselineBody }}</pre>
        </div>

        <!-- 中间流向标识 -->
        <div class="diff-divider-col">
          <div class="divider-arrow-circle">
            <SwapOutlined />
          </div>
          <span class="divider-text">深度比对</span>
        </div>

        <!-- 右栏: 线下回放响应 -->
        <div class="diff-card replayed-card">
          <div class="card-header">
            <span class="card-title text-success">
              <ThunderboltOutlined /> 线下实际回放响应 (Replayed Actual)
            </span>
            <span class="font-mono" :class="isStatusCodeMatch ? 'text-success' : 'text-danger'">
              HTTP {{ replayedStatusCode }}
            </span>
          </div>

          <pre class="json-code-pre font-mono" :class="{ 'has-diffs': effectiveDiffCount > 0 }">{{ formattedReplayedBody }}</pre>
        </div>
      </div>

      <!-- 差异项明细表格 -->
      <div class="diff-table-section">
        <div class="section-title-row">
          <h4 class="section-title">
            <ProfileOutlined /> 细颗粒度响应结构差异与动态噪声过滤透视
          </h4>
          <span class="section-subtext">展示两端字段级比对明细，包含已识别并剔除的时间戳与 TraceID 动态伪差异</span>
        </div>

        <a-table
          :data-source="diffList"
          :columns="diffColumns"
          :pagination="false"
          size="middle"
          row-key="diff_id"
          class="diffs-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(record.category)">
                {{ record.category }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'severity'">
              <a-tag :color="getSeverityColor(record.severity)">
                {{ record.severity }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'json_path'">
              <span class="font-mono font-bold text-primary">{{ record.json_path }}</span>
            </template>

            <template v-else-if="column.key === 'values_compare'">
              <div class="values-flow font-mono">
                <span class="val-pill old-val">{{ reprVal(record.baseline_value) }}</span>
                <ArrowRightOutlined class="arrow-icon" />
                <span class="val-pill new-val">{{ reprVal(record.replayed_value) }}</span>
              </div>
            </template>

            <template v-else-if="column.key === 'noise_status'">
              <a-tag :color="record.is_noise ? 'default' : 'red'">
                {{ record.is_noise ? '已降噪忽略' : '真实业务差异' }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'actions'">
              <a-button
                v-if="!record.is_noise"
                size="small"
                type="link"
                @click="markAsNoiseRule(record)"
              >
                设为噪声规则
              </a-button>
              <span v-else class="text-secondary font-mono text-xs">已过滤</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  CloudOutlined,
  ThunderboltOutlined,
  SwapOutlined,
  ProfileOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  open: boolean
  recordData?: any
  diffReport?: any
  evaluationResult?: any
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'updatedBaseline', recordId: string): void
  (e: 'addedNoiseRule', rule: any): void
}>()

const updatingBaseline = ref(false)

const consistencyScore = computed(() => {
  return props.evaluationResult?.consistency_score ?? 93.0
})

const verdict = computed(() => {
  return props.evaluationResult?.verdict ?? 'WARN_PERMISSIVE'
})

const replayedStatusCode = computed(() => {
  return props.diffReport?.replayed_status_code ?? props.recordData?.status_code ?? 200
})

const isStatusCodeMatch = computed(() => {
  const baseCode = props.recordData?.status_code ?? 200
  return baseCode === replayedStatusCode.value
})

const effectiveDiffCount = computed(() => {
  if (props.diffReport?.effective_diff_count !== undefined) {
    return props.diffReport.effective_diff_count
  }
  return 1
})

const suppressedNoiseCount = computed(() => {
  if (props.diffReport?.suppressed_noise_count !== undefined) {
    return props.diffReport.suppressed_noise_count
  }
  return 2
})

const formattedBaselineBody = computed(() => {
  const b = props.recordData?.response_body
  if (!b) {
    return JSON.stringify({ code: 200, order_id: 'OD_1001', amount: 99.0, created_at: '2026-10-17T10:00:00Z' }, null, 2)
  }
  return typeof b === 'string' ? b : JSON.stringify(b, null, 2)
})

const formattedReplayedBody = computed(() => {
  const r = props.recordData?.replayed_response_body || props.recordData?.response_body
  if (!r) {
    return JSON.stringify({ code: 200, order_id: 'OD_1001', amount: 105.0, created_at: '2026-10-17T10:00:05Z' }, null, 2)
  }
  return typeof r === 'string' ? r : JSON.stringify(r, null, 2)
})

const diffList = computed(() => {
  const rep = props.diffReport
  if (rep?.effective_diffs || rep?.noise_diffs) {
    return [...(rep.effective_diffs || []), ...(rep.noise_diffs || [])]
  }
  if (rep?.diffs && rep.diffs.length > 0) {
    return rep.diffs
  }
  return [
    {
      diff_id: 'd_amount',
      category: 'VALUE_MISMATCH',
      severity: 'MINOR',
      json_path: '$.amount',
      baseline_value: 99.0,
      replayed_value: 105.0,
      is_noise: false,
    },
    {
      diff_id: 'd_time',
      category: 'VALUE_MISMATCH',
      severity: 'MINOR',
      json_path: '$.created_at',
      baseline_value: '2026-10-17T10:00:00Z',
      replayed_value: '2026-10-17T10:00:05Z',
      is_noise: true,
    },
  ]
})

const diffColumns = [
  { title: '差异类别', key: 'category', width: 180 },
  { title: '严重程度', key: 'severity', width: 110 },
  { title: 'JSONPath 目标路径', key: 'json_path', width: 220 },
  { title: '两端数值比对 (基线 ➔ 回放)', key: 'values_compare', width: 280 },
  { title: '判定状态', key: 'noise_status', width: 130 },
  { title: '操作', key: 'actions', width: 120 },
]

function getScoreClass(s: number) {
  if (s >= 90) return 'text-success'
  if (s >= 70) return 'text-warning'
  return 'text-danger'
}

function getVerdictColor(v: string) {
  switch (v) {
    case 'PASSED':
      return 'green'
    case 'WARN_PERMISSIVE':
      return 'orange'
    case 'BLOCKED_BREAKING':
      return 'red'
    default:
      return 'blue'
  }
}

function getMethodColor(m?: string) {
  switch (m?.toUpperCase()) {
    case 'POST':
      return 'blue'
    case 'GET':
      return 'green'
    case 'DELETE':
      return 'red'
    default:
      return 'cyan'
  }
}

function getCategoryColor(cat: string) {
  switch (cat) {
    case 'STATUS_CODE_MISMATCH':
      return 'red'
    case 'MISSING_KEY':
      return 'magenta'
    case 'TYPE_MISMATCH':
      return 'purple'
    case 'VALUE_MISMATCH':
      return 'orange'
    case 'UNEXPECTED_KEY':
      return 'blue'
    default:
      return 'default'
  }
}

function getSeverityColor(sev: string) {
  switch (sev) {
    case 'BLOCKER':
      return 'red'
    case 'MAJOR':
      return 'volcano'
    case 'MINOR':
      return 'gold'
    default:
      return 'default'
  }
}

function reprVal(v: any): string {
  if (v === null) return 'null'
  if (v === undefined) return '--'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function markAsNoiseRule(record: any) {
  emit('addedNoiseRule', {
    name: `自动忽略 ${record.json_path}`,
    path_pattern: record.json_path,
    noise_type: 'CUSTOM_RULE',
  })
  message.success(`已将 [${record.json_path}] 提交为噪声规则`)
}

async function handleUpdateBaseline() {
  updatingBaseline.value = true
  try {
    const rid = props.recordData?.record_id || 'rec_sample'
    message.success('已成功将本次回放响应更新为最新基线！')
    emit('updatedBaseline', rid)
    emit('update:open', false)
  } finally {
    updatingBaseline.value = false
  }
}

function handleClose() {
  emit('update:open', false)
}
</script>

<style scoped>
.traffic-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-kpi-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.kpi-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.score-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.score-val {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}

.score-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  margin-top: 4px;
}

.meta-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.path-title {
  font-size: 15px;
  color: var(--c-text-primary, #1e293b);
}

.status-pills-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.response-body-diff-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: stretch;
  gap: 14px;
}

.diff-card {
  padding: 14px;
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
  background: var(--c-bg-card, #ffffff);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.baseline-card {
  border-left: 4px solid #3b82f6;
}

.replayed-card {
  border-left: 4px solid #10b981;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.json-code-pre {
  margin: 0;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  max-height: 360px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.diff-divider-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.divider-arrow-circle {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.divider-text {
  font-size: 11px;
  color: #64748b;
}

.diff-table-section {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.section-title-row {
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text-primary, #1e293b);
}

.section-subtext {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.values-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.val-pill {
  padding: 2px 6px;
  border-radius: 4px;
}

.old-val {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}

.new-val {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}

.arrow-icon {
  color: #94a3b8;
}

.text-success {
  color: #10b981;
}

.text-warning {
  color: #f59e0b;
}

.text-danger {
  color: #ef4444;
}

.text-primary {
  color: #2563eb;
}

.text-secondary {
  color: var(--c-text-secondary, #64748b);
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: bold;
}
</style>
