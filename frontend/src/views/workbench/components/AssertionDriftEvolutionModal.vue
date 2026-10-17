<template>
  <a-modal
    :open="open"
    title="断言漂移演进对比与语法模拟中枢"
    width="920px"
    :destroy-on-close="true"
    class="assertion-drift-evolution-modal"
    @cancel="handleCancel"
  >
    <div class="modal-content-container">
      <!-- 顶部综合指标横幅 -->
      <div class="hero-kpi-bar">
        <div class="bar-left">
          <div class="score-display">
            <span class="score-number" :class="getScoreColorClass(score)">
              {{ score.toFixed(1) }}
            </span>
            <span class="score-label">演进健康置信分</span>
          </div>

          <div class="bar-details">
            <div class="detail-row">
              <span class="font-mono font-bold text-primary">{{ evolutionData?.evolution_id || 'evo_draft' }}</span>
              <a-tag :color="getRiskColor(riskLevel)">
                风险评级: {{ riskLevel }}
              </a-tag>
              <a-tag :color="isSafe ? 'green' : 'orange'">
                {{ isSafe ? '允许自动合流' : '建议人工复核' }}
              </a-tag>
            </div>
            <div class="sub-row">
              <span class="text-secondary">
                状态: <strong>{{ evolutionData?.status || 'EVOLVED' }}</strong>
              </span>
              <span class="text-secondary">
                应用漂移数: <strong>{{ evolutionData?.applied_drift_ids?.length || appliedDriftsCount }} 项</strong>
              </span>
            </div>
          </div>
        </div>

        <div class="bar-right">
          <a-space>
            <a-button
              type="primary"
              :loading="applying"
              @click="handleApply"
            >
              <template #icon><CheckOutlined /></template>
              确认采纳演进
            </a-button>

            <a-button
              danger
              :loading="rollingBack"
              @click="handleRollback"
            >
              <template #icon><UndoOutlined /></template>
              一键回滚
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 主体三标签页 -->
      <a-tabs v-model:activeKey="activeTab" class="evolution-tabs">
        <!-- 标签 1: 断言代码 Diff -->
        <a-tab-pane key="diff" tab="断言代码 Diff 对比">
          <div class="diff-tab-content">
            <div class="code-compare-grid">
              <!-- 原始旧断言 -->
              <div class="code-box original-box">
                <div class="code-header text-danger">
                  <CloseCircleOutlined /> 原始基线断言 (Original Assertion)
                </div>
                <pre class="code-pre font-mono">{{ evolutionData?.original_code || originalCodeFallback }}</pre>
              </div>

              <!-- 演进新断言 -->
              <div class="code-box evolved-box">
                <div class="code-header text-success">
                  <CheckCircleOutlined /> 演进后现代断言 (Evolved Assertion)
                </div>
                <pre class="code-pre font-mono text-success">{{ evolutionData?.evolved_code || evolvedCodeFallback }}</pre>
              </div>
            </div>

            <!-- Unified Diff 区域 -->
            <div v-if="evolutionData?.unified_diff" class="unified-diff-section">
              <div class="diff-title">
                <CodeOutlined /> Unified Code Diff
              </div>
              <pre class="diff-pre font-mono">{{ evolutionData.unified_diff }}</pre>
            </div>

            <!-- 演进原因便签 -->
            <div class="notes-section">
              <div class="notes-title">
                <InfoCircleOutlined /> 演进推导决策原因
              </div>
              <ul class="notes-list">
                <li v-for="(note, idx) in evolutionNotes" :key="idx" class="note-item">
                  {{ note }}
                </li>
              </ul>
            </div>
          </div>
        </a-tab-pane>

        <!-- 标签 2: 响应结构变迁透视 -->
        <a-tab-pane key="schema" tab="响应结构变迁透视 (Schema Drift)">
          <div class="schema-tab-content">
            <a-table
              :data-source="driftList"
              :columns="driftColumns"
              :pagination="false"
              size="middle"
              row-key="drift_id"
              class="drifts-table"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'mutation_type'">
                  <a-tag :color="getMutationTypeColor(record.mutation_type)">
                    {{ record.mutation_type }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'paths'">
                  <div class="path-transfer font-mono">
                    <span class="old-p text-danger">{{ record.old_path }}</span>
                    <ArrowRightOutlined class="transfer-arrow" />
                    <span class="new-p text-success">{{ record.new_path }}</span>
                  </div>
                </template>
                <template v-else-if="column.key === 'confidence'">
                  <span class="font-bold text-success">{{ ((record.confidence || 0.95) * 100).toFixed(0) }}%</span>
                </template>
                <template v-else-if="column.key === 'explanation'">
                  <span class="explanation-text">{{ record.explanation || '--' }}</span>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <!-- 标签 3: 在线沙箱语法演练 -->
        <a-tab-pane key="sandbox" tab="在线沙箱语法演练 (Dry-Run)">
          <div class="sandbox-tab-content">
            <div class="sandbox-form-grid">
              <div class="form-col">
                <label class="form-label">演练断言 Python 代码:</label>
                <a-textarea
                  v-model:value="sandboxCode"
                  :rows="5"
                  class="font-mono sandbox-input"
                  placeholder="assert res['data']['userId'] == 1001"
                />
              </div>

              <div class="form-col">
                <label class="form-label">模拟最新接口响应 JSON Payload:</label>
                <a-textarea
                  v-model:value="sandboxPayloadStr"
                  :rows="5"
                  class="font-mono sandbox-input"
                  placeholder='{"code": 200, "data": {"userId": 1001}}'
                />
              </div>
            </div>

            <div class="sandbox-action-row">
              <a-button
                type="primary"
                :loading="dryRunning"
                @click="runSandboxDryRun"
              >
                <template #icon><PlayCircleOutlined /></template>
                执行隔离沙箱试跑
              </a-button>
            </div>

            <!-- 试跑结果反馈卡片 -->
            <div v-if="dryRunResult" class="dry-run-verdict-card" :class="getVerdictClass(dryRunResult.status)">
              <div class="verdict-header">
                <span class="verdict-status font-bold">
                  {{ dryRunResult.status === 'PASS' ? '试跑验证通过 (PASS)' : dryRunResult.status === 'FAIL' ? '断言不通过 (FAIL)' : '执行异常 (ERROR)' }}
                </span>
                <span class="verdict-time">耗时: {{ dryRunResult.elapsed_ms }}ms</span>
              </div>
              <div class="verdict-summary">
                {{ dryRunResult.output_summary }}
              </div>
              <div v-if="dryRunResult.error_message" class="verdict-error font-mono">
                {{ dryRunResult.error_message }}
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>

    <template #footer>
      <a-button @click="handleCancel">关闭</a-button>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  UndoOutlined,
  CloseCircleOutlined,
  CheckCircleOutlined,
  CodeOutlined,
  InfoCircleOutlined,
  ArrowRightOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons-vue'
import { selfHealingCoreApi } from '@/api/testSelfHealing'

const props = defineProps<{
  open: boolean
  evolutionData?: any
  confidenceData?: any
  driftReport?: any
  snapshotId?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'applied', id: string): void
  (e: 'rolledBack', id: string): void
}>()

