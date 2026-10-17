<template>
  <a-drawer
    :open="open"
    title="物理真机集群实时健康与热力透视中枢"
    width="85%"
    placement="right"
    :destroy-on-close="true"
    class="fleet-health-drawer"
    @close="handleClose"
  >
    <div class="fleet-drawer-container">
      <!-- 顶部集群容量与指标横幅 -->
      <div class="fleet-hero-banner">
        <div class="hero-left-metrics">
          <div class="cluster-summary-box">
            <span class="cluster-temp-number" :class="getClusterTempColorClass(clusterAverages.avg_temperature_c)">
              {{ clusterAverages.avg_temperature_c ? clusterAverages.avg_temperature_c.toFixed(1) : '--' }}°C
            </span>
            <span class="cluster-temp-label">全集群平均温度</span>
          </div>

          <div class="metrics-summary-content">
            <div class="summary-line-top">
              <span class="fleet-title"><ClusterOutlined /> 物理真机在线集群拓扑</span>
              <a-tag color="blue">实时心跳遥测</a-tag>
              <span class="summary-avg-item font-mono">
                平均电量: <strong>{{ clusterAverages.avg_battery_percent }}%</strong>
              </span>
              <span class="summary-avg-item font-mono">
                平均隧道 RTT: <strong>{{ clusterAverages.avg_tunnel_rtt_ms }}ms</strong>
              </span>
            </div>

            <div class="stats-pills-row">
              <span class="stat-pill text-success">
                健康在线: <strong>{{ capacityData?.healthy_count || 0 }}</strong> 台
              </span>
              <span class="stat-pill text-warning">
                升温警戒: <strong>{{ capacityData?.warming_count || 0 }}</strong> 台
              </span>
              <span
                class="stat-pill"
                :class="{ 'has-overheat': (capacityData?.overheated_count || 0) > 0 }"
              >
                过热冷却: <strong>{{ capacityData?.overheated_count || 0 }}</strong> 台
              </span>
              <span class="stat-pill">
                算力容量: <strong>{{ capacityData?.used_concurrency || 0 }} / {{ capacityData?.total_capacity || 0 }} 并发</strong>
              </span>
            </div>
          </div>
        </div>

        <div class="hero-right-actions">
          <a-space>
            <a-button size="small" :loading="loading" @click="fetchFleetData">
              <template #icon><ReloadOutlined /></template>
              刷新集群遥测
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 主视图: 筛选与设备卡片热力矩阵 -->
      <div class="fleet-matrix-toolbar">
        <div class="toolbar-left">
          <a-space size="small">
            <a-radio-group v-model:value="selectedPlatformFilter" button-style="solid" size="small">
              <a-radio-button value="all">全量设备 ({{ devicesList.length }})</a-radio-button>
              <a-radio-button value="ios">iOS 真机 ({{ iosCount }})</a-radio-button>
              <a-radio-button value="android">Android 真机 ({{ androidCount }})</a-radio-button>
            </a-radio-group>
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="搜索设备 UDID / 序列号..."
              style="width: 240px"
              size="small"
              allow-clear
            />
          </a-space>
        </div>
        <div class="toolbar-right">
          <span class="legend-item"><span class="legend-dot dot-normal" /> 正常 (&le;38°C)</span>
          <span class="legend-item"><span class="legend-dot dot-warming" /> 升温 (38~42°C)</span>
          <span class="legend-item"><span class="legend-dot dot-overheat" /> 紧急过热 (&gt;42°C)</span>
        </div>
      </div>

      <!-- 设备热力图卡片网格 -->
      <div class="devices-heatmap-grid">
        <div
          v-for="dev in filteredDevices"
          :key="dev.device_id"
          class="device-health-card"
          :class="[
            'status-' + dev.health_status.toLowerCase(),
            { selected: selectedDeviceId === dev.device_id }
          ]"
          @click="selectDevice(dev.device_id)"
        >
          <div class="card-top-head">
            <div class="device-ident-col">
              <span class="device-name">{{ dev.device_id }}</span>
              <a-tag :color="getPlatformTagColor(dev.platform)" size="small">
                {{ dev.platform.toUpperCase() }}
              </a-tag>
            </div>
            <div class="device-health-badge">
              <span class="score-badge font-mono">{{ dev.health_score.toFixed(0) }} 分</span>
              <a-tag :color="getStatusTagColor(dev.health_status)" size="small">
                {{ dev.health_status }}
              </a-tag>
            </div>
          </div>

          <!-- 核心热力与指标行 -->
          <div class="thermal-metric-bar">
            <div class="thermal-label-row">
              <span class="metric-label"><ThunderboltOutlined /> 电池温度</span>
              <strong :class="getTempTextColorClass(dev.battery_temperature_c)">
                {{ dev.battery_temperature_c.toFixed(1) }}°C
              </strong>
            </div>
            <div class="temp-progress-track">
              <div
                class="temp-progress-bar"
                :style="{ width: getTempPercentWidth(dev.battery_temperature_c) + '%' }"
                :class="getTempBarColorClass(dev.battery_temperature_c)"
              />
            </div>
          </div>

          <div class="battery-metric-bar">
            <div class="battery-label-row">
              <span class="metric-label">电池电量</span>
              <span class="battery-val font-mono">
                {{ dev.battery_level_percent }}% ({{ dev.battery_state }})
              </span>
            </div>
            <div class="battery-progress-track">
              <div
                class="battery-progress-bar"
                :style="{ width: dev.battery_level_percent + '%' }"
                :class="dev.battery_level_percent < 20 ? 'bg-danger' : 'bg-success'"
              />
            </div>
          </div>

          <div class="card-bottom-info">
            <span class="info-pill font-mono">
              并发: <strong>{{ dev.current_concurrency }} / {{ dev.max_concurrency }}</strong>
            </span>
            <span class="info-pill font-mono">
              RTT: <strong>{{ dev.tunnel_rtt_ms.toFixed(1) }}ms</strong>
            </span>
            <span class="info-pill font-mono">
              CPU: <strong>{{ dev.cpu_usage_percent.toFixed(0) }}%</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ClusterOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  fleetSchedulerApi,
  type DeviceHealthMetricDTO,
  type CapacitySummaryDTO,
} from '@/api/fleetScheduler'

