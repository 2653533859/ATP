<template>
  <a-drawer
    :open="open"
    :width="960"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <div class="drawer-title-box">
        <span>接口契约变更影响面分析与受损用例逆向推导</span>
        <a-tag v-if="report?.has_breaking_changes" color="red">存在破坏性变更</a-tag>
        <a-tag v-else-if="report" color="green">向后兼容</a-tag>
      </div>
    </template>

    <div class="contract-change-impact-drawer">
      <!-- 头部控制与快捷预设 -->
      <a-card size="small" class="control-card">
        <div class="control-top">
          <div class="method-path-box">
            <a-select v-model:value="method" style="width: 100px" size="small">
              <a-select-option value="POST">POST</a-select-option>
              <a-select-option value="GET">GET</a-select-option>
              <a-select-option value="PUT">PUT</a-select-option>
              <a-select-option value="DELETE">DELETE</a-select-option>
            </a-select>
            <a-input v-model:value="path" placeholder="接口路径如 /api/v1/orders" size="small" style="flex: 1" />
          </div>

          <div class="preset-actions">
            <a-space size="small">
              <a-button size="small" @click="loadBreakingPreset">
                载入破坏性变更示例
              </a-button>
              <a-button size="small" @click="loadCompatiblePreset">
                载入兼容变更示例
              </a-button>
              <a-button
                type="primary"
                :danger="report?.has_breaking_changes"
                size="small"
                :loading="analyzing"
                @click="handleAnalyze"
              >
                开始逆向影响分析
              </a-button>
            </a-space>
          </div>
        </div>
      </a-card>

      <!-- 双栏契约 Schema 编辑区 -->
      <a-row :gutter="12" class="schema-editors-row">
        <a-col :span="12">
          <div class="editor-pane">
            <div class="editor-header">
              <span class="editor-title">基线契约 (Baseline OpenAPI Schema)</span>
              <a-tag color="blue">基准版本</a-tag>
            </div>
            <a-textarea
              v-model:value="baselineSchemaText"
              :rows="9"
              class="schema-textarea"
              placeholder="请输入基线 OpenAPI / JSON Schema..."
            />
          </div>
        </a-col>

        <a-col :span="12">
          <div class="editor-pane">
            <div class="editor-header">
              <span class="editor-title">当前版本契约 (Current OpenAPI Schema)</span>
              <a-tag color="purple">变更版本</a-tag>
            </div>
            <a-textarea
              v-model:value="currentSchemaText"
              :rows="9"
              class="schema-textarea"
              placeholder="请输入当前变更后的 OpenAPI / JSON Schema..."
            />
          </div>
        </a-col>
      </a-row>

      <!-- 影响面评估 KPI 指标行 -->
      <div v-if="report" class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">破坏性变更 (Breaking)</span>
          <div class="metric-value">
            <strong :class="report.diff_summary.breaking_count > 0 ? 'text-red' : 'text-slate'">
              {{ report.diff_summary.breaking_count }}
            </strong>
            <small class="unit">处破坏</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">潜在风险告警 (Warnings)</span>
          <div class="metric-value">
            <strong :class="report.diff_summary.warning_count > 0 ? 'text-orange' : 'text-slate'">
              {{ report.diff_summary.warning_count }}
            </strong>
            <small class="unit">处告警</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">向后兼容变更 (Compatible)</span>
          <div class="metric-value">
            <strong class="text-green">{{ report.diff_summary.compatible_count }}</strong>
            <small class="unit">处兼容</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">受波及受损用例 (Impacted Cases)</span>
          <div class="metric-value">
            <strong :class="report.total_impacted_cases_count > 0 ? 'text-purple' : 'text-slate'">
              {{ report.total_impacted_cases_count }}
            </strong>
            <small class="unit">个用例</small>
          </div>
        </div>
      </div>

      <!-- 破坏性阻断告警横幅 -->
      <a-alert
        v-if="report?.has_breaking_changes"
        type="error"
        show-icon
        class="impact-alert"
        :message="`[契约破坏性风险] 检测到 ${report.diff_summary.breaking_count} 处 Breaking 破坏性字段变更！`"
        :description="`波及受损测试用例 ${report.total_impacted_cases_count} 个，影响测试套件 ${report.impacted_suites_count} 个，计划 ${report.impacted_plans_count} 个。需组织精准回归验证。`"
      />

      <!-- 分析明细双标签页：字段 Diff 与受波及用例 -->
      <a-card v-if="report" size="small" class="detail-card">
        <a-tabs v-model:activeKey="activeTab" size="small">
          <!-- 字段 Diff 变更明细 -->
          <a-tab-pane key="diff" :tab="`契约 Diff 变更明细 (${allChangesCount})`">
            <a-table
              :data-source="allChanges"
              :columns="changeColumns"
              row-key="field_path"
              size="small"
              :pagination="{ pageSize: 5 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'change_type'">
                  <a-tag :color="getSeverityColor(record.change_type)">
                    {{ record.change_type.toUpperCase() }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'field_path'">
                  <code>{{ record.field_path }}</code>
                </template>
                <template v-if="column.key === 'rule'">
                  <span>{{ record.rule }}</span>
                </template>
                <template v-if="column.key === 'description'">
                  <span>{{ record.description }}</span>
                </template>
              </template>
            </a-table>
          </a-tab-pane>

          <!-- 逆向推导受波及测试用例 -->
          <a-tab-pane key="cases" :tab="`受波及受损用例 (${report.impacted_cases.length})`">
            <div class="cases-pane-header">
              <span class="hint-text">通过资产图谱反向追踪依赖该接口的全部测试用例：</span>
              <a-button
                v-if="report.impacted_cases.length > 0"
                type="primary"
                size="small"
                @click="handleTriggerRegressionWizard"
              >
                基于受损用例合成回归套件
              </a-button>
            </div>

            <a-table
              :data-source="report.impacted_cases"
              :columns="caseColumns"
              row-key="case_id"
              size="small"
              :pagination="{ pageSize: 5 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'case_name'">
                  <strong>{{ record.case_name }}</strong>
                </template>
                <template v-if="column.key === 'severity'">
                  <a-tag :color="getSeverityColor(record.severity)">
                    {{ record.severity.toUpperCase() }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'reasons'">
                  <div class="reasons-list">
                    <span v-for="(r, i) in record.reasons" :key="i" class="reason-item">
                      • {{ r }}
                    </span>
                  </div>
                </template>
                <template v-if="column.key === 'remediation'">
                  <span class="remediation-text">{{ record.actionable_remediation }}</span>
                </template>
              </template>
            </a-table>
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  assetGraphApi,
  type ContractImpactReport,
  type ChangeSeverity,
  type ContractSchemaChange,
} from '@/api/assetGraph'

const props = withDefaults(
  defineProps<{
    open: boolean
    defaultProjectId?: number
  }>(),
  {
    open: false,
    defaultProjectId: 1,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'synthesize-regression', caseIds: number[]): void
}>()

const analyzing = ref(false)
const method = ref('POST')
const path = ref('/api/v1/orders')
const activeTab = ref('diff')
const report = ref<ContractImpactReport | null>(null)

const defaultBaseline = {
  type: 'object',
  required: ['order_id', 'amount', 'currency'],
  properties: {
    order_id: { type: 'string' },
    amount: { type: 'number' },
    currency: { type: 'string' },
  },
}

const defaultCurrent = {
  type: 'object',
  required: ['amount', 'currency'],
  properties: {
    amount: { type: 'string' },
    currency: { type: 'string' },
    discount_code: { type: 'string' },
  },
}

const baselineSchemaText = ref(JSON.stringify(defaultBaseline, null, 2))
const currentSchemaText = ref(JSON.stringify(defaultCurrent, null, 2))

const changeColumns = [
  { title: '变更等级', key: 'change_type', width: 120 },
  { title: '字段路径', key: 'field_path', width: 180 },
  { title: '规则特征', dataIndex: 'rule', key: 'rule', width: 170 },
  { title: '详细差异说明', dataIndex: 'description', key: 'description' },
]

const caseColumns = [
  { title: '用例 ID', dataIndex: 'case_id', key: 'case_id', width: 90 },
  { title: '用例名称', dataIndex: 'case_name', key: 'case_name', width: 180 },
  { title: '受损等级', key: 'severity', width: 110 },
  { title: '受损归因', key: 'reasons' },
  { title: '建议修复方案', key: 'remediation', width: 220 },
]

const allChanges = computed<ContractSchemaChange[]>(() => {
  if (!report.value) return []
  return [
    ...report.value.breaking_changes,
    ...report.value.warnings,
    ...report.value.compatible_changes,
  ]
})

const allChangesCount = computed(() => allChanges.value.length)

function getSeverityColor(s: ChangeSeverity): string {
  switch (s) {
    case 'breaking':
      return 'red'
    case 'warning':
      return 'orange'
    case 'compatible':
      return 'green'
    default:
      return 'default'
  }
}

function handleClose() {
  emit('update:open', false)
}

function loadBreakingPreset() {
  method.value = 'POST'
  path.value = '/api/v1/orders'
  baselineSchemaText.value = JSON.stringify(defaultBaseline, null, 2)
  currentSchemaText.value = JSON.stringify(defaultCurrent, null, 2)
  message.info('已载入破坏性变更（Breaking）契约示例！')
}

function loadCompatiblePreset() {
  method.value = 'POST'
  path.value = '/api/v1/orders'
  baselineSchemaText.value = JSON.stringify(defaultBaseline, null, 2)
  const compatibleSchema = {
    ...defaultBaseline,
    properties: {
      ...defaultBaseline.properties,
      remark: { type: 'string' },
    },
  }
  currentSchemaText.value = JSON.stringify(compatibleSchema, null, 2)
  message.info('已载入完全向后兼容契约示例！')
}

async function handleAnalyze() {
  analyzing.value = true
  try {
    let baselineObj: any
    let currentObj: any
    try {
      baselineObj = JSON.parse(baselineSchemaText.value)
    } catch {
      throw new Error('基线契约 JSON 格式错误')
    }
    try {
      currentObj = JSON.parse(currentSchemaText.value)
    } catch {
      throw new Error('当前版本契约 JSON 格式错误')
    }

    const res = await assetGraphApi.analyzeContractImpact({
      method: method.value,
      path: path.value,
      baseline_schema: baselineObj,
      current_schema: currentObj,
      project_id: props.defaultProjectId,
    })

    report.value = res
    if (res.has_breaking_changes) {
      message.warning(`分析完成：检测到 ${res.diff_summary.breaking_count} 项破坏性变更，波及 ${res.total_impacted_cases_count} 个用例！`)
    } else {
      message.success('分析完成：契约完全向后兼容，未检测到破坏性变更。')
    }
  } catch (err: any) {
    message.error(err.message || '分析契约影响面失败')
  } finally {
    analyzing.value = false
  }
}

function handleTriggerRegressionWizard() {
  if (!report.value || report.value.impacted_cases.length === 0) return
  const caseIds = report.value.impacted_cases.map((c) => c.case_id)
  emit('synthesize-regression', caseIds)
  message.success(`已提取 ${caseIds.length} 个受损用例，准备合成精准回归套件！`)
}
</script>

<style scoped>
.contract-change-impact-drawer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.control-card,
.detail-card {
  border-radius: 8px;
}

.control-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}

.method-path-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.schema-editors-row {
  margin-top: 2px;
}

.editor-pane {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-title {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.schema-textarea {
  font-family: monospace;
  font-size: 11px;
  line-height: 1.4;
  background: #ffffff;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.metric-card {
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 11px;
  color: #64748b;
  display: block;
  margin-bottom: 2px;
}

.metric-value {
  font-size: 17px;
  color: #0f172a;
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.unit {
  font-size: 11px;
  font-weight: normal;
  color: #94a3b8;
}

.text-red {
  color: #ef4444;
}

.text-orange {
  color: #f59e0b;
}

.text-green {
  color: #10b981;
}

.text-purple {
  color: #8b5cf6;
}

.text-slate {
  color: #64748b;
}

.impact-alert {
  border-radius: 6px;
}

.cases-pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.hint-text {
  font-size: 12px;
  color: #64748b;
}

.reasons-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: #dc2626;
}

.remediation-text {
  font-size: 11px;
  color: #2563eb;
}
</style>
