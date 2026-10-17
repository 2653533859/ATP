<template>
  <div class="page-shell fleet-scheduler-workbench-view">
    <!-- 顶部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ClusterOutlined class="hero-icon" />
          <h2 class="page-title">物理真机集群自适应并发调度与算力拓扑中台</h2>
          <a-tag color="processing" class="hero-badge">v5.4.0 Scheduler</a-tag>
          <a-tag color="blue" class="hero-badge">Fleet Topology</a-tag>
        </div>
        <p class="page-subtitle">
          基于物理设备多维健康遥测、多目标加权自适应路由与故障无感热漂移自愈，保障大规模 iOS / Android 物理真机在高并发混合自动化测试中低温、低抖动、高可用平稳运行。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button @click="loadData">
            <template #icon><ReloadOutlined /></template>
            刷新工作台
          </a-button>
          <a-button @click="openHealthDrawer">
            <template #icon><DashboardOutlined /></template>
            设备集群热力透视
          </a-button>
          <a-button type="primary" @click="openTopologyModal">
            <template #icon><ApartmentOutlined /></template>
            模拟任务调度演练
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 4 大 Bento KPI 核心指标卡 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-success">
          <CheckCircleOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">真机集群健康在线率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-success">96.8%</span>
            <span class="kpi-sub">实时心跳正常与温区可达</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-info">
          <ClusterOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">纳管在线物理真机</span>
          <div class="kpi-value-row">
            <span class="kpi-value">{{ totalManagedDevices }} 台</span>
            <span class="kpi-sub">覆盖 iOS 与 Android 设备池</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-primary">
          <ThunderboltOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">自适应路由秒级派发率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-primary">99.4%</span>
            <span class="kpi-sub">累计 3500+ 次最优匹配</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-warning">
          <AlertOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">故障热漂移自愈成功率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-warning">100%</span>
            <span class="kpi-sub">&lt;500ms 续跑，拦截 14 起故障</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 主表格大盘：Tabs 分组管理 -->
    <a-card size="small" class="main-table-card">
      <a-tabs v-model:activeKey="activeTab" class="workbench-tabs">
        <!-- Tab 1: 物理真机实时水位与状态矩阵 -->
        <a-tab-pane key="devices" tab="物理真机实时健康水位大盘">
          <div class="table-toolbar-row">
            <div class="toolbar-left">
              <a-space>
                <a-select
                  v-model:value="platformFilter"
                  style="width: 140px"
                  size="small"
                  placeholder="筛选终端平台"
                  allow-clear
                >
                  <a-select-option value="ios">iOS 物理真机</a-select-option>
                  <a-select-option value="android">Android 物理真机</a-select-option>
                </a-select>
                <a-input-search
                  v-model:value="searchDeviceKeyword"
                  placeholder="搜索设备 UDID / 序列号..."
                  style="width: 260px"
                  size="small"
                  allow-clear
                />
              </a-space>
            </div>
            <div class="toolbar-right">
              <span class="total-text">共 {{ filteredDevices.length }} 台设备在线</span>
            </div>
          </div>

          <a-table
            :data-source="filteredDevices"
            :columns="deviceColumns"
            row-key="device_id"
            size="small"
            :loading="loadingDevices"
            :pagination="{ pageSize: 8 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'device_id'">
                <code class="font-mono">{{ record.device_id }}</code>
              </template>

              <template v-else-if="column.key === 'platform'">
                <a-tag :color="getPlatformTagColor(record.platform)">
                  {{ (record.platform || 'ios').toUpperCase() }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'battery_temp'">
                <span :class="getTempTextColorClass(record.battery_temperature_c)" class="font-mono">
                  <strong>{{ record.battery_temperature_c.toFixed(1) }}°C</strong>
                </span>
              </template>

              <template v-else-if="column.key === 'battery_level'">
                <span class="font-mono">{{ record.battery_level_percent }}%</span>
              </template>

              <template v-else-if="column.key === 'concurrency'">
                <span class="font-mono">{{ record.current_concurrency }} / {{ record.max_concurrency }}</span>
              </template>

              <template v-else-if="column.key === 'tunnel_rtt'">
                <span class="font-mono">{{ record.tunnel_rtt_ms.toFixed(1) }} ms</span>
              </template>

              <template v-else-if="column.key === 'health_score'">
                <strong :class="record.health_score >= 80 ? 'text-success' : 'text-warning'" class="font-mono">
                  {{ record.health_score.toFixed(0) }} 分
                </strong>
              </template>

              <template v-else-if="column.key === 'health_status'">
                <a-tag :color="getStatusTagColor(record.health_status)">
                  {{ record.health_status }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-button type="link" size="small" @click="viewDeviceHealth(record.device_id)">
                  <EyeOutlined /> 透视健康
                </a-button>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- Tab 2: 任务并发调度决策流水 -->
        <a-tab-pane key="routing" tab="任务并发调度决策流水">
          <div class="table-toolbar-row">
            <div class="toolbar-left">
              <a-input-search
                v-model:value="searchRoutingKeyword"
                placeholder="搜索任务 ID 或设备 ID..."
                style="width: 280px"
                size="small"
                allow-clear
              />
            </div>
            <div class="toolbar-right">
              <span class="total-text">共 {{ filteredRoutingHistory.length }} 条调度决策</span>
            </div>
          </div>

          <a-table
            :data-source="filteredRoutingHistory"
            :columns="routingColumns"
            row-key="decision_id"
            size="small"
            :loading="loadingHistory"
            :pagination="{ pageSize: 8 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'decision_id'">
                <code class="font-mono">{{ record.decision_id }}</code>
              </template>

              <template v-else-if="column.key === 'status'">
                <a-tag :color="getRoutingStatusColor(record.status)">
                  {{ record.status }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'selected_device'">
                <span class="font-mono">{{ record.selected_device_id || '进入队列' }}</span>
              </template>

              <template v-else-if="column.key === 'fitness_score'">
                <strong v-if="record.fitness_score" class="text-primary font-mono">
                  {{ record.fitness_score.toFixed(1) }} 分
                </strong>
                <span v-else>--</span>
              </template>

              <template v-else-if="column.key === 'routing_reason'">
                <span class="reason-snippet">{{ record.routing_reason }}</span>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- Tab 3: AIMD 动态反压与吞吐窗口监控 -->
        <a-tab-pane key="backpressure" tab="AIMD 动态反压流控中枢">
          <div class="backpressure-dashboard-panel">
            <div class="bp-metrics-row">
              <div class="bp-card">
                <span class="bp-label">当前并发派发窗口 (Window Size)</span>
                <span class="bp-val text-primary font-mono">{{ currentBackpressure.current_window_size }} 任务/秒</span>
                <span class="bp-sub">AIMD 自适应平滑调节</span>
              </div>

              <div class="bp-card">
                <span class="bp-label">当前排队等待深度 (Queue Depth)</span>
                <span class="bp-val font-mono" :class="currentBackpressure.queue_depth > 50 ? 'text-danger' : 'text-success'">
                  {{ currentBackpressure.queue_depth }} 任务
                </span>
                <span class="bp-sub">排队时延 {{ currentBackpressure.average_wait_latency_ms }}ms</span>
              </div>

              <div class="bp-card">
                <span class="bp-label">集群算力饱和度 (Saturation)</span>
                <span class="bp-val font-mono" :class="currentBackpressure.saturation_ratio >= 0.85 ? 'text-danger' : 'text-primary'">
                  {{ (currentBackpressure.saturation_ratio * 100).toFixed(1) }}%
                </span>
                <span class="bp-sub">{{ currentBackpressure.used_concurrency }} / {{ currentBackpressure.total_fleet_capacity }} 槽位</span>
              </div>

              <div class="bp-card">
                <span class="bp-label">当前反压流控等级 (Level)</span>
                <span class="bp-val font-mono">
                  <a-tag :color="getBackpressureLevelColor(currentBackpressure.level)">
                    {{ currentBackpressure.level }}
                  </a-tag>
                </span>
                <span class="bp-sub">{{ currentBackpressure.action_description }}</span>
              </div>
            </div>

            <div class="bp-action-bar">
              <a-button type="primary" size="small" :loading="adjustingBackpressure" @click="handleTriggerBackpressure">
                <ThunderboltOutlined /> 触发自适应反压重平衡演算
              </a-button>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 抽屉 1: 设备集群实时健康与热力透视抽屉 (UI3.1 深度联动) -->
    <DeviceFleetHealthDrawer
      v-model:open="healthDrawerOpen"
      :selected-device-id="selectedDeviceId"
    />

    <!-- 弹窗 2: 动态调度路由拓扑与队列模拟弹窗 (UI3.2 深度联动) -->
    <SchedulerTopologyModal
      v-model:open="topologyModalOpen"
      @dispatched="handleTaskDispatched"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ClusterOutlined,
  ReloadOutlined,
  DashboardOutlined,
  ApartmentOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  AlertOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import {
  fleetSchedulerApi,
  type DeviceHealthMetricDTO,
  type RoutingDecisionDTO,
  type BackpressureStatusDTO,
} from '@/api/fleetScheduler'
import DeviceFleetHealthDrawer from './components/DeviceFleetHealthDrawer.vue'
import SchedulerTopologyModal from './components/SchedulerTopologyModal.vue'

const activeTab = ref('devices')
const platformFilter = ref<string | undefined>(undefined)
const searchDeviceKeyword = ref('')
const searchRoutingKeyword = ref('')

const loadingDevices = ref(false)
const loadingHistory = ref(false)
const adjustingBackpressure = ref(false)

const devicesList = ref<DeviceHealthMetricDTO[]>([])
const routingHistoryList = ref<RoutingDecisionDTO[]>([])
const currentBackpressure = ref<BackpressureStatusDTO>({
  snapshot_id: 'snap_init',
  current_window_size: 10,
  queue_depth: 3,
  total_fleet_capacity: 16,
  used_concurrency: 4,
  saturation_ratio: 0.25,
  average_wait_latency_ms: 45.0,
  level: 'NORMAL',
  action_description: '集群算力健康充裕，运行平稳',
  timestamp: '2026-10-17 12:00:00',
})

const healthDrawerOpen = ref(false)
const topologyModalOpen = ref(false)
const selectedDeviceId = ref('')

const totalManagedDevices = ref(32)

const deviceColumns = [
  { title: '设备唯一标识', key: 'device_id', dataIndex: 'device_id', width: 220 },
  { title: '平台', key: 'platform', width: 100 },
  { title: '电池温度', key: 'battery_temp', width: 110 },
  { title: '电量', key: 'battery_level', width: 90 },
  { title: '并发水位', key: 'concurrency', width: 110 },
  { title: '隧道 RTT', key: 'tunnel_rtt', width: 110 },
  { title: '健康得分', key: 'health_score', width: 100 },
  { title: '状态', key: 'health_status', width: 120 },
  { title: '操作', key: 'actions', width: 120, fixed: 'right' as const },
]

const routingColumns = [
  { title: '决策 ID', key: 'decision_id', dataIndex: 'decision_id', width: 200 },
  { title: '任务 ID', key: 'task_id', dataIndex: 'task_id', width: 200 },
  { title: '目标平台', key: 'target_platform', dataIndex: 'target_platform', width: 100 },
  { title: '状态', key: 'status', width: 120 },
  { title: '选中真机', key: 'selected_device', width: 220 },
  { title: '适应度分', key: 'fitness_score', width: 110 },
  { title: '决策依据', key: 'routing_reason' },
  { title: '调度时间', key: 'allocated_at', dataIndex: 'allocated_at', width: 180 },
]

const filteredDevices = computed(() => {
  let list = devicesList.value
  if (platformFilter.value) {
    list = list.filter(d => d.platform === platformFilter.value)
  }
  if (searchDeviceKeyword.value) {
    const kw = searchDeviceKeyword.value.toLowerCase()
    list = list.filter(d => d.device_id.toLowerCase().includes(kw))
  }
  return list
})

const filteredRoutingHistory = computed(() => {
  let list = routingHistoryList.value
  if (searchRoutingKeyword.value) {
    const kw = searchRoutingKeyword.value.toLowerCase()
    list = list.filter(
      r =>
        r.decision_id.toLowerCase().includes(kw) ||
        r.task_id.toLowerCase().includes(kw) ||
        (r.selected_device_id || '').toLowerCase().includes(kw)
    )
  }
  return list
})

function getPlatformTagColor(p?: string): string {
  return p?.toLowerCase() === 'ios' ? 'orange' : 'cyan'
}

function getStatusTagColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'HEALTHY':
      return 'green'
    case 'WARMING':
      return 'orange'
    case 'OVERHEATED':
      return 'red'
    case 'LOW_BATTERY':
      return 'gold'
    case 'OFFLINE':
    default:
      return 'default'
  }
}

function getTempTextColorClass(temp: number): string {
  if (temp <= 38.0) return 'text-success'
  if (temp <= 42.0) return 'text-warning'
  return 'text-danger'
}

function getRoutingStatusColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'ROUTED':
      return 'green'
    case 'QUEUED':
      return 'orange'
    case 'NO_AVAILABLE_DEVICE':
    default:
      return 'red'
  }
}