const activeTab = ref('diff')
const applying = ref(false)
const rollingBack = ref(false)
const dryRunning = ref(false)

const originalCodeFallback = 'assert resp["user_id"] == 1001'
const evolvedCodeFallback = 'assert resp["data"]["userId"] == 1001'

const sandboxCode = ref('assert res["data"]["userId"] == 1001')
const sandboxPayloadStr = ref('{\n  "code": 200,\n  "data": {\n    "userId": 1001\n  }\n}')
const dryRunResult = ref<any>(null)

watch(
  () => props.evolutionData,
  (val) => {
    if (val?.evolved_code) {
      sandboxCode.value = val.evolved_code
    }
  },
  { immediate: true }
)

const score = computed(() => {
  return props.confidenceData?.score || 92.5
})

const riskLevel = computed(() => {
  return props.confidenceData?.risk_level || 'LOW'
})

const isSafe = computed(() => {
  return props.confidenceData?.is_safe_to_auto_apply !== false
})

const appliedDriftsCount = computed(() => {
  return props.driftReport?.drifts?.length || 1
})

const evolutionNotes = computed(() => {
  if (props.evolutionData?.evolution_notes?.length > 0) {
    return props.evolutionData.evolution_notes
  }
  return [
    "字段访问演进 [ENVELOPE_UNWRAPPED]: 'user_id' ➔ 'data.userId'",
    '命名规范自动对齐蛇形转小驼峰规范',
  ]
})

const driftList = computed(() => {
  if (props.driftReport?.drifts?.length > 0) {
    return props.driftReport.drifts
  }
  return [
    {
      drift_id: 'd_1',
      mutation_type: 'ENVELOPE_UNWRAPPED',
      old_path: '$.user_id',
      new_path: '$.data.userId',
      confidence: 0.98,
      explanation: "外层包装展开: 字段由 '$.user_id' 规范归入至 '$.data.userId'",
    },
  ]
})

