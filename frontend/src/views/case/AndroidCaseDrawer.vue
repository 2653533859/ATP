<template>
  <a-drawer
    :open="open"
    :title="isEdit ? t('case.drawer.android.edit_title') : t('case.drawer.android.new_title')"
    width="960"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <a-divider orientation="left">{{ t('case.detail.basic_info') }}</a-divider>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item :label="t('case.drawer.case_name')" name="name" :rules="[{ required: true, message: t('case.drawer.msg.name_required') }]">
            <a-input v-model:value="form.name" :placeholder="t('case.drawer.case_name')" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.detail.tags')">
            <a-select v-model:value="form.tags" mode="tags" :placeholder="t('case.drawer.tags_placeholder_simple')" :token-separators="[',']" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('case.drawer.android.device_matrix')">
        <a-switch v-model:checked="deviceMatrixEnabled" />
        <span class="mode-hint">{{ t('case.drawer.android.device_matrix_hint') }}</span>
      </a-form-item>
      <a-form-item v-if="deviceMatrixEnabled" :label="t('case.drawer.android.device_group')">
        <a-select v-model:value="cfg.device_group_id" allow-clear :placeholder="t('case.drawer.android.device_group_placeholder')" @change="applyDeviceGroup">
          <a-select-option v-for="group in deviceGroups" :key="group.id" :value="group.id">
            {{ group.name }}（{{ group.devices.length }}）
          </a-select-option>
        </a-select>
      </a-form-item>
      <div v-if="deviceMatrixEnabled" class="device-matrix">
        <a-space v-for="(variant, index) in cfg.device_matrix" :key="index" style="display: flex; margin-bottom: 8px">
          <a-select v-model:value="variant.serial" :placeholder="t('case.drawer.android.select_device')" style="min-width: 360px">
            <a-select-option v-for="device in devices" :key="device.serial" :value="device.serial">
              {{ device.brand }} {{ device.model }} · Android {{ device.os_version || '-' }} ({{ device.serial }})
            </a-select-option>
          </a-select>
          <a-button danger @click="removeDeviceVariant(index)">{{ t('common.delete') }}</a-button>
        </a-space>
        <a-button size="small" @click="addDeviceVariant">{{ t('case.drawer.android.device_matrix_add') }}</a-button>
      </div>
      <a-form-item :label="t('case.drawer.android.record_video')">
        <a-switch v-model:checked="cfg.record_video" />
        <span class="mode-hint">{{ t('case.drawer.android.record_video_hint') }}</span>
      </a-form-item>

      <a-form-item :label="t('case.drawer.scenario_summary')">
        <a-textarea v-model:value="form.summary" :rows="2" :placeholder="t('case.drawer.scenario_summary_placeholder')" />
      </a-form-item>

      <a-form-item :label="t('common.description')">
        <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('case.drawer.optional')" />
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item :label="t('case.filters.priority')">
            <a-select v-model:value="form.priority">
              <a-select-option value="P0">P0</a-select-option>
              <a-select-option value="P1">P1</a-select-option>
              <a-select-option value="P2">P2</a-select-option>
              <a-select-option value="P3">P3</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.drawer.case_level')">
            <a-select v-model:value="form.case_level">
              <a-select-option value="smoke">{{ t('case.levels.smoke') }}</a-select-option>
              <a-select-option value="core">{{ t('case.levels.core') }}</a-select-option>
              <a-select-option value="regression">{{ t('case.levels.regression') }}</a-select-option>
              <a-select-option value="extended">{{ t('case.levels.extended') }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.filters.automation_status')">
            <a-select v-model:value="form.automation_status">
              <a-select-option value="manual">{{ t('case.automation_statuses.manual') }}</a-select-option>
              <a-select-option value="semi_auto">{{ t('case.automation_statuses.semi_auto') }}</a-select-option>
              <a-select-option value="auto">{{ t('case.automation_statuses.auto') }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <CaseDatasetBinding
        v-model="datasetBinding"
        :project-id="projectId"
      />

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('case.detail.preconditions')">
            <a-select v-model:value="form.preconditions" mode="tags" :placeholder="t('case.drawer.conditions_placeholder')" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('case.detail.postconditions')">
            <a-select v-model:value="form.postconditions" mode="tags" :placeholder="t('case.drawer.conditions_placeholder')" />
          </a-form-item>
        </a-col>
      </a-row>

      <div class="standard-step-heading">
        <a-divider orientation="left">{{ t('case.detail.standard_steps') }}</a-divider>
        <a-button
          v-if="editMode === 'lowcode' && lowcodeSteps.length"
          size="small"
          @click="regenerateStandardSteps"
        >
          {{ t('case.android_standard_steps.regenerate') }}
        </a-button>
      </div>
      <a-alert
        v-if="editMode === 'lowcode' && lowcodeSteps.length"
        :message="standardStepsDirty
          ? t('case.android_standard_steps.manual_hint')
          : t('case.android_standard_steps.auto_hint')"
        type="info"
        show-icon
        closable
        style="margin-bottom: 12px"
      />
      <CaseStepEditor
        :model-value="managementSteps"
        @update:modelValue="handleManagementStepsUpdate"
      />

      <a-divider orientation="left">{{ t('case.detail.execution_config') }}</a-divider>
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item :label="t('case.drawer.android.target_device')">
            <a-select
              v-model:value="cfg.device_serial"
              :placeholder="t('case.drawer.android.select_device')"
              allow-clear
              style="width: 100%"
              :loading="devicesLoading"
            >
              <a-select-option v-for="device in devices" :key="device.serial" :value="device.serial">
                <a-badge :status="device.status === 'online' ? 'success' : 'default'" />
                {{ device.brand }} {{ device.model }} ({{ device.serial }})
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.drawer.android.install_apk')">
            <a-select
              v-model:value="cfg.apk_id"
              :placeholder="t('case.drawer.android.no_apk')"
              allow-clear
              style="width: 100%"
              :loading="apksLoading"
            >
              <a-select-option v-for="apk in apks" :key="apk.id" :value="apk.id">
                {{ apk.filename }}
                <span v-if="apk.version_name" class="muted"> v{{ apk.version_name }}</span>
                <span v-if="apk.package_name" class="muted"> · {{ apk.package_name }}</span>
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.drawer.timeout_seconds')">
            <a-input-number v-model:value="cfg.timeout" :min="10" :max="600" style="width: 100%" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-divider orientation="left">{{ t('case.drawer.automation_content') }}</a-divider>
      <a-form-item :label="t('case.drawer.edit_mode')">
        <a-radio-group v-model:value="editMode" button-style="solid">
          <a-radio-button value="lowcode">{{ t('case.drawer.lowcode') }}</a-radio-button>
          <a-radio-button value="script">{{ t('case.drawer.script') }}</a-radio-button>
        </a-radio-group>
        <span class="mode-hint">
          {{ editMode === 'lowcode' ? t('case.drawer.android.lowcode_hint') : t('case.drawer.android.script_hint') }}
        </span>
      </a-form-item>

      <template v-if="editMode === 'lowcode'">
        <div class="android-script-toolbar">
          <a-button size="small" :disabled="!lowcodeSteps.length" @click="openGeneratedScriptPreview">
            <CodeOutlined /> {{ t('case.drawer.generate_script') }}
          </a-button>
          <span>{{ t('case.drawer.android.generate_script_hint') }}</span>
        </div>
        <a-alert
          v-if="selectedDeviceId && editorLeaseLoading"
          :message="t('case.android_editor.lease_acquiring')"
          type="info"
          show-icon
          style="margin-bottom: 12px"
        />
        <a-alert
          v-else-if="selectedDeviceId && !editorLease"
          :message="t('case.android_editor.lease_required')"
          type="warning"
          show-icon
          style="margin-bottom: 12px"
        />
        <AndroidStepEditor
          v-model="lowcodeSteps"
          :device-id="selectedDeviceId"
          :lease-token="editorLease?.lease_token"
          :apk-options="apks"
        />
      </template>

      <template v-else>
        <a-alert
          v-if="!localCaseId"
          :message="t('case.drawer.android.save_before_script')"
          type="info"
          show-icon
          style="margin-bottom: 0"
        />

        <template v-else>
          <div class="script-toolbar">
            <a-upload :before-upload="handleUpload" :show-upload-list="false" accept=".py">
              <a-button :loading="uploading" size="small">
                <UploadOutlined /> {{ t('case.drawer.upload_script') }}
              </a-button>
            </a-upload>
            <span v-if="scriptPath" class="script-path-ok">
              <CheckCircleOutlined /> {{ scriptPath }}
            </span>
            <span v-else class="script-path-empty">{{ t('case.drawer.no_script') }}</span>
            <a-tag color="green" class="script-tag">uiautomator2 + pytest</a-tag>
          </div>

          <a-spin :spinning="loadingScript">
            <MonacoEditor v-model="scriptContent" height="420px" language="python" />
          </a-spin>

          <a-collapse style="margin-top: 12px">
            <a-collapse-panel key="requirements" :header="t('case.drawer.script_requirements')">
              <a-alert :message="t('case.drawer.script_requirements_hint')" type="info" show-icon style="margin-bottom: 8px" />
              <a-textarea v-model:value="requirementsContent" :rows="5" placeholder="requests==2.32.3" />
              <a-button :loading="savingRequirements" style="margin-top: 8px" @click="handleSaveRequirements">
                {{ t('case.drawer.save_requirements') }}
              </a-button>
            </a-collapse-panel>
          </a-collapse>

          <div class="script-actions">
            <a-button :loading="savingScript" :disabled="!scriptContent.trim()" @click="handleSaveScript">
              {{ t('case.drawer.save_script') }}
            </a-button>
          </div>
        </template>
      </template>
    </a-form>

    <GeneratedScriptModal
      :open="scriptPreviewOpen"
      :content="generatedScriptContent"
      kind="android"
      :saving="savingGeneratedScript"
      @close="scriptPreviewOpen = false"
      @save="handleSaveGeneratedScript"
    />

    <template #footer>
      <a-space style="float: right">
        <a-button @click="handleClose">{{ t('common.cancel') }}</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">
          {{ localCaseId ? t('case.drawer.save_config') : t('case.drawer.create_case') }}
        </a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { CheckCircleOutlined, CodeOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { apkApi, caseApi, deviceApi, type DeviceGroupItem, type DeviceItem, type DeviceLeaseItem, scriptApi, type CaseStepItem } from '@/api'
import CaseStepEditor from '@/components/case/CaseStepEditor.vue'
import { buildAndroidStandardSteps } from '@/utils/androidStandardSteps'
import AndroidStepEditor from '@/components/common/AndroidStepEditor.vue'
import MonacoEditor from '@/components/common/MonacoEditor.vue'
import GeneratedScriptModal from '@/components/common/GeneratedScriptModal.vue'
import { generateAndroidPythonScript } from '@/utils/pythonScriptGenerator'
import CaseDatasetBinding from '@/components/common/CaseDatasetBinding.vue'
import {
  buildCaseDatasetConfig,
  createCaseDatasetBinding,
  type CaseDatasetBinding as CaseDatasetBindingState,
  type DatasetExecutionStrategy,
} from '@/types/caseDataset'

interface AndroidStepDef {
  action: string
  name: string
  params: Record<string, unknown>
}

const route = useRoute()
const { t } = useI18n()

const props = defineProps<{
  open: boolean
  moduleId: number | null
  projectId?: number | null
  editCase?: { id: number } | null
}>()

const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const formRef = ref()
const localCaseId = ref<number | null>(null)
const editMode = ref<'lowcode' | 'script'>('lowcode')

const form = reactive({
  name: '',
  summary: '',
  description: '',
  tags: [] as string[],
  priority: 'P2' as 'P0' | 'P1' | 'P2' | 'P3',
  case_level: 'regression' as 'smoke' | 'core' | 'regression' | 'extended',
  automation_status: 'auto' as 'manual' | 'semi_auto' | 'auto',
  preconditions: [] as string[],
  postconditions: [] as string[],
})
const datasetBinding = ref<CaseDatasetBindingState>(createCaseDatasetBinding())

const cfg = reactive({
  device_serial: undefined as string | undefined,
  apk_id: undefined as number | undefined,
  timeout: 120,
  device_group_id: undefined as number | undefined,
  device_matrix: [] as Array<{ serial: string }>,
  record_video: false,
})
const deviceMatrixEnabled = ref(false)

const devices = ref<DeviceItem[]>([])
const deviceGroups = ref<DeviceGroupItem[]>([])
const devicesLoading = ref(false)
const editorLease = ref<DeviceLeaseItem | null>(null)
const editorLeaseLoading = ref(false)
let editorLeaseSeq = 0
let editorLeaseHeartbeatTimer: ReturnType<typeof setInterval> | null = null
const apks = ref<Array<{ id: number; filename: string; package_name?: string | null; version_name?: string; object_name?: string }>>([])
const apksLoading = ref(false)
const apkMap = ref<Record<number, string>>({})

const lowcodeSteps = ref<AndroidStepDef[]>([])
const managementSteps = ref<CaseStepItem[]>([])
const standardStepsDirty = ref(false)
const syncingStandardSteps = ref(false)
const scriptPreviewOpen = ref(false)
const generatedScriptContent = ref('')
const pendingGeneratedScript = ref('')
const savingGeneratedScript = ref(false)

const scriptContent = ref('')
const scriptPath = ref<string | null>(null)
const uploading = ref(false)
const savingScript = ref(false)
const loadingScript = ref(false)
const requirementsContent = ref('')
const savingRequirements = ref(false)
const initSeq = ref(0)

const selectedDeviceId = computed(() =>
  devices.value.find((device) => device.serial === cfg.device_serial)?.id ?? null,
)

function resolveEditMode(config: Record<string, unknown>) {
  if (Array.isArray(config.steps)) {
    return 'lowcode' as const
  }
  if (typeof config.script_path === 'string' && config.script_path) {
    return 'script' as const
  }
  return 'lowcode' as const
}

function resolveDatasetStrategy(value: unknown): DatasetExecutionStrategy {
  return value === 'random' || value === 'fixed_count' || value === 'cartesian' || value === 'pairwise'
    ? value
    : 'sequential'
}

function resetDrawerState() {
  isEdit.value = false
  localCaseId.value = null
  editMode.value = 'lowcode'
  form.name = ''
  form.summary = ''
  form.description = ''
  form.tags = []
  form.priority = 'P2'
  form.case_level = 'regression'
  form.automation_status = 'auto'
  form.preconditions = []
  form.postconditions = []
  datasetBinding.value = createCaseDatasetBinding()
  cfg.device_serial = undefined
  cfg.device_group_id = undefined
  cfg.apk_id = undefined
  cfg.timeout = 120
  cfg.device_matrix = []
  deviceMatrixEnabled.value = false
  cfg.record_video = false
  lowcodeSteps.value = []
  managementSteps.value = []
  standardStepsDirty.value = false
  syncingStandardSteps.value = false
  scriptPreviewOpen.value = false
  generatedScriptContent.value = ''
  pendingGeneratedScript.value = ''
  savingGeneratedScript.value = false
  scriptContent.value = ''
  scriptPath.value = null
}

async function loadDevices() {
  devicesLoading.value = true
  try {
    const [deviceItems, groupItems] = await Promise.all([deviceApi.list(), deviceApi.groups()])
    devices.value = deviceItems
    deviceGroups.value = groupItems
  } catch {
    devices.value = []
    deviceGroups.value = []
  } finally {
    devicesLoading.value = false
  }
}

async function loadApks() {
  apksLoading.value = true
  try {
    const routeProjectId = Number(route.params.projectId || route.query.project_id)
    const projectId = props.projectId ?? (Number.isFinite(routeProjectId) ? routeProjectId : undefined)
    apks.value = await apkApi.list(projectId ? { project_id: projectId } : undefined) as Array<{ id: number; filename: string; package_name?: string | null; version_name?: string; object_name?: string }>
    apkMap.value = apks.value.reduce<Record<number, string>>((acc, item) => {
      if (item.object_name) {
        acc[item.id] = item.object_name
      }
      return acc
    }, {})
  } catch {
    apks.value = []
    apkMap.value = {}
  } finally {
    apksLoading.value = false
  }
}

async function loadScript() {
  if (!localCaseId.value) {
    return
  }
  loadingScript.value = true
  try {
    const response = await scriptApi.get(localCaseId.value)
    scriptContent.value = response.exists ? response.content : ''
    const requirements = await scriptApi.getRequirements(localCaseId.value)
    requirementsContent.value = requirements.exists ? requirements.content : ''
  } catch {
    scriptContent.value = ''
  } finally {
    loadingScript.value = false
  }
}

async function handleSaveRequirements() {
  if (!localCaseId.value) return
  savingRequirements.value = true
  try {
    const result = await scriptApi.saveRequirements(localCaseId.value, requirementsContent.value)
    requirementsContent.value = result.content
    message.success(t('case.drawer.msg.requirements_saved'))
  } catch (error: unknown) {
    message.error(String(error ?? t('case.drawer.msg.save_failed')))
  } finally {
    savingRequirements.value = false
  }
}

async function releaseEditorLease() {
  const current = editorLease.value
  editorLease.value = null
  editorLeaseLoading.value = false
  stopEditorLeaseHeartbeat()
  if (!current?.lease_token) return
  try {
    await deviceApi.releaseLease(current.device_id, current.lease_token)
  } catch {
    // 关闭抽屉时租约释放失败由后台过期回收，不阻塞表单关闭。
  }
}

function stopEditorLeaseHeartbeat() {
  if (editorLeaseHeartbeatTimer !== null) {
    clearInterval(editorLeaseHeartbeatTimer)
    editorLeaseHeartbeatTimer = null
  }
}

function startEditorLeaseHeartbeat() {
  stopEditorLeaseHeartbeat()
  editorLeaseHeartbeatTimer = setInterval(() => { void heartbeatEditorLease() }, 240000)
}

async function heartbeatEditorLease() {
  const current = editorLease.value
  if (!current?.lease_token) return
  try {
    const refreshed = await deviceApi.heartbeatLease(current.device_id, current.lease_token)
    editorLease.value = { ...refreshed, lease_token: current.lease_token }
  } catch {
    stopEditorLeaseHeartbeat()
    editorLease.value = null
    message.warning(t('case.android_editor.lease_expired'))
  }
}

async function syncEditorLease(deviceId: number | null) {
  const seq = ++editorLeaseSeq
  await releaseEditorLease()
  if (!props.open || !deviceId || seq !== editorLeaseSeq) return

  editorLeaseLoading.value = true
  try {
    const lease = await deviceApi.acquireLease(deviceId, {
      ttl_seconds: 900,
      owner_label: 'android-case-editor',
    })
    if (seq !== editorLeaseSeq || !props.open) {
      if (lease.lease_token) await deviceApi.releaseLease(lease.device_id, lease.lease_token)
      return
    }
    editorLease.value = lease
    startEditorLeaseHeartbeat()
  } catch (error) {
    if (seq === editorLeaseSeq) {
      editorLease.value = null
      message.warning(String(error ?? t('case.android_editor.lease_failed')))
    }
  } finally {
    if (seq === editorLeaseSeq) editorLeaseLoading.value = false
  }
}

async function handleClose() {
  ++editorLeaseSeq
  await releaseEditorLease()
  emit('close')
}

watch(
  () => props.open,
  async (opened) => {
    if (!opened) {
      return
    }

    const seq = ++initSeq.value
    resetDrawerState()
    void loadDevices()
    void loadApks()

    if (!props.editCase?.id) {
      return
    }

    try {
      const detail = await caseApi.get(props.editCase.id)
      if (seq !== initSeq.value || !props.open) {
        return
      }
      isEdit.value = true
      localCaseId.value = detail.id
      form.name = detail.name
      form.summary = detail.summary ?? detail.name
      form.description = detail.description ?? ''
      form.tags = detail.tags ?? []
      form.priority = detail.priority ?? 'P2'
      form.case_level = detail.case_level ?? 'regression'
      form.automation_status = detail.automation_status ?? 'auto'
      form.preconditions = detail.preconditions ?? []
      form.postconditions = detail.postconditions ?? []
      const config = detail.config ?? {}
      datasetBinding.value = {
        ...createCaseDatasetBinding(),
        datasetId: detail.dataset_id ?? null,
        datasetVersion: detail.dataset_version ?? null,
        strictSchema: config.dataset_strict_schema === true,
        strategy: resolveDatasetStrategy(config.dataset_strategy),
        fixedCount: config.dataset_fixed_count == null ? null : Number(config.dataset_fixed_count),
        seed: config.dataset_seed == null ? null : Number(config.dataset_seed),
        maxIterations: Number(config.dataset_max_iterations ?? 1000),
        combinationFields: Array.isArray(config.dataset_combination_fields) ? config.dataset_combination_fields.map(String) : [],
        redactFields: Array.isArray(config.dataset_redact_fields) ? config.dataset_redact_fields.map(String) : [],
      }
      managementSteps.value = detail.steps ?? []
      standardStepsDirty.value = managementSteps.value.length > 0

      cfg.device_serial = typeof config.device_serial === 'string' ? config.device_serial : undefined
      cfg.device_group_id = typeof config.device_group_id === 'number' ? config.device_group_id : undefined
      cfg.apk_id = typeof config.apk_id === 'number' ? config.apk_id : undefined
      cfg.timeout = typeof config.timeout === 'number' ? config.timeout : 120
      cfg.record_video = config.record_video === true
      cfg.device_matrix = Array.isArray(config.device_matrix)
        ? config.device_matrix
          .filter((item): item is { serial: string } => Boolean(item && typeof item === 'object' && typeof (item as Record<string, unknown>).serial === 'string'))
          .map((item) => ({ serial: item.serial }))
        : []
      deviceMatrixEnabled.value = cfg.device_matrix.length > 0
      scriptPath.value = typeof config.script_path === 'string' ? config.script_path : null
      lowcodeSteps.value = Array.isArray(config.steps) ? (config.steps as AndroidStepDef[]) : []
      editMode.value = resolveEditMode(config)
    } catch {
      if (seq !== initSeq.value || !props.open) {
        return
      }
      message.error(t('case.detail.msg.load_failed'))
      emit('close')
    }
  },
)

watch(
  [selectedDeviceId, () => props.open, editMode],
  ([deviceId, opened, mode]) => {
    if (!opened || mode !== 'lowcode' || !deviceId) {
      ++editorLeaseSeq
      editorLeaseLoading.value = false
      void releaseEditorLease()
      return
    }
    void syncEditorLease(deviceId)
  },
  { immediate: true },
)

watch(
  lowcodeSteps,
  () => {
    if (!props.open || editMode.value !== 'lowcode' || standardStepsDirty.value || !lowcodeSteps.value.length) {
      return
    }
    regenerateStandardSteps()
  },
  { deep: true },
)

function regenerateStandardSteps() {
  syncingStandardSteps.value = true
  managementSteps.value = buildAndroidStandardSteps(lowcodeSteps.value, t)
  standardStepsDirty.value = false
  syncingStandardSteps.value = false
}

function handleManagementStepsUpdate(steps: CaseStepItem[]) {
  managementSteps.value = steps
  if (!syncingStandardSteps.value) {
    standardStepsDirty.value = true
  }
}

watch(editMode, async (mode) => {
  if (!props.open) {
    return
  }
  if (mode === 'script') {
    await loadScript()
  } else {
    scriptContent.value = ''
  }
})

async function handleUpload(file: File) {
  if (!localCaseId.value) {
    return false
  }
  uploading.value = true
  try {
    const response = await scriptApi.upload(localCaseId.value, file) as { script_path?: string }
    scriptPath.value = response.script_path ?? null
    message.success(t('case.drawer.msg.script_uploaded'))
    await loadScript()
  } catch (error) {
    message.error(String(error ?? t('case.drawer.msg.upload_failed')))
  } finally {
    uploading.value = false
  }
  return false
}

async function handleSaveScript() {
  if (!localCaseId.value || !scriptContent.value.trim()) {
    return
  }
  savingScript.value = true
  try {
    const response = await scriptApi.saveContent(localCaseId.value, scriptContent.value) as { script_path?: string }
    scriptPath.value = response.script_path ?? null
    message.success(t('case.drawer.msg.script_saved'))
  } catch (error) {
    message.error(String(error ?? t('case.drawer.msg.save_failed')))
  } finally {
    savingScript.value = false
  }
}

function openGeneratedScriptPreview() {
  if (!lowcodeSteps.value.length) {
    message.warning(t('case.drawer.android.msg.automation_step_required'))
    return
  }
  generatedScriptContent.value = generateAndroidPythonScript(lowcodeSteps.value)
  scriptPreviewOpen.value = true
}

async function handleSaveGeneratedScript(content: string) {
  if (!content.trim()) return
  generatedScriptContent.value = content
  savingGeneratedScript.value = true
  try {
    if (!localCaseId.value) {
      pendingGeneratedScript.value = content
      scriptPreviewOpen.value = false
      message.info(t('case.drawer.script_preview.save_note'))
      return
    }

    const response = await scriptApi.saveContent(localCaseId.value, content) as { script_path?: string }
    scriptPath.value = response.script_path ?? null
    scriptContent.value = content
    scriptPreviewOpen.value = false
    message.success(t('case.drawer.msg.script_saved'))
  } catch (error) {
    message.error(String(error ?? t('case.drawer.msg.save_failed')))
  } finally {
    savingGeneratedScript.value = false
  }
}

function buildConfig() {
  const config: Record<string, unknown> = { ...buildCaseDatasetConfig(datasetBinding.value), timeout: cfg.timeout }
  if (cfg.record_video) {
    config.record_video = true
  }
  if (deviceMatrixEnabled.value && cfg.device_matrix.length) {
    config.device_matrix = cfg.device_matrix.filter((item) => item.serial.trim())
    if (cfg.device_group_id) config.device_group_id = cfg.device_group_id
  } else if (cfg.device_serial) {
    config.device_serial = cfg.device_serial
  }
  if (cfg.apk_id) {
    config.apk_id = cfg.apk_id
    config.apk_object_name = apkMap.value[cfg.apk_id]
  }
  if (editMode.value === 'lowcode') {
    config.steps = lowcodeSteps.value
    if (scriptPath.value) {
      config.script_path = scriptPath.value
    }
  } else if (scriptPath.value) {
    config.script_path = scriptPath.value
  }
  return config
}

function addDeviceVariant() {
  cfg.device_matrix.push({ serial: cfg.device_serial || devices.value[0]?.serial || '' })
}

function applyDeviceGroup(groupId: unknown) {
  const group = deviceGroups.value.find((item) => item.id === Number(groupId))
  if (!group) return
  cfg.device_matrix = group.devices.map((device) => ({ serial: device.serial }))
}

function removeDeviceVariant(index: number) {
  cfg.device_matrix.splice(index, 1)
  if (!cfg.device_matrix.length) deviceMatrixEnabled.value = false
}

async function handleSave() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  if (editMode.value === 'lowcode' && lowcodeSteps.value.length === 0) {
    message.warning(t('case.drawer.android.msg.automation_step_required'))
    return
  }

  if (managementSteps.value.length === 0) {
    message.warning(t('case.drawer.android.msg.standard_step_required'))
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.name,
      summary: form.summary || form.name,
      description: form.description,
      case_type: 'android' as const,
      tags: form.tags,
      priority: form.priority,
      case_level: form.case_level,
      automation_status: form.automation_status,
      preconditions: form.preconditions,
      postconditions: form.postconditions,
      steps: managementSteps.value,
      module_id: props.moduleId ?? undefined,
      dataset_id: datasetBinding.value.datasetId,
      dataset_version: datasetBinding.value.datasetVersion,
      config: buildConfig(),
    }

    if (isEdit.value && localCaseId.value) {
      await caseApi.update(localCaseId.value, payload)
      message.success(t('common.success'))
      emit('saved')
      await handleClose()
      return
    }

    const newCase = await caseApi.create(payload)
    localCaseId.value = newCase.id
    isEdit.value = true
    if (pendingGeneratedScript.value) {
      try {
        const response = await scriptApi.saveContent(newCase.id, pendingGeneratedScript.value) as { script_path?: string }
        scriptPath.value = response.script_path ?? null
        scriptContent.value = pendingGeneratedScript.value
        pendingGeneratedScript.value = ''
        message.success(t('case.drawer.msg.script_saved'))
      } catch (error) {
        message.error(String(error ?? t('case.drawer.msg.save_failed')))
      }
    }
    message.success(t('case.drawer.msg.case_created'))
    emit('saved')
    if (editMode.value === 'lowcode') {
      await handleClose()
    }
  } catch (error) {
    message.error(String(error ?? t('case.drawer.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

onBeforeUnmount(() => {
  ++editorLeaseSeq
  void releaseEditorLease()
})
</script>

<style scoped>
.muted {
  color: #999;
}

.standard-step-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.standard-step-heading :deep(.ant-divider) {
  flex: 1;
  margin: 16px 0;
}

.mode-hint {
  margin-left: 12px;
  color: #999;
  font-size: 12px;
}

.android-script-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: -4px 0 12px;
}

.android-script-toolbar span {
  color: #98a2b3;
  font-size: 12px;
}

.script-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.script-path-ok {
  color: #52c41a;
  font-size: 13px;
}

.script-path-empty {
  color: #999;
  font-size: 13px;
}

.script-tag {
  cursor: default;
  margin-left: auto;
}

.script-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}
</style>
