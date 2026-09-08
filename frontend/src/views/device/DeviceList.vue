<template>
  <div class="page-shell device-page">
    <!-- 顶部场景化上下文与二级导航条 (对齐参考图：首页 / APP 自动化 / 设备管理 + 二级功能Tab) -->
    <div class="prototype-context-bar">
      <div class="context-breadcrumb">
        <span class="crumb-link" @click="router.push('/dashboard')">首页</span>
        <span class="crumb-sep">/</span>
        <span class="crumb-link" @click="router.push('/mobile-special/workbench')">APP 自动化</span>
        <span class="crumb-sep">/</span>
        <span class="crumb-current">{{ t('device.title') }}</span>
      </div>

      <!-- APP 自动化 二级场景水平导航 -->
      <div class="subnav-tabs">
        <span class="subnav-tab" @click="router.push('/mobile-special/workbench')">APP 自动化</span>
        <span class="subnav-tab" @click="router.push('/mobile-special/workbench')">工作台</span>
        <span class="subnav-tab" @click="router.push('/cases')">用例库</span>
        <span class="subnav-tab" @click="router.push('/suites')">流程套件</span>
        <span class="subnav-tab" @click="router.push('/ios-assets')">资产中心</span>
        <span class="subnav-tab" @click="router.push('/apks')">应用包管理</span>
        <span class="subnav-tab active">设备管理</span>
        <span class="subnav-tab" @click="router.push('/mobile-special/reports')">执行结果</span>
      </div>
    </div>

    <!-- 页面标题与全局操作栏 -->
    <div class="page-header-row">
      <div class="header-titles">
        <h1 class="main-title">{{ t('device.title') }}</h1>
        <p class="main-subtitle">统一查看 Agent 托管设备，直接进入远程控制工作台。</p>
      </div>
      <div class="header-actions">
        <!-- 第一个按钮为 handleScan，保证既有测试 wrapper.findAll('button')[0] 行为一致 -->
        <a-tooltip title="刷新设备状态">
          <a-button class="action-icon-btn" :loading="scanning" @click="handleScan">
            <ReloadOutlined />
          </a-button>
        </a-tooltip>
        <a-button class="action-btn" :loading="scanning" @click="handleScan">
          <SyncOutlined /> 同步 ADB
        </a-button>
        <a-tooltip title="后端暂未提供批量指标采集能力">
          <a-button class="action-btn" disabled><ThunderboltOutlined /> 批量采集</a-button>
        </a-tooltip>
        <a-tooltip title="设备由在线 Agent 扫描并接入">
          <a-button type="primary" class="action-btn add-btn" disabled><PlusOutlined /> 添加设备</a-button>
        </a-tooltip>
        <div class="view-mode-toggle">
          <a-tooltip title="卡片矩阵视图">
            <button
              :class="['view-toggle-btn', { active: viewMode === 'card' }]"
              @click="viewMode = 'card'"
            >
              <AppstoreOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="数据表格视图">
            <button
              :class="['view-toggle-btn', { active: viewMode === 'table' }]"
              @click="viewMode = 'table'"
            >
              <BarsOutlined />
            </button>
          </a-tooltip>
        </div>
      </div>
    </div>

    <!-- Worker 状态与设备分组简报 -->
    <div class="worker-status-bar">
      <div class="worker-status-item">
        <span class="worker-label">{{ t('device.worker.title') }}:</span>
        <span v-if="workers.length" class="worker-online">
          {{ workers.map((worker) => worker.worker_id).join(', ') }} · {{ t('device.worker.online') }}
        </span>
        <span v-else class="worker-offline">{{ t('device.worker.offline') }}</span>
      </div>
      <div class="group-chips">
        <span class="group-label">设备组:</span>
        <a-space wrap size="small">
          <a-tag
            v-for="group in groups"
            :key="group.id"
            closable
            class="group-tag"
            @close.prevent="deleteGroup(group.id)"
            @click="openGroup(group)"
          >
            {{ group.name }} ({{ group.devices.length }})
          </a-tag>
          <a-button type="dashed" size="small" class="new-group-btn" @click="openGroup()">+ {{ t('device.groups.new') }}</a-button>
        </a-space>
      </div>
    </div>

    <!-- 状态胶囊统计过滤器 (参考图：全部 5 | 空闲 1 | 在线 0 | 已锁定 0 | 离线 4) -->
    <div class="status-pill-row">
      <div class="status-pills">
        <button
          :class="['status-pill', { active: activeStatusPill === 'all' }]"
          @click="setStatusPill('all')"
        >
          全部 <span class="pill-count">{{ devices.length }}</span>
        </button>
        <button
          :class="['status-pill', { active: activeStatusPill === 'online' }]"
          @click="setStatusPill('online')"
        >
          在线 <span class="pill-count">{{ deviceStats.online }}</span>
        </button>
        <button
          :class="['status-pill', { active: activeStatusPill === 'busy' }]"
          @click="setStatusPill('busy')"
        >
          已锁定 <span class="pill-count">{{ deviceStats.busy }}</span>
        </button>
        <button
          :class="['status-pill', { active: activeStatusPill === 'offline' }]"
          @click="setStatusPill('offline')"
        >
          离线 <span class="pill-count">{{ deviceStats.offline }}</span>
        </button>
      </div>
    </div>

    <!-- 多维属性过滤检索条 (搜索 + 平台/状态/品牌/系统版本 + 最近同步时间) -->
    <div class="filter-controls-row">
      <div class="filter-controls-left">
        <a-input-search
          v-model:value="keyword"
          placeholder="搜索设备 ID、型号或标签"
          allow-clear
          class="search-input-box"
        />
        <a-select
          v-model:value="statusFilter"
          placeholder="状态"
          allow-clear
          class="filter-select"
          @change="loadDevices"
        >
          <a-select-option value="online">{{ t('device.statuses.online') }}</a-select-option>
          <a-select-option value="offline">{{ t('device.statuses.offline') }}</a-select-option>
          <a-select-option value="busy">{{ t('device.statuses.busy') }}</a-select-option>
        </a-select>
        <a-select
          v-model:value="brandFilter"
          placeholder="品牌"
          allow-clear
          class="filter-select"
        >
          <a-select-option value="all">全部品牌</a-select-option>
          <a-select-option value="Xiaomi">小米 (Xiaomi)</a-select-option>
          <a-select-option value="OPPO">OPPO</a-select-option>
          <a-select-option value="vivo">vivo</a-select-option>
          <a-select-option value="Huawei">华为 (Huawei)</a-select-option>
          <a-select-option value="Samsung">三星 (Samsung)</a-select-option>
          <a-select-option value="Google">Google</a-select-option>
          <a-select-option value="Apple">Apple</a-select-option>
        </a-select>
        <a-select
          v-model:value="versionFilter"
          placeholder="系统版本"
          allow-clear
          class="filter-select"
        >
          <a-select-option value="all">全部版本</a-select-option>
          <a-select-option value="15">Android 15</a-select-option>
          <a-select-option value="14">Android 14</a-select-option>
          <a-select-option value="13">Android 13</a-select-option>
          <a-select-option value="10">Android 10</a-select-option>
        </a-select>
      </div>
      <div class="filter-controls-right">
        <span class="sync-time-badge">最近同步: {{ lastSyncTime }}</span>
      </div>
    </div>

    <!-- 视图 1：高保真真机硬件卡片矩阵 (核心原型展示，对齐参考图) -->
    <div v-show="viewMode === 'card'" class="device-matrix-grid">
      <div
        v-for="device in displayDevices"
        :key="device.id"
        class="device-card-item"
        :class="[`status-${device.status}`]"
      >
        <!-- 卡片顶栏：型号、品牌、ADB与状态标签 -->
        <div class="card-head">
          <div class="device-naming">
            <h3 class="device-model-title" :title="device.model || device.name || device.serial">
              {{ device.model || device.name || device.serial }}
            </h3>
            <span class="device-brand-subtitle">
              {{ device.brand ? device.brand : '品牌未上报' }}
            </span>
          </div>
          <div class="card-tags">
            <span class="protocol-tag">ADB</span>
            <span :class="['status-chip', `chip-${device.status}`]">
              {{ getDeviceStatusText(device.status) }}
            </span>
          </div>
        </div>

        <!-- 卡片主体：左拟真手机外壳 + 桌面预览，右规格参数面板 -->
        <div class="card-body">
          <!-- 拟真手机外壳 -->
          <div class="phone-mockup" :class="[`phone-${device.status}`]">
            <div class="phone-top-notch">
              <div class="phone-camera-dot"></div>
              <div class="phone-speaker-bar"></div>
            </div>

            <!-- 手机屏幕 -->
            <div class="phone-screen">
              <template v-if="device.status === 'online'">
                <div class="screen-live">
                  <div class="screen-status-bar">
                    <span class="status-time">ADB</span>
                    <div class="status-icons">
                      <span class="status-wifi">●</span>
                    </div>
                  </div>
                  <div class="screen-app-grid">
                    <div class="mini-app app-1"></div>
                    <div class="mini-app app-2"></div>
                    <div class="mini-app app-3"></div>
                    <div class="mini-app app-4"></div>
                    <div class="mini-app app-5"></div>
                    <div class="mini-app app-6"></div>
                  </div>
                  <div class="screen-dock">
                    <div class="dock-app dock-phone"></div>
                    <div class="dock-app dock-msg"></div>
                    <div class="dock-app dock-web"></div>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="screen-offline">
                  <div class="offline-icon-wrap">
                    <MobileOutlined class="offline-phone-icon" />
                  </div>
                  <span class="offline-text">设备离线</span>
                </div>
              </template>
            </div>

            <div class="phone-bottom-bar"></div>
          </div>

          <!-- 右侧设备参数属性面板 -->
          <div class="device-specs-sheet">
            <div class="spec-row">
              <span class="spec-label">系统</span>
              <span class="spec-val">Android {{ device.os_version || '--' }}</span>
            </div>
            <div class="spec-row">
              <span class="spec-label">电量</span>
              <span class="spec-val">
                --
              </span>
            </div>
            <div class="spec-row">
              <span class="spec-label">分辨率</span>
              <span class="spec-val">{{ device.resolution || '--' }}</span>
            </div>
            <div class="spec-row">
              <span class="spec-label">最后使用人</span>
              <span class="spec-val user-val">--</span>
            </div>
            <div class="spec-row">
              <span class="spec-label">Agent</span>
              <span class="spec-val agent-val">--</span>
            </div>
            <div class="spec-row">
              <span class="spec-label">备注</span>
              <span class="spec-val remark-val">{{ device.description || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- 卡片底栏：快捷操作链接 + 全宽 "立即使用" CTA 按钮 -->
        <div class="card-footer-actions">
          <div class="minor-actions">
            <a-button type="link" size="small" class="footer-link" @click="openEdit(device)">详情</a-button>
            <a-tooltip title="后端暂未提供远程重启能力">
              <a-button type="link" size="small" class="footer-link" disabled>重启</a-button>
            </a-tooltip>
            <a-popconfirm :title="t('device.confirm_delete')" @confirm="handleDelete(device.id)">
              <a-button type="link" size="small" danger class="footer-link">删除</a-button>
            </a-popconfirm>
          </div>
          <button
            :class="['cta-use-btn', { disabled: device.status === 'offline' }]"
            :disabled="device.status === 'offline'"
            @click="device.status !== 'offline' ? openMirror(device) : null"
          >
            立即使用
          </button>
        </div>
      </div>

      <div v-if="displayDevices.length === 0" class="empty-matrix-card">
        <a-empty :description="t('device.empty')" />
      </div>
    </div>

    <!-- 视图 2：数据表格视图 (并保留在 DOM 保证现有自动化与 TableStub 测试全通过) -->
    <div v-show="viewMode === 'table'" class="table-card-wrap">
      <a-table
        :columns="columns"
        :data-source="filteredDevices"
        :loading="loading"
        row-key="id"
        size="middle"
        :pagination="false"
        :locale="{ emptyText: t('device.empty') }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-badge
              :status="statusBadge(record.status)"
              :text="statusLabel(record.status)"
            />
          </template>

          <template v-if="column.key === 'device_info'">
            <div>{{ record.brand }} {{ record.model }}</div>
            <div style="color: var(--c-text-tertiary); font-size: 12px">{{ record.serial }}</div>
          </template>

          <template v-if="column.key === 'os'">
            Android {{ record.os_version }}
            <span v-if="record.sdk_version" style="color: var(--c-text-tertiary)">(API {{ record.sdk_version }})</span>
          </template>

          <template v-if="column.key === 'last_seen'">
            {{ record.last_seen_at ? formatTime(record.last_seen_at) : '-' }}
          </template>

          <template v-if="column.key === 'action'">
            <a-space>
              <a-button
                v-if="record.status === 'online'"
                type="link"
                size="small"
                @click="openMirror(asDevice(record))"
              >
                <EyeOutlined /> {{ t('device.mirror') }}
              </a-button>
              <a-button type="link" size="small" @click="openEdit(asDevice(record))">{{ t('common.edit') }}</a-button>
              <a-popconfirm :title="t('device.confirm_delete')" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 编辑设备弹窗 -->
    <a-modal
      v-model:open="editOpen"
      :title="t('device.edit')"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('device.fields.name')">
          <a-input v-model:value="editForm.name" :placeholder="t('device.placeholders.name')" />
        </a-form-item>
        <a-form-item :label="t('device.fields.description')">
          <a-textarea v-model:value="editForm.description" :placeholder="t('device.placeholders.description')" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分组弹窗 -->
    <a-modal v-model:open="groupOpen" :title="t('device.groups.edit')" :confirm-loading="groupSaving" @ok="saveGroup">
      <a-form layout="vertical">
        <a-form-item :label="t('device.groups.name')" required><a-input v-model:value="groupForm.name" /></a-form-item>
        <a-form-item :label="t('device.groups.members')">
          <a-select v-model:value="groupForm.device_ids" mode="multiple" style="width: 100%">
            <a-select-option v-for="device in devices" :key="device.id" :value="device.id">{{ device.name || device.model || device.serial }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('device.fields.description')"><a-textarea v-model:value="groupForm.description" :rows="3" /></a-form-item>
      </a-form>
    </a-modal>

    <!-- 屏幕镜像与远程控制工作台弹窗 -->
    <a-modal
      v-model:open="mirrorOpen"
      :title="t('device.mirror_title', { name: `${mirrorDevice?.brand ?? ''} ${mirrorDevice?.model ?? ''}`.trim() })"
      width="440px"
      :footer="null"
      :destroy-on-close="true"
      @cancel="closeMirror"
    >
      <div class="mirror-container">
        <img
          v-if="mirrorSrc"
          :src="mirrorSrc"
          :alt="t('device.screen_alt')"
          class="mirror-img"
          @error="onMirrorError"
        />
        <div v-else class="mirror-placeholder">
          <a-spin :tip="t('device.connecting')" />
        </div>
      </div>
      <div class="mirror-footer">
        <a-button size="small" @click="() => refreshMirror()">
          <ReloadOutlined /> {{ t('device.refresh_screenshot') }}
        </a-button>
        <span style="color: var(--c-text-tertiary); font-size: 12px">{{ t('device.auto_refresh') }}</span>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  EyeOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  AppstoreOutlined,
  BarsOutlined,
  MobileOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { deviceApi } from '@/api'
import type { AndroidWorkerItem, DeviceGroupItem, DeviceItem, DeviceStatus } from '@/api'

const asDevice = (record: unknown) => record as DeviceItem

const router = useRouter()
const { t } = useI18n()
const devices = ref<DeviceItem[]>([])
const workers = ref<AndroidWorkerItem[]>([])
const groups = ref<DeviceGroupItem[]>([])
const loading = ref(false)
const scanning = ref(false)
const statusFilter = ref<string | undefined>(undefined)
const keyword = ref('')

// 原型交互状态
const viewMode = ref<'card' | 'table'>('card')
const activeStatusPill = ref<'all' | 'online' | 'busy' | 'offline'>('all')
const brandFilter = ref<string | undefined>(undefined)
const versionFilter = ref<string | undefined>(undefined)
const lastSyncTime = ref('--')

const editOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({ name: '', description: '' })

const groupOpen = ref(false)
const groupSaving = ref(false)
const editingGroupId = ref<number | null>(null)
const groupForm = ref({ name: '', description: '', device_ids: [] as number[] })

const mirrorOpen = ref(false)
const mirrorDevice = ref<DeviceItem | null>(null)
const mirrorSrc = ref<string | null>(null)
let mirrorTimer: ReturnType<typeof setInterval> | null = null
let mirrorObjectUrl: string | null = null
let mirrorRefreshing = false
let mirrorSession = 0

const columns = computed(() => [
  { title: t('device.columns.device_info'), key: 'device_info', width: 240 },
  { title: t('device.columns.status'), key: 'status', width: 100 },
  { title: t('device.columns.os'), key: 'os', width: 200 },
  { title: t('device.columns.resolution'), dataIndex: 'resolution', key: 'resolution', width: 120 },
  { title: t('device.columns.last_seen'), key: 'last_seen', width: 170 },
  { title: t('device.columns.action'), key: 'action', width: 180, fixed: 'right' as const },
])

const filteredDevices = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return devices.value
  return devices.value.filter((device) =>
    [device.name ?? '', device.brand ?? '', device.model ?? '', device.serial ?? '', device.os_version ?? '', device.resolution ?? '']
      .some((value) => value.toLowerCase().includes(needle)),
  )
})

const deviceStats = computed(() => ({
  online: devices.value.filter((device) => device.status === 'online').length,
  busy: devices.value.filter((device) => device.status === 'busy').length,
  offline: devices.value.filter((device) => device.status === 'offline').length,
}))

const displayDevices = computed(() => {
  let list = filteredDevices.value
  if (activeStatusPill.value === 'online') {
    list = list.filter((d) => d.status === 'online')
  } else if (activeStatusPill.value === 'busy') {
    list = list.filter((d) => d.status === 'busy')
  } else if (activeStatusPill.value === 'offline') {
    list = list.filter((d) => d.status === 'offline')
  }

  if (brandFilter.value && brandFilter.value !== 'all') {
    list = list.filter((d) => (d.brand || '').toLowerCase().includes(brandFilter.value!.toLowerCase()))
  }

  if (versionFilter.value && versionFilter.value !== 'all') {
    list = list.filter((d) => (d.os_version || '').includes(versionFilter.value!))
  }
  return list
})

function setStatusPill(status: 'all' | 'online' | 'busy' | 'offline') {
  activeStatusPill.value = status
}

function getDeviceStatusText(s: DeviceStatus) {
  if (s === 'online') return '空闲'
  if (s === 'busy') return '使用中'
  return '离线'
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

function statusBadge(s: DeviceStatus): 'success' | 'default' | 'processing' {
  const map: Record<string, 'success' | 'default' | 'processing'> = {
    online: 'success', offline: 'default', busy: 'processing',
  }
  return map[s] ?? 'default'
}

function statusLabel(s: DeviceStatus) {
  return {
    online: t('device.statuses.online'),
    offline: t('device.statuses.offline'),
    busy: t('device.statuses.busy'),
  }[s] ?? s
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ')
}

async function loadDevices() {
  loading.value = true
  try {
    devices.value = await deviceApi.list(
      statusFilter.value ? { status_filter: statusFilter.value } : undefined,
    )
    if (devices.value.length === 0 && import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      devices.value = getPrototypeMockDevices()
    }
  } catch (e: unknown) {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA !== 'true') {
      message.error(errorMessage(e, t('device.msg.load_failed')))
    }
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      devices.value = getPrototypeMockDevices()
    }
  } finally {
    loading.value = false
  }
}
function getPrototypeMockDevices(): DeviceItem[] {
  return [
    {
      id: 1,
      serial: 'PJX110-001',
      model: 'PJX110',
      brand: '',
      os_version: '15',
      resolution: '1080 × 2376',
      status: 'online',
      description: '',
      created_at: '2026-09-07T10:00:00Z',
      updated_at: '2026-09-07T14:52:00Z',
    },
    {
      id: 2,
      serial: 'MIX3-002',
      model: 'MIX 3',
      brand: '',
      os_version: '10',
      resolution: '1080 × 2340',
      status: 'offline',
      description: '',
      created_at: '2026-09-07T10:00:00Z',
      updated_at: '2026-09-07T14:52:00Z',
    },
    {
      id: 3,
      serial: 'PAFM00-003',
      model: 'PAFM00',
      brand: '',
      os_version: '10',
      resolution: '1080 × 2340',
      status: 'offline',
      description: '',
      created_at: '2026-09-07T10:00:00Z',
      updated_at: '2026-09-07T14:52:00Z',
    },
    {
      id: 4,
      serial: 'V1805A-004',
      model: 'vivo NEX A',
      brand: '',
      os_version: '10',
      resolution: '1080 × 2316',
      status: 'offline',
      description: '',
      created_at: '2026-09-07T10:00:00Z',
      updated_at: '2026-09-07T14:52:00Z',
    },
    {
      id: 5,
      serial: 'V1805A-005',
      model: 'vivo NEX A',
      brand: '',
      os_version: '10',
      resolution: '1080 × 2316',
      status: 'offline',
      description: '',
      created_at: '2026-09-07T10:00:00Z',
      updated_at: '2026-09-07T14:52:00Z',
    },
  ]
}

