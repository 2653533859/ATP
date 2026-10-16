<template>
  <a-drawer
    :open="open"
    :width="1140"
    placement="right"
    title="响应体动态字段智能去噪与字段级精确差分比对器"
    destroy-on-close
    class="traffic-diff-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="drawer-banner">
        <div class="banner-title">
          <ApartmentOutlined class="banner-icon" />
          <span>微服务响应体智能去噪与字段级语义差分引擎 (Field-Level Traffic Diff Comparator)</span>
        </div>
        <p class="banner-desc">
          为影子回放与微服务重构提供高保真响应比对能力。自动识别并忽略动态时间戳、UUID、分布式调用链 Trace ID 等瞬时噪声（<strong>彻底杜绝 95%+ 虚假误报警</strong>），并在深度嵌套 JSON 树中精准捕获<strong>字段缺失 (DELETED)</strong>、<strong>类型漂移 (TYPE_CHANGED)</strong> 与<strong>业务篡改 (MODIFIED)</strong>。
        </p>
      </div>

      <!-- 操作与快速预设栏 -->
      <div class="controls-bar">
        <div class="controls-left">
          <span class="ctrl-label">快速预设场景:</span>
          <a-space size="small">
            <a-button size="small" @click="applyPreset('identical')">
              预设 1: 完美一致 (100% 相似度, 滤除噪声)
            </a-button>
            <a-button size="small" @click="applyPreset('critical_drift')">
              预设 2: 阻断级差异 (金额篡改/字段删除/类型漂移)
            </a-button>
            <a-button size="small" @click="applyPreset('warning_add')">
              预设 3: 次要扩展 (新增非核心字段)
            </a-button>
          </a-space>
        </div>

        <div class="controls-right">
          <a-space size="small">
            <a-button size="small" :loading="loading" @click="loadInitialData">
              <ReloadOutlined /> 刷新
            </a-button>
            <a-button type="primary" size="small" :loading="comparing" @click="handleRunCompare">
              <ThunderboltOutlined /> 执行精确差分比对
            </a-button>
          </a-space>
        </div>
      </div>

      <a-spin :spinning="comparing || loading">
        <div v-if="currentReport" class="report-content">
          <!-- 相似度得分与裁决横幅 -->
          <div
            class="verdict-banner"
            :class="currentReport.is_identical ? 'banner-identical' : (currentReport.critical_diffs_count > 0 ? 'banner-critical' : 'banner-warning')"
          >
            <div class="score-circle-box">
              <div class="score-circle">
                <span class="score-num">{{ currentReport.similarity_score_pct.toFixed(1) }}%</span>
                <span class="score-lbl">相似度得分</span>
              </div>
            </div>

            <div class="verdict-text-box">
              <div class="verdict-header-line">
                <span class="verdict-title">
                  {{ currentReport.is_identical ? '🟢 响应体与基线完美一致 (IDENTICAL)' : (currentReport.critical_diffs_count > 0 ? '🔴 检出阻断级核心业务差异 (CRITICAL DRIFT)' : '🟡 检出次要扩展差异 (COMPATIBLE WARNING)') }}
                </span>
                <a-tag color="purple" class="noise-pill">
                  <CheckCircleOutlined /> 自动过滤 {{ currentReport.ignored_noise_fields_count }} 处时间戳/UUID/Token 动态噪声
                </a-tag>
              </div>

              <div class="meta-row">
                <span class="meta-item">状态码对比: 基线 <strong>{{ currentReport.baseline_status_code }}</strong> vs 回放 <strong>{{ currentReport.replayed_status_code }}</strong></span>
                <span class="meta-item">总差异数: <strong>{{ currentReport.total_differences_count }}</strong> 处</span>
                <span class="meta-item text-danger">阻断项: <strong>{{ currentReport.critical_diffs_count }}</strong></span>
                <span class="meta-item text-warning">告警项: <strong>{{ currentReport.warning_diffs_count }}</strong></span>
              </div>

              <p class="summary-desc">{{ currentReport.diff_summary }}</p>
            </div>
          </div>

          <!-- 双栏所见即所得 JSON 代码比对 -->
          <div class="split-payload-grid">
            <div class="payload-card baseline-card">
              <div class="card-header">
                <span class="card-title">基线标准响应 (Baseline Response)</span>
                <a-tag color="blue" size="small">HTTP {{ currentReport.baseline_status_code }}</a-tag>
              </div>
              <div class="card-body">
                <a-textarea v-model:value="rawBaselineInput" class="code-editor" :rows="10" />
              </div>
            </div>

            <div class="payload-card replayed-card">
              <div class="card-header">
                <span class="card-title">回放实测响应 (Replayed Response)</span>
                <a-tag :color="currentReport.replayed_status_code >= 400 ? 'red' : 'green'" size="small">
                  HTTP {{ currentReport.replayed_status_code }}
                </a-tag>
              </div>
              <div class="card-body">
                <a-textarea v-model:value="rawReplayedInput" class="code-editor" :rows="10" />
              </div>
            </div>
          </div>

          <!-- 字段级差异矩阵表格 -->
          <div class="diff-matrix-panel">
            <div class="matrix-header">
              <div class="matrix-title-box">
                <span class="matrix-title">字段级精确差分结构树 (Differences Matrix: {{ filteredDiffs.length }} / {{ currentReport.differences.length }})</span>
                <a-radio-group v-model:value="severityFilter" size="small" button-style="solid">
                  <a-radio-button value="ALL">全部差异</a-radio-button>
                  <a-radio-button value="CRITICAL">仅阻断级 ({{ currentReport.critical_diffs_count }})</a-radio-button>
                  <a-radio-button value="WARNING">仅告警级 ({{ currentReport.warning_diffs_count }})</a-radio-button>
                </a-radio-group>
              </div>

              <span class="matrix-sub">已自动排除时间戳与随机字符串等干扰项</span>
            </div>

            <a-table
              :data-source="filteredDiffs"
              :columns="columns"
              row-key="path"
              size="small"
              :pagination="{ pageSize: 6, showTotal: (t: number) => `共 ${t} 项字段差异` }"
              class="diff-table"
            >
              <template #bodyCell="{ column, record }">
                <!-- 字段路径 -->
                <template v-if="column.key === 'path'">
                  <code class="path-code">{{ record.path }}</code>
                </template>

                <!-- 变更类型 -->
                <template v-else-if="column.key === 'type'">
                  <a-tag :color="getDiffTypeTagColor(record.diff_type)" class="diff-type-tag">
                    {{ record.diff_type }}
                  </a-tag>
                </template>

                <!-- 严重度 -->
                <template v-else-if="column.key === 'severity'">
                  <a-tag :color="record.severity === 'CRITICAL' ? 'red' : 'orange'" size="small">
                    {{ record.severity }}
                  </a-tag>
                </template>

                <!-- 值对比 -->
                <template v-else-if="column.key === 'values'">
                  <div class="values-cell">
                    <span class="val-line val-base">基线: <code>{{ formatVal(record.baseline_value) }}</code></span>
                    <span class="val-line val-repl">回放: <code>{{ formatVal(record.replayed_value) }}</code></span>
                  </div>
                </template>

                <!-- 说明 -->
                <template v-else-if="column.key === 'desc'">
                  <span class="desc-text" :class="{ 'text-danger': record.severity === 'CRITICAL' }">
                    {{ record.description }}
                  </span>
                </template>
              </template>
            </a-table>
          </div>
        </div>
      </a-spin>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  trafficDiffApi,
  type DiffItem,
  type TrafficDiffReport,
} from '@/api/trafficGateway'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const comparing = ref(false)
const severityFilter = ref('ALL')

