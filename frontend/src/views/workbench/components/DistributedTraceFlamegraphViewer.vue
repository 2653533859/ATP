<template>
  <div class="distributed-trace-flamegraph-viewer">
    <!-- 头部工具栏 -->
    <header class="viewer-header">
      <div class="header-left">
        <div class="header-icon-box">
          <ApartmentOutlined class="header-icon" />
        </div>
        <div>
          <div class="header-title-row">
            <h3 class="header-title">分布式追踪 TraceID 慢调用火焰图分析</h3>
            <a-tag color="processing">OpenTelemetry / Jaeger</a-tag>
          </div>
          <p class="header-desc">
            跨微服务解析父子调用依赖树、计算自身独占耗时 (Self-Time)，自动高亮长耗时慢调用节点并推导全链路性能瓶颈。
          </p>
        </div>
      </div>

      <div class="header-right">
        <a-space>
          <a-select
            v-model:value="selectedTraceId"
            style="width: 260px"
            size="small"
            placeholder="选择 TraceID 调用链"
            :options="traceOptions"
            @change="handleSelectTrace"
          />
          <a-button size="small" :loading="loading" @click="loadTraces">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" type="primary" ghost @click="handleIngestDemo">
            <FireOutlined /> 摄入仿真全链路 Trace
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <template v-if="currentTrace">
        <!-- 核心链路指标与瓶颈诊断横幅 -->
        <div class="trace-overview-banner" :class="{ 'banner-has-slow': currentTrace.slow_spans_count > 0 }">
          <div class="overview-left">
            <div class="duration-box">
              <span class="duration-num">{{ currentTrace.total_duration_ms }}</span>
              <span class="duration-unit">ms</span>
              <span class="duration-lbl">全链路总时延</span>
            </div>
            <div class="overview-info">
              <div class="root-title">
                <span class="root-tag">ROOT</span>
                <code>{{ currentTrace.root_service }} :: {{ currentTrace.root_operation }}</code>
              </div>
              <div class="bottleneck-text">
                <AlertOutlined v-if="currentTrace.slow_spans_count" class="alert-icon" />
                <CheckCircleOutlined v-else class="success-icon" />
                <span>{{ currentTrace.bottleneck_summary }}</span>
              </div>
              <div class="services-badge-row">
                <span class="services-lbl">涉及微服务 ({{ currentTrace.services_involved.length }}):</span>
                <a-tag
                  v-for="svc in currentTrace.services_involved"
                  :key="svc"
                  size="small"
                  :color="getServiceColor(svc)"
                >
                  {{ svc }}
                </a-tag>
              </div>
            </div>
          </div>

          <div class="overview-right-kpi">
            <div class="mini-kpi">
              <span class="mini-kpi-lbl">Span 节点总数</span>
              <span class="mini-kpi-val">{{ currentTrace.total_spans_count }}</span>
            </div>
            <div class="mini-kpi">
              <span class="mini-kpi-lbl">慢调用 (Slow)</span>
              <span class="mini-kpi-val" :class="currentTrace.slow_spans_count ? 'text-critical' : 'text-success'">
                {{ currentTrace.slow_spans_count }}
              </span>
            </div>
          </div>
        </div>

        <!-- 选项卡：火焰图甘特视图 vs 调用树表格 vs 慢调用排行 -->
        <a-card size="small" class="trace-content-card" :bordered="false">
          <a-tabs v-model:activeKey="activeTab">
            <!-- 标签页 1：阶梯火焰图 (Flamegraph Stepped Gantt View) -->
            <a-tab-pane key="flamegraph" tab="全链路阶梯火焰图 (Flamegraph View)">
              <div class="flamegraph-toolbar">
                <div class="timeline-indicator">
                  <span>0 ms</span>
                  <span class="timeline-axis-line" />
                  <span>{{ currentTrace.total_duration_ms }} ms</span>
                </div>
                <div class="flamegraph-legend">
                  <span class="legend-item"><span class="legend-dot slow-dot" /> 慢调用瓶颈 (&gt;100ms)</span>
                  <span class="legend-item"><span class="legend-dot normal-dot" /> 正常节点</span>
                </div>
              </div>

              <!-- 火焰图层级行容器 -->
              <div class="flamegraph-canvas">
                <div
                  v-for="(levelNodes, depth) in flamegraphLevels"
                  :key="depth"
                  class="flamegraph-depth-row"
                >
                  <div
                    v-for="node in levelNodes"
                    :key="node.span_id"
                    class="flame-block"
                    :class="{ 'flame-block-slow': node.is_slow, 'flame-block-active': selectedSpanId === node.span_id }"
                    :style="getBlockStyle(node)"
                    @click="handleSelectSpan(node.span_id)"
                  >
                    <div class="flame-block-content" :title="`${node.service_name} : ${node.name} (${node.duration_ms}ms)`">
                      <FireOutlined v-if="node.is_slow" class="flame-icon" />
                      <span class="block-title">{{ node.name }}</span>
                      <span class="block-time">{{ node.duration_ms }}ms</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 选中的 Span 详情剖析微卡片 -->
              <div v-if="selectedSpan" class="span-detail-drawer">
                <div class="span-detail-header">
                  <span class="span-service-tag" :style="{ backgroundColor: getServiceColor(selectedSpan.service_name) }">
                    {{ selectedSpan.service_name }}
                  </span>
                  <span class="span-op-name">{{ selectedSpan.operation_name }}</span>
                  <a-tag v-if="selectedSpan.is_slow" color="error">慢调用</a-tag>
                  <a-tag :color="selectedSpan.status === 'OK' ? 'success' : 'error'">{{ selectedSpan.status }}</a-tag>
                </div>
                <div class="span-metrics-grid">
                  <div class="span-stat">
                    <span class="stat-lbl">Span ID</span>
                    <span class="stat-val mono">{{ selectedSpan.span_id }}</span>
                  </div>
                  <div class="span-stat">
                    <span class="stat-lbl">总执行耗时</span>
                    <span class="stat-val mono text-primary">{{ selectedSpan.duration_ms }} ms</span>
                  </div>
                  <div class="span-stat">
                    <span class="stat-lbl">独占耗时 (Self-Time)</span>
                    <span class="stat-val mono text-accent">{{ selectedSpan.self_time_ms }} ms</span>
                  </div>
                  <div class="span-stat">
                    <span class="stat-lbl">耗时占总链路</span>
                    <span class="stat-val mono">
                      {{ Math.round((selectedSpan.duration_ms / currentTrace.total_duration_ms) * 100) }}%
                    </span>
                  </div>
                </div>
              </div>
            </a-tab-pane>

            <!-- 标签页 2：调用树表格 (Hierarchical Span Tree) -->
            <a-tab-pane key="tree" tab="调用树明细与独占耗时 (Span Tree)">
              <a-table
                :data-source="spanTreeData"
                :columns="treeColumns"
                row-key="span_id"
                size="small"
                :default-expand-all-rows="true"
                :pagination="false"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'operation_name'">
                    <span class="tree-op-cell">
                      <a-tag :color="getServiceColor(record.service_name)" size="small">
                        {{ record.service_name }}
                      </a-tag>
                      <strong class="op-title">{{ record.operation_name }}</strong>
                      <a-tag v-if="record.is_slow" color="error" size="small">慢调用</a-tag>
                    </span>
                  </template>
                  <template v-else-if="column.key === 'duration_ms'">
                    <span class="mono-text" :class="{ 'text-critical': record.is_slow }">
                      {{ record.duration_ms }} ms
                    </span>
                  </template>
                  <template v-else-if="column.key === 'self_time_ms'">
                    <span class="mono-text text-accent">{{ record.self_time_ms }} ms</span>
                  </template>
                  <template v-else-if="column.key === 'ratio'">
                    <a-progress
                      :percent="Math.min(100, Math.round((record.duration_ms / currentTrace.total_duration_ms) * 100))"
                      size="small"
                      :stroke-color="record.is_slow ? '#ef4444' : '#6366f1'"
                    />
                  </template>
                  <template v-else-if="column.key === 'status'">
                    <a-tag :color="record.status === 'OK' ? 'success' : 'error'">{{ record.status }}</a-tag>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>

            <!-- 标签页 3：慢调用排行 (Top Slow Spans) -->
            <a-tab-pane key="slow_spans" tab="慢调用瓶颈排行 (Bottlenecks)">
              <a-table
                :data-source="currentTrace.slow_spans || []"
                :columns="slowColumns"
                row-key="span_id"
                size="small"
                :pagination="false"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'service_name'">
                    <a-tag :color="getServiceColor(record.service_name)">{{ record.service_name }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'operation_name'">
                    <span class="mono-text font-bold">{{ record.operation_name }}</span>
                  </template>
                  <template v-else-if="column.key === 'duration_ms'">
                    <span class="mono-text text-critical font-bold">{{ record.duration_ms }} ms</span>
                  </template>
                  <template v-else-if="column.key === 'self_time_ms'">
                    <span class="mono-text text-accent font-bold">{{ record.self_time_ms }} ms</span>
                  </template>
                  <template v-else-if="column.key === 'advice'">
                    <span class="advice-text">
                      {{ getSlowSpanAdvice(record) }}
                    </span>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </template>

      <a-empty v-else description="暂无选中的分布式追踪报告，请在右上角选择 TraceID 或点击「摄入仿真全链路 Trace」" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ReloadOutlined,
  FireOutlined,
  AlertOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  distributedTracesApi,
  type TraceTreeReportItem,
  type DistributedSpanItem,
  type FlamegraphNodeItem,
} from '@/api/distributedTraces'