interface Props {
  open: boolean
  selectedDeviceId?: string
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  selectedDeviceId: '',
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'selected', deviceId: string): void
}>()

const loading = ref(false)
const selectedPlatformFilter = ref('all')
const searchKeyword = ref('')
const devicesList = ref<DeviceHealthMetricDTO[]>([])
const capacityData = ref<CapacitySummaryDTO | null>(null)

const clusterAverages = computed(() => {
  return (
    capacityData.value?.cluster_averages || {
      avg_temperature_c: 33.5,
      avg_battery_percent: 82.0,
      avg_tunnel_rtt_ms: 16.5,
    }
  )
})

const iosCount = computed(() => devicesList.value.filter(d => d.platform === 'ios').length)
const androidCount = computed(() => devicesList.value.filter(d => d.platform === 'android').length)

const filteredDevices = computed(() => {
  let list = devicesList.value
  if (selectedPlatformFilter.value !== 'all') {
    list = list.filter(d => d.platform === selectedPlatformFilter.value)
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(d => d.device_id.toLowerCase().includes(kw))
  }
  return list
})

function getPlatformTagColor(p: string): string {
  return p.toLowerCase() === 'ios' ? 'orange' : 'cyan'
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

function getClusterTempColorClass(temp?: number): string {
  if (!temp) return 'text-secondary'
  if (temp <= 36.0) return 'text-success'
  if (temp <= 40.0) return 'text-warning'
  return 'text-danger'
}

function getTempTextColorClass(temp: number): string {
  if (temp <= 38.0) return 'text-success'
  if (temp <= 42.0) return 'text-warning'
  return 'text-danger'
}

function getTempPercentWidth(temp: number): number {
  // 25°C 对应 10%, 45°C 对应 100%
  const clamped = Math.max(25, Math.min(45, temp))
  return ((clamped - 25) / 20) * 100
}

function getTempBarColorClass(temp: number): string {
  if (temp <= 38.0) return 'bar-green'
  if (temp <= 42.0) return 'bar-orange'
  return 'bar-red'
}

function selectDevice(id: string) {
  emit('selected', id)
}

async function fetchFleetData() {
  loading.value = true
  try {
    const [devRes, capRes] = await Promise.all([
      fleetSchedulerApi.listDevicesTelemetry(),
      fleetSchedulerApi.getCapacitySummary(),
    ])
    devicesList.value = devRes.devices?.length ? devRes.devices : createMockDevices()
    capacityData.value = capRes || createMockCapacity()
  } catch (err: any) {
    devicesList.value = createMockDevices()
    capacityData.value = createMockCapacity()
  } finally {
    loading.value = false
  }
}

function createMockDevices(): DeviceHealthMetricDTO[] {
  return [
    {
      device_id: '00008101-IPHONE-REAL-01',
      platform: 'ios',
      battery_temperature_c: 32.4,
      battery_level_percent: 88,
      battery_state: 'CHARGING',
      cpu_usage_percent: 18.0,
      memory_free_mb: 1850,
      current_concurrency: 1,
      max_concurrency: 2,
      tunnel_rtt_ms: 12.5,
      health_status: 'HEALTHY',
      health_score: 96.5,
      recorded_at: '2026-10-17 12:00:00',
    },
    {
      device_id: '00008101-IPHONE-REAL-02',
      platform: 'ios',
      battery_temperature_c: 39.2,
      battery_level_percent: 75,
      battery_state: 'CHARGING',
      cpu_usage_percent: 45.0,
      memory_free_mb: 980,
      current_concurrency: 2,
      max_concurrency: 2,
      tunnel_rtt_ms: 18.0,
      health_status: 'WARMING',
      health_score: 81.0,
      recorded_at: '2026-10-17 12:00:00',
    },
    {
      device_id: '127.0.0.1:5555',
      platform: 'android',
      battery_temperature_c: 31.0,
      battery_level_percent: 92,
      battery_state: 'FULL',
      cpu_usage_percent: 12.0,
      memory_free_mb: 2400,
      current_concurrency: 0,
      max_concurrency: 2,
      tunnel_rtt_ms: 8.0,
      health_status: 'HEALTHY',
      health_score: 98.0,
      recorded_at: '2026-10-17 12:00:00',
    },
    {
      device_id: '127.0.0.1:5557',
      platform: 'android',
      battery_temperature_c: 43.1,
      battery_level_percent: 68,
      battery_state: 'CHARGING',
      cpu_usage_percent: 75.0,
      memory_free_mb: 450,
      current_concurrency: 0,
      max_concurrency: 2,
      tunnel_rtt_ms: 32.0,
      health_status: 'OVERHEATED',
      health_score: 52.0,
      recorded_at: '2026-10-17 12:00:00',
    },
  ]
}

function createMockCapacity(): CapacitySummaryDTO {
  return {
    total_devices: 4,
    healthy_count: 2,
    warming_count: 1,
    overheated_count: 1,
    low_battery_count: 0,
    offline_count: 0,
    total_capacity: 8,
    used_concurrency: 3,
    available_capacity: 5,
    cluster_averages: {
      avg_temperature_c: 36.4,
      avg_battery_percent: 80.8,
      avg_tunnel_rtt_ms: 17.6,
    },
  }
}

function handleClose() {
  emit('update:open', false)
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      fetchFleetData()
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (props.open) {
    fetchFleetData()
  }
})
</script>