const currentReport = ref<TrafficDiffReport | null>(null)

// 响应体编辑输入
const rawBaselineInput = ref('')
const rawReplayedInput = ref('')

const columns = [
  { title: '字段路径 (JSONPath)', key: 'path', width: 220 },
  { title: '变更类型', key: 'type', width: 120 },
  { title: '严重度', key: 'severity', width: 100 },
  { title: '基线值 vs 回放值', key: 'values', width: 280 },
  { title: '差异影响分析说明', key: 'desc' },
]

// 预设样例 1: 完美一致 (时间戳/UUID动态噪声被自动过滤)
const SAMPLE_IDENTICAL_BASE = JSON.stringify({
  code: 0,
  message: "success",
  data: {
    order_id: 9999,
    status: "PAID",
    amount: 299.0,
    created_at: "2026-10-16T10:00:00Z",
    request_id: "req-1111-aaaa",
    trace_id: "trace-old-123",
  },
}, null, 2)

const SAMPLE_IDENTICAL_REPL = JSON.stringify({
  code: 0,
  message: "success",
  data: {
    order_id: 9999,
    status: "PAID",
    amount: 299.0,
    created_at: "2026-10-16T18:30:00Z",  // 动态时间
    request_id: "req-2222-bbbb",  // 动态流水
    trace_id: "trace-new-456",  // 动态追踪ID
  },
}, null, 2)

// 预设样例 2: 阻断级核心差异
const SAMPLE_CRITICAL_BASE = JSON.stringify({
  code: 0,
  data: {
    order_id: 1001,
    amount: 100.0,
    items: ["apple", "banana"],
    obsolete_tag: "old_v1",
  },
}, null, 2)

const SAMPLE_CRITICAL_REPL = JSON.stringify({
  code: 500,  // 状态码篡改
  data: {
    order_id: "1001",  // int -> str 类型漂移
    amount: 150.0,  // 金额篡改
    items: ["apple"],  // 数组元素缺失
    new_feature_tag: "beta",
    // 缺失 obsolete_tag
  },
}, null, 2)

