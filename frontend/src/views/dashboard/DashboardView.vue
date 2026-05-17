<template>
  <div>
    <a-alert
      v-if="storageAlert"
      style="margin-bottom: 16px"
      type="warning"
      show-icon
      :message="`存储使用率告警：${storageAlert.bucket} 当前已使用 ${storageAlert.total_gb} GB，已超过阈值 ${storageAlert.threshold_gb} GB`"
      :description="`触发时间：${formatAlertTime(storageAlert.triggered_at)}。请到「存储管理」页面执行清理或调整策略。`"
      closable
    />
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center">
      <h2 style="margin: 0">统计看板</h2>
      <a-space>
        <a-select
          v-model:value="projectId"
          placeholder="全部项目"
          allow-clear
          style="width: 200px"
          :options="projectOptions"
        />
        <a-select
          v-model:value="caseType"
          placeholder="全部类型"
          allow-clear
          style="width: 160px"
          :options="caseTypeOptions"
        />
        <a-select v-model:value="days" style="width: 120px" :options="dayOptions" />
      </a-space>
    </div>

    <div style="margin-bottom: 16px; color: #666; font-size: 13px">
      当前筛选：{{ activeFilterText }}
    </div>

    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic title="总用例数" :value="overview.total_cases" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic title="总执行次数" :value="overview.total_runs" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic
            title="通过率"
            :value="overview.pass_rate"
            suffix="%"
            :precision="1"
            :value-style="{ color: overview.pass_rate >= 80 ? '#3f8600' : '#cf1322' }"
          />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <a-card>
          <a-statistic title="近 7 日执行" :value="overview.recent_runs_7d" />
        </a-card>
      </a-col>
    </a-row>

    <template v-if="!loading && overview.total_runs === 0">
      <a-card>
        <a-empty :description="emptyDescription">
          <a-button type="primary" @click="goToCaseManagement(projectId)">前往用例管理</a-button>
        </a-empty>
      </a-card>
    </template>

    <template v-else>
      <a-spin :spinning="loading">
        <a-card title="通过率趋势" style="margin-bottom: 24px">
          <v-chart :option="passRateOption" style="height: 320px" autoresize />
        </a-card>

        <a-row :gutter="16">
          <a-col :xs="24" :md="12">
            <a-card title="执行时长趋势">
              <v-chart :option="durationOption" style="height: 320px" autoresize />
            </a-card>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-card title="失败 Top 10">
              <v-chart :option="failureTopOption" style="height: 320px" autoresize @click="handleFailureClick" />
            </a-card>
          </a-col>
        </a-row>

        <a-row :gutter="16" style="margin-top: 16px">
          <a-col :xs="24" :md="12">
            <a-card title="执行人 Top 10">
              <v-chart :option="executorTopOption" style="height: 320px" autoresize />
            </a-card>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-card title="触发方式分布">
              <v-chart :option="triggerTypeOption" style="height: 320px" autoresize />
            </a-card>
          </a-col>
        </a-row>

        <a-row :gutter="16" style="margin-top: 16px">
          <a-col :xs="24" :md="12">
            <a-card title="计划执行趋势">
              <v-chart :option="planTrendOption" style="height: 320px" autoresize />
            </a-card>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-card title="套件执行趋势">
              <v-chart :option="suiteTrendOption" style="height: 320px" autoresize />
            </a-card>
          </a-col>
        </a-row>
      </a-spin>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { projectApi, statisticsApi, storageApi, type StatisticsAggregateTrendItem, type StatisticsExecutorTopItem, type StatisticsTriggerTypeStatItem, type StorageAlertPayload } from '@/api'

