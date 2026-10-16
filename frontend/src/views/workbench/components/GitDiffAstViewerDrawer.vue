<template>
  <a-drawer
    :open="open"
    :width="1040"
    placement="right"
    title="Git Diff 代码变更差异 AST 语义分析与符号路由映射"
    destroy-on-close
    @close="handleClose"
  >
    <div class="git-diff-ast-viewer">
      <!-- 头部说明横幅 -->
      <div class="drawer-banner">
        <div class="banner-left">
          <CodeOutlined class="banner-icon" />
          <div>
            <div class="banner-title-row">
              <span class="banner-title">源码级 Diff 语法树 (AST) 语义提取引擎</span>
              <a-tag color="processing">Python AST 3.12</a-tag>
              <a-tag color="purple">FastAPI 路由映射</a-tag>
            </div>
            <p class="banner-desc">
              解析 Git Unified Diff 补丁，基于 AST 树提取代码变更所触及的类、函数与 API 路由端点，为精准回归测试提供源头证据。
            </p>
          </div>
        </div>
        <div class="banner-actions">
          <a-space>
            <a-button size="small" @click="loadSampleDiff('orders')">示例: 订单与折扣变更</a-button>
            <a-button size="small" @click="loadSampleDiff('auth')">示例: 认证路由修改</a-button>
          </a-space>
        </div>
      </div>

      <!-- Diff 输入与控制操作栏 -->
      <div class="input-controls-row">
        <a-space style="width: 100%; justify-content: space-between">
          <a-space>
            <a-select
              v-if="historyReports.length > 0"
              v-model:value="selectedReportId"
              placeholder="查看历史 Diff AST 分析报告"
              style="width: 280px"
              size="small"
              :options="historyOptions"
              @change="handleSelectHistory"
            />
            <a-button size="small" :loading="loading" @click="loadReports">
              <ReloadOutlined /> 刷新
            </a-button>
          </a-space>

          <a-button type="primary" size="small" :loading="analyzing" @click="handleRunAnalyze">
            <ThunderboltOutlined /> 解析 Diff AST 语义
          </a-button>
        </a-space>
      </div>

      <a-spin :spinning="loading || analyzing">
        <!-- 统计摘要 KPI 卡片 -->
        <div v-if="currentReport" class="stats-grid">
          <div class="kpi-card">
            <span class="kpi-label">变更文件总数</span>
            <span class="kpi-num">{{ currentReport.diff_summary?.total_files_changed ?? 0 }}</span>
            <span class="kpi-sub">代码模块改动</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">新增代码行 (LOC)</span>
            <span class="kpi-num text-success">+{{ currentReport.diff_summary?.total_added_lines ?? 0 }}</span>
            <span class="kpi-sub">有效新增逻辑</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">删除代码行 (LOC)</span>
            <span class="kpi-num text-danger">-{{ currentReport.diff_summary?.total_deleted_lines ?? 0 }}</span>
            <span class="kpi-sub">清理与重构行</span>
          </div>
          <div class="kpi-card highlight-card-purple">
            <span class="kpi-label">触及 AST 符号</span>
            <span class="kpi-num text-purple">{{ currentReport.diff_summary?.affected_symbols_count ?? 0 }}</span>
            <span class="kpi-sub">修改的类与函数</span>
          </div>
          <div class="kpi-card highlight-card-blue">
            <span class="kpi-label">波及 API 路由</span>
            <span class="kpi-num text-blue">{{ currentReport.diff_summary?.affected_routes_count ?? 0 }}</span>
            <span class="kpi-sub">受影响外部端点</span>
          </div>
        </div>

        <!-- 双栏：左侧 Diff 文本编辑/预览，右侧 AST 符号与路由表格 -->
        <div class="diff-viewer-grid">
          <!-- 左栏：Diff 补丁文本框 -->
          <div class="diff-editor-col">
            <div class="col-header">
              <span class="col-title">Git Unified Diff 补丁内容</span>
              <a-tag color="default">{{ diffLineCount }} 行</a-tag>
            </div>
            <a-textarea
              v-model:value="diffInputText"
              :rows="16"
              class="diff-textarea"
              placeholder="在此粘贴 Git Diff 补丁文本 (diff --git a/... b/...)"
            />
          </div>

          <!-- 右栏：AST 符号与路由详情 Tab -->
          <div class="ast-symbols-col">
            <a-card size="small" class="ast-tabs-card" :bordered="false">
              <a-tabs v-model:activeKey="activeTab">
                <!-- Tab 1: 受影响代码符号 -->
                <a-tab-pane key="symbols" tab="受影响代码符号 (Symbols)">
                  <a-table
                    :data-source="currentReport?.affected_symbols || []"
                    :columns="symbolColumns"
                    row-key="symbol_id"
                    size="small"
                    :pagination="{ pageSize: 5 }"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.key === 'symbol_name'">
                        <div class="symbol-name-cell">
                          <span class="symbol-title font-bold">{{ record.symbol_name }}</span>
                          <small class="symbol-id-sub">{{ record.symbol_id }}</small>
                        </div>
                      </template>
                      <template v-else-if="column.key === 'symbol_type'">
                        <a-tag :color="getSymbolTypeColor(record.symbol_type)">
                          {{ record.symbol_type }}
                        </a-tag>
                      </template>
                      <template v-else-if="column.key === 'lines'">
                        <span class="mono-text">L{{ record.start_line }}-L{{ record.end_line }}</span>
                      </template>
                      <template v-else-if="column.key === 'changed_lines'">
                        <a-space :size="2" wrap>
                          <a-tag v-for="ln in record.changed_lines.slice(0, 3)" :key="ln" size="small" color="blue">
                            +{{ ln }}
                          </a-tag>
                          <span v-if="record.changed_lines.length > 3" class="more-tag">
                            +{{ record.changed_lines.length - 3 }}
                          </span>
                        </a-space>
                      </template>
                      <template v-else-if="column.key === 'change_kind'">
                        <a-tag :color="record.change_kind === 'ADDED' ? 'success' : 'processing'">
                          {{ record.change_kind }}
                        </a-tag>
                      </template>
                    </template>
                  </a-table>
                </a-tab-pane>

                <!-- Tab 2: 受波及 API 路由端点 -->
                <a-tab-pane key="routes" tab="受波及 API 端点 (Routes)">
                  <a-table
                    :data-source="currentReport?.affected_routes || []"
                    :columns="routeColumns"
                    row-key="symbol_id"
                    size="small"
                    :pagination="{ pageSize: 5 }"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.key === 'route'">
                        <div class="route-cell">
                          <a-tag :color="getRouteMethodColor(record.route_method)">
                            {{ record.route_method }}
                          </a-tag>
                          <span class="route-path mono-text font-bold">{{ record.route_path }}</span>
                        </div>
                      </template>
                      <template v-else-if="column.key === 'handler'">
                        <span class="mono-text">{{ record.handler_function }}</span>
                      </template>
                      <template v-else-if="column.key === 'file_path'">
                        <small class="mono-text">{{ record.file_path }}</small>
                      </template>
                      <template v-else-if="column.key === 'changed_lines_count'">
                        <a-tag color="orange">{{ record.changed_lines_count }} 行变动</a-tag>
                      </template>
                    </template>
                  </a-table>
                </a-tab-pane>

                <!-- Tab 3: 变更文件清单 -->
                <a-tab-pane key="files" tab="变更文件清单 (Files)">
                  <a-table
                    :data-source="currentReport?.changed_files || []"
                    :columns="fileColumns"
                    row-key="file_path"
                    size="small"
                    :pagination="{ pageSize: 5 }"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.key === 'file_path'">
                        <span class="mono-text font-bold">{{ record.file_path }}</span>
                      </template>
                      <template v-else-if="column.key === 'added'">
                        <span class="mono-text text-success">+{{ record.added_lines_count }}</span>
                      </template>
                      <template v-else-if="column.key === 'deleted'">
                        <span class="mono-text text-danger">-{{ record.deleted_lines_count }}</span>
                      </template>
                    </template>
                  </a-table>
                </a-tab-pane>
              </a-tabs>
            </a-card>
          </div>
        </div>
      </a-spin>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CodeOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type DiffAstAnalysisReportItem,
} from '@/api/ciImpact'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const loading = ref(false)
const analyzing = ref(false)
const historyReports = ref<DiffAstAnalysisReportItem[]>([])
const selectedReportId = ref<string | undefined>(undefined)
const currentReport = ref<DiffAstAnalysisReportItem | null>(null)
const activeTab = ref<'symbols' | 'routes' | 'files'>('symbols')

