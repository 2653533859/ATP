<template>
  <div class="page-shell app-workbench">
    <section class="app-hero">
      <div class="hero-copy">
        <div class="eyebrow"><MobileOutlined /> {{ t('app_workbench.eyebrow') }}</div>
        <div class="hero-title-row">
          <h1>{{ t('app_workbench.title') }}</h1>
          <span class="hero-chip">ADB / Windows lane</span>
        </div>
        <p>{{ t('app_workbench.subtitle') }}</p>
        <div class="hero-rail">
          <span class="live-dot" :class="{ muted: !workers.length }" />
          <span>{{ workers.length ? t('app_workbench.worker_online', { count: workers.length }) : t('app_workbench.worker_offline') }}</span>
          <span class="rail-separator" />
          <span class="rail-muted">{{ selectedProjectName || t('app_workbench.no_project') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label>{{ t('app_workbench.project_label') }}</label>
        <a-select
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :disabled="Boolean(lease)"
          :placeholder="t('app_workbench.project_placeholder')"
          @change="handleProjectChange"
        />
        <div class="hero-control-row">
          <a-button :loading="loading" @click="refreshAll"><ReloadOutlined /> {{ t('common.refresh') }}</a-button>
          <a-button type="link" @click="openDevices"><ToolOutlined /> {{ t('app_workbench.device_management') }}</a-button>
        </div>
      </div>
    </section>

    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('app_workbench.readonly_title')"
      :description="t('app_workbench.readonly_description')"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('app_workbench.select_project_hint')" />

    <template v-else>
      <section class="signal-grid" aria-label="Android workspace summary">
        <div class="signal-card signal-card-primary">
          <span class="signal-label">{{ t('app_workbench.signals.online_devices') }}</span>
          <strong>{{ onlineDeviceCount }}<small>/{{ devices.length }}</small></strong>
          <span class="signal-note">{{ t('app_workbench.signals.device_pool') }}</span>
        </div>
        <div class="signal-card">
          <span class="signal-label">{{ t('app_workbench.signals.android_cases') }}</span>
          <strong>{{ androidCases.length }}</strong>
          <span class="signal-note">{{ readyAndroidCaseCount }} {{ t('app_workbench.signals.ready_cases') }}</span>
        </div>
        <div class="signal-card">
          <span class="signal-label">{{ t('app_workbench.signals.apk_assets') }}</span>
          <strong>{{ apks.length }}</strong>
          <span class="signal-note">{{ t('app_workbench.signals.package_ready') }}</span>
        </div>
        <div class="signal-card signal-card-run">
          <span class="signal-label">{{ t('app_workbench.signals.active_runs') }}</span>
          <strong>{{ activeRunCount }}</strong>
          <span class="signal-note">{{ t('app_workbench.signals.worker_queue') }}</span>
        </div>
      </section>

      <section class="workspace-grid">
        <aside class="device-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('app_workbench.device_kicker') }}</div>
              <h2>{{ t('app_workbench.device_pool') }}</h2>
            </div>
            <a-button size="small" :loading="scanning" :disabled="!canModify" @click="scanDevices">
              <ReloadOutlined />
            </a-button>
          </div>
          <div class="panel-caption">
            <span>{{ t('app_workbench.device_pool_caption') }}</span>
            <span class="count-pill">{{ onlineDeviceCount }} {{ t('app_workbench.online') }}</span>
          </div>

          <div v-if="devices.length" class="device-list">
            <button
              v-for="device in devices"
              :key="device.id"
              type="button"
              class="device-row"
              :class="{ selected: device.id === selectedDeviceId, locked: lease && lease.device_id !== device.id }"
              @click="selectDevice(device)"
            >
              <span class="device-status-dot" :class="`status-${device.status}`" />
              <span class="device-row-main">
                <strong>{{ device.name || device.model || device.serial }}</strong>
                <small>{{ device.brand || 'Android' }} · {{ device.os_version || '—' }} · {{ device.serial }}</small>
              </span>
              <span class="device-status-text">{{ deviceStatusLabel(device.status) }}</span>
            </button>
          </div>
          <a-empty v-else :description="t('app_workbench.no_devices')" />

          <div v-if="selectedDevice" class="device-focus">
            <div class="focus-heading">
              <div>
                <span class="focus-kicker">{{ t('app_workbench.selected_device') }}</span>
                <strong>{{ selectedDevice.name || selectedDevice.model || selectedDevice.serial }}</strong>
              </div>
              <a-tag :color="selectedDevice.status === 'online' ? 'green' : 'default'">{{ deviceStatusLabel(selectedDevice.status) }}</a-tag>
            </div>
            <div class="device-specs">
              <span>{{ selectedDevice.resolution || '—' }}</span>
              <span>API {{ selectedDevice.sdk_version || '—' }}</span>
              <span>{{ selectedDevice.ip_address || t('app_workbench.local_adb') }}</span>
            </div>
            <div v-if="lease" class="lease-banner">
              <SafetyCertificateOutlined />
              <span>{{ t('app_workbench.lease_active', { time: formatTime(lease.expires_at) }) }}</span>
            </div>
            <div class="focus-actions">
              <a-button
                v-if="!lease"
                size="small"
                type="primary"
                ghost
                :disabled="!canModify || selectedDevice.status !== 'online'"
                :loading="leaseLoading"
                @click="acquireLease"
              >{{ t('app_workbench.reserve') }}</a-button>
              <a-button v-else size="small" danger :loading="leaseLoading" @click="() => releaseLease()">{{ t('app_workbench.release') }}</a-button>
              <a-button size="small" :disabled="!lease || selectedDevice.status !== 'online'" @click="openPreview">
                <EyeOutlined /> {{ t('app_workbench.preview') }}
              </a-button>
            </div>
          </div>
        </aside>

        <main class="launch-panel panel">
          <div class="panel-head launch-head">
            <div>
              <div class="panel-kicker">{{ t('app_workbench.launch_kicker') }}</div>
              <h2>{{ t('app_workbench.launch_title') }}</h2>
              <p>{{ t('app_workbench.launch_description') }}</p>
            </div>
            <div class="launch-signal"><span class="signal-line" />{{ t('app_workbench.local_execution') }}</div>
          </div>

          <div class="mode-switch" role="tablist">
            <button type="button" :class="{ active: launchMode === 'case' }" @click="launchMode = 'case'">
              <MobileOutlined /> {{ t('app_workbench.android_case') }}
            </button>
            <button type="button" :class="{ active: launchMode === 'special' }" @click="launchMode = 'special'">
              <ThunderboltOutlined /> {{ t('app_workbench.special_task') }}
            </button>
          </div>

          <div v-if="launchMode === 'case'" class="launch-form">
            <label>{{ t('app_workbench.case_label') }}</label>
            <a-select
              v-model:value="selectedCaseId"
              :options="androidCaseOptions"
              allow-clear
              :placeholder="t('app_workbench.case_placeholder')"
              :loading="loading"
            />
            <div v-if="selectedAndroidCase" class="selection-card">
              <div class="selection-title">
                <strong>{{ selectedAndroidCase.name }}</strong>
                <a-tag :color="selectedAndroidCase.is_ready_for_execution ? 'green' : 'orange'">
                  {{ selectedAndroidCase.is_ready_for_execution ? t('app_workbench.ready') : t('app_workbench.not_ready') }}
                </a-tag>
              </div>
              <div class="selection-meta">
                <span>{{ selectedAndroidCase.case_code }}</span>
                <span>{{ selectedAndroidCase.priority }}</span>
                <span>{{ t(`case.levels.${selectedAndroidCase.case_level}`) }}</span>
                <span>{{ selectedAndroidCase.script_status === 'generated' ? t('app_workbench.script_generated') : t('app_workbench.script_missing') }}</span>
              </div>
            </div>
            <div class="launch-actions">
              <a-button type="primary" :disabled="!canRunAndroidCase" :loading="runLoading" @click="runAndroidCase">
                <PlayCircleOutlined /> {{ t('app_workbench.run_case') }}
              </a-button>
              <a-button type="link" @click="openAndroidCases">{{ t('app_workbench.manage_cases') }}</a-button>
            </div>
            <p class="launch-note"><SafetyCertificateOutlined /> {{ t('app_workbench.case_device_note') }}</p>
          </div>

          <div v-else class="launch-form">
            <label>{{ t('app_workbench.task_label') }}</label>
            <a-select
              v-model:value="selectedSpecialTaskId"
              :options="specialTaskOptions"
              allow-clear
              :placeholder="t('app_workbench.task_placeholder')"
              :loading="loading"
            />
            <div class="launch-two-col">
              <div>
                <label>{{ t('app_workbench.target_device') }}</label>
                <a-select v-model:value="launchDeviceSelectId" :options="onlineDeviceOptions" allow-clear :placeholder="t('app_workbench.device_placeholder')" />
              </div>
              <div>
                <label>{{ t('app_workbench.override_apk') }}</label>
                <a-select v-model:value="selectedApkId" :options="apkOptions" allow-clear :placeholder="t('app_workbench.apk_placeholder')" />
              </div>
            </div>
            <div v-if="selectedSpecialTask" class="selection-card">
              <div class="selection-title">
                <strong>{{ selectedSpecialTask.name }}</strong>
                <a-tag :color="taskTypeColor(selectedSpecialTask.task_type)">{{ taskTypeLabel(selectedSpecialTask.task_type) }}</a-tag>
              </div>
              <div class="selection-meta">
                <span>{{ sourceTypeLabel(selectedSpecialTask.source_type) }}</span>
                <span>{{ deviceScopeLabel(selectedSpecialTask.device_scope_type) }}</span>
                <span>{{ selectedSpecialTask.config_json.capture_replay ? t('app_workbench.replay_enabled') : t('app_workbench.replay_disabled') }}</span>
              </div>
            </div>
            <div class="launch-actions">
              <a-button type="primary" :disabled="!canRunSpecialTask" :loading="runLoading" @click="runSpecialTask">
                <PlayCircleOutlined /> {{ t('app_workbench.run_special') }}
              </a-button>
              <a-button type="link" @click="openSpecialTasks">{{ t('app_workbench.manage_tasks') }}</a-button>
            </div>
            <p class="launch-note"><SafetyCertificateOutlined /> {{ lease ? t('app_workbench.release_before_run') : t('app_workbench.special_device_note') }}</p>
          </div>
        </main>
      </section>

      <section class="lower-grid">
        <div class="activity-panel panel">
          <div class="panel-head compact-head">
            <div>
              <div class="panel-kicker">{{ t('app_workbench.activity_kicker') }}</div>
              <h2>{{ t('app_workbench.activity_title') }}</h2>
            </div>
            <a-button type="link" size="small" @click="openSpecialReports">{{ t('app_workbench.view_all_runs') }}</a-button>
          </div>
          <div v-if="recentActivities.length" class="activity-list">
            <button v-for="activity in recentActivities" :key="activity.key" type="button" class="activity-row" @click="openActivity(activity)">
              <span class="activity-mark" :class="`activity-${activity.kind}`"><MobileOutlined v-if="activity.kind === 'case'" /><ThunderboltOutlined v-else /></span>
              <span class="activity-main">
                <strong>{{ activity.name }}</strong>
                <small>{{ activity.device || t('app_workbench.device_unassigned') }} · {{ formatTime(activity.created_at) }}</small>
              </span>
              <span class="activity-status" :class="`activity-status-${activity.status}`">{{ runStatusLabel(activity.status) }}</span>
            </button>
          </div>
          <a-empty v-else :description="t('app_workbench.no_activity')" />
        </div>

        <div class="asset-panel panel">
          <div class="panel-head compact-head">
            <div>
              <div class="panel-kicker">{{ t('app_workbench.asset_kicker') }}</div>
              <h2>{{ t('app_workbench.asset_title') }}</h2>
            </div>
            <a-button type="link" size="small" @click="openApks">{{ t('app_workbench.manage_apks') }}</a-button>
          </div>
          <div v-if="apks.length" class="apk-list">
            <div v-for="apk in apks.slice(0, 4)" :key="apk.id" class="apk-row">
              <span class="apk-mark"><AndroidOutlined /></span>
              <span class="apk-main">
                <strong>{{ apk.package_name || apk.filename }}</strong>
                <small>{{ apk.version_name ? `v${apk.version_name}` : t('app_workbench.version_unknown') }} · {{ formatSize(apk.file_size) }}</small>
              </span>
              <span class="apk-code">#{{ apk.id }}</span>
            </div>
          </div>
          <a-empty v-else :description="t('app_workbench.no_apks')" />
          <div class="compatibility-strip">
            <div class="strip-label"><AppstoreOutlined /> {{ t('app_workbench.compatibility_title') }}</div>
            <span v-for="family in deviceFamilies" :key="family" class="compatibility-chip">{{ family }}</span>
            <span v-if="!deviceFamilies.length" class="compatibility-empty">{{ t('app_workbench.no_device_matrix') }}</span>
          </div>
        </div>
      </section>
    </template>

    <a-modal v-model:open="previewOpen" :title="t('app_workbench.preview_title', { name: selectedDevice?.name || selectedDevice?.serial || '' })" :footer="null" width="430px" @cancel="closePreview">
      <div class="preview-stage">
        <img v-if="previewSrc" :src="previewSrc" :alt="t('app_workbench.preview_alt')" />
        <a-spin v-else :tip="t('app_workbench.preview_loading')" />
      </div>
      <div class="preview-footer">
        <span><span class="live-dot" />{{ t('app_workbench.preview_live') }}</span>
        <a-button size="small" @click="() => refreshPreview()"><ReloadOutlined /> {{ t('app_workbench.refresh_preview') }}</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  AndroidOutlined,
  AppstoreOutlined,
  EyeOutlined,
  MobileOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  apkApi,
  caseApi,
  deviceApi,
  mobileSpecialApi,
  projectApi,
  runApi,
  type ApkItem,
  type AndroidWorkerItem,
  type CaseSummaryItem,
  type CaseType,
  type DeviceItem,
  type DeviceLeaseItem,
  type MobileSpecialRunItem,
  type MobileSpecialTaskItem,
  type ProjectItem,
  type RunDetailItem,
  type TaskType,
} from '@/api'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type LaunchMode = 'case' | 'special'
type ErrorLike = { response?: { data?: { detail?: unknown } }; message?: unknown }
type SelectOption<T extends string | number> = { label: string; value: T }
type ActivityItem = {
  key: string
  kind: 'case' | 'special'
  id: number
  name: string
  status: string
  device?: string | null
  created_at: string
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const devices = ref<DeviceItem[]>([])
const workers = ref<AndroidWorkerItem[]>([])
const apks = ref<ApkItem[]>([])
const androidCases = ref<CaseSummaryItem[]>([])
const specialTasks = ref<MobileSpecialTaskItem[]>([])
const specialRuns = ref<MobileSpecialRunItem[]>([])
const androidRuns = ref<RunDetailItem[]>([])
const selectedDeviceId = ref<number | null>(null)
const launchDeviceId = ref<number | null>(null)
const launchDeviceSelectId = computed<number | undefined>({
  get: () => launchDeviceId.value ?? undefined,
  set: (value) => { launchDeviceId.value = positiveInt(value) },
})
const selectedCaseId = ref<number | undefined>(undefined)
const selectedSpecialTaskId = ref<number | undefined>(undefined)
const selectedApkId = ref<number | undefined>(undefined)
const launchMode = ref<LaunchMode>('case')
const loading = ref(false)
const scanning = ref(false)
const runLoading = ref(false)
const leaseLoading = ref(false)
const lease = ref<DeviceLeaseItem | null>(null)
const previewOpen = ref(false)
const previewSrc = ref<string | null>(null)
let previewObjectUrl: string | null = null
let previewTimer: number | null = null
let previewSession = 0
let leaseHeartbeatTimer: number | null = null

const projectOptions = computed<SelectOption<number>[]>(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const selectedDevice = computed(() => devices.value.find((device) => device.id === selectedDeviceId.value) || null)
const selectedAndroidCase = computed(() => androidCases.value.find((item) => item.id === selectedCaseId.value) || null)
const selectedSpecialTask = computed(() => specialTasks.value.find((task) => task.id === selectedSpecialTaskId.value) || null)
const selectedApk = computed(() => apks.value.find((apk) => apk.id === selectedApkId.value) || null)
const onlineDevices = computed(() => devices.value.filter((device) => device.status === 'online'))
const onlineDeviceCount = computed(() => onlineDevices.value.length)
const readyAndroidCaseCount = computed(() => androidCases.value.filter((item) => item.is_ready_for_execution).length)
const activeRunCount = computed(() =>
  specialRuns.value.filter((run) => run.status === 'pending' || run.status === 'running').length
  + androidRuns.value.filter((run) => run.status === 'pending' || run.status === 'running').length,
)
const compatibilityFamilies = computed(() => Array.from(new Set(
  devices.value
    .map((device) => [device.brand, device.model].filter(Boolean).join(' '))
    .filter(Boolean),
)).slice(0, 5))
const androidCaseOptions = computed<SelectOption<number>[]>(() => androidCases.value.map((item) => ({
  label: `${item.name} · ${item.case_code}`,
  value: item.id,
})))
const specialTaskOptions = computed<SelectOption<number>[]>(() => specialTasks.value.map((task) => ({
  label: `${task.name} · ${taskTypeLabel(task.task_type)}`,
  value: task.id,
})))
const onlineDeviceOptions = computed<SelectOption<number>[]>(() => onlineDevices.value.map((device) => ({
  label: `${device.name || device.model || device.serial} · ${device.serial}`,
  value: device.id,
})))
const apkOptions = computed<SelectOption<number>[]>(() => [
  { label: t('app_workbench.no_apk_override'), value: 0 },
  ...apks.value.map((apk) => ({ label: `${apk.package_name || apk.filename}${apk.version_name ? ` · v${apk.version_name}` : ''}`, value: apk.id })),
])
const canRunAndroidCase = computed(() => Boolean(canModify.value && selectedAndroidCase.value?.is_ready_for_execution && !lease.value && !runLoading.value))
const canRunSpecialTask = computed(() => Boolean(canModify.value && selectedSpecialTask.value && !lease.value && !runLoading.value))
const deviceFamilies = compatibilityFamilies

const recentActivities = computed<ActivityItem[]>(() => {
  const items: ActivityItem[] = [
    ...specialRuns.value.map((run) => ({
      key: `special-${run.id}`,
      kind: 'special' as const,
      id: run.id,
      name: run.task_name || t('app_workbench.special_run', { id: run.id }),
      status: run.status,
      device: run.device_serial,
      created_at: run.created_at,
    })),
    ...androidRuns.value.map((run) => ({
      key: `case-${run.id}`,
      kind: 'case' as const,
      id: run.id,
      name: run.case_name || t('app_workbench.case_run', { id: run.id }),
      status: run.status,
      device: run.environment,
      created_at: run.created_at,
    })),
  ]
  return items.sort((left, right) => right.created_at.localeCompare(left.created_at)).slice(0, 8)
})

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return error instanceof Error ? error.message : fallback
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '—'
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function deviceStatusLabel(status: DeviceItem['status']) {
  return t(`app_workbench.device_status.${status}`)
}

function taskTypeLabel(type: TaskType) {
  return t(`mobile_special.task_types.${type}`)
}

function taskTypeColor(type: TaskType) {
  return ({ performance: 'blue', stability: 'orange', fluency: 'purple' } as Record<string, string>)[type] || 'default'
}

function sourceTypeLabel(source: string) {
  return t(`mobile_special.source_types.${source}`)
}

function deviceScopeLabel(scope: string) {
  return t(`mobile_special.device_scopes.${scope}`)
}

function runStatusLabel(status?: string | null) {
  if (!status) return t('app_workbench.status.unknown')
  const key = ['pending', 'running', 'completed', 'passed', 'failed', 'error', 'stopped', 'cancelled'].includes(status) ? status : 'unknown'
  return t(`app_workbench.status.${key}`)
}

function syncRoute() {
  void router.replace({
    query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {},
  })
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (!selectedProjectId.value || !projects.value.some((project) => project.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
    }
    syncRoute()
    await loadProjectData()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('app_workbench.load_failed')))
  }
}

async function loadProjectData() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    devices.value = []
    workers.value = []
    apks.value = []
    androidCases.value = []
    specialTasks.value = []
    specialRuns.value = []
    androidRuns.value = []
    selectedDeviceId.value = null
    return
  }
  loading.value = true
  try {
    await Promise.all([
      loadDevices(),
      loadWorkers(),
      loadApks(projectId),
      loadAndroidCases(projectId),
      loadSpecialTasks(projectId),
      loadSpecialRuns(projectId),
    ])
    await loadAndroidRuns()
    if (!selectedDeviceId.value || !devices.value.some((device) => device.id === selectedDeviceId.value)) {
      selectedDeviceId.value = onlineDevices.value[0]?.id ?? devices.value[0]?.id ?? null
    }
    if (!selectedCaseId.value || !androidCases.value.some((item) => item.id === selectedCaseId.value)) {
      selectedCaseId.value = androidCases.value[0]?.id
    }
    if (!selectedSpecialTaskId.value || !specialTasks.value.some((task) => task.id === selectedSpecialTaskId.value)) {
      selectedSpecialTaskId.value = specialTasks.value[0]?.id
    }
  } finally {
    loading.value = false
  }
}