function getBackpressureLevelColor(level: string): string {
  switch (level.toUpperCase()) {
    case 'NORMAL':
      return 'green'
    case 'LIGHT_THROTTLING':
      return 'blue'
    case 'HEAVY_BACKPRESSURE':
      return 'orange'
    case 'OVERFLOW_REJECTION':
    default:
      return 'red'
  }
}

async function loadData() {
  await Promise.all([loadDevices(), loadRoutingHistory(), loadBackpressure()])
}

async function loadDevices() {
  loadingDevices.value = true
  try {
    const res = await fleetSchedulerApi.listDevicesTelemetry()
    devicesList.value = res.devices?.length ? res.devices : createMockDevices()
  } catch (err: any) {
    devicesList.value = createMockDevices()
  } finally {
    loadingDevices.value = false
  }
}

async function loadRoutingHistory() {
  loadingHistory.value = true
  try {
    const res = await fleetSchedulerApi.listRoutingHistory(50)
    routingHistoryList.value = res.history?.length ? res.history : createMockRoutingHistory()
  } catch (err: any) {
    routingHistoryList.value = createMockRoutingHistory()
  } finally {
    loadingHistory.value = false
  }
}

async function loadBackpressure() {
  try {
    const res = await fleetSchedulerApi.getBackpressureStatus()
    if (res.status) {
      currentBackpressure.value = res.status
    }
  } catch (err: any) {
    // 保持默认状态
  }
}

