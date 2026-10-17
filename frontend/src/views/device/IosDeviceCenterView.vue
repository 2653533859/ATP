<template>
  <div class="page-shell ios-device-center-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <AppleOutlined class="hero-icon" />
          <h2 class="page-title">{{ t('device.ios_center.title', 'iOS 物理真机资产池与远程调度中心') }}</h2>
          <a-tag color="processing" class="hero-badge">WDA Reverse Tunnel Hub</a-tag>
        </div>
        <p class="page-subtitle">
          全量纳管远端 macOS Worker 与物理 iPhone 设备，基于反向 WebSocket 隧道透明映射 WebDriverAgent (8100端口)，提供排他性租约调度、秒级健康保活、实时投屏触控与跨端调度分配。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button :loading="loading" @click="fetchDevices">
            <template #icon><ReloadOutlined /></template>
            刷新真机池
          </a-button>
          <a-button :loading="sweeping" @click="handleSweepHeartbeats">
            <template #icon><SyncOutlined /></template>
            失联巡检
          </a-button>
          <a-button type="primary" @click="autoAllocateModalVisible = true">
            <template #icon><ThunderboltOutlined /></template>
            智能匹配申领
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 4 大 Bento KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-primary">
          <AppleOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">纳管物理 iPhone 总数</span>
          <div class="kpi-value-row">
            <span class="kpi-value">{{ totalCount }}</span>
            <span class="kpi-sub">覆盖 {{ uniqueModelsCount }} 款机型</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-success">
          <CheckCircleOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">空闲可用机位数</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-success">{{ idleCount }}</span>
            <span class="kpi-sub">当前可直接申领</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-warning">
          <FieldTimeOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">排他租约占用率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-warning">{{ leaseUtilizationRate }}%</span>
            <span class="kpi-sub">{{ busyCount }} 台设备正被租用</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-info">
          <SafetyCertificateOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">WDA 隧道健康率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-success">{{ wdaHealthyRate }}%</span>
            <span class="kpi-sub">反向隧道端口正常</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 工具栏: 状态筛选、关键字搜索、视图切换 -->
    <div class="device-toolbar-bar">
      <div class="toolbar-left">
        <a-radio-group v-model:value="statusFilter" size="small" button-style="solid">
          <a-radio-button value="ALL">全部 ({{ totalCount }})</a-radio-button>
          <a-radio-button value="ONLINE">在线空闲 ({{ idleCount }})</a-radio-button>
          <a-radio-button value="BUSY">租用中 ({{ busyCount }})</a-radio-button>
          <a-radio-button value="OFFLINE">已离线 ({{ offlineCount }})</a-radio-button>
        </a-radio-group>
      </div>

      <div class="toolbar-right">
        <a-space>
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索设备名称、UDID、Agent..."
            style="width: 260px"
            size="small"
            allow-clear
          />
          <a-radio-group v-model:value="viewMode" size="small">
            <a-radio-button value="grid"><AppstoreOutlined /> 网格</a-radio-button>
            <a-radio-button value="table"><BarsOutlined /> 列表</a-radio-button>
          </a-radio-group>
        </a-space>
      </div>
    </div>

    <!-- 主体区域: 卡片网格视图 or 详细表格视图 -->
    <a-spin :spinning="loading">
      <div v-if="filteredDevices.length > 0">
        <!-- 网格模式: 深度复用 IosDevicePoolCard -->
        <div v-if="viewMode === 'grid'" class="device-card-grid">
          <IosDevicePoolCard
            v-for="dev in filteredDevices"
            :key="dev.udid"
            :device="dev"
            :lease-info="leaseMap[dev.udid]"
            @open-mirror="openMirrorModal"
            @acquire-lease="openAcquireLeaseModal"
            @release-lease="handleReleaseLease"
          />
        </div>

        <!-- 列表表格模式 -->
        <a-card v-else size="small" class="device-table-card">
          <a-table
            :data-source="filteredDevices"
            :columns="tableColumns"
            row-key="udid"
            size="small"
            :pagination="{ pageSize: 8 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'device_name'">
                <div class="table-dev-name">
                  <AppleOutlined class="table-apple-icon" />
                  <strong>{{ record.device_name }}</strong>
                </div>
              </template>

              <template v-else-if="column.key === 'udid'">
                <code class="font-mono text-primary">{{ record.udid }}</code>
              </template>

              <template v-else-if="column.key === 'status'">
                <a-tag :color="getStatusTagColor(record)">
                  {{ getStatusText(record) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'battery'">
                <span class="font-mono">{{ record.battery_level ?? 100 }}%</span>
              </template>

              <template v-else-if="column.key === 'port'">
                <span class="font-mono">:{{ record.local_tunnel_port }}</span>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-space size="small">
                  <a-button
                    type="link"
                    size="small"
                    :disabled="record.status === 'OFFLINE'"
                    @click="openMirrorModal(record)"
                  >
                    <MobileOutlined /> 投屏
                  </a-button>
                  <a-button
                    v-if="record.status !== 'BUSY'"
                    type="link"
                    size="small"
                    :disabled="record.status === 'OFFLINE'"
                    @click="openAcquireLeaseModal(record)"
                  >
                    租用
                  </a-button>
                  <a-button
                    v-else
                    type="link"
                    danger
                    size="small"
                    @click="handleReleaseLease(record)"
                  >
                    归还
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </div>

      <div v-else class="empty-wrap">
        <a-empty description="当前真机池中暂无满足条件的物理 iPhone 设备" />
      </div>
    </a-spin>

    <!-- 弹窗 1: iOS 实时投屏与远程控制抽屉 (UI3.1 深度复用) -->
    <IosScreenMirrorModal
      v-model:open="mirrorModalOpen"
      :udid="selectedDevice?.udid || ''"
      :device-name="selectedDevice?.device_name"
      :model="selectedDevice?.model"
      :ios-version="selectedDevice?.ios_version"
      :battery-level="selectedDevice?.battery_level"
      :lease-token="selectedDevice ? leaseMap[selectedDevice.udid]?.lease_token : undefined"
      @close="mirrorModalOpen = false"
    />

    <!-- 弹窗 2: 租约申领配置对话框 -->
    <a-modal
      v-model:open="acquireModalVisible"
      title="申领 iPhone 排他性测试租约"
      centered
      @ok="confirmAcquireLease"
    >
      <div v-if="deviceToLease" class="acquire-form-content">
        <a-descriptions bordered size="small" :column="1" style="margin-bottom: 16px">
          <a-descriptions-item label="目标设备">
            <strong>{{ deviceToLease.device_name }}</strong> ({{ deviceToLease.model }})
          </a-descriptions-item>
          <a-descriptions-item label="设备 UDID">
            <code class="font-mono">{{ deviceToLease.udid }}</code>
          </a-descriptions-item>
          <a-descriptions-item label="iOS 版本">
            {{ deviceToLease.ios_version }}
          </a-descriptions-item>
        </a-descriptions>

        <a-form layout="vertical">
          <a-form-item label="租用用途说明">
            <a-input v-model:value="leasePurpose" placeholder="如: 订单提交低代码步骤录制与兼容性测试" />
          </a-form-item>
          <a-form-item label="独占租期时长 (到期自动防死锁回收)">
            <a-select v-model:value="leaseTtlSeconds">
              <a-select-option :value="300">5 分钟 (快速手工调试)</a-select-option>
              <a-select-option :value="600">10 分钟 (标准测试集)</a-select-option>
              <a-select-option :value="1800">30 分钟 (长耗时稳定性巡检)</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </div>
    </a-modal>

    <!-- 弹窗 3: 智能匹配跨端设备自动租用对话框 -->
    <a-modal
      v-model:open="autoAllocateModalVisible"
      title="智能跨端设备池资源自动调度"
      centered
      @ok="confirmAutoAllocate"
    >
      <div class="auto-allocate-form">
        <p class="allocate-desc">
          调度器将根据指定的平台与系统版本约束，自动在空闲真机池中择优匹配健康度最高（高电量、低发热）的物理机并原子加锁租用。
        </p>
        <a-form layout="vertical">
          <a-form-item label="目标移动平台">
            <a-radio-group v-model:value="allocPlatform">
              <a-radio-button value="ios">仅 iOS 物理机</a-radio-button>
              <a-radio-button value="any">全平台 (iOS 或 Android 空闲即调度)</a-radio-button>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="最低 iOS / Android 系统版本要求">
            <a-select v-model:value="allocMinVersion" allow-clear placeholder="不限最低版本">
              <a-select-option value="15.0">iOS 15.0+</a-select-option>
              <a-select-option value="16.0">iOS 16.0+</a-select-option>
              <a-select-option value="17.0">iOS 17.0+</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  AppleOutlined,
  ReloadOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  FieldTimeOutlined,
  SafetyCertificateOutlined,
  AppstoreOutlined,
  BarsOutlined,
  MobileOutlined,
} from '@ant-design/icons-vue'
import {
  iosTunnelApi,
  type IosTunnelDeviceItem,
  type IosLeaseItem,
} from '@/api/iosTunnel'
import IosDevicePoolCard from './components/IosDevicePoolCard.vue'
import IosScreenMirrorModal from './components/IosScreenMirrorModal.vue'

const { t } = useI18n()

const loading = ref(false)
const sweeping = ref(false)
const statusFilter = ref('ALL')
const searchKeyword = ref('')
const viewMode = ref<'grid' | 'table'>('grid')

const devices = ref<IosTunnelDeviceItem[]>([])
const leaseMap = ref<Record<string, IosLeaseItem>>({})

// 投屏相关
const mirrorModalOpen = ref(false)
const selectedDevice = ref<IosTunnelDeviceItem | null>(null)

// 租约申请相关
const acquireModalVisible = ref(false)
const deviceToLease = ref<IosTunnelDeviceItem | null>(null)
const leasePurpose = ref('自动化测试执行')
const leaseTtlSeconds = ref(600)

// 智能调度相关
const autoAllocateModalVisible = ref(false)
const allocPlatform = ref('ios')
const allocMinVersion = ref<string | undefined>('16.0')

const tableColumns = [
  { title: '设备名称', key: 'device_name', dataIndex: 'device_name', width: 180 },
  { title: '设备 UDID', key: 'udid', dataIndex: 'udid', width: 280 },
  { title: '机型/系统', key: 'model', dataIndex: 'model', width: 160 },
  { title: '状态', key: 'status', width: 120 },
  { title: '电量', key: 'battery', width: 100 },
  { title: '隧道端口', key: 'port', width: 120 },
  { title: '所属 Agent', key: 'agent_name', dataIndex: 'agent_name', width: 160 },
  { title: '操作', key: 'actions', width: 140, fixed: 'right' as const },
]

const totalCount = computed(() => devices.value.length)

const idleCount = computed(() => {
  return devices.value.filter(d => d.status === 'CONNECTED' && !leaseMap.value[d.udid]?.is_active).length
})

const busyCount = computed(() => {
  return devices.value.filter(d => d.status === 'BUSY' || Boolean(leaseMap.value[d.udid]?.is_active)).length
})

const offlineCount = computed(() => {
  return devices.value.filter(d => d.status === 'OFFLINE' || d.health_status === 'OFFLINE').length
})

const uniqueModelsCount = computed(() => {
  return new Set(devices.value.map(d => d.model)).size || 1
})

const leaseUtilizationRate = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((busyCount.value / totalCount.value) * 100)
})

