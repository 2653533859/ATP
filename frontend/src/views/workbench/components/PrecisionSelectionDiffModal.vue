<template>
  <a-modal
    :open="open"
    title="增量精准测试用例推荐与影响分析对比中枢"
    width="920px"
    :destroy-on-close="true"
    class="precision-selection-diff-modal"
    @cancel="handleCancel"
  >
    <div class="precision-modal-container">
      <!-- 顶部对比指标横幅 -->
      <div class="metrics-banner">
        <div class="banner-stat">
          <div class="stat-num text-success font-bold font-mono">
            {{ (reductionRatio * 100).toFixed(1) }}%
          </div>
          <div class="stat-label">用例裁剪节省率</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ timeSavedMinutes.toFixed(1) }}m
          </div>
          <div class="stat-label">预估节约回归耗时</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            {{ impactedCasesList.length }} <span class="text-xs text-secondary">/ {{ totalSuiteSize }}</span>
          </div>
          <div class="stat-label">增量用例 / 全量套件</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-purple font-mono">
            {{ changedSymbolsCount }} 符号 / {{ impactedEndpointsCount }} 接口
          </div>
          <div class="stat-label">代码影响面范围</div>
        </div>
      </div>

      <!-- 双 Tab 切换面板 -->
      <a-tabs v-model:activeKey="activeTab" class="precision-tabs">
        <!-- Tab 1: 增量推荐用例集 -->
        <a-tab-pane key="cases" tab="增量精准推荐用例集 (Recommended Cases)">
          <div class="tab-cases-toolbar">
            <span class="selection-summary text-xs">
              已选中 <strong>{{ selectedRowKeys.length }} / {{ impactedCasesList.length }}</strong> 条核心用例执行精准回归
            </span>
            <a-space size="small">
              <a-button size="small" @click="selectAll">全选</a-button>
              <a-button size="small" @click="deselectAll">清空选择</a-button>
            </a-space>
          </div>

          <a-table
            :data-source="impactedCasesList"
            :columns="casesColumns"
            :pagination="false"
            size="middle"
            row-key="case_id"
            :row-selection="rowSelection"
            class="cases-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'case_info'">
                <div class="case-info-col">
                  <span class="font-mono font-bold text-primary">{{ record.case_id }}</span>
                  <span class="case-name">{{ record.case_name }}</span>
                </div>
              </template>

              <template v-else-if="column.key === 'priority'">
                <a-tag :color="getPriorityColor(record.priority)">
                  {{ record.priority }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'endpoints'">
                <div class="endpoints-tag-wrap font-mono">
                  <a-tag
                    v-for="ep in record.impacted_by_endpoints"
                    :key="ep"
                    color="blue"
                  >
                    {{ ep }}
                  </a-tag>
                </div>
              </template>

              <template v-else-if="column.key === 'lineage'">
                <div class="lineage-flow-wrap font-mono text-xs">
                  <div
                    v-for="(link, lidx) in record.call_lineage"
                    :key="lidx"
                    class="lineage-item"
                  >
                    <ShareAltOutlined /> {{ link }}
                  </div>
                </div>
              </template>

              <template v-else-if="column.key === 'cost'">
                <span class="font-mono text-secondary text-xs">{{ record.execution_cost_seconds }}s</span>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- Tab 2: AST 变更高危符号树 -->
        <a-tab-pane key="symbols" tab="代码变更 AST 符号影响源 (Changed Symbols)">
          <a-table
            :data-source="symbolsList"
            :columns="symbolColumns"
            :pagination="false"
            size="middle"
            row-key="symbol_id"
            class="symbols-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'symbol_name'">
                <div class="symbol-info-col font-mono">
                  <span class="font-bold text-primary">{{ record.qualified_name || record.symbol_name }}</span>
                  <span class="text-xs text-secondary">{{ record.file_path }}</span>
                </div>
              </template>

              <template v-else-if="column.key === 'change_type'">
                <a-tag :color="getChangeTypeColor(record.change_type)">
                  {{ record.change_type }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)">
                  {{ record.severity }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'signature'">
                <pre class="sig-pre font-mono text-xs">{{ record.signature }}</pre>
              </template>

              <template v-else-if="column.key === 'lines'">
                <span class="font-mono text-xs">L{{ record.line_start }}-L{{ record.line_end }}</span>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button
          type="primary"
          :disabled="selectedRowKeys.length === 0"
          :loading="starting"
          @click="handleStartRegression"
        >
          <template #icon><RocketOutlined /></template>
          一键派发增量精准回归 ({{ selectedRowKeys.length }}条)
        </a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ShareAltOutlined,
  RocketOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  open: boolean
  analysisResult?: any
  diffReport?: any
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'startRegression', selectedCaseIds: string[]): void
}>()

const activeTab = ref('cases')
const starting = ref(false)
const selectedRowKeys = ref<string[]>([])

