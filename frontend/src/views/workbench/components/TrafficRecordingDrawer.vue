<template>
  <a-drawer
    :open="open"
    :width="920"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>微服务反向代理流量录制与抓包工作台</span>
    </template>
    <div class="traffic-recording-drawer">
      <!-- 头部控制栏：目标网关与启停控制 -->
      <a-card size="small" class="control-card">
        <a-form layout="inline" class="control-form">
          <a-form-item label="目标微服务 Base URL" required class="url-form-item">
            <a-input
              v-model:value="targetBaseUrl"
              placeholder="例如: http://api.internal:8000"
              :disabled="session?.is_recording"
              style="width: 280px"
            />
          </a-form-item>

          <a-form-item label="静音清洗">
            <a-switch
              v-model:checked="filterNoise"
              :disabled="session?.is_recording"
              checked-children="开启"
              un-checked-children="关闭"
            />
          </a-form-item>

          <a-form-item class="actions-form-item">
            <a-button
              v-if="!session?.is_recording"
              type="primary"
              :loading="loadingAction"
              @click="handleStartSession"
            >
              开始流量录制
            </a-button>
            <a-button
              v-else
              danger
              type="primary"
              :loading="loadingAction"
              @click="handleStopSession"
            >
              停止录制
            </a-button>

            <a-button
              v-if="session?.is_recording"
              class="simulate-btn"
              @click="handleSimulateIngest"
            >
              模拟抓包流入
            </a-button>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 状态与统计摘要指标卡 -->
      <div class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">录制状态</span>
          <div class="metric-value status-val">
            <span v-if="session?.is_recording" class="live-dot" />
            <a-tag :color="session?.is_recording ? 'success' : 'default'">
              {{ session?.is_recording ? '正在实时录制' : '空闲待命中' }}
            </a-tag>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">已捕获请求数</span>
          <div class="metric-value">
            <strong>{{ session?.total_captured ?? 0 }}</strong>
            <small class="metric-unit">次</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">噪声过滤清洗率</span>
          <div class="metric-value">
            <strong>{{ session?.noise_filtered_ratio_pct ?? 0 }}%</strong>
            <small class="metric-unit">静态/心跳</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">会话标识 (Session ID)</span>
          <div class="metric-value session-id-text">
            <code>{{ session?.session_id ? session.session_id.slice(0, 16) + '...' : '未初始化' }}</code>
          </div>
        </div>
      </div>

      <!-- 实时捕获流量列表流水 -->
      <a-card size="small" title="实时抓包流量流水与敏感凭据脱敏" class="traffic-table-card">
        <template #extra>
          <a-space>
            <a-tag color="blue">Authorization 已脱敏</a-tag>
            <a-tag color="purple">Cookie 已脱敏</a-tag>
          </a-space>
        </template>

        <a-table
          :data-source="session?.recorded_entries ?? []"
          :columns="columns"
          row-key="captured_at"
          size="small"
          :pagination="{ pageSize: 6 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'method'">
              <a-tag :color="getMethodColor(record.method)">
                {{ record.method }}
              </a-tag>
            </template>

            <template v-if="column.key === 'path'">
              <code class="path-code">{{ record.path }}</code>
            </template>

            <template v-if="column.key === 'status_code'">
              <a-badge
                :status="record.status_code >= 400 ? 'error' : 'success'"
                :text="String(record.status_code)"
              />
            </template>

            <template v-if="column.key === 'duration_ms'">
              <span>{{ record.duration_ms }} ms</span>
            </template>

            <template v-if="column.key === 'noise'">
              <a-tag v-if="record.is_noise_filtered" color="orange">已过滤</a-tag>
              <a-tag v-else color="green">有效业务流</a-tag>
            </template>
          </template>

          <template #expandedRowRender="{ record }">
            <div class="expanded-detail">
              <a-descriptions size="small" bordered :column="1">
                <a-descriptions-item label="请求头 (Headers)">
                  <pre class="json-box">{{ formatJson(record.headers) }}</pre>
                </a-descriptions-item>
                <a-descriptions-item v-if="record.request_body" label="请求体 (Request Body)">
                  <pre class="json-box">{{ formatJson(record.request_body) }}</pre>
                </a-descriptions-item>
                <a-descriptions-item v-if="record.response_body" label="响应体 (Response Body)">
                  <pre class="json-box">{{ formatJson(record.response_body) }}</pre>
                </a-descriptions-item>
              </a-descriptions>
            </div>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  trafficRecordingApi,
  type TrafficRecordingSession,
} from '@/api/trafficRecording'

