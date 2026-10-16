<template>
  <div class="healing-audit-trail-panel">
    <!-- 头部工具栏 -->
    <header class="panel-header">
      <div class="header-left">
        <div class="header-icon-box">
          <ClusterOutlined class="header-icon" />
        </div>
        <div>
          <div class="header-title-row">
            <h3 class="header-title">异常故障簇智能聚合与自愈执行流水审计</h3>
            <a-tag color="processing">AI Healing Trail</a-tag>
          </div>
          <p class="header-desc">
            提取异常堆栈特征进行智能归一化聚类，追踪全生命周期用例自愈动作历史流水，精确量化二次验证成功率与节省工程工时。
          </p>
        </div>
      </div>
      <div class="header-right">
        <a-space>
          <a-button size="small" :loading="loading" @click="loadData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" type="dashed" @click="showSimulateClusterModal = true">
            <BugOutlined /> 演练故障聚类
          </a-button>
          <a-button size="small" type="primary" ghost @click="showSimulateActionModal = true">
            <PlusOutlined /> 记录自愈流水
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 成效 KPI 概览卡片 -->
    <a-spin :spinning="loading">
      <div class="metrics-kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">累计自愈执行流水</div>
          <div class="kpi-value-row">
            <span class="kpi-number">{{ metrics.total_healing_actions_count }}</span>
            <span class="kpi-unit">次</span>
          </div>
          <div class="kpi-sub">自动定位修复与契约容差</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">二次验证成功率</div>
          <div class="kpi-value-row">
            <span class="kpi-number text-success">{{ (metrics.verification_success_rate_pct || 0).toFixed(1) }}%</span>
          </div>
          <div class="kpi-sub">
            <CheckCircleOutlined style="color: var(--c-success); margin-right: 4px" />
            自愈动作通过二次执行验证
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">平均自愈置信度</div>
          <div class="kpi-value-row">
            <span class="kpi-number text-primary">{{ ((metrics.average_confidence_score || 0) * 100).toFixed(1) }}%</span>
          </div>
          <div class="kpi-sub">多模态四维加权综合打分</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">聚合异常故障簇</div>
          <div class="kpi-value-row">
            <span class="kpi-number text-warning">{{ metrics.total_fault_clusters_count }}</span>
            <span class="kpi-unit">个簇</span>
          </div>
          <div class="kpi-sub">同构错误堆栈自动归一化</div>
        </div>

        <div class="kpi-card highlight-card">
          <div class="kpi-label">累计节省工程工时</div>
          <div class="kpi-value-row">
            <span class="kpi-number text-accent">{{ (metrics.estimated_engineering_hours_saved || 0).toFixed(1) }}</span>
            <span class="kpi-unit">小时</span>
          </div>
          <div class="kpi-sub">相当于减少人工排查 ~{{ Math.round((metrics.estimated_engineering_hours_saved || 0) * 60) }} 分钟</div>
        </div>
      </div>

      <!-- 主标签页：故障簇看板 vs 执行流水审计 -->
      <a-tabs v-model:activeKey="activeTab" class="audit-tabs">
        <!-- 标签页 1：异常故障簇智能聚合看板 -->
        <a-tab-pane key="clusters" tab="异常故障簇智能聚合看板 (Fault Clusters)">
          <div class="tab-toolbar">
            <span class="tab-tip">
              基于异常类型、错误文本与堆栈关键行计算特征签名（Signature），自动收敛重复告警并推导根因自愈策略。
            </span>
            <span class="cluster-count-badge">已聚合 {{ clusters.length }} 个故障簇</span>
          </div>

          <a-table
            :data-source="clusters"
            :columns="clusterColumns"
            row-key="cluster_id"
            size="small"
            :pagination="{ pageSize: 6, showTotal: (t: number) => `共 ${t} 个故障簇` }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'cluster_id'">
                <div class="cluster-id-box">
                  <span class="cluster-id-text">{{ record.cluster_id }}</span>
                  <a-tooltip :title="record.signature">
                    <span class="signature-tag">sig: {{ record.signature.slice(0, 10) }}...</span>
                  </a-tooltip>
                </div>
              </template>

              <template v-else-if="column.key === 'primary_exception'">
                <a-tag color="error" class="exception-tag">{{ record.primary_exception }}</a-tag>
              </template>

              <template v-else-if="column.key === 'root_cause_summary'">
                <div class="root-cause-cell">
                  <div class="summary-text">{{ record.root_cause_summary }}</div>
                  <div class="suggested-action">
                    <span class="action-label">推荐自愈:</span>
                    <a-tag color="cyan">{{ record.suggested_healing_action }}</a-tag>
                  </div>
                </div>
              </template>

              <template v-else-if="column.key === 'occurrences_count'">
                <a-tag color="orange" style="font-weight: 600">{{ record.occurrences_count }} 次</a-tag>
              </template>

              <template v-else-if="column.key === 'affected_cases'">
                <div class="affected-cases-box">
                  <span class="affected-label">用例 ({{ record.affected_case_ids?.length || 0 }}):</span>
                  <a-space :size="2" wrap>
                    <a-tag
                      v-for="cid in (record.affected_case_ids || []).slice(0, 4)"
                      :key="cid"
                      size="small"
                      color="blue"
                    >
                      #{{ cid }}
                    </a-tag>
                    <span v-if="(record.affected_case_ids?.length || 0) > 4" class="more-text">
                      +{{ record.affected_case_ids.length - 4 }}
                    </span>
                  </a-space>
                </div>
              </template>

              <template v-else-if="column.key === 'time_range'">
                <div class="time-range-cell">
                  <small>首次: {{ formatTime(record.first_seen) }}</small>
                  <small>末次: {{ formatTime(record.last_seen) }}</small>
                </div>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- 标签页 2：用例自愈执行动作流水 -->
        <a-tab-pane key="entries" tab="用例自愈动作历史流水 (Healing Action Audit Trail)">
          <div class="entries-filter-bar">
            <a-space>
              <a-input-number
                v-model:value="filterCaseId"
                placeholder="按用例 ID 过滤"
                size="small"
                style="width: 140px"
                :min="1"
                allow-clear
                @change="loadEntries"
              />
              <a-select
                v-model:value="filterActionType"
                placeholder="动作类型过滤"
                size="small"
                style="width: 160px"
                allow-clear
                :options="actionTypeOptions"
                @change="loadEntries"
              />
              <a-button size="small" @click="loadEntries">查询</a-button>
              <a-button size="small" @click="resetFilters">重置</a-button>
            </a-space>
            <span class="entry-total-text">共 {{ entries.length }} 条流水</span>
          </div>

          <a-table
            :data-source="entries"
            :columns="entryColumns"
            row-key="audit_id"
            size="small"
            :pagination="{ pageSize: 8, showTotal: (t: number) => `共 ${t} 条流水` }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'audit_id'">
                <span class="mono-text">{{ record.audit_id }}</span>
              </template>

              <template v-else-if="column.key === 'case_step'">
                <div>
                  <a-tag color="geekblue">#{{ record.case_id }}</a-tag>
                  <span class="step-text">{{ record.step_name }}</span>
                </div>
              </template>

              <template v-else-if="column.key === 'action_type'">
                <a-tag :color="getActionTypeColor(record.action_type)">
                  {{ getActionTypeLabel(record.action_type) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'value_diff'">
                <div class="diff-card">
                  <div class="diff-row">
                    <span class="diff-tag-old">前</span>
                    <span class="diff-val" :title="String(record.original_value)">{{ formatValue(record.original_value) }}</span>
                  </div>
                  <div class="diff-row">
                    <span class="diff-tag-new">后</span>
                    <span class="diff-val text-success" :title="String(record.healed_value)">{{ formatValue(record.healed_value) }}</span>
                  </div>
                </div>
              </template>

              <template v-else-if="column.key === 'confidence_score'">
                <div class="confidence-box">
                  <a-progress
                    :percent="Math.round(record.confidence_score * 100)"
                    size="small"
                    :stroke-color="record.confidence_score >= 0.8 ? '#10b981' : '#f59e0b'"
                    :status="record.confidence_score >= 0.8 ? 'success' : 'normal'"
                  />
                </div>
              </template>

              <template v-else-if="column.key === 'verification_status'">
                <a-tag :color="getVerificationStatusColor(record.verification_status)">
                  {{ getVerificationStatusLabel(record.verification_status) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'duration_ms'">
                <span class="mono-text">{{ record.duration_ms }} ms</span>
              </template>

              <template v-else-if="column.key === 'created_at'">
                <small class="time-text">{{ formatTime(record.created_at) }}</small>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-spin>

    <!-- 演练故障聚类 Modal -->
    <a-modal
      v-model:open="showSimulateClusterModal"
      title="演练异常错误特征归一化与故障簇智能聚类"
      @ok="handleSimulateCluster"
    >
      <a-form layout="vertical">
        <a-form-item label="关联用例 ID" required>
          <a-input-number v-model:value="clusterForm.case_id" :min="1" style="width: 100%" />
        </a-form-item>
        <a-form-item label="执行批次 Run ID" required>
          <a-input-number v-model:value="clusterForm.run_id" :min="1" style="width: 100%" />
        </a-form-item>
        <a-form-item label="异常类型 (Exception Type)" required>
          <a-select v-model:value="clusterForm.exception_type">
            <a-select-option value="NoSuchElementException">NoSuchElementException (定位器失效)</a-select-option>
            <a-select-option value="SchemaValidationError">SchemaValidationError (接口响应契约漂移)</a-select-option>
            <a-select-option value="ElementNotInteractableException">ElementNotInteractableException (元素不可交互)</a-select-option>
            <a-select-option value="AssertionError">AssertionError (断言不匹配)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="错误报错详细文本" required>
          <a-textarea v-model:value="clusterForm.error_message" :rows="3" />
        </a-form-item>
        <a-form-item label="错误堆栈信息 (可选)">
          <a-textarea v-model:value="clusterForm.stack_trace" :rows="3" placeholder="org.openqa.selenium.NoSuchElementException..." />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 模拟自愈流水 Modal -->
    <a-modal
      v-model:open="showSimulateActionModal"
      title="模拟记录用例自愈执行动作流水"
      @ok="handleSimulateAction"
    >
      <a-form layout="vertical">
        <a-form-item label="用例 ID" required>
          <a-input-number v-model:value="actionForm.case_id" :min="1" style="width: 100%" />
        </a-form-item>
        <a-form-item label="步骤名称" required>
          <a-input v-model:value="actionForm.step_name" placeholder="如: 点击提交结算按钮" />
        </a-form-item>
        <a-form-item label="自愈动作类型" required>
          <a-select v-model:value="actionForm.action_type">
            <a-select-option value="locator_replaced">元素定位器自愈替换 (locator_replaced)</a-select-option>
            <a-select-option value="schema_autofixed">Schema 契约自愈修正 (schema_autofixed)</a-select-option>
            <a-select-option value="assertion_tolerated">柔性契约断言容差 (assertion_tolerated)</a-select-option>
            <a-select-option value="retry_with_backoff">自适应指数退避重试 (retry_with_backoff)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="自愈前失效值" required>
          <a-input v-model:value="actionForm.original_value" />
        </a-form-item>
        <a-form-item label="自愈后替换值" required>
          <a-input v-model:value="actionForm.healed_value" />
        </a-form-item>
        <a-form-item label="自愈置信度打分 (0.0 - 1.0)">
          <a-input-number v-model:value="actionForm.confidence_score" :min="0" :max="1" :step="0.05" style="width: 100%" />
        </a-form-item>
        <a-form-item label="二次验证状态">
          <a-select v-model:value="actionForm.verification_status">
            <a-select-option value="verified_success">二次验证成功 (verified_success)</a-select-option>
            <a-select-option value="auto_accepted">策略自动采纳 (auto_accepted)</a-select-option>
            <a-select-option value="pending_verify">待执行验证 (pending_verify)</a-select-option>
            <a-select-option value="verified_failure">二次验证失败 (verified_failure)</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  ClusterOutlined,
  ReloadOutlined,
  BugOutlined,
  PlusOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  healingAuditTrailApi,
  type FaultClusterItem,
  type HealingAuditEntryItem,
  type HealingMetricsSummary,
  type HealingActionType,
  type HealingVerificationStatus,
} from '@/api/aiHealing'

const loading = ref(false)
const activeTab = ref<'clusters' | 'entries'>('clusters')

const metrics = reactive<HealingMetricsSummary>({
  total_healing_actions_count: 0,
  verification_success_rate_pct: 100,
  average_confidence_score: 0,
  total_fault_clusters_count: 0,
  estimated_engineering_hours_saved: 0,
})

const clusters = ref<FaultClusterItem[]>([])
const entries = ref<HealingAuditEntryItem[]>([])

const filterCaseId = ref<number | undefined>(undefined)
const filterActionType = ref<string | undefined>(undefined)

const actionTypeOptions = [
  { label: '全部类型', value: undefined },
  { label: '定位器替换 (locator_replaced)', value: 'locator_replaced' },
  { label: 'Schema 自愈修正 (schema_autofixed)', value: 'schema_autofixed' },
  { label: '柔性断言容差 (assertion_tolerated)', value: 'assertion_tolerated' },
  { label: '指数退避重试 (retry_with_backoff)', value: 'retry_with_backoff' },
]

const clusterColumns = [
  { title: '故障簇 ID / 特征签名', key: 'cluster_id', width: 220 },
  { title: '主要异常类型', key: 'primary_exception', width: 200 },
  { title: '根因摘要与自愈策略', key: 'root_cause_summary' },
  { title: '捕获频次', key: 'occurrences_count', width: 95 },
  { title: '波及范围', key: 'affected_cases', width: 220 },
  { title: '首/末次捕获时间', key: 'time_range', width: 170 },
]

const entryColumns = [
  { title: '流水 ID', key: 'audit_id', width: 160 },
  { title: '用例 & 步骤', key: 'case_step', width: 170 },
  { title: '自愈动作类型', key: 'action_type', width: 140 },
  { title: '自愈前后对比', key: 'value_diff' },
  { title: '置信度', key: 'confidence_score', width: 130 },
  { title: '二次验证', key: 'verification_status', width: 110 },
  { title: '算法耗时', key: 'duration_ms', width: 90 },
  { title: '执行时间', key: 'created_at', width: 140 },
]

// 模拟弹窗与表单
const showSimulateClusterModal = ref(false)
const clusterForm = reactive({
  case_id: 101,
  run_id: 501,
  exception_type: 'NoSuchElementException',
  error_message: 'Cannot locate element with locator: //*[@id="checkout-btn-v1"]',
  stack_trace: 'org.openqa.selenium.NoSuchElementException: An element could not be located on the page using the given search parameters.',
})

const showSimulateActionModal = ref(false)
const actionForm = reactive({
  case_id: 101,
  step_name: '点击结算按钮',
  action_type: 'locator_replaced' as HealingActionType,
  original_value: '//*[@id="checkout-btn-v1"]',
  healed_value: '//*[@data-testid="submit-order-btn"]',
  confidence_score: 0.95,
  verification_status: 'verified_success' as HealingVerificationStatus,
})

function formatTime(isoStr?: string): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return isoStr
  }
}

function formatValue(val: any): string {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

function getActionTypeLabel(type: HealingActionType): string {
  switch (type) {
    case 'locator_replaced':
      return '定位器自愈'
    case 'schema_autofixed':
      return '契约自愈修正'
    case 'assertion_tolerated':
      return '柔性断言放行'
    case 'retry_with_backoff':
      return '退避重试成功'
    default:
      return type
  }
}

function getActionTypeColor(type: HealingActionType): string {
  switch (type) {
    case 'locator_replaced':
      return 'blue'
    case 'schema_autofixed':
      return 'purple'
    case 'assertion_tolerated':
      return 'green'
    case 'retry_with_backoff':
      return 'orange'
    default:
      return 'default'
  }
}

function getVerificationStatusLabel(status: HealingVerificationStatus): string {
  switch (status) {
    case 'verified_success':
      return '验证成功'
    case 'auto_accepted':
      return '自动采纳'
    case 'pending_verify':
      return '待验证'
    case 'verified_failure':
      return '验证失败'
    default:
      return status
  }
}

function getVerificationStatusColor(status: HealingVerificationStatus): string {
  switch (status) {
    case 'verified_success':
      return 'success'
    case 'auto_accepted':
      return 'processing'
    case 'pending_verify':
      return 'warning'
    case 'verified_failure':
      return 'error'
    default:
      return 'default'
  }
}

async function loadData() {
  loading.value = true
  try {
    const [metricsRes, clustersRes, entriesRes] = await Promise.all([
      healingAuditTrailApi.getMetrics(),
      healingAuditTrailApi.listClusters(),
      healingAuditTrailApi.listEntries({
        case_id: filterCaseId.value,
        action_type: filterActionType.value,
      }),
    ])

    Object.assign(metrics, metricsRes)
    clusters.value = clustersRes.clusters || []
    entries.value = entriesRes.entries || []
  } catch (err: any) {
    message.error(`加载自愈审计数据失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function loadEntries() {
  try {
    const entriesRes = await healingAuditTrailApi.listEntries({
      case_id: filterCaseId.value,
      action_type: filterActionType.value,
    })
    entries.value = entriesRes.entries || []
  } catch (err: any) {
    message.error(`加载自愈流水失败: ${err.message || err}`)
  }
}

function resetFilters() {
  filterCaseId.value = undefined
  filterActionType.value = undefined
  loadEntries()
}

async function handleSimulateCluster() {
  try {
    const res = await healingAuditTrailApi.clusterError(clusterForm)
    message.success(res.message || '故障特征归一化与聚类成功')
    showSimulateClusterModal.value = false
    await loadData()
  } catch (err: any) {
    message.error(`聚类失败: ${err.message || err}`)
  }
}

async function handleSimulateAction() {
  try {
    const res = await healingAuditTrailApi.recordAction(actionForm)
    message.success(res.message || '自愈流水记录成功')
    showSimulateActionModal.value = false
    await loadData()
  } catch (err: any) {
    message.error(`记录流水失败: ${err.message || err}`)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.healing-audit-trail-panel {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--c-border-subtle, #e2e8f0);
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.header-icon-box {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--c-primary-soft, #eff6ff);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-icon {
  font-size: 18px;
  color: var(--c-primary, #3b82f6);
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
}

.header-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.5;
}

/* 成效 KPI 概览卡片 */
.metrics-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.kpi-card {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  transition: all 0.2s ease;
}

.kpi-card:hover {
  border-color: var(--c-primary, #3b82f6);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.highlight-card {
  background: var(--c-primary-soft, #eff6ff);
  border-color: var(--c-primary, #3b82f6);
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin-bottom: 6px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.kpi-number {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--c-text-primary, #1e293b);
}

.kpi-unit {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  margin-top: 6px;
  display: flex;
  align-items: center;
}

.text-success {
  color: var(--c-success, #10b981) !important;
}

.text-primary {
  color: var(--c-primary, #3b82f6) !important;
}

.text-warning {
  color: var(--c-warning, #f59e0b) !important;
}

.text-accent {
  color: #8b5cf6 !important;
}

/* 标签页与工具栏 */
.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.cluster-count-badge {
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
}

.cluster-id-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cluster-id-text {
  font-family: monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
}

.signature-tag {
  font-family: monospace;
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.root-cause-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-text {
  font-size: 12px;
  color: var(--c-text-primary, #1e293b);
}

.suggested-action {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-label {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.affected-cases-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.affected-label {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.more-text {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
}

.time-range-cell {
  display: flex;
  flex-direction: column;
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

/* 流水过滤栏与表格 */
.entries-filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.entry-total-text {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.step-text {
  margin-left: 4px;
  font-size: 12px;
}

.diff-card {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-family: monospace;
  font-size: 11px;
}

.diff-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.diff-tag-old {
  background: #fee2e2;
  color: #dc2626;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
}

.diff-tag-new {
  background: #d1fae5;
  color: #059669;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
}

.diff-val {
  max-width: 280px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.confidence-box {
  width: 100px;
}

.time-text {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}
</style>