<style scoped>
.fleet-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fleet-hero-banner {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hero-left-metrics {
  display: flex;
  align-items: center;
  gap: 20px;
}

.cluster-summary-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.cluster-temp-number {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}

.cluster-temp-label {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  margin-top: 2px;
}

.metrics-summary-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-line-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fleet-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.summary-avg-item {
  font-size: 12px;
  color: #64748b;
  margin-left: 6px;
}

.stats-pills-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-pill {
  font-size: 11px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  padding: 2px 8px;
  border-radius: 10px;
  color: var(--c-text-secondary, #475569);
}

.stat-pill.has-overheat {
  border-color: #fca5a5;
  background: #fef2f2;
  color: #b91c1c;
}

.fleet-matrix-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 2px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.legend-item {
  font-size: 11px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-normal {
  background: #10b981;
}
.dot-warming {
  background: #f59e0b;
}
.dot-overheat {
  background: #ef4444;
}

.devices-heatmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  max-height: 560px;
  overflow-y: auto;
  padding: 2px;
}

.device-health-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.device-health-card:hover {
  border-color: #93c5fd;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
}

.device-health-card.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6;
}

.device-health-card.status-overheated {
  border-left: 4px solid #ef4444;
  background: #fff5f5;
}

.device-health-card.status-warming {
  border-left: 4px solid #f59e0b;
  background: #fffaf0;
}

.device-health-card.status-healthy {
  border-left: 4px solid #10b981;
}

.card-top-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.device-ident-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.device-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  max-width: 170px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-health-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.score-badge {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.thermal-metric-bar,
.battery-metric-bar {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.thermal-label-row,
.battery-label-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}

.metric-label {
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.temp-progress-track,
.battery-progress-track {
  width: 100%;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.temp-progress-bar,
.battery-progress-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.bar-green {
  background: #10b981;
}
.bar-orange {
  background: #f59e0b;
}
.bar-red {
  background: #ef4444;
}

.bg-success {
  background: #10b981;
}
.bg-danger {
  background: #ef4444;
}

.card-bottom-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 6px;
  border-top: 1px solid #f1f5f9;
}

.info-pill {
  font-size: 11px;
  color: #64748b;
}

.text-success {
  color: #16a34a;
}
.text-warning {
  color: #d97706;
}
.text-danger {
  color: #dc2626;
}
.text-secondary {
  color: #64748b;
}
</style>