async function loadDevices() {
  try {
    devices.value = await deviceApi.list()
  } catch {
    devices.value = []
  }
}

async function loadWorkers() {
  try {
    workers.value = await deviceApi.workers()
  } catch {
    workers.value = []
  }
}

async function loadApks(projectId: number) {
  try {
    apks.value = await apkApi.list({ project_id: projectId })
  } catch {
    apks.value = []
  }
}

async function loadAndroidCases(projectId: number) {
  try {
    const result = await caseApi.list({ project_id: projectId, case_type: 'android' as CaseType })
    androidCases.value = result.filter((item) => item.case_type === 'android')
  } catch {
    androidCases.value = []
  }
}

async function loadSpecialTasks(projectId: number) {
  try {
    specialTasks.value = await mobileSpecialApi.listTasks({ project_id: projectId })
  } catch {
    specialTasks.value = []
  }
}

async function loadSpecialRuns(projectId: number) {
  try {
    specialRuns.value = await mobileSpecialApi.listRuns({ project_id: projectId, limit: 8 })
  } catch {
    specialRuns.value = []
  }
}

async function loadAndroidRuns() {
  const caseIds = new Set(androidCases.value.map((item) => item.id))
  if (!caseIds.size) {
    androidRuns.value = []
    return
  }
  try {
    const result = await runApi.list({ page: 1, page_size: 100 })
    androidRuns.value = result.items
      .filter((run) => caseIds.has(run.case_id))
      .sort((left, right) => right.created_at.localeCompare(left.created_at))
      .slice(0, 8)
  } catch {
    androidRuns.value = []
  }
}