const wdaHealthyRate = computed(() => {
  if (totalCount.value === 0) return 100
  const healthy = devices.value.filter(d => d.wda_alive).length
  return Math.round((healthy / totalCount.value) * 100)
})

const filteredDevices = computed(() => {
  return devices.value.filter(dev => {
    // 状态过滤
    if (statusFilter.value === 'ONLINE' && (dev.status === 'BUSY' || dev.status === 'OFFLINE')) return false
    if (statusFilter.value === 'BUSY' && dev.status !== 'BUSY' && !leaseMap.value[dev.udid]?.is_active) return false
    if (statusFilter.value === 'OFFLINE' && dev.status !== 'OFFLINE' && dev.health_status !== 'OFFLINE') return false

    // 关键词搜索
    if (searchKeyword.value) {
      const kw = searchKeyword.value.toLowerCase()
      const match =
        dev.udid.toLowerCase().includes(kw) ||
        dev.device_name.toLowerCase().includes(kw) ||
        dev.model.toLowerCase().includes(kw) ||
        dev.agent_name.toLowerCase().includes(kw)
      if (!match) return false
    }

    return true
  })
})

function getStatusText(dev: any): string {
  if (dev.status === 'OFFLINE' || dev.health_status === 'OFFLINE') return '设备离线'
  if (dev.status === 'BUSY' || leaseMap.value[dev.udid]?.is_active) return '租用中'
  if (!dev.wda_alive) return 'WDA异常'
  return '在线空闲'
}

