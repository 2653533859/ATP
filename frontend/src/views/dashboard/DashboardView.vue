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

    <section class="workbench-panel">
      <div class="workbench-header">
        <div>
          <div class="section-title">{{ t('dashboard.workbench.title') }}</div>
          <div class="section-subtitle">{{ t('dashboard.workbench.subtitle') }}</div>
        </div>
        <a-space wrap>
          <a-button size="small" @click="goToCaseManagement(effectiveProjectId)">
            {{ t('dashboard.workbench.open_cases') }}
          </a-button>
          <a-button size="small" @click="goToRuns">
            {{ t('dashboard.workbench.open_runs') }}
          </a-button>
        </a-space>
      </div>

      <a-row :gutter="[12, 12]">
        <a-col :xs="12" :md="6">
          <button class="workbench-card" type="button" @click="goToRuns">
            <span class="workbench-card-icon workbench-card-icon-primary"><ClockCircleOutlined /></span>
            <span class="workbench-card-body">
              <span class="workbench-card-value">{{ workbench.todayRuns }}</span>
              <span class="workbench-card-label">{{ t('dashboard.workbench.today_runs') }}</span>
            </span>
          </button>
        </a-col>
        <a-col :xs="12" :md="6">
          <button class="workbench-card" type="button" @click="focusFailureChart">
            <span class="workbench-card-icon" :class="workbench.todayFailed > 0 ? 'workbench-card-icon-error' : 'workbench-card-icon-success'">
              <ExclamationCircleOutlined />
            </span>
            <span class="workbench-card-body">
              <span class="workbench-card-value">{{ workbench.todayFailed }}</span>
              <span class="workbench-card-label">{{ t('dashboard.workbench.today_failed') }}</span>
            </span>
          </button>
        </a-col>
        <a-col :xs="12" :md="6">
          <button class="workbench-card" type="button" @click="goToPendingReviews">
            <span class="workbench-card-icon workbench-card-icon-warning"><FileSearchOutlined /></span>
            <span class="workbench-card-body">
              <span class="workbench-card-value">{{ workbench.pendingReviews }}</span>
              <span class="workbench-card-label">{{ t('dashboard.workbench.pending_reviews') }}</span>
            </span>
          </button>
        </a-col>
        <a-col :xs="12" :md="6">
          <button class="workbench-card" type="button" @click="goToDashboardAlerts">
            <span class="workbench-card-icon" :class="workbench.alertCount > 0 ? 'workbench-card-icon-error' : 'workbench-card-icon-muted'">
              <AlertOutlined />
            </span>
            <span class="workbench-card-body">
              <span class="workbench-card-value">{{ workbench.alertCount }}</span>
              <span class="workbench-card-label">{{ t('dashboard.workbench.active_alerts') }}</span>
            </span>
          </button>
        </a-col>
      </a-row>

      <div class="recent-runs">
        <div class="recent-runs-header">
          <div class="section-title">{{ t('dashboard.workbench.recent_runs') }}</div>
          <a-button type="link" size="small" @click="goToRuns">{{ t('common.view_all') }}</a-button>
        </div>
        <a-skeleton v-if="workbenchLoading" active :paragraph="{ rows: 2 }" />
        <a-empty v-else-if="recentRuns.length === 0" :description="t('dashboard.workbench.no_recent_runs')" />
        <div v-else class="recent-run-list">
          <button
            v-for="run in recentRuns"
            :key="run.id"
            class="recent-run-item"
            type="button"
            @click="goToRunDetail(run.id)"
          >
            <span class="recent-run-main">
              <span class="recent-run-title">{{ run.case_name || run.case?.name || `#${run.case_id}` }}</span>
              <span class="recent-run-meta">{{ formatRunTime(run.created_at) }} · {{ formatDuration(run.duration_ms) }}</span>
            </span>
            <a-tag :color="runStatusColor(run.status)">{{ runStatusLabel(run.status) }}</a-tag>
          </button>
        </div>
      </div>
    </section>

    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :xs="12" :sm="12" :md="6">
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon-primary"><ProfileOutlined /></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ overview.total_cases }}</div>
            <div class="kpi-label">{{ t('dashboard.total_cases') }}</div>
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon-info"><PlayCircleOutlined /></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ overview.total_runs }}</div>
            <div class="kpi-label">{{ t('dashboard.total_runs') }}</div>
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <div class="kpi-card">
          <div class="kpi-icon" :class="overview.pass_rate >= 80 ? 'kpi-icon-success' : 'kpi-icon-error'"><CheckCircleOutlined /></div>
          <div class="kpi-body">
            <div class="kpi-value" :style="{ color: overview.pass_rate >= 80 ? 'var(--c-success)' : 'var(--c-error)' }">
              {{ overview.pass_rate.toFixed(1) }}<span style="font-size: 15px; font-weight: 600; margin-left: 2px">%</span>
            </div>
            <div class="kpi-label">{{ t('dashboard.pass_rate') }}</div>
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :sm="12" :md="6">
        <div class="kpi-card">
          <div class="kpi-icon kpi-icon-warning"><ThunderboltOutlined /></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ overview.recent_runs_7d }}</div>
            <div class="kpi-label">{{ t('dashboard.recent_runs_7d') }}</div>
          </div>
        </div>
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
            :data-dashboard-chart="chart.dataAttr"
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
                :theme="chartTheme"
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
import { DownloadOutlined, SettingOutlined, ProfileOutlined, PlayCircleOutlined, CheckCircleOutlined, ThunderboltOutlined, ClockCircleOutlined, ExclamationCircleOutlined, FileSearchOutlined, AlertOutlined } from '@ant-design/icons-vue'
import LazyChartCard from '@/components/dashboard/LazyChartCard.vue'
import { useChartTheme } from '@/utils/chartTheme'
import { caseApi, dashboardAlertApi, projectApi, runApi, statisticsApi, storageApi, userSettingsApi, type DashboardAlertEventItem, type RunDetailItem, type StatisticsAggregateTrendItem, type StatisticsCaseTypeDistributionItem, type StatisticsExecutorTopItem, type StatisticsTriggerTypeStatItem, type StorageAlertPayload } from '@/api'
import {
  cloneDefaultDashboardLayout,
  fillTrendGaps,
  normalizeDashboardLayout,
  type DashboardLayoutItem,
} from '@/utils/dashboardView'