const loading = ref(false)
const traces = ref<TraceTreeReportItem[]>([])
const selectedTraceId = ref<string | undefined>(undefined)
const currentTrace = ref<TraceTreeReportItem | null>(null)
const activeTab = ref<'flamegraph' | 'tree' | 'slow_spans'>('flamegraph')
const selectedSpanId = ref<string | null>(null)

const traceOptions = computed(() =>
  traces.value.map((t) => ({
    label: `${t.trace_id} (${t.root_service} · ${t.total_duration_ms}ms)`,
    value: t.trace_id,
  }))
)

const selectedSpan = computed<DistributedSpanItem | null>(() => {
  if (!selectedSpanId.value || !currentTrace.value) return null
  return (currentTrace.value.spans_flat.find((s) => s.span_id === selectedSpanId.value) as DistributedSpanItem) || null
})

// 将火焰图递归树展平为按深度（层级）分布的二维数组，用于渲染火焰图阶梯条
const flamegraphLevels = computed(() => {
  if (!currentTrace.value) return []
  const levels: FlamegraphNodeItem[][] = []

  function walk(node: FlamegraphNodeItem, depth: number) {
    if (!levels[depth]) levels[depth] = []
    levels[depth].push(node)
    for (const child of node.children || []) {
      walk(child, depth + 1)
    }
  }

  walk(currentTrace.value.flamegraph_root, 0)
  return levels
})