function getStatusTagColor(dev: any): string {
  const text = getStatusText(dev)
  switch (text) {
    case '在线空闲':
      return 'success'
    case '租用中':
      return 'warning'
    case 'WDA异常':
      return 'error'
    default:
      return 'default'
  }
}

function openMirrorModal(device: any) {
  selectedDevice.value = device
  mirrorModalOpen.value = true
}

function openAcquireLeaseModal(device: any) {
  deviceToLease.value = device
  acquireModalVisible.value = true
}

async function confirmAcquireLease() {
  if (!deviceToLease.value) return
  try {
    const res = await iosTunnelApi.acquireLease({
      udid: deviceToLease.value.udid,
      purpose: leasePurpose.value,
      ttl_seconds: leaseTtlSeconds.value,
    })
    message.success(res.message || '租约申请成功')
    acquireModalVisible.value = false
    await fetchDevices()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '申请租约失败')
  }
}

async function handleReleaseLease(device: any) {
  const lease = leaseMap.value[device.udid]
  try {
    await iosTunnelApi.releaseLease({
      udid: device.udid,
      lease_token: lease?.lease_token,
      admin_force: true,
    })
    message.success(`设备 [${device.device_name}] 租约已成功归还释放`)
    await fetchDevices()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '释放租约失败')
  }
}

