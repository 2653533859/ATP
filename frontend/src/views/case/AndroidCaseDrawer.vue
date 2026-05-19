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
              <a-select-option value="smoke">smoke</a-select-option>
              <a-select-option value="core">core</a-select-option>
              <a-select-option value="regression">regression</a-select-option>
              <a-select-option value="extended">extended</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.filters.automation_status')">
            <a-select v-model:value="form.automation_status">
              <a-select-option value="manual">manual</a-select-option>
              <a-select-option value="semi_auto">semi_auto</a-select-option>
              <a-select-option value="auto">auto</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

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

      <a-divider orientation="left">{{ t('case.detail.standard_steps') }}</a-divider>
      <CaseStepEditor v-model="managementSteps" />

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
        <AndroidStepEditor v-model="lowcodeSteps" />
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

          <div class="script-actions">
            <a-button :loading="savingScript" :disabled="!scriptContent.trim()" @click="handleSaveScript">
              {{ t('case.drawer.save_script') }}
            </a-button>
          </div>
        </template>
      </template>
    </a-form>

    <template #footer>
      <a-space style="float: right">
        <a-button @click="emit('close')">{{ t('common.cancel') }}</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">
          {{ localCaseId ? t('case.drawer.save_config') : t('case.drawer.create_case') }}
        </a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { CheckCircleOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { apkApi, caseApi, deviceApi, scriptApi, type CaseStepItem } from '@/api'
import CaseStepEditor from '@/components/case/CaseStepEditor.vue'
import AndroidStepEditor from '@/components/common/AndroidStepEditor.vue'
import MonacoEditor from '@/components/common/MonacoEditor.vue'

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

const cfg = reactive({
  device_serial: undefined as string | undefined,
  apk_id: undefined as number | undefined,
  timeout: 120,
})

const devices = ref<Array<{ serial: string; status: string; brand: string; model: string }>>([])
const devicesLoading = ref(false)
const apks = ref<Array<{ id: number; filename: string; version_name?: string; object_name?: string }>>([])
const apksLoading = ref(false)
const apkMap = ref<Record<number, string>>({})

const lowcodeSteps = ref<AndroidStepDef[]>([])
const managementSteps = ref<CaseStepItem[]>([])

const scriptContent = ref('')
const scriptPath = ref<string | null>(null)
const uploading = ref(false)
const savingScript = ref(false)
const loadingScript = ref(false)
const initSeq = ref(0)

function resolveEditMode(config: Record<string, unknown>) {
  if (Array.isArray(config.steps)) {
    return 'lowcode' as const
  }
  if (typeof config.script_path === 'string' && config.script_path) {
    return 'script' as const
  }
  return 'lowcode' as const
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
  cfg.device_serial = undefined
  cfg.apk_id = undefined
  cfg.timeout = 120
  lowcodeSteps.value = []
  managementSteps.value = []
  scriptContent.value = ''
  scriptPath.value = null
}

async function loadDevices() {
  devicesLoading.value = true
  try {
    devices.value = await deviceApi.list() as Array<{ serial: string; status: string; brand: string; model: string }>
  } catch {
    devices.value = []
  } finally {
    devicesLoading.value = false
  }
}

async function loadApks() {
  apksLoading.value = true
  try {
    const routeProjectId = Number(route.params.projectId || route.query.project_id)
    const projectId = props.projectId ?? (Number.isFinite(routeProjectId) ? routeProjectId : undefined)
    apks.value = await apkApi.list(projectId ? { project_id: projectId } : undefined) as Array<{ id: number; filename: string; version_name?: string; object_name?: string }>
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
  } catch {
    scriptContent.value = ''
  } finally {
    loadingScript.value = false
  }
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
      managementSteps.value = detail.steps ?? []

      const config = detail.config ?? {}
      cfg.device_serial = typeof config.device_serial === 'string' ? config.device_serial : undefined
      cfg.apk_id = typeof config.apk_id === 'number' ? config.apk_id : undefined
      cfg.timeout = typeof config.timeout === 'number' ? config.timeout : 120
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

function buildConfig() {
  const config: Record<string, unknown> = { timeout: cfg.timeout }
  if (cfg.device_serial) {
    config.device_serial = cfg.device_serial
  }
  if (cfg.apk_id) {
    config.apk_id = cfg.apk_id
    config.apk_object_name = apkMap.value[cfg.apk_id]
  }
  if (editMode.value === 'lowcode') {
    config.steps = lowcodeSteps.value
  } else if (scriptPath.value) {
    config.script_path = scriptPath.value
  }
  return config
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
      config: buildConfig(),
    }

    if (isEdit.value && localCaseId.value) {
      await caseApi.update(localCaseId.value, payload)
      message.success(t('common.success'))
      emit('saved')
      emit('close')
      return
    }

    const newCase = await caseApi.create(payload)
    localCaseId.value = newCase.id
    isEdit.value = true
    message.success(t('case.drawer.msg.case_created'))
    emit('saved')
    if (editMode.value === 'lowcode') {
      emit('close')
    }
  } catch (error) {
    message.error(String(error ?? t('case.drawer.msg.save_failed')))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.muted {
  color: #999;
}

.mode-hint {
  margin-left: 12px;
  color: #999;
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