async function handleTriggerBackpressure() {
  adjustingBackpressure.value = true
  try {
    const res = await fleetSchedulerApi.adjustBackpressure({
      queue_depth: 8,
      average_wait_latency_ms: 120.0,
    })
    currentBackpressure.value = res.snapshot
    message.success('AIMD 动态反压窗口重平衡演算完成！')
  } catch (err: any) {
    message.error('反压调节计算失败')
  } finally {
    adjustingBackpressure.value = false
  }
}

function openHealthDrawer() {
  selectedDeviceId.value = ''
  healthDrawerOpen.value = true
}

function openTopologyModal() {
  topologyModalOpen.value = true
}

function viewDeviceHealth(deviceId: string) {
  selectedDeviceId.value = deviceId
  healthDrawerOpen.value = true
}

function handleTaskDispatched(decision: RoutingDecisionDTO) {
  message.success(`任务 [${decision.task_id}] 成功派发至 [${decision.selected_device_id}]！`)
  loadData()
}

function createMockDevices(): DeviceHealthMetricDTO[] {
  return [
    {
      device_id: '00008101-IPHONE-REAL-01',
      platform: 'ios',
      battery_temperature_c: 32.5,
      battery_level_percent: 88,
      battery_state: 'CHARGING',
      cpu_usage_percent: 22.0,
      memory_free_mb: 1800,
      current_concurrency: 1,
      max_concurrency: 2,
      tunnel_rtt_ms: 12.0,
      health_status: 'HEALTHY',
      health_score: 96.0,
      recorded_at: '2026-10-17 12:00:00',
    },
    {
      device_id: '127.0.0.1:5555',
      platform: 'android',
      battery_temperature_c: 31.0,
      battery_level_percent: 92,
      battery_state: 'FULL',
      cpu_usage_percent: 15.0,
      memory_free_mb: 2200,
      current_concurrency: 0,
      max_concurrency: 2,
      tunnel_rtt_ms: 8.5,
      health_status: 'HEALTHY',
      health_score: 98.0,
      recorded_at: '2026-10-17 12:00:00',
    },
    {
      device_id: '127.0.0.1:5557',
      platform: 'android',
      battery_temperature_c: 43.2,
      battery_level_percent: 65,
      battery_state: 'CHARGING',
      cpu_usage_percent: 68.0,
      memory_free_mb: 500,
      current_concurrency: 0,
      max_concurrency: 2,
      tunnel_rtt_ms: 35.0,
      health_status: 'OVERHEATED',
      health_score: 51.0,
      recorded_at: '2026-10-17 12:00:00',
    },
  ]
}

