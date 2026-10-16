<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="影子流量无副作用沙箱隔离回放与外部依赖 Mock 代理控制台"
    destroy-on-close
    class="shadow-replay-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="drawer-banner">
        <div class="banner-title">
          <SendOutlined class="banner-icon" />
          <span>影子流量安全回放与零副作用沙箱调度引擎 (Shadow Traffic Replay Engine)</span>
        </div>
        <p class="banner-desc">
          将捕获与脱敏后的生产真实流量，以可控 QPS 流速重放至新版本被测服务。提供 <strong>BLOCK_WRITES</strong> 严格写拦截、<strong>X-Shadow-Traffic</strong> 影子链路打标与<strong>第三方外部不可控依赖 (支付/短信/邮件) 自动 Mock 代理</strong>，确保线上回放 0 脏数据、0 资金消耗、0 用户骚扰。
        </p>
      </div>

      <!-- 回放参数与安全防护配置折叠面板 -->
      <a-collapse v-model:activeKey="activeCollapse" class="config-collapse">
        <a-collapse-panel key="guard_cfg" header="🛡️ 影子回放目标与写操作安全防护配置 (Guard Settings)">
          <div class="config-grid">
            <div class="config-col">
              <span class="field-label">目标服务 Base URL:</span>
              <a-input v-model:value="targetBaseUrl" placeholder="http://127.0.0.1:8000" size="small" />
            </div>

            <div class="config-col">
              <span class="field-label">写操作安全防护模式 (Write Guard):</span>
              <a-select v-model:value="writeGuardMode" size="small" style="width: 100%">
                <a-select-option value="BLOCK_WRITES">
                  <span class="mode-opt text-warning">BLOCK_WRITES (推荐: 拦截所有写请求，0脏数据)</span>
                </a-select-option>
                <a-select-option value="SHADOW_HEADER_ONLY">
                  <span class="mode-opt text-primary">SHADOW_HEADER_ONLY (注入影子头，需微服务影子库)</span>
                </a-select-option>
                <a-select-option value="ALLOW_ALL">
                  <span class="mode-opt text-danger">ALLOW_ALL (独立隔离环境全量放行)</span>
                </a-select-option>
                <a-select-option value="DRY_RUN">
                  <span class="mode-opt text-info">DRY_RUN (纯沙箱演练，不发真实网络请求)</span>
                </a-select-option>
              </a-select>
            </div>

            <div class="config-col">
              <span class="field-label">QPS 流速控制:</span>
              <div class="slider-row">
                <a-slider v-model:value="rateLimitQps" :min="1" :max="200" :step="5" class="qps-slider" />
                <span class="rate-val">{{ rateLimitQps }} QPS</span>
              </div>
            </div>

            <div class="config-col">
              <span class="field-label">单请求超时上限:</span>
              <div class="slider-row">
                <a-input-number v-model:value="timeoutSec" :min="1" :max="30" size="small" style="width: 80px" />
                <span class="unit-text">秒</span>
              </div>
            </div>

            <!-- 外部依赖 Mock 规则概览 -->
            <div class="config-col-full">
              <span class="field-label">第三方外部依赖拦截 Mock 代理 (已激活 {{ defaultMockRules.length }} 条规则):</span>
              <div class="mock-rules-tags">
                <a-tag v-for="r in defaultMockRules" :key="r.rule_id" color="purple">
                  <LockOutlined /> {{ r.name }}
                </a-tag>
              </div>
            </div>
          </div>
        </a-collapse-panel>
      </a-collapse>

      <!-- 核心指标 KPI 看板 (6 大指标) -->
      <div v-if="currentReport" class="kpi-grid">
        <div class="kpi-card">
          <span class="kpi-label">回放总请求数</span>
          <span class="kpi-val text-default">{{ currentReport.total_items }}</span>
          <span class="kpi-sub">流速 {{ rateLimitQps }} QPS</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">成功响应 (Success)</span>
          <span class="kpi-val text-success">{{ currentReport.success_count }}</span>
          <span class="kpi-sub">响应码正常或受保护</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">写操作安全拦截</span>
          <span class="kpi-val text-warning">{{ currentReport.blocked_write_count }}</span>
          <span class="kpi-sub">免除线上脏写副作用</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">外部依赖 Mock 代理</span>
          <span class="kpi-val text-purple">{{ currentReport.mocked_external_count }}</span>
          <span class="kpi-sub">免除支付/短信外部扣费</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">异常失败请求</span>
          <span class="kpi-val text-danger">{{ currentReport.failure_count }}</span>
          <span class="kpi-sub">5xx 服务端错误或超时</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">平均响应耗时</span>
          <span class="kpi-val text-info">{{ currentReport.avg_duration_ms }} ms</span>
          <span class="kpi-sub">实际往返 RTT 时延</span>
        </div>
      </div>

      <!-- 回放流水面板 -->
      <div class="results-panel">
        <div class="panel-header-row">
          <div class="header-left">
            <span class="panel-title">影子回放执行流水明细 ({{ filteredResults.length }} / {{ currentReport?.results.length || 0 }})</span>
            <a-radio-group v-model:value="statusFilter" size="small" button-style="solid">
              <a-radio-button value="ALL">全部</a-radio-button>
              <a-radio-button value="BLOCKED_WRITE">仅写拦截 ({{ currentReport?.blocked_write_count || 0 }})</a-radio-button>
              <a-radio-button value="MOCKED">外部Mock ({{ currentReport?.mocked_external_count || 0 }})</a-radio-button>
              <a-radio-button value="FAILURE">失败 ({{ currentReport?.failure_count || 0 }})</a-radio-button>
            </a-radio-group>
          </div>

          <div class="header-right">
            <a-space size="small">
              <a-button size="small" :loading="loading" @click="loadInitialData">
                <ReloadOutlined /> 刷新
              </a-button>
              <a-button size="small" @click="applyPreset('mock_blocked')">
                预设: 包含写拦截与外部Mock
              </a-button>
              <a-button type="primary" size="small" :loading="replaying" @click="handleRunReplay">
                <PlayCircleOutlined /> 启动影子沙箱回放
              </a-button>
            </a-space>
          </div>
        </div>

        <a-table
          :data-source="filteredResults"
          :columns="columns"
          row-key="item_id"
          size="small"
          :loading="replaying || loading"
          :pagination="{ pageSize: 7, showTotal: (t: number) => `共 ${t} 条回放流水` }"
          class="replay-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 方法 -->
            <template v-if="column.key === 'method'">
              <span class="method-tag" :class="`method-${record.method.split(' ')[0].toLowerCase()}`">
                {{ record.method.split(' ')[0] }}
              </span>
            </template>

            <!-- 端点与目标 URL -->
            <template v-else-if="column.key === 'endpoint'">
              <div class="endpoint-cell">
                <span class="endpoint-text">{{ record.path_or_endpoint }}</span>
                <span class="target-url">{{ record.executed_url }}</span>
              </div>
            </template>

            <!-- 状态码对比 -->
            <template v-else-if="column.key === 'status_compare'">
              <div class="status-box">
                <a-tag size="small" color="default">原: {{ record.original_status_code }}</a-tag>
                <span class="arrow">→</span>
                <a-tag size="small" :color="record.replayed_status_code >= 400 ? 'red' : 'green'">
                  放: {{ record.replayed_status_code }}
                </a-tag>
              </div>
            </template>

            <!-- 耗时 -->
            <template v-else-if="column.key === 'duration'">
              <span class="duration-text">{{ record.duration_ms }} ms</span>
            </template>

            <!-- 安全防护与拦截状态 -->
            <template v-else-if="column.key === 'guard_status'">
              <a-tag v-if="record.was_write_blocked" color="orange">
                <LockOutlined /> 写操作安全拦截 (0脏数据)
              </a-tag>
              <a-tag v-else-if="record.was_mocked" color="purple">
                <ApiOutlined /> 外部依赖 Mock 代理
              </a-tag>
              <a-tag v-else-if="record.success" color="green">
                <CheckCircleOutlined /> 正常回放放行
              </a-tag>
              <a-tag v-else color="red">
                <CloseCircleOutlined /> 调用异常失败
              </a-tag>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <a-button size="small" type="link" @click="handleViewDetail(record)">
                查看应答
              </a-button>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 响应体明细模态框 -->
      <a-modal
        v-model:open="showDetailModal"
        title="影子回放应答体明细 (Replay Response Payload)"
        width="760px"
        :footer="null"
      >
        <div v-if="selectedItem" class="detail-container">
          <div class="detail-meta-box">
            <span>方法: <strong>{{ selectedItem.method }}</strong></span>
            <span>URL: <code>{{ selectedItem.executed_url }}</code></span>
            <span>回放响应码: <strong>{{ selectedItem.replayed_status_code }}</strong></span>
            <span>耗时: <strong>{{ selectedItem.duration_ms }} ms</strong></span>
          </div>

          <div v-if="selectedItem.mock_reason" class="alert-box mock-alert">
            {{ selectedItem.mock_reason }}
          </div>

          <div class="payload-box">
            <div class="box-title">Replayed Response Body (回放响应体):</div>
            <pre class="code-pre"><code>{{ selectedItem.replayed_response_body || '(空响应体)' }}</code></pre>
          </div>
        </div>
      </a-modal>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  SendOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LockOutlined,
  ApiOutlined,
} from '@ant-design/icons-vue'
import {
  shadowReplayApi,
  type MockRuleConfigItem,
  type ReplayItemResult,
  type ReplaySessionReport,
} from '@/api/trafficGateway'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const replaying = ref(false)
const activeCollapse = ref<string[]>(['guard_cfg'])

