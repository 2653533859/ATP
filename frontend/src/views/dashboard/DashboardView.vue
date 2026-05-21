<template>
  <div>
    <a-alert
      v-if="storageAlert"
      style="margin-bottom: 16px"
      type="warning"
      show-icon
      :message="t('dashboard.storage_alert_msg', { bucket: storageAlert.bucket, total: storageAlert.total_gb, threshold: storageAlert.threshold_gb })"
      :description="t('dashboard.storage_alert_desc', { at: formatAlertTime(storageAlert.triggered_at) })"
      closable
    />
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center">
      <h2 style="margin: 0">{{ t('dashboard.title') }}</h2>
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('dashboard.all_projects')"
          allow-clear
          style="width: 200px"
          :options="projectOptions"
        />
        <a-select
          v-model:value="caseType"
          :placeholder="t('dashboard.all_types')"
          allow-clear
          style="width: 160px"
          :options="caseTypeOptions"
        />
        <a-select v-model:value="days" style="width: 120px" :options="dayOptions" />
      </a-space>
    </div>

    <div style="margin-bottom: 16px; color: #666; font-size: 13px">
      {{ t('dashboard.filter_label') }}：{{ activeFilterText }}
    </div>

    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic :title="t('dashboard.total_cases')" :value="overview.total_cases" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic :title="t('dashboard.total_runs')" :value="overview.total_runs" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic
            :title="t('dashboard.pass_rate')"
            :value="overview.pass_rate"
            suffix="%"
            :precision="1"
            :value-style="{ color: overview.pass_rate >= 80 ? '#3f8600' : '#cf1322' }"
          />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic :title="t('dashboard.recent_runs_7d')" :value="overview.recent_runs_7d" />
        </a-card>
      </a-col>
    </a-row>

    <template v-if="!loading && overview.total_runs === 0">
      <a-card>
        <a-empty :description="emptyDescription">
          <a-button type="primary" @click="goToCaseManagement(projectId)">{{ t('dashboard.go_cases') }}</a-button>
        </a-empty>
      </a-card>
    </template>

    <template v-else>
      <a-spin :spinning="loading">
        <a-card :title="t('dashboard.charts.pass_rate_trend')" style="margin-bottom: 24px">
          <v-chart :option="passRateOption" style="height: 320px" autoresize />
        </a-card>

        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <LazyChartCard
              :title="t('dashboard.charts.duration_trend')"
              @visible="onChartVisible('duration', loadDurationTrend)"
            >
              <v-chart :option="durationOption" style="height: 320px" autoresize />
            </LazyChartCard>
          </a-col>
          <a-col :xs="24" :md="12">
            <LazyChartCard
              :title="t('dashboard.charts.failure_top')"
              @visible="onChartVisible('failure', loadFailureTop)"
            >
              <v-chart :option="failureTopOption" style="height: 320px" autoresize @click="handleFailureClick" />
            </LazyChartCard>
          </a-col>
        </a-row>

        <a-row :gutter="16" style="margin-top: 16px">
          <a-col :xs="24" :md="12">
            <LazyChartCard
              :title="t('dashboard.charts.executor_top')"
              @visible="onChartVisible('executor', loadExecutorTop)"
            >
              <v-chart :option="executorTopOption" style="height: 320px" autoresize />
            </LazyChartCard>
          </a-col>
          <a-col :xs="24" :md="12">
            <LazyChartCard
              :title="t('dashboard.charts.trigger_type')"
              @visible="onChartVisible('trigger', loadTriggerTypeStats)"
            >
              <v-chart :option="triggerTypeOption" style="height: 320px" autoresize />
            </LazyChartCard>
          </a-col>
        </a-row>

        <a-row :gutter="16" style="margin-top: 16px">
          <a-col :xs="24" :md="12">
            <LazyChartCard
              :title="t('dashboard.charts.plan_trend')"
              @visible="onChartVisible('plan', loadPlanTrend)"
            >
              <v-chart :option="planTrendOption" style="height: 320px" autoresize />
            </LazyChartCard>
          </a-col>
          <a-col :xs="24" :md="12">
            <LazyChartCard
              :title="t('dashboard.charts.suite_trend')"
              @visible="onChartVisible('suite', loadSuiteTrend)"
            >
              <v-chart :option="suiteTrendOption" style="height: 320px" autoresize />
            </LazyChartCard>
          </a-col>
        </a-row>
      </a-spin>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import LazyChartCard from '@/components/dashboard/LazyChartCard.vue'
