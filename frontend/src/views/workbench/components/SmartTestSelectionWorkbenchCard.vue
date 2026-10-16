<template>
  <div class="smart-test-selection-card">
    <a-card size="small" class="selection-panel" :bordered="false">
      <!-- 头部控制与策略选择 -->
      <template #title>
        <div class="panel-header-row">
          <div class="header-left">
            <AimOutlined class="panel-icon" />
            <span class="panel-title">精准测试用例推荐与冗余裁剪 (Test Impact Analysis)</span>
            <a-tag color="processing">TIA 智能裁剪</a-tag>
          </div>

          <div class="header-right">
            <a-space size="small">
              <a-radio-group v-model:value="strategy" size="small" button-style="solid" @change="handleRunSelection">
                <a-radio-button value="minimal">最小必要 (Minimal)</a-radio-button>
                <a-radio-button value="balanced">平衡推荐 (Balanced)</a-radio-button>
                <a-radio-button value="comprehensive">深度覆盖 (Full)</a-radio-button>
              </a-radio-group>

              <a-button size="small" :loading="loading" @click="handleRunSelection">
                <ReloadOutlined /> 重新推导
              </a-button>

              <a-button
                type="primary"
                size="small"
                :disabled="!currentReport?.selected_cases?.length"
                :loading="executing"
                @click="handleExecuteSelected"
              >
                <PlayCircleOutlined /> 一键执行推荐集 ({{ currentReport?.selected_cases_count || 0 }})
              </a-button>
            </a-space>
          </div>
        </div>
      </template>

      <a-spin :spinning="loading">
        <template v-if="currentReport">
          <!-- 核心效能收益度量卡片网格 -->
          <div class="metrics-grid">
            <div class="metric-box highlight-green">
              <span class="m-lbl">冗余用例裁剪率</span>
              <div class="m-val-row">
                <span class="m-val text-success">{{ currentReport.pruning_ratio_pct }}%</span>
              </div>
              <span class="m-sub">已过滤 {{ currentReport.pruned_cases_count }} 个非必要用例</span>
            </div>

            <div class="metric-box">
              <span class="m-lbl">推荐测试子集</span>
              <div class="m-val-row">
                <span class="m-val text-blue">{{ currentReport.selected_cases_count }}</span>
                <span class="m-unit">/ {{ currentReport.total_repository_cases_count }} 全量</span>
              </div>
              <span class="m-sub">仅聚焦变更关联代码</span>
            </div>

            <div class="metric-box">
              <span class="m-lbl">精选执行耗时预估</span>
              <div class="m-val-row">
                <span class="m-val text-purple">{{ currentReport.estimated_execution_time_sec }}</span>
                <span class="m-unit">秒</span>
              </div>
              <span class="m-sub">基于历史实测平均耗时</span>
            </div>

            <div class="metric-box highlight-accent">
              <span class="m-lbl">预估节省 CI 等待时间</span>
              <div class="m-val-row">
                <span class="m-val text-accent">~{{ Math.round(currentReport.estimated_time_saved_sec) }}</span>
                <span class="m-unit">秒</span>
              </div>
              <span class="m-sub">提速约 {{ calculateSpeedupFactor() }} 倍</span>
            </div>
          </div>

          <!-- 推荐用例清单表格 -->
          <div class="cases-table-section">
            <div class="table-bar">
              <span class="table-bar-title">精准入选用例清单 (按置信度排序)</span>
              <span class="table-bar-meta">策略: <code>{{ currentReport.strategy }}</code></span>
            </div>

            <a-table
              :data-source="currentReport.selected_cases || []"
              :columns="columns"
              row-key="case_id"
              size="small"
              :pagination="{ pageSize: 5, showTotal: (t: number) => `共推荐 ${t} 个用例` }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'case_name'">
                  <div class="case-name-cell">
                    <span class="case-title font-bold">#{{ record.case_id }} {{ record.case_name }}</span>
                    <small v-if="record.matched_routes?.length" class="matched-route">
                      路由: {{ record.matched_routes.join(', ') }}
                    </small>
                  </div>
                </template>

                <template v-else-if="column.key === 'priority'">
                  <a-tag :color="record.priority === 'P0' ? 'error' : (record.priority === 'P1' ? 'blue' : 'default')">
                    {{ record.priority }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'selection_reason'">
                  <span class="reason-text">{{ record.selection_reason }}</span>
                </template>

                <template v-else-if="column.key === 'confidence_score'">
                  <div class="confidence-box">
                    <a-progress
                      :percent="Math.round(record.confidence_score * 100)"
                      size="small"
                      :stroke-color="record.confidence_score >= 0.9 ? '#10b981' : '#6366f1'"
                    />
                  </div>
                </template>

                <template v-else-if="column.key === 'estimated_duration_sec'">
                  <span class="mono-text">{{ record.estimated_duration_sec }}s</span>
                </template>
              </template>
            </a-table>
          </div>
        </template>

        <a-empty v-else description="暂无测试推荐报告，请点击「重新推导」运行 TIA 分析" />
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  AimOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type SelectionStrategy,
  type SmartTestSelectionReportItem,
} from '@/api/ciImpact'

