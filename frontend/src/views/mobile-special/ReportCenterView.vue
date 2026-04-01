<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <!-- Header -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
      <h2 style="margin: 0">专项测试报告</h2>
      <a-select
        v-model:value="selectedProjectId"
        placeholder="选择项目"
        style="width: 200px"
        :options="projectOptions"
        allow-clear
        @change="onProjectChange"
      />
      <a-select
        v-model:value="selectedTaskType"
        placeholder="任务类型"
        style="width: 140px"
        :options="taskTypeOptions"
        allow-clear
        @change="loadRuns"
      />
      <a-select
        v-model:value="selectedStatus"
        placeholder="执行状态"
        style="width: 120px"
        :options="statusOptions"
        allow-clear
        @change="loadRuns"
      />
      <a-range-picker
        v-model:value="dateRange"
        :placeholder="['开始日期', '结束日期']"
        style="width: 260px"
        @change="loadRuns"
      />
    </div>

    <!-- Overview KPI Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px">
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">总执行次数</div>
        <div style="font-size: 24px; font-weight: 600; color: #1890ff">{{ overview.total_runs }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">完成率</div>
        <div style="font-size: 24px; font-weight: 600; color: #52c41a">{{ overview.pass_rate }}%</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">近7天执行</div>
        <div style="font-size: 24px; font-weight: 600; color: #722ed1">{{ overview.recent_runs_7d }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">失败次数</div>
        <div style="font-size: 24px; font-weight: 600; color: #ff4d4f">{{ overview.failed_runs }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">异常事件</div>
        <div style="font-size: 24px; font-weight: 600; color: #faad14">{{ overview.total_incidents }}</div>
      </a-card>
      <a-card size="small" :body-style="{ padding: '12px 16px' }">
        <div style="color: #999; font-size: 12px; margin-bottom: 4px">平均耗时</div>
        <div style="font-size: 24px; font-weight: 600; color: #13c2c2">
          {{ overview.avg_duration_ms ? (overview.avg_duration_ms / 1000).toFixed(1) + 's' : '-' }}
        </div>
      </a-card>
    </div>

    <!-- Trend Chart -->
    <a-card style="margin-bottom: 16px" :body-style="{ padding: '12px 16px' }">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
        <span style="font-size: 14px; font-weight: 500">执行趋势（近14天）</span>
        <span style="font-size: 12px; color: #999">
          完成 {{ trendCompleted }} / 失败 {{ trendFailed }}
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
            <a-button type="primary" size="small" @click="viewDetail(record)">详情</a-button>
            <a-dropdown>
              <a-button type="link" size="small">导出</a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="csv" @click="exportCsv(record)">CSV 指标</a-menu-item>
                  <a-menu-item key="json" @click="exportJson(record)">JSON 报告</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
            <a-button
              v-if="record.status === 'running' || record.status === 'pending'"
              type="link"
              size="small"
              danger
              @click="handleStop(record)"
            >停止</a-button>
          </template>
        </template>
      </a-table>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { projectApi, mobileSpecialApi, type MobileSpecialRunItem, type TaskType, type MobileRunStatus } from '@/api'

const router = useRouter()
const loading = ref(false)
const runs = ref<MobileSpecialRunItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const selectedProjectId = ref<number | null>(null)
const selectedTaskType = ref<TaskType | null>(null)
const selectedStatus = ref<MobileRunStatus | null>(null)
const dateRange = ref<[string, string] | null>(null)

const overview = ref({
  total_runs: 0, completed_runs: 0, failed_runs: 0, running_runs: 0,
  pass_rate: 0, avg_duration_ms: null as number | null, total_incidents: 0, recent_runs_7d: 0,
})
const trendCompleted = ref(0)
const trendFailed = ref(0)

const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: ECharts | null = null

const taskTypeOptions = [
  { label: '性能测试', value: 'performance' },
  { label: '稳定性测试', value: 'stability' },
  { label: '流畅度测试', value: 'fluency' },
]

const statusOptions = [
  { label: '已完成', value: 'completed' },
  { label: '进行中', value: 'running' },
  { label: '失败', value: 'failed' },
  { label: '已停止', value: 'stopped' },
]

const columns = [
  { title: '任务名称', key: 'task_name', dataIndex: 'task_name', width: 180, ellipsis: true },
  { title: '类型', key: 'task_type', dataIndex: 'task_type', width: 100 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 90 },
  { title: '设备', key: 'device_serial', dataIndex: 'device_serial', width: 140, ellipsis: true },
  { title: '包名', key: 'app_package', dataIndex: 'app_package', width: 160, ellipsis: true },
  { title: '耗时', key: 'duration', width: 90 },
  { title: '开始时间', key: 'started_at', width: 160 },
  { title: '操作', key: 'action', width: 200 },
]

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projectOptions.value = list.map((p: any) => ({ label: p.name, value: p.id }))
    if (list.length > 0) {
      selectedProjectId.value = list[0].id
    }
  } catch (e: any) {
    message.error(e?.message || '加载项目失败')
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
    const params: any = {}
    if (selectedProjectId.value) params.project_id = selectedProjectId.value
    if (selectedTaskType.value) params.task_type = selectedTaskType.value
    if (selectedStatus.value) params.status_filter = selectedStatus.value
    params.limit = 100

    const data = await mobileSpecialApi.listRuns(params)
    let filtered = data as MobileSpecialRunItem[]

    if (dateRange.value && dateRange.value.length === 2) {
      const [start, end] = dateRange.value
      filtered = filtered.filter(r => {
        if (!r.started_at) return false
        const t = new Date(r.started_at).getTime()
        return t >= new Date(start).getTime() && t <= new Date(end).getTime() + 86400000
      })
    }

    const taskMap = new Map<number, string>()
    const uniqueTaskIds = [...new Set(filtered.map(r => r.task_id))]
    await Promise.all(
      uniqueTaskIds.map(async id => {
        try {
          const task = await mobileSpecialApi.getTask(id)
          taskMap.set(id, task.name)
        } catch {
          taskMap.set(id, `任务 #${id}`)
        }
      })
    )
    runs.value = filtered.map(r => ({ ...r, task_name: taskMap.get(r.task_id) || `任务 #${r.task_id}` }))

    // Load trend data
    await loadTrend()
  } catch (e: any) {
    message.error(e?.message || '加载报告失败')
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
    trendCompleted.value = trend.reduce((sum, d) => sum + d.completed, 0)
    trendFailed.value = trend.reduce((sum, d) => sum + d.failed, 0)
    updateTrendChart(trend)
  } catch { /* ignore */ }
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
}

function updateTrendChart(trend: Array<{ date: string; total: number; completed: number; failed: number; pass_rate: number }>) {
  if (!trendChart) return

  const dates = trend.map(d => d.date.slice(5))
  const completedData = trend.map(d => d.completed)
  const failedData = trend.map(d => d.failed)

  const option: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['完成', '失败'], bottom: 0 },
    grid: { top: 10, right: 20, bottom: 36, left: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
    series: [
      { name: '完成', type: 'bar', data: completedData, itemStyle: { color: '#52c41a' } },
      { name: '失败', type: 'bar', data: failedData, itemStyle: { color: '#ff4d4f' } },
    ],
  }

  trendChart.setOption(option, true)
}

function taskTypeColor(type: string) {
  return { performance: 'blue', stability: 'orange', fluency: 'purple' }[type] || 'default'
}

function taskTypeLabel(type: string) {
  return { performance: '性能', stability: '稳定性', fluency: '流畅度' }[type] || type
}

function statusColor(status: string) {
  return { pending: 'default', running: 'processing', completed: 'success', failed: 'error', stopped: 'warning' }[status] || 'default'
}

function statusLabel(status: string) {
  return { pending: '等待', running: '运行中', completed: '完成', failed: '失败', stopped: '已停止' }[status] || status
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
    message.success('CSV 已下载')
  } catch (e: any) {
    message.error(e?.message || '导出失败')
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
    message.success('JSON 已下载')
  } catch (e: any) {
    message.error(e?.message || '导出失败')
  }
}

async function handleStop(record: MobileSpecialRunItem) {
  try {
    await mobileSpecialApi.stopRun(record.id)
    message.success('任务已停止')
    await loadRuns()
    await loadOverview()
  } catch (e: any) {
    message.error(e?.message || '停止任务失败')
  }
}
</script>