import { projectApi, statisticsApi, storageApi, type StatisticsAggregateTrendItem, type StatisticsExecutorTopItem, type StatisticsTriggerTypeStatItem, type StorageAlertPayload } from '@/api'

use([CanvasRenderer, LineChart, BarChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const router = useRouter()
const { t, locale } = useI18n()

type DashboardCaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android'
type Aggregate = 'daily' | 'weekly'

type DashboardParams = {
  project_id?: number
  days: number
  case_type?: DashboardCaseType
}

type TrendParams = DashboardParams & { aggregate: Aggregate }

type AggregateParams = {
  project_id?: number
  days: number
  aggregate: Aggregate
}

type OverviewData = {
  total_cases: number
  total_runs: number
  pass_rate: number
  recent_runs_7d: number
}

type PassRateTrendItem = {
  date: string
  total: number
  passed: number
  rate: number
}

type DurationTrendItem = {
  date: string
  avg_duration_ms: number
  max_duration_ms: number
  run_count: number
}

type FailureTopItem = {
  case_id: number
  project_id: number
  module_id: number
  case_name: string
  case_type: string
  failure_count: number
}

type FailureTopChartPoint = {
  value: number
  _caseId: number
  _projectId: number
  _moduleId: number
}

type ExecutorTopItem = StatisticsExecutorTopItem

type FailureChartClickParams = {
  componentType?: string
  data?: FailureTopChartPoint | null
}

type TriggerTypeStatItem = StatisticsTriggerTypeStatItem

type AggregateTrendItem = StatisticsAggregateTrendItem

const projectId = ref<number | undefined>(undefined)
const days = ref(30)
const caseType = ref<DashboardCaseType | undefined>(undefined)
const loading = ref(false)
const storageAlert = ref<StorageAlertPayload | null>(null)
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const dayOptions = computed(() => [
  { label: t('dashboard.last_7_days'), value: 7 },
  { label: t('dashboard.last_30_days'), value: 30 },
  { label: t('dashboard.last_90_days'), value: 90 },
  { label: t('dashboard.last_180_days'), value: 180 },
  { label: t('dashboard.last_365_days'), value: 365 },
])
const caseTypeOptions = computed(() => [
  { label: t('dashboard.all_types'), value: undefined },
  { label: t('dashboard.case_types.api'), value: 'api' },
  { label: t('dashboard.case_types.graphql'), value: 'graphql' },
  { label: t('dashboard.case_types.websocket'), value: 'websocket' },
  { label: t('dashboard.case_types.grpc'), value: 'grpc' },
  { label: t('dashboard.case_types.web'), value: 'web' },
  { label: t('dashboard.case_types.android'), value: 'android' },
])
const caseTypeLabel = (type: string) => t(`dashboard.case_types.${type}`)
const triggerTypeLabel = (type: string) => {
  const key = `dashboard.trigger_types.${type}`
  const translated = t(key)
  return translated === key ? type : translated
}

const effectiveAggregate = computed<Aggregate>(() => (days.value > 90 ? 'weekly' : 'daily'))

function getProjectLabel(id?: number) {
  if (!id) return t('dashboard.all_projects')
  return projectOptions.value.find(option => option.value === id)?.label ?? `#${id}`
}

const activeFilterText = computed(() => {
  const projectText = getProjectLabel(projectId.value)
  const typeText = caseType.value ? caseTypeLabel(caseType.value) : t('dashboard.all_types')
  return `${projectText} / ${typeText} / ${t('dashboard.filter_window', { days: days.value })}`
})

const emptyDescription = computed(() => {
  return caseType.value
    ? t('dashboard.empty_no_runs_typed', { type: caseTypeLabel(caseType.value) })
    : t('dashboard.empty_no_runs')
})

function createEmptyOverview(): OverviewData {
  return { total_cases: 0, total_runs: 0, pass_rate: 0, recent_runs_7d: 0 }
}

function generateDateRange(startDate: string, endDate: string): string[] {
  const dates: string[] = []
  const current = new Date(startDate)
  const end = new Date(endDate)
  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10))
    current.setDate(current.getDate() + 1)
  }
  return dates
}