const props = withDefaults(
  defineProps<{
    open: boolean
    projectId?: number
  }>(),
  {
    open: false,
    projectId: 1,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const targetBaseUrl = ref('http://127.0.0.1:8000')
const filterNoise = ref(true)
const loadingAction = ref(false)
const session = ref<TrafficRecordingSession | null>(null)

const columns = [
  { title: '请求方法', key: 'method', width: 90 },
  { title: '接口路径', key: 'path', ellipsis: true },
  { title: '状态码', key: 'status_code', width: 85 },
  { title: '耗时', key: 'duration_ms', width: 85 },
  { title: '清洗标记', key: 'noise', width: 100 },
  { title: '抓包时间', dataIndex: 'captured_at', key: 'captured_at', width: 180 },
]

function getMethodColor(method: string): string {
  switch (method.toUpperCase()) {
    case 'GET':
      return 'green'
    case 'POST':
      return 'blue'
    case 'PUT':
      return 'orange'
    case 'DELETE':
      return 'red'
    default:
      return 'default'
  }
}

function formatJson(val: any): string {
  if (!val) return '{}'
  if (typeof val === 'string') return val
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

function handleClose() {
  emit('update:open', false)
}

async function handleStartSession() {
  if (!targetBaseUrl.value.trim()) {
    message.warning('请输入目标微服务 Base URL')
    return
  }
  loadingAction.value = true
  try {
    const res = await trafficRecordingApi.startSession({
      project_id: props.projectId,
      target_base_url: targetBaseUrl.value.trim(),
      filter_noise: filterNoise.value,
    })
    session.value = res
    message.success('流量录制会话已启动！')
  } catch (err: any) {
    message.error(err.message || '启动流量录制失败')
  } finally {
    loadingAction.value = false
  }
}

async function handleStopSession() {
  if (!session.value) return
  loadingAction.value = true
  try {
    const res = await trafficRecordingApi.stopSession(session.value.session_id)
    session.value = res
    message.success('流量录制会话已停止！')
  } catch (err: any) {
    message.error(err.message || '停止流量录制失败')
  } finally {
    loadingAction.value = false
  }
}

async function handleSimulateIngest() {
  if (!session.value || !session.value.is_recording) return
  try {
    await trafficRecordingApi.ingestEntry(session.value.session_id, {
      method: 'POST',
      path: '/api/v1/orders/checkout',
      status_code: 201,
      duration_ms: 45,
      headers: {
        Authorization: 'Bearer ***REDACTED***',
        'Content-Type': 'application/json',
      },
      request_body: { item_id: 'prod_9872', quantity: 2 },
      response_body: { order_id: 'ord_20261016_01', status: 'created' },
    })
    // Refresh session data
    const updated = await trafficRecordingApi.getSession(session.value.session_id)
    session.value = updated
    message.success('已模拟注入一条微服务抓包业务流')
  } catch (err: any) {
    message.error(err.message || '模拟抓包失败')
  }
}
</script>

<style scoped>
.traffic-recording-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-card {
  border-radius: 8px;
  background: var(--c-bg-surface, #fff);
}

.control-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.url-form-item {
  margin-bottom: 0;
}

.actions-form-item {
  margin-bottom: 0;
  margin-left: auto;
}

.simulate-btn {
  margin-left: 8px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 12px;
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

.metric-unit {
  font-size: 12px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.status-val {
  font-size: 14px;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
}

.session-id-text code {
  font-size: 11px;
  color: #3b82f6;
}

.traffic-table-card {
  border-radius: 8px;
}

.path-code {
  font-family: monospace;
  font-size: 12px;
  color: var(--c-primary, #3b82f6);
}

.expanded-detail {
  padding: 8px 0;
}

.json-box {
  margin: 0;
  max-height: 140px;
  overflow-y: auto;
  font-size: 11px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 8px;
  border-radius: 4px;
}
</style>