// 配置项绑定
const targetBaseUrl = ref('http://127.0.0.1:8000')
const writeGuardMode = ref('BLOCK_WRITES')
const rateLimitQps = ref(20)
const timeoutSec = ref(5.0)
const defaultMockRules = ref<MockRuleConfigItem[]>([])

const currentReport = ref<ReplaySessionReport | null>(null)
const statusFilter = ref('ALL')

// 详情查看
const showDetailModal = ref(false)
const selectedItem = ref<ReplayItemResult | null>(null)

const columns = [
  { title: '方法', key: 'method', width: 90 },
  { title: '端点路径与目标 URL', key: 'endpoint' },
  { title: '状态码对比', key: 'status_compare', width: 140 },
  { title: '耗时', key: 'duration', width: 90 },
  { title: '安全防护与拦截标记', key: 'guard_status', width: 220 },
  { title: '操作', key: 'action', width: 100 },
]

// 预设回放样例
const PRESET_REPORT: ReplaySessionReport = {
  session_id: 'rpl_demo_safe_001',
  target_base_url: 'http://test-gateway:8000',
  write_guard_mode: 'BLOCK_WRITES',
  total_items: 6,
  success_count: 6,
  failure_count: 0,
  blocked_write_count: 2,
  mocked_external_count: 2,
  avg_duration_ms: 12.4,
  created_at: '2026-10-16T12:00:00Z',
  results: [
    {
      item_id: 'rit_1',
      traffic_id: 'trf_1',
      method: 'GET',
      path_or_endpoint: '/api/v1/products/101',
      executed_url: 'http://test-gateway:8000/api/v1/products/101',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 22.5,
      was_mocked: false,
      mock_reason: null,
      was_write_blocked: false,
      replayed_response_body: '{"product_id": 101, "name": "Apple iPhone", "stock": 50}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_2',
      traffic_id: 'trf_2',
      method: 'POST',
      path_or_endpoint: '/api/v1/orders/checkout',
      executed_url: 'http://test-gateway:8000/api/v1/orders/checkout',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 1.5,
      was_mocked: false,
      mock_reason: null,
      was_write_blocked: true,
      replayed_response_body: '{"code": 0, "shadow_blocked": true, "message": "ATP 安全防护：写操作 [POST] 已被拦截，未产生线上副作用"}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_3',
      traffic_id: 'trf_3',
      method: 'POST',
      path_or_endpoint: '/api.alipay.com/gateway.do',
      executed_url: 'https://api.alipay.com/gateway.do',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 2.0,
      was_mocked: true,
      mock_reason: '命中第三方外部依赖 Mock 规则: 第三方支付网关拦截 (微信/支付宝)',
      was_write_blocked: false,
      replayed_response_body: '{"code": 0, "status": "SUCCESS", "mock": true}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_4',
      traffic_id: 'trf_4',
      method: 'POST',
      path_or_endpoint: '/sms.provider.com/send',
      executed_url: 'http://sms.provider.com/send',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 2.0,
      was_mocked: true,
      mock_reason: '命中第三方外部依赖 Mock 规则: 短信与消息推送服务拦截',
      was_write_blocked: false,
      replayed_response_body: '{"code": 0, "message": "SMS Mock Sent", "mock": true}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_5',
      traffic_id: 'trf_5',
      method: 'DELETE',
      path_or_endpoint: '/api/v1/cart/items/88',
      executed_url: 'http://test-gateway:8000/api/v1/cart/items/88',
      original_status_code: 204,
      replayed_status_code: 200,
      duration_ms: 1.2,
      was_mocked: false,
      mock_reason: null,
      was_write_blocked: true,
      replayed_response_body: '{"code": 0, "shadow_blocked": true, "message": "ATP 安全防护：写操作 [DELETE] 已被拦截"}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_6',
      traffic_id: 'trf_6',
      method: 'GET',
      path_or_endpoint: '/api/v1/user/profile',
      executed_url: 'http://test-gateway:8000/api/v1/user/profile',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 15.0,
      was_mocked: false,
      mock_reason: null,
      was_write_blocked: false,
      replayed_response_body: '{"user_id": 888, "role": "VIP"}',
      success: true,
      error_message: null,
    },
  ],
}

