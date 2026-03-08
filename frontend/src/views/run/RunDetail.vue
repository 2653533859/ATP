<template>
  <div>
    <a-page-header title="执行详情" @back="router.back()">
      <template #extra>
        <a-space>
          <a-button size="small" :loading="exportingHtml" @click="handleExportHtml">
            <FileTextOutlined /> {{ exportingHtml ? '生成中...' : '导出 HTML' }}
          </a-button>
          <a-button size="small" :loading="exportingPdf" @click="handleExportPdf">
            <FilePdfOutlined /> {{ exportingPdf ? '正在生成 PDF...' : '导出 PDF' }}
          </a-button>
          <a-button
            v-if="canCreateBug && run && (run.status === 'failed' || run.status === 'error')"
            size="small"
            type="primary"
            danger
            @click="openBugModal"
          >
            <BugOutlined /> 创建缺陷
          </a-button>
          <a-tag v-if="run" :color="statusColor(run.status)" style="font-size: 14px">
            {{ run.status }}
          </a-tag>
          <a-spin v-if="isRunning" size="small" />
        </a-space>
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
            <span style="color: #ff4d4f">
              <template v-if="run.error_message.length > 500 && !expandedErrors.has('run')">
                {{ run.error_message.slice(0, 500) }}...
                <a-button type="link" size="small" @click="expandedErrors.add('run')">展开全部</a-button>
              </template>
              <template v-else>
                {{ run.error_message }}
                <a-button v-if="run.error_message.length > 500" type="link" size="small" @click="expandedErrors.delete('run')">收起</a-button>
              </template>
            </span>
          </a-descriptions-item>
          <a-descriptions-item v-if="run.result_summary?.bug" label="关联缺陷" :span="2">
            <a :href="run.result_summary.bug.bug_url" target="_blank">
              <LinkOutlined /> {{ run.result_summary.bug.bug_id }}
            </a>
            <span style="margin-left: 8px; color: #666">{{ run.result_summary.bug.title }}</span>
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
              style="margin-bottom: 12px"
              show-icon
            >
              <template #message>
                <template v-if="step.error_message.length > 500 && !expandedErrors.has(`step-${step.step_index}`)">
                  {{ step.error_message.slice(0, 500) }}...
                  <a-button type="link" size="small" @click="expandedErrors.add(`step-${step.step_index}`)">展开全部</a-button>
                </template>
                <template v-else>
                  {{ step.error_message }}
                  <a-button v-if="step.error_message.length > 500" type="link" size="small" @click="expandedErrors.delete(`step-${step.step_index}`)">收起</a-button>
                </template>
              </template>
            </a-alert>

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

    <!-- 创建缺陷 Modal -->
    <a-modal
      v-model:open="bugModalOpen"
      title="创建缺陷"
      ok-text="创建"
      cancel-text="取消"
      :confirm-loading="bugCreating"
      @ok="confirmCreateBug"
    >
      <a-form layout="vertical">
        <a-form-item label="缺陷跟踪平台">
          <a-select
            v-model:value="bugTrackerId"
            placeholder="请选择"
            style="width: 100%"
            :options="bugTrackerOptions"
            :loading="bugTrackerLoading"
          />
        </a-form-item>
        <a-form-item label="关联步骤（可选）">
          <a-select
            v-model:value="bugStepIndex"
            placeholder="不指定（使用 Run 级错误）"
            allow-clear
            style="width: 100%"
          >
            <a-select-option
              v-for="s in failedSteps"
              :key="s.step_index"
              :value="s.step_index"
            >
              #{{ s.step_index + 1 }} {{ s.name }} ({{ s.status }})
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
      <a-divider v-if="bugPreviewTitle" style="margin: 12px 0 8px">即将创建的缺陷</a-divider>
      <div v-if="bugPreviewTitle" class="bug-preview">
        <div class="bug-preview-label">标题</div>
        <div class="bug-preview-value">{{ bugPreviewTitle }}</div>
        <div class="bug-preview-label" style="margin-top: 8px">描述（摘要）</div>
        <pre class="bug-preview-value bug-preview-desc">{{ bugPreviewDesc }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import { VideoCameraOutlined, CameraOutlined, FileTextOutlined, FilePdfOutlined, BugOutlined, LinkOutlined } from '@ant-design/icons-vue'
import { runApi, bugTrackerApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { createRunWebSocket, type WsMessage } from '@/utils/websocket'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const runId = Number(route.params.runId)

const run = ref<any>(null)
const steps = ref<any[]>([])
const loading = ref(false)
const expandedKeys = ref<number[]>([])
const exportingHtml = ref(false)
const exportingPdf = ref(false)
const bugModalOpen = ref(false)
const bugTrackerId = ref<number | undefined>(undefined)
const bugStepIndex = ref<number | undefined>(undefined)
const bugTrackerOptions = ref<Array<{ label: string; value: number }>>([])
const bugTrackerLoading = ref(false)
const bugCreating = ref(false)
const expandedErrors = reactive(new Set<string>())
let wsHandle: ReturnType<typeof createRunWebSocket> | null = null

const fallbackImage = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5IiBmb250LXNpemU9IjE0Ij7miKrlm77liqDovb3lpLHotKU8L3RleHQ+PC9zdmc+'

const isRunning = computed(() => run.value?.status === 'running' || run.value?.status === 'pending')
const canCreateBug = computed(() => ['admin', 'engineer'].includes(auth.user?.role ?? ''))

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

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleExportHtml() {
  exportingHtml.value = true
  try {
    const blob = await runApi.exportHtml(runId)
    downloadBlob(blob, `run-${runId}-report.html`)
  } catch (e: any) {
    message.error(e ?? '导出 HTML 失败')
  } finally {
    exportingHtml.value = false
  }
}

async function handleExportPdf() {
  exportingPdf.value = true
  try {
    const blob = await runApi.exportPdf(runId)
    downloadBlob(blob, `run-${runId}-report.pdf`)
  } catch (e: any) {
    message.error(e ?? '导出 PDF 失败')
  } finally {
    exportingPdf.value = false
  }
}

// ── 创建缺陷 ───────────────────────────────────────────
const failedSteps = computed(() =>
  steps.value.filter(s => s.status === 'failed' || s.status === 'error'),
)

const bugPreviewTitle = computed(() => {
  if (!run.value) return ''
  const caseName = `Case-${run.value.case_id}`
  let title = `[ATP] ${caseName}`
  if (bugStepIndex.value !== undefined) {
    const step = steps.value.find((s: any) => s.step_index === bugStepIndex.value)
    if (step?.name) title += ` - ${step.name}`
  }
  title += ' 执行失败'
  return title
})

const bugPreviewDesc = computed(() => {
  if (!run.value) return ''
  const lines: string[] = [
    `来自 ATP 自动化测试平台，执行记录 #${run.value.id}`,
    `用例: Case-${run.value.case_id}`,
    `环境: ${run.value.environment || '-'}`,
  ]
  if (bugStepIndex.value !== undefined) {
    const step = steps.value.find((s: any) => s.step_index === bugStepIndex.value)
    if (step) {
      lines.push(`失败步骤: #${step.step_index + 1} ${step.name}`)
      if (step.error_message) {
        const msg = step.error_message.length > 500 ? step.error_message.slice(0, 500) + '...' : step.error_message
        lines.push(`\n错误信息:\n${msg}`)
      }
    }
  } else if (run.value.error_message) {
    const msg = run.value.error_message.length > 500 ? run.value.error_message.slice(0, 500) + '...' : run.value.error_message
    lines.push(`\n错误信息:\n${msg}`)
  }
  return lines.join('\n')
})

async function openBugModal() {
  if (!canCreateBug.value) {
    return
  }

  bugTrackerId.value = undefined
  bugStepIndex.value = failedSteps.value.length > 0 ? failedSteps.value[0].step_index : undefined
  bugModalOpen.value = true

  bugTrackerLoading.value = true
  try {
    const trackers = await bugTrackerApi.list()
    bugTrackerOptions.value = trackers
      .filter((t: any) => t.is_enabled)
      .map((t: any) => ({ label: `${t.name} (${t.tracker_type === 'jira' ? 'Jira' : '禅道'})`, value: t.id }))
  } catch {
    bugTrackerOptions.value = []
  } finally {
    bugTrackerLoading.value = false
  }
}

async function confirmCreateBug() {
  if (!bugTrackerId.value) { message.warning('请选择缺陷跟踪平台'); return }
  bugCreating.value = true
  try {
    const payload: { tracker_id: number; step_index?: number } = { tracker_id: bugTrackerId.value }
    if (bugStepIndex.value !== undefined) {
      payload.step_index = bugStepIndex.value
    }
    const result = await bugTrackerApi.createBug(runId, payload)
    // 更新本地数据以展示缺陷链接
    if (run.value) {
      run.value.result_summary = {
        ...(run.value.result_summary || {}),
        bug: { bug_id: result.bug_id, bug_url: result.bug_url, title: bugPreviewTitle.value },
      }
    }
    message.success(`缺陷已创建: ${result.bug_id}`)
    bugModalOpen.value = false
    window.open(result.bug_url, '_blank')
  } catch (e: any) {
    const msg = typeof e === 'string' ? e : e?.message || ''
    if (msg.includes('401') || msg.includes('认证') || msg.includes('Unauthorized')) {
      message.error('缺陷平台认证失败，请检查配置中的用户名/密码/Token')
    } else if (msg.includes('timeout') || msg.includes('ETIMEDOUT') || msg.includes('超时')) {
      message.error('连接缺陷平台超时，请检查网络或平台地址配置')
    } else if (msg.includes('404') || msg.includes('不存在')) {
      message.error('缺陷平台项目不存在，请检查配置中的项目标识')
    } else {
      message.error(msg || '创建缺陷失败，请稍后重试')
    }
  } finally {
    bugCreating.value = false
  }
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
  if (auth.token && !auth.user) {
    await auth.fetchMe()
  }

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

/* 缺陷预览 */
.bug-preview-label {
  font-weight: 600;
  color: #595959;
  font-size: 13px;
  margin-bottom: 4px;
}
.bug-preview-value {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  padding: 8px 12px;
  font-size: 13px;
}
.bug-preview-desc {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
}
</style>
