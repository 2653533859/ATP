<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
      <h2 style="margin: 0">{{ t('mobile_special.reports.title') }}</h2>
      <a-select
        v-model:value="selectedProjectId"
        :placeholder="t('mobile_special.select_project')"
        style="width: 200px"
        :options="projectOptions"
        allow-clear
        @change="onProjectChange"
      />
      <a-select
        v-model:value="selectedTaskType"
        :placeholder="t('mobile_special.task_type')"
        style="width: 140px"
        :options="taskTypeOptions"
        allow-clear
        @change="loadRuns"
      />
      <a-select
        v-model:value="selectedStatus"
        :placeholder="t('mobile_special.reports.status')"
        style="width: 120px"
        :options="statusOptions"
        allow-clear
        @change="loadRuns"
      />
      <a-range-picker
        v-model:value="dateRange"
        :placeholder="[t('mobile_special.reports.start_date'), t('mobile_special.reports.end_date')]"
        style="width: 260px"
        @change="loadRuns"
      />
    </div>

    <!-- Overview KPI Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px">
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ t('mobile_special.reports.total_runs') }}</div>
        <div style="font-size: 24px; font-weight: 600; color: #1890ff">{{ overview.total_runs }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ t('mobile_special.reports.completion_rate') }}</div>
        <div style="font-size: 24px; font-weight: 600; color: #52c41a">{{ overview.pass_rate }}%</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ t('mobile_special.reports.recent_runs_7d') }}</div>
        <div style="font-size: 24px; font-weight: 600; color: #722ed1">{{ overview.recent_runs_7d }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ t('mobile_special.reports.failed_runs') }}</div>
        <div style="font-size: 24px; font-weight: 600; color: #ff4d4f">{{ overview.failed_runs }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ t('mobile_special.reports.incidents') }}</div>
        <div style="font-size: 24px; font-weight: 600; color: #faad14">{{ overview.total_incidents }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">{{ t('mobile_special.reports.avg_duration') }}</div>
        <div style="font-size: 24px; font-weight: 600; color: #13c2c2">
          {{ overview.avg_duration_ms ? (overview.avg_duration_ms / 1000).toFixed(1) + 's' : '-' }}
        </div>
      </a-card>
    </div>

    <!-- Trend Chart -->
    <a-card style="margin-bottom: 16px" :body-style="{ padding: '12px 16px' }">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
        <span style="font-size: 14px; font-weight: 500">{{ t('mobile_special.reports.trend_title') }}</span>
        <span style="font-size: 12px; color: #999">
          {{ t('mobile_special.reports.trend_summary', { completed: trendCompleted, failed: trendFailed }) }}
        </span>
      </div>
      <div ref="trendChartRef" style="width: 100%; height: 220px"></div>
    </a-card>

    <!-- Run Table -->
    <a-spin :spinning="loading">
      <a-table
        :data-source="runs"
        :columns="columns"
        :pagination="{ pageSize: 15 }"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'task_type'">
            <a-tag :color="taskTypeColor(record.task_type)">{{ taskTypeLabel(record.task_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'duration'">
            {{ record.duration_ms ? `${(record.duration_ms / 1000).toFixed(1)}s` : '-' }}
          </template>
          <template v-else-if="column.key === 'started_at'">
            {{ record.started_at ? formatDate(record.started_at) : '-' }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="primary" size="small" @click="viewDetail(record)">{{ t('case.actions.detail') }}</a-button>
            <a-dropdown>
              <a-button type="link" size="small">{{ t('common.export') }}</a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="csv" @click="exportCsv(record)">{{ t('mobile_special.reports.csv_metrics') }}</a-menu-item>
                  <a-menu-item key="json" @click="exportJson(record)">{{ t('mobile_special.reports.json_report') }}</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
            <a-button
              v-if="record.status === 'running' || record.status === 'pending'"
              type="link"
              size="small"
              danger
              @click="handleStop(record)"
            >{{ t('mobile_special.reports.stop') }}</a-button>
          </template>
        </template>
      </a-table>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { init, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { useChartTheme } from '@/utils/chartTheme'
import { projectApi, mobileSpecialApi, type MobileSpecialRunItem, type ProjectItem, type TaskType, type MobileRunStatus } from '@/api'
import {
  addMobileRunTaskFallback,
  buildMobileRunQuery,
  filterMobileRunsByDateRange,
  summarizeMobileTrend,
  type DateRangeValue,
} from '@/utils/mobileReport'

const router = useRouter()
const { t, locale } = useI18n()
const { chartTheme } = useChartTheme()
const loading = ref(false)
const runs = ref<MobileSpecialRunItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const selectedProjectId = ref<number | null>(null)
const selectedTaskType = ref<TaskType | null>(null)
const selectedStatus = ref<MobileRunStatus | null>(null)
const dateRange = ref<[DateRangeValue, DateRangeValue] | null>(null)

const overview = ref({
  total_runs: 0, completed_runs: 0, failed_runs: 0, running_runs: 0,
  pass_rate: 0, avg_duration_ms: null as number | null, total_incidents: 0, recent_runs_7d: 0,
})
const trendCompleted = ref(0)
const trendFailed = ref(0)
const latestTrend = ref<Array<{ date: string; total: number; completed: number; failed: number; pass_rate: number }>>([])

const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: ECharts | null = null

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

const taskTypeOptions = computed(() => [
  { label: t('mobile_special.task_types.performance'), value: 'performance' },
  { label: t('mobile_special.task_types.stability'), value: 'stability' },
  { label: t('mobile_special.task_types.fluency'), value: 'fluency' },
])

const statusOptions = computed(() => [
  { label: t('mobile_special.statuses.completed'), value: 'completed' },
  { label: t('mobile_special.statuses.running'), value: 'running' },
  { label: t('mobile_special.statuses.failed'), value: 'failed' },
  { label: t('mobile_special.statuses.stopped'), value: 'stopped' },
])

const columns = computed(() => [
  { title: t('mobile_special.columns.name'), key: 'task_name', dataIndex: 'task_name', width: 180, ellipsis: true },
  { title: t('common.type'), key: 'task_type', dataIndex: 'task_type', width: 100 },
  { title: t('common.status'), key: 'status', dataIndex: 'status', width: 90 },
  { title: t('mobile_special.reports.device'), key: 'device_serial', dataIndex: 'device_serial', width: 140, ellipsis: true },
  { title: t('mobile_special.columns.app_package'), key: 'app_package', dataIndex: 'app_package', width: 160, ellipsis: true },
  { title: t('mobile_special.reports.duration'), key: 'duration', width: 90 },
  { title: t('mobile_special.reports.started_at'), key: 'started_at', width: 160 },
  { title: t('common.action'), key: 'action', width: 200 },
])

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projectOptions.value = list.map((p: ProjectItem) => ({ label: p.name, value: p.id }))
    if (list.length > 0) {
      selectedProjectId.value = list[0].id
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.msg.load_projects_failed')))
  }
  await Promise.all([loadOverview(), loadRuns()])
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

async function onProjectChange() {
  await Promise.all([loadOverview(), loadRuns()])
}

async function loadOverview() {
  try {
    const data = await mobileSpecialApi.getOverview({
      project_id: selectedProjectId.value ?? undefined,
      days: 30,
    })
    overview.value = data
  } catch { /* ignore */ }
}

async function loadRuns() {
  loading.value = true
  try {
    const data = await mobileSpecialApi.listRuns(buildMobileRunQuery({
      projectId: selectedProjectId.value,
      taskType: selectedTaskType.value,
      status: selectedStatus.value,
    }))
    const filtered = filterMobileRunsByDateRange(data, dateRange.value)
    runs.value = addMobileRunTaskFallback(
      filtered,
      (taskId) => t('mobile_special.reports.task_fallback', { id: taskId }),
    )

    // Load trend data
    await loadTrend()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  try {
    const trend = await mobileSpecialApi.getTrend({
      project_id: selectedProjectId.value ?? undefined,
      days: 14,
    })
    const summary = summarizeMobileTrend(trend)
    trendCompleted.value = summary.completed
    trendFailed.value = summary.failed
    latestTrend.value = trend
    updateTrendChart(trend)
  } catch { /* ignore */ }
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = init(trendChartRef.value, chartTheme.value)
}

function updateTrendChart(trend: Array<{ date: string; total: number; completed: number; failed: number; pass_rate: number }>) {
  if (!trendChart) return

  const dates = trend.map(d => d.date.slice(5))
  const completedData = trend.map(d => d.completed)
  const failedData = trend.map(d => d.failed)

  const option: EChartsCoreOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: [t('mobile_special.statuses.completed'), t('mobile_special.statuses.failed')], bottom: 0 },
    grid: { top: 10, right: 20, bottom: 36, left: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series: [
      { name: t('mobile_special.statuses.completed'), type: 'bar', data: completedData, itemStyle: { color: '#52c41a' } },
      { name: t('mobile_special.statuses.failed'), type: 'bar', data: failedData, itemStyle: { color: '#ff4d4f' } },
    ],
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

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString()
}

function viewDetail(record: MobileSpecialRunItem) {
  router.push(`/mobile-special/reports/${record.id}`)
}

async function exportCsv(record: MobileSpecialRunItem) {
  try {
    const blob = await mobileSpecialApi.exportRunCsv(record.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mobile_run_${record.id}_metrics.csv`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('mobile_special.reports.msg.csv_downloaded'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.export_failed')))
  }
}

async function exportJson(record: MobileSpecialRunItem) {
  try {
    const blob = await mobileSpecialApi.exportRunJson(record.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mobile_run_${record.id}_report.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('mobile_special.reports.msg.json_downloaded'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.export_failed')))
  }
}

async function handleStop(record: MobileSpecialRunItem) {
  try {
    await mobileSpecialApi.stopRun(record.id)
    message.success(t('mobile_special.reports.msg.stopped'))
    await loadRuns()
    await loadOverview()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('mobile_special.reports.msg.stop_failed')))
  }
}

watch(locale, () => updateTrendChart(latestTrend.value))
watch(chartTheme, () => {
  trendChart?.dispose()
  trendChart = null
  initTrendChart()
  updateTrendChart(latestTrend.value)
})
</script>