async function loadWorkers() {
  try {
    workers.value = await deviceApi.workers()
  } catch (_e) {
    workers.value = []
  }
}

async function loadGroups() {
  try { groups.value = await deviceApi.groups() } catch { groups.value = [] }
}

function openGroup(group?: DeviceGroupItem) {
  editingGroupId.value = group?.id ?? null
  groupForm.value = { name: group?.name ?? '', description: group?.description ?? '', device_ids: group?.devices.map((item) => item.id) ?? [] }
  groupOpen.value = true
}

async function saveGroup() {
  if (!groupForm.value.name.trim()) return message.warning(t('device.groups.name_required'))
  groupSaving.value = true
  try {
    if (editingGroupId.value) await deviceApi.updateGroup(editingGroupId.value, groupForm.value)
    else await deviceApi.createGroup(groupForm.value)
    groupOpen.value = false
    await loadGroups()
  } finally { groupSaving.value = false }
}

async function deleteGroup(id: number) { await deviceApi.deleteGroup(id); await loadGroups() }

async function handleScan() {
  scanning.value = true
  try {
    const result = await deviceApi.scan()
    devices.value = result.devices
    if (result.status === 'failed') {
      throw new Error(result.error || t('device.msg.scan_failed'))
    }
    if (result.status === 'queued' || result.status === 'running') {
      if (!result.scan_id) {
        throw new Error(t('device.msg.scan_pending'))
      }
      message.info(t('device.msg.scan_queued'))
      await waitForScan(result.scan_id)
    } else {
      message.success(t('device.msg.scan_success', { count: devices.value.length }))
      markSynced()
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.scan_failed')))
  } finally {
    scanning.value = false
  }
}

async function waitForScan(scanId: string) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < 30000) {
    await new Promise((resolve) => setTimeout(resolve, 500))
    const status = await deviceApi.scanStatus(scanId)
    if (status.status === 'completed') {
      devices.value = status.devices
      message.success(t('device.msg.scan_success', { count: status.devices.length }))
      markSynced()
      return
    }
    if (status.status === 'failed') {
      throw new Error(status.error || t('device.msg.scan_failed'))
    }
  }
  throw new Error(t('device.msg.scan_timeout'))
}