const props = withDefaults(
  defineProps<{
    projectId?: number | null
    defaultDiffText?: string
  }>(),
  {
    projectId: null,
    defaultDiffText: '',
  }
)

const emit = defineEmits<{
  (e: 'execute', caseIds: number[]): void
}>()

const loading = ref(false)
const executing = ref(false)
const strategy = ref<SelectionStrategy>('balanced')
const currentReport = ref<SmartTestSelectionReportItem | null>(null)

// 默认基准 Diff
const SAMPLE_DIFF = `diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -8,4 +8,6 @@ def calculate_discount(price: float) -> float:
+    if price > 1000:
+        return price * 0.8
     return price * 0.95
`

const columns = [
  { title: '测试用例 ID 与名称', key: 'case_name', width: 280 },
  { title: '优先级', key: 'priority', width: 80 },
  { title: '入选推荐归因', key: 'selection_reason' },
  { title: '匹配置信度', key: 'confidence_score', width: 140 },
  { title: '预估耗时', key: 'estimated_duration_sec', width: 90 },
]

function calculateSpeedupFactor(): string {
  if (!currentReport.value) return '1.0'
  const full = currentReport.value.total_repository_cases_count * 3.5
  const sel = currentReport.value.estimated_execution_time_sec || 1
  return (full / sel).toFixed(1)
}

async function handleRunSelection() {
  loading.value = true
  try {
    const diff = props.defaultDiffText || SAMPLE_DIFF
    const res = await ciImpactApi.selectTests({
      diff_text: diff,
      strategy: strategy.value,
      project_id: props.projectId,
      total_repo_cases_override: 20, // 假设基准全量 20 个用例
    })
    currentReport.value = res.report
    message.success(res.message || '精准测试集推导完成')
  } catch (err: any) {
    message.error(`推荐推导失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

function handleExecuteSelected() {
  if (!currentReport.value || !currentReport.value.selected_cases.length) return
  const caseIds = currentReport.value.selected_cases.map((c) => c.case_id)
  emit('execute', caseIds)
  message.success(`已下发执行精选测试集 (共 ${caseIds.length} 个用例)`)
}

onMounted(() => {
  handleRunSelection()
})
</script>

<style scoped>
.smart-test-selection-card {
  margin-top: 14px;
}

.selection-panel {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  background: var(--c-bg-card, #ffffff);
}

.panel-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-icon {
  font-size: 16px;
  color: #6366f1;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

/* 核心效能收益度量卡片网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.metric-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
}

.highlight-green {
  background: #ecfdf5;
  border-color: #a7f3d0;
}

.highlight-accent {
  background: #faf5ff;
  border-color: #e9d5ff;
}

.m-lbl {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.m-val-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.m-val {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  color: #0f172a;
}

.m-unit {
  font-size: 11px;
  color: #64748b;
}

.m-sub {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
}

.text-success {
  color: #10b981;
}

.text-blue {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

.text-accent {
  color: #9333ea;
}

/* 列表区 */
.cases-table-section {
  display: flex;
  flex-direction: column;
}

.table-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
}

.table-bar-title {
  font-weight: 600;
  color: #1e293b;
}

.table-bar-meta code {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 4px;
  border-radius: 4px;
}

.case-name-cell {
  display: flex;
  flex-direction: column;
}

.case-title {
  font-size: 12px;
  color: #0f172a;
}

.matched-route {
  font-family: monospace;
  font-size: 10px;
  color: #64748b;
}

.font-bold {
  font-weight: 700;
}

.reason-text {
  font-size: 11px;
  color: #334155;
}

.confidence-box {
  width: 120px;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}
</style>