const impactedCasesList = computed(() => {
  const cases = props.analysisResult?.impacted_cases
  if (cases && cases.length > 0) {
    return cases
  }
  return [
    {
      case_id: 'case_order_checkout_flow',
      case_name: '收银台正常加购下单主流程',
      priority: 'P0',
      execution_cost_seconds: 15.0,
      impacted_by_endpoints: ['POST /api/v1/orders/checkout'],
      call_lineage: ['discount.calculate_discount ➔ POST /api/v1/orders/checkout ➔ case_order_checkout_flow'],
    },
    {
      case_id: 'case_order_zero_discount',
      case_name: '无优惠券零折扣兜底用例',
      priority: 'P1',
      execution_cost_seconds: 8.0,
      impacted_by_endpoints: ['POST /api/v1/orders/checkout'],
      call_lineage: ['discount.calculate_discount ➔ POST /api/v1/orders/checkout ➔ case_order_zero_discount'],
    },
    {
      case_id: 'case_discount_preview_vip',
      case_name: 'VIP优惠券抵扣预览测试',
      priority: 'P1',
      execution_cost_seconds: 6.0,
      impacted_by_endpoints: ['GET /api/v1/discounts/preview'],
      call_lineage: ['discount.calculate_discount ➔ GET /api/v1/discounts/preview ➔ case_discount_preview_vip'],
    },
  ]
})

const symbolsList = computed(() => {
  const syms = props.diffReport?.symbols
  if (syms && syms.length > 0) {
    return syms
  }
  return [
    {
      symbol_id: 'sym_calc_discount',
      symbol_name: 'calculate_discount',
      qualified_name: 'discount.calculate_discount',
      file_path: 'backend/app/services/discount.py',
      change_type: 'SIGNATURE_CHANGED',
      severity: 'CRITICAL',
      signature: 'calculate_discount(price, rate, vip_level=1)',
      line_start: 1,
      line_end: 5,
    },
  ]
})

watch(
  impactedCasesList,
  (list) => {
    selectedRowKeys.value = list.map((c: any) => c.case_id)
  },
  { immediate: true }
)

const reductionRatio = computed(() => {
  return props.analysisResult?.regression_reduction_ratio || 0.97
})

const totalSuiteSize = computed(() => {
  return props.analysisResult?.total_cases_in_suite || 100
})

const timeSavedMinutes = computed(() => {
  const sec = props.analysisResult?.estimated_time_saved_seconds || 970.0
  return sec / 60.0
})

const changedSymbolsCount = computed(() => {
  return symbolsList.value.length
})

const impactedEndpointsCount = computed(() => {
  return props.analysisResult?.impacted_endpoints_count || 2
})

const casesColumns = [
  { title: '用例信息 (Case Info)', key: 'case_info', width: 220 },
  { title: '优先级', key: 'priority', width: 90 },
  { title: '影响服务接口', key: 'endpoints', width: 200 },
  { title: '端到端调用溯源链', key: 'lineage', width: 280 },
  { title: '预估耗时', key: 'cost', width: 90 },
]

const symbolColumns = [
  { title: 'AST 符号全限定名', key: 'symbol_name', width: 240 },
  { title: '变迁类型', key: 'change_type', width: 140 },
  { title: '高危严重度', key: 'severity', width: 110 },
  { title: '函数签名定义', key: 'signature', width: 260 },
  { title: '代码行号', key: 'lines', width: 100 },
]

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: any[]) => {
    selectedRowKeys.value = keys
  },
}))

function selectAll() {
  selectedRowKeys.value = impactedCasesList.value.map((c: any) => c.case_id)
}

function deselectAll() {
  selectedRowKeys.value = []
}

function getPriorityColor(p: string) {
  switch (p) {
    case 'P0':
      return 'red'
    case 'P1':
      return 'orange'
    case 'P2':
      return 'blue'
    default:
      return 'default'
  }
}

function getChangeTypeColor(t: string) {
  switch (t) {
    case 'SIGNATURE_CHANGED':
      return 'magenta'
    case 'MODIFIED':
      return 'cyan'
    case 'ADDED':
      return 'green'
    case 'DELETED':
      return 'red'
    default:
      return 'default'
  }
}

function getSeverityColor(s: string) {
  switch (s) {
    case 'CRITICAL':
      return 'red'
    case 'MAJOR':
      return 'volcano'
    case 'MINOR':
      return 'gold'
    default:
      return 'default'
  }
}

async function handleStartRegression() {
  starting.value = true
  try {
    message.success(`已成功派发 ${selectedRowKeys.value.length} 条增量精准回归任务！`)
    emit('startRegression', selectedRowKeys.value)
    emit('update:open', false)
  } finally {
    starting.value = false
  }
}

function handleCancel() {
  emit('update:open', false)
}
</script>

<style scoped>
.precision-modal-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metrics-banner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 18px;
}

.banner-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-num {
  font-size: 20px;
  line-height: 1.2;
}

.stat-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.precision-tabs {
  margin-top: 4px;
}

.tab-cases-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.case-info-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.case-name {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.endpoints-tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.lineage-flow-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--c-text-secondary, #64748b);
}

.lineage-item {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.symbol-info-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sig-pre {
  margin: 0;
  padding: 2px 6px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

.text-success {
  color: #10b981;
}

.text-primary {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
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

.text-xs {
  font-size: 12px;
}
</style>
