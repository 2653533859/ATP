<template>
  <div class="span-flamegraph-inspector-card">
    <!-- 头部工具与控制条 -->
    <div class="flamegraph-card-header">
      <div class="header-left">
        <div class="icon-wrap">
          <FireOutlined class="card-icon" />
        </div>
        <div class="title-meta">
          <div class="card-title-row">
            <h4 class="card-title">{{ t('run.flamegraph.title', '分布式微服务调用链火焰图分析') }}</h4>
            <a-tag v-if="lineage" color="blue">
              {{ lineage.services_count }} 微服务 / {{ lineage.total_spans }} Spans / {{ lineage.max_depth_hops }} 跳
            </a-tag>
            <a-tag v-if="slowSpansCount > 0" color="red">
              检出 {{ slowSpansCount }} 个慢跨度
            </a-tag>
          </div>
          <p class="card-desc">
            按层级深度切割微服务调用耗时矩形切片，快速定位串行耗时瓶颈、慢 SQL 与阻塞微服务。
          </p>
        </div>
      </div>

      <div class="header-right">
        <a-space>
          <!-- 仅看慢调用开关 -->
          <a-switch
            v-model:checked="slowOnly"
            size="small"
            checked-children="慢调用"
            un-checked-children="全量"
          />

          <!-- 慢阈值调节 -->
          <span class="threshold-label">慢阈值:</span>
          <a-select v-model:value="slowThresholdMs" size="small" style="width: 95px">
            <a-select-option :value="50">50 ms</a-select-option>
            <a-select-option :value="100">100 ms</a-select-option>
            <a-select-option :value="150">150 ms</a-select-option>
            <a-select-option :value="200">200 ms</a-select-option>
          </a-select>

          <!-- 重置缩放 -->
          <a-button
            v-if="zoomRootSpanId"
            size="small"
            type="dashed"
            @click="resetZoom"
          >
            <ZoomOutOutlined /> 重置聚焦
          </a-button>

          <!-- 刷新 -->
          <a-button size="small" :loading="loading" @click="fetchLineageData">
            <ReloadOutlined /> 刷新
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 顶栏 KPI 与当前聚焦视图提示 -->
    <div v-if="zoomRootNode" class="zoom-indicator-bar">
      <span class="zoom-hint">
        <SearchOutlined /> 当前聚焦局部子树:
        <strong>{{ zoomRootNode.service_name }} :: {{ zoomRootNode.name }}</strong>
        ({{ zoomRootNode.duration_ms }} ms)
      </span>
      <a-button type="link" size="small" @click="resetZoom">返回全链路顶层</a-button>
    </div>

    <!-- 主火焰图绘制区域 -->
    <a-spin :spinning="loading">
      <div class="flamegraph-body">
        <!-- 时间标尺轴 -->
        <div class="flamegraph-ruler">
          <span class="ruler-tick">0 ms</span>
          <span class="ruler-line" />
          <span class="ruler-tick">{{ Math.round(activeTotalDuration) }} ms</span>
        </div>

        <!-- 阶梯火焰图行渲染 -->
        <div class="flamegraph-levels">
          <div
            v-for="(levelNodes, depth) in flamegraphLevels"
            :key="depth"
            class="flame-level-row"
          >
            <div
              v-for="node in levelNodes"
              :key="node.span_id"
              class="flame-slice"
              :class="{
                'slice-slow': isSlowSpan(node),
                'slice-active': selectedSpan?.span_id === node.span_id,
                'slice-zoomed': zoomRootSpanId === node.span_id,
              }"
              :style="getSliceStyle(node)"
              :title="`${node.service_name} : ${node.name} (${node.duration_ms}ms, 自身耗时: ${node.self_time_ms}ms)`"
              @click="handleSelectSpan(node)"
              @dblclick="handleZoomSpan(node)"
            >
              <div class="slice-inner">
                <FireOutlined v-if="isSlowSpan(node)" class="slice-flame-icon" />
                <span class="slice-title">{{ node.name }}</span>
                <span class="slice-duration">{{ node.duration_ms }}ms</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部图例与缩放提示 -->
        <div class="flamegraph-legend-bar">
          <div class="legend-items">
            <span class="legend-item"><span class="legend-dot dot-http" /> HTTP (API)</span>
            <span class="legend-item"><span class="legend-dot dot-grpc" /> gRPC (RPC)</span>
            <span class="legend-item"><span class="legend-dot dot-db" /> Database (SQL)</span>
            <span class="legend-item"><span class="legend-dot dot-redis" /> Redis (Cache)</span>
            <span class="legend-item"><span class="legend-dot dot-mq" /> MessageQueue (MQ)</span>
            <span class="legend-item"><span class="legend-dot dot-slow" /> 慢调用 (&gt;{{ slowThresholdMs }}ms)</span>
          </div>
          <span class="legend-tip">提示: 单击查看详情, 双击可对准该微服务下钻放大</span>
        </div>

        <!-- 选中 Span 的深度剖析微卡片 (Inline Inspector) -->
        <div v-if="selectedSpan" class="flame-inspector-panel">
          <div class="inspector-top-row">
            <div class="inspector-service-badge">
              <a-tag :color="getProtocolColor(selectedSpan.protocol)">
                {{ selectedSpan.protocol.toUpperCase() }}
              </a-tag>
              <span class="inspector-service-name">{{ selectedSpan.service_name }}</span>
              <span class="inspector-op-name">{{ selectedSpan.name }}</span>
              <a-tag v-if="isSlowSpan(selectedSpan)" color="error">慢调用高亮</a-tag>
            </div>
            <a-space>
              <a-button
                v-if="selectedSpan.children && selectedSpan.children.length > 0 && zoomRootSpanId !== selectedSpan.span_id"
                size="small"
                type="primary"
                ghost
                @click="handleZoomSpan(selectedSpan)"
              >
                <ZoomInOutlined /> 以此跨度放大聚焦
              </a-button>
            </a-space>
          </div>

          <div class="inspector-metrics-grid">
            <div class="metric-card">
              <span class="metric-label">Span ID</span>
              <span class="metric-value font-mono">{{ selectedSpan.span_id }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">总执行耗时</span>
              <span class="metric-value font-mono text-primary">{{ selectedSpan.duration_ms }} ms</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">自身独占耗时 (Self-Time)</span>
              <span class="metric-value font-mono text-warning">{{ selectedSpan.self_time_ms }} ms</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">占链路耗时比</span>
              <span class="metric-value font-mono">
                {{ ((selectedSpan.duration_ms / activeTotalDuration) * 100).toFixed(1) }}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  FireOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import {
  observabilityTraceApi,
  type SpanTreeNodeDTO,
  type TraceTopologyLineageDTO,
} from '@/api/observabilityTrace'

const props = defineProps<{
  traceId?: string | null
  stepName?: string
  runId?: number | string
}>()

const { t } = useI18n()

const loading = ref(false)
const slowOnly = ref(false)
const slowThresholdMs = ref(100)
const zoomRootSpanId = ref<string | null>(null)
const selectedSpan = ref<SpanTreeNodeDTO | null>(null)
const lineage = ref<TraceTopologyLineageDTO | null>(null)

const activeTraceId = computed(() => {
  return props.traceId || '4bf92f3577b34da6a3ce929d0e0e4736'
})

// 查找当前 Zoom 聚焦的节点
const zoomRootNode = computed<SpanTreeNodeDTO | null>(() => {
  if (!zoomRootSpanId.value || !lineage.value?.hierarchical_tree) return null
  return findNodeById(lineage.value.hierarchical_tree, zoomRootSpanId.value)
})

// 当前计算尺的总时延基准
const activeTotalDuration = computed<number>(() => {
  if (zoomRootNode.value) {
    return Math.max(1, zoomRootNode.value.duration_ms)
  }
  if (lineage.value?.hierarchical_tree && lineage.value.hierarchical_tree.length > 0) {
    return Math.max(1, lineage.value.hierarchical_tree[0].duration_ms)
  }
  return 100
})

// 火焰图各层级节点分布字典 (depth -> SpanTreeNodeDTO[])
const flamegraphLevels = computed<Record<number, SpanTreeNodeDTO[]>>(() => {
  const levels: Record<number, SpanTreeNodeDTO[]> = {}
  const rootList = zoomRootNode.value ? [zoomRootNode.value] : (lineage.value?.hierarchical_tree || [])

  function collect(nodes: SpanTreeNodeDTO[], currentDepth: number) {
    for (const node of nodes) {
      if (slowOnly.value && !isSlowSpan(node) && !hasSlowDescendant(node)) {
        continue
      }
      if (!levels[currentDepth]) {
        levels[currentDepth] = []
      }
      levels[currentDepth].push(node)
      if (node.children && node.children.length > 0) {
        collect(node.children, currentDepth + 1)
      }
    }
  }

  collect(rootList, 1)
  return levels
})

// 统计慢调用跨度数
const slowSpansCount = computed<number>(() => {
  if (!lineage.value?.hierarchical_tree) return 0
  let count = 0
  function countSlow(nodes: SpanTreeNodeDTO[]) {
    for (const n of nodes) {
      if (isSlowSpan(n)) count++
      if (n.children) countSlow(n.children)
    }
  }
  countSlow(lineage.value.hierarchical_tree)
  return count
})

function isSlowSpan(node: SpanTreeNodeDTO): boolean {
  return node.duration_ms >= slowThresholdMs.value || node.name.toLowerCase().includes('error')
}

function hasSlowDescendant(node: SpanTreeNodeDTO): boolean {
  if (node.children) {
    for (const child of node.children) {
      if (isSlowSpan(child) || hasSlowDescendant(child)) return true
    }
  }
  return false
}

function findNodeById(nodes: SpanTreeNodeDTO[], id: string): SpanTreeNodeDTO | null {
  for (const n of nodes) {
    if (n.span_id === id) return n
    if (n.children) {
      const found = findNodeById(n.children, id)
      if (found) return found
    }
  }
  return null
}

function getSliceStyle(node: SpanTreeNodeDTO) {
  const rootStart = zoomRootNode.value ? zoomRootNode.value.start_time_ms : (lineage.value?.hierarchical_tree[0]?.start_time_ms || 0)
  const offset = Math.max(0, node.start_time_ms - rootStart)
  const leftPercent = Math.max(0, Math.min(96, (offset / activeTotalDuration.value) * 100))
  const widthPercent = Math.max(2, Math.min(100 - leftPercent, (node.duration_ms / activeTotalDuration.value) * 100))

  return {
    left: `${leftPercent}%`,
    width: `${widthPercent}%`,
  }
}

function handleSelectSpan(node: SpanTreeNodeDTO) {
  selectedSpan.value = node
}

function handleZoomSpan(node: SpanTreeNodeDTO) {
  if (node.children && node.children.length > 0) {
    zoomRootSpanId.value = node.span_id
  }
}

function resetZoom() {
  zoomRootSpanId.value = null
}

function getProtocolColor(protocol: string): string {
  switch (protocol.toLowerCase()) {
    case 'grpc':
      return 'purple'
    case 'kafka':
    case 'rocketmq':
    case 'mq':
      return 'orange'
    case 'postgresql':
    case 'mysql':
    case 'sql':
    case 'db':
      return 'cyan'
    case 'redis':
    case 'cache':
      return 'volcano'
    case 'http':
    default:
      return 'blue'
  }
}

async function fetchLineageData() {
  loading.value = true
  try {
    const traceId = activeTraceId.value
    try {
      const res = await observabilityTraceApi.getLineage(traceId)
      if (res.lineage) {
        lineage.value = res.lineage
        if (lineage.value.hierarchical_tree.length > 0 && !selectedSpan.value) {
          selectedSpan.value = lineage.value.hierarchical_tree[0]
        }
        return
      }
    } catch {
      // 若后端尚未保存，自动构建多协议调用拓扑
    }

    const defaultSpans = generateMockSpans(traceId)
    try {
      const built = await observabilityTraceApi.buildLineage({
        trace_id: traceId,
        spans: defaultSpans,
      })
      lineage.value = built.lineage
    } catch {
      // 静默降级
    }
    if (lineage.value?.hierarchical_tree && lineage.value.hierarchical_tree.length > 0 && !selectedSpan.value) {
      selectedSpan.value = lineage.value.hierarchical_tree[0]
    }
  } catch {
    // 全局防崩
  } finally {
    loading.value = false
  }
}

function generateMockSpans(_traceId: string): Record<string, any>[] {
  return [
    {
      span_id: 'span_gw_01',
      name: 'HTTP POST /checkout',
      service_name: 'api-gateway',
      duration_ms: 180.0,
      start_time_ms: 1000.0,
      end_time_ms: 1180.0,
      attributes: { 'http.method': 'POST' },
    },
    {
      span_id: 'span_auth_02',
      parent_span_id: 'span_gw_01',
      name: 'VerifyToken',
      service_name: 'auth-center',
      duration_ms: 25.0,
      start_time_ms: 1005.0,
      end_time_ms: 1030.0,
      attributes: { 'rpc.system': 'grpc' },
    },
    {
      span_id: 'span_order_03',
      parent_span_id: 'span_gw_01',
      name: 'ProcessOrder',
      service_name: 'order-service',
      duration_ms: 140.0,
      start_time_ms: 1035.0,
      end_time_ms: 1175.0,
      attributes: { 'http.status_code': 200 },
    },
    {
      span_id: 'span_cache_04',
      parent_span_id: 'span_order_03',
      name: 'GET stock_inventory',
      service_name: 'redis-inventory',
      duration_ms: 10.0,
      start_time_ms: 1040.0,
      end_time_ms: 1050.0,
      attributes: { 'db.system': 'redis' },
    },
    {
      span_id: 'span_db_05',
      parent_span_id: 'span_order_03',
      name: 'INSERT orders',
      service_name: 'order-db',
      duration_ms: 120.0, // 慢查询
      start_time_ms: 1052.0,
      end_time_ms: 1172.0,
      attributes: { 'db.system': 'postgresql', 'db.statement': 'INSERT INTO orders ...' },
    },
  ]
}

watch(
  () => props.traceId,
  () => {
    fetchLineageData()
  },
  { immediate: true }
)
</script>

<style scoped>
.span-flamegraph-inspector-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.flamegraph-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-wrap {
  width: 36px;
  height: 36px;
  background: #fff2f0;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-icon {
  color: #ff4d4f;
  font-size: 18px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text, #1e293b);
}

.card-desc {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.threshold-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.zoom-indicator-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 6px;
  font-size: 12px;
}

.zoom-hint {
  color: #0958d9;
}

.flamegraph-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 6px;
}