const router = useRouter()
const { t, locale } = useI18n()
const { chartTheme } = useChartTheme()

type DashboardCaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android' | 'ios'
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

type WorkbenchData = {
  todayRuns: number
  todayFailed: number
  pendingReviews: number
  alertCount: number
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
const DASHBOARD_LAYOUT_SETTING_KEY = 'dashboard.layout'

type LayoutItem = DashboardLayoutItem

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
  return cloneDefaultDashboardLayout()
}

function loadDashboardLayoutFromLocal(): LayoutItem[] {
  try {
    const raw = localStorage.getItem(DASHBOARD_LAYOUT_KEY)
    if (!raw) return cloneDefaultLayout()
    return normalizeDashboardLayout(JSON.parse(raw))
  } catch {
    return cloneDefaultLayout()
  }
}

function saveDashboardLayoutLocal(layout: LayoutItem[]) {
  try {
    localStorage.setItem(DASHBOARD_LAYOUT_KEY, JSON.stringify(layout))
  } catch {
  }
}

const dashboardScope = ref<DashboardScope>(initialScope())
const projectId = ref<number | undefined>(initialProjectId())
const settingsOpen = ref(false)
const dashboardLayout = ref<LayoutItem[]>(loadDashboardLayoutFromLocal())
const days = ref(30)
const caseType = ref<DashboardCaseType | undefined>(undefined)
const loading = ref(false)
const workbenchLoading = ref(false)
const storageAlert = ref<StorageAlertPayload | null>(null)
const dashboardAlertEvents = ref<DashboardAlertEventItem[]>([])
const recentRuns = ref<RunDetailItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const passRateChartRef = ref<ChartRef | null>(null)
const durationChartRef = ref<ChartRef | null>(null)
const failureTopChartRef = ref<ChartRef | null>(null)
const executorTopChartRef = ref<ChartRef | null>(null)
const triggerTypeChartRef = ref<ChartRef | null>(null)
const planTrendChartRef = ref<ChartRef | null>(null)
const suiteTrendChartRef = ref<ChartRef | null>(null)
const caseTypeDistributionChartRef = ref<ChartRef | null>(null)
const applyingRemoteLayout = ref(false)
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
  { label: t('dashboard.case_types.ios'), value: 'ios' },
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

function resetWorkbench() {
  workbench.todayRuns = 0
  workbench.todayFailed = 0
  workbench.pendingReviews = 0
  workbench.alertCount = dashboardAlertEvents.value.length
}