const filteredResults = computed(() => {
  if (!currentReport.value?.results) return []
  if (statusFilter.value === 'ALL') return currentReport.value.results
  if (statusFilter.value === 'BLOCKED_WRITE') return currentReport.value.results.filter(r => r.was_write_blocked)
  if (statusFilter.value === 'MOCKED') return currentReport.value.results.filter(r => r.was_mocked)
  if (statusFilter.value === 'FAILURE') return currentReport.value.results.filter(r => !r.success)
  return currentReport.value.results
})

const loadInitialData = async () => {
  loading.value = true
  try {
    // 1. 获取默认 Mock 规则
    const mockRes = await shadowReplayApi.getDefaultMockRules()
    defaultMockRules.value = mockRes.rules

    // 2. 获取历史回放批次
    const sessionsRes = await shadowReplayApi.listSessions()
    if (sessionsRes.sessions && sessionsRes.sessions.length > 0) {
      currentReport.value = sessionsRes.sessions[0]
    } else {
      currentReport.value = PRESET_REPORT
    }
  } catch {
    currentReport.value = PRESET_REPORT
    defaultMockRules.value = [
      { rule_id: 'mock_pay', name: '第三方支付网关拦截 (微信/支付宝)', pattern: '.*pay.*', mock_status_code: 200, mock_response_body: '{}', enabled: true },
      { rule_id: 'mock_sms', name: '短信与消息推送服务拦截', pattern: '.*sms.*', mock_status_code: 200, mock_response_body: '{}', enabled: true },
    ]
  } finally {
    loading.value = false
  }
}