// 示例 Diff 与代码
const SAMPLE_ORDERS_DIFF = `diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -8,4 +8,6 @@ def calculate_discount(price: float) -> float:
+    if price > 1000:
+        return price * 0.8
     return price * 0.95
@@ -19,4 +21,6 @@ class OrderService:
     def checkout(self, user_id: int) -> bool:
+        # Added fraud detection check
+        logger.info("Checking fraud for user %s", user_id)
         return True
`

const SAMPLE_ORDERS_CODE = `# Orders module
from fastapi import APIRouter
router = APIRouter()

def helper_init():
    pass

def calculate_discount(price: float) -> float:
    if price > 1000:
        return price * 0.8
    return price * 0.95

def unused_func():
    return 1

class OrderService:
    def __init__(self):
        pass

    def checkout(self, user_id: int) -> bool:
        # Added fraud detection check
        logger.info("Checking fraud for user %s", user_id)
        return True

@router.post("/api/v1/orders/create")
async def create_order_endpoint(payload: dict):
    return {"status": "created"}
`

const SAMPLE_AUTH_DIFF = `diff --git a/app/api/auth.py b/app/api/auth.py
--- a/app/api/auth.py
+++ b/app/api/auth.py
@@ -5,3 +5,4 @@
 @router.post("/api/v1/auth/token")
 async def login_endpoint(form: dict):
+    logger.info("Audit login attempt")
     return {"token": "jwt_token_123"}
`