function fillPassRateGaps(data: PassRateTrendItem[], numDays: number): PassRateTrendItem[] {
  if (data.length === 0) return []
  // 周聚合时不补零（密度本身就低，X 轴是周一日期）
  if (effectiveAggregate.value === 'weekly') return data

  const today = new Date()
  const start = new Date(today)
  start.setDate(start.getDate() - numDays + 1)

  const startStr = start.toISOString().slice(0, 10)
  const endStr = today.toISOString().slice(0, 10)
  const allDates = generateDateRange(startStr, endStr)

  const dataMap = new Map(data.map(item => [item.date, item]))

  return allDates.map(date => {
    const existing = dataMap.get(date)
    if (existing) return existing
    return { date, total: 0, passed: 0, rate: 0 }
  })
}

function fillDurationGaps(data: DurationTrendItem[], numDays: number): DurationTrendItem[] {
  if (data.length === 0) return []
  if (effectiveAggregate.value === 'weekly') return data

  const today = new Date()
  const start = new Date(today)
  start.setDate(start.getDate() - numDays + 1)

  const startStr = start.toISOString().slice(0, 10)
  const endStr = today.toISOString().slice(0, 10)
  const allDates = generateDateRange(startStr, endStr)

  const dataMap = new Map(data.map(item => [item.date, item]))

  return allDates.map(date => {
    const existing = dataMap.get(date)
    if (existing) return existing
    return { date, avg_duration_ms: 0, max_duration_ms: 0, run_count: 0 }
  })
}

function buildPassRateOption(data: PassRateTrendItem[] = []) {
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: [t('dashboard.charts.pass_rate'), t('dashboard.charts.run_count')] },
    xAxis: { type: 'category' as const, data: data.map(item => item.date) },
    yAxis: [
      { type: 'value' as const, name: t('dashboard.charts.pass_rate_y'), min: 0, max: 100 },
      { type: 'value' as const, name: t('dashboard.charts.run_count') },
    ],
    series: [
      {
        name: t('dashboard.charts.pass_rate'),
        type: 'line' as const,
        smooth: true,
        data: data.map(item => item.rate),
        itemStyle: { color: '#1890ff' },
        areaStyle: { color: 'rgba(24,144,255,0.15)' },
      },
      {
        name: t('dashboard.charts.run_count'),
        type: 'bar' as const,
        yAxisIndex: 1,
        data: data.map(item => item.total),
        itemStyle: { color: 'rgba(24,144,255,0.35)' },
      },
    ],
  }
}

function buildDurationOption(data: DurationTrendItem[] = []) {
  return {
    tooltip: { trigger: 'axis' as const, valueFormatter: (value: number) => `${value} ms` },
    legend: { data: [t('dashboard.charts.avg_duration'), t('dashboard.charts.max_duration')] },
    xAxis: { type: 'category' as const, data: data.map(item => item.date) },
    yAxis: { type: 'value' as const, name: t('dashboard.charts.duration_y') },
    series: [
      {
        name: t('dashboard.charts.avg_duration'),
        type: 'bar' as const,
        data: data.map(item => item.avg_duration_ms),
        itemStyle: { color: '#52c41a' },
      },
      {
        name: t('dashboard.charts.max_duration'),
        type: 'line' as const,
        smooth: true,
        data: data.map(item => item.max_duration_ms),
        itemStyle: { color: '#faad14' },
      },
    ],
  }
}

function buildFailureTopOption(data: FailureTopItem[] = []) {
  const sorted = [...data].reverse()

  return {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '30%' },
    xAxis: { type: 'value' as const, name: t('dashboard.charts.failure_count') },
    yAxis: {
      type: 'category' as const,
      data: sorted.map(item => item.case_name.length > 15 ? item.case_name.slice(0, 15) + '...' : item.case_name),
      triggerEvent: true,
    },
    series: [
      {
        type: 'bar' as const,
        data: sorted.map(item => ({
          value: item.failure_count,
          _caseId: item.case_id,
          _projectId: item.project_id,
          _moduleId: item.module_id,
        })),
        itemStyle: { color: '#ff4d4f' },
        cursor: 'pointer',
      },
    ],
  }
}

