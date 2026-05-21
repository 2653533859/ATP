<template>
  <div>
    <a-page-header :title="t('run.detail_title')" @back="router.back()">
      <template #extra>
        <a-space>
          <a-button size="small" :loading="exportingHtml" @click="handleExportHtml">
            <FileTextOutlined /> {{ exportingHtml ? t('run.generating') : t('run.export_html') }}
          </a-button>
          <a-button size="small" :loading="exportingPdf" @click="handleExportPdf">
            <FilePdfOutlined /> {{ exportingPdf ? t('run.generating_pdf') : t('run.export_pdf') }}
          </a-button>
          <a-button
            v-if="canCreateBug && run && (run.status === 'failed' || run.status === 'error')"
            size="small"
            type="primary"
            danger
            @click="openBugModal"
          >
            <BugOutlined /> {{ t('run.create_bug') }}
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
          <a-descriptions-item :label="t('run.labels.run_id')">{{ run.id }}</a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.case_id')">{{ run.case_id }}</a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.trace_id')" :span="2">
            <code>{{ run.trace_id || '-' }}</code>
            <a
              v-if="jaegerSearchUrl"
              :href="jaegerSearchUrl"
              target="_blank"
              rel="noopener noreferrer"
              style="margin-left: 8px"
            >
              <LinkOutlined /> {{ t('run.open_in_jaeger') }}
            </a>
          </a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.environment')">{{ run.environment ?? '-' }}</a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.duration')">
            {{ run.duration_ms != null ? `${run.duration_ms} ms` : (isRunning ? t('common.running') : '-') }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('run.labels.triggered_at')" :span="2">
            {{ run.created_at?.slice(0, 19).replace('T', ' ') }}
          </a-descriptions-item>
          <a-descriptions-item v-if="run.error_message" :label="t('run.labels.error_message')" :span="2">
            <span style="color: #ff4d4f">
              <template v-if="run.error_message.length > 500 && !expandedErrors.has('run')">
                {{ run.error_message.slice(0, 500) }}...
                <a-button type="link" size="small" @click="expandedErrors.add('run')">{{ t('run.expand_all') }}</a-button>
              </template>
              <template v-else>
                {{ run.error_message }}
                <a-button v-if="run.error_message.length > 500" type="link" size="small" @click="expandedErrors.delete('run')">{{ t('run.collapse') }}</a-button>
              </template>
            </span>
          </a-descriptions-item>
          <a-descriptions-item v-if="bugInfo" :label="t('run.labels.linked_bug')" :span="2">
            <a :href="bugInfo.bug_url" target="_blank">
              <LinkOutlined /> {{ bugInfo.bug_id }}
            </a>
            <span style="margin-left: 8px; color: #666">{{ bugInfo.title }}</span>
            <a-tag v-if="bugInfo.status" style="margin-left: 8px">{{ bugInfo.status }}</a-tag>
            <a-button size="small" type="link" :loading="bugStatusRefreshing" @click="refreshBugStatus">{{ t('run.msg.refresh_status') }}</a-button>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 步骤统计 -->
        <div class="steps-header">
          <strong>{{ t('run.labels.steps') }}</strong>
          <span class="steps-summary">
            {{ t('run.summary.total_steps', { count: steps.length }) }}
            <template v-if="stepStats.passed > 0">
              <span class="stat-passed">{{ t('run.summary.passed', { count: stepStats.passed }) }}</span>
            </template>
            <template v-if="stepStats.failed > 0">
              <span class="stat-failed">{{ t('run.summary.failed', { count: stepStats.failed }) }}</span>
            </template>
            <template v-if="stepStats.error > 0">
              <span class="stat-error">{{ t('run.summary.error', { count: stepStats.error }) }}</span>
            </template>
            <template v-if="stepStats.skipped > 0">
              <span class="stat-skipped">{{ t('run.summary.skipped', { count: stepStats.skipped }) }}</span>
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

        <!-- 运行级 AI 诊断（iter3 多 step 综合分析）-->
        <div v-if="runHealing" class="run-healing-card">
          <a-divider orientation="left" style="margin: 16px 0 8px">
            <BulbOutlined />
            <span style="margin-left: 6px">{{ t('run.healing.run_title') }}</span>
            <a-tag :color="healingTagColor(runHealing.status)" style="margin-left: 8px">
              {{ healingStatusLabel(runHealing.status) }}
            </a-tag>
            <a-tag
              v-if="runHealing.cache_hit && runHealing.status === 'done'"
              color="purple"
              style="margin-left: 4px"
            >
              ⚡ {{ t('run.healing.cache_hit') }}
            </a-tag>
          </a-divider>
          <div v-if="runHealing.status === 'pending'" class="healing-pending">
            <LoadingOutlined /> <span style="margin-left: 6px">{{ t('run.healing.run_diagnosing') }}</span>
          </div>
          <pre
            v-else-if="runHealing.status === 'done' && runHealing.suggestion"
            class="healing-text"
          >{{ runHealing.suggestion }}</pre>
          <a-empty
            v-else-if="runHealing.status === 'failed'"
            :description="t('run.healing.run_failed_fallback')"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />
          <a-empty
            v-else-if="runHealing.status === 'skipped'"
            :description="runHealing.suggestion === 'daily-limit-reached'
              ? t('run.healing.daily_limit_reached')
              : t('run.healing.run_skipped_too_few_failures')"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />
        </div>

        <!-- 录像播放 -->
        <div v-if="videoUrl" class="video-section">
          <a-divider orientation="left" style="margin: 16px 0 12px">
            <VideoCameraOutlined /> {{ t('run.labels.video') }}
          </a-divider>
          <video
            :src="videoUrl"
            controls
            class="video-player"
          >
            {{ t('run.no_video_support') }}
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
                <a-button type="link" size="small" @click="expandedErrors.add(`step-${step.step_index}`)">{{ t('run.expand_all') }}</a-button>
                </template>
                <template v-else>
                  {{ step.error_message }}
                  <a-button v-if="step.error_message.length > 500" type="link" size="small" @click="expandedErrors.delete(`step-${step.step_index}`)">{{ t('run.collapse') }}</a-button>
                </template>
              </template>
            </a-alert>

            <!-- AI 诊断建议（P3.A）-->
            <a-collapse
              v-if="step.healing_status"
              class="healing-panel"
              ghost
              :bordered="false"
              style="margin-bottom: 12px"
            >
              <a-collapse-panel :key="`healing-${step.step_index}`">
                <template #header>
                  <span class="healing-title">
                    <BulbOutlined />
                    <span style="margin-left: 6px">{{ t('run.healing.title') }}</span>
                    <a-tag :color="healingTagColor(step.healing_status)" style="margin-left: 8px">
                      {{ healingStatusLabel(step.healing_status) }}
                    </a-tag>
                    <a-tag
                      v-if="step.healing_cache_hit && step.healing_status === 'done'"
                      color="purple"
                      style="margin-left: 4px"
                    >
                      ⚡ {{ t('run.healing.cache_hit') }}
                    </a-tag>
                  </span>
                </template>
                <div v-if="step.healing_status === 'pending'" class="healing-body healing-pending">
                  <LoadingOutlined /> <span style="margin-left: 6px">{{ t('run.healing.diagnosing') }}</span>
                </div>
                <pre
                  v-else-if="step.healing_status === 'done' && step.healing_suggestion"
                  class="healing-text"
                >{{ step.healing_suggestion }}</pre>
                <a-empty
                  v-else-if="step.healing_status === 'failed'"
                  :description="t('run.healing.failed_fallback')"
                  :image="Empty.PRESENTED_IMAGE_SIMPLE"
                />
                <a-empty
                  v-else-if="step.healing_status === 'skipped'"
                  :description="step.healing_suggestion === 'daily-limit-reached'
                    ? t('run.healing.daily_limit_reached')
                    : t('run.healing.skipped_no_config')"
                  :image="Empty.PRESENTED_IMAGE_SIMPLE"
                />
              </a-collapse-panel>
            </a-collapse>

            <!-- 截图展示 -->
            <div v-if="step.screenshot_url" class="screenshot-section">
              <div class="panel-label">
                <CameraOutlined /> {{ t('run.labels.screenshot') }}
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
                <div class="panel-label">{{ t('run.labels.request') }}</div>
                <pre class="code-block">{{ formatJson(step.request_data) }}</pre>
              </a-col>
              <!-- 响应 -->
              <a-col :span="12">
                <div class="panel-label">{{ t('run.labels.response') }}</div>
                <pre class="code-block">{{ formatJson(step.response_data) }}</pre>
              </a-col>
            </a-row>
          </a-collapse-panel>
        </a-collapse>

        <a-empty v-else :description="t('run.empty_steps')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
      </template>
    </a-spin>

    <!-- 创建缺陷 Modal -->
    <a-modal
      v-model:open="bugModalOpen"
      :title="t('run.create_bug')"
      :ok-text="t('common.create')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="bugCreating"
      @ok="confirmCreateBug"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('run.bug.tracker')">
          <a-select
            v-model:value="bugTrackerId"
            :placeholder="t('common.search')"
            style="width: 100%"
            :options="bugTrackerOptions"
            :loading="bugTrackerLoading"
          />
        </a-form-item>
        <a-form-item :label="t('run.bug.related_step')">
          <a-select
            v-model:value="bugStepIndex"
            :placeholder="t('run.bug.no_step')"
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
      <a-divider v-if="bugPreviewTitle" style="margin: 12px 0 8px">{{ t('run.bug.preview') }}</a-divider>
      <div v-if="bugPreviewTitle" class="bug-preview">
        <div class="bug-preview-label">{{ t('run.bug.title') }}</div>
        <div class="bug-preview-value">{{ bugPreviewTitle }}</div>
        <div class="bug-preview-label" style="margin-top: 8px">{{ t('run.bug.desc') }}</div>
        <pre class="bug-preview-value bug-preview-desc">{{ bugPreviewDesc }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import { VideoCameraOutlined, CameraOutlined, FileTextOutlined, FilePdfOutlined, BugOutlined, LinkOutlined, BulbOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { runApi, bugTrackerApi, tracingApi, type BugLinkInfo, type BugTrackerItem, type RunDetailItem, type RunStepItem } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { createRunWebSocket, type WsMessage } from '@/utils/websocket'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const auth = useAuthStore()
const runId = Number(route.params.runId)

const run = ref<RunDetailItem | null>(null)
const steps = ref<RunStepItem[]>([])
const loading = ref(false)
const expandedKeys = ref<number[]>([])
const exportingHtml = ref(false)
const jaegerUiUrl = ref('')

const jaegerSearchUrl = computed(() => {
  const tid = run.value?.trace_id
  const base = jaegerUiUrl.value
  if (!tid || !base) return ''
  const tags = encodeURIComponent(JSON.stringify({ 'app.trace_id': tid }))
  return `${base.replace(/\/$/, '')}/search?tags=${tags}`
})
const exportingPdf = ref(false)
const bugModalOpen = ref(false)
const bugTrackerId = ref<number | undefined>(undefined)
const bugStepIndex = ref<number | undefined>(undefined)
const bugTrackerOptions = ref<Array<{ label: string; value: number }>>([])
const bugTrackerLoading = ref(false)
const bugCreating = ref(false)
const bugStatusRefreshing = ref(false)
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

function healingTagColor(status?: string | null) {
  return (
    { pending: 'blue', done: 'green', failed: 'red', skipped: 'default' }[status ?? ''] ?? 'default'
  )
}

function healingStatusLabel(status?: string | null) {
  if (!status) return ''
  const key = `run.healing.status_${status}`
  return t(key)
}

function formatJson(data: Record<string, unknown> | null | undefined) {
  if (data == null) return '-'
  return JSON.stringify(data, null, 2)
}

function computeExpandedKeys(stepList: RunStepItem[]) {
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
  } catch (e: unknown) {
    const messageText = e instanceof Error ? e.message : ''
    message.error(messageText || t('run.msg.export_html_failed'))
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
    message.error(e ?? t('run.msg.export_pdf_failed'))
  } finally {
    exportingPdf.value = false
  }
}

// ── 创建缺陷 ───────────────────────────────────────────
const failedSteps = computed(() =>
  steps.value.filter(s => s.status === 'failed' || s.status === 'error'),
)

const caseDisplayName = computed(() => {
  if (!run.value) return ''
  return run.value.case_name || run.value.case?.name || `Case-${run.value.case_id}`
})

const bugInfo = computed<BugLinkInfo | null>(() => {
  const info = run.value?.result_summary?.bug
  return info && typeof info === 'object' ? info as BugLinkInfo : null
})

const videoUrl = computed(() => {
  const value = run.value?.result_summary?.video_url
  return typeof value === 'string' ? value : ''
})

interface RunHealingPayload {
  status: 'pending' | 'done' | 'failed' | 'skipped'
  suggestion: string | null
  at: string | null
  cache_hit: boolean
}

const runHealing = computed<RunHealingPayload | null>(() => {
  const raw = run.value?.result_summary?.healing
  if (!raw || typeof raw !== 'object') return null
  const h = raw as Record<string, unknown>
  if (!h.status) return null
  return {
    status: h.status as RunHealingPayload['status'],
    suggestion: typeof h.suggestion === 'string' ? h.suggestion : null,
    at: typeof h.at === 'string' ? h.at : null,
    cache_hit: Boolean(h.cache_hit),
  }
})

const bugPreviewTitle = computed(() => {
  if (!run.value) return ''
  let title = `[ATP] ${caseDisplayName.value}`
  if (bugStepIndex.value !== undefined) {
    const step = steps.value.find((s) => s.step_index === bugStepIndex.value)
    if (step?.name) title += ` - ${step.name}`
  }
  title += ` ${t('run.bug.title_suffix')}`
  return title
})

const bugPreviewDesc = computed(() => {
  if (!run.value) return ''
  const lines: string[] = [
    t('run.bug.desc_from', { id: run.value.id }),
    t('run.bug.desc_case', { name: caseDisplayName.value }),
    t('run.bug.desc_env', { environment: run.value.environment || '-' }),
  ]
  if (bugStepIndex.value !== undefined) {
    const step = steps.value.find((s) => s.step_index === bugStepIndex.value)
    if (step) {
      lines.push(t('run.bug.desc_failed_step', { index: step.step_index + 1, name: step.name }))
      if (step.error_message) {
        const msg = step.error_message.length > 500 ? step.error_message.slice(0, 500) + '...' : step.error_message
        lines.push(`\n${t('run.bug.desc_error')}\n${msg}`)
      }
    }
  } else if (run.value.error_message) {
    const msg = run.value.error_message.length > 500 ? run.value.error_message.slice(0, 500) + '...' : run.value.error_message
    lines.push(`\n${t('run.bug.desc_error')}\n${msg}`)
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
    const trackers = await bugTrackerApi.list({ project_id: run.value?.project_id })
    bugTrackerOptions.value = trackers
      .filter((t: BugTrackerItem) => t.is_enabled)
      .map((t: BugTrackerItem) => ({
        label: `${t.name} (${t.tracker_type === 'jira' ? 'Jira' : t.tracker_type === 'github' ? 'GitHub Issues' : 'Zentao'})`,
        value: t.id,
      }))
  } catch {
    bugTrackerOptions.value = []
  } finally {
    bugTrackerLoading.value = false
  }
}

async function confirmCreateBug() {
  if (!bugTrackerId.value) { message.warning(t('run.msg.select_tracker')); return }
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
        bug: {
          ...(bugInfo.value || {}),
          bug_id: result.bug_id,
          bug_url: result.bug_url,
          title: result.title || bugPreviewTitle.value,
          duplicate_of: result.duplicate_of ?? null,
          attachment_uploaded: result.attachment_uploaded ?? false,
        },
      }
    }
    if (result.duplicate_of) {
      message.warning(t('run.msg.duplicate_bug', { id: result.duplicate_of }))
    } else if (result.attachment_uploaded) {
      message.success(t('run.msg.bug_created_with_attachment', { id: result.bug_id }))
    } else {
      message.success(t('run.msg.bug_created', { id: result.bug_id }))
    }
    bugModalOpen.value = false
    window.open(result.bug_url, '_blank')
  } catch (e: any) {
    const msg = typeof e === 'string' ? e : e?.message || ''
    // 双语 fallback：兼容后端返回中文/英文错误消息；待后端切到 error_code 后可清理
    if (msg.includes('401') || msg.includes('认证') || msg.includes('Unauthorized')) {
      message.error(t('run.msg.bug_auth_failed'))
    } else if (msg.includes('timeout') || msg.includes('ETIMEDOUT') || msg.includes('超时')) {
      message.error(t('run.msg.bug_timeout'))
    } else if (msg.includes('404') || msg.includes('不存在')) {
      message.error(t('run.msg.bug_project_missing'))
    } else {
      message.error(msg || t('run.msg.create_bug_failed'))
    }
  } finally {
    bugCreating.value = false
  }
}