// 为树形表格组装数据源
const spanTreeData = computed(() => {
  if (!currentTrace.value) return []
  const map = new Map<string, any>()
  const roots: any[] = []

  for (const span of currentTrace.value.spans_flat) {
    map.set(span.span_id, { ...span, children: [] })
  }

  for (const span of currentTrace.value.spans_flat) {
    const node = map.get(span.span_id)
    if (span.parent_span_id && map.has(span.parent_span_id)) {
      map.get(span.parent_span_id).children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
})

const treeColumns = [
  { title: '微服务与调用操作', key: 'operation_name', width: 340 },
  { title: '总耗时', key: 'duration_ms', width: 110 },
  { title: '自身独占耗时 (Self-Time)', key: 'self_time_ms', width: 170 },
  { title: '占链路时延比', key: 'ratio', width: 140 },
  { title: '状态', key: 'status', width: 90 },
]

const slowColumns = [
  { title: '微服务', key: 'service_name', width: 150 },
  { title: '慢调用操作', key: 'operation_name', width: 220 },
  { title: '总时延 (ms)', key: 'duration_ms', width: 110 },
  { title: '独占耗时 (Self-Time)', key: 'self_time_ms', width: 170 },
  { title: '性能调优诊断建议', key: 'advice' },
]

function getServiceColor(serviceName: string): string {
  const hash = serviceName.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  const colors = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#06b6d4', '#ec4899', '#6366f1']
  return colors[hash % colors.length]
}

function getBlockStyle(node: FlamegraphNodeItem) {
  if (!currentTrace.value) return {}
  const total = currentTrace.value.total_duration_ms || 1
  const widthPct = Math.max(8, Math.min(100, (node.duration_ms / total) * 100))

  return {
    width: `${widthPct}%`,
    backgroundColor: node.is_slow ? '#fee2e2' : getServiceColor(node.service_name),
    color: node.is_slow ? '#b91c1c' : '#ffffff',
    borderColor: node.is_slow ? '#ef4444' : 'transparent',
  }
}

function getSlowSpanAdvice(span: any): string {
  if ((span?.self_time_ms || 0) > 100) {
    return '该节点自身内部运算耗时高，建议排查高频 CPU 密集循环、大批量内存反序列化或本地磁盘 I/O 阻塞。'
  }
  return '该节点下游存在耗时累加效应，建议对下游依赖接口引入异步非阻塞调用、分布式并发聚合或 Redis 二级缓存。'
}

function handleSelectSpan(spanId: string) {
  selectedSpanId.value = spanId
}

async function loadTraces() {
  loading.value = true
  try {
    const res = await distributedTracesApi.listTraces()
    traces.value = res.traces || []
    if (traces.value.length > 0) {
      if (!selectedTraceId.value || !traces.value.some((t) => t.trace_id === selectedTraceId.value)) {
        selectedTraceId.value = traces.value[0].trace_id
      }
      await loadTraceDetail(selectedTraceId.value)
    } else {
      currentTrace.value = null
    }
  } catch (err: any) {
    message.error(`加载 Trace 列表失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function loadTraceDetail(traceId: string) {
  try {
    const report = await distributedTracesApi.getTrace(traceId)
    currentTrace.value = report
    if (report.spans_flat.length > 0 && !selectedSpanId.value) {
      selectedSpanId.value = report.spans_flat[0].span_id
    }
  } catch (err: any) {
    message.error(`获取 Trace 报告失败: ${err.message || err}`)
  }
}

function handleSelectTrace(val: any) {
  if (!val) return
  const tid = String(val)
  selectedTraceId.value = tid
  loadTraceDetail(tid)
}

async function handleIngestDemo() {
  const tid = `trace_demo_${Date.now().toString().slice(-6)}`
  const baseTime = Date.now() * 1000

  // 构造标准 OpenTelemetry 树状 Spans 链路
  const demoSpans = [
    {
      span_id: `${tid}_root`,
      parent_span_id: null,
      service_name: 'api-gateway',
      operation_name: 'HTTP POST /api/v1/orders/checkout',
      kind: 'SERVER',
      start_time_us: baseTime,
      duration_us: 1450000, // 1450ms
      status: 'OK',
    },
    {
      span_id: `${tid}_auth`,
      parent_span_id: `${tid}_root`,
      service_name: 'auth-service',
      operation_name: 'verify_token_jwt',
      kind: 'INTERNAL',
      start_time_us: baseTime + 10000,
      duration_us: 35000, // 35ms
      status: 'OK',
    },
    {
      span_id: `${tid}_order`,
      parent_span_id: `${tid}_root`,
      service_name: 'order-service',
      operation_name: 'create_order_entity',
      kind: 'SERVER',
      start_time_us: baseTime + 50000,
      duration_us: 1380000, // 1380ms
      status: 'OK',
    },
    {
      span_id: `${tid}_pay_client`,
      parent_span_id: `${tid}_order`,
      service_name: 'order-service',
      operation_name: 'RPC CALL payment-service::process_card',
      kind: 'CLIENT',
      start_time_us: baseTime + 120000,
      duration_us: 1250000, // 1250ms (慢调用)
      status: 'OK',
    },
    {
      span_id: `${tid}_pay_server`,
      parent_span_id: `${tid}_pay_client`,
      service_name: 'payment-service',
      operation_name: 'process_card_third_party',
      kind: 'SERVER',
      start_time_us: baseTime + 140000,
      duration_us: 1220000, // 1220ms
      status: 'OK',
    },
    {
      span_id: `${tid}_db_order`,
      parent_span_id: `${tid}_order`,
      service_name: 'order-service',
      operation_name: 'SQL INSERT INTO orders',
      kind: 'CLIENT',
      start_time_us: baseTime + 1380000,
      duration_us: 45000, // 45ms
      status: 'OK',
    },
  ]

  try {
    const res = await distributedTracesApi.ingestTrace({
      trace_id: tid,
      spans: demoSpans,
      slow_span_threshold_ms: 100.0,
    })
    message.success(res.message || '仿真分布式 Trace 摄入成功')
    selectedTraceId.value = tid
    await loadTraces()
  } catch (err: any) {
    message.error(`摄入 Trace 失败: ${err.message || err}`)
  }
}

onMounted(() => {
  loadTraces()
})
</script>

<style scoped>
.distributed-trace-flamegraph-viewer {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}

.viewer-header {
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
  background: #eff6ff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-icon {
  font-size: 18px;
  color: #3b82f6;
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

/* 链路概览横幅 */
.trace-overview-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 16px;
}

.banner-has-slow {
  background: #fff1f2;
  border-color: #fecaca;
}

.overview-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.duration-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-right: 20px;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}

.duration-num {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}

.duration-unit {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.duration-lbl {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 2px;
}

.overview-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.root-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.root-tag {
  background: #e0e7ff;
  color: #4338ca;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 4px;
}

.root-title code {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.bottleneck-text {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #475569;
}

.alert-icon {
  color: #ef4444;
}

.success-icon {
  color: #10b981;
}

.services-badge-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.services-lbl {
  font-size: 11px;
  color: #64748b;
}

.overview-right-kpi {
  display: flex;
  gap: 16px;
}

.mini-kpi {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.mini-kpi-lbl {
  font-size: 11px;
  color: #64748b;
}

.mini-kpi-val {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

/* 火焰图画布 */
.trace-content-card {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
}

.flamegraph-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.timeline-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: monospace;
  font-size: 11px;
  color: #64748b;
  flex: 1;
  max-width: 480px;
}

.timeline-axis-line {
  flex: 1;
  height: 1px;
  background: #cbd5e1;
}

.flamegraph-legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #64748b;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.slow-dot {
  background: #ef4444;
}

.normal-dot {
  background: #3b82f6;
}

.flamegraph-canvas {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  min-height: 220px;
}

.flamegraph-depth-row {
  display: flex;
  gap: 4px;
}

.flame-block {
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
  overflow: hidden;
  border: 1px solid transparent;
  user-select: none;
}

.flame-block:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}

.flame-block-active {
  box-shadow: 0 0 0 2px #2563eb !important;
}

.flame-block-slow {
  border-color: #ef4444 !important;
  font-weight: 600;
}

.flame-block-content {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
}

.flame-icon {
  color: #ef4444;
}

.block-title {
  overflow: hidden;
  text-overflow: ellipsis;
}

.block-time {
  font-family: monospace;
  font-size: 10px;
  opacity: 0.9;
  margin-left: auto;
}

/* 选中 Span 剖析抽屉卡片 */
.span-detail-drawer {
  margin-top: 12px;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.span-detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.span-service-tag {
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.span-op-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.span-metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.span-stat {
  display: flex;
  flex-direction: column;
}

.stat-lbl {
  font-size: 11px;
  color: #64748b;
}

.stat-val {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.mono {
  font-family: monospace;
}

.tree-op-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.op-title {
  font-size: 12px;
  color: #1e293b;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.font-bold {
  font-weight: 700;
}

.advice-text {
  font-size: 11px;
  color: #334155;
  line-height: 1.4;
}

.text-critical {
  color: #ef4444 !important;
}

.text-success {
  color: #10b981 !important;
}

.text-primary {
  color: #3b82f6 !important;
}

.text-accent {
  color: #8b5cf6 !important;
}
</style>