async function handleProjectChange(value: unknown) {
  selectedProjectId.value = positiveInt(value)
  selectedCaseId.value = undefined
  selectedSpecialTaskId.value = undefined
  selectedApkId.value = undefined
  launchDeviceId.value = null
  await loadProjectData()
  syncRoute()
}

async function refreshAll() {
  await loadProjects()
}

function selectDevice(device: DeviceItem) {
  if (lease.value && lease.value.device_id !== device.id) {
    message.warning(t('app_workbench.release_device_first'))
    return
  }
  selectedDeviceId.value = device.id
}

async function scanDevices() {
  if (!canModify.value) return
  scanning.value = true
  try {
    const result = await deviceApi.scan()
    devices.value = result.devices
    if (result.status === 'failed') throw new Error(result.error || t('app_workbench.scan_failed'))
    if (result.status === 'queued' || result.status === 'running') {
      if (!result.scan_id) throw new Error(t('app_workbench.scan_pending'))
      message.info(t('app_workbench.scan_queued'))
      await waitForScan(result.scan_id)
    } else {
      message.success(t('app_workbench.scan_success', { count: devices.value.length }))
    }
  } catch (error: unknown) {
    message.error(errorMessage(error, t('app_workbench.scan_failed')))
  } finally {
    scanning.value = false
  }
}

