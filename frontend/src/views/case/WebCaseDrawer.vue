<template>
  <a-drawer
    :open="open"
    :title="isEdit ? '编辑 Web UI 用例' : '新建 Web UI 用例'"
    width="960"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <!-- ── 基本信息 ───────────────────────────────────── -->
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
              placeholder="输入后回车添加（如 smoke、p0）"
              :token-separators="[',']"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="描述">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
      </a-form-item>

      <!-- ── 执行配置 ────────────────────────────────────── -->
      <a-divider orientation="left">执行配置</a-divider>
      <a-row :gutter="16">
        <a-col :span="6">
          <a-form-item label="浏览器">
            <a-select v-model:value="cfg.browser" style="width: 100%">
              <a-select-option value="chromium">Chromium</a-select-option>
              <a-select-option value="firefox">Firefox</a-select-option>
              <a-select-option value="webkit">WebKit (Safari)</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item label="超时时间（秒）">
            <a-input-number
              v-model:value="cfg.timeout"
              :min="10"
              :max="600"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item label="视口宽度 (px)">
            <a-input-number
              v-model:value="cfg.viewportWidth"
              :min="320"
              :max="3840"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item label="视口高度 (px)">
            <a-input-number
              v-model:value="cfg.viewportHeight"
              :min="240"
              :max="2160"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="无头模式">
        <a-switch v-model:checked="cfg.headless" checked-children="开启" un-checked-children="关闭" />
        <span style="margin-left: 8px; color: #999; font-size: 12px">
          关闭后浏览器将显示界面（仅本地部署时有效）
        </span>
      </a-form-item>

      <!-- ── 测试脚本 ────────────────────────────────────── -->
      <a-divider orientation="left">测试脚本</a-divider>

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
          <a-tooltip title="脚本中每个 test_ 开头的函数对应报告中的一个步骤，需安装 pytest + pytest-playwright">
            <a-tag color="blue" style="cursor: default; margin-left: auto">pytest-playwright</a-tag>
          </a-tooltip>
        </div>

        <a-spin :spinning="loadingScript">
          <MonacoEditor
            v-model:value="scriptContent"
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
import { message } from 'ant-design-vue'
import { UploadOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import { caseApi, scriptApi } from '@/api'
import MonacoEditor from '@/components/common/MonacoEditor.vue'

const props = defineProps<{
  open: boolean
  moduleId: number | null
  editCase?: any
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const formRef = ref()
const localCaseId = ref<number | null>(null)

const form = reactive({
  name: '',
  description: '',
  tags: [] as string[],
})

const cfg = reactive({
  browser: 'chromium',
  headless: true,
  timeout: 60,
  viewportWidth: 1280,
  viewportHeight: 720,
})

// Script
const scriptContent = ref('')
const scriptPath = ref<string | null>(null)
const uploading = ref(false)
const savingScript = ref(false)
const loadingScript = ref(false)

watch(() => props.open, async (v) => {
  if (!v) return
  if (props.editCase) {
    isEdit.value = true
    localCaseId.value = props.editCase.id
    form.name = props.editCase.name
    form.description = props.editCase.description ?? ''
    form.tags = props.editCase.tags ?? []
    const c = props.editCase.config ?? {}
    cfg.browser = c.browser ?? 'chromium'
    cfg.headless = c.headless ?? true
    cfg.timeout = c.timeout ?? 60
    cfg.viewportWidth = c.viewport?.width ?? 1280
    cfg.viewportHeight = c.viewport?.height ?? 720
    scriptPath.value = c.script_path ?? null
    await loadScript()
  } else {
    isEdit.value = false
    localCaseId.value = null
    form.name = ''
    form.description = ''
    form.tags = []
    cfg.browser = 'chromium'
    cfg.headless = true
    cfg.timeout = 60
    cfg.viewportWidth = 1280
    cfg.viewportHeight = 720
    scriptContent.value = ''
    scriptPath.value = null
  }
})

async function loadScript() {
  if (!localCaseId.value) return
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
  return {
    browser: cfg.browser,
    headless: cfg.headless,
    timeout: cfg.timeout,
    viewport: { width: cfg.viewportWidth, height: cfg.viewportHeight },
    ...(scriptPath.value ? { script_path: scriptPath.value } : {}),
  }
}

async function handleSave() {
  try { await formRef.value?.validate() } catch { return }
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
        case_type: 'web',
        tags: form.tags,
        module_id: props.moduleId!,
        config,
      }) as any
      localCaseId.value = newCase.id
      isEdit.value = true
      message.success('用例已创建，可继续上传或编辑测试脚本')
      emit('saved')
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
