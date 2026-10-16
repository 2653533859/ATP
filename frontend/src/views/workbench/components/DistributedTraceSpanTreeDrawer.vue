<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="OpenTelemetry 全链路 Span 追踪与层级调用树控制台"
    destroy-on-close
    class="trace-tree-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <ClusterOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">OpenTelemetry / W3C TraceContext 全链路调用树追踪 (T1.1)</div>
            <div class="banner-desc">
              遵循 W3C TraceContext（traceparent）规范，自动串联微服务多协议调用的父子依赖关系。支持递归展开级联调用树、定位首发异常点、量化跨服务耗时占比并可视化微服务血缘链路。
            </div>
          </div>
        </div>

        <!-- W3C TraceContext 报文头部解析展示框 -->
        <div v-if="selectedTrace" class="traceparent-box">
          <span class="tp-label">W3C traceparent Header:</span>
          <code class="tp-code">00-{{ selectedTrace.trace_id }}-{{ selectedTrace.root_span_id }}-01</code>
          <a-button size="small" type="link" @click="copyTraceparent">
            <CopyOutlined /> 复制
          </a-button>
        </div>
      </div>

      <!-- 快捷预设场景与过滤控制栏 -->
      <div class="filter-bar">
        <div class="preset-row">
          <span class="preset-label">典型调用链场景:</span>
          <a-space :size="8">
            <a-button
              size="small"
              :type="presetKey === 'checkout' ? 'primary' : 'default'"
              danger
              @click="applyPreset('checkout')"
            >
              场景 1: 电商结账调用链 (含支付下游异常 504)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'profile' ? 'primary' : 'default'"
              @click="applyPreset('profile')"
            >
              场景 2: 用户资料多层级只读链 (全链路正常通过)
            </a-button>
          </a-space>
        </div>

        <div class="control-row">
          <a-space :size="12" align="center" wrap>
            <span class="ctrl-label">过滤微服务:</span>
            <a-select v-model:value="filterService" style="width: 160px" size="small" allow-clear placeholder="全部服务">
              <a-select-option value="all">全部微服务</a-select-option>
              <a-select-option value="api-gateway">api-gateway</a-select-option>
              <a-select-option value="order-service">order-service</a-select-option>
              <a-select-option value="pay-service">pay-service</a-select-option>
              <a-select-option value="inventory-service">inventory-service</a-select-option>
            </a-select>

            <span class="ctrl-label">仅看异常链路:</span>
            <a-switch v-model:checked="filterOnlyError" size="small" @change="loadTraces" />

            <a-button size="small" :loading="loadingTraces" @click="loadTraces">
              <ReloadOutlined /> 刷新链路列表
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 链路概览选择卡片 (Trace Selector) -->
      <div v-if="traceList.length > 0" class="traces-selector">
        <div class="selector-title">链路追踪批次选择：</div>
        <div class="trace-chips">
          <div
            v-for="t in traceList"
            :key="t.trace_id"
            class="trace-chip"
            :class="{ 'chip-active': currentTraceId === t.trace_id }"
            @click="selectTrace(t.trace_id)"
          >
            <div class="chip-top">
              <span class="chip-op">{{ t.root_operation }}</span>
              <a-tag :color="t.has_error ? 'red' : 'green'" size="small">
                {{ t.has_error ? 'ERROR' : 'OK' }}
              </a-tag>
            </div>
            <div class="chip-sub">
              <span>{{ t.root_service }}</span>
              <span><strong>{{ t.total_duration_ms }} ms</strong> ({{ t.total_spans_count }} Spans)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 选中 Trace 的 KPI 统计横幅 -->
      <div v-if="selectedTrace" class="trace-kpi-banner" :class="selectedTrace.has_error ? 'kpi-err' : 'kpi-ok'">
        <div class="kpi-item">
          <div class="kpi-val">{{ selectedTrace.total_duration_ms }} ms</div>
          <div class="kpi-lbl">全链路总时延</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-val">{{ selectedTrace.total_spans_count }} 个</div>
          <div class="kpi-lbl">Span 节点总数</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-val">{{ selectedTrace.services_involved.length }} 个</div>
          <div class="kpi-lbl">跨越微服务数</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-val" :class="selectedTrace.has_error ? 'text-red' : 'text-green'">
            {{ selectedTrace.has_error ? '🚨 存在未捕获异常' : '✅ 全链路健康' }}
          </div>
          <div class="kpi-lbl">链路诊断状态</div>
        </div>
      </div>

      <!-- 核心工作区：层级调用树展示 (Tree Table) -->
      <div v-if="selectedTrace" class="tree-section">
        <div class="section-title">
          <span>分布式层级调用树 (Trace Hierarchy Tree)</span>
          <div class="service-tags">
            <span class="tags-label">涉及微服务:</span>
            <a-tag v-for="svc in selectedTrace.services_involved" :key="svc" color="blue">
              {{ svc }}
            </a-tag>
          </div>
        </div>

        <a-table
          :data-source="selectedTrace.root_nodes"
          :columns="columns"
          row-key="span_id"
          size="small"
          :pagination="false"
          bordered
          :default-expand-all-rows="true"
          class="span-tree-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'service_op'">
              <div class="span-node-cell">
                <a-tag :color="getServiceColor(record.service_name)" class="svc-tag">
                  {{ record.service_name }}
                </a-tag>
                <strong class="op-name">{{ record.name }}</strong>
                <code class="span-id">{{ record.span_id }}</code>
              </div>
            </template>

            <template v-if="column.key === 'kind'">
              <a-tag>{{ record.kind }}</a-tag>
            </template>

            <template v-if="column.key === 'duration'">
              <div class="duration-cell">
                <span>{{ record.duration_ms }} ms</span>
                <a-progress
                  :percent="Math.min(100, Math.round((record.duration_ms / (selectedTrace.total_duration_ms || 1)) * 100))"
                  size="small"
                  :status="record.status_code === 'ERROR' ? 'exception' : 'normal'"
                />
              </div>
            </template>

            <template v-if="column.key === 'status'">
              <a-tag :color="record.status_code === 'ERROR' ? 'red' : 'green'">
                {{ record.status_code }}
              </a-tag>
              <div v-if="record.status_message" class="status-msg">
                {{ record.status_message }}
              </div>
            </template>

            <template v-if="column.key === 'attributes'">
              <div class="attr-preview">
                <span v-for="(v, k) in record.attributes" :key="k" class="attr-chip">
                  <code>{{ k }}: {{ v }}</code>
                </span>
              </div>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ClusterOutlined,
  CopyOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  traceTelemetryApi,
  type TraceTreeReport,
  type TraceSummaryItem,
} from '@/api/traceObservability'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