async function waitForScan(scanId: string) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 500))
    const result = await deviceApi.scanStatus(scanId)
    devices.value = result.devices
    if (result.status === 'completed') {
      message.success(t('app_workbench.scan_success', { count: devices.value.length }))
      return
    }
    if (result.status === 'failed') throw new Error(result.error || t('app_workbench.scan_failed'))
  }
  message.info(t('app_workbench.scan_pending'))
}

async function acquireLease() {
  const device = selectedDevice.value
  if (!device || !canModify.value) return
  leaseLoading.value = true
  try {
    const result = await deviceApi.acquireLease(device.id, { ttl_seconds: 900, owner_label: 'app-workbench' })
    if (!result.lease_token) throw new Error(t('app_workbench.lease_token_missing'))
    lease.value = result
    startLeaseHeartbeat()
    message.success(t('app_workbench.reserve_success'))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('app_workbench.reserve_failed')))
  } finally {
    leaseLoading.value = false
  }
}

function startLeaseHeartbeat() {
  stopLeaseHeartbeat()
  leaseHeartbeatTimer = window.setInterval(() => { void heartbeatLease() }, 240000)
}

function stopLeaseHeartbeat() {
  if (leaseHeartbeatTimer !== null) {
    window.clearInterval(leaseHeartbeatTimer)
    leaseHeartbeatTimer = null
  }
}

