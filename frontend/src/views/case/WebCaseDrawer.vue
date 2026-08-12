<template>
  <a-drawer
    :open="open"
    :title="isEdit ? t('case.drawer.web.edit_title') : t('case.drawer.web.new_title')"
    width="960"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <a-divider orientation="left">{{ t('case.detail.basic_info') }}</a-divider>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item
            :label="t('case.drawer.case_name')"
            name="name"
            :rules="[{ required: true, message: t('case.drawer.msg.name_required') }]"
          >
            <a-input v-model:value="form.name" :placeholder="t('case.drawer.case_name')" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.detail.tags')">
            <a-select
              v-model:value="form.tags"
              mode="tags"
              :placeholder="t('case.drawer.tags_placeholder')"
              :token-separators="[',']"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('common.description')">
        <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('case.drawer.optional')" />
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('case.filters.priority')">
            <a-select v-model:value="form.priority">
              <a-select-option value="P0">P0</a-select-option>
              <a-select-option value="P1">P1</a-select-option>
              <a-select-option value="P2">P2</a-select-option>
              <a-select-option value="P3">P3</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('case.filters.level')">
            <a-select v-model:value="form.case_level">
              <a-select-option value="smoke">{{ t('case.levels.smoke') }}</a-select-option>
              <a-select-option value="core">{{ t('case.levels.core') }}</a-select-option>
              <a-select-option value="regression">{{ t('case.levels.regression') }}</a-select-option>
              <a-select-option value="extended">{{ t('case.levels.extended') }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-divider orientation="left">{{ t('case.detail.execution_config') }}</a-divider>
      <a-row :gutter="16">
        <a-col :span="6">
          <a-form-item :label="t('case.drawer.browser')">
            <a-select v-model:value="cfg.browser" style="width: 100%">
              <a-select-option value="chromium">Chromium</a-select-option>
              <a-select-option value="firefox">Firefox</a-select-option>
              <a-select-option value="webkit">WebKit</a-select-option>
            </a-select>
            <div style="margin-top: 6px; color: #999; font-size: 12px">
              {{ t('case.drawer.web.browser_hint') }}
            </div>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item :label="t('case.drawer.timeout_seconds')">
            <a-input-number
              v-model:value="cfg.timeout"
              :min="10"
              :max="600"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item :label="t('case.drawer.viewport_width')">
            <a-input-number
              v-model:value="cfg.viewportWidth"
              :min="320"
              :max="3840"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item :label="t('case.drawer.viewport_height')">
            <a-input-number
              v-model:value="cfg.viewportHeight"
              :min="240"
              :max="2160"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('case.drawer.headless')">
        <a-switch v-model:checked="cfg.headless" :checked-children="t('common.enabled')" :un-checked-children="t('common.disabled')" />
        <span style="margin-left: 8px; color: #999; font-size: 12px">
          {{ t('case.drawer.web.headless_hint') }}
        </span>
      </a-form-item>
      <a-form-item :label="t('case.drawer.web.matrix_label')">
        <a-switch v-model:checked="matrixEnabled" />
        <span style="margin-left: 8px; color: #999; font-size: 12px">{{ t('case.drawer.web.matrix_hint') }}</span>
      </a-form-item>
      <div v-if="matrixEnabled" class="matrix-editor">
        <div v-for="(variant, index) in matrixVariants" :key="index" class="matrix-row">
          <a-select v-model:value="variant.browser" style="width: 120px">
            <a-select-option value="chromium">Chromium</a-select-option>
            <a-select-option value="firefox">Firefox</a-select-option>
            <a-select-option value="webkit">WebKit</a-select-option>
          </a-select>
          <a-input-number v-model:value="variant.viewport.width" :min="320" :max="3840" style="width: 110px" />
          <a-input-number v-model:value="variant.viewport.height" :min="240" :max="2160" style="width: 110px" />
          <a-input v-model:value="variant.device" :placeholder="t('case.drawer.web.matrix_device_placeholder')" />
          <a-button danger type="text" :disabled="matrixVariants.length <= 1" @click="matrixVariants.splice(index, 1)">×</a-button>
        </div>
        <a-button size="small" type="dashed" @click="addMatrixVariant">{{ t('case.drawer.web.matrix_add') }}</a-button>
      </div>

      <a-divider orientation="left">{{ t('case.drawer.test_content') }}</a-divider>
      <a-form-item :label="t('case.drawer.edit_mode')">
        <a-radio-group v-model:value="editMode" button-style="solid">
          <a-radio-button value="lowcode">{{ t('case.drawer.lowcode') }}</a-radio-button>
          <a-radio-button value="script">{{ t('case.drawer.script') }}</a-radio-button>
        </a-radio-group>
        <span style="margin-left: 12px; color: #999; font-size: 12px">
          {{ editMode === 'lowcode' ? t('case.drawer.web.lowcode_hint') : t('case.drawer.web.script_hint') }}
        </span>
      </a-form-item>

      <template v-if="editMode === 'lowcode'">
        <div class="lowcode-toolbar">
          <a-space>
            <a-button size="small" @click="recorderOpen = true">
              {{ t('case.drawer.web.record_steps') }}
            </a-button>
            <a-button size="small" :disabled="!lowcodeSteps.length" @click="openGeneratedScriptPreview">
              <CodeOutlined /> {{ t('case.drawer.generate_script') }}
            </a-button>
          </a-space>
          <span>{{ t('case.drawer.web.record_hint') }}</span>
        </div>
        <LowcodeStepEditor v-model="lowcodeSteps" :project-id="projectId" />
      </template>

      <template v-else>
        <a-alert
          v-if="!localCaseId"
          :message="t('case.drawer.web.save_before_script')"
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
            <a-tooltip :title="t('case.drawer.web.script_tooltip')">
              <a-tag color="blue" style="cursor: default; margin-left: auto">pytest-playwright</a-tag>
            </a-tooltip>
          </div>

          <a-spin :spinning="loadingScript">
            <MonacoEditor
              v-model="scriptContent"
              height="420px"
              language="python"
            />
          </a-spin>

          <div style="margin-top: 8px; display: flex; justify-content: flex-end">
            <a-button
              :loading="savingScript"
              :disabled="!scriptContent.trim()"
              @click="handleSaveScript"
            >
              {{ t('case.drawer.save_script') }}
            </a-button>
          </div>
        </template>
      </template>
    </a-form>

    <WebRecorderModal
      :open="recorderOpen"
      :project-id="projectId"
      @close="recorderOpen = false"
      @recorded="handleRecordedSteps"
    />
    <GeneratedScriptModal
      :open="scriptPreviewOpen"
      :content="generatedScriptContent"
      kind="web"
      :saving="savingGeneratedScript"
      @close="scriptPreviewOpen = false"
      @save="handleSaveGeneratedScript"
    />

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
import { ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { CodeOutlined, UploadOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  caseApi,
  scriptApi,
  webAssetsApi,
  type CaseLevel,
  type CasePriority,
  type CaseSummaryItem,
  type WebElementAssetItem,
  type WebPageObjectItem,
} from '@/api'
import MonacoEditor from '@/components/common/MonacoEditor.vue'
import LowcodeStepEditor from '@/components/common/LowcodeStepEditor.vue'
import WebRecorderModal from '@/components/common/WebRecorderModal.vue'
import GeneratedScriptModal from '@/components/common/GeneratedScriptModal.vue'
import { generateWebPythonScript } from '@/utils/pythonScriptGenerator'

type LowcodeStep = {
  action: string
  name: string
  params: Record<string, unknown>
}

type WebCaseConfig = Record<string, unknown> & {
  browser?: string
  headless?: boolean
  timeout?: number
  viewport?: {
    width?: number
    height?: number
  }
  browser_matrix?: Array<{
    browser?: string
    viewport?: { width?: number; height?: number }
    device?: string
  }>
  script_path?: string
  steps?: LowcodeStep[]
}

const props = defineProps<{
  open: boolean
  moduleId: number | null
  projectId: number | null
  editCase?: CaseSummaryItem | null
}>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()

const isEdit = ref(false)
const saving = ref(false)
const formRef = ref()
const localCaseId = ref<number | null>(null)

const editMode = ref<'lowcode' | 'script'>('lowcode')

const form = reactive({
  name: '',
  description: '',
  tags: [] as string[],
  priority: 'P2' as CasePriority,
  case_level: 'regression' as CaseLevel,
})

const cfg = reactive({
  browser: 'chromium',
  headless: true,
  timeout: 60,
  viewportWidth: 1280,
  viewportHeight: 720,
})

type WebMatrixVariant = {
  browser: 'chromium' | 'firefox' | 'webkit'
  viewport: { width: number; height: number }
  device: string
}

const matrixEnabled = ref(false)
const matrixVariants = ref<WebMatrixVariant[]>([])

const lowcodeSteps = ref<LowcodeStep[]>([])
const recorderOpen = ref(false)
const scriptPreviewOpen = ref(false)
const generatedScriptContent = ref('')
const pendingGeneratedScript = ref('')
const savingGeneratedScript = ref(false)
const scriptElementAssets = ref<WebElementAssetItem[]>([])
const scriptPageObjects = ref<WebPageObjectItem[]>([])

// Script
const scriptContent = ref('')
const scriptPath = ref<string | null>(null)
const uploading = ref(false)
const savingScript = ref(false)
const loadingScript = ref(false)
const initSeq = ref(0)

function hasOwn(obj: object | null | undefined, key: string) {
  return Object.prototype.hasOwnProperty.call(obj ?? {}, key)
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

function resetDrawerState() {
  isEdit.value = false
  localCaseId.value = null
  form.name = ''
  form.description = ''
  form.tags = []
  form.priority = 'P2'
  form.case_level = 'regression'
  cfg.browser = 'chromium'
  cfg.headless = true
  cfg.timeout = 60
  cfg.viewportWidth = 1280
  cfg.viewportHeight = 720
  matrixEnabled.value = false
  matrixVariants.value = []
  scriptContent.value = ''
  scriptPath.value = null
  lowcodeSteps.value = []
  editMode.value = 'lowcode'
  recorderOpen.value = false
  scriptPreviewOpen.value = false
  generatedScriptContent.value = ''
  pendingGeneratedScript.value = ''
  savingGeneratedScript.value = false
  scriptElementAssets.value = []
  scriptPageObjects.value = []
}

function resolveEditMode(config: WebCaseConfig) {
  if (hasOwn(config, 'steps')) {
    return 'lowcode' as const
  }
  if (config.script_path) {
    return 'script' as const
  }
  return 'lowcode' as const
}

watch(() => props.open, async (v) => {
  if (!v) return
  const seq = ++initSeq.value
  resetDrawerState()

  if (props.projectId) {
    try {
      const [elements, pageObjects] = await Promise.all([
        webAssetsApi.listElements(props.projectId),
        webAssetsApi.listPageObjects(props.projectId),
      ])
      if (seq !== initSeq.value || !props.open) return
      scriptElementAssets.value = elements
      scriptPageObjects.value = pageObjects
    } catch {
      if (seq !== initSeq.value || !props.open) return
      // 资产加载失败不阻塞用例编辑；生成脚本时会明确提示无法展开的页面对象。
      scriptElementAssets.value = []
      scriptPageObjects.value = []
    }
  }

  if (props.editCase) {
    try {
      const detail = await caseApi.get(props.editCase.id)
      if (seq !== initSeq.value || !props.open) return

      if (!hasOwn(detail, 'config')) {
        message.error(t('case.drawer.web.msg.config_missing_cancel'))
        emit('close')
        return
      }

      isEdit.value = true
      localCaseId.value = detail.id
      form.name = detail.name
      form.description = detail.description ?? ''
      form.tags = detail.tags ?? []
      form.priority = detail.priority ?? 'P2'
      form.case_level = detail.case_level ?? 'regression'
      const c = detail.config as WebCaseConfig
      cfg.browser = 'chromium'
      cfg.headless = c.headless ?? true
      cfg.timeout = c.timeout ?? 60
      cfg.viewportWidth = c.viewport?.width ?? 1280
      cfg.viewportHeight = c.viewport?.height ?? 720
      if (Array.isArray(c.browser_matrix) && c.browser_matrix.length) {
        matrixEnabled.value = true
        matrixVariants.value = c.browser_matrix.map((item) => ({
          browser: item.browser === 'firefox' || item.browser === 'webkit' ? item.browser : 'chromium',
          viewport: {
            width: Number(item.viewport?.width ?? 1280),
            height: Number(item.viewport?.height ?? 720),
          },
          device: String(item.device ?? ''),
        }))
      }
      scriptPath.value = c.script_path ?? null
      lowcodeSteps.value = Array.isArray(c.steps) ? c.steps : []
      editMode.value = resolveEditMode(c)
    } catch {
      if (seq !== initSeq.value || !props.open) return
      message.error(t('case.drawer.web.msg.load_failed_cancel'))
      emit('close')
      return
    }
  }
})

watch(editMode, async (mode) => {
  if (!props.open) return
  if (mode === 'script') {
    if (!localCaseId.value) {
      scriptContent.value = ''
      return
    }
    await loadScript()
    return
  }
  scriptContent.value = ''
})

async function loadScript() {
  if (!localCaseId.value) return
  scriptContent.value = ''
  loadingScript.value = true
  try {
    const res = await scriptApi.get(localCaseId.value)
    scriptContent.value = res.exists ? res.content : ''
  } catch {
    scriptContent.value = ''
  } finally {
    loadingScript.value = false
  }
}

async function handleUpload(file: File) {
  if (!localCaseId.value) return false
  uploading.value = true
  try {
    const res = await scriptApi.upload(localCaseId.value, file)
    scriptPath.value = res.script_path
    message.success(t('case.drawer.msg.script_uploaded'))
    await loadScript()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.drawer.msg.upload_failed')))
  } finally {
    uploading.value = false
  }
  return false
}

async function handleSaveScript() {
  if (!localCaseId.value || !scriptContent.value.trim()) return
  savingScript.value = true
  try {
    const res = await scriptApi.saveContent(localCaseId.value, scriptContent.value)
    scriptPath.value = res.script_path
    message.success(t('case.drawer.msg.script_saved'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.drawer.msg.save_failed')))
  } finally {
    savingScript.value = false
  }
}

function openGeneratedScriptPreview() {
  if (!lowcodeSteps.value.length) {
    message.warning(t('case.drawer.web.msg.add_step_required'))
    return
  }
  generatedScriptContent.value = generateWebPythonScript(lowcodeSteps.value, {
    elementAssets: scriptElementAssets.value,
    pageObjects: scriptPageObjects.value,
  })
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

    const response = await scriptApi.saveContent(localCaseId.value, content)
    scriptPath.value = response.script_path
    scriptContent.value = content
    scriptPreviewOpen.value = false
    message.success(t('case.drawer.msg.script_saved'))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.drawer.msg.save_failed')))
  } finally {
    savingGeneratedScript.value = false
  }
}

function buildConfig() {
  const base = {
    browser: cfg.browser,
    headless: cfg.headless,
    timeout: cfg.timeout,
    viewport: { width: cfg.viewportWidth, height: cfg.viewportHeight },
    ...(matrixEnabled.value ? {
      browser_matrix: matrixVariants.value.map((variant) => ({
        browser: variant.browser,
        viewport: variant.viewport,
        ...(variant.device ? { device: variant.device } : {}),
      })),
    } : {}),
  }

  if (editMode.value === 'lowcode') {
    return {
      ...base,
      steps: lowcodeSteps.value,
      ...(scriptPath.value ? { script_path: scriptPath.value } : {}),
    }
  }

  return {
    ...base,
    ...(scriptPath.value ? { script_path: scriptPath.value } : {}),
  }
}

function addMatrixVariant() {
  matrixVariants.value.push({
    browser: 'chromium',
    viewport: { width: 1280, height: 720 },
    device: '',
  })
}

function handleRecordedSteps(steps: LowcodeStep[]) {
  lowcodeSteps.value = [...lowcodeSteps.value, ...steps]
  message.success(t('case.drawer.web.recorder.imported', { count: steps.length }))
}

async function handleSave() {
  try { await formRef.value?.validate() } catch { return }

  if (editMode.value === 'lowcode' && lowcodeSteps.value.length === 0) {
    message.warning(t('case.drawer.web.msg.add_step_required'))
    return
  }

  saving.value = true
  try {
    const config = buildConfig()
    if (isEdit.value && localCaseId.value) {
      await caseApi.update(localCaseId.value, {
        name: form.name,
        description: form.description,
        tags: form.tags,
        priority: form.priority,
        case_level: form.case_level,
        config,
      })
      message.success(t('common.success'))
      emit('saved')
      emit('close')
    } else {
      const newCase = await caseApi.create({
        name: form.name,
        description: form.description,
        case_type: 'web',
        tags: form.tags,
        priority: form.priority,
        case_level: form.case_level,
        module_id: props.moduleId!,
        config,
      })
      localCaseId.value = newCase.id
      isEdit.value = true
      if (pendingGeneratedScript.value) {
        try {
          const response = await scriptApi.saveContent(newCase.id, pendingGeneratedScript.value)
          scriptPath.value = response.script_path
          scriptContent.value = pendingGeneratedScript.value
          pendingGeneratedScript.value = ''
          message.success(t('case.drawer.msg.script_saved'))
        } catch (error: unknown) {
          message.error(errorMessage(error, t('case.drawer.msg.save_failed')))
        }
      }
      message.success(t('case.drawer.msg.case_created'))
      emit('saved')
      if (editMode.value === 'lowcode') {
        emit('close')
      }
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.drawer.msg.save_failed')))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.script-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.lowcode-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.lowcode-toolbar span {
  color: #999;
  font-size: 12px;
}
.script-path-ok {
  color: #52c41a;
  font-size: 13px;
}
.script-path-empty {
  color: #999;
  font-size: 13px;
}
</style>
