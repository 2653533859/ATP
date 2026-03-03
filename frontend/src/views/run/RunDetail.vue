<template>
  <div>
    <a-page-header title="执行详情" @back="router.back()">
      <template #extra>
        <a-tag v-if="run" :color="statusColor(run.status)" style="font-size: 14px">
          {{ run.status }}
        </a-tag>
        <a-spin v-if="isRunning" size="small" />
      </template>
    </a-page-header>

    <a-spin :spinning="loading">
      <template v-if="run">
        <!-- 基本信息 -->
        <a-descriptions bordered :column="4" size="small" style="margin-bottom: 24px">
          <a-descriptions-item label="执行 ID">{{ run.id }}</a-descriptions-item>
          <a-descriptions-item label="用例 ID">{{ run.case_id }}</a-descriptions-item>
          <a-descriptions-item label="环境">{{ run.environment ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="耗时">
            {{ run.duration_ms != null ? `${run.duration_ms} ms` : (isRunning ? '执行中...' : '-') }}
          </a-descriptions-item>
          <a-descriptions-item label="触发时间" :span="2">
            {{ run.created_at?.slice(0, 19).replace('T', ' ') }}
          </a-descriptions-item>
          <a-descriptions-item v-if="run.error_message" label="错误信息" :span="2">
            <span style="color: #ff4d4f">{{ run.error_message }}</span>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 步骤列表 -->
        <div class="steps-header">
          <strong>步骤详情</strong>
          <span style="color: #8c8c8c; font-size: 13px; margin-left: 8px">
            {{ steps.length }} 个步骤
          </span>
        </div>

        <a-collapse v-if="steps.length" :default-active-key="[0]">
          <a-collapse-panel
            v-for="step in steps"
            :key="step.step_index"
            :header="`[${step.step_index + 1}] ${step.name}`"
          >
            <template #extra>
              <a-space>
                <a-tag :color="statusColor(step.status)">{{ step.status }}</a-tag>
                <span v-if="step.duration_ms != null" style="color: #8c8c8c; font-size: 12px">
                  {{ step.duration_ms }} ms
                </span>
              </a-space>
            </template>

            <a-row :gutter="16">
              <!-- 请求 -->
              <a-col :span="12">
                <div class="panel-label">请求</div>
                <pre class="code-block">{{ formatJson(step.request_data) }}</pre>
              </a-col>
              <!-- 响应 -->
              <a-col :span="12">
                <div class="panel-label">响应</div>
                <pre class="code-block">{{ formatJson(step.response_data) }}</pre>
              </a-col>
            </a-row>

            <a-alert
              v-if="step.error_message"
              type="error"
              :message="step.error_message"
              style="margin-top: 12px"
              show-icon
            />

            <a-image v-if="step.screenshot_url" :src="step.screenshot_url" width="320" style="margin-top: 12px" />
          </a-collapse-panel>
        </a-collapse>

        <a-empty v-else description="暂无步骤数据" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
      </template>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Empty } from 'ant-design-vue'
import { runApi } from '@/api'
import { createRunWebSocket, type WsMessage } from '@/utils/websocket'

const router = useRouter()
const route = useRoute()
const runId = Number(route.params.runId)

const run = ref<any>(null)
const steps = ref<any[]>([])
const loading = ref(false)
let wsHandle: ReturnType<typeof createRunWebSocket> | null = null

const isRunning = computed(() => run.value?.status === 'running' || run.value?.status === 'pending')

function statusColor(status: string) {
  return (
    { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
  )
}

function formatJson(data: any) {
  if (data == null) return '-'
  return JSON.stringify(data, null, 2)
}

function applyWsMessage(msg: WsMessage) {
  if (msg.type === 'run_status') {
    if (run.value) run.value.status = msg.status
    return
  }

  if (msg.type === 'step_result' && msg.step) {
    const idx = steps.value.findIndex(s => s.step_index === msg.step!.step_index)
    if (idx >= 0) {
      steps.value[idx] = { ...steps.value[idx], ...msg.step }
    } else {
      steps.value.push(msg.step)
      steps.value.sort((a, b) => a.step_index - b.step_index)
    }
    return
  }

  if (msg.type === 'completed') {
    if (run.value) {
      run.value.status = msg.status
      if (msg.duration_ms != null) run.value.duration_ms = msg.duration_ms
    }
    wsHandle?.close()
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const data = await runApi.get(runId) as any
    run.value = data
    steps.value = data.steps ?? []
  } finally {
    loading.value = false
  }

  // 执行中或刚触发才订阅 WebSocket
  if (run.value?.status === 'pending' || run.value?.status === 'running') {
    wsHandle = createRunWebSocket(runId, applyWsMessage, () => {
      // WebSocket 关闭时拉一次最新数据，确保最终状态正确
      runApi.get(runId).then((d: any) => {
        run.value = d
        steps.value = d.steps ?? []
      })
    })
  }
})

onUnmounted(() => {
  wsHandle?.close()
})
</script>

<style scoped>
.steps-header {
  margin-bottom: 12px;
}
.panel-label {
  font-weight: 600;
  margin-bottom: 6px;
  color: #595959;
}
.code-block {
  background: #f5f5f5;
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
