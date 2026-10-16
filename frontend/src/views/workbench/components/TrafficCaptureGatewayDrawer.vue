<template>
  <a-drawer
    :open="open"
    :width="1100"
    placement="right"
    title="微服务网关旁路流量捕获与动态采样过滤控制台"
    destroy-on-close
    class="traffic-capture-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="drawer-banner">
        <div class="banner-title">
          <ClusterOutlined class="banner-icon" />
          <span>微服务网关旁路流量镜像捕获引擎 (Sidecar Traffic Capture Gateway)</span>
        </div>
        <p class="banner-desc">
          在微服务 API 网关或 Envoy/Sidecar 代理层旁路监听真实生产业务请求。支持多协议解析（HTTP REST / gRPC）、动态采样率平滑截流、路径与方法正则过滤，为影子回放与自动化测试用例合成提供高保真数据底座。
        </p>
      </div>

      <!-- 动态采样与过滤配置折叠面板 -->
      <a-collapse v-model:activeKey="activeCollapse" class="config-collapse">
        <a-collapse-panel key="filter_cfg" header="⚙️ 网关旁路过滤与采样规则配置 (Filter & Sampling Settings)">
          <div class="config-grid">
            <div class="config-col">
              <span class="field-label">动态采样率 (Sampling Rate):</span>
              <div class="slider-row">
                <a-slider
                  v-model:value="samplingRatePct"
                  :min="0"
                  :max="100"
                  :step="5"
                  class="sampling-slider"
                />
                <span class="rate-val">{{ samplingRatePct }}%</span>
              </div>
            </div>

            <div class="config-col">
              <span class="field-label">排除路径正则 (Exclude Paths):</span>
              <a-input
                v-model:value="excludePathsInput"
                placeholder="如: ^/health.*, ^/metrics.*"
                size="small"
              />
            </div>

            <div class="config-col">
              <span class="field-label">包含路径正则 (Include Paths):</span>
              <a-input
                v-model:value="includePathsInput"
                placeholder="如: ^/api/v1/.*"
                size="small"
              />
            </div>

            <div class="config-col actions-col">
              <a-space size="small">
                <a-button type="primary" size="small" :loading="savingConfig" @click="handleSaveConfig">
                  <SaveOutlined /> 保存并应用规则
                </a-button>
                <a-button size="small" @click="handleResetConfig">
                  重置出厂规则
                </a-button>
              </a-space>
            </div>
          </div>
        </a-collapse-panel>
      </a-collapse>

      <!-- 网关运行指标 KPI 看板 (5 大指标) -->
      <div v-if="metrics" class="kpi-grid">
        <div class="kpi-card">
          <span class="kpi-label">网关总拦截流量</span>
          <span class="kpi-val text-default">{{ metrics.metrics.total_intercepted }}</span>
          <span class="kpi-sub">旁路接收所有请求</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">成功捕获入库</span>
          <span class="kpi-val text-success">{{ metrics.metrics.total_captured }}</span>
          <span class="kpi-sub">符合过滤与采样标准</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">规则过滤丢弃</span>
          <span class="kpi-val text-warning">{{ metrics.metrics.total_filtered_out }}</span>
          <span class="kpi-sub">命中健康检查/排除路径</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">采样率截流丢弃</span>
          <span class="kpi-val text-purple">{{ metrics.metrics.total_sampled_out }}</span>
          <span class="kpi-sub">非100%采样削峰保护</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">活动流量池记录</span>
          <span class="kpi-val text-info">{{ metrics.active_records_count }}</span>
          <span class="kpi-sub">可供回放与用例合成</span>
        </div>
      </div>

      <!-- 流量列表与操作工具栏 -->
      <div class="records-panel">
        <div class="panel-header-row">
          <div class="header-left">
            <span class="panel-title">已捕获生产镜像流量流水 ({{ totalRecords }})</span>
            <a-radio-group v-model:value="protocolFilter" size="small" button-style="solid" @change="loadRecords">
              <a-radio-button value="ALL">全部协议</a-radio-button>
              <a-radio-button value="HTTP">HTTP (REST)</a-radio-button>
              <a-radio-button value="GRPC">gRPC (RPC)</a-radio-button>
            </a-radio-group>
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="搜索路径或关键字..."
              size="small"
              style="width: 200px"
              @search="loadRecords"
            />
          </div>

          <div class="header-right">
            <a-space size="small">
              <a-button size="small" :loading="loading" @click="loadInitialData">
                <ReloadOutlined /> 刷新
              </a-button>
              <a-button size="small" @click="showSimulateModal = true">
                <SendOutlined /> 模拟注入流量
              </a-button>
              <a-popconfirm title="确定清空当前捕获的所有流量记录吗？" @confirm="handleClearRecords">
                <a-button size="small" danger>
                  <DeleteOutlined /> 清空记录
                </a-button>
              </a-popconfirm>
            </a-space>
          </div>
        </div>

        <!-- 流量表格 -->
        <a-table
          :data-source="records"
          :columns="columns"
          row-key="traffic_id"
          size="small"
          :loading="loading"
          :pagination="{ pageSize: 8, showTotal: (t: number) => `共 ${t} 条捕获流量` }"
          class="traffic-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 协议 -->
            <template v-if="column.key === 'protocol'">
              <a-tag :color="record.protocol === 'GRPC' ? 'purple' : 'blue'" size="small">
                {{ record.protocol }}
              </a-tag>
            </template>

            <!-- 方法 -->
            <template v-else-if="column.key === 'method'">
              <span class="method-tag" :class="`method-${record.method.split(' ')[0].toLowerCase()}`">
                {{ record.method.split(' ')[0] }}
              </span>
            </template>

            <!-- 路径与参数 -->
            <template v-else-if="column.key === 'endpoint'">
              <div class="endpoint-cell">
                <span class="endpoint-text">{{ record.path_or_endpoint }}</span>
                <span class="traffic-id">ID: {{ record.traffic_id.slice(0, 10) }}</span>
              </div>
            </template>

            <!-- 响应状态码 -->
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.response_status_code >= 400 ? 'red' : 'green'" size="small">
                {{ record.response_status_code }}
              </a-tag>
            </template>

            <!-- 耗时 -->
            <template v-else-if="column.key === 'duration'">
              <span class="duration-text">{{ record.duration_ms }} ms</span>
            </template>

            <!-- 客户端源 IP -->
            <template v-else-if="column.key === 'client_ip'">
              <span class="ip-text">{{ record.client_ip || '127.0.0.1' }}</span>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <a-button size="small" type="link" @click="handleViewDetail(record as any)">
                查看详情
              </a-button>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 流量 Payload 明细模态框 -->
      <a-modal
        v-model:open="showDetailModal"
        title="捕获流量完整请求与响应明细 (Payload Viewer)"
        width="820px"
        :footer="null"
      >
        <div v-if="selectedItem" class="detail-container">
          <div class="detail-meta-box">
            <span class="detail-meta">协议: <strong>{{ selectedItem.protocol }}</strong></span>
            <span class="detail-meta">方法: <strong>{{ selectedItem.method }}</strong></span>
            <span class="detail-meta">端点: <code>{{ selectedItem.path_or_endpoint }}</code></span>
            <span class="detail-meta">状态码: <strong>{{ selectedItem.response_status_code }}</strong></span>
            <span class="detail-meta">耗时: <strong>{{ selectedItem.duration_ms }} ms</strong></span>
          </div>

          <!-- 请求体 -->
          <div class="payload-box">
            <div class="box-title">Request Body (请求体):</div>
            <pre class="code-pre"><code>{{ selectedItem.request_body || '(空)' }}</code></pre>
          </div>

          <!-- 响应体 -->
          <div class="payload-box">
            <div class="box-title">Response Body (响应体):</div>
            <pre class="code-pre"><code>{{ selectedItem.response_body || '(空)' }}</code></pre>
          </div>

          <!-- 请求头 -->
          <div class="payload-box">
            <div class="box-title">Headers (请求头):</div>
            <pre class="code-pre"><code>{{ JSON.stringify(selectedItem.headers, null, 2) }}</code></pre>
          </div>
        </div>
      </a-modal>

      <!-- 模拟注入流量模态框 -->
      <a-modal
        v-model:open="showSimulateModal"
        title="模拟网关旁路流量镜像注入"
        width="620px"
        @ok="handleSimulateSubmit"
      >
        <a-form layout="vertical">
          <a-form-item label="协议与方法:">
            <a-space>
              <a-select v-model:value="simulateForm.protocol" style="width: 120px">
                <a-select-option value="HTTP">HTTP (REST)</a-select-option>
                <a-select-option value="GRPC">gRPC</a-select-option>
              </a-select>
              <a-select v-model:value="simulateForm.method" style="width: 120px">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
              </a-select>
            </a-space>
          </a-form-item>
          <a-form-item label="请求路径/端点:">
            <a-input v-model:value="simulateForm.path_or_endpoint" placeholder="/api/v1/orders/checkout" />
          </a-form-item>
          <a-form-item label="请求体 (JSON):">
            <a-textarea v-model:value="simulateForm.request_body" :rows="3" />
          </a-form-item>
          <a-form-item label="模拟响应状态码与耗时:">
            <a-space>
              <span>状态码: <a-input-number v-model:value="simulateForm.response_status_code" style="width: 90px" /></span>
              <span>耗时: <a-input-number v-model:value="simulateForm.duration_ms" style="width: 90px" /> ms</span>
            </a-space>
          </a-form-item>
        </a-form>
      </a-modal>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ClusterOutlined,
  SaveOutlined,
  ReloadOutlined,
  SendOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import {
  trafficCaptureApi,
  type CapturedTrafficItem,
  type CaptureMetrics,
} from '@/api/trafficGateway'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const savingConfig = ref(false)
const activeCollapse = ref<string[]>([])
const protocolFilter = ref('ALL')
const searchKeyword = ref('')
const totalRecords = ref(0)
const records = ref<CapturedTrafficItem[]>([])
const metrics = ref<CaptureMetrics | null>(null)