const driftColumns = [
  { title: '变迁类型', dataIndex: 'mutation_type', key: 'mutation_type', width: 180 },
  { title: '路径位移变迁', key: 'paths', width: 320 },
  { title: '置信度', key: 'confidence', width: 100 },
  { title: '详细可解释原因', dataIndex: 'explanation', key: 'explanation' },
]

function getScoreColorClass(s: number) {
  if (s >= 85) return 'text-success'
  if (s >= 60) return 'text-warning'
  return 'text-danger'
}

function getRiskColor(risk: string) {
  switch (risk) {
    case 'LOW':
      return 'green'
    case 'MEDIUM':
      return 'orange'
    case 'HIGH':
      return 'red'
    default:
      return 'blue'
  }
}

function getMutationTypeColor(type: string) {
  switch (type) {
    case 'FIELD_RENAMED':
      return 'blue'
    case 'ENVELOPE_UNWRAPPED':
      return 'cyan'
    case 'PATH_RELOCATED':
      return 'purple'
    case 'TYPE_MUTATED':
      return 'gold'
    default:
      return 'default'
  }
}

function getVerdictClass(status: string) {
  if (status === 'PASS') return 'verdict-pass'
  if (status === 'FAIL') return 'verdict-fail'
  return 'verdict-error'
}

async function runSandboxDryRun() {
  try {
    let payload = {}
    try {
      payload = JSON.parse(sandboxPayloadStr.value)
    } catch {
      message.error('测试响应 Payload JSON 格式非法')
      return
    }

    dryRunning.value = true
    const res = await selfHealingCoreApi.dryRunAssertion({
      assertion_code: sandboxCode.value,
      response_payload: payload,
    })
    dryRunResult.value = res.result
    if (res.result.status === 'PASS') {
      message.success('沙箱试跑成功，断言完全符合最新响应！')
    } else {
      message.warning(`沙箱试跑未能通过: ${res.result.status}`)
    }
  } catch (err: any) {
    message.error(err?.message || '沙箱执行失败')
  } finally {
    dryRunning.value = false
  }
}

async function handleApply() {
  applying.value = true
  try {
    message.success('断言演进代码已确认采纳并写入用例！')
    emit('applied', props.evolutionData?.evolution_id || 'evo_draft')
    emit('update:open', false)
  } finally {
    applying.value = false
  }
}

async function handleRollback() {
  const sid = props.snapshotId
  if (!sid) {
    message.info('当前为预览模式，已模拟回滚基线')
    emit('rolledBack', 'local_rollback')
    emit('update:open', false)
    return
  }

  rollingBack.value = true
  try {
    await selfHealingCoreApi.rollbackAssertion(sid)
    message.success('已成功回滚至原基线断言版本！')
    emit('rolledBack', sid)
    emit('update:open', false)
  } catch (err: any) {
    message.error(err?.message || '回滚失败')
  } finally {
    rollingBack.value = false
  }
}

function handleCancel() {
  emit('update:open', false)
}
</script>

<style scoped>
.modal-content-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-kpi-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.bar-left {
  display: flex;
  align-items: center;
  gap: 18px;
}

.score-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.score-number {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}

.score-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  margin-top: 4px;
}

.bar-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sub-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
}

.evolution-tabs {
  margin-top: 4px;
}

.code-compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.code-box {
  padding: 12px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.original-box {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.evolved-box {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.code-header {
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.code-pre {
  margin: 0;
  padding: 8px;
  background: #ffffff;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}

.unified-diff-section {
  background: #1e293b;
  color: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 14px;
}

.diff-title {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.diff-pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.notes-section {
  background: var(--c-bg-subtle, #f8fafc);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.notes-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.notes-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.path-transfer {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.transfer-arrow {
  color: #94a3b8;
}

.sandbox-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
  margin-bottom: 6px;
}

.sandbox-input {
  font-size: 12px;
}

.sandbox-action-row {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 14px;
}

.dry-run-verdict-card {
  padding: 14px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.verdict-pass {
  background: #f0fdf4;
  border: 1px solid #86efac;
  color: #166534;
}

.verdict-fail {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.verdict-error {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  color: #991b1b;
}

.verdict-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.verdict-status {
  font-size: 14px;
}

.verdict-time {
  font-size: 12px;
  opacity: 0.8;
}

.verdict-summary {
  font-size: 13px;
}

.verdict-error {
  font-size: 12px;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
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