function fillPassRateGaps(data: PassRateTrendItem[], numDays: number): PassRateTrendItem[] {
  return fillTrendGaps(
    data,
    numDays,
    (date) => ({ date, total: 0, passed: 0, rate: 0 }),
    { weekly: effectiveAggregate.value === 'weekly' },
  )
}

function fillDurationGaps(data: DurationTrendItem[], numDays: number): DurationTrendItem[] {
  return fillTrendGaps(
    data,
    numDays,
    (date) => ({ date, avg_duration_ms: 0, max_duration_ms: 0, run_count: 0 }),
    { weekly: effectiveAggregate.value === 'weekly' },
  )
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

function goToRuns() {
  void router.push({ name: 'runs' })
}

function goToRunDetail(runId: number) {
  void router.push({ name: 'run-detail', params: { runId: String(runId) } })
}

function goToPendingReviews() {
  void router.push({
    name: 'cases',
    query: {
      review_status: 'pending',
      ...(effectiveProjectId.value ? { project_id: String(effectiveProjectId.value) } : {}),
    },
  })
}

function focusFailureChart() {
  const el = document.querySelector('[data-dashboard-chart="failure_top"]')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  void loadFailureTop()
}

function runStatusColor(status: string) {
  return { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
}

function runStatusLabel(status: string) {
  const key = `dashboard.run_statuses.${status}`
  const translated = t(key)
  return translated === key ? status : translated
}

function formatRunTime(value?: string | null) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function formatDuration(value?: number | null) {
  if (!value) return '-'
  if (value < 1000) return `${value}ms`
  return `${(value / 1000).toFixed(1)}s`
}

function isToday(value: string) {
  const today = new Date().toISOString().slice(0, 10)
  return value === today
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

function extractRemoteDashboardLayout(value: Record<string, unknown>): LayoutItem[] | null {
  const rawItems = value.items ?? value.layout
  if (!Array.isArray(rawItems)) return null
  return normalizeDashboardLayout(rawItems)
}

async function loadDashboardLayoutSetting() {
  try {
    const setting = await userSettingsApi.get(DASHBOARD_LAYOUT_SETTING_KEY)
    const remoteLayout = extractRemoteDashboardLayout(setting.value)
    if (!remoteLayout) return
    applyingRemoteLayout.value = true
    dashboardLayout.value = remoteLayout
    saveDashboardLayoutLocal(remoteLayout)
  } catch {
    // 未配置或未登录时继续使用 localStorage 降级。
  } finally {
    applyingRemoteLayout.value = false
  }
}

async function saveDashboardLayoutSetting(layout: LayoutItem[]) {
  try {
    await userSettingsApi.update(DASHBOARD_LAYOUT_SETTING_KEY, {
      items: layout,
      version: 1,
    })
  } catch {
    // 服务端偏好写入失败不阻断看板本地设置。
  }
}

const overview = reactive(createEmptyOverview())
const workbench = reactive<WorkbenchData>({
  todayRuns: 0,
  todayFailed: 0,
  pendingReviews: 0,
  alertCount: 0,
})
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
    dataAttr: 'pass_rate_trend',
    lazyKey: 'passRate' as const,
    loader: loadPassRateTrend,
    exportKey: 'pass_rate_trend' as const,
    option: passRateOption,
    span: 24,
  },
  duration_trend: {
    key: 'duration_trend' as const,
    title: chartTitle('duration_trend'),
    dataAttr: 'duration_trend',
    lazyKey: 'duration' as const,
    loader: loadDurationTrend,
    exportKey: 'duration_trend' as const,
    option: durationOption,
    span: 12,
  },
  failure_top: {
    key: 'failure_top' as const,
    title: chartTitle('failure_top'),
    dataAttr: 'failure_top',
    lazyKey: 'failure' as const,
    loader: loadFailureTop,
    exportKey: 'failure_top' as const,
    option: failureTopOption,
    span: 12,
  },
  executor_top: {
    key: 'executor_top' as const,
    title: chartTitle('executor_top'),
    dataAttr: 'executor_top',
    lazyKey: 'executor' as const,
    loader: loadExecutorTop,
    exportKey: 'executor_top' as const,
    option: executorTopOption,
    span: 12,
  },
  trigger_type: {
    key: 'trigger_type' as const,
    title: chartTitle('trigger_type'),
    dataAttr: 'trigger_type',
    lazyKey: 'trigger' as const,
    loader: loadTriggerTypeStats,
    exportKey: 'trigger_type' as const,
    option: triggerTypeOption,
    span: 12,
  },
  plan_trend: {
    key: 'plan_trend' as const,
    title: chartTitle('plan_trend'),
    dataAttr: 'plan_trend',
    lazyKey: 'plan' as const,
    loader: loadPlanTrend,
    exportKey: 'plan_trend' as const,
    option: planTrendOption,
    span: 12,
  },
  suite_trend: {
    key: 'suite_trend' as const,
    title: chartTitle('suite_trend'),
    dataAttr: 'suite_trend',
    lazyKey: 'suite' as const,
    loader: loadSuiteTrend,
    exportKey: 'suite_trend' as const,
    option: suiteTrendOption,
    span: 12,
  },
  case_type_distribution: {
    key: 'case_type_distribution' as const,
    title: chartTitle('case_type_distribution'),
    dataAttr: 'case_type_distribution',
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

async function loadWorkbench() {
  workbenchLoading.value = true
  try {
    const params = currentTrendParams()
    const [trend, pendingCases, runs] = await Promise.all([
      statisticsApi.passRateTrend({ ...params, days: Math.min(params.days, 7), aggregate: 'daily' }),
      caseApi.list({
        project_id: effectiveProjectId.value,
        review_status: 'pending',
      }),
      runApi.list({ page: 1, page_size: 5 }),
    ])
    const today = trend.find(item => isToday(item.date))
    workbench.todayRuns = today?.total ?? 0
    workbench.todayFailed = today ? Math.max(today.total - today.passed, 0) : 0
    workbench.pendingReviews = pendingCases.length
    workbench.alertCount = dashboardAlertEvents.value.length
    recentRuns.value = runs.items
  } catch {
    recentRuns.value = []
    resetWorkbench()
  } finally {
    workbenchLoading.value = false
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
  await loadWorkbench()
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
  saveDashboardLayoutLocal(layout)
  if (!applyingRemoteLayout.value) {
    void saveDashboardLayoutSetting(layout)
  }
}, { deep: true })

// 语言切换：重新拉取数据以让 echarts 配置中的 t() 文案刷新
watch(locale, async () => {
  await loadFirstScreen()
  await refreshLoadedCharts()
})

onMounted(() => {
  void loadDashboardLayoutSetting()
  void loadProjects()
  void loadFirstScreen()
  void loadStorageAlert()
  void loadDashboardAlerts().then(() => loadWorkbench())
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
    workbench.alertCount = 0
    return
  }
  try {
    dashboardAlertEvents.value = await dashboardAlertApi.listEvents({
      project_id: projectId.value,
      limit: 3,
    })
    workbench.alertCount = dashboardAlertEvents.value.length
  } catch {
    dashboardAlertEvents.value = []
    workbench.alertCount = 0
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
.workbench-panel {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-elevated);
}
.workbench-header,
.recent-runs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text);
}
.section-subtitle {
  margin-top: 2px;
  color: var(--c-text-secondary);
  font-size: 12px;
}
.workbench-card {
  width: 100%;
  min-height: 86px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.workbench-card:hover {
  border-color: var(--c-primary);
}
.workbench-card-icon {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 20px;
}
.workbench-card-icon-primary {
  color: var(--c-primary);
  background: rgba(22, 119, 255, 0.1);
}
.workbench-card-icon-success {
  color: var(--c-success);
  background: rgba(82, 196, 26, 0.12);
}
.workbench-card-icon-warning {
  color: var(--c-warning);
  background: rgba(250, 173, 20, 0.14);
}
.workbench-card-icon-error {
  color: var(--c-error);
  background: rgba(255, 77, 79, 0.12);
}
.workbench-card-icon-muted {
  color: var(--c-text-secondary);
  background: rgba(0, 0, 0, 0.04);
}
.workbench-card-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.workbench-card-value {
  font-size: 24px;
  font-weight: 650;
  line-height: 1.1;
}
.workbench-card-label {
  margin-top: 6px;
  color: var(--c-text-secondary);
  font-size: 12px;
}
.recent-runs {
  margin-top: 16px;
}
.recent-run-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}
.recent-run-item {
  min-width: 0;
  min-height: 74px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
  cursor: pointer;
  text-align: left;
}
.recent-run-item:hover {
  border-color: var(--c-primary);
}
.recent-run-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.recent-run-title {
  overflow: hidden;
  color: var(--c-text);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent-run-meta {
  color: var(--c-text-secondary);
  font-size: 12px;
}
@media (max-width: 1200px) {
  .recent-run-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .workbench-header,
  .recent-runs-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .recent-run-list {
    grid-template-columns: 1fr;
  }
}
</style>
