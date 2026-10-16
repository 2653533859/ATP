<template>
  <a-drawer
    :open="open"
    :width="960"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <div class="drawer-title-box">
        <span>瞬时轻量级多协议仿真沙箱与端口生命周期管理</span>
        <a-tag color="cyan">20000~29999 端口动态池</a-tag>
      </div>
    </template>

    <div class="ephemeral-sandbox-manager-drawer">
      <!-- 头部控制栏：一键拉起沙箱与配置 -->
      <a-card size="small" class="provision-card">
        <div class="provision-header">
          <h4 class="title">瞬时仿真沙箱快速拉起 (On-demand Ephemeral Sandbox)</h4>
          <p class="subtitle">
            支持基于操作系统底层 `SO_REUSEADDR` 端口防冲突探测算法，在 20000~29999 端口区间动态开辟独立沙箱环境；支持 HTTP、gRPC、WebSocket 单协议及多协议混合仿真与过期自动化安全收割。
          </p>
        </div>

        <a-form layout="inline" class="provision-form">
          <a-form-item label="沙箱会话名称" required>
            <a-input
              v-model:value="newSessionName"
              placeholder="如：订单结算链路瞬时沙箱"
              size="small"
              style="width: 200px"
            />
          </a-form-item>

          <a-form-item label="协议类型">
            <a-select v-model:value="newProtocol" size="small" style="width: 140px">
              <a-select-option value="http">HTTP / REST</a-select-option>
              <a-select-option value="grpc">gRPC 协议</a-select-option>
              <a-select-option value="websocket">WebSocket</a-select-option>
              <a-select-option value="multi_protocol">混合多协议</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="生命周期 TTL">
            <a-input-number
              v-model:value="newTtlSeconds"
              :min="10"
              :max="3600"
              size="small"
              style="width: 80px"
            />
            <span class="unit-label">秒</span>
          </a-form-item>

          <a-form-item>
            <a-space size="small">
              <a-button
                type="primary"
                size="small"
                :loading="provisioning"
                @click="handleProvision"
              >
                一键拉起沙箱
              </a-button>
              <a-button
                danger
                size="small"
                :loading="reaping"
                @click="handleReapExpired"
              >
                过期自动收割 (Reap)
              </a-button>
              <a-button size="small" :loading="loading" @click="loadSandboxes">
                刷新列表
              </a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 沙箱池运行水位 KPI 概览 -->
      <div class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">活跃运行沙箱 (Active)</span>
          <div class="metric-value">
            <span class="live-dot" />
            <strong class="text-green">{{ activeSandboxesCount }}</strong>
            <small class="unit">个实例</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">端口占用总数 (Ports Allocated)</span>
          <div class="metric-value">
            <strong class="text-blue">{{ allocatedPortsCount }}</strong>
            <small class="unit">个端口 (20000~29999)</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">已过期待收割 (Expired)</span>
          <div class="metric-value">
            <strong :class="expiredSandboxesCount > 0 ? 'text-orange' : 'text-slate'">
              {{ expiredSandboxesCount }}
            </strong>
            <small class="unit">个待释放</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">协议分布过滤</span>
          <div class="filter-box">
            <a-select v-model:value="protocolFilter" size="small" style="width: 140px" @change="loadSandboxes">
              <a-select-option value="">全部协议</a-select-option>
              <a-select-option value="http">HTTP</a-select-option>
              <a-select-option value="grpc">gRPC</a-select-option>
              <a-select-option value="websocket">WebSocket</a-select-option>
              <a-select-option value="multi_protocol">多协议</a-select-option>
            </a-select>
          </div>
        </div>
      </div>

      <!-- 沙箱实例流水表格 -->
      <a-card size="small" title="瞬时仿真沙箱生命周期流水" class="sandboxes-table-card">
        <a-table
          :data-source="sandboxes"
          :columns="columns"
          row-key="sandbox_id"
          size="small"
          :pagination="{ pageSize: 6 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'session_name'">
              <div class="sandbox-title-cell">
                <strong>{{ record.session_name }}</strong>
                <code class="sandbox-id">{{ record.sandbox_id }}</code>
              </div>
            </template>

            <template v-if="column.key === 'protocol'">
              <a-tag :color="getProtocolColor(record.protocol)">
                {{ record.protocol.toUpperCase() }}
              </a-tag>
            </template>

            <template v-if="column.key === 'endpoint'">
              <div class="endpoint-cell">
                <span class="port-badge">端口 {{ record.allocated_port }}</span>
                <code class="url-text">{{ record.base_url }}</code>
              </div>
            </template>

            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusLabel(record.status) }}
              </a-tag>
            </template>

            <template v-if="column.key === 'actions'">
              <a-space size="small">
                <a-button
                  v-if="record.status !== 'terminated'"
                  size="small"
                  type="link"
                  @click="openMockTest(record)"
                >
                  Mock 测试
                </a-button>
                <a-button
                  v-if="record.status !== 'terminated'"
                  size="small"
                  type="link"
                  danger
                  @click="handleTerminate(record.sandbox_id)"
                >
                  释放
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 流量镜像与写操作副作用安全隔离卡片 -->
      <SandboxTrafficMirrorCard />

      <!-- 内联 Mock 派发测试弹窗 -->
      <a-modal
        v-model:open="mockModalOpen"
        :title="`沙箱 Mock 路由测试 - ${selectedSandbox?.session_name || ''}`"
        :footer="null"
        width="620px"
        destroy-on-close
      >
        <div class="mock-test-box">
          <div class="mock-req-bar">
            <a-select v-model:value="mockMethod" size="small" style="width: 100px">
              <a-select-option value="GET">GET</a-select-option>
              <a-select-option value="POST">POST</a-select-option>
              <a-select-option value="PUT">PUT</a-select-option>
              <a-select-option value="DELETE">DELETE</a-select-option>
            </a-select>
            <a-input
              v-model:value="mockPath"
              placeholder="请求路径如 /api/v1/orders"
              size="small"
              style="flex: 1"
            />
            <a-button type="primary" size="small" :loading="dispatching" @click="handleDispatchMock">
              发送测试
            </a-button>
          </div>

          <div v-if="mockResult" class="mock-result-box">
            <div class="result-title">响应数据 (Mock Response):</div>
            <pre class="json-preview">{{ JSON.stringify(mockResult, null, 2) }}</pre>
          </div>
        </div>
      </a-modal>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  sandboxesApi,
  type EphemeralSandboxItem,
  type SandboxProtocol,
  type SandboxStatus,
  type MockDispatchResult,
} from '@/api/sandboxes'
import SandboxTrafficMirrorCard from './SandboxTrafficMirrorCard.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const provisioning = ref(false)
const reaping = ref(false)
const dispatching = ref(false)