use([CanvasRenderer, LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const router = useRouter()

type DashboardCaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android'

type DashboardParams = {
  project_id?: number
  days: number
  case_type?: DashboardCaseType
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
const dayOptions = [
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
]
const caseTypeOptions = [
  { label: '全部类型', value: undefined },
  { label: '接口', value: 'api' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
  { label: 'gRPC', value: 'grpc' },
  { label: 'Web', value: 'web' },
  { label: 'Android', value: 'android' },
]
const caseTypeLabelMap: Record<string, string> = {
  api: '接口',
  graphql: 'GraphQL',
  websocket: 'WebSocket',
  grpc: 'gRPC',
  web: 'Web',
  android: 'Android',
}
const triggerTypeLabelMap: Record<string, string> = {
  manual: '手动',
  cron: '定时',
  webhook: 'Webhook',
}

function getProjectLabel(id?: number) {
  if (!id) return '全部项目'
  return projectOptions.value.find(option => option.value === id)?.label ?? `项目 #${id}`
}

const activeFilterText = computed(() => {
  const projectText = getProjectLabel(projectId.value)
  const typeText = caseType.value ? caseTypeLabelMap[caseType.value] : '全部类型'
  return `${projectText} / ${typeText} / 近 ${days.value} 天`
})

const emptyDescription = computed(() => {
  return caseType.value
    ? `当前筛选下还没有 ${caseTypeLabelMap[caseType.value]} 执行记录，去创建并执行对应类型用例吧`
    : '还没有执行记录，去创建用例并执行吧'
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
    legend: { data: ['通过率', '执行数'] },
    xAxis: { type: 'category' as const, data: data.map(item => item.date) },
    yAxis: [
      { type: 'value' as const, name: '通过率(%)', min: 0, max: 100 },
      { type: 'value' as const, name: '执行数' },
    ],
    series: [
      {
        name: '通过率',
        type: 'line' as const,
        smooth: true,
        data: data.map(item => item.rate),
        itemStyle: { color: '#1890ff' },
        areaStyle: { color: 'rgba(24,144,255,0.15)' },
      },
      {
        name: '执行数',
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
    legend: { data: ['平均时长', '最大时长'] },
    xAxis: { type: 'category' as const, data: data.map(item => item.date) },
    yAxis: { type: 'value' as const, name: '时长(ms)' },
    series: [
      {
        name: '平均时长',
        type: 'bar' as const,
        data: data.map(item => item.avg_duration_ms),
        itemStyle: { color: '#52c41a' },
      },
      {
        name: '最大时长',
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
    xAxis: { type: 'value' as const, name: '失败次数' },
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
    xAxis: { type: 'value' as const, name: '执行次数' },
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
        name: '触发方式',
        type: 'pie' as const,
        radius: ['45%', '70%'],
        data: data.map(item => ({ value: item.count, name: triggerTypeLabelMap[item.trigger_type] ?? item.trigger_type })),
      },
    ],
  }
}

function buildAggregateTrendOption(data: AggregateTrendItem[] = [], label: string) {
  return {
    tooltip: { trigger: 'axis' as const },
    legend: { data: [`${label}通过率`, `${label}执行数`] },
    xAxis: { type: 'category' as const, data: data.map(item => item.date) },
    yAxis: [
      { type: 'value' as const, name: '通过率(%)', min: 0, max: 100 },
      { type: 'value' as const, name: '执行数' },
    ],
    series: [
      {
        name: `${label}通过率`,
        type: 'line' as const,
        smooth: true,
        data: data.map(item => item.rate),
        itemStyle: { color: '#722ed1' },
        areaStyle: { color: 'rgba(114,46,209,0.15)' },
      },
      {
        name: `${label}执行数`,
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
const planTrendOption = ref(buildAggregateTrendOption([], '计划'))
const suiteTrendOption = ref(buildAggregateTrendOption([], '套件'))

function resetOverview() {
  Object.assign(overview, createEmptyOverview())
}

async function loadProjects() {
  try {
    const list = await projectApi.list()
    projectOptions.value = list.map(project => ({ label: project.name, value: project.id }))
  } catch {
  }
}

async function loadAll() {
  loading.value = true
  const params: DashboardParams = {
    project_id: projectId.value,
    days: days.value,
    case_type: caseType.value,
  }
  const aggregateParams = {
    project_id: projectId.value,
    days: days.value,
  }

  try {
    await Promise.all([
      loadOverview(params),
      loadPassRateTrend(params),
      loadDurationTrend(params),
      loadFailureTop(params),
      loadExecutorTop(params),
      loadTriggerTypeStats(aggregateParams),
      loadPlanTrend(aggregateParams),
      loadSuiteTrend(aggregateParams),
    ])
  } finally {
    loading.value = false
  }
}

async function loadOverview(params: DashboardParams) {
  try {
    const data = await statisticsApi.overview(params)
    Object.assign(overview, data)
  } catch {
    resetOverview()
  }
}

async function loadPassRateTrend(params: DashboardParams) {
  try {
    const data = await statisticsApi.passRateTrend(params)
    const filled = fillPassRateGaps(data, params.days)
    passRateOption.value = buildPassRateOption(filled)
  } catch {
    passRateOption.value = buildPassRateOption()
  }
}

async function loadDurationTrend(params: DashboardParams) {
  try {
    const data = await statisticsApi.durationTrend(params)
    const filled = fillDurationGaps(data, params.days)
    durationOption.value = buildDurationOption(filled)
  } catch {
    durationOption.value = buildDurationOption()
  }
}

async function loadFailureTop(params: DashboardParams) {
  try {
    const data = await statisticsApi.failureTop({ ...params, top: 10 })
    failureTopOption.value = buildFailureTopOption(data)
  } catch {
    failureTopOption.value = buildFailureTopOption()
  }
}

async function loadExecutorTop(params: DashboardParams) {
  try {
    const data = await statisticsApi.executorTop({ ...params, top: 10 })
    executorTopOption.value = buildExecutorTopOption(data)
  } catch {
    executorTopOption.value = buildExecutorTopOption()
  }
}

async function loadTriggerTypeStats(params: { project_id?: number; days: number }) {
  try {
    const data = await statisticsApi.triggerTypeStats(params)
    triggerTypeOption.value = buildTriggerTypeOption(data)
  } catch {
    triggerTypeOption.value = buildTriggerTypeOption()
  }
}

async function loadPlanTrend(params: { project_id?: number; days: number }) {
  try {
    const data = await statisticsApi.planTrend(params)
    planTrendOption.value = buildAggregateTrendOption(data, '计划')
  } catch {
    planTrendOption.value = buildAggregateTrendOption([], '计划')
  }
}

async function loadSuiteTrend(params: { project_id?: number; days: number }) {
  try {
    const data = await statisticsApi.suiteTrend(params)
    suiteTrendOption.value = buildAggregateTrendOption(data, '套件')
  } catch {
    suiteTrendOption.value = buildAggregateTrendOption([], '套件')
  }
}

watch([projectId, days, caseType], () => {
  void loadAll()
})

onMounted(() => {
  void loadProjects()
  void loadAll()
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