function markSynced() {
  const now = new Date()
  lastSyncTime.value = `${String(now.getMonth() + 1).padStart(2, '0')}/${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

function openEdit(device: DeviceItem) {
  editingId.value = device.id
  editForm.value = {
    name: device.name || '',
    description: device.description || '',
  }
  editOpen.value = true
}

async function handleSave() {
  if (!editingId.value) return
  saving.value = true
  try {
    await deviceApi.update(editingId.value, editForm.value)
    editOpen.value = false
    message.success(t('common.saved'))
    await loadDevices()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.update_failed')))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deviceApi.delete(id)
    message.success(t('common.deleted'))
    await loadDevices()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.delete_failed')))
  }
}

function openMirror(device: DeviceItem) {
  mirrorDevice.value = device
  mirrorOpen.value = true
  mirrorSession += 1
  refreshMirror(mirrorSession)
  startMirrorPolling()
}

function closeMirror() {
  mirrorOpen.value = false
  mirrorDevice.value = null
  mirrorSession += 1
  stopMirrorPolling()
  revokeMirrorUrl()
}

function revokeMirrorUrl() {
  if (mirrorObjectUrl) {
    URL.revokeObjectURL(mirrorObjectUrl)
    mirrorObjectUrl = null
  }
  mirrorSrc.value = null
}

async function refreshMirror(session = mirrorSession) {
  if (!mirrorDevice.value || mirrorRefreshing || session !== mirrorSession) return
  mirrorRefreshing = true
  try {
    const blob = await deviceApi.screenshot(mirrorDevice.value.id)
    if (session !== mirrorSession) return
    const nextUrl = URL.createObjectURL(blob)
    const prevUrl = mirrorObjectUrl
    mirrorObjectUrl = nextUrl
    mirrorSrc.value = nextUrl
    if (prevUrl) URL.revokeObjectURL(prevUrl)
  } catch (_e) {
    // Keep the current screenshot visible on intermittent adb errors
  } finally {
    mirrorRefreshing = false
  }
}

function onMirrorError() {
  revokeMirrorUrl()
}

function startMirrorPolling() {
  stopMirrorPolling()
  const activeSession = mirrorSession
  mirrorTimer = setInterval(() => {
    refreshMirror(activeSession)
  }, 500)
}

function stopMirrorPolling() {
  if (mirrorTimer) {
    clearInterval(mirrorTimer)
    mirrorTimer = null
  }
}

onMounted(() => {
  loadDevices()
  loadWorkers()
  loadGroups()
})

onUnmounted(() => {
  stopMirrorPolling()
  revokeMirrorUrl()
})
</script>

<style scoped>
.device-page {
  display: flex;
  flex-direction: column;
  background: var(--c-bg-body);
  min-height: 100%;
  padding-bottom: 36px;
}

/* 顶部上下文与二级导航 */
.prototype-context-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: -8px -8px 16px -8px;
  padding: 12px 18px 0;
  background: var(--c-bg-elevated);
  border-bottom: 1px solid var(--c-border-subtle);
}

.context-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--c-text-secondary);
}

.crumb-link {
  color: var(--c-text-secondary);
  cursor: pointer;
  transition: color 0.15s;
}

.crumb-link:hover {
  color: var(--c-primary);
}

.crumb-sep {
  color: var(--c-text-tertiary);
}

.crumb-current {
  color: var(--c-text);
  font-weight: 600;
}

.project-selector-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-left: 12px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  color: var(--c-text);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.project-selector-pill:hover {
  background: var(--c-bg-muted);
}

.selector-arrow {
  font-size: 10px;
  color: var(--c-text-tertiary);
}

.subnav-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding-top: 4px;
}

.subnav-tab {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--c-text-secondary);
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition: all 0.15s;
}

.subnav-tab:hover {
  color: var(--c-primary);
}

.subnav-tab.active {
  color: var(--c-primary);
  font-weight: 600;
  border-bottom-color: var(--c-primary);
}

/* 页面标头与操作区 */
.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 16px;
}

.main-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--c-text);
  margin: 0;
  letter-spacing: -0.02em;
}

.main-subtitle {
  font-size: 13px;
  color: var(--c-text-secondary);
  margin: 4px 0 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.action-icon-btn {
  border-radius: 6px;
  color: var(--c-text-secondary);
}

.action-btn {
  border-radius: 6px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.add-btn {
  background: var(--c-primary);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
}

.view-mode-toggle {
  display: inline-flex;
  align-items: center;
  background: var(--c-bg-muted);
  padding: 2px;
  border-radius: 6px;
  margin-left: 4px;
}

.view-toggle-btn {
  background: transparent;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--c-text-secondary);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.view-toggle-btn.active {
  background: var(--c-bg-elevated);
  color: var(--c-text);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Worker 状态与分组简报 */
.worker-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 8px 12px;
  background: var(--c-bg-elevated);
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle);
  margin-bottom: 12px;
  font-size: 12px;
}

.worker-label, .group-label {
  color: var(--c-text-secondary);
  font-weight: 600;
  margin-right: 6px;
}

.worker-online {
  color: #16a34a;
  font-weight: 500;
}

.worker-offline {
  color: var(--c-text-tertiary);
}

.group-tag {
  cursor: pointer;
  border-radius: 4px;
}

.new-group-btn {
  font-size: 11px;
}

/* 状态胶囊筛选条 */
.status-pill-row {
  margin-bottom: 12px;
}

.status-pills {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  background: var(--c-bg-elevated);
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.16s ease;
}

.status-pill:hover {
  border-color: var(--c-border-strong);
  background: var(--c-bg-body);
}

.status-pill.active {
  background: var(--c-primary);
  color: #ffffff;
  border-color: var(--c-primary);
}

.pill-count {
  font-weight: 700;
  font-size: 11px;
  opacity: 0.85;
}

/* 多维过滤条 */
.filter-controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-controls-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.search-input-box {
  width: 250px;
}

.filter-select {
  width: 110px;
}

.sync-time-badge {
  font-size: 12px;
  color: var(--c-text-tertiary);
}

/* 真机卡片矩阵 (Device Matrix Grid) */
.device-matrix-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.device-card-item {
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.device-card-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
  border-color: var(--c-border-strong);
}

/* 卡片顶栏 */
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}

.device-naming {
  min-width: 0;
  flex: 1;
}

.device-model-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-text);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-brand-subtitle {
  font-size: 11px;
  color: var(--c-text-tertiary);
  margin-top: 2px;
  display: block;
}

.card-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.protocol-tag {
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 600;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.status-chip {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.chip-online {
  background: #dcfce7;
  color: #15803d;
}

.chip-busy {
  background: #ffedd5;
  color: #c2410c;
}

.chip-offline {
  background: #fee2e2;
  color: #b91c1c;
}

/* 卡片主体：手机外壳 + 属性面板 */
.card-body {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 14px;
}

/* 拟真手机外壳 Mockup */
.phone-mockup {
  width: 106px;
  height: 182px;
  border-radius: 20px;
  background: #0f172a;
  border: 3px solid #334155;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex-shrink: 0;
}

.phone-top-notch {
  height: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: #0f172a;
  z-index: 2;
}

.phone-camera-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #475569;
}

.phone-speaker-bar {
  width: 14px;
  height: 2px;
  border-radius: 2px;
  background: #475569;
}

.phone-bottom-bar {
  height: 6px;
  background: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
}

.phone-bottom-bar::after {
  content: '';
  width: 24px;
  height: 2px;
  border-radius: 2px;
  background: #475569;
}

.phone-screen {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* 在线屏幕桌面 */
.screen-live {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #1e3a8a, #0d9488 70%, #059669);
  padding: 4px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.screen-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 8px;
  color: #f8fafc;
  padding: 0 2px;
}

.status-icons {
  display: flex;
  gap: 3px;
  font-size: 7px;
}

.screen-app-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 5px;
  padding: 6px 3px;
}

.mini-app {
  height: 16px;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.app-1 { background: #38bdf8; }
.app-2 { background: #fb7185; }
.app-3 { background: #facc15; }
.app-4 { background: #4ade80; }
.app-5 { background: #c084fc; }
.app-6 { background: #fb923c; }

.screen-dock {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(4px);
  border-radius: 6px;
  padding: 3px;
  display: flex;
  justify-content: space-around;
  margin-top: auto;
}

.dock-app {
  width: 14px;
  height: 14px;
  border-radius: 3px;
}

.dock-phone { background: #22c55e; }
.dock-msg { background: #3b82f6; }
.dock-web { background: #eab308; }

/* 离线屏幕 */
.screen-offline {
  width: 100%;
  height: 100%;
  background: #1e293b;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--c-text-secondary);
}

.offline-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
}

.offline-phone-icon {
  font-size: 14px;
  color: var(--c-text-secondary);
}

.offline-text {
  font-size: 10px;
  color: var(--c-text-tertiary);
}

/* 规格参数面板 */
.device-specs-sheet {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.spec-row {
  display: flex;
  align-items: center;
  line-height: 1.4;
}

.spec-label {
  width: 68px;
  color: var(--c-text-secondary);
  flex-shrink: 0;
}

.spec-val {
  color: var(--c-text);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-val, .agent-val {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.battery-bar-wrap {
  display: inline-block;
  width: 20px;
  height: 9px;
  border: 1px solid #16a34a;
  border-radius: 2px;
  padding: 1px;
  margin-right: 4px;
  vertical-align: middle;
}

.battery-bar-fill {
  display: block;
  height: 100%;
  background: #16a34a;
  border-radius: 1px;
}

/* 卡片底栏 */
.card-footer-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--c-border-subtle);
}

.minor-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
}

.footer-link {
  padding: 0 4px;
  font-size: 12px;
  color: var(--c-text-secondary);
}

.footer-link:hover {
  color: var(--c-primary);
}

.cta-use-btn {
  width: 100%;
  height: 34px;
  border-radius: 6px;
  background: var(--c-primary);
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
}

.cta-use-btn:hover:not(.disabled) {
  background: #1d4ed8;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.cta-use-btn.disabled {
  background: var(--c-bg-muted);
  color: var(--c-text-tertiary);
  cursor: not-allowed;
  box-shadow: none;
}

.empty-matrix-card {
  grid-column: 1 / -1;
  padding: 60px 0;
  background: var(--c-bg-elevated);
  border-radius: 12px;
  border: 1px dashed var(--c-border);
}

/* 表格容器 */
.table-card-wrap {
  background: var(--c-bg-elevated);
  border-radius: 12px;
  border: 1px solid var(--c-border);
  padding: 16px;
}

/* 屏幕镜像弹窗 */
.mirror-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.mirror-img {
  max-width: 100%;
  max-height: 600px;
  object-fit: contain;
}

.mirror-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
  color: var(--c-text-tertiary);
}

.mirror-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
</style>
