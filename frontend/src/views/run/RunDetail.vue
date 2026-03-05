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

        <!-- 步骤统计 -->
        <div class="steps-header">
          <strong>步骤详情</strong>
          <span class="steps-summary">
            共 {{ steps.length }} 步
            <template v-if="stepStats.passed > 0">
              <span class="stat-passed">{{ stepStats.passed }} 通过</span>
            </template>
            <template v-if="stepStats.failed > 0">
              <span class="stat-failed">{{ stepStats.failed }} 失败</span>
            </template>
            <template v-if="stepStats.error > 0">
              <span class="stat-error">{{ stepStats.error }} 异常</span>
            </template>
            <template v-if="stepStats.skipped > 0">
              <span class="stat-skipped">{{ stepStats.skipped }} 跳过</span>
            </template>
          </span>
        </div>

        <!-- 步骤进度条 -->
        <div v-if="steps.length" class="steps-progress">
          <div
            v-for="step in steps"
            :key="step.step_index"
            :class="['progress-segment', `segment-${step.status}`]"
            :style="{ flex: Math.max(step.duration_ms ?? 1, 1) }"
            :title="`#${step.step_index + 1} ${step.name} (${step.status}, ${step.duration_ms ?? 0}ms)`"
          />
        </div>

        <!-- 录像播放 -->
        <div v-if="run.result_summary?.video_url" class="video-section">
          <a-divider orientation="left" style="margin: 16px 0 12px">
            <VideoCameraOutlined /> 执行录像
          </a-divider>
          <video
            :src="run.result_summary.video_url"
            controls
            class="video-player"
          >
            您的浏览器不支持 video 标签
          </video>
        </div>

        <a-collapse
          v-if="steps.length"
          :activeKey="expandedKeys"
          @change="onCollapseChange"
        >
          <a-collapse-panel
            v-for="step in steps"
            :key="step.step_index"
            :class="{ 'step-failed': step.status === 'failed', 'step-error': step.status === 'error' }"
          >
            <template #header>
              <div class="step-panel-header">
                <span class="step-number">#{{ step.step_index + 1 }}</span>
                <span class="step-name">{{ step.name }}</span>
              </div>
            </template>
            <template #extra>
              <a-space>
                <a-tag :color="statusColor(step.status)">{{ step.status }}</a-tag>
                <span v-if="step.duration_ms != null" class="step-duration">
                  {{ step.duration_ms }} ms
                </span>
              </a-space>
            </template>

            <!-- 错误信息优先展示 -->
            <a-alert
              v-if="step.error_message"
              type="error"
              :message="step.error_message"
              style="margin-bottom: 12px"
              show-icon
            />

            <!-- 截图展示 -->
            <div v-if="step.screenshot_url" class="screenshot-section">
              <div class="panel-label">
                <CameraOutlined /> 截图
              </div>
              <a-image
                :src="step.screenshot_url"
                :width="480"
                :preview="{ src: step.screenshot_url }"
                class="step-screenshot"
                :fallback="fallbackImage"
              />
            </div>

            <a-row :gutter="16" style="margin-top: 12px">
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
import { VideoCameraOutlined, CameraOutlined } from '@ant-design/icons-vue'
import { runApi } from '@/api'
import { createRunWebSocket, type WsMessage } from '@/utils/websocket'

const router = useRouter()
const route = useRoute()
const runId = Number(route.params.runId)

const run = ref<any>(null)
const steps = ref<any[]>([])
const loading = ref(false)
const expandedKeys = ref<number[]>([])
let wsHandle: ReturnType<typeof createRunWebSocket> | null = null

const fallbackImage = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5IiBmb250LXNpemU9IjE0Ij7miKrlm77liqDovb3lpLHotKU8L3RleHQ+PC9zdmc+'

const isRunning = computed(() => run.value?.status === 'running' || run.value?.status === 'pending')

const stepStats = computed(() => {
  const stats = { passed: 0, failed: 0, error: 0, skipped: 0 }
  for (const s of steps.value) {
    if (s.status === 'passed') stats.passed++
    else if (s.status === 'failed') stats.failed++
    else if (s.status === 'error') stats.error++
    else if (s.status === 'skipped') stats.skipped++
  }
  return stats
})

function statusColor(status: string) {
  return (
    { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
  )
}

function formatJson(data: any) {
  if (data == null) return '-'
  return JSON.stringify(data, null, 2)
}

function computeExpandedKeys(stepList: any[]) {
  // 自动展开失败和异常步骤；如果全部通过则展开第一步
  const failedKeys = stepList
    .filter(s => s.status === 'failed' || s.status === 'error')
    .map(s => s.step_index)
  if (failedKeys.length > 0) return failedKeys
  return stepList.length > 0 ? [stepList[0].step_index] : []
}

function onCollapseChange(keys: any) {
  expandedKeys.value = keys
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
    expandedKeys.value = computeExpandedKeys(steps.value)
    return
  }

  if (msg.type === 'completed') {
    if (run.value) {
      run.value.status = msg.status
      if (msg.duration_ms != null) run.value.duration_ms = msg.duration_ms
      if (msg.video_url) {
        run.value.result_summary = {
          ...(run.value.result_summary || {}),
          video_url: msg.video_url,
        }
      }
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
    expandedKeys.value = computeExpandedKeys(steps.value)
  } finally {
    loading.value = false
  }

  if (run.value?.status === 'pending' || run.value?.status === 'running') {
    wsHandle = createRunWebSocket(runId, applyWsMessage, () => {
      runApi.get(runId).then((d: any) => {
        run.value = d
        steps.value = d.steps ?? []
        expandedKeys.value = computeExpandedKeys(steps.value)
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
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}
.steps-summary {
  color: #8c8c8c;
  font-size: 13px;
  margin-left: 12px;
  display: flex;
  gap: 10px;
}
.stat-passed { color: #52c41a; font-weight: 500; }
.stat-failed { color: #ff4d4f; font-weight: 500; }
.stat-error { color: #fa8c16; font-weight: 500; }
.stat-skipped { color: #8c8c8c; font-weight: 500; }

/* 步骤进度条 */
.steps-progress {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 16px;
  gap: 2px;
}
.progress-segment {
  min-width: 4px;
  border-radius: 2px;
  transition: opacity 0.2s;
}
.progress-segment:hover {
  opacity: 0.75;
}
.segment-passed { background: #52c41a; }
.segment-failed { background: #ff4d4f; }
.segment-error { background: #fa8c16; }
.segment-running { background: #1890ff; }
.segment-pending { background: #d9d9d9; }
.segment-skipped { background: #bfbfbf; }

/* 失败/异常步骤高亮 */
.step-failed :deep(.ant-collapse-header) {
  background: #fff2f0 !important;
  border-left: 3px solid #ff4d4f !important;
}
.step-error :deep(.ant-collapse-header) {
  background: #fff7e6 !important;
  border-left: 3px solid #fa8c16 !important;
}

.step-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-number {
  font-weight: 600;
  color: #8c8c8c;
  min-width: 28px;
}
.step-name {
  font-weight: 500;
}
.step-duration {
  color: #8c8c8c;
  font-size: 12px;
}

/* 截图区域 */
.screenshot-section {
  margin-bottom: 12px;
}
.step-screenshot {
  border-radius: 6px;
  border: 1px solid #f0f0f0;
  cursor: pointer;
}

/* 录像播放 */
.video-section {
  margin-bottom: 16px;
}
.video-player {
  width: 100%;
  max-width: 800px;
  border-radius: 8px;
  background: #000;
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
