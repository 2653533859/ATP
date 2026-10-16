<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="生产流量 OpenAPI 3.0 / Protobuf 3 动态逆向推导与代码预览控制台"
    destroy-on-close
    class="live-contract-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="drawer-banner">
        <div class="banner-title">
          <BranchesOutlined class="banner-icon" />
          <span>生产流量接口契约动态逆向推导引擎 (Live Traffic Contract Schema Extractor)</span>
        </div>
        <p class="banner-desc">
          从微服务网关旁路捕获的海量真实调用流量中，通过自适应多样本归纳算法自动推导字段类型、必填性（<code>required</code>）与枚举约束（<code>enum</code>）。一键生成标准的 <strong>OpenAPI 3.0</strong> 规范与 <strong>Protobuf 3</strong> IDL 接口定义，彻底解决开发设计文档滞后与线上隐藏参数盲区。
        </p>
      </div>

      <!-- 操作与预设栏 -->
      <div class="controls-bar">
        <div class="controls-left">
          <span class="ctrl-label">被测接口端点:</span>
          <a-input v-model:value="currentEndpoint" placeholder="POST /api/v1/orders/checkout" style="width: 260px" size="small" />
          <a-space size="small">
            <a-button size="small" @click="applyPreset('orders')">
              示例 1: 订单结算 (含必填/枚举/双响应码)
            </a-button>
            <a-button size="small" @click="applyPreset('users')">
              示例 2: 用户资料 (含Query参数与Protobuf)
            </a-button>
          </a-space>
        </div>

        <div class="controls-right">
          <a-space size="small">
            <a-button size="small" :loading="loading" @click="loadInitialData">
              <ReloadOutlined /> 刷新
            </a-button>
            <a-button type="primary" size="small" :loading="extracting" @click="handleRunExtract">
              <ThunderboltOutlined /> 一键逆向提取契约
            </a-button>
          </a-space>
        </div>
      </div>

      <a-spin :spinning="extracting || loading">
        <div v-if="currentContract" class="contract-content">
          <!-- 核心指标 KPI 看板 (4 大卡片) -->
          <div class="kpi-grid">
            <div class="kpi-card">
              <span class="kpi-label">归纳样本总数</span>
              <span class="kpi-val text-default">{{ currentContract.samples_count }} 条</span>
              <span class="kpi-sub">海量真实流量提炼</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">推导必填字段数</span>
              <span class="kpi-val text-success">{{ requiredFieldsCount }} 个</span>
              <span class="kpi-sub">100% 出现率强约束</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">自动识别枚举字段</span>
              <span class="kpi-val text-purple">{{ enumFieldsCount }} 个</span>
              <span class="kpi-sub">固定候选范围归纳</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">响应状态码分支</span>
              <span class="kpi-val text-info">{{ Object.keys(currentContract.response_schemas || {}).length }} 个</span>
              <span class="kpi-sub">覆盖正常与异常分支</span>
            </div>
          </div>

          <!-- 双选项卡：OpenAPI 3.0 规范树 vs Protobuf 3 IDL 定义 -->
          <div class="tabs-card">
            <a-tabs v-model:activeKey="activeTabKey" class="contract-tabs">
              <!-- Tab 1: OpenAPI 3.0 规范 -->
              <a-tab-pane key="openapi" tab="📘 OpenAPI 3.0 JSON Schema 契约规范">
                <div class="tab-pane-content">
                  <!-- 请求体字段属性表 -->
                  <div class="schema-block">
                    <div class="block-header">
                      <span class="block-title">📥 Request Body 属性规范 (请求体)</span>
                      <a-tag v-if="requiredFieldsCount > 0" color="red" size="small">
                        含 {{ requiredFieldsCount }} 项必需传参
                      </a-tag>
                    </div>

                    <a-table
                      :data-source="requestPropertiesList"
                      :columns="propertyColumns"
                      row-key="name"
                      size="small"
                      :pagination="false"
                      class="props-table"
                    >
                      <template #bodyCell="{ column, record }">
                        <template v-if="column.key === 'name'">
                          <span class="prop-name">{{ record.name }}</span>
                        </template>

                        <template v-else-if="column.key === 'type'">
                          <a-tag color="blue" size="small">{{ record.type }}</a-tag>
                          <a-tag v-if="record.format" color="cyan" size="small">{{ record.format }}</a-tag>
                        </template>

                        <template v-else-if="column.key === 'required'">
                          <a-tag :color="record.required ? 'red' : 'default'" size="small">
                            {{ record.required ? '必填 (Required)' : '可选 (Optional)' }}
                          </a-tag>
                        </template>

                        <template v-else-if="column.key === 'enum'">
                          <span v-if="record.enum && record.enum.length > 0">
                            <a-tag v-for="e in record.enum" :key="e" color="purple" size="small">
                              {{ e }}
                            </a-tag>
                          </span>
                          <span v-else class="text-muted">-</span>
                        </template>
                      </template>
                    </a-table>
                  </div>

                  <!-- 响应体分支规范 -->
                  <div class="schema-block">
                    <div class="block-header">
                      <span class="block-title">📤 Response Body 分支规范 (响应体)</span>
                      <span class="block-sub">共覆盖 {{ Object.keys(currentContract.response_schemas || {}).length }} 个响应码分支</span>
                    </div>

                    <div class="response-status-accordion">
                      <div
                        v-for="(schema, st) in currentContract.response_schemas"
                        :key="st"
                        class="status-resp-box"
                      >
                        <div class="status-resp-header">
                          <a-tag :color="Number(st) >= 400 ? 'red' : 'green'">HTTP {{ st }}</a-tag>
                          <span class="status-desc">{{ Number(st) === 200 ? '正常业务响应' : '异常或校验失败分支' }}</span>
                        </div>
                        <pre class="schema-pre"><code>{{ JSON.stringify(schema, null, 2) }}</code></pre>
                      </div>
                    </div>
                  </div>

                  <!-- 完整 OpenAPI 3.0 Schema 导出框 -->
                  <div class="raw-code-box">
                    <div class="box-header">
                      <span>完整 OpenAPI 3.0 请求体 Schema JSON:</span>
                      <a-button size="small" type="link" @click="copyCode(JSON.stringify(currentContract.request_schema, null, 2))">
                        <CopyOutlined /> 复制 OpenAPI JSON
                      </a-button>
                    </div>
                    <pre class="raw-pre"><code>{{ JSON.stringify(currentContract.request_schema, null, 2) }}</code></pre>
                  </div>
                </div>
              </a-tab-pane>

              <!-- Tab 2: Protobuf 3 IDL 定义 -->
              <a-tab-pane key="protobuf" tab="⚡ 原生 Protobuf 3 IDL 语法定义">
                <div class="tab-pane-content">
                  <div class="raw-code-box proto-box">
                    <div class="box-header">
                      <span class="proto-title">
                        <CodeOutlined /> 自动生成的标准 Protobuf 3 接口消息定义 (IDL)
                      </span>
                      <a-button size="small" type="primary" @click="copyCode(currentContract.protobuf_definition)">
                        <CopyOutlined /> 复制 Protobuf 3 代码
                      </a-button>
                    </div>
                    <pre class="proto-pre"><code>{{ currentContract.protobuf_definition }}</code></pre>
                  </div>
                </div>
              </a-tab-pane>
            </a-tabs>
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
  BranchesOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  CodeOutlined,
} from '@ant-design/icons-vue'
import {
  liveContractApi,
  type ExtractedContractItem,
} from '@/api/trafficGateway'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const extracting = ref(false)
const activeTabKey = ref<'openapi' | 'protobuf'>('openapi')
const currentEndpoint = ref('POST /api/v1/orders/checkout')