const handleRunReplay = async () => {
  replaying.value = true
  try {
    const res = await shadowReplayApi.runReplay({
      target_base_url: targetBaseUrl.value,
      write_guard_mode: writeGuardMode.value,
      rate_limit_qps: rateLimitQps.value,
      timeout_sec: timeoutSec.value,
    })
    currentReport.value = res.report
    message.success(res.message || '影子流量无副作用回放完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '回放执行失败')
  } finally {
    replaying.value = false
  }
}

const applyPreset = (type: string) => {
  currentReport.value = PRESET_REPORT
  message.info(`已切换至预设回放报告 (${type})`)
}

const handleViewDetail = (item: any) => {
  selectedItem.value = item
  showDetailModal.value = true
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

/* 配置折叠 */
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

.config-col-full {
  grid-column: span 2;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
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

.qps-slider {
  flex: 1;
  margin: 6px 0;
}

.rate-val {
  font-size: 12px;
  font-weight: 700;
  color: #0284c7;
  width: 60px;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
}

.mode-opt {
  font-size: 11px;
  font-weight: 600;
}

.text-warning { color: #d97706; }
.text-primary { color: #0284c7; }
.text-danger { color: #dc2626; }
.text-info { color: #2563eb; }

.mock-rules-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}

.kpi-card {
  padding: 10px 12px;
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
  font-size: 20px;
  font-weight: 700;
  margin: 2px 0;
}

.kpi-sub {
  font-size: 10px;
  color: #94a3b8;
}

.text-default { color: #0284c7; }
.text-success { color: #16a34a; }
.text-purple { color: #7c3aed; }

/* 流水表格面板 */
.results-panel {
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

.target-url {
  font-size: 10px;
  font-family: monospace;
  color: #94a3b8;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 4px;
}

.arrow {
  color: #94a3b8;
  font-size: 11px;
}

.duration-text {
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

.mock-alert {
  padding: 6px 12px;
  background: #faf5ff;
  border: 1px solid #e9d5ff;
  border-radius: 4px;
  color: #7c3aed;
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
  max-height: 220px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