const protocolFilter = ref('')
const newSessionName = ref('核心结算链路瞬时仿真沙箱')
const newProtocol = ref<SandboxProtocol>('http')
const newTtlSeconds = ref(300)

const sandboxes = ref<EphemeralSandboxItem[]>([])
const selectedSandbox = ref<EphemeralSandboxItem | null>(null)
const mockModalOpen = ref(false)
const mockMethod = ref('GET')
const mockPath = ref('/api/v1/resource')
const mockResult = ref<MockDispatchResult | null>(null)

const columns = [
  { title: '沙箱名称 / 标识', key: 'session_name', width: 220 },
  { title: '协议类型', key: 'protocol', width: 100 },
  { title: '端口与仿真基地址', key: 'endpoint', width: 260 },
  { title: '生命周期状态', key: 'status', width: 120 },
  { title: '操作', key: 'actions', width: 140 },
]

const activeSandboxesCount = computed(
  () => sandboxes.value.filter((s) => s.status === 'ready' || s.status === 'active').length
)
const allocatedPortsCount = computed(
  () => sandboxes.value.filter((s) => s.status !== 'terminated').length
)
const expiredSandboxesCount = computed(
  () => sandboxes.value.filter((s) => s.status === 'expired' || s.is_expired).length
)

function getProtocolColor(proto: SandboxProtocol): string {
  switch (proto) {
    case 'http':
      return 'blue'
    case 'grpc':
      return 'purple'
    case 'websocket':
      return 'orange'
    case 'multi_protocol':
      return 'cyan'
    default:
      return 'default'
  }
}

function getStatusColor(status: SandboxStatus): string {
  switch (status) {
    case 'ready':
      return 'green'
    case 'active':
      return 'blue'
    case 'expired':
      return 'orange'
    case 'terminated':
      return 'default'
    default:
      return 'default'
  }
}