const currentContract = ref<ExtractedContractItem | null>(null)

const propertyColumns = [
  { title: '字段名称', key: 'name', width: 220 },
  { title: '数据类型 & 格式', key: 'type', width: 160 },
  { title: '必填约束', key: 'required', width: 150 },
  { title: '识别枚举候选值', key: 'enum' },
]

// 预设样例数据
const PRESET_ORDERS_CONTRACT: ExtractedContractItem = {
  contract_id: 'ct_demo_order_101',
  endpoint: 'POST /api/v1/orders/checkout',
  method: 'POST',
  path: '/api/v1/orders/checkout',
  protocol: 'HTTP',
  samples_count: 5,
  request_schema: {
    type: 'object',
    properties: {
      order_id: { type: 'integer', format: 'int64' },
      amount: { type: 'number', format: 'double' },
      channel: { type: 'string', enum: ['APP', 'H5', 'WEB'] },
      buyer_email: { type: 'string', format: 'email' },
      coupon_code: { type: 'string' },
    },
    required: ['amount', 'buyer_email', 'order_id'],
  },
  response_schemas: {
    '200': {
      type: 'object',
      properties: {
        code: { type: 'integer' },
        status: { type: 'string', enum: ['CREATED', 'PAID'] },
        trade_no: { type: 'string', format: 'uuid' },
      },
      required: ['code', 'status', 'trade_no'],
    },
    '400': {
      type: 'object',
      properties: {
        code: { type: 'integer' },
        error: { type: 'string' },
      },
      required: ['code', 'error'],
    },
  },
  query_parameters: [
    { name: 'channel', type: 'string', required: false },
  ],
  header_parameters: [
    { name: 'content-type', type: 'string', required: true },
    { name: 'authorization', type: 'string', required: true },
  ],
  protobuf_definition: `syntax = "proto3";\n\nmessage Post_api_v1_orders_checkout_request {\n  double amount = 1;\n  string buyer_email = 2;\n  string channel = 3;\n  string coupon_code = 4;\n  int64 order_id = 5;\n}`,
  extracted_at: '2026-10-16T12:00:00Z',
}