function handleClose() {
  emit('update:open', false)
}

const loadingTraces = ref(false)
const traceList = ref<TraceSummaryItem[]>([])
const currentTraceId = ref('')
const selectedTrace = ref<TraceTreeReport | null>(null)
const filterService = ref('all')
const filterOnlyError = ref(false)
const presetKey = ref<'checkout' | 'profile'>('checkout')

const columns = [
  { title: '微服务与调用动作', key: 'service_op', width: 360 },
  { title: '类型 (Kind)', key: 'kind', width: 110 },
  { title: '执行耗时 (ms) & 占比', key: 'duration', width: 220 },
  { title: '状态', key: 'status', width: 140 },
  { title: '属性与事件', key: 'attributes' },
]

function getServiceColor(svc: string): string {
  switch (svc) {
    case 'api-gateway': return 'blue'
    case 'order-service': return 'orange'
    case 'pay-service': return 'red'
    case 'inventory-service': return 'purple'
    case 'auth-service': return 'cyan'
    default: return 'geekblue'
  }
}

// 演练预设
const PRESETS = {
  checkout: [
    {
      trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
      span_id: '00f067aa0ba902b7',
      parent_span_id: null,
      name: 'POST /api/v1/orders/checkout',
      service_name: 'api-gateway',
      kind: 'SERVER',
      duration_ms: 550.0,
      start_time_us: 1000000,
      end_time_us: 1550000,
      status_code: 'ERROR',
      attributes: { 'http.status_code': 504 },
    },
    {
      trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
      span_id: '11a067aa0ba902b8',
      parent_span_id: '00f067aa0ba902b7',
      name: 'create_order_flow',
      service_name: 'order-service',
      kind: 'INTERNAL',
      duration_ms: 500.0,
      start_time_us: 1020000,
      end_time_us: 1520000,
      status_code: 'ERROR',
      attributes: { 'order.id': 1001 },
    },
    {
      trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
      span_id: '22b067aa0ba902b9',
      parent_span_id: '11a067aa0ba902b8',
      name: 'call_payment_gateway',
      service_name: 'pay-service',
      kind: 'CLIENT',
      duration_ms: 450.0,
      start_time_us: 1050000,
      end_time_us: 1500000,
      status_code: 'ERROR',
      status_message: 'HTTPSConnectionPool: Read timed out (504)',
      attributes: { 'http.url': 'https://api.alipay.com/pay', 'http.status_code': 504 },
    },
    {
      trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
      span_id: '33c067aa0ba902ba',
      parent_span_id: '11a067aa0ba902b8',
      name: 'lock_inventory_stock',
      service_name: 'inventory-service',
      kind: 'SERVER',
      duration_ms: 40.0,
      start_time_us: 1030000,
      end_time_us: 1070000,
      status_code: 'OK',
      attributes: { 'stock.sku_id': 'SKU_9982' },
    },
  ],
  profile: [
    {
      trace_id: '5cf92f3577b34da6a3ce929d0e0e8888',
      span_id: '55f067aa0ba902b1',
      parent_span_id: null,
      name: 'GET /api/v1/users/profile',
      service_name: 'api-gateway',
      kind: 'SERVER',
      duration_ms: 65.0,
      start_time_us: 2000000,
      end_time_us: 2065000,
      status_code: 'OK',
      attributes: { 'http.status_code': 200 },
    },
    {
      trace_id: '5cf92f3577b34da6a3ce929d0e0e8888',
      span_id: '66a067aa0ba902b2',
      parent_span_id: '55f067aa0ba902b1',
      name: 'get_user_info',
      service_name: 'auth-service',
      kind: 'SERVER',
      duration_ms: 45.0,
      start_time_us: 2010000,
      end_time_us: 2055000,
      status_code: 'OK',
      attributes: { 'user.id': 1002 },
    },
  ],
}