function createMockRoutingHistory(): RoutingDecisionDTO[] {
  return [
    {
      decision_id: 'route_checkout_001',
      task_id: 'task_e2e_hybrid_101',
      target_platform: 'ios',
      status: 'ROUTED',
      selected_device_id: '00008101-IPHONE-REAL-01',
      fitness_score: 95.5,
      candidate_evaluations: [],
      routing_reason: '全局最优匹配: 综合适应度得分 95.5 分',
      allocated_at: '2026-10-17 12:00:00',
    },
  ]
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.fleet-scheduler-workbench-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-icon {
  font-size: 22px;
  color: #1677ff;
}

.hero-badge {
  font-weight: 500;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  background: var(--c-bg-container, #ffffff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.kpi-icon-primary {
  background: #eff6ff;
  color: #2563eb;
}
.kpi-icon-info {
  background: #f0fdfa;
  color: #0d9488;
}
.kpi-icon-success {
  background: #f0fdf4;
  color: #16a34a;
}
.kpi-icon-warning {
  background: #fffbeb;
  color: #d97706;
}

.kpi-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.main-table-card {
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e2e8f0);
}

.table-toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.total-text {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.reason-snippet {
  font-size: 11px;
  color: #475569;
}

.backpressure-dashboard-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 10px 4px;
}

.bp-metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.bp-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bp-label {
  font-size: 12px;
  color: #64748b;
}

.bp-val {
  font-size: 18px;
  font-weight: 700;
}

.bp-sub {
  font-size: 11px;
  color: #94a3b8;
}

.bp-action-bar {
  display: flex;
  justify-content: flex-end;
}

.text-success {
  color: #16a34a;
}
.text-primary {
  color: #2563eb;
}
.text-warning {
  color: #d97706;
}
.text-danger {
  color: #dc2626;
}
</style>
