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
                <a-button type="link" size="small" @click="downloadArtifact(record)">{{ t('mobile_special.reports.download') }}</a-button>
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
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { useChartTheme } from '@/utils/chartTheme'
import {
  mobileSpecialApi,
  type MobileSpecialRunItem,
  type MobileSpecialTaskItem,
  type MobileMetricSampleItem,
  type MobileIncidentItem,
  type MobileRunArtifactItem,
  type ArtifactType,
  type IncidentType,
  type MobileRunStatus,
  type MobileTriggerType,
  type TaskType,
} from '@/api'

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
const samples = ref<MobileMetricSampleItem[]>([])
const incidents = ref<MobileIncidentItem[]>([])
const artifacts = ref<MobileRunArtifactItem[]>([])

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
  { label: 'CPU (%)', value: 'cpu_pct' },
  { label: t('mobile_special.reports.metrics.battery'), value: 'battery_pct' },
  { label: 'FPS', value: 'fps' },
])

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
  if (!samples.value.length) return []
  const summary = run.value?.summary_json ?? {}

  const byType = (type: string) => {
    const vals = samples.value.filter(s => s.metric_type === type).map(s => s.metric_value)
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
    ...(fps ? [{ label: t('mobile_special.reports.kpi.jank_count'), value: Number(summary.jank_count ?? 0), unit: t('mobile_special.reports.units.times'), color: '#ff4d4f' }] : []),
    ...(incidents.value.length ? [{ label: t('mobile_special.reports.incidents'), value: incidents.value.length, unit: t('mobile_special.reports.units.items'), color: '#ff4d4f' }] : []),
    ...(run.value?.duration_ms ? [{ label: t('mobile_special.reports.kpi.total_duration'), value: (run.value.duration_ms / 1000).toFixed(1), unit: 's', color: '#722ed1' }] : []),
  ].slice(0, 6)
})

onMounted(async () => {
  await loadAll()
  initTrendChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  trendChart?.dispose()
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  trendChart?.resize()
}

async function loadAll() {
  loading.value = true
  try {
    const [runData, samplesData, incidentsData, artifactsData] = await Promise.all([
      mobileSpecialApi.getRun(runId.value),
      mobileSpecialApi.getRunSamples(runId.value, { limit: 500 }),
      mobileSpecialApi.getRunIncidents(runId.value),
      mobileSpecialApi.getRunArtifacts(runId.value),
    ])

    run.value = runData
    samples.value = samplesData
    incidents.value = incidentsData
    artifacts.value = artifactsData

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
    samples.value = data
    updateTrendChart()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.load_metrics_failed')))
  }
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value, chartTheme.value)
  updateTrendChart()
}

function updateTrendChart() {
  if (!trendChart) return

  const filtered = samples.value
    .filter(s => s.metric_type === selectedMetricType.value)
    .sort((a, b) => new Date(a.sample_time).getTime() - new Date(b.sample_time).getTime())

  const times = filtered.map(s => new Date(s.sample_time).toLocaleTimeString())
  const values = filtered.map(s => s.metric_value)

  const unitMap: Record<string, string> = { mem_mb: 'MB', cpu_pct: '%', battery_pct: '%', fps: '' }
  const colorMap: Record<string, string> = { mem_mb: '#1890ff', cpu_pct: '#faad14', battery_pct: '#52c41a', fps: '#722ed1' }

  const option: EChartsOption = {
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
    message.info(t('mobile_special.reports.msg.download_pending', { file: record.file_name }))
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
