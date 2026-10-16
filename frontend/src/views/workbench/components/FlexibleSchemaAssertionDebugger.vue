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
        <span>接口响应 Schema 动态漂移自适应修正与柔性断言调试器</span>
        <a-tag v-if="assertionResult?.passed" color="green">断言放行 (PASS)</a-tag>
        <a-tag v-else-if="assertionResult" color="red">断言阻断 (FAIL)</a-tag>
      </div>
    </template>

    <div class="schema-debugger-body">
      <!-- 头部控制栏：容差模式与高级开关 -->
      <a-card size="small" class="control-card">
        <div class="control-header">
          <h4 class="title">多级契约容差策略与漂移自愈模式配置</h4>
          <p class="subtitle">
            针对微服务接口持续演进中常见的非破坏性新增字段、数组乱序或弱类型强转，提供智能柔性断言（Flexible Assertion），在严防破坏性破坏（Breaking）的同时杜绝假阳性误报。
          </p>
        </div>

        <div class="mode-control-row">
          <span class="ctrl-label">断言容差模式:</span>
          <a-radio-group v-model:value="toleranceMode" size="small">
            <a-radio-button value="compatible">兼容自愈 (COMPATIBLE)</a-radio-button>
            <a-radio-button value="strict">严格模式 (STRICT)</a-radio-button>
            <a-radio-button value="lenient">宽容强转 (LENIENT)</a-radio-button>
          </a-radio-group>

          <a-space size="small" class="toggle-space">
            <a-checkbox v-model:checked="ignoreExtraFields">容忍冗余字段</a-checkbox>
            <a-checkbox v-model:checked="allowNumericCoercion">允许字符串数字强转</a-checkbox>
          </a-space>

          <a-space size="small" class="preset-space">
            <a-button size="small" @click="loadBenignDriftPreset">
              载入冗余字段示例
            </a-button>
            <a-button size="small" @click="loadBreakingDriftPreset">
              载入破坏性示例
            </a-button>
            <a-button
              type="primary"
              size="small"
              :loading="evaluating"
              @click="handleEvaluateAssertion"
            >
              执行柔性断言
            </a-button>
          </a-space>
        </div>
      </a-card>

      <!-- 双栏输入：预期 Schema vs 实际响应 Payload -->
      <a-row :gutter="12" class="editors-row">
        <a-col :span="12">
          <div class="editor-pane">
            <div class="pane-header">
              <span class="pane-title">预期 JSON Schema (Expected Schema)</span>
              <a-tag color="blue">契约基线</a-tag>
            </div>
            <a-textarea
              v-model:value="expectedSchemaText"
              :rows="8"
              class="json-textarea"
              placeholder="请输入预期的 OpenAPI / JSON Schema..."
            />
          </div>
        </a-col>

        <a-col :span="12">
          <div class="editor-pane">
            <div class="pane-header">
              <span class="pane-title">接口实际响应数据 (Actual Payload)</span>
              <a-tag color="purple">接口返回</a-tag>
            </div>
            <a-textarea
              v-model:value="actualPayloadText"
              :rows="8"
              class="json-textarea"
              placeholder="请输入接口实际返回的 JSON 数据载荷..."
            />
          </div>
        </a-col>
      </a-row>

      <!-- 判定结果横幅 -->
      <div v-if="assertionResult" class="result-banner-section">
        <a-alert
          :type="assertionResult.passed ? 'success' : 'error'"
          show-icon
          class="res-alert"
          :message="assertionResult.passed ? '[柔性断言通过 PASS] 响应数据结构合规！' : '[契约断言失败 FAIL] 检测到破坏性 Schema 违规！'"
          :description="assertionResult.summary"
        />

        <!-- 漂移分类 KPI 卡片行 -->
        <div class="drift-kpi-row">
          <div class="kpi-item">
            <span class="kpi-label">响应漂移总数</span>
            <strong class="kpi-val">{{ assertionResult.total_drifts_count }}</strong>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">新增冗余字段 (Extra)</span>
            <strong class="kpi-val text-blue">{{ extraFieldsCount }}</strong>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">缺失必填字段 (Missing)</span>
            <strong :class="missingFieldsCount > 0 ? 'text-red' : 'text-slate'" class="kpi-val">
              {{ missingFieldsCount }}
            </strong>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">字段类型漂移 (Type)</span>
            <strong :class="typeDriftsCount > 0 ? 'text-orange' : 'text-slate'" class="kpi-val">
              {{ typeDriftsCount }}
            </strong>
          </div>
        </div>
      </div>

      <!-- 漂移明细表格 -->
      <a-card
        v-if="assertionResult && assertionResult.drifts.length > 0"
        size="small"
        :title="`Schema 动态漂移特征清单 (${assertionResult.drifts.length} 处)`"
        class="drifts-table-card"
      >
        <a-table
          :data-source="assertionResult.drifts"
          :columns="driftColumns"
          row-key="field_path"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'field_path'">
              <code>{{ record.field_path }}</code>
            </template>

            <template v-if="column.key === 'drift_type'">
              <a-tag :color="getDriftTypeColor(record.drift_type)">
                {{ record.drift_type.toUpperCase() }}
              </a-tag>
            </template>

            <template v-if="column.key === 'breaking'">
              <a-tag :color="record.is_breaking ? 'red' : 'green'">
                {{ record.is_breaking ? '破坏性违规' : '良性放行' }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 自愈修正版 Schema 预览 -->
      <a-card
        v-if="assertionResult?.autofixed_schema"
        size="small"
        title="AI 自愈修正版 Schema 建议 (Autofixed Schema Proposal)"
        class="autofix-card"
      >
        <template #extra>
          <a-button size="small" type="primary" ghost @click="copyAutofixSchema">
            复制自愈 Schema 覆盖用例基线
          </a-button>
        </template>

        <div class="autofix-preview-box">
          <pre class="json-code-box">{{ JSON.stringify(assertionResult.autofixed_schema, null, 2) }}</pre>
        </div>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  flexibleAssertionApi,
  type AssertionToleranceMode,
  type FlexibleAssertionResultItem,
  type SchemaDriftType,
} from '@/api/aiHealing'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const evaluating = ref(false)
const toleranceMode = ref<AssertionToleranceMode>('compatible')
const ignoreExtraFields = ref(true)
const allowNumericCoercion = ref(true)