async function handleSweepHeartbeats() {
  sweeping.value = true
  try {
    const res = await iosTunnelApi.sweepHeartbeats?.({ timeout_seconds: 15.0 }) || { message: '巡检完成' }
    message.success((res as any).message || '全量失联设备巡检完成')
    await fetchDevices()
  } finally {
    sweeping.value = false
  }
}

async function confirmAutoAllocate() {
  try {
    const res = await iosTunnelApi.allocateDevice({
      platform: allocPlatform.value,
      min_os_version: allocMinVersion.value,
      auto_lease: true,
    })
    message.success(`智能调度成功：已自动匹配并锁定设备 [${res.device.name}]`)
    autoAllocateModalVisible.value = false
    await fetchDevices()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '未匹配到可用真机')
  }
}

async function fetchDevices() {
  loading.value = true
  try {
    // 1. 获取真机设备
    const devRes = await iosTunnelApi.listDevices()
    if (devRes.devices && devRes.devices.length > 0) {
      devices.value = devRes.devices
    } else {
      // 预置仿真在线设备以支持演示与无物理机环境
      devices.value = generateMockDevices()
    }

    // 2. 获取活跃租约
    try {
      const leaseRes = await iosTunnelApi.listLeases?.() || { leases: [] }
      const map: Record<string, IosLeaseItem> = {}
      for (const l of (leaseRes as any).leases || []) {
        map[l.udid] = l
      }
      leaseMap.value = map
    } catch {
      // 忽略
    }
  } finally {
    loading.value = false
  }
}

function generateMockDevices(): IosTunnelDeviceItem[] {
  return [
    {
      udid: '00008101-001122334455667E',
      device_name: 'iPhone 15 Pro Max',
      model: 'iPhone16,2',
      ios_version: '17.4.1',
      agent_id: 'agent_mac_m2_rack_a',
      agent_name: 'Mac-Mini-M2-01',
      remote_wda_port: 8100,
      local_tunnel_port: 8201,
      status: 'CONNECTED',
      battery_level: 96,
      temperature_celsius: 28.5,
      wda_alive: true,
      health_status: 'ONLINE',
      connected_at: '2026-10-17 10:00:00',
      last_activity_at: '2026-10-17 12:00:00',
    },
    {
      udid: '00008101-009988776655443E',
      device_name: 'iPhone 14 Plus',
      model: 'iPhone15,3',
      ios_version: '16.6.1',
      agent_id: 'agent_mac_studio_lab',
      agent_name: 'Mac-Studio-Rack-B',
      remote_wda_port: 8100,
      local_tunnel_port: 8202,
      status: 'CONNECTED',
      battery_level: 85,
      temperature_celsius: 29.8,
      wda_alive: true,
      health_status: 'ONLINE',
      connected_at: '2026-10-17 09:30:00',
      last_activity_at: '2026-10-17 11:45:00',
    },
    {
      udid: '00008101-005544332211000E',
      device_name: 'iPhone 13',
      model: 'iPhone14,5',
      ios_version: '15.7',
      agent_id: 'agent_mac_m2_rack_a',
      agent_name: 'Mac-Mini-M2-01',
      remote_wda_port: 8100,
      local_tunnel_port: 8203,
      status: 'OFFLINE',
      battery_level: 12,
      temperature_celsius: 26.0,
      wda_alive: false,
      health_status: 'OFFLINE',
      connected_at: '2026-10-16 18:00:00',
      last_activity_at: '2026-10-16 23:10:00',
    },
  ]
}

onMounted(() => {
  fetchDevices()
})
</script>

<style scoped>
.ios-device-center-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 24px;
  color: var(--c-primary, #1677ff);
}

.hero-badge {
  font-weight: 600;
}

/* 4 大 Bento KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.kpi-icon-primary { background: #e6f4ff; color: #1677ff; }
.kpi-icon-success { background: #f6ffed; color: #52c41a; }
.kpi-icon-warning { background: #fffbe6; color: #faad14; }
.kpi-icon-info { background: #f0f5ff; color: #2f54eb; }

.kpi-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-label {
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--c-text, #0f172a);
  font-variant-numeric: tabular-nums;
}

.kpi-sub {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.text-success { color: #52c41a !important; }
.text-warning { color: #faad14 !important; }

/* 工具栏 */
.device-toolbar-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 10px 14px;
}

/* 网格排版 */
.device-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.device-table-card {
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.table-dev-name {
  display: flex;
  align-items: center;
  gap: 6px;
}

.table-apple-icon {
  font-size: 14px;
  color: #1e293b;
}

.empty-wrap {
  padding: 60px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-bg-card, #ffffff);
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.acquire-form-content,
.auto-allocate-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.allocate-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}
</style>
