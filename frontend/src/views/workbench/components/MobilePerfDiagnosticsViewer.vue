<template>
  <div class="mobile-perf-diagnostics-viewer">
    <!-- 头部工具栏 -->
    <header class="viewer-header">
      <div class="header-left">
        <div class="header-icon-box">
          <DashboardOutlined class="header-icon" />
        </div>
        <div>
          <div class="header-title-row">
            <h3 class="header-title">移动端原生性能剖析与深度质量诊断控制台</h3>
            <a-tag :color="currentSession ? (currentSession.ended_at ? 'default' : 'success') : 'default'">
              <span class="live-dot" :class="{ 'live-dot-active': currentSession && !currentSession.ended_at }" />
              {{ sessionStatusText }}
            </a-tag>
          </div>
          <p class="header-desc">
            实时多维采样移动端 CPU、物理内存 (PSS/Native/Dalvik)、渲染帧率 (FPS/Jank) 与网络流量，结合线性回归算法智能诊断内存泄漏与掉帧卡顿。
          </p>
        </div>
      </div>

      <div class="header-right">
        <a-space>
          <a-select
            v-model:value="selectedSessionId"
            style="width: 240px"
            size="small"
            placeholder="选择历史诊断会话"
            :options="sessionOptions"
            @change="handleSessionChange"
          />
          <a-button size="small" :loading="loading" @click="refreshData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" type="primary" ghost @click="showStartModal = true">
            <PlayCircleOutlined /> 启动采集
          </a-button>
          <a-button
            v-if="currentSession && !currentSession.ended_at"
            size="small"
            type="dashed"
            @click="showAppendModal = true"
          >
            <PlusOutlined /> 注入采样
          </a-button>
          <a-button
            v-if="currentSession && !currentSession.ended_at"
            size="small"
            danger
            :loading="stopping"
            @click="handleStopSession"
          >
            <StopOutlined /> 结束并诊断
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <!-- 性能体检诊断结论横幅 -->
      <div v-if="currentSession" class="diagnostic-banner" :class="bannerClass">
        <div class="banner-icon-box">
          <AlertOutlined v-if="hasCriticalAnomaly" class="banner-icon text-critical" />
          <WarningOutlined v-else-if="hasWarningAnomaly" class="banner-icon text-warning" />
          <CheckCircleOutlined v-else class="banner-icon text-success" />
        </div>
        <div class="banner-content">
          <div class="banner-title">{{ diagnosticVerdictTitle }}</div>
          <div class="banner-desc">{{ diagnosticVerdictDesc }}</div>
        </div>
        <div class="banner-meta">
          <span class="meta-item">会话: <code>{{ currentSession.session_id }}</code></span>
          <span class="meta-item">设备: <code>{{ currentSession.device_serial }}</code></span>
          <span class="meta-item">包名: <code>{{ currentSession.package_name }}</code></span>
          <span class="meta-item">采样点: <strong>{{ currentSession.total_samples_count }}</strong> 个</span>
        </div>
      </div>

      <!-- 核心指标 KPI 概览卡片 -->
      <div v-if="currentSession" class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">App 平均 CPU / 峰值</div>
          <div class="kpi-value-row">
            <span class="kpi-number">{{ currentSession.summary?.cpu_app_avg ?? 0 }}%</span>
            <span class="kpi-sub-num">/ {{ currentSession.summary?.cpu_app_max ?? 0 }}%</span>
          </div>
          <div class="kpi-sub">
            <span :class="(currentSession.summary?.cpu_app_avg || 0) > 75 ? 'text-warning' : 'text-success'">
              {{ (currentSession.summary?.cpu_app_avg || 0) > 75 ? '超过 75% 警戒水位' : '计算负载处于健康区间' }}
            </span>
          </div>
        </div>

        <div class="kpi-card" :class="{ 'card-alert': currentSession.summary?.has_memory_leak }">
          <div class="kpi-label">物理内存峰值 (PSS)</div>
          <div class="kpi-value-row">
            <span class="kpi-number">{{ currentSession.summary?.memory_pss_max ?? 0 }}</span>
            <span class="kpi-unit">MB</span>
          </div>
          <div class="kpi-sub">
            <span>持续增长斜率: </span>
            <strong :class="(currentSession.summary?.memory_growth_slope_mb_per_min || 0) > 5.0 ? 'text-critical' : 'text-success'">
              {{ currentSession.summary?.memory_growth_slope_mb_per_min ?? 0 }} MB/min
            </strong>
          </div>
        </div>

        <div class="kpi-card" :class="{ 'card-warning': currentSession.summary?.has_jank_drops }">
          <div class="kpi-label">平均渲染帧率 (FPS)</div>
          <div class="kpi-value-row">
            <span class="kpi-number" :class="(currentSession.summary?.fps_avg || 60) < 40 ? 'text-critical' : 'text-success'">
              {{ currentSession.summary?.fps_avg ?? 0 }}
            </span>
            <span class="kpi-unit">FPS</span>
          </div>
          <div class="kpi-sub">
            <span>累计卡顿掉帧: </span>
            <strong :class="(currentSession.summary?.total_janks || 0) > 10 ? 'text-warning' : 'text-success'">
              {{ currentSession.summary?.total_janks ?? 0 }} 次
            </strong>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">检出性能异常项</div>
          <div class="kpi-value-row">
            <span class="kpi-number" :class="(currentSession.summary?.anomalies_count || 0) > 0 ? 'text-critical' : 'text-success'">
              {{ currentSession.summary?.anomalies_count ?? 0 }}
            </span>
            <span class="kpi-unit">项</span>
          </div>
          <div class="kpi-sub">
            <span v-if="currentSession.summary?.anomalies_count">需研发关注与专项排查</span>
            <span v-else class="text-success">未发现严重性能劣化指标</span>
          </div>
        </div>
      </div>

      <!-- 多维时序曲线区 -->
      <a-card class="chart-section" :bordered="false">
        <a-tabs v-model:activeKey="activeChartTab">
          <a-tab-pane key="cpu" tab="CPU 计算负载 (App vs 系统)">
            <v-chart class="perf-chart" :option="cpuChartOption" :theme="chartTheme" autoresize />
          </a-tab-pane>
          <a-tab-pane key="memory" tab="物理内存与堆栈 (PSS / Native / Dalvik)">
            <v-chart class="perf-chart" :option="memoryChartOption" :theme="chartTheme" autoresize />
          </a-tab-pane>
          <a-tab-pane key="fps" tab="渲染帧率与卡顿掉帧 (FPS & Jank)">
            <v-chart class="perf-chart" :option="fpsChartOption" :theme="chartTheme" autoresize />
          </a-tab-pane>
          <a-tab-pane key="network" tab="网络 I/O 速率 (TX / RX)">
            <v-chart class="perf-chart" :option="networkChartOption" :theme="chartTheme" autoresize />
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <!-- 诊断异常事件与采样数据预览 -->
      <div v-if="currentSession" class="lower-tables-grid">
        <!-- 性能诊断异常列表 -->
        <a-card title="性能体检与智能归因异常项 (Anomalies)" size="small" class="sub-table-card">
          <template #extra>
            <a-tag color="error">{{ currentSession.anomalies?.length || 0 }} 处异常</a-tag>
          </template>
          <a-table
            :data-source="currentSession.anomalies || []"
            :columns="anomalyColumns"
            row-key="description"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'severity'">
                <a-tag :color="record.severity === 'critical' ? 'error' : 'warning'">
                  {{ record.severity.toUpperCase() }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'anomaly_type'">
                <a-tag color="purple">{{ formatAnomalyType(record.anomaly_type) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'metric_compare'">
                <span class="mono-text">
                  {{ record.metric_name }}: <strong>{{ record.metric_value }}</strong> (阈值: {{ record.threshold }})
                </span>
              </template>
              <template v-else-if="column.key === 'description'">
                <span class="desc-text">{{ record.description }}</span>
              </template>
            </template>
          </a-table>
        </a-card>

        <!-- 时序采样点快照表格 -->
        <a-card title="时序采样点数据快照 (Latest Samples)" size="small" class="sub-table-card">
          <template #extra>
            <span class="sample-count-note">已采集 {{ currentSession.samples_preview?.length || 0 }} 个采样点</span>
          </template>
          <a-table
            :data-source="currentSession.samples_preview || []"
            :columns="sampleColumns"
            row-key="timestamp_sec"
            size="small"
            :pagination="{ pageSize: 5, showTotal: (t: number) => `共 ${t} 点` }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'timestamp_sec'">
                <span class="mono-text">+{{ record.timestamp_sec.toFixed(1) }}s</span>
              </template>
              <template v-else-if="column.key === 'cpu'">
                <span class="mono-text">{{ record.cpu_app_pct }}% / {{ record.cpu_total_pct }}%</span>
              </template>
              <template v-else-if="column.key === 'memory'">
                <span class="mono-text">{{ record.memory_pss_mb }} MB</span>
              </template>
              <template v-else-if="column.key === 'fps'">
                <span class="mono-text" :class="record.fps < 40 ? 'text-critical' : ''">
                  {{ record.fps }} FPS ({{ record.jank_count }})
                </span>
              </template>
              <template v-else-if="column.key === 'network'">
                <span class="mono-text">{{ record.net_tx_kbps }} / {{ record.net_rx_kbps }} KB/s</span>
              </template>
            </template>
          </a-table>
        </a-card>
      </div>

      <a-empty v-else description="暂无选中的性能诊断会话，请点击「启动采集」新建会话或在下拉框选择历史会话" />
    </a-spin>

    <!-- 启动采集会话 Modal -->
    <a-modal
      v-model:open="showStartModal"
      title="启动移动端原生性能诊断采集会话"
      @ok="handleStartSession"
    >
      <a-form layout="vertical">
        <a-form-item label="性能采集会话 ID (Session ID)" required>
          <a-input v-model:value="startForm.session_id" placeholder="如: session_perf_smoke_01" />
        </a-form-item>
        <a-form-item label="移动设备序列号 (Device Serial)" required>
          <a-input v-model:value="startForm.device_serial" placeholder="如: emulator-5554 或 127.0.0.1:5555" />
        </a-form-item>
        <a-form-item label="目标应用被测包名 (Package Name)" required>
          <a-input v-model:value="startForm.package_name" placeholder="如: com.atp.autotest.demo" />
        </a-form-item>
        <a-form-item label="采样周期间隔 (秒)">
          <a-input-number v-model:value="startForm.sample_interval_sec" :min="0.1" :max="10.0" :step="0.5" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 批量注入模拟采样点 Modal -->
    <a-modal
      v-model:open="showAppendModal"
      title="追加时序采样点数据 (可模拟内存持续泄露与掉帧)"
      @ok="handleAppendSamples"
    >
      <div class="append-modal-tip">
        选择预设测试场景将自动构造带有特定性能特征（如持续递增的 PSS 内存模拟泄漏、或周期性极低 FPS 模拟卡顿掉帧）的时序点上报至当前会话。
      </div>
      <a-radio-group v-model:value="appendPreset" style="margin-bottom: 16px">
        <a-radio-button value="leak">内存线性递增泄露场景 (Slope > 15MB/min)</a-radio-button>
        <a-radio-button value="jank">频繁掉帧卡顿场景 (FPS &lt; 30)</a-radio-button>
        <a-radio-button value="healthy">正常平稳健康场景</a-radio-button>
      </a-radio-group>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import VChart from 'vue-echarts'
import { message } from 'ant-design-vue'
import {
  DashboardOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  StopOutlined,
  PlusOutlined,
  WarningOutlined,
  AlertOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  mobilePerfApi,
  type MobilePerfSessionReport,
  type PerformanceSamplePoint,
  type AnomalyType,
} from '@/api/mobilePerf'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme } = useChartTheme()

const loading = ref(false)
const stopping = ref(false)
const sessions = ref<MobilePerfSessionReport[]>([])
const selectedSessionId = ref<string | undefined>(undefined)
const currentSession = ref<MobilePerfSessionReport | null>(null)
const activeChartTab = ref<'cpu' | 'memory' | 'fps' | 'network'>('cpu')

const showStartModal = ref(false)
const startForm = reactive({
  session_id: `session_perf_${Date.now().toString().slice(-6)}`,
  device_serial: 'emulator-5554',
  package_name: 'com.atp.autotest.demo',
  sample_interval_sec: 1.0,
})

const showAppendModal = ref(false)
const appendPreset = ref<'leak' | 'jank' | 'healthy'>('leak')

const sessionOptions = computed(() =>
  sessions.value.map((s) => ({
    label: `${s.session_id} (${s.package_name})`,
    value: s.session_id,
  }))
)

const sessionStatusText = computed(() => {
  if (!currentSession.value) return '未选定会话'
  return currentSession.value.ended_at ? '采集已完成 (诊断归档)' : '采集中 (Active)'
})

const hasCriticalAnomaly = computed(() =>
  currentSession.value?.anomalies?.some((a) => a.severity === 'critical')
)

const hasWarningAnomaly = computed(() =>
  currentSession.value?.anomalies?.some((a) => a.severity === 'warning')
)

const bannerClass = computed(() => {
  if (hasCriticalAnomaly.value) return 'banner-critical'
  if (hasWarningAnomaly.value) return 'banner-warning'
  return 'banner-healthy'
})

const diagnosticVerdictTitle = computed(() => {
  if (hasCriticalAnomaly.value) return '发现高危性能劣化缺陷 (Critical Performance Anomaly)'
  if (hasWarningAnomaly.value) return '检测到轻中度性能警告 (Performance Warning)'
  return '移动端原生运行时性能达标 (Healthy Performance Profile)'
})

const diagnosticVerdictDesc = computed(() => {
  if (!currentSession.value) return ''
  const summary = currentSession.value.summary
  if (summary?.has_memory_leak) {
    return `检测到应用物理内存 (PSS) 呈现持续单调线性增长趋势 (增长斜率: ${summary.memory_growth_slope_mb_per_min} MB/min)，判定存在确定性内存泄露风险！`
  }
  if (summary?.has_jank_drops) {
    return `检测到应用平均帧率仅 ${summary.fps_avg} FPS，并伴随 ${summary.total_janks} 次 Jank 严重卡顿掉帧，界面存在明显卡顿。`
  }
  return `应用平均 CPU 占用 ${summary?.cpu_app_avg || 0}%，最高 PSS 内存 ${summary?.memory_pss_max || 0} MB，平均帧率 ${summary?.fps_avg || 60} FPS，各项指标均在稳定阈值内。`
})

// 表格列定义
const anomalyColumns = [
  { title: '严重级别', key: 'severity', width: 95 },
  { title: '异常类型', key: 'anomaly_type', width: 140 },
  { title: '指标实测 / 阈值', key: 'metric_compare', width: 220 },
  { title: '诊断与建议', key: 'description' },
]

const sampleColumns = [
  { title: '偏移时序', key: 'timestamp_sec', width: 90 },
  { title: 'CPU (App/系统)', key: 'cpu', width: 130 },
  { title: '物理内存 PSS', key: 'memory', width: 110 },
  { title: '渲染 FPS (Jank)', key: 'fps', width: 130 },
  { title: '网络速率 (TX/RX)', key: 'network' },
]

function formatAnomalyType(type: AnomalyType): string {
  switch (type) {
    case 'MEMORY_LEAK_WARNING':
      return '内存持续泄露'
    case 'HIGH_CPU_ALERT':
      return '高 CPU 占用'
    case 'JANK_FRAME_DROP':
      return '严重掉帧卡顿'
    default:
      return type
  }
}

// ECharts 图表配置计算
const samples = computed(() => currentSession.value?.samples_preview || [])
const timestamps = computed(() => samples.value.map((s) => `+${s.timestamp_sec.toFixed(1)}s`))

const cpuChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['App CPU (%)', '系统总 CPU (%)'] },
  grid: { top: 36, right: 20, bottom: 24, left: 40 },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
  series: [
    {
      name: 'App CPU (%)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.cpu_app_pct),
      itemStyle: { color: '#6366f1' },
      areaStyle: { opacity: 0.15, color: '#6366f1' },
    },
    {
      name: '系统总 CPU (%)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.cpu_total_pct),
      itemStyle: { color: '#94a3b8' },
    },
  ],
}))

const memoryChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['物理内存 PSS (MB)', 'Native Heap (MB)', 'Dalvik Heap (MB)'] },
  grid: { top: 36, right: 20, bottom: 24, left: 48 },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value', axisLabel: { formatter: '{value} MB' } },
  series: [
    {
      name: '物理内存 PSS (MB)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.memory_pss_mb),
      itemStyle: { color: '#ec4899' },
      areaStyle: { opacity: 0.15, color: '#ec4899' },
    },
    {
      name: 'Native Heap (MB)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.memory_native_heap_mb),
      itemStyle: { color: '#3b82f6' },
    },
    {
      name: 'Dalvik Heap (MB)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.memory_dalvik_heap_mb),
      itemStyle: { color: '#10b981' },
    },
  ],
}))

const fpsChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['渲染帧率 FPS', 'Jank 掉帧次数'] },
  grid: { top: 36, right: 48, bottom: 24, left: 40 },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: [
    { type: 'value', max: 60, axisLabel: { formatter: '{value} fps' } },
    { type: 'value', position: 'right', axisLabel: { formatter: '{value} 次' } },
  ],
  series: [
    {
      name: '渲染帧率 FPS',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.fps),
      itemStyle: { color: '#10b981' },
    },
    {
      name: 'Jank 掉帧次数',
      type: 'bar',
      yAxisIndex: 1,
      data: samples.value.map((s) => s.jank_count),
      itemStyle: { color: '#f59e0b' },
    },
  ],
}))

const networkChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['上行 TX (KB/s)', '下行 RX (KB/s)'] },
  grid: { top: 36, right: 20, bottom: 24, left: 48 },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value', axisLabel: { formatter: '{value} KB/s' } },
  series: [
    {
      name: '上行 TX (KB/s)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.net_tx_kbps),
      itemStyle: { color: '#06b6d4' },
    },
    {
      name: '下行 RX (KB/s)',
      type: 'line',
      smooth: true,
      data: samples.value.map((s) => s.net_rx_kbps),
      itemStyle: { color: '#8b5cf6' },
      areaStyle: { opacity: 0.15, color: '#8b5cf6' },
    },
  ],
}))

async function refreshData() {
  loading.value = true
  try {
    const res = await mobilePerfApi.listSessions()
    sessions.value = res.sessions || []
    if (sessions.value.length > 0) {
      if (!selectedSessionId.value || !sessions.value.some((s) => s.session_id === selectedSessionId.value)) {
        selectedSessionId.value = sessions.value[0].session_id
      }
      await loadSessionDetail(selectedSessionId.value)
    } else {
      currentSession.value = null
    }
  } catch (err: any) {
    message.error(`加载性能会话列表失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function loadSessionDetail(sessionId: string) {
  try {
    const report = await mobilePerfApi.getSession(sessionId)
    currentSession.value = report
  } catch (err: any) {
    message.error(`获取性能会话报告失败: ${err.message || err}`)
  }
}

function handleSessionChange(val: any) {
  if (!val) return
  const sid = String(val)
  selectedSessionId.value = sid
  loadSessionDetail(sid)
}

async function handleStartSession() {
  try {
    const res = await mobilePerfApi.startSession(startForm)
    message.success(res.message || '性能采集会话已启动')
    showStartModal.value = false
    selectedSessionId.value = startForm.session_id
    await refreshData()
  } catch (err: any) {
    message.error(`启动性能会话失败: ${err.message || err}`)
  }
}

async function handleAppendSamples() {
  if (!currentSession.value) return
  const sid = currentSession.value.session_id

  // 构造模拟时序数据
  const mockBatch: PerformanceSamplePoint[] = []
  const baseTime = currentSession.value.samples_preview.length * 1.0

  for (let i = 0; i < 6; i++) {
    const t = baseTime + i * 1.0
    if (appendPreset.value === 'leak') {
      mockBatch.push({
        timestamp_sec: t,
        cpu_app_pct: 35.0 + Math.random() * 10,
        cpu_total_pct: 55.0,
        memory_pss_mb: 120.0 + (t * 2.5), // 持续增长模拟内存泄漏
        memory_native_heap_mb: 60.0 + t,
        memory_dalvik_heap_mb: 40.0,
        fps: 58.0,
        jank_count: 0,
        net_tx_kbps: 12.0,
        net_rx_kbps: 45.0,
      })
    } else if (appendPreset.value === 'jank') {
      mockBatch.push({
        timestamp_sec: t,
        cpu_app_pct: 85.0 + Math.random() * 10,
        cpu_total_pct: 95.0,
        memory_pss_mb: 130.0,
        memory_native_heap_mb: 65.0,
        memory_dalvik_heap_mb: 42.0,
        fps: 22.0 + Math.random() * 8, // 严重掉帧
        jank_count: 5,
        net_tx_kbps: 5.0,
        net_rx_kbps: 10.0,
      })
    } else {
      mockBatch.push({
        timestamp_sec: t,
        cpu_app_pct: 20.0 + Math.random() * 5,
        cpu_total_pct: 35.0,
        memory_pss_mb: 95.0 + Math.random() * 2,
        memory_native_heap_mb: 45.0,
        memory_dalvik_heap_mb: 30.0,
        fps: 59.5,
        jank_count: 0,
        net_tx_kbps: 8.0,
        net_rx_kbps: 16.0,
      })
    }
  }

  try {
    const res = await mobilePerfApi.appendSamples(sid, mockBatch)
    message.success(res.message || '时序采样点已注入')
    showAppendModal.value = false
    await loadSessionDetail(sid)
  } catch (err: any) {
    message.error(`注入采样数据失败: ${err.message || err}`)
  }
}

async function handleStopSession() {
  if (!currentSession.value) return
  stopping.value = true
  try {
    const res = await mobilePerfApi.stopSession(currentSession.value.session_id)
    message.success(res.message || '性能诊断报告已生成')
    currentSession.value = res.report
    await refreshData()
  } catch (err: any) {
    message.error(`停止并诊断失败: ${err.message || err}`)
  } finally {
    stopping.value = false
  }
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.mobile-perf-diagnostics-viewer {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--c-border-subtle, #e2e8f0);
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.header-icon-box {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #ede9fe;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-icon {
  font-size: 18px;
  color: #7c3aed;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
}

.header-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.5;
}

.live-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  margin-right: 4px;
}

.live-dot-active {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

/* 诊断结论横幅 */
.diagnostic-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.banner-healthy {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.banner-warning {
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.banner-critical {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.banner-icon-box {
  font-size: 24px;
}

.banner-content {
  flex: 1;
}

.banner-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  margin-top: 2px;
}

.banner-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: #64748b;
  text-align: right;
}

.banner-meta code {
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 4px;
  border-radius: 4px;
}

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.kpi-card {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 6px;
  padding: 12px;
}

.card-alert {
  border-color: #f87171;
  background: #fff1f2;
}

.card-warning {
  border-color: #fbbf24;
  background: #fffbeb;
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin-bottom: 6px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.kpi-number {
  font-size: 22px;
  font-weight: 700;
  color: var(--c-text-primary, #1e293b);
}

.kpi-sub-num {
  font-size: 13px;
  color: var(--c-text-tertiary, #94a3b8);
}

.kpi-unit {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  margin-top: 6px;
}

.chart-section {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 6px;
  margin-bottom: 16px;
}

.perf-chart {
  height: 280px;
  width: 100%;
}

.lower-tables-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.sub-table-card {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.desc-text {
  font-size: 11px;
  color: #334155;
}

.sample-count-note {
  font-size: 11px;
  color: #64748b;
}

.append-modal-tip {
  font-size: 12px;
  color: #475569;
  background: #f1f5f9;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 14px;
}

.text-critical {
  color: #ef4444 !important;
}

.text-warning {
  color: #f59e0b !important;
}

.text-success {
  color: #10b981 !important;
}
</style>
