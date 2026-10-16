<template>
  <div class="page-shell flamegraph-dashboard-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <FireOutlined class="hero-icon" />
          <h2 class="page-title">跨微服务关键路径时延分析与火焰图性能瓶颈大盘</h2>
        </div>
        <p class="page-subtitle">
          基于最长依赖路径动态规划算法精准识别端到端最慢关键执行路径（Critical Path），剔除并发旁路干扰，分层渲染交互式性能火焰图，深度诊断数据库慢 SQL、外部网络调用与密集计算瓶颈。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button type="primary" :loading="analyzing" @click="handleRunAnalysis">
            <ThunderboltOutlined /> 立即执行关键路径与火焰图分析
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 参数配置与快速演练预设 -->
    <a-card size="small" class="control-card">
      <div class="control-grid">
        <div class="config-row">
          <span class="cfg-label">链路 Trace ID:</span>
          <a-input
            v-model:value="currentTraceId"
            placeholder="例如: trace_parallel_checkout_101"
            style="width: 320px"
            size="small"
          />

          <span class="cfg-label">分析模式:</span>
          <a-tag color="blue">动态规划最长依赖路径 (Critical Path)</a-tag>
        </div>

        <div class="preset-row">
          <span class="preset-label">典型性能瓶颈演练场景:</span>
          <a-space :size="8" wrap>
            <a-button
              size="small"
              :type="presetKey === 'external' ? 'primary' : 'default'"
              danger
              @click="applyPreset('external')"
            >
              场景 1: 外部支付网关高时延瓶颈 (EXTERNAL_HTTP_LATENCY 300ms)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'database' ? 'primary' : 'default'"
              @click="applyPreset('database')"
            >
              场景 2: 数据库行锁慢 SQL 瓶颈 (DATABASE_SLOW_QUERY 250ms)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'compute' ? 'primary' : 'default'"
              @click="applyPreset('compute')"
            >
              场景 3: 内部密集计算递归瓶颈 (INTERNAL_COMPUTATION 180ms)
            </a-button>
          </a-space>
        </div>
      </div>
    </a-card>

    <!-- 首要瓶颈裁决大横幅 (Bottleneck Verdict Banner) -->
    <div v-if="report && report.primary_bottleneck" class="verdict-banner" :class="`banner-cat-${report.primary_bottleneck.bottleneck_category.toLowerCase()}`">
      <div class="verdict-head">
        <div class="verdict-title-box">
          <span class="cat-badge" :class="`badge-${report.primary_bottleneck.bottleneck_category.toLowerCase()}`">
            {{ report.primary_bottleneck.bottleneck_category }}
          </span>
          <span class="verdict-summary-text">{{ report.diagnosis_summary }}</span>
        </div>
        <div class="meta-box">
          <span>Trace ID: <code>{{ report.trace_id }}</code></span>
        </div>
      </div>

      <!-- 3 大核心指标 KPI 卡片 -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-val text-red">{{ report.critical_path_duration_ms }} ms</div>
          <div class="kpi-lbl">关键路径决定性总耗时</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-orange">{{ report.primary_bottleneck.self_time_ms }} ms</div>
          <div class="kpi-lbl">首要瓶颈自身独占耗时 (Self-Time)</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-purple">{{ report.primary_bottleneck.critical_path_ratio_pct }}%</div>
          <div class="kpi-lbl">瓶颈对关键路径耗时贡献率</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-blue">{{ report.critical_path_spans_count }} / {{ countAllNodes(report.flamegraph_root) }}</div>
          <div class="kpi-lbl">关键路径 Span 节点数 / 全链路总数</div>
        </div>
      </div>
    </div>

    <!-- 交互式性能火焰图可视化组件 (Interactive Flamegraph Visualizer) -->
    <div v-if="report" class="flamegraph-panel">
      <div class="flame-header">
        <div class="flame-title">
          <FireOutlined style="color: #ea580c" />
          <span>分层性能火焰图 (Interactive Flamegraph)</span>
          <small class="flame-sub">火条宽度代表总耗时占比，高亮红/橙色火条为端到端关键执行路径，带有 ⚠️ 为首要性能瓶颈</small>
        </div>
        <div class="flame-legend">
          <span class="leg-item"><span class="leg-color bg-bottleneck"></span> 首要瓶颈</span>
          <span class="leg-item"><span class="leg-color bg-critical"></span> 关键路径 (Critical Path)</span>
          <span class="leg-item"><span class="leg-color bg-normal"></span> 正常旁路调用</span>
        </div>
      </div>

      <!-- 火焰图层级堆叠渲染 -->
      <div class="flame-container">
        <div
          v-for="(levelNodes, depth) in flameRows"
          :key="depth"
          class="flame-row"
        >
          <div class="row-depth-label">D{{ depth }}</div>
          <div class="row-bars">
            <div
              v-for="node in levelNodes"
              :key="node.span_id"
              class="flame-bar"
              :class="{
                'bar-bottleneck': node.is_bottleneck,
                'bar-critical': node.is_critical_path && !node.is_bottleneck,
                'bar-normal': !node.is_critical_path,
                'bar-active': selectedNode?.span_id === node.span_id,
              }"
              :style="{ width: `${getBarWidthPercent(node.value, report.total_trace_duration_ms)}%` }"
              @click="selectedNode = node"
            >
              <div class="bar-content">
                <span v-if="node.is_bottleneck" class="bn-icon">⚠️</span>
                <span class="bar-svc">[{{ node.service_name }}]</span>
                <span class="bar-name">{{ node.name }}</span>
                <span class="bar-dur">{{ node.value }}ms (独占: {{ node.self_value }}ms)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 选中节点详情抽屉/卡片 -->
      <div v-if="selectedNode" class="node-detail-bar">
        <div class="detail-top">
          <span>已选中火焰条: <strong>{{ selectedNode.service_name }}</strong> - <code>{{ selectedNode.name }}</code> (SpanId: {{ selectedNode.span_id }})</span>
          <a-tag :color="selectedNode.is_bottleneck ? 'red' : selectedNode.is_critical_path ? 'orange' : 'default'">
            {{ selectedNode.is_bottleneck ? '首要性能瓶颈' : selectedNode.is_critical_path ? '关键执行路径' : '普通旁路' }}
          </a-tag>
        </div>
        <div class="detail-grid">
          <div>总持续耗时: <strong>{{ selectedNode.value }} ms</strong></div>
          <div>自身独占耗时 (Self-Time): <strong>{{ selectedNode.self_value }} ms</strong></div>
          <div>判定瓶颈分类: <strong>{{ selectedNode.bottleneck_category || 'NONE' }}</strong></div>
        </div>
      </div>
    </div>

    <!-- 关键路径时序列表与贡献比表格 -->
    <div v-if="report" class="critical-table-section">
      <div class="sec-title">
        <span>关键路径执行序列与时延贡献矩阵 (Critical Path Breakdown)</span>
        <a-tag color="blue">共 {{ report.critical_path.length }} 个关键路径节点</a-tag>
      </div>

      <a-table
        :data-source="report.critical_path"
        :columns="tableColumns"
        row-key="span_id"
        size="small"
        :pagination="false"
        bordered
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'seq'">
            <code>Step {{ index + 1 }}</code>
          </template>

          <template v-if="column.key === 'service_op'">
            <div class="svc-cell">
              <a-tag :color="getServiceTagColor(record.service_name)">{{ record.service_name }}</a-tag>
              <strong>{{ record.name }}</strong>
            </div>
          </template>

          <template v-if="column.key === 'duration'">
            <span>{{ record.duration_ms }} ms</span>
          </template>

          <template v-if="column.key === 'self_time'">
            <span :class="record.is_bottleneck ? 'text-red' : ''">
              <strong>{{ record.self_time_ms }} ms</strong>
            </span>
          </template>

          <template v-if="column.key === 'ratio'">
            <div class="ratio-cell">
              <span>{{ record.critical_path_ratio_pct }}%</span>
              <a-progress
                :percent="record.critical_path_ratio_pct"
                size="small"
                :status="record.is_bottleneck ? 'exception' : 'active'"
              />
            </div>
          </template>

          <template v-if="column.key === 'category'">
            <a-tag :color="getCategoryColor(record.bottleneck_category)">
              {{ record.bottleneck_category }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  FireOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  traceFlamegraphApi,
  type CriticalPathProfileReport,
  type TraceFlamegraphNodeItem,
} from '@/api/traceObservability'