async function heartbeatLease() {
  const current = lease.value
  if (!current?.lease_token) return
  try {
    const result = await deviceApi.heartbeatLease(current.device_id, current.lease_token)
    lease.value = { ...result, lease_token: current.lease_token }
  } catch {
    stopLeaseHeartbeat()
    lease.value = null
    message.warning(t('app_workbench.lease_expired'))
  }
}

async function releaseLease(silent = false) {
  const current = lease.value
  if (!current?.lease_token) return
  leaseLoading.value = true
  try {
    await deviceApi.releaseLease(current.device_id, current.lease_token)
    lease.value = null
    stopLeaseHeartbeat()
    if (!silent) message.success(t('app_workbench.release_success'))
  } catch (error: unknown) {
    if (!silent) message.error(errorMessage(error, t('app_workbench.release_failed')))
  } finally {
    leaseLoading.value = false
  }
}

async function runAndroidCase() {
  const current = selectedAndroidCase.value
  if (!current || !canRunAndroidCase.value) return
  runLoading.value = true
  try {
    const result = await caseApi.run(current.id)
    message.success(t('app_workbench.run_started'))
    await router.push({ name: 'run-detail', params: { runId: String(result.id) } })
  } catch (error: unknown) {
    message.error(errorMessage(error, t('app_workbench.run_failed')))
  } finally {
    runLoading.value = false
  }
}