async function refreshBugStatus() {
  if (!run.value?.result_summary?.bug) return
  bugStatusRefreshing.value = true
  try {
    const result = await bugTrackerApi.getBugStatus(runId)
    run.value.result_summary = {
      ...(run.value.result_summary || {}),
      bug: {
        ...(bugInfo.value || {}),
        status: result.status,
        bug_url: result.bug_url || bugInfo.value?.bug_url,
      },
    }
    message.success(t('run.msg.bug_status_refreshed', { status: result.status }))
  } catch (e: unknown) {
    const messageText = e instanceof Error ? e.message : typeof e === 'string' ? e : ''
    message.error(messageText || t('run.msg.refresh_bug_status_failed'))
  } finally {
    bugStatusRefreshing.value = false
  }
}

function applyWsMessage(msg: WsMessage) {
  if (msg.type === 'run_status') {
    if (run.value && msg.status) run.value.status = msg.status
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

  if (msg.type === 'healing_suggestion' && msg.step_index != null) {
    const idx = steps.value.findIndex(s => s.step_index === msg.step_index)
    if (idx >= 0) {
      steps.value[idx] = {
        ...steps.value[idx],
        healing_status: msg.status,
        healing_suggestion: msg.suggestion ?? null,
        healing_cache_hit: msg.cache_hit ?? false,
      }
    }
    return
  }

  if (msg.type === 'run_healing_suggestion' && run.value) {
    run.value.result_summary = {
      ...(run.value.result_summary || {}),
      healing: {
        status: msg.status,
        suggestion: msg.suggestion ?? null,
        at: new Date().toISOString(),
        cache_hit: msg.cache_hit ?? false,
      },
    }
    return
  }

  if (msg.type === 'completed') {
    if (run.value) {
      if (msg.status) run.value.status = msg.status
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

  // Jaeger 跳转链接是 best-effort，配置缺失或接口失败都不影响详情页主流程
  try {
    const cfg = await tracingApi.getConfig()
    jaegerUiUrl.value = cfg.jaeger_ui_url || ''
  } catch {
    jaegerUiUrl.value = ''
  }

  loading.value = true
  try {
    const data = await runApi.get(runId) as RunDetailItem
    run.value = data
    steps.value = data.steps ?? []
    expandedKeys.value = computeExpandedKeys(steps.value)
  } finally {
    loading.value = false
  }

  if (run.value?.status === 'pending' || run.value?.status === 'running') {
    wsHandle = createRunWebSocket(runId, applyWsMessage, () => {
      runApi.get(runId).then((d: RunDetailItem) => {
        run.value = d
        steps.value = d.steps ?? []
        expandedKeys.value = computeExpandedKeys(steps.value)
      })
    })
  }

  if (run.value?.result_summary?.bug) {
    void refreshBugStatus()
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

.healing-panel :deep(.ant-collapse-header) {
  padding: 6px 0 !important;
  font-size: 13px;
}

.healing-title {
  display: inline-flex;
  align-items: center;
  color: #1677ff;
  font-weight: 500;
}

.healing-pending {
  color: #1677ff;
  font-size: 13px;
}

.healing-text {
  margin: 0;
  padding: 8px 12px;
  background: #f6f8fa;
  border-left: 3px solid #1677ff;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
}
</style>