function buildExecutorTopOption(data: ExecutorTopItem[] = []) {
  const sorted = [...data].reverse()
  return {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '24%' },
    xAxis: { type: 'value' as const, name: t('dashboard.charts.executor_count') },
    yAxis: {
      type: 'category' as const,
      data: sorted.map(item => item.username),
    },
    series: [
      {
        type: 'bar' as const,
        data: sorted.map(item => item.run_count),
        itemStyle: { color: '#1677ff' },
      },
    ],
  }
}

function buildTriggerTypeOption(data: TriggerTypeStatItem[] = []) {
  return {
    tooltip: { trigger: 'item' as const },
    legend: { bottom: 0 },
    series: [
      {
        name: t('dashboard.charts.trigger_method'),
        type: 'pie' as const,
        radius: ['45%', '70%'],
        data: data.map(item => ({ value: item.count, name: triggerTypeLabel(item.trigger_type) })),
      },
    ],
  }
}

function buildAggregateTrendOption(data: AggregateTrendItem[] = [], label: string) {
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: [`${label} ${t('dashboard.charts.pass_rate_suffix')}`, `${label} ${t('dashboard.charts.run_count_suffix')}`] },
    xAxis: { type: 'category' as const, data: data.map(item => item.date) },
    yAxis: [
      { type: 'value' as const, name: t('dashboard.charts.pass_rate_y'), min: 0, max: 100 },
      { type: 'value' as const, name: t('dashboard.charts.run_count') },
    ],
    series: [
      {
        name: `${label} ${t('dashboard.charts.pass_rate_suffix')}`,
        type: 'line' as const,
        smooth: true,
        data: data.map(item => item.rate),
        itemStyle: { color: '#722ed1' },
        areaStyle: { color: 'rgba(114,46,209,0.15)' },
      },
      {
        name: `${label} ${t('dashboard.charts.run_count_suffix')}`,
        type: 'bar' as const,
        yAxisIndex: 1,
        data: data.map(item => item.total),
        itemStyle: { color: 'rgba(114,46,209,0.3)' },
      },
    ],
  }
}

function goToCaseManagement(targetProjectId?: number, targetModuleId?: number) {
  if (targetProjectId) {
    void router.push({
      name: 'cases',
      query: {
        project_id: String(targetProjectId),
        ...(targetModuleId ? { module_id: String(targetModuleId) } : {}),
      },
    })
    return
  }

  void router.push({ name: 'cases' })
}

function handleFailureClick(params: unknown) {
  const event = params as FailureChartClickParams
  if (event.componentType === 'series' && event.data?._caseId) {
    goToCaseManagement(event.data._projectId, event.data._moduleId)
  }
}

const overview = reactive(createEmptyOverview())
const passRateOption = ref(buildPassRateOption())
const durationOption = ref(buildDurationOption())
const failureTopOption = ref(buildFailureTopOption())
const executorTopOption = ref(buildExecutorTopOption())
const triggerTypeOption = ref(buildTriggerTypeOption())
const planTrendOption = ref(buildAggregateTrendOption([], t('dashboard.charts.plan')))
const suiteTrendOption = ref(buildAggregateTrendOption([], t('dashboard.charts.suite')))

const loadedCharts = ref(new Set<string>())

type ChartKey = 'duration' | 'failure' | 'executor' | 'trigger' | 'plan' | 'suite'

function resetOverview() {
  Object.assign(overview, createEmptyOverview())
}

function currentDashboardParams(): DashboardParams {
  return {
    project_id: projectId.value,
    days: days.value,
    case_type: caseType.value,
  }
}

function currentTrendParams(): TrendParams {
  return { ...currentDashboardParams(), aggregate: effectiveAggregate.value }
}

function currentAggregateParams(): AggregateParams {
  return {
    project_id: projectId.value,
    days: days.value,
    aggregate: effectiveAggregate.value,
  }
}

function onChartVisible(key: ChartKey, loader: () => Promise<void>) {
  loadedCharts.value.add(key)
  void loader()
}