// 规则配置表单绑定
const samplingRatePct = ref(100)
const excludePathsInput = ref('^/health.*, ^/metrics.*')
const includePathsInput = ref('^/.*')

// 详情模态框
const showDetailModal = ref(false)
const selectedItem = ref<CapturedTrafficItem | null>(null)

// 模拟注入模态框
const showSimulateModal = ref(false)
const simulateForm = reactive({
  protocol: 'HTTP',
  method: 'POST',
  path_or_endpoint: '/api/v1/orders/checkout',
  request_body: '{"order_id": 1001, "amount": 199.0}',
  response_status_code: 200,
  duration_ms: 45.0,
})

const columns = [
  { title: '协议', key: 'protocol', width: 90 },
  { title: '方法', key: 'method', width: 90 },
  { title: '请求端点与流量 ID', key: 'endpoint' },
  { title: '状态码', key: 'status', width: 90 },
  { title: '耗时', key: 'duration', width: 100 },
  { title: '源 IP', key: 'client_ip', width: 130 },
  { title: '操作', key: 'action', width: 100 },
]

// 预设示例数据 (在后端无数据时提供友好体验)
const PRESET_RECORDS: CapturedTrafficItem[] = [
  {
    traffic_id: 'trf_sample_001',
    protocol: 'HTTP',
    method: 'POST',
    path_or_endpoint: '/api/v1/orders/checkout',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer token123' },
    query_params: { source: 'mobile' },
    request_body: '{"order_id": 1001, "amount": 199.0}',
    response_status_code: 200,
    response_body: '{"code": 0, "status": "CREATED"}',
    duration_ms: 45.2,
    client_ip: '192.168.1.100',
    tags: {},
    captured_at: '2026-10-16T10:00:00Z',
  },
  {
    traffic_id: 'trf_sample_002',
    protocol: 'GRPC',
    method: 'POST',
    path_or_endpoint: '/order.OrderService/GetOrderDetail',
    headers: { 'content-type': 'application/grpc' },
    query_params: {},
    request_body: '{"order_id": 1001}',
    response_status_code: 0,
    response_body: '{"code": 0, "order": {"id": 1001, "status": "PAID"}}',
    duration_ms: 18.0,
    client_ip: '192.168.1.105',
    tags: {},
    captured_at: '2026-10-16T10:02:00Z',
  },
]