const analyzing = ref(false)
const currentTraceId = ref('trace_parallel_checkout_101')
const report = ref<CriticalPathProfileReport | null>(null)
const selectedNode = ref<TraceFlamegraphNodeItem | null>(null)
const presetKey = ref<'external' | 'database' | 'compute'>('external')

const tableColumns = [
  { title: '依赖时序', key: 'seq', width: 90 },
  { title: '微服务与执行动作', key: 'service_op', width: 340 },
  { title: '总耗时 (ms)', key: 'duration', width: 130 },
  { title: '自身独占耗时 (Self-Time)', key: 'self_time', width: 180 },
  { title: '对关键路径时延贡献比', key: 'ratio', width: 220 },
  { title: '瓶颈类别判定', key: 'category' },
]

function getServiceTagColor(svc: string): string {
  switch (svc) {
    case 'api-gateway': return 'blue'
    case 'order-service': return 'orange'
    case 'pay-service': return 'red'
    case 'user-service': return 'cyan'
    default: return 'geekblue'
  }
}

function getCategoryColor(cat: string): string {
  switch (cat) {
    case 'EXTERNAL_HTTP_LATENCY': return 'red'
    case 'DATABASE_SLOW_QUERY': return 'purple'
    case 'INTERNAL_COMPUTATION': return 'orange'
    case 'QUEUE_LAG': return 'blue'
    default: return 'default'
  }
}