function getStatusLabel(status: SandboxStatus): string {
  switch (status) {
    case 'ready':
      return '就绪就绪 (ready)'
    case 'active':
      return '运行中 (active)'
    case 'expired':
      return '已过期 (expired)'
    case 'terminated':
      return '已释放 (terminated)'
    default:
      return status
  }
}

function handleClose() {
  emit('update:open', false)
}

async function loadSandboxes() {
  loading.value = true
  try {
    const res = await sandboxesApi.list(protocolFilter.value || undefined)
    sandboxes.value = res.sandboxes
  } catch (err: any) {
    message.error(err.message || '获取沙箱列表失败')
  } finally {
    loading.value = false
  }
}

async function handleProvision() {
  if (!newSessionName.value) {
    message.warning('请输入沙箱会话名称')
    return
  }
  provisioning.value = true
  try {
    const res = await sandboxesApi.provision({
      session_name: newSessionName.value,
      protocol: newProtocol.value,
      ttl_seconds: newTtlSeconds.value,
      mock_rules: [
        {
          method: 'GET',
          path: '/api/v1/resource',
          status_code: 200,
          response_body: { message: 'Mock response from ephemeral sandbox', status: 'mock_ok' },
        },
      ],
    })
    message.success(`沙箱拉起成功！已动态分配端口：${res.sandbox.allocated_port}`)
    await loadSandboxes()
  } catch (err: any) {
    message.error(err.message || '拉起沙箱失败')
  } finally {
    provisioning.value = false
  }
}

async function handleReapExpired() {
  reaping.value = true
  try {
    const res = await sandboxesApi.reapExpired()
    message.success(`过期收割完成！成功释放 ${res.reaped_count} 个已过期沙箱。`)
    await loadSandboxes()
  } catch (err: any) {
    message.error(err.message || '收割过期沙箱失败')
  } finally {
    reaping.value = false
  }
}

async function handleTerminate(sandboxId: string) {
  try {
    await sandboxesApi.terminate(sandboxId)
    message.success('沙箱已安全终止，端口已回收释放！')
    await loadSandboxes()
  } catch (err: any) {
    message.error(err.message || '释放沙箱失败')
  }
}

function openMockTest(sandbox: any) {
  selectedSandbox.value = sandbox
  mockMethod.value = 'GET'
  mockPath.value = '/api/v1/resource'
  mockResult.value = null
  mockModalOpen.value = true
}

async function handleDispatchMock() {
  if (!selectedSandbox.value) return
  dispatching.value = true
  try {
    const res = await sandboxesApi.mockDispatch(selectedSandbox.value.sandbox_id, {
      method: mockMethod.value,
      path: mockPath.value,
    })
    mockResult.value = res
    message.success('Mock 派发成功！')
  } catch (err: any) {
    message.error(err.message || 'Mock 派发测试失败')
  } finally {
    dispatching.value = false
  }
}

onMounted(() => {
  loadSandboxes()
})
</script>

<style scoped>
.ephemeral-sandbox-manager-drawer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.provision-card,
.sandboxes-table-card {
  border-radius: 8px;
}

.provision-header {
  margin-bottom: 10px;
}

.title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.provision-form {
  margin-top: 6px;
}

.unit-label {
  font-size: 11px;
  color: #64748b;
  margin-left: 4px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  display: block;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  color: var(--c-text, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.unit {
  font-size: 11px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
}

.text-green {
  color: #16a34a;
}

.text-blue {
  color: #2563eb;
}

.text-orange {
  color: #ea580c;
}

.text-slate {
  color: #64748b;
}

.sandbox-title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sandbox-id {
  font-size: 10px;
  color: #94a3b8;
  font-family: monospace;
}

.endpoint-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.port-badge {
  font-size: 10px;
  font-weight: 600;
  color: #2563eb;
}

.url-text {
  font-size: 11px;
  font-family: monospace;
  color: #334155;
}

.mock-test-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 10px;
}

.mock-req-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mock-result-box {
  background: #0f172a;
  border-radius: 6px;
  padding: 10px;
}

.result-title {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.json-preview {
  margin: 0;
  color: #38bdf8;
  font-size: 11px;
  font-family: monospace;
  max-height: 220px;
  overflow-y: auto;
}
</style>