const loadInitialData = async () => {
  loading.value = true
  try {
    // 1. 获取配置
    const cfg = await trafficCaptureApi.getFilterConfig()
    samplingRatePct.value = Math.round(cfg.sampling_rate * 100)
    excludePathsInput.value = (cfg.exclude_paths || []).join(', ')
    includePathsInput.value = (cfg.include_paths || []).join(', ')

    // 2. 获取指标
    metrics.value = await trafficCaptureApi.getMetrics()

    // 3. 加载记录
    await loadRecords()
  } catch {
    // 降级使用本地预设
    records.value = PRESET_RECORDS
    totalRecords.value = PRESET_RECORDS.length
    metrics.value = {
      metrics: { total_intercepted: 24, total_captured: 18, total_filtered_out: 4, total_sampled_out: 2 },
      active_records_count: 18,
      protocol_breakdown: { HTTP: 14, GRPC: 4 },
      filter_config: {
        include_paths: ['^/.*'],
        exclude_paths: ['^/health.*'],
        allowed_methods: ['GET', 'POST'],
        sampling_rate: 1.0,
        capture_request_body: true,
        capture_response_body: true,
        max_body_bytes: 1048576,
      },
    }
  } finally {
    loading.value = false
  }
}

const loadRecords = async () => {
  try {
    const params: any = { limit: 100 }
    if (protocolFilter.value !== 'ALL') {
      params.protocol = protocolFilter.value
    }
    if (searchKeyword.value.trim()) {
      params.path_pattern = searchKeyword.value.trim()
    }
    const res = await trafficCaptureApi.listRecords(params)
    records.value = res.records.length > 0 ? res.records : PRESET_RECORDS
    totalRecords.value = res.records.length > 0 ? res.total : PRESET_RECORDS.length
  } catch {
    records.value = PRESET_RECORDS
    totalRecords.value = PRESET_RECORDS.length
  }
}