const defaultExpected = {
  type: 'object',
  required: ['order_id', 'amount', 'currency'],
  properties: {
    order_id: { type: 'string' },
    amount: { type: 'number' },
    currency: { type: 'string' },
  },
}

const defaultActual = {
  order_id: 'ORD-20261016-9901',
  amount: 199.5,
  currency: 'CNY',
  coupon_code: 'PROMO-2026',
  discount_pct: 0.15,
}

const expectedSchemaText = ref(JSON.stringify(defaultExpected, null, 2))
const actualPayloadText = ref(JSON.stringify(defaultActual, null, 2))
const assertionResult = ref<FlexibleAssertionResultItem | null>(null)

const driftColumns = [
  { title: '字段路径 (Field Path)', key: 'field_path', width: 220 },
  { title: '漂移类型', key: 'drift_type', width: 140 },
  { title: '性质判定', key: 'breaking', width: 110 },
  { title: '详细差异说明', dataIndex: 'description', key: 'description' },
]

const extraFieldsCount = computed(
  () => assertionResult.value?.drifts.filter((d) => d.drift_type === 'extra_field').length || 0
)
const missingFieldsCount = computed(
  () => assertionResult.value?.drifts.filter((d) => d.drift_type === 'missing_field').length || 0
)
const typeDriftsCount = computed(
  () => assertionResult.value?.drifts.filter((d) => d.drift_type === 'type_drift').length || 0
)

function getDriftTypeColor(dt: SchemaDriftType): string {
  switch (dt) {
    case 'extra_field':
      return 'blue'
    case 'missing_field':
      return 'red'
    case 'type_drift':
      return 'orange'
    case 'nullable_drift':
      return 'purple'
    default:
      return 'default'
  }
}

function handleClose() {
  emit('update:open', false)
}

function loadBenignDriftPreset() {
  expectedSchemaText.value = JSON.stringify(defaultExpected, null, 2)
  actualPayloadText.value = JSON.stringify(defaultActual, null, 2)
  toleranceMode.value = 'compatible'
  message.info('已载入新增冗余字段的良性漂移示例！')
}

function loadBreakingDriftPreset() {
  expectedSchemaText.value = JSON.stringify(defaultExpected, null, 2)
  const brokenPayload = {
    amount: 'invalid_amount_string', // 破坏性类型错误
    currency: 'CNY',
    // 缺失必填 order_id
  }
  actualPayloadText.value = JSON.stringify(brokenPayload, null, 2)
  message.warning('已载入破坏性字段缺失与类型错误示例！')
}

async function handleEvaluateAssertion() {
  evaluating.value = true
  try {
    let expected: any
    let actual: any
    try {
      expected = JSON.parse(expectedSchemaText.value)
    } catch {
      throw new Error('预期 Schema JSON 格式不合法')
    }
    try {
      actual = JSON.parse(actualPayloadText.value)
    } catch {
      throw new Error('实际响应 Payload JSON 格式不合法')
    }

    const res = await flexibleAssertionApi.evaluate({
      expected_schema: expected,
      actual_payload: actual,
      mode: toleranceMode.value,
      ignore_extra_fields: ignoreExtraFields.value,
      allow_numeric_string_coercion: allowNumericCoercion.value,
      autofix_schema: true,
    })

    assertionResult.value = res
    if (res.passed) {
      message.success('柔性断言通过：未检测到破坏性违规！')
    } else {
      message.error('柔性断言阻断：存在破坏性必填字段缺失或类型不兼容！')
    }
  } catch (err: any) {
    message.error(err.message || '执行柔性断言失败')
  } finally {
    evaluating.value = false
  }
}

function copyAutofixSchema() {
  if (assertionResult.value?.autofixed_schema && navigator.clipboard) {
    navigator.clipboard.writeText(JSON.stringify(assertionResult.value.autofixed_schema, null, 2))
    message.success('自愈修正版 Schema 已复制到剪贴板！')
  }
}
</script>

<style scoped>
.schema-debugger-body {
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
.drifts-table-card,
.autofix-card {
  border-radius: 8px;
}

.control-header {
  margin-bottom: 8px;
}

.title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.mode-control-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ctrl-label {
  font-size: 12px;
  color: #334155;
  font-weight: 600;
}

.editors-row {
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

.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pane-title {
  font-size: 11px;
  font-weight: 600;
  color: #334155;
}

.json-textarea {
  font-family: monospace;
  font-size: 11px;
  background: #ffffff;
}

.result-banner-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.res-alert {
  border-radius: 6px;
}

.drift-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.kpi-item {
  padding: 8px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
}

.kpi-val {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.text-blue {
  color: #2563eb;
}

.text-red {
  color: #dc2626;
}

.text-orange {
  color: #ea580c;
}

.text-slate {
  color: #64748b;
}

.autofix-preview-box {
  background: #0f172a;
  border-radius: 6px;
  padding: 10px;
}

.json-code-box {
  margin: 0;
  color: #38bdf8;
  font-family: monospace;
  font-size: 11px;
  max-height: 200px;
  overflow-y: auto;
}
</style>
