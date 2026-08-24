<template>
  <div style="display: flex; flex-direction: column; height: 100%; overflow: auto">
    <div style="margin-bottom: 12px">
      <a-button type="link" @click="router.back()">
        {{ t('mobile_special.reports.back_to_center') }}
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <template v-if="run">
        <a-card style="margin-bottom: 16px" :body-style="{ padding: '16px 20px' }">
          <a-descriptions :column="{ xs: 1, sm: 2, md: 3 }" size="small">
            <a-descriptions-item :label="t('mobile_special.columns.name')">{{ taskInfo?.name || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.task_type')">
              <a-tag :color="taskTypeColor(run.task_type)">{{ taskTypeLabel(run.task_type) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item :label="t('common.status')">
              <a-tag :color="statusColor(run.status)">{{ statusLabel(run.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.reports.device_serial')">{{ run.device_serial || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.columns.app_package')">{{ run.app_package || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.reports.duration')">
              {{ run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.reports.started_at')">
              {{ run.started_at ? formatDate(run.started_at) : '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.reports.finished_at')">
              {{ run.finished_at ? formatDate(run.finished_at) : '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('mobile_special.reports.trigger_type')">
              {{ triggerLabel(run.trigger_type) }}
            </a-descriptions-item>
          </a-descriptions>
          <div v-if="run.task_type === 'stability'" class="run-toolbar">
            <a-tag v-if="monkeySeed !== null" color="purple">
              {{ t('mobile_special.replay_seed') }}: {{ monkeySeed }}
            </a-tag>
            <a-button type="primary" ghost size="small" @click="replayRun">
              {{ t('mobile_special.replay_run') }}
            </a-button>
          </div>
        </a-card>

        <a-card v-if="isLiveRun || live.logs.length" class="live-panel" :body-style="{ padding: '16px' }">
          <template #title>
            <div class="live-header">
              <span>{{ t('mobile_special.reports.live.title') }}</span>
              <span class="live-connection">
                <span class="pulse-dot" :class="{ connected: live.connected }"></span>
                {{ live.connected ? t('mobile_special.reports.live.connected') : t('mobile_special.reports.live.polling') }}
              </span>
            </div>
          </template>
          <div class="live-progress-row">
            <a-progress :percent="live.progress" :status="liveProgressStatus" :show-info="false" />
            <strong>{{ live.progress }}%</strong>
          </div>
          <div class="live-kpi-grid">
            <div>
              <span>{{ t('mobile_special.reports.live.current_step') }}</span>
              <strong>{{ live.currentStep || t('mobile_special.reports.live.waiting') }}</strong>
            </div>
            <div>
              <span>{{ t('mobile_special.reports.live.device_status') }}</span>
              <strong>{{ deviceStatusLabel }}</strong>
            </div>
            <div>
              <span>{{ t('mobile_special.reports.live.sample_count') }}</span>
              <strong>{{ live.sampleCount }}</strong>
            </div>
            <div>
              <span>{{ t('mobile_special.reports.live.incident_count') }}</span>
              <strong :class="{ danger: live.incidentCount > 0 }">{{ live.incidentCount }}</strong>
            </div>
          </div>
          <a-alert v-if="live.error" type="error" show-icon :message="live.error" style="margin-top: 12px" />
          <div v-if="live.logs.length" class="live-log-list">
            <div class="live-log-title">{{ t('mobile_special.reports.live.logs') }}</div>
            <div v-for="item in live.logs.slice(-8).reverse()" :key="item.id" class="live-log-line">
              <span class="live-log-time">{{ item.at }}</span>
              <a-tag :color="logLevelColor(item.level)" size="small">{{ item.level }}</a-tag>
              <span>{{ item.message }}</span>
            </div>
          </div>
        </a-card>

        <a-alert
          v-if="replayError"
          type="warning"
          show-icon
          :message="t('mobile_special.reports.replay_unavailable')"
          :description="replayError"
          style="margin-bottom: 16px"
        />

        <a-card v-if="artifactStatuses.length" style="margin-bottom: 16px" :body-style="{ padding: '12px 16px' }">
          <template #title>
            <span style="font-size: 14px">{{ t('mobile_special.reports.artifact_status_title') }}</span>
          </template>
          <div class="artifact-status-list">
            <div v-for="item in artifactStatuses" :key="item.kind" class="artifact-status-item">
              <a-tag :color="item.saved ? 'green' : 'orange'">
                {{ item.saved ? t('mobile_special.reports.artifact_saved') : t('mobile_special.reports.artifact_not_saved') }}
              </a-tag>
              <strong>{{ item.label }}</strong>
              <span v-if="item.fileName">{{ item.fileName }}</span>
              <span v-if="item.error" class="artifact-status-error">{{ item.error }}</span>
            </div>
          </div>
        </a-card>

        <a-card class="event-timeline-card" :body-style="{ padding: '0 20px 20px' }">
          <template #title>
            <div class="timeline-heading">
              <span>{{ t('mobile_special.event_timeline', { count: events.length }) }}</span>
              <a-tag v-if="events.length" color="blue">{{ events.length }}</a-tag>
            </div>
          </template>
          <a-empty v-if="!events.length" :description="t('mobile_special.event_timeline_empty')" style="padding: 24px 0" />
          <div v-else class="event-timeline">
            <div v-for="event in events" :key="event.id" class="event-row">
              <div class="event-spine"><span class="event-dot" :class="eventDotClass(event)"></span></div>
              <div class="event-content">
                <div class="event-meta">
                  <span class="event-time">{{ formatDate(event.event_time) }}</span>
                  <a-tag :color="eventLevelColor(event.level)">{{ eventLabel(event.event_type) }}</a-tag>
                  <a-tag v-if="event.phase" color="default">{{ event.phase }}</a-tag>
                  <span v-if="event.action" class="event-action">{{ event.action }}</span>
                  <span v-if="event.duration_ms !== null && event.duration_ms !== undefined" class="event-duration">
                    {{ t('mobile_special.event_duration', { duration: event.duration_ms }) }}
                  </span>
                </div>
                <div v-if="event.message" class="event-message">{{ event.message }}</div>
                <div v-if="Object.keys(event.parameters_json || {}).length || Object.keys(event.result_json || {}).length" class="event-details">
                  <details v-if="Object.keys(event.parameters_json || {}).length">
                    <summary>{{ t('mobile_special.event_parameters') }}</summary>
                    <pre>{{ prettyJson(event.parameters_json) }}</pre>
                  </details>
                  <details v-if="Object.keys(event.result_json || {}).length">
                    <summary>{{ t('mobile_special.event_result') }}</summary>
                    <pre>{{ prettyJson(event.result_json) }}</pre>
                  </details>
                </div>
              </div>
            </div>
          </div>
        </a-card>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px">
          <MetricKpiCard
            v-for="kpi in kpiCards"
            :key="kpi.label"
            :label="kpi.label"
            :value="kpi.value"
            :unit="kpi.unit"
            :color="kpi.color"
          />
        </div>

        <a-card v-if="latestMetricCards.length" style="margin-bottom: 16px" :body-style="{ padding: '16px' }">
          <template #title>
            <span style="font-size: 14px">{{ t('mobile_special.reports.device_metrics') }}</span>
          </template>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px">
            <MetricKpiCard
              v-for="metric in latestMetricCards"
              :key="metric.label"
              :label="metric.label"
              :value="metric.value"
              :unit="metric.unit"
              :color="metric.color"
            />
          </div>
        </a-card>

        <a-card style="margin-bottom: 16px" :body-style="{ padding: '16px' }">
          <template #title>
            <span style="font-size: 14px">{{ t('mobile_special.reports.metric_trend') }}</span>
          </template>
          <div style="display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap">
            <a-select
              v-model:value="selectedMetricType"
              :placeholder="t('mobile_special.reports.select_metric')"
              style="width: 160px"
              :options="metricTypeOptions"
              @change="loadSamples"
            />
          </div>
          <div ref="trendChartRef" style="width: 100%; height: 280px"></div>
        </a-card>

        <a-card style="margin-bottom: 16px" :body-style="{ padding: '0 16px 16px' }">
          <template #title>
            <span style="font-size: 14px">{{ t('mobile_special.reports.incidents_title', { count: incidents.length }) }}</span>
          </template>
          <a-table
            v-if="incidents.length > 0"
            :data-source="incidents"
            :columns="incidentColumns"
            :pagination="{ pageSize: 10 }"
            row-key="id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'incident_type'">
                <a-tag :color="incidentColor(record.incident_type)">
                  {{ incidentLabel(record.incident_type) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'event_time'">
                {{ formatDate(record.event_time) }}
              </template>
              <template v-else-if="column.key === 'title'">
                <span style="font-weight: 500">{{ record.title }}</span>
                <div v-if="record.detail" style="color: #999; font-size: 12px; margin-top: 2px">
                  {{ record.detail }}
                </div>
              </template>
            </template>
          </a-table>
          <a-empty v-else :description="t('mobile_special.reports.no_incidents')" style="padding: 24px 0" />
        </a-card>

        <a-card :body-style="{ padding: '0 16px 16px' }">
          <template #title>
            <span style="font-size: 14px; margin-right: 8px">{{ t('mobile_special.reports.artifacts_title', { count: artifacts.length }) }}</span>
            <a-button type="link" size="small" @click="doExportCsv">{{ t('mobile_special.reports.export_csv') }}</a-button>
            <a-button type="link" size="small" @click="doExportJson">{{ t('mobile_special.reports.export_json') }}</a-button>
          </template>
          <a-table
            v-if="artifacts.length > 0"
            :data-source="artifacts"
            :columns="artifactColumns"
            :pagination="{ pageSize: 10 }"
            row-key="id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'artifact_type'">
                <a-tag>{{ artifactLabel(record.artifact_type) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'file_size'">
                {{ record.file_size ? formatFileSize(record.file_size) : '-' }}
              </template>
              <template v-else-if="column.key === 'created_at'">
                {{ formatDate(record.created_at) }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" size="small" @click="downloadArtifact(asArtifact(record))">{{ t('mobile_special.reports.download') }}</a-button>
              </template>
            </template>
          </a-table>
          <a-empty v-else :description="t('mobile_special.reports.no_artifacts')" style="padding: 24px 0" />
        </a-card>
      </template>

      <a-empty v-else :description="t('mobile_special.reports.not_found')" style="padding: 48px 0" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { init, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { useChartTheme } from '@/utils/chartTheme'
import { createRunWebSocket, type WsMessage } from '@/utils/websocket'
import {
  mobileSpecialApi,
  type MobileSpecialRunItem,
  type MobileSpecialTaskItem,
  type MobileMetricSampleItem,
  type MobileIncidentItem,
  type MobileRunArtifactItem,
  type MobileRunEventItem,
  type ArtifactType,
  type IncidentType,
  type MobileRunStatus,
  type MobileTriggerType,
  type TaskType,
} from '@/api'

// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asArtifact = (record: unknown) => record as MobileRunArtifactItem

const MetricKpiCard = {
  props: { label: String, value: [String, Number], unit: String, color: String },
  template: `
    <a-card :body-style="{ padding: '12px 16px' }" size="small">
      <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ label }}</div>
      <div style="font-size: 22px; font-weight: 600; color: {{ color || '#333' }}">
        {{ value !== null && value !== undefined ? value : '-' }}<span style="font-size: 13px; font-weight: 400; margin-left: 2px">{{ unit || '' }}</span>
      </div>
    </a-card>
  `,
}

const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()
const { chartTheme } = useChartTheme()

const loading = ref(false)
const runId = computed(() => Number(route.params.runId))
const run = ref<MobileSpecialRunItem | null>(null)
const taskInfo = ref<MobileSpecialTaskItem | null>(null)
const allSamples = ref<MobileMetricSampleItem[]>([])
const samples = ref<MobileMetricSampleItem[]>([])
const incidents = ref<MobileIncidentItem[]>([])
const artifacts = ref<MobileRunArtifactItem[]>([])
const events = ref<MobileRunEventItem[]>([])
const EVENT_LIMIT = 5000
const liveSamples = ref<MobileMetricSampleItem[]>([])
type LiveLog = { id: number; at: string; level: string; message: string }
const live = ref({
  connected: false,
  progress: 0,
  phase: '',
  currentStep: '',
  sampleCount: 0,
  incidentCount: 0,
  deviceStatus: 'unknown',
  lastUpdated: '',
  error: '',
  logs: [] as LiveLog[],
})
let liveSocket: ReturnType<typeof createRunWebSocket> | null = null
let livePollTimer: number | null = null
let liveLogSequence = 0

const isLiveRun = computed(() => run.value?.status === 'pending' || run.value?.status === 'running')
const monkeySeed = computed(() => {
  const value = run.value?.config_snapshot?.monkey_seed
  return typeof value === 'number' || typeof value === 'string' ? value : null
})
const replayError = computed(() => {
  const replay = run.value?.summary_json?.incident_replay
  if (!replay || typeof replay !== 'object' || Array.isArray(replay)) return ''
  const error = (replay as Record<string, unknown>).error
  return typeof error === 'string' ? error : ''
})
type ArtifactStatus = { kind: string; label: string; saved: boolean; fileName?: string; error?: string }
const artifactStatuses = computed<ArtifactStatus[]>(() => {
  const raw = run.value?.summary_json?.android_artifacts
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return []
  return Object.entries(raw as Record<string, unknown>).flatMap(([kind, value]) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return []
    const item = value as Record<string, unknown>
    return [{
      kind,
      label: kind === 'logcat'
        ? t('mobile_special.reports.device_log_artifact')
        : t('mobile_special.reports.screenshot_artifact'),
      saved: item.saved === true,
      fileName: typeof item.file_name === 'string' ? item.file_name : undefined,
      error: typeof item.error === 'string' ? item.error : undefined,
    }]
  })
})
const liveProgressStatus = computed(() => live.value.error ? 'exception' : undefined)
const deviceStatusLabel = computed(() => {
  const key = live.value.deviceStatus
  return t(`mobile_special.reports.live.device_statuses.${key}`, key)
})

const selectedMetricType = ref('mem_mb')
const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: ECharts | null = null

type TooltipDataPoint = {
  name: string
  seriesName: string
  value: number | string
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

function firstTooltipPoint(params: unknown): TooltipDataPoint | null {
  if (!Array.isArray(params)) return null
  const first = params[0]
  if (typeof first !== 'object' || first === null) return null
  const item = first as Partial<TooltipDataPoint>
  if (item.name === undefined || item.seriesName === undefined || item.value === undefined) return null
  return {
    name: String(item.name),
    seriesName: String(item.seriesName),
    value: item.value,
  }
}

const metricTypeOptions = computed(() => [
  { label: t('mobile_special.reports.metrics.memory'), value: 'mem_mb' },
  { label: t('mobile_special.reports.metrics.cpu'), value: 'cpu_pct' },
  { label: t('mobile_special.reports.metrics.battery'), value: 'battery_pct' },
  { label: t('mobile_special.reports.metrics.temperature'), value: 'temperature_c' },
  { label: t('mobile_special.reports.metrics.fps'), value: 'fps' },
  { label: t('mobile_special.reports.metrics.jank'), value: 'jank_count' },
])

const effectiveSamples = computed(() => [...allSamples.value, ...liveSamples.value])

const incidentColumns = computed(() => [
  { title: t('common.type'), key: 'incident_type', width: 100 },
  { title: t('mobile_special.reports.time'), key: 'event_time', width: 160 },
  { title: t('mobile_special.reports.title_detail'), key: 'title' },
])

const artifactColumns = computed(() => [
  { title: t('common.type'), key: 'artifact_type', width: 100 },
  { title: t('mobile_special.reports.file_name'), key: 'file_name', dataIndex: 'file_name' },
  { title: t('mobile_special.reports.file_size'), key: 'file_size', width: 100 },
  { title: t('mobile_special.reports.time'), key: 'created_at', width: 160 },
  { title: t('common.action'), key: 'action', width: 80 },
])

const kpiCards = computed(() => {
  if (!effectiveSamples.value.length) return []
  const summary = run.value?.summary_json ?? {}

  const byType = (type: string) => {
    const vals = effectiveSamples.value.filter(s => s.metric_type === type).map(s => s.metric_value)
    if (!vals.length) return null
    return { avg: vals.reduce((a, b) => a + b, 0) / vals.length, min: Math.min(...vals), max: Math.max(...vals) }
  }

  const mem = byType('mem_mb')
  const cpu = byType('cpu_pct')
  const fps = byType('fps')

  return [
    ...(mem ? [{ label: t('mobile_special.reports.kpi.memory_avg'), value: mem.avg.toFixed(1), unit: 'MB', color: '#1890ff' }] : []),
    ...(cpu ? [{ label: t('mobile_special.reports.kpi.cpu_avg'), value: cpu.avg.toFixed(1), unit: '%', color: '#faad14' }] : []),
    ...(fps ? [{ label: t('mobile_special.reports.kpi.fps_avg'), value: fps.avg.toFixed(1), unit: '', color: '#52c41a' }] : []),
    ...(fps ? [{ label: t('mobile_special.reports.kpi.jank_count'), value: Number(summary.total_jank_count ?? 0), unit: t('mobile_special.reports.units.times'), color: '#ff4d4f' }] : []),
    ...(incidents.value.length ? [{ label: t('mobile_special.reports.incidents'), value: incidents.value.length, unit: t('mobile_special.reports.units.items'), color: '#ff4d4f' }] : []),
    ...(run.value?.duration_ms ? [{ label: t('mobile_special.reports.kpi.total_duration'), value: (run.value.duration_ms / 1000).toFixed(1), unit: 's', color: '#722ed1' }] : []),
  ].slice(0, 6)
})

const latestMetricCards = computed(() => {
  const definitions = [
    { type: 'cpu_pct', label: t('mobile_special.reports.metrics.cpu'), unit: '%', color: '#faad14' },
    { type: 'mem_mb', label: t('mobile_special.reports.metrics.memory'), unit: 'MB', color: '#1890ff' },
    { type: 'battery_pct', label: t('mobile_special.reports.metrics.battery'), unit: '%', color: '#52c41a' },
    { type: 'temperature_c', label: t('mobile_special.reports.metrics.temperature'), unit: '°C', color: '#fa541c' },
    { type: 'fps', label: t('mobile_special.reports.metrics.fps'), unit: '', color: '#722ed1' },
    { type: 'jank_count', label: t('mobile_special.reports.metrics.jank'), unit: t('mobile_special.reports.units.times'), color: '#ff4d4f' },
  ]
  return definitions.flatMap((definition) => {
    const latest = [...effectiveSamples.value]
      .filter(sample => sample.metric_type === definition.type)
      .sort((a, b) => new Date(b.sample_time).getTime() - new Date(a.sample_time).getTime())[0]
    return latest ? [{ label: definition.label, value: latest.metric_value.toFixed(2), unit: definition.unit, color: definition.color }] : []
  })
})

onMounted(async () => {
  await loadAll()
  initTrendChart()
  startLiveStream()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  stopLiveStream()
  trendChart?.dispose()
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  trendChart?.resize()
}

async function loadAll() {
  loading.value = true
  try {
    const [runData, samplesData, incidentsData, eventsData, artifactsData] = await Promise.all([
      mobileSpecialApi.getRun(runId.value),
      mobileSpecialApi.getRunSamples(runId.value, { limit: 500 }),
      mobileSpecialApi.getRunIncidents(runId.value),
      mobileSpecialApi.getRunEvents(runId.value, { limit: EVENT_LIMIT }),
      mobileSpecialApi.getRunArtifacts(runId.value),
    ])

    run.value = runData
    allSamples.value = samplesData
    samples.value = samplesData
    incidents.value = incidentsData
    events.value = eventsData
    artifacts.value = artifactsData
    if (!isLiveStatus(runData.status)) {
      liveSamples.value = []
    }
    live.value.sampleCount = Math.max(live.value.sampleCount, samplesData.length)
    live.value.incidentCount = incidentsData.length
    if (!isLiveStatus(runData.status) && runData.status === 'completed') {
      live.value.progress = 100
      live.value.currentStep = t('mobile_special.reports.live.completed')
    }

    if (runData.task_id) {
      try {
        taskInfo.value = await mobileSpecialApi.getTask(runData.task_id)
      } catch { /* ignore */ }
    }

    updateTrendChart()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.load_detail_failed')))
  } finally {
    loading.value = false
  }
}

async function loadSamples() {
  if (!run.value) return
  try {
    const data = await mobileSpecialApi.getRunSamples(runId.value, {
      metric_type: selectedMetricType.value,
      limit: 500,
    })
    samples.value = [...data, ...liveSamples.value]
    updateTrendChart()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.load_metrics_failed')))
  }
}

function isLiveStatus(status: MobileRunStatus) {
  return status === 'pending' || status === 'running'
}

function addLiveLog(level: string, messageText: string) {
  if (!messageText) return
  liveLogSequence += 1
  live.value.logs = [
    ...live.value.logs,
    { id: liveLogSequence, at: new Date().toLocaleTimeString(), level, message: messageText },
  ].slice(-80)
}

function applyLiveMessage(msg: WsMessage) {
  if (msg.run_id !== runId.value) return
  live.value.connected = true
  live.value.lastUpdated = new Date().toLocaleTimeString()
  if (typeof msg.progress === 'number') live.value.progress = Math.max(0, Math.min(100, Math.round(msg.progress)))
  if (msg.phase) live.value.phase = msg.phase
  if (msg.current_step) live.value.currentStep = msg.current_step
  if (msg.device_status) live.value.deviceStatus = msg.device_status
  if (msg.device_serial && run.value) run.value.device_serial = msg.device_serial

  if (msg.type === 'run_status' || msg.type === 'started') {
    if (run.value && msg.status) run.value.status = msg.status as MobileRunStatus
    addLiveLog('info', msg.current_step || t('mobile_special.reports.live.started'))
  }
  if (msg.type === 'log') addLiveLog(msg.level || 'info', msg.message || '')
  if (msg.type === 'sampling') {
    if (typeof msg.sample_count === 'number') live.value.sampleCount = Math.max(live.value.sampleCount, msg.sample_count)
    const incoming = (msg.sample_metrics || []).map((sample, index): MobileMetricSampleItem => ({
      id: -(Date.now() + index),
      run_id: runId.value,
      sample_time: sample.sample_time || new Date().toISOString(),
      metric_type: sample.metric_type,
      metric_value: sample.metric_value,
      source: 'live',
      extra_json: {},
    }))
    if (incoming.length) {
      liveSamples.value = [...liveSamples.value, ...incoming].slice(-300)
      samples.value = [...samples.value, ...incoming]
    }
    addLiveLog('info', t('mobile_special.reports.live.sampled', { count: live.value.sampleCount }))
  }
  if (msg.type === 'incident') {
    live.value.incidentCount = Math.max(live.value.incidentCount, msg.incident_count || 0, incidents.value.length + 1)
    addLiveLog('error', msg.title || t('mobile_special.reports.live.incident_detected'))
  }
  if (msg.type === 'stage_start' || msg.type === 'stage_end') {
    addLiveLog('info', `${msg.type === 'stage_start' ? t('mobile_special.reports.live.stage_started') : t('mobile_special.reports.live.stage_finished')}: ${msg.stage_name || '-'}`)
  }
  if (msg.type === 'completed') {
    if (run.value) {
      run.value.status = (msg.status || 'completed') as MobileRunStatus
      if (typeof msg.duration_ms === 'number') run.value.duration_ms = msg.duration_ms
    }
    live.value.progress = 100
    live.value.error = msg.error || ''
    live.value.currentStep = msg.current_step || t('mobile_special.reports.live.completed')
    addLiveLog(msg.status === 'failed' ? 'error' : 'info', live.value.currentStep)
    void loadAll().then(() => stopLiveStream())
  }
  updateTrendChart()
}

function startLiveStream() {
  if (!run.value || !isLiveStatus(run.value.status)) return
  liveSocket?.close()
  liveSocket = createRunWebSocket(runId.value, applyLiveMessage, () => {
    live.value.connected = false
  }, 'mobile')
  if (livePollTimer !== null) window.clearInterval(livePollTimer)
  livePollTimer = window.setInterval(async () => {
    try {
      const latest = await mobileSpecialApi.getRun(runId.value)
      if (run.value) Object.assign(run.value, latest)
      if (!isLiveStatus(latest.status)) {
        live.value.progress = 100
        await loadAll()
        stopLiveStream()
      } else {
        const [latestSamples, latestIncidents, latestEvents] = await Promise.all([
          mobileSpecialApi.getRunSamples(runId.value, { limit: 500 }),
          mobileSpecialApi.getRunIncidents(runId.value),
          mobileSpecialApi.getRunEvents(runId.value, { limit: EVENT_LIMIT }),
        ])
        allSamples.value = latestSamples
        samples.value = [...latestSamples, ...liveSamples.value]
        incidents.value = latestIncidents
        events.value = latestEvents
        live.value.sampleCount = Math.max(live.value.sampleCount, latestSamples.length)
        live.value.incidentCount = latestIncidents.length
        updateTrendChart()
      }
    } catch {
      // WebSocket remains the primary path; polling errors are intentionally silent.
    }
  }, 3000)
}

function stopLiveStream() {
  liveSocket?.close()
  liveSocket = null
  if (livePollTimer !== null) {
    window.clearInterval(livePollTimer)
    livePollTimer = null
  }
  live.value.connected = false
}

function logLevelColor(level: string) {
  return { error: 'red', warning: 'orange', info: 'blue', debug: 'default' }[level] || 'default'
}

function eventLabel(type: string) {
  const key = `mobile_special.event_types.${type}`
  const translated = t(key)
  return translated === key ? type : translated
}

function eventLevelColor(level?: string | null) {
  return level === 'error' ? 'red' : level === 'warning' ? 'orange' : level === 'debug' ? 'default' : 'blue'
}

function eventDotClass(event: MobileRunEventItem) {
  return event.level === 'error' ? 'danger' : event.event_type === 'run_completed' ? 'success' : ''
}

function prettyJson(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2)
}

async function replayRun() {
  if (!run.value) return
  try {
    const replay = await mobileSpecialApi.replayRun(run.value.id)
    message.success(t('mobile_special.replay_started'))
    await router.push(`/mobile-special/reports/${replay.id}`)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.load_detail_failed')))
  }
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = init(trendChartRef.value, chartTheme.value)
  updateTrendChart()
}

function updateTrendChart() {
  if (!trendChart) return

  const filtered = samples.value
    .filter(s => s.metric_type === selectedMetricType.value)
    .sort((a, b) => new Date(a.sample_time).getTime() - new Date(b.sample_time).getTime())

  const times = filtered.map(s => new Date(s.sample_time).toLocaleTimeString())
  const values = filtered.map(s => s.metric_value)

  const unitMap: Record<string, string> = { mem_mb: 'MB', cpu_pct: '%', battery_pct: '%', temperature_c: '°C', fps: '', jank_count: '' }
  const colorMap: Record<string, string> = { mem_mb: '#1890ff', cpu_pct: '#faad14', battery_pct: '#52c41a', temperature_c: '#fa541c', fps: '#722ed1', jank_count: '#ff4d4f' }

  const option: EChartsCoreOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = firstTooltipPoint(params)
        if (!p) return ''
        return `${p.name}<br/>${p.seriesName}: ${p.value} ${unitMap[selectedMetricType.value] || ''}`
      },
    },
    grid: { top: 10, right: 20, bottom: 30, left: 50 },
    xAxis: { type: 'category', data: times, axisLabel: { fontSize: 10, rotate: 30 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 11, formatter: (v: number) => `${v}${unitMap[selectedMetricType.value] || ''}` } },
    series: [{ name: metricTypeOptions.value.find(o => o.value === selectedMetricType.value)?.label || '', type: 'line', data: values, smooth: true, itemStyle: { color: colorMap[selectedMetricType.value] || '#1890ff' } }],
  }

  trendChart.setOption(option, true)
}

function taskTypeColor(type: TaskType) {
  return { performance: 'blue', stability: 'orange', fluency: 'purple' }[type] || 'default'
}

function taskTypeLabel(type: TaskType) {
  return {
    performance: t('mobile_special.task_types.performance'),
    stability: t('mobile_special.task_types.stability'),
    fluency: t('mobile_special.task_types.fluency'),
  }[type] || type
}

function statusColor(status: MobileRunStatus) {
  return { pending: 'default', running: 'processing', completed: 'success', failed: 'error', stopped: 'warning' }[status] || 'default'
}

function statusLabel(status: MobileRunStatus) {
  return {
    pending: t('mobile_special.statuses.pending'),
    running: t('mobile_special.statuses.running'),
    completed: t('mobile_special.statuses.completed'),
    failed: t('mobile_special.statuses.failed'),
    stopped: t('mobile_special.statuses.stopped'),
  }[status] || status
}

function triggerLabel(type: MobileTriggerType) {
  return {
    manual: t('mobile_special.trigger_types.manual'),
    schedule: t('mobile_special.trigger_types.schedule'),
    webhook: 'Webhook',
  }[type] || type
}

function incidentColor(type: IncidentType) {
  return { crash: 'red', anr: 'orange', fatal_log: 'purple', watchdog: 'magenta' }[type] || 'default'
}

function incidentLabel(type: IncidentType) {
  return {
    crash: t('mobile_special.incident_types.crash'),
    anr: 'ANR',
    fatal_log: t('mobile_special.incident_types.fatal_log'),
    watchdog: 'Watchdog',
  }[type] || type
}

function artifactLabel(type: ArtifactType) {
  return {
    csv: 'CSV',
    json: 'JSON',
    screenshot: t('mobile_special.artifact_types.screenshot'),
    raw_log: t('mobile_special.artifact_types.raw_log'),
    trace: 'Trace',
    replay: t('mobile_special.artifact_types.replay'),
  }[type] || type
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString()
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function downloadArtifact(record: MobileRunArtifactItem) {
  try {
    const result = await mobileSpecialApi.getArtifactUrl(runId.value, record.id)
    window.open(result.url, '_blank', 'noopener,noreferrer')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.download_failed')))
  }
}

async function doExportCsv() {
  if (!run.value) return
  try {
    const blob = await mobileSpecialApi.exportRunCsv(run.value.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mobile_run_${run.value.id}_metrics.csv`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('mobile_special.reports.msg.csv_downloaded'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.export_failed')))
  }
}

async function doExportJson() {
  if (!run.value) return
  try {
    const blob = await mobileSpecialApi.exportRunJson(run.value.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mobile_run_${run.value.id}_report.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('mobile_special.reports.msg.json_downloaded'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.export_failed')))
  }
}

watch(locale, () => updateTrendChart())
watch(chartTheme, () => {
  trendChart?.dispose()
  trendChart = null
  initTrendChart()
})
</script>

<style scoped>
.run-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.event-timeline-card {
  margin-bottom: 16px;
  border-color: #e5e7eb;
}

.timeline-heading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-timeline {
  position: relative;
  padding-top: 4px;
}

.event-row {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  min-height: 64px;
}

.event-spine {
  position: relative;
  display: flex;
  justify-content: center;
}

.event-spine::after {
  position: absolute;
  top: 16px;
  bottom: -1px;
  width: 1px;
  background: #dbe3f0;
  content: '';
}

.event-row:last-child .event-spine::after {
  display: none;
}

.event-dot {
  position: relative;
  z-index: 1;
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: #6b7cff;
  box-shadow: 0 0 0 1px #9aa7ff;
}

.event-dot.danger {
  background: #ff4d4f;
  box-shadow: 0 0 0 1px #ffaaa5;
}

.event-dot.success {
  background: #52c41a;
  box-shadow: 0 0 0 1px #b7eb8f;
}

.event-content {
  min-width: 0;
  padding: 0 0 16px 10px;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.event-time,
.event-action,
.event-duration {
  color: #667085;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}

.event-action {
  color: #344054;
}

.event-message {
  margin-top: 5px;
  color: #344054;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.event-details {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.event-details details {
  min-width: min(280px, 100%);
  max-width: 100%;
  border: 1px solid #eaecf0;
  border-radius: 6px;
  background: #fafbfc;
}

.event-details summary {
  padding: 5px 8px;
  color: #667085;
  cursor: pointer;
  font-size: 12px;
}

.event-details pre {
  max-width: 100%;
  margin: 0;
  padding: 8px;
  overflow: auto;
  border-top: 1px solid #eaecf0;
  color: #344054;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.live-panel {
  margin-bottom: 16px;
  border-color: #dce4ff;
  background: linear-gradient(135deg, #f6f8ff 0%, #ffffff 72%);
}

.live-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}

.live-connection {
  color: #667085;
  font-size: 12px;
  font-weight: 400;
}

.pulse-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 5px;
  border-radius: 50%;
  background: #bfbfbf;
}

.pulse-dot.connected {
  background: #52c41a;
}

@media (prefers-reduced-motion: no-preference) {
  .pulse-dot.connected {
    animation: live-pulse 1.8s ease-in-out infinite;
  }
}

@keyframes live-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.35); }
  50% { box-shadow: 0 0 0 5px rgba(82, 196, 26, 0); }
}

.live-progress-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.live-progress-row :deep(.ant-progress) {
  flex: 1;
}

.live-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 10px;
}

.live-kpi-grid > div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e7ebf7;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
}

.live-kpi-grid span {
  display: block;
  overflow: hidden;
  color: #8c8c8c;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-kpi-grid strong {
  display: block;
  overflow: hidden;
  margin-top: 4px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-kpi-grid strong.danger {
  color: #ff4d4f;
}

.live-log-list {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #e7ebf7;
}

.live-log-title {
  margin-bottom: 6px;
  color: #667085;
  font-size: 12px;
  font-weight: 600;
}

.live-log-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 26px;
  color: #344054;
  font-size: 12px;
}

.live-log-time {
  width: 72px;
  color: #98a2b3;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.artifact-status-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.artifact-status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  color: #667085;
  font-size: 12px;
}

.artifact-status-error {
  color: #d92d20;
}

@media (max-width: 720px) {
  .event-time {
    width: 100%;
  }

  .live-kpi-grid {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }
}
</style>