const SAMPLE_AUTH_CODE = `from fastapi import APIRouter
router = APIRouter()

@router.post("/api/v1/auth/token")
async def login_endpoint(form: dict):
    logger.info("Audit login attempt")
    return {"token": "jwt_token_123"}
`

const diffInputText = ref<string>(SAMPLE_ORDERS_DIFF)
const currentSourceCodeMap = ref<Record<string, string>>({
  'app/api/orders.py': SAMPLE_ORDERS_CODE,
  'app/api/auth.py': SAMPLE_AUTH_CODE,
})

const diffLineCount = computed(() => {
  if (!diffInputText.value) return 0
  return diffInputText.value.split('\n').length
})

const historyOptions = computed(() =>
  historyReports.value.map((r) => ({
    label: `${r.analysis_id} (${r.diff_summary?.total_files_changed} 文件 · ${r.diff_summary?.affected_symbols_count} 符号)`,
    value: r.analysis_id,
  }))
)

const symbolColumns = [
  { title: '代码符号名与路径', key: 'symbol_name', width: 220 },
  { title: '类型', key: 'symbol_type', width: 110 },
  { title: 'AST 跨行', key: 'lines', width: 90 },
  { title: '变更物理行', key: 'changed_lines', width: 120 },
  { title: '变更性质', key: 'change_kind', width: 90 },
]

const routeColumns = [
  { title: 'API 路由方法与路径', key: 'route', width: 260 },
  { title: '处理函数', key: 'handler', width: 140 },
  { title: '所属源码文件', key: 'file_path', width: 150 },
  { title: '变更行数', key: 'changed_lines_count', width: 100 },
]

const fileColumns = [
  { title: '文件路径', key: 'file_path' },
  { title: '新增行', key: 'added', width: 90 },
  { title: '删除行', key: 'deleted', width: 90 },
]

function getSymbolTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case 'class':
      return 'purple'
    case 'function':
      return 'blue'
    case 'method':
      return 'cyan'
    case 'route_endpoint':
      return 'green'
    default:
      return 'default'
  }
}

function getRouteMethodColor(method?: string): string {
  switch (method?.toUpperCase()) {
    case 'GET':
      return 'blue'
    case 'POST':
      return 'green'
    case 'PUT':
      return 'orange'
    case 'DELETE':
      return 'red'
    default:
      return 'default'
  }
}

function loadSampleDiff(type: 'orders' | 'auth') {
  if (type === 'orders') {
    diffInputText.value = SAMPLE_ORDERS_DIFF
  } else {
    diffInputText.value = SAMPLE_AUTH_DIFF
  }
  handleRunAnalyze()
}

async function loadReports() {
  loading.value = true
  try {
    const res = await ciImpactApi.listDiffAstReports()
    historyReports.value = res.reports || []
    if (historyReports.value.length > 0) {
      if (!selectedReportId.value || !historyReports.value.some((r) => r.analysis_id === selectedReportId.value)) {
        selectedReportId.value = historyReports.value[0].analysis_id
      }
      currentReport.value = historyReports.value[0]
    } else {
      await handleRunAnalyze()
    }
  } catch (err: any) {
    message.error(`加载 Diff 报告失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function handleRunAnalyze() {
  analyzing.value = true
  try {
    const res = await ciImpactApi.analyzeDiffAst({
      diff_text: diffInputText.value,
      file_sources: currentSourceCodeMap.value,
    })
    message.success(res.message || 'Diff AST 解析完成')
    currentReport.value = res.report
    selectedReportId.value = res.report.analysis_id

    // 重新加载历史
    const listRes = await ciImpactApi.listDiffAstReports()
    historyReports.value = listRes.reports || []
  } catch (err: any) {
    message.error(`AST 解析失败: ${err.message || err}`)
  } finally {
    analyzing.value = false
  }
}

async function handleSelectHistory(val: any) {
  if (!val) return
  loading.value = true
  try {
    const r = await ciImpactApi.getDiffAstReport(String(val))
    currentReport.value = r
  } catch (err: any) {
    message.error(`获取报告详情失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      loadReports()
    }
  }
)

onMounted(() => {
  if (props.open) {
    loadReports()
  }
})
</script>

<style scoped>
.git-diff-ast-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.banner-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 24px;
  color: #6366f1;
  margin-top: 2px;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
}

.highlight-card-purple {
  background: #faf5ff;
  border-color: #d8b4fe;
}

.highlight-card-blue {
  background: #eff6ff;
  border-color: #93c5fd;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.kpi-num {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
}

.kpi-sub {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
}

.text-success {
  color: #10b981 !important;
}

.text-danger {
  color: #ef4444 !important;
}

.text-purple {
  color: #8b5cf6 !important;
}

.text-blue {
  color: #2563eb !important;
}

/* 双栏布局 */
.diff-viewer-grid {
  display: grid;
  grid-template-columns: 460px 1fr;
  gap: 14px;
}

.diff-editor-col {
  display: flex;
  flex-direction: column;
}

.col-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.col-title {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.diff-textarea {
  font-family: monospace;
  font-size: 11px;
  background: #0f172a;
  color: #38bdf8;
  border-radius: 6px;
  padding: 8px;
}

.ast-tabs-card {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.symbol-name-cell {
  display: flex;
  flex-direction: column;
}

.symbol-title {
  font-size: 12px;
  color: #0f172a;
}

.symbol-id-sub {
  font-family: monospace;
  font-size: 10px;
  color: #94a3b8;
}

.route-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.route-path {
  font-size: 11px;
  color: #1e293b;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.font-bold {
  font-weight: 700;
}

.more-tag {
  font-size: 10px;
  color: #94a3b8;
}
</style>
