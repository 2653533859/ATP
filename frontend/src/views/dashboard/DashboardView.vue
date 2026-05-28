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
    <a-alert
      v-if="dashboardAlertEvents.length"
      style="margin-bottom: 16px"
      type="error"
      show-icon
      :message="t('dashboard.dashboard_alert_msg', { count: dashboardAlertEvents.length })"
      :description="t('dashboard.dashboard_alert_desc', { at: formatAlertTime(dashboardAlertEvents[0]?.triggered_at) })"
    >
      <template #action>
        <a-button size="small" type="link" @click="goToDashboardAlerts">
          {{ t('dashboard.dashboard_alert_action') }}
        </a-button>
      </template>
    </a-alert>
    <div class="dashboard-header">
      <div>
        <h2 style="margin: 0">{{ t('dashboard.title') }}</h2>
        <div class="scope-label">
          {{ dashboardScope === 'global'
            ? t('dashboard.scope_global_label')
            : t('dashboard.scope_project_label', { project: getProjectLabel(projectId) }) }}
        </div>
      </div>
      <a-space wrap>
        <a-segmented v-model:value="dashboardScope" :options="scopeOptions" />
        <a-select
          v-if="dashboardScope === 'project'"
          v-model:value="projectId"
          :placeholder="t('dashboard.select_project')"
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
        <a-button @click="settingsOpen = true">
          <SettingOutlined /> {{ t('dashboard.layout_settings') }}
        </a-button>
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
        <a-empty v-if="visibleChartConfigs.length === 0" :description="t('dashboard.layout_empty')" />
        <a-row v-else :gutter="[16, 16]">
          <a-col
            v-for="chart in visibleChartConfigs"
            :key="chart.key"
            :xs="24"
            :md="chart.span"
          >
            <LazyChartCard
              :title="chart.title"
              @visible="onChartVisible(chart.lazyKey, chart.loader)"
            >
              <template #extra>
                <a-dropdown>
                  <a-button size="small"><DownloadOutlined /></a-button>
                  <template #overlay>
                    <a-menu @click="handleExportMenu(chart.exportKey, $event)">
                      <a-menu-item key="png">{{ t('dashboard.export_png') }}</a-menu-item>
                      <a-menu-item key="csv">{{ t('dashboard.export_csv') }}</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </template>
              <v-chart
                :ref="el => setChartRef(chart.exportKey, el)"
                :option="chart.option.value"
                style="height: 320px"
                autoresize
                @click="params => handleChartClick(chart.key, params)"
              />
            </LazyChartCard>
          </a-col>
        </a-row>
      </a-spin>
    </template>

    <a-modal
      v-model:open="settingsOpen"
      :title="t('dashboard.layout_settings')"
      width="560px"
      :ok-text="t('common.ok')"
      :cancel-text="t('common.cancel')"
    >
      <Draggable
        v-model="dashboardLayout"
        item-key="key"
        handle=".drag-handle"
      >
        <template #item="{ element, index }">
          <div class="layout-row">
            <span class="drag-handle">☰</span>
            <a-checkbox v-model:checked="element.visible">
              {{ chartTitle(element.key) }}
            </a-checkbox>
            <a-space>
              <a-button size="small" :disabled="index === 0" @click="moveLayoutItem(index, -1)">↑</a-button>
              <a-button size="small" :disabled="index === dashboardLayout.length - 1" @click="moveLayoutItem(index, 1)">↓</a-button>
            </a-space>
          </div>
        </template>
      </Draggable>
      <template #footer>
        <a-button @click="resetDashboardLayout">{{ t('dashboard.layout_reset') }}</a-button>
        <a-button type="primary" @click="settingsOpen = false">{{ t('common.ok') }}</a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type ComponentPublicInstance } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import Draggable from 'vuedraggable'
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
import { DownloadOutlined, SettingOutlined } from '@ant-design/icons-vue'
import LazyChartCard from '@/components/dashboard/LazyChartCard.vue'
import { dashboardAlertApi, projectApi, statisticsApi, storageApi, type DashboardAlertEventItem, type StatisticsAggregateTrendItem, type StatisticsCaseTypeDistributionItem, type StatisticsExecutorTopItem, type StatisticsTriggerTypeStatItem, type StorageAlertPayload } from '@/api'

