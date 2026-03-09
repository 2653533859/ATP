<template>
  <div>
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
        <a-select v-model:value="days" style="width: 120px" :options="dayOptions" />
      </a-space>
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

    <!-- 空状态引导 -->
    <template v-if="!loading && overview.total_runs === 0">
      <a-card>
        <a-empty description="还没有执行记录，去创建用例并执行吧">
          <a-button type="primary" @click="goToCaseManagement(projectId)">前往用例管理</a-button>
        </a-empty>
      </a-card>
    </template>

    <!-- 图表区域 -->
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
      </a-spin>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
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
import { projectApi, statisticsApi } from '@/api'

use([CanvasRenderer, LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const router = useRouter()

type DashboardParams = {
  project_id?: number
  days: number
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

const projectId = ref<number | undefined>(undefined)
const days = ref(30)
const loading = ref(false)
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const dayOptions = [
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
]

function createEmptyOverview(): OverviewData {
  return { total_cases: 0, total_runs: 0, pass_rate: 0, recent_runs_7d: 0 }
}

/**
 * 生成从 startDate 到 endDate 的完整日期序列
 */
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

/**
 * 将稀疏的趋势数据补零为完整日期序列
 */
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

function handleFailureClick(params: any) {
  // 点击柱状图跳转到已注册的用例管理页
  if (params.componentType === 'series' && params.data?._caseId) {
    goToCaseManagement(params.data._projectId, params.data._moduleId)
  }
}

const overview = reactive(createEmptyOverview())
const passRateOption = ref(buildPassRateOption())
const durationOption = ref(buildDurationOption())
const failureTopOption = ref(buildFailureTopOption())

function resetOverview() {
  Object.assign(overview, createEmptyOverview())
}

async function loadProjects() {
  try {
    const list = await projectApi.list()
    projectOptions.value = list.map((project: any) => ({ label: project.name, value: project.id }))
  } catch {
  }
}

async function loadAll() {
  loading.value = true
  const params: DashboardParams = { project_id: projectId.value, days: days.value }

  try {
    await Promise.all([
      loadOverview(params),
      loadPassRateTrend(params),
      loadDurationTrend(params),
      loadFailureTop(params),
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
    const data = await statisticsApi.failureTop(params)
    failureTopOption.value = buildFailureTopOption(data)
  } catch {
    failureTopOption.value = buildFailureTopOption()
  }
}

watch([projectId, days], () => {
  void loadAll()
})

onMounted(() => {
  void loadProjects()
  void loadAll()
})
</script>