// 预设数据集
const PRESET_SPANS = {
  external: [
    {
      span_id: 's_gw',
      parent_span_id: null,
      name: 'POST /checkout',
      service_name: 'api-gateway',
      duration_ms: 420.0,
      start_time_us: 1000000,
      end_time_us: 1420000,
    },
    {
      span_id: 's_auth',
      parent_span_id: 's_gw',
      name: 'verify_token',
      service_name: 'auth-service',
      duration_ms: 35.0,
      start_time_us: 1010000,
      end_time_us: 1045000,
    },
    {
      span_id: 's_order',
      parent_span_id: 's_gw',
      name: 'create_order_flow',
      service_name: 'order-service',
      duration_ms: 380.0,
      start_time_us: 1020000,
      end_time_us: 1400000,
    },
    {
      span_id: 's_pay',
      parent_span_id: 's_order',
      name: 'call_alipay_gateway',
      service_name: 'pay-service',
      kind: 'CLIENT',
      duration_ms: 300.0,
      start_time_us: 1050000,
      end_time_us: 1350000,
      attributes: { 'http.url': 'https://api.alipay.com/pay', 'http.status_code': 200 },
    },
  ],
  database: [
    {
      span_id: 's_root_user',
      parent_span_id: null,
      name: 'GET /api/v1/users/profile',
      service_name: 'user-service',
      duration_ms: 320.0,
    },
    {
      span_id: 's_sql_slow',
      parent_span_id: 's_root_user',
      name: 'SELECT * FROM users WHERE active = 1',
      service_name: 'user-service',
      duration_ms: 250.0,
      attributes: { 'db.system': 'postgresql', 'db.statement': 'SELECT * FROM users' },
    },
  ],
  compute: [
    {
      span_id: 's_root_calc',
      parent_span_id: null,
      name: 'POST /api/v1/pricing/compute',
      service_name: 'pricing-service',
      duration_ms: 260.0,
    },
    {
      span_id: 's_heavy_calc',
      parent_span_id: 's_root_calc',
      name: 'dynamic_matrix_discount',
      service_name: 'pricing-service',
      kind: 'INTERNAL',
      duration_ms: 180.0,
    },
  ],
}

function applyPreset(key: 'external' | 'database' | 'compute') {
  presetKey.value = key
  currentTraceId.value = `trace_preset_${key}_101`
  handleRunAnalysis()
}