async function applyPreset(key: 'checkout' | 'profile') {
  presetKey.value = key
  const spans = PRESETS[key]
  try {
    await traceTelemetryApi.ingestSpans(spans)
    message.success('已加载并中继预设链路 Spans')
    await loadTraces()
    if (spans.length > 0) {
      await selectTrace(spans[0].trace_id)
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '加载失败')
  }
}

async function loadTraces() {
  loadingTraces.value = true
  try {
    const params: any = {}
    if (filterService.value && filterService.value !== 'all') {
      params.service_name = filterService.value
    }
    if (filterOnlyError.value) {
      params.has_error = true
    }
    const res = await traceTelemetryApi.listTraces(params)
    traceList.value = res.traces
    if (res.traces.length > 0 && !currentTraceId.value) {
      await selectTrace(res.traces[0].trace_id)
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取链路列表失败')
  } finally {
    loadingTraces.value = false
  }
}

async function selectTrace(tid: string) {
  currentTraceId.value = tid
  try {
    const tree = await traceTelemetryApi.getTraceTree(tid)
    selectedTrace.value = tree
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取链路树失败')
  }
}

function copyTraceparent() {
  if (!selectedTrace.value) return
  const tp = `00-${selectedTrace.value.trace_id}-${selectedTrace.value.root_span_id}-01`
  void navigator.clipboard.writeText(tp)
  message.success('已复制 W3C traceparent 头部')
}

onMounted(async () => {
  await applyPreset('checkout')
})
</script>

<style scoped>
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intro-banner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.banner-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 22px;
  color: #0284c7;
  margin-top: 2px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  margin-top: 4px;
}

.traceparent-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.tp-label {
  color: #64748b;
  font-weight: 500;
}

.tp-code {
  background: #f1f5f9;
  color: #0369a1;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: Consolas, monospace;
}

.filter-bar {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.ctrl-label {
  font-size: 12px;
  color: #64748b;
}

.traces-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.trace-chips {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.trace-chip {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  min-width: 220px;
  transition: all 0.2s;
}

.trace-chip:hover {
  border-color: #0284c7;
}

.chip-active {
  background: #f0f9ff;
  border-color: #0284c7;
}

.chip-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.chip-op {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.chip-sub {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
}

/* KPI Banner */
.trace-kpi-banner {
  border-radius: 8px;
  padding: 12px 16px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  border: 1px solid transparent;
}

.kpi-ok {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.kpi-err {
  background: #fef2f2;
  border-color: #fecaca;
}

.kpi-item {
  text-align: center;
}

.kpi-val {
  font-size: 18px;
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

.text-green {
  color: #16a34a;
}

.tree-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.service-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tags-label {
  font-size: 11px;
  color: #64748b;
}

.span-tree-table {
  background: #ffffff;
}

.span-node-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.svc-tag {
  font-weight: 600;
}

.op-name {
  color: #0f172a;
  font-size: 12px;
}

.span-id {
  font-size: 10px;
  color: #94a3b8;
}

.duration-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.status-msg {
  font-size: 10px;
  color: #dc2626;
  margin-top: 2px;
}

.attr-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.attr-chip code {
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10px;
  color: #475569;
}
</style>