async function runSpecialTask() {
  const task = selectedSpecialTask.value
  if (!task || !canRunSpecialTask.value) return
  runLoading.value = true
  try {
    const result = await mobileSpecialApi.triggerTask(task.id, {
      device_id: launchDeviceId.value ?? undefined,
      apk_id: selectedApkId.value || undefined,
      app_package: selectedApk.value?.package_name ?? undefined,
    })
    message.success(t('app_workbench.run_started'))
    await router.push(`/mobile-special/reports/${result.id}`)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('app_workbench.run_failed')))
  } finally {
    runLoading.value = false
  }
}

function openActivity(activity: ActivityItem) {
  if (activity.kind === 'case') {
    void router.push({ name: 'run-detail', params: { runId: String(activity.id) } })
  } else {
    void router.push(`/mobile-special/reports/${activity.id}`)
  }
}

function openDevices() { void router.push('/devices') }
function openApks() { void router.push('/apks') }
function openSpecialTasks() { void router.push('/mobile-special/tasks') }
function openSpecialReports() { void router.push('/mobile-special/reports') }
function openAndroidCases() {
  void router.push({ path: '/cases', query: selectedProjectId.value ? { project_id: String(selectedProjectId.value), case_type: 'android' } : {} })
}

function openPreview() {
  if (!lease.value) {
    message.warning(t('app_workbench.reserve_before_preview'))
    return
  }
  previewOpen.value = true
  previewSession += 1
  void refreshPreview(previewSession)
  previewTimer = window.setInterval(() => { void refreshPreview(previewSession) }, 700)
}

function revokePreviewUrl() {
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl)
    previewObjectUrl = null
  }
}

function closePreview() {
  previewSession += 1
  previewOpen.value = false
  previewSrc.value = null
  revokePreviewUrl()
  if (previewTimer !== null) {
    window.clearInterval(previewTimer)
    previewTimer = null
  }
}

async function refreshPreview(session = previewSession) {
  const device = selectedDevice.value
  if (!device || !previewOpen.value || session !== previewSession) return
  try {
    const blob = await deviceApi.screenshot(device.id)
    if (session !== previewSession || !previewOpen.value) return
    const nextUrl = URL.createObjectURL(blob)
    revokePreviewUrl()
    previewObjectUrl = nextUrl
    previewSrc.value = nextUrl
  } catch {
    // Keep the last frame while the Worker is temporarily busy.
  }
}

onMounted(() => { void loadProjects() })
onUnmounted(() => {
  closePreview()
  stopLeaseHeartbeat()
  if (lease.value?.lease_token) void deviceApi.releaseLease(lease.value.device_id, lease.value.lease_token)
})
</script>

<style scoped>
.app-workbench {
  --app-ink: #142238;
  --app-muted: #718096;
  --app-line: #dfe7ed;
  --app-cyan: #37c4c6;
  --app-copper: #ee7557;
  color: var(--app-ink);
}