const chartLoaders: Record<ChartKey, () => Promise<void>> = {
  duration: () => loadDurationTrend(),
  failure: () => loadFailureTop(),
  executor: () => loadExecutorTop(),
  trigger: () => loadTriggerTypeStats(),
  plan: () => loadPlanTrend(),
  suite: () => loadSuiteTrend(),
}

async function loadProjects() {
  try {
    const list = await projectApi.list()
    projectOptions.value = list.map(project => ({ label: project.name, value: project.id }))
  } catch {
  }
}

async function loadFirstScreen() {
  loading.value = true
  try {
    await Promise.all([
      loadOverview(),
      loadPassRateTrend(),
    ])
  } finally {
    loading.value = false
  }
}

async function refreshLoadedCharts() {
  const tasks: Promise<void>[] = []
  for (const key of loadedCharts.value) {
    const loader = chartLoaders[key as ChartKey]
    if (loader) tasks.push(loader())
  }
  if (tasks.length) await Promise.all(tasks)
}

async function loadOverview() {
  const params = currentDashboardParams()
  try {
    const data = await statisticsApi.overview({ project_id: params.project_id, days: params.days })
    Object.assign(overview, data)
  } catch {
    resetOverview()
  }
}

async function loadPassRateTrend() {
  const params = currentTrendParams()
  try {
    const data = await statisticsApi.passRateTrend(params)
    const filled = fillPassRateGaps(data, params.days)
    passRateOption.value = buildPassRateOption(filled)
  } catch {
    passRateOption.value = buildPassRateOption()
  }
}

async function loadDurationTrend() {
  const params = currentTrendParams()
  try {
    const data = await statisticsApi.durationTrend(params)
    const filled = fillDurationGaps(data, params.days)
    durationOption.value = buildDurationOption(filled)
  } catch {
    durationOption.value = buildDurationOption()
  }
}

async function loadFailureTop() {
  const params = currentDashboardParams()
  try {
    const data = await statisticsApi.failureTop({ ...params, top: 10 })
    failureTopOption.value = buildFailureTopOption(data)
  } catch {
    failureTopOption.value = buildFailureTopOption()
  }
}

async function loadExecutorTop() {
  const params = currentDashboardParams()
  try {
    const data = await statisticsApi.executorTop({ ...params, top: 10 })
    executorTopOption.value = buildExecutorTopOption(data)
  } catch {
    executorTopOption.value = buildExecutorTopOption()
  }
}

async function loadTriggerTypeStats() {
  try {
    const data = await statisticsApi.triggerTypeStats({ project_id: projectId.value, days: days.value })
    triggerTypeOption.value = buildTriggerTypeOption(data)
  } catch {
    triggerTypeOption.value = buildTriggerTypeOption()
  }
}

async function loadPlanTrend() {
  const params = currentAggregateParams()
  try {
    const data = await statisticsApi.planTrend(params)
    planTrendOption.value = buildAggregateTrendOption(data, t('dashboard.charts.plan'))
  } catch {
    planTrendOption.value = buildAggregateTrendOption([], t('dashboard.charts.plan'))
  }
}

async function loadSuiteTrend() {
  const params = currentAggregateParams()
  try {
    const data = await statisticsApi.suiteTrend(params)
    suiteTrendOption.value = buildAggregateTrendOption(data, t('dashboard.charts.suite'))
  } catch {
    suiteTrendOption.value = buildAggregateTrendOption([], t('dashboard.charts.suite'))
  }
}

watch([projectId, days, caseType], async () => {
  await loadFirstScreen()
  await refreshLoadedCharts()
})

// 语言切换：重新拉取数据以让 echarts 配置中的 t() 文案刷新
watch(locale, async () => {
  await loadFirstScreen()
  await refreshLoadedCharts()
})

onMounted(() => {
  void loadProjects()
  void loadFirstScreen()
  void loadStorageAlert()
})

async function loadStorageAlert() {
  try {
    const resp = await storageApi.getAlert()
    storageAlert.value = resp?.alert ?? null
  } catch {
    storageAlert.value = null
  }
}

function formatAlertTime(value?: string | null) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
</script>