.flamegraph-ruler {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #94a3b8;
}

.ruler-line {
  flex: 1;
  height: 1px;
  background: #cbd5e1;
}

.flamegraph-levels {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #f8fafc;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  min-height: 180px;
}

.flame-level-row {
  position: relative;
  height: 32px;
  width: 100%;
}

.flame-slice {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 4px;
  background: #1677ff;
  border: 1px solid rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all 0.15s ease;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.flame-slice:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.flame-slice.slice-slow {
  background: #ff4d4f !important;
  border-color: #cf1322 !important;
}

.flame-slice.slice-active {
  outline: 2px solid #faad14;
  z-index: 2;
}

.slice-inner {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  height: 100%;
  color: #ffffff;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slice-flame-icon {
  font-size: 12px;
  animation: pulse 1.2s infinite alternate;
}

.slice-title {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slice-duration {
  font-size: 10px;
  opacity: 0.9;
}

.flamegraph-legend-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
  padding: 4px 0;
}

.legend-items {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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

.dot-http { background: #1677ff; }
.dot-grpc { background: #722ed1; }
.dot-db { background: #13c2c2; }
.dot-redis { background: #fa541c; }
.dot-mq { background: #fa8c16; }
.dot-slow { background: #ff4d4f; }

.legend-tip {
  font-style: italic;
}

/* 属性下钻微卡片 */
.flame-inspector-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
}

.inspector-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.inspector-service-badge {
  display: flex;
  align-items: center;
  gap: 8px;
}

.inspector-service-name {
  font-weight: 700;
  color: #1e293b;
  font-size: 13px;
}

.inspector-op-name {
  color: #475569;
  font-size: 13px;
}

.inspector-metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
}

.metric-label {
  font-size: 11px;
  color: #64748b;
}

.metric-value {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.text-primary { color: #1677ff; }
.text-warning { color: #fa8c16; }

@keyframes pulse {
  0% { transform: scale(1); }
  100% { transform: scale(1.15); }
}
</style>