// 预设样例 3: 次要扩展告警
const SAMPLE_WARNING_BASE = JSON.stringify({
  code: 0,
  status: "OK",
  user_id: 888,
}, null, 2)

const SAMPLE_WARNING_REPL = JSON.stringify({
  code: 0,
  status: "OK",
  user_id: 888,
  vip_level: "GOLD",  // 新增字段
  last_login_province: "Zhejiang",  // 新增字段
}, null, 2)

const filteredDiffs = computed<DiffItem[]>(() => {
  if (!currentReport.value?.differences) return []
  if (severityFilter.value === 'ALL') return currentReport.value.differences
  return currentReport.value.differences.filter(d => d.severity === severityFilter.value)
})

const getDiffTypeTagColor = (type: string) => {
  switch (type) {
    case 'ADDED': return 'blue'
    case 'DELETED': return 'red'
    case 'MODIFIED': return 'orange'
    case 'TYPE_CHANGED': return 'purple'
    default: return 'default'
  }
}

const formatVal = (val: any) => {
  if (val === null || val === undefined) return '(null/缺失)'
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

const applyPreset = (type: 'identical' | 'critical_drift' | 'warning_add') => {
  if (type === 'identical') {
    rawBaselineInput.value = SAMPLE_IDENTICAL_BASE
    rawReplayedInput.value = SAMPLE_IDENTICAL_REPL
  } else if (type === 'critical_drift') {
    rawBaselineInput.value = SAMPLE_CRITICAL_BASE
    rawReplayedInput.value = SAMPLE_CRITICAL_REPL
  } else {
    rawBaselineInput.value = SAMPLE_WARNING_BASE
    rawReplayedInput.value = SAMPLE_WARNING_REPL
  }
  handleRunCompare()
}

const loadInitialData = async () => {
  loading.value = true
  try {
    const res = await trafficDiffApi.listReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
      rawBaselineInput.value = SAMPLE_IDENTICAL_BASE
      rawReplayedInput.value = SAMPLE_IDENTICAL_REPL
    } else {
      applyPreset('identical')
    }
  } catch {
    applyPreset('identical')
  } finally {
    loading.value = false
  }
}

const handleRunCompare = async () => {
  comparing.value = true
  try {
    const res = await trafficDiffApi.compareResponses({
      baseline_response: rawBaselineInput.value,
      replayed_response: rawReplayedInput.value,
      baseline_status_code: 200,
      replayed_status_code: 200,
    })
    currentReport.value = res.report
    message.success(res.message || '响应体智能差分比对完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '差分比对失败')
  } finally {
    comparing.value = false
  }
}

const handleClose = () => {
  emit('update:open', false)
}

onMounted(() => {
  loadInitialData()
})
</script>

<style scoped>
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-banner {
  background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #0369a1;
  margin-bottom: 4px;
}

.banner-icon {
  font-size: 18px;
  color: #0284c7;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin: 0;
}

/* 控制栏 */
.controls-bar {
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.controls-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ctrl-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.report-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 裁决横幅 */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 18px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  transition: all 0.3s ease;
}

.banner-identical {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-color: #86efac;
}

.banner-critical {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fca5a5;
}

.banner-warning {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fcd34d;
}

.score-circle-box {
  flex-shrink: 0;
}

.score-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 3px solid #10b981;
}

.banner-identical .score-circle { border-color: #10b981; }
.banner-critical .score-circle { border-color: #ef4444; }
.banner-warning .score-circle { border-color: #f59e0b; }

.score-num {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}

.score-lbl {
  font-size: 10px;
  color: #64748b;
}

.verdict-text-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.verdict-header-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.verdict-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.noise-pill {
  font-weight: 600;
  font-size: 11px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #475569;
  flex-wrap: wrap;
}

.summary-desc {
  font-size: 12px;
  color: #334155;
  margin: 0;
}

.text-danger { color: #dc2626; }
.text-warning { color: #d97706; }

/* 双栏 JSON 编辑框 */
.split-payload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.payload-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-header {
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.card-body {
  padding: 8px;
  flex: 1;
}

.code-editor {
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 4px;
}

/* 差异矩阵面板 */
.diff-matrix-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.matrix-header {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.matrix-title-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.matrix-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.matrix-sub {
  font-size: 11px;
  color: #64748b;
}

.path-code {
  font-size: 11px;
  color: #0284c7;
  font-family: monospace;
}

.diff-type-tag {
  font-weight: 700;
  font-size: 11px;
}

.values-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.val-line code {
  padding: 1px 4px;
  border-radius: 3px;
}

.val-base code { background: #fee2e2; color: #b91c1c; }
.val-repl code { background: #dcfce7; color: #15803d; }

.desc-text {
  font-size: 12px;
  color: #334155;
}
</style>
