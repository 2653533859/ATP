<template>
  <a-drawer
    :open="open"
    :title="isEdit ? '编辑 Android UI 用例' : '新建 Android UI 用例'"
    width="960"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <!-- 基本信息 -->
      <a-divider orientation="left">基本信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item
            label="用例名称"
            name="name"
            :rules="[{ required: true, message: '请输入用例名称' }]"
          >
            <a-input v-model:value="form.name" placeholder="用例名称" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="标签">
            <a-select
              v-model:value="form.tags"
              mode="tags"
              placeholder="输入后回车添加"
              :token-separators="[',']"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="描述">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
      </a-form-item>

      <!-- 执行配置 -->
      <a-divider orientation="left">执行配置</a-divider>
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="目标设备">
            <a-select
              v-model:value="cfg.device_serial"
              placeholder="选择设备"
              allow-clear
              style="width: 100%"
              :loading="devicesLoading"
            >
              <a-select-option v-for="d in devices" :key="d.serial" :value="d.serial">
                <a-badge :status="d.status === 'online' ? 'success' : 'default'" />
                {{ d.brand }} {{ d.model }} ({{ d.serial }})
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="安装 APK（可选）">
            <a-select
              v-model:value="cfg.apk_id"
              placeholder="不安装 APK"
              allow-clear
              style="width: 100%"
              :loading="apksLoading"
            >
              <a-select-option v-for="a in apks" :key="a.id" :value="a.id">
                {{ a.filename }}
                <span v-if="a.version_name" style="color: #999"> v{{ a.version_name }}</span>
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="超时时间（秒）">
            <a-input-number
              v-model:value="cfg.timeout"
              :min="10"
              :max="600"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <!-- 测试模式切换 -->
      <a-divider orientation="left">测试内容</a-divider>
      <a-form-item label="编辑模式">
        <a-radio-group v-model:value="editMode" button-style="solid">
          <a-radio-button value="lowcode">低代码</a-radio-button>
          <a-radio-button value="script">脚本</a-radio-button>
        </a-radio-group>
        <span style="margin-left: 12px; color: #999; font-size: 12px">
          {{ editMode === 'lowcode' ? '可视化配置步骤（通过 ADB 命令执行）' : '上传或编辑 uiautomator2 + pytest 脚本' }}
        </span>
      </a-form-item>

      <!-- 低代码模式 -->
      <template v-if="editMode === 'lowcode'">
        <AndroidStepEditor v-model="lowcodeSteps" />
      </template>

      <!-- 脚本模式 -->
      <template v-else>
        <a-alert
          v-if="!localCaseId"
          message="请先点击「创建用例」保存基本信息，保存后可上传或编辑测试脚本"
          type="info"
          show-icon
          style="margin-bottom: 0"
        />

        <template v-else>
          <div class="script-toolbar">
            <a-upload :before-upload="handleUpload" :show-upload-list="false" accept=".py">
              <a-button :loading="uploading" size="small">
                <UploadOutlined /> 上传脚本（.py）
              </a-button>
            </a-upload>
            <span v-if="scriptPath" class="script-path-ok">
              <CheckCircleOutlined /> {{ scriptPath }}
            </span>
            <span v-else class="script-path-empty">尚未上传脚本</span>
            <a-tooltip title="脚本中使用 device_serial fixture 获取设备序列号，使用 uiautomator2 进行自动化测试">
              <a-tag color="green" style="cursor: default; margin-left: auto">uiautomator2 + pytest</a-tag>
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
              保存脚本修改
            </a-button>
          </div>
        </template>
      </template>
    </a-form>

    <template #footer>
      <a-space style="float: right">
        <a-button @click="emit('close')">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">
          {{ localCaseId ? '保存配置' : '创建用例' }}
        </a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { UploadOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import { caseApi, scriptApi, deviceApi, apkApi } from '@/api'
import MonacoEditor from '@/components/common/MonacoEditor.vue'
import AndroidStepEditor from '@/components/common/AndroidStepEditor.vue'

const route = useRoute()

const props = defineProps<{
  open: boolean
  moduleId: number | null
  projectId?: number | null
  editCase?: any
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const formRef = ref()
const localCaseId = ref<number | null>(null)

// 编辑模式
const editMode = ref<'lowcode' | 'script'>('lowcode')

const form = reactive({
  name: '',
  description: '',
  tags: [] as string[],
})

const cfg = reactive({
  device_serial: undefined as string | undefined,
  apk_id: undefined as number | undefined,
  timeout: 120,
})

// Devices & APKs
const devices = ref<any[]>([])
const devicesLoading = ref(false)
const apks = ref<any[]>([])
const apksLoading = ref(false)

// 低代码步骤
const lowcodeSteps = ref<Array<{ action: string; name: string; params: Record<string, any> }>>([])

// Script
const scriptContent = ref('')
const scriptPath = ref<string | null>(null)
const uploading = ref(false)
const savingScript = ref(false)
const loadingScript = ref(false)
const initSeq = ref(0)

// APK object_name lookup
const apkMap = ref<Record<number, string>>({})

function hasOwn(obj: any, key: string) {
  return Object.prototype.hasOwnProperty.call(obj ?? {}, key)
}

function resolveEditMode(config: Record<string, any>) {
  if (hasOwn(config, 'steps')) return 'lowcode' as const
  if (config.script_path) return 'script' as const
  return 'lowcode' as const
}

function resetDrawerState() {
  isEdit.value = false
  localCaseId.value = null
  form.name = ''
  form.description = ''
  form.tags = []
  cfg.device_serial = undefined
  cfg.apk_id = undefined
  cfg.timeout = 120
  scriptContent.value = ''
  scriptPath.value = null
  lowcodeSteps.value = []
  editMode.value = 'lowcode'
}

async function loadDevices() {
  devicesLoading.value = true
  try {
    devices.value = await deviceApi.list()
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
    apks.value = await apkApi.list(projectId ? { project_id: projectId } : undefined)
    const map: Record<number, string> = {}
    for (const a of apks.value) {
      map[a.id] = a.object_name
    }
    apkMap.value = map
  } catch {
    apks.value = []
  } finally {
    apksLoading.value = false
  }
}

watch(() => props.open, async (v) => {
  if (!v) return
  const seq = ++initSeq.value
  resetDrawerState()

  loadDevices()
  loadApks()

  if (props.editCase) {
    let detail: any
    try {
      detail = await caseApi.get(props.editCase.id) as any
    } catch {
      if (seq !== initSeq.value || !props.open) return
      message.error('加载用例详情失败')
      emit('close')
      return
    }
    if (seq !== initSeq.value || !props.open) return

    isEdit.value = true
    localCaseId.value = detail.id
    form.name = detail.name
    form.description = detail.description ?? ''
    form.tags = detail.tags ?? []
    const c = detail.config ?? {}
    cfg.device_serial = c.device_serial
    cfg.apk_id = c.apk_id
    cfg.timeout = c.timeout ?? 120
    scriptPath.value = c.script_path ?? null
    lowcodeSteps.value = c.steps ?? []
    editMode.value = resolveEditMode(c)
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
  } else {
    scriptContent.value = ''
  }
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
    const res = await scriptApi.upload(localCaseId.value, file) as any
    scriptPath.value = res.script_path
    message.success('脚本上传成功')
    await loadScript()
  } catch (e: any) {
    message.error(e ?? '上传失败')
  } finally {
    uploading.value = false
  }
  return false
}

async function handleSaveScript() {
  if (!localCaseId.value || !scriptContent.value.trim()) return
  savingScript.value = true
  try {
    const res = await scriptApi.saveContent(localCaseId.value, scriptContent.value) as any
    scriptPath.value = res.script_path
    message.success('脚本已保存')
  } catch (e: any) {
    message.error(e ?? '保存失败')
  } finally {
    savingScript.value = false
  }
}

function buildConfig() {
  const config: Record<string, any> = {
    timeout: cfg.timeout,
  }
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
  try { await formRef.value?.validate() } catch { return }

  if (editMode.value === 'lowcode' && lowcodeSteps.value.length === 0) {
    message.warning('请至少添加一个步骤')
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
        config,
      })
      message.success('保存成功')
      emit('saved')
      emit('close')
    } else {
      const newCase = await caseApi.create({
        name: form.name,
        description: form.description,
        case_type: 'android',
        tags: form.tags,
        module_id: props.moduleId!,
        config,
      }) as any
      localCaseId.value = newCase.id
      isEdit.value = true
      message.success('用例已创建')
      emit('saved')
      if (editMode.value === 'lowcode') {
        emit('close')
      }
    }
  } catch (e: any) {
    message.error(e ?? '保存失败')
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
.script-path-ok {
  color: #52c41a;
  font-size: 13px;
}
.script-path-empty {
  color: #999;
  font-size: 13px;
}
</style>