.app-hero {
  display: flex;
  justify-content: space-between;
  gap: 30px;
  padding: 30px 32px 26px;
  overflow: hidden;
  border: 1px solid #1f3144;
  border-radius: 18px;
  background: radial-gradient(circle at 82% 18%, rgba(55, 196, 198, .18), transparent 23%), linear-gradient(120deg, #121e2d, #172c3c 68%, #233543);
  box-shadow: 0 16px 34px rgba(18, 35, 53, .16);
  color: #f7fbfc;
}
.hero-copy { min-width: 0; }
.eyebrow, .panel-kicker, .focus-kicker { color: var(--app-cyan); font-size: 11px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.eyebrow { display: flex; align-items: center; gap: 7px; }
.hero-title-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 7px 0 8px; }
.app-hero h1 { margin: 0; color: #fff; font-size: 31px; letter-spacing: -.045em; }
.hero-chip { padding: 4px 8px; border: 1px solid rgba(93, 210, 211, .34); border-radius: 5px; color: #9ce5e4; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; letter-spacing: .04em; }
.app-hero p { max-width: 700px; margin: 0; color: #b7c9d0; line-height: 1.7; }
.hero-rail { display: flex; align-items: center; gap: 9px; margin-top: 21px; color: #e2f2f0; font-size: 12px; font-weight: 650; }
.live-dot, .device-status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--app-cyan); box-shadow: 0 0 0 4px rgba(55, 196, 198, .14); }
.live-dot.muted { background: #ef9a62; box-shadow: 0 0 0 4px rgba(239, 154, 98, .12); }
.rail-separator { width: 1px; height: 14px; margin: 0 2px; background: #496274; }
.rail-muted { color: #8fa7b2; font-weight: 500; }
.hero-controls { display: flex; flex: 0 0 252px; flex-direction: column; gap: 8px; }
.hero-controls label { color: #9eb7c0; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.hero-controls .ant-select { width: 100%; }
.hero-control-row { display: flex; align-items: center; gap: 5px; margin-top: 3px; }
.hero-control-row .ant-btn { color: #e8f7f6; }
.hero-control-row .ant-btn-link { padding-inline: 5px; color: #91d9d6; }
.readonly-alert { margin-top: 16px; }
.project-empty { min-height: 320px; padding: 100px 0; }

.signal-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.signal-card { position: relative; min-height: 112px; overflow: hidden; padding: 17px 18px; border: 1px solid var(--app-line); border-radius: 12px; background: #fff; }
.signal-card::after { position: absolute; right: 0; bottom: 0; width: 45px; height: 3px; background: #d7e1e6; content: ''; }
.signal-card-primary { border-color: #b7dfdf; background: #f2fcfb; }.signal-card-primary::after { background: var(--app-cyan); }.signal-card-run::after { background: var(--app-copper); }
.signal-label { display: block; color: var(--app-muted); font-size: 11px; font-weight: 750; letter-spacing: .05em; text-transform: uppercase; }
.signal-card strong { display: block; margin-top: 10px; color: #112c3e; font-size: 28px; letter-spacing: -.05em; }.signal-card strong small { margin-left: 3px; color: #8d9da5; font-size: 14px; font-weight: 600; letter-spacing: 0; }
.signal-note { display: block; margin-top: 6px; color: #8997a4; font-size: 11px; }

.workspace-grid { display: grid; grid-template-columns: minmax(260px, 330px) minmax(0, 1fr); gap: 16px; }
.lower-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr); gap: 16px; margin-top: 16px; }
.panel { border: 1px solid var(--app-line); border-radius: 14px; background: #fff; box-shadow: 0 8px 24px rgba(31, 58, 77, .05); }
.device-panel, .launch-panel, .activity-panel, .asset-panel { padding: 20px; }
.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.panel-head h2 { margin: 5px 0 0; color: #172f40; font-size: 20px; letter-spacing: -.03em; }.compact-head { align-items: center; }.compact-head h2 { font-size: 17px; }.panel-caption { display: flex; justify-content: space-between; gap: 8px; margin: 9px 0 12px; color: #84919d; font-size: 11px; line-height: 1.5; }.count-pill { padding: 3px 7px; border-radius: 999px; background: #eaf9f6; color: #208a7f; font-weight: 700; white-space: nowrap; }
.device-list { display: flex; flex-direction: column; gap: 6px; max-height: 330px; overflow: auto; }
.device-row { display: flex; align-items: center; gap: 9px; width: 100%; padding: 10px 9px; border: 1px solid transparent; border-radius: 9px; background: #f8fafb; color: inherit; text-align: left; transition: border-color .16s, background .16s, transform .16s; }.device-row:hover, .device-row.selected { border-color: #a5d9d7; background: #effafa; }.device-row.selected { box-shadow: inset 3px 0 0 var(--app-cyan); }.device-row.locked { cursor: not-allowed; opacity: .55; }.device-row:focus-visible, .activity-row:focus-visible, .mode-switch button:focus-visible { outline: 2px solid var(--app-cyan); outline-offset: 2px; }
.device-status-dot { flex: 0 0 auto; width: 8px; height: 8px; box-shadow: none; }.status-online { background: #35b890; }.status-busy { background: var(--app-copper); }.status-offline { background: #adb9c0; }
.device-row-main { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.device-row-main strong { overflow: hidden; color: #234051; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.device-row-main small { overflow: hidden; color: #91a0aa; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.device-status-text { color: #96a3aa; font-size: 10px; white-space: nowrap; }
.device-focus { margin-top: 16px; padding-top: 15px; border-top: 1px solid #edf1f3; }.focus-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }.focus-heading strong { display: block; margin-top: 4px; color: #254455; font-size: 13px; }.device-specs { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 10px; color: #84949f; font-size: 10px; }.lease-banner { display: flex; align-items: center; gap: 6px; margin-top: 11px; padding: 8px 9px; border: 1px solid #f5d5ad; border-radius: 7px; background: #fff8ed; color: #a66b27; font-size: 10px; }.focus-actions { display: flex; gap: 7px; margin-top: 13px; }

.launch-panel { min-width: 0; }.launch-head p { max-width: 630px; margin: 7px 0 0; color: #84919f; font-size: 12px; line-height: 1.6; }.launch-signal { display: flex; align-items: center; gap: 7px; color: #78909a; font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }.signal-line { width: 20px; height: 2px; background: var(--app-copper); box-shadow: 7px 0 0 rgba(238, 117, 87, .35), 14px 0 0 rgba(238, 117, 87, .16); }
.mode-switch { display: inline-flex; gap: 4px; margin: 24px 0 20px; padding: 4px; border-radius: 9px; background: #f0f4f5; }.mode-switch button { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; border: 0; border-radius: 6px; background: transparent; color: #7a8994; cursor: pointer; font: inherit; font-size: 12px; font-weight: 700; }.mode-switch button.active { background: #fff; color: #1e6f73; box-shadow: 0 2px 7px rgba(40, 76, 85, .12); }
.launch-form { max-width: 730px; }.launch-form > label, .launch-two-col label { display: block; margin-bottom: 7px; color: #617481; font-size: 11px; font-weight: 750; letter-spacing: .04em; }.launch-form > .ant-select { width: 100%; }.selection-card { margin-top: 14px; padding: 14px; border: 1px solid #dce8ea; border-left: 3px solid var(--app-cyan); border-radius: 9px; background: #f8fcfc; }.selection-title { display: flex; align-items: center; justify-content: space-between; gap: 9px; }.selection-title strong { color: #244353; font-size: 13px; }.selection-meta { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 8px; color: #83929c; font-size: 11px; }.selection-meta span + span { position: relative; }.selection-meta span + span::before { position: absolute; top: 50%; left: -9px; width: 3px; height: 3px; border-radius: 50%; background: #b5c1c6; content: ''; transform: translateY(-50%); }.launch-actions { display: flex; align-items: center; gap: 8px; margin-top: 19px; }.launch-note { display: flex; align-items: center; gap: 6px; margin: 15px 0 0; color: #8b9aa3; font-size: 11px; line-height: 1.6; }.launch-note .anticon { color: #b28a4e; }.launch-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 15px; }.launch-two-col .ant-select { width: 100%; }

.activity-list, .apk-list { display: flex; flex-direction: column; gap: 5px; margin-top: 15px; }.activity-row { display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 8px; border: 0; border-radius: 8px; background: transparent; color: inherit; text-align: left; cursor: pointer; }.activity-row:hover { background: #f4f8f8; }.activity-mark, .apk-mark { display: grid; flex: 0 0 auto; width: 28px; height: 28px; place-items: center; border-radius: 8px; background: #e8f7f6; color: #208b8b; font-size: 13px; }.activity-mark.activity-special { background: #fff0e9; color: #d86f48; }.activity-main, .apk-main { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.activity-main strong, .apk-main strong { overflow: hidden; color: #2a4656; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.activity-main small, .apk-main small { overflow: hidden; color: #91a0a8; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.activity-status { font-size: 10px; font-weight: 750; white-space: nowrap; }.activity-status-passed, .activity-status-completed { color: #229276; }.activity-status-failed, .activity-status-error { color: #ce6558; }.activity-status-running, .activity-status-pending { color: #b67a2f; }.activity-status-stopped, .activity-status-cancelled { color: #80909a; }
.apk-row { display: flex; align-items: center; gap: 10px; padding: 8px; border-bottom: 1px solid #eef2f3; }.apk-row:last-child { border-bottom: 0; }.apk-mark { background: #edf2ff; color: #6875c5; }.apk-code { color: #a0abb1; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; }.compatibility-strip { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 14px; padding-top: 13px; border-top: 1px solid #edf1f2; }.strip-label { display: inline-flex; align-items: center; gap: 5px; margin-right: 4px; color: #71828c; font-size: 10px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }.compatibility-chip { padding: 4px 7px; border-radius: 5px; background: #f1f5f6; color: #72858f; font-size: 10px; }.compatibility-empty { color: #9ba8af; font-size: 10px; }
.preview-stage { display: flex; min-height: 480px; align-items: center; justify-content: center; border-radius: 8px; background: #111c25; }.preview-stage img { display: block; max-width: 100%; max-height: 560px; object-fit: contain; }.preview-footer { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 12px; color: #85939c; font-size: 11px; }.preview-footer > span { display: inline-flex; align-items: center; gap: 7px; }.preview-footer .live-dot { width: 6px; height: 6px; box-shadow: none; }

@media (max-width: 1050px) { .app-hero { flex-direction: column; }.hero-controls { flex-basis: auto; width: min(100%, 360px); }.signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.lower-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .workspace-grid { display: block; }.launch-panel { margin-top: 16px; }.app-hero { padding: 23px 20px; }.device-panel, .launch-panel, .activity-panel, .asset-panel { padding: 17px; }.launch-two-col { grid-template-columns: 1fr; }.signal-grid { gap: 8px; }.signal-card { min-height: 100px; padding: 14px; }.signal-card strong { font-size: 23px; }.launch-signal { display: none; } }
@media (prefers-reduced-motion: reduce) { .device-row { transition: none; } }
</style>