use([CanvasRenderer, LineChart, BarChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const router = useRouter()
const { t, locale } = useI18n()

type DashboardCaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android'
type Aggregate = 'daily' | 'weekly'
type DashboardScope = 'global' | 'project'
type ExportChartKey = 'pass_rate_trend' | 'duration_trend' | 'failure_top' | 'executor_top' | 'trigger_type' | 'plan_trend' | 'suite_trend' | 'case_type_distribution'
type ExportAction = 'png' | 'csv'
type MenuClickInfo = { key: string | number }
type LayoutChartKey = ExportChartKey
type ChartRef = {
  getDataURL?: (options: { pixelRatio?: number; backgroundColor?: string }) => string
  chart?: {
    getDataURL?: (options: { pixelRatio?: number; backgroundColor?: string }) => string
  }
}

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

const DASHBOARD_SCOPE_KEY = 'atp:dashboard:scope'
const DASHBOARD_PROJECT_KEY = 'atp:dashboard:project_id'
const DASHBOARD_LAYOUT_KEY = 'atp:dashboard:layout'

type LayoutItem = {
  key: LayoutChartKey
  visible: boolean
}

const DEFAULT_DASHBOARD_LAYOUT: LayoutItem[] = [
  { key: 'pass_rate_trend', visible: true },
  { key: 'duration_trend', visible: true },
  { key: 'failure_top', visible: true },
  { key: 'executor_top', visible: true },
  { key: 'trigger_type', visible: true },
  { key: 'plan_trend', visible: true },
  { key: 'suite_trend', visible: true },
  { key: 'case_type_distribution', visible: true },
]

function initialScope(): DashboardScope {
  try {
    return localStorage.getItem(DASHBOARD_SCOPE_KEY) === 'project' ? 'project' : 'global'
  } catch {
    return 'global'
  }
}

function initialProjectId(): number | undefined {
  try {
    const raw = localStorage.getItem(DASHBOARD_PROJECT_KEY)
    const parsed = raw ? Number(raw) : undefined
    return Number.isFinite(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function cloneDefaultLayout(): LayoutItem[] {
  return DEFAULT_DASHBOARD_LAYOUT.map(item => ({ ...item }))
}

function loadDashboardLayout(): LayoutItem[] {
  try {
    const raw = localStorage.getItem(DASHBOARD_LAYOUT_KEY)
    if (!raw) return cloneDefaultLayout()
    const parsed = JSON.parse(raw) as Array<Partial<LayoutItem>>
    const byKey = new Map(parsed.map(item => [item.key, item]))
    const knownKeys = new Set(DEFAULT_DASHBOARD_LAYOUT.map(item => item.key))
    const ordered = parsed
      .filter((item): item is LayoutItem => Boolean(item.key && knownKeys.has(item.key) && typeof item.visible === 'boolean'))
      .map(item => ({ key: item.key, visible: item.visible }))
    for (const defaultItem of DEFAULT_DASHBOARD_LAYOUT) {
      if (!byKey.has(defaultItem.key)) ordered.push({ ...defaultItem })
    }
    return ordered.length ? ordered : cloneDefaultLayout()
  } catch {
    return cloneDefaultLayout()
  }
}

const dashboardScope = ref<DashboardScope>(initialScope())
const projectId = ref<number | undefined>(initialProjectId())
const settingsOpen = ref(false)
const dashboardLayout = ref<LayoutItem[]>(loadDashboardLayout())
const days = ref(30)
const caseType = ref<DashboardCaseType | undefined>(undefined)
const loading = ref(false)
const storageAlert = ref<StorageAlertPayload | null>(null)
const dashboardAlertEvents = ref<DashboardAlertEventItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const passRateChartRef = ref<ChartRef | null>(null)
const durationChartRef = ref<ChartRef | null>(null)
const failureTopChartRef = ref<ChartRef | null>(null)
const executorTopChartRef = ref<ChartRef | null>(null)
const triggerTypeChartRef = ref<ChartRef | null>(null)
const planTrendChartRef = ref<ChartRef | null>(null)
const suiteTrendChartRef = ref<ChartRef | null>(null)
const caseTypeDistributionChartRef = ref<ChartRef | null>(null)
const scopeOptions = computed(() => [
  { label: t('dashboard.scope_global'), value: 'global' },
  { label: t('dashboard.scope_project'), value: 'project' },
])
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
const effectiveProjectId = computed(() => dashboardScope.value === 'project' ? projectId.value : undefined)

function getProjectLabel(id?: number) {
  if (!id) return t('dashboard.all_projects')
  return projectOptions.value.find(option => option.value === id)?.label ?? `#${id}`
}

const activeFilterText = computed(() => {
  const projectText = dashboardScope.value === 'global' ? t('dashboard.scope_global') : getProjectLabel(projectId.value)
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

function caseTypeLabelForPie(value: string): string {
  return t(`dashboard.case_types.${value}`, value)
}

function buildCaseTypeDistributionOption(data: StatisticsCaseTypeDistributionItem[] = []) {
  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: { name: string; value: number; percent: number; data: { passed?: number; failed?: number; error?: number; pass_rate?: number } }) => {
        const d = params.data
        return `${params.name}<br/>${t('dashboard.charts.case_type_pie.total')}: ${params.value} (${params.percent}%)<br/>` +
          `${t('dashboard.charts.case_type_pie.passed')}: ${d.passed ?? 0}<br/>` +
          `${t('dashboard.charts.case_type_pie.failed')}: ${d.failed ?? 0}<br/>` +
          `${t('dashboard.charts.case_type_pie.error')}: ${d.error ?? 0}<br/>` +
          `${t('dashboard.charts.case_type_pie.pass_rate')}: ${d.pass_rate ?? 0}%`
      },
    },
    legend: { bottom: 0 },
    series: [
      {
        name: t('dashboard.charts.case_type_distribution'),
        type: 'pie' as const,
        radius: ['45%', '70%'],
        data: data.map(item => ({
          value: item.total,
          name: caseTypeLabelForPie(item.case_type),
          passed: item.passed,
          failed: item.failed,
          error: item.error,
          pass_rate: item.pass_rate,
        })),
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

function goToDashboardAlerts() {
  void router.push({ name: 'system-dashboard-alerts' })
}

function handleFailureClick(params: unknown) {
  const event = params as FailureChartClickParams
  if (event.componentType === 'series' && event.data?._caseId) {
    goToCaseManagement(event.data._projectId, event.data._moduleId)
  }
}

function chartRefFor(chart: ExportChartKey) {
  return {
    pass_rate_trend: passRateChartRef,
    duration_trend: durationChartRef,
    failure_top: failureTopChartRef,
    executor_top: executorTopChartRef,
    trigger_type: triggerTypeChartRef,
    plan_trend: planTrendChartRef,
    suite_trend: suiteTrendChartRef,
    case_type_distribution: caseTypeDistributionChartRef,
  }[chart]
}

function setChartRef(chart: ExportChartKey, el: Element | ComponentPublicInstance | null) {
  chartRefFor(chart).value = el as ChartRef | null
}

function handleChartClick(chart: LayoutChartKey, params: unknown) {
  if (chart === 'failure_top') {
    handleFailureClick(params)
  }
}

function downloadUrl(url: string, filename: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function chartFilename(chart: ExportChartKey, extension: string) {
  const scope = dashboardScope.value === 'project' ? `project-${projectId.value ?? 'unknown'}` : 'global'
  return `${chart}-${scope}-${days.value}d.${extension}`
}

function downloadChartPng(chart: ExportChartKey) {
  const instance = chartRefFor(chart).value
  const dataUrl = instance?.getDataURL?.({ pixelRatio: 2, backgroundColor: '#fff' })
    ?? instance?.chart?.getDataURL?.({ pixelRatio: 2, backgroundColor: '#fff' })
  if (!dataUrl) {
    message.warning(t('dashboard.export_chart_not_ready'))
    return
  }
  downloadUrl(dataUrl, chartFilename(chart, 'png'))
}

async function downloadChartCsv(chart: ExportChartKey) {
  try {
    const blob = await statisticsApi.exportCsv({
      chart,
      project_id: effectiveProjectId.value,
      days: days.value,
      case_type: caseType.value,
      aggregate: effectiveAggregate.value,
      top: 10,
    })
    const url = URL.createObjectURL(blob)
    downloadUrl(url, chartFilename(chart, 'csv'))
    URL.revokeObjectURL(url)
  } catch {
    message.error(t('dashboard.export_failed'))
  }
}

function handleChartExport(chart: ExportChartKey, key: string | number) {
  const action = String(key) as ExportAction
  if (action === 'png') {
    downloadChartPng(chart)
    return
  }
  void downloadChartCsv(chart)
}

function handleExportMenu(chart: ExportChartKey, info: MenuClickInfo) {
  handleChartExport(chart, info.key)
}

function moveLayoutItem(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= dashboardLayout.value.length) return
  const next = [...dashboardLayout.value]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  dashboardLayout.value = next
}

function resetDashboardLayout() {
  dashboardLayout.value = cloneDefaultLayout()
}

const overview = reactive(createEmptyOverview())
const passRateOption = ref(buildPassRateOption())
const durationOption = ref(buildDurationOption())
const failureTopOption = ref(buildFailureTopOption())
const executorTopOption = ref(buildExecutorTopOption())
const triggerTypeOption = ref(buildTriggerTypeOption())
const planTrendOption = ref(buildAggregateTrendOption([], t('dashboard.charts.plan')))
const suiteTrendOption = ref(buildAggregateTrendOption([], t('dashboard.charts.suite')))
const caseTypeDistributionOption = ref(buildCaseTypeDistributionOption())

const loadedCharts = ref(new Set<string>())

type ChartKey = 'passRate' | 'duration' | 'failure' | 'executor' | 'trigger' | 'plan' | 'suite' | 'caseTypeDist'

function resetOverview() {
  Object.assign(overview, createEmptyOverview())
}

function currentDashboardParams(): DashboardParams {
  return {
    project_id: effectiveProjectId.value,
    days: days.value,
    case_type: caseType.value,
  }
}

function currentTrendParams(): TrendParams {
  return { ...currentDashboardParams(), aggregate: effectiveAggregate.value }
}

function currentAggregateParams(): AggregateParams {
  return {
    project_id: effectiveProjectId.value,
    days: days.value,
    aggregate: effectiveAggregate.value,
  }
}

function onChartVisible(key: ChartKey, loader: () => Promise<void>) {
  loadedCharts.value.add(key)
  void loader()
}

const chartLoaders: Record<ChartKey, () => Promise<void>> = {
  passRate: () => loadPassRateTrend(),
  duration: () => loadDurationTrend(),
  failure: () => loadFailureTop(),
  executor: () => loadExecutorTop(),
  trigger: () => loadTriggerTypeStats(),
  plan: () => loadPlanTrend(),
  suite: () => loadSuiteTrend(),
  caseTypeDist: () => loadCaseTypeDistribution(),
}

function chartTitle(key: LayoutChartKey): string {
  return {
    pass_rate_trend: t('dashboard.charts.pass_rate_trend'),
    duration_trend: t('dashboard.charts.duration_trend'),
    failure_top: t('dashboard.charts.failure_top'),
    executor_top: t('dashboard.charts.executor_top'),
    trigger_type: t('dashboard.charts.trigger_type'),
    plan_trend: t('dashboard.charts.plan_trend'),
    suite_trend: t('dashboard.charts.suite_trend'),
    case_type_distribution: t('dashboard.charts.case_type_distribution'),
  }[key]
}

const chartDefinitions = computed(() => ({
  pass_rate_trend: {
    key: 'pass_rate_trend' as const,
    title: chartTitle('pass_rate_trend'),
    lazyKey: 'passRate' as const,
    loader: loadPassRateTrend,
    exportKey: 'pass_rate_trend' as const,
    option: passRateOption,
    span: 24,
  },
  duration_trend: {
    key: 'duration_trend' as const,
    title: chartTitle('duration_trend'),
    lazyKey: 'duration' as const,
    loader: loadDurationTrend,
    exportKey: 'duration_trend' as const,
    option: durationOption,
    span: 12,
  },
  failure_top: {
    key: 'failure_top' as const,
    title: chartTitle('failure_top'),
    lazyKey: 'failure' as const,
    loader: loadFailureTop,
    exportKey: 'failure_top' as const,
    option: failureTopOption,
    span: 12,
  },
  executor_top: {
    key: 'executor_top' as const,
    title: chartTitle('executor_top'),
    lazyKey: 'executor' as const,
    loader: loadExecutorTop,
    exportKey: 'executor_top' as const,
    option: executorTopOption,
    span: 12,
  },
  trigger_type: {
    key: 'trigger_type' as const,
    title: chartTitle('trigger_type'),
    lazyKey: 'trigger' as const,
    loader: loadTriggerTypeStats,
    exportKey: 'trigger_type' as const,
    option: triggerTypeOption,
    span: 12,
  },
  plan_trend: {
    key: 'plan_trend' as const,
    title: chartTitle('plan_trend'),
    lazyKey: 'plan' as const,
    loader: loadPlanTrend,
    exportKey: 'plan_trend' as const,
    option: planTrendOption,
    span: 12,
  },
  suite_trend: {
    key: 'suite_trend' as const,
    title: chartTitle('suite_trend'),
    lazyKey: 'suite' as const,
    loader: loadSuiteTrend,
    exportKey: 'suite_trend' as const,
    option: suiteTrendOption,
    span: 12,
  },
  case_type_distribution: {
    key: 'case_type_distribution' as const,
    title: chartTitle('case_type_distribution'),
    lazyKey: 'caseTypeDist' as const,
    loader: loadCaseTypeDistribution,
    exportKey: 'case_type_distribution' as const,
    option: caseTypeDistributionOption,
    span: 12,
  },
}))

const visibleChartConfigs = computed(() =>
  dashboardLayout.value
    .filter(item => item.visible)
    .map(item => chartDefinitions.value[item.key]),
)

async function loadProjects() {
  try {
    const list = await projectApi.list()
    projectOptions.value = list.map(project => ({ label: project.name, value: project.id }))
    if (dashboardScope.value === 'project' && !projectId.value && projectOptions.value.length) {
      projectId.value = projectOptions.value[0].value
    }
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
    const data = await statisticsApi.triggerTypeStats({ project_id: effectiveProjectId.value, days: days.value })
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

async function loadCaseTypeDistribution() {
  const params = currentDashboardParams()
  try {
    const data = await statisticsApi.caseTypeDistribution({ project_id: params.project_id, days: params.days })
    caseTypeDistributionOption.value = buildCaseTypeDistributionOption(data)
  } catch {
    caseTypeDistributionOption.value = buildCaseTypeDistributionOption()
  }
}

watch([dashboardScope, projectId, days, caseType], async () => {
  await loadFirstScreen()
  await loadDashboardAlerts()
  await refreshLoadedCharts()
})

watch(dashboardScope, (scope) => {
  try {
    localStorage.setItem(DASHBOARD_SCOPE_KEY, scope)
  } catch {
  }
  if (scope === 'project' && !projectId.value && projectOptions.value.length) {
    projectId.value = projectOptions.value[0].value
  }
})

watch(projectId, (id) => {
  try {
    if (id) localStorage.setItem(DASHBOARD_PROJECT_KEY, String(id))
    else localStorage.removeItem(DASHBOARD_PROJECT_KEY)
  } catch {
  }
})

watch(dashboardLayout, (layout) => {
  try {
    localStorage.setItem(DASHBOARD_LAYOUT_KEY, JSON.stringify(layout))
  } catch {
  }
}, { deep: true })

// 语言切换：重新拉取数据以让 echarts 配置中的 t() 文案刷新
watch(locale, async () => {
  await loadFirstScreen()
  await refreshLoadedCharts()
})

onMounted(() => {
  void loadProjects()
  void loadFirstScreen()
  void loadStorageAlert()
  void loadDashboardAlerts()
})

async function loadStorageAlert() {
  try {
    const resp = await storageApi.getAlert()
    storageAlert.value = resp?.alert ?? null
  } catch {
    storageAlert.value = null
  }
}

async function loadDashboardAlerts() {
  if (dashboardScope.value !== 'project' || !projectId.value) {
    dashboardAlertEvents.value = []
    return
  }
  try {
    dashboardAlertEvents.value = await dashboardAlertApi.listEvents({
      project_id: projectId.value,
      limit: 3,
    })
  } catch {
    dashboardAlertEvents.value = []
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

<style scoped>
.dashboard-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.scope-label {
  margin-top: 4px;
  color: #666;
  font-size: 13px;
}
.layout-row {
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.drag-handle {
  cursor: grab;
  color: #999;
  font-size: 16px;
}
</style>