const handleSaveConfig = async () => {
  savingConfig.value = true
  try {
    const excludes = excludePathsInput.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
    const includes = includePathsInput.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
    const res = await trafficCaptureApi.updateFilterConfig({
      sampling_rate: samplingRatePct.value / 100.0,
      exclude_paths: excludes,
      include_paths: includes,
    })
    message.success(res.message || '网关过滤配置已成功应用')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '更新配置失败')
  } finally {
    savingConfig.value = false
  }
}

const handleResetConfig = () => {
  samplingRatePct.value = 100
  excludePathsInput.value = '^/health.*, ^/metrics.*'
  includePathsInput.value = '^/.*'
  message.info('已恢复为出厂标准过滤规则')
}

const handleClearRecords = async () => {
  try {
    await trafficCaptureApi.clearRecords()
    records.value = []
    totalRecords.value = 0
    if (metrics.value) {
      metrics.value.active_records_count = 0
    }
    message.success('已清空捕获流量记录')
  } catch (err: any) {
    message.error(err.message || '清空失败')
  }
}

const handleViewDetail = (item: any) => {
  selectedItem.value = item
  showDetailModal.value = true
}

const handleSimulateSubmit = async () => {
  showSimulateModal.value = false
  try {
    const res = await trafficCaptureApi.interceptTraffic({
      protocol: simulateForm.protocol,
      method: simulateForm.method,
      path_or_endpoint: simulateForm.path_or_endpoint,
      request_body: simulateForm.request_body,
      response_status_code: simulateForm.response_status_code,
      duration_ms: simulateForm.duration_ms,
    })
    if (res.captured && res.item) {
      message.success(res.message || '模拟流量已成功捕获入库')
      records.value.unshift(res.item)
      totalRecords.value += 1
    } else {
      message.warning('模拟流量已被网关过滤规则或采样率丢弃')
    }
  } catch (err: any) {
    message.error(err.message || '模拟注入失败')
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

/* 过滤折叠面板 */
.config-collapse {
  background: #f8fafc;
  border-radius: 6px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.config-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.actions-col {
  grid-column: span 2;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  margin-top: 6px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sampling-slider {
  flex: 1;
  margin: 6px 0;
}

.rate-val {
  font-size: 12px;
  font-weight: 700;
  color: #0284c7;
  width: 40px;
}

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.kpi-card {
  padding: 10px 14px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
}

.kpi-val {
  font-size: 22px;
  font-weight: 700;
  margin: 2px 0;
}

.kpi-sub {
  font-size: 10px;
  color: #94a3b8;
}

.text-default { color: #0284c7; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-purple { color: #7c3aed; }
.text-info { color: #2563eb; }

/* 流量表格面板 */
.records-panel {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.panel-header-row {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.method-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.method-get { background: #dbeafe; color: #1d4ed8; }
.method-post { background: #dcfce7; color: #15803d; }
.method-put { background: #fef3c7; color: #b45309; }
.method-delete { background: #fee2e2; color: #b91c1c; }

.endpoint-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.endpoint-text {
  font-weight: 600;
  color: #0f172a;
}

.traffic-id {
  font-size: 10px;
  font-family: monospace;
  color: #94a3b8;
}

.duration-text {
  font-size: 11px;
  font-family: monospace;
  color: #64748b;
}

.ip-text {
  font-size: 11px;
  font-family: monospace;
  color: #64748b;
}

/* 详情框 */
.detail-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-meta-box {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 12px;
}

.payload-box {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.box-title {
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
}

.code-pre {
  margin: 0;
  padding: 10px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  background: #1e293b;
  color: #f8fafc;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
