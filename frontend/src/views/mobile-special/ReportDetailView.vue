<template>
  <div style="display: flex; flex-direction: column; height: 100%; overflow: auto">
    <!-- Back button -->
    <div style="margin-bottom: 12px">
      <a-button type="link" @click="router.back()">
        < Left 返回报告中心
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <template v-if="run">
        <!-- Task Info Header -->
        <a-card style="margin-bottom: 16px" :body-style="{ padding: '16px 20px' }">
          <a-descriptions :column="{ xs: 1, sm: 2, md: 3 }" size="small">
            <a-descriptions-item label="任务名称">{{ taskInfo?.name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="任务类型">
              <a-tag :color="taskTypeColor(run.task_type)">{{ taskTypeLabel(run.task_type) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="statusColor(run.status)">{{ statusLabel(run.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="设备序列号">{{ run.device_serial || '-' }}</a-descriptions-item>
            <a-descriptions-item label="应用包名">{{ run.app_package || '-' }}</a-descriptions-item>
            <a-descriptions-item label="耗时">
              {{ run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="开始时间">
              {{ run.started_at ? formatDate(run.started_at) : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="结束时间">
              {{ run.finished_at ? formatDate(run.finished_at) : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="触发方式">
              {{ triggerLabel(run.trigger_type) }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- KPI Cards -->
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

        <!-- Metric Trend Chart -->
        <a-card style="margin-bottom: 16px" :body-style="{ padding: '16px' }">
          <template #title>
            <span style="font-size: 14px">指标趋势</span>
          </template>
          <div style="display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap">
            <a-select
              v-model:value="selectedMetricType"
              placeholder="选择指标"
              style="width: 160px"
              :options="metricTypeOptions"
              @change="loadSamples"
            />
          </div>
          <div ref="trendChartRef" style="width: 100%; height: 280px"></div>
        </a-card>

        <!-- Incidents Table -->
        <a-card style="margin-bottom: 16px" :body-style="{ padding: '0 16px 16px' }">
          <template #title>
            <span style="font-size: 14px">异常事件 ({{ incidents.length }})</span>
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
          <a-empty v-else description="暂无异常事件" style="padding: 24px 0" />
        </a-card>

        <!-- Artifacts -->
        <a-card :body-style="{ padding: '0 16px 16px' }">
          <template #title>
            <span style="font-size: 14px; margin-right: 8px">报告文件 ({{ artifacts.length }})</span>
            <a-button type="link" size="small" @click="doExportCsv">导出CSV</a-button>
            <a-button type="link" size="small" @click="doExportJson">导出JSON</a-button>
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
                <a-button type="link" size="small" @click="downloadArtifact(record)">下载</a-button>
              </template>
            </template>
          </a-table>
          <a-empty v-else description="暂无报告文件" style="padding: 24px 0" />
        </a-card>
      </template>

      <a-empty v-else description="报告不存在" style="padding: 48px 0" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import {
  mobileSpecialApi,
  type MobileSpecialRunItem,
  type MobileSpecialTaskItem,
  type MobileMetricSampleItem,
  type MobileIncidentItem,
  type MobileRunArtifactItem,
} from '@/api'

// Simple KPI Card component inline
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

const metricTypeOptions = [
  { label: '内存 (MB)', value: 'mem_mb' },
  { label: 'CPU (%)', value: 'cpu_pct' },
  { label: '电池 (%)', value: 'battery_pct' },
  { label: 'FPS', value: 'fps' },
]

const incidentColumns = [
  { title: '类型', key: 'incident_type', width: 100 },
  { title: '时间', key: 'event_time', width: 160 },
  { title: '标题/详情', key: 'title' },
]

const artifactColumns = [
  { title: '类型', key: 'artifact_type', width: 100 },
  { title: '文件名', key: 'file_name', dataIndex: 'file_name' },
  { title: '大小', key: 'file_size', width: 100 },
  { title: '时间', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 80 },
]

const kpiCards = computed(() => {
  if (!samples.value.length) return []
  const summary = run.value?.summary_json as Record<string, any> || {}

  const byType = (type: string) => {
    const vals = samples.value.filter(s => s.metric_type === type).map(s => s.metric_value)
    if (!vals.length) return null
    return { avg: vals.reduce((a, b) => a + b, 0) / vals.length, min: Math.min(...vals), max: Math.max(...vals) }
  }

  const mem = byType('mem_mb')
  const cpu = byType('cpu_pct')
  const fps = byType('fps')

  return [
    ...(mem ? [{ label: '内存平均 (MB)', value: mem.avg.toFixed(1), unit: 'MB', color: '#1890ff' }] : []),
    ...(cpu ? [{ label: 'CPU平均 (%)', value: cpu.avg.toFixed(1), unit: '%', color: '#faad14' }] : []),
    ...(fps ? [{ label: '平均 FPS', value: fps.avg.toFixed(1), unit: '', color: '#52c41a' }] : []),
    ...(fps ? [{ label: 'Jank 次数', value: summary.jank_count || 0, unit: '次', color: '#ff4d4f' }] : []),
    ...(incidents.value.length ? [{ label: '异常事件', value: incidents.value.length, unit: '个', color: '#ff4d4f' }] : []),
    ...(run.value?.duration_ms ? [{ label: '总耗时', value: (run.value.duration_ms / 1000).toFixed(1), unit: 's', color: '#722ed1' }] : []),
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
  } catch (e: any) {
    message.error(e?.message || '加载报告详情失败')
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
  } catch (e: any) {
    message.error(e?.message || '加载指标数据失败')
  }
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
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
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>${p.seriesName}: ${p.value} ${unitMap[selectedMetricType.value] || ''}`
      },
    },
    grid: { top: 10, right: 20, bottom: 30, left: 50 },
    xAxis: { type: 'category', data: times, axisLabel: { fontSize: 10, rotate: 30 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 11, formatter: (v: number) => `${v}${unitMap[selectedMetricType.value] || ''}` } },
    series: [{ name: metricTypeOptions.find(o => o.value === selectedMetricType.value)?.label || '', type: 'line', data: values, smooth: true, itemStyle: { color: colorMap[selectedMetricType.value] || '#1890ff' } }],
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

function triggerLabel(type: string) {
  return { manual: '手动', schedule: '调度', webhook: 'Webhook' }[type] || type
}

function incidentColor(type: string) {
  return { crash: 'red', anr: 'orange', fatal_log: 'purple', watchdog: 'magenta' }[type] || 'default'
}

function incidentLabel(type: string) {
  return { crash: '崩溃', anr: 'ANR', fatal_log: 'Fatal日志', watchdog: 'Watchdog' }[type] || type
}

function artifactLabel(type: string) {
  return { csv: 'CSV', json: 'JSON', screenshot: '截图', raw_log: '日志', trace: 'Trace' }[type] || type
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
    message.info(`文件: ${record.file_name}，下载功能待后端提供`)
  } catch (e: any) {
    message.error(e?.message || '下载失败')
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
    message.success('CSV 已下载')
  } catch (e: any) {
    message.error(e?.message || '导出失败')
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
    message.success('JSON 已下载')
  } catch (e: any) {
    message.error(e?.message || '导出失败')
  }
}
</script>