const PRESET_USERS_CONTRACT: ExtractedContractItem = {
  contract_id: 'ct_demo_user_102',
  endpoint: 'GET /api/v1/users/profile',
  method: 'GET',
  path: '/api/v1/users/profile',
  protocol: 'HTTP',
  samples_count: 4,
  request_schema: {
    type: 'object',
    properties: {},
  },
  response_schemas: {
    '200': {
      type: 'object',
      properties: {
        user_id: { type: 'integer' },
        username: { type: 'string' },
        role: { type: 'string', enum: ['ADMIN', 'OPERATOR', 'VIEWER'] },
        last_login_at: { type: 'string', format: 'date-time' },
      },
      required: ['role', 'user_id', 'username'],
    },
  },
  query_parameters: [
    { name: 'user_id', type: 'integer', required: true },
  ],
  header_parameters: [
    { name: 'authorization', type: 'string', required: true },
  ],
  protobuf_definition: `syntax = "proto3";\n\nmessage Get_api_v1_users_profile_request {\n}`,
  extracted_at: '2026-10-16T12:05:00Z',
}

const requiredFieldsCount = computed(() => {
  return currentContract.value?.request_schema?.required?.length || 0
})

const enumFieldsCount = computed(() => {
  const props = currentContract.value?.request_schema?.properties || {}
  return Object.values(props).filter((p: any) => p.enum && p.enum.length > 0).length
})

const requestPropertiesList = computed(() => {
  if (!currentContract.value?.request_schema?.properties) return []
  const reqSet = new Set(currentContract.value.request_schema.required || [])
  return Object.entries(currentContract.value.request_schema.properties).map(([k, v]: [string, any]) => ({
    name: k,
    type: v.type,
    format: v.format,
    required: reqSet.has(k),
    enum: v.enum || [],
  }))
})

const applyPreset = (type: 'orders' | 'users') => {
  if (type === 'orders') {
    currentEndpoint.value = 'POST /api/v1/orders/checkout'
    currentContract.value = PRESET_ORDERS_CONTRACT
  } else {
    currentEndpoint.value = 'GET /api/v1/users/profile'
    currentContract.value = PRESET_USERS_CONTRACT
  }
  message.info(`已切换至「${type === 'orders' ? '订单结算' : '用户资料'}」契约预设`)
}

const loadInitialData = async () => {
  loading.value = true
  try {
    const res = await liveContractApi.listContracts()
    if (res.contracts && res.contracts.length > 0) {
      currentContract.value = res.contracts[0]
      currentEndpoint.value = res.contracts[0].endpoint
    } else {
      currentContract.value = PRESET_ORDERS_CONTRACT
    }
  } catch {
    currentContract.value = PRESET_ORDERS_CONTRACT
  } finally {
    loading.value = false
  }
}

const handleRunExtract = async () => {
  extracting.value = true
  try {
    const res = await liveContractApi.extractBatch({ limit_captured: 100 })
    if (res.report && res.report.contracts.length > 0) {
      currentContract.value = res.report.contracts[0]
      currentEndpoint.value = res.report.contracts[0].endpoint
    }
    message.success(res.message || '全网接口契约逆向推导完成')
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || '契约推导失败')
  } finally {
    extracting.value = false
  }
}

const copyCode = (code: string) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(code)
    message.success('已复制到剪贴板')
  } else {
    message.info('当前环境不支持自动剪贴板，请手动复制')
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
  flex-wrap: wrap;
}

.ctrl-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.contract-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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
.text-purple { color: #7c3aed; }
.text-info { color: #2563eb; }

/* 标签页与内容卡片 */
.tabs-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  padding: 12px 16px;
}

.tab-pane-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.schema-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.block-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.block-sub {
  font-size: 11px;
  color: #64748b;
}

.prop-name {
  font-weight: 600;
  color: #0f172a;
}

.text-muted {
  color: #94a3b8;
}

/* 响应码手风琴 */
.response-status-accordion {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.status-resp-box {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.status-resp-header {
  padding: 6px 10px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-desc {
  font-size: 11px;
  color: #64748b;
}

.schema-pre {
  margin: 0;
  padding: 8px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  background: #1e293b;
  color: #f8fafc;
  max-height: 140px;
  overflow-y: auto;
}

/* 源码框 */
.raw-code-box {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}

.box-header {
  padding: 8px 12px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.proto-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.raw-pre,
.proto-pre {
  margin: 0;
  padding: 12px;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
  background: #1e293b;
  color: #38bdf8;
  max-height: 280px;
  overflow-y: auto;
}

.proto-pre {
  color: #4ade80;
}
</style>