async function handleRunAnalysis() {
  analyzing.value = true
  try {
    const spans = PRESET_SPANS[presetKey.value]
    const res = await traceFlamegraphApi.profileSpans({
      trace_id: currentTraceId.value,
      spans,
    })
    report.value = res
    if (res.flamegraph_root) {
      selectedNode.value = res.primary_bottleneck ? findNodeById(res.flamegraph_root, res.primary_bottleneck.span_id) : res.flamegraph_root
    }
    message.success('关键路径分析与火焰图构建完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

function findNodeById(root: TraceFlamegraphNodeItem, id: string): TraceFlamegraphNodeItem | null {
  if (root.span_id === id) return root
  for (const c of root.children) {
    const f = findNodeById(c, id)
    if (f) return f
  }
  return null
}

function countAllNodes(root: TraceFlamegraphNodeItem): number {
  if (!root) return 0
  let count = 1
  for (const c of root.children) {
    count += countAllNodes(c)
  }
  return count
}

function getBarWidthPercent(val: number, total: number): number {
  if (!total || total <= 0) return 100
  const pct = (val / total) * 100
  return Math.max(8, Math.min(100, pct))
}

// 将树形转换为层级行列表 (行对应 depth: FlamegraphNodeItem[])
const flameRows = computed(() => {
  if (!report.value?.flamegraph_root) return []
  const rows: TraceFlamegraphNodeItem[][] = []

  function _traverse(node: TraceFlamegraphNodeItem, depth: number) {
    if (!rows[depth]) rows[depth] = []
    rows[depth].push(node)
    for (const c of node.children) {
      _traverse(c, depth + 1)
    }
  }

  _traverse(report.value.flamegraph_root, 0)
  return rows
})

onMounted(async () => {
  await handleRunAnalysis()
})
</script>

<style scoped>
.flamegraph-dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
}

.hero-icon {
  font-size: 20px;
  color: #ea580c;
}

.control-card {
  border-radius: 8px;
}

.control-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.cfg-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

/* 裁决横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.banner-cat-external_http_latency {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-cat-database_slow_query {
  background: #faf5ff;
  border-color: #e9d5ff;
}

.banner-cat-internal_computation {
  background: #fff7ed;
  border-color: #fed7aa;
}

.verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.verdict-title-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cat-badge {
  font-size: 13px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.badge-external_http_latency {
  background: #ef4444;
  color: #ffffff;
}

.badge-database_slow_query {
  background: #9333ea;
  color: #ffffff;
}

.badge-internal_computation {
  background: #ea580c;
  color: #ffffff;
}

.verdict-summary-text {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.meta-box {
  font-size: 11px;
  color: #64748b;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  text-align: center;
}

.kpi-val {
  font-size: 20px;
  font-weight: 800;
}

.kpi-lbl {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.text-red {
  color: #dc2626;
}

.text-orange {
  color: #ea580c;
}

.text-purple {
  color: #9333ea;
}

.text-blue {
  color: #0284c7;
}

/* 火焰图面板 */
.flamegraph-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flame-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.flame-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.flame-sub {
  font-size: 11px;
  color: #64748b;
  font-weight: normal;
}

.flame-legend {
  display: flex;
  align-items: center;
  gap: 12px;
}

.leg-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #475569;
}

.leg-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.bg-bottleneck {
  background: #ef4444;
}

.bg-critical {
  background: #f97316;
}

.bg-normal {
  background: #94a3b8;
}

.flame-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: #0f172a;
  border-radius: 6px;
  min-height: 240px;
  overflow-x: auto;
}

.flame-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.row-depth-label {
  font-size: 10px;
  font-family: Consolas, monospace;
  color: #64748b;
  width: 24px;
}

.row-bars {
  display: flex;
  gap: 4px;
  flex: 1;
}

.flame-bar {
  border-radius: 3px;
  padding: 6px 8px;
  cursor: pointer;
  transition: all 0.15s;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.bar-bottleneck {
  background: #ef4444;
  color: #ffffff;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
}

.bar-critical {
  background: #ea580c;
  color: #ffffff;
}

.bar-normal {
  background: #334155;
  color: #cbd5e1;
}

.bar-active {
  outline: 2px solid #38bdf8;
  outline-offset: 1px;
}

.bar-content {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.bar-svc {
  font-weight: 700;
}

.bar-dur {
  font-size: 10px;
  opacity: 0.9;
}

.node-detail-bar {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}

.detail-grid {
  display: flex;
  gap: 20px;
  font-size: 11px;
  color: #475569;
}

.critical-table-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sec-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.svc-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ratio-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}
</style>
