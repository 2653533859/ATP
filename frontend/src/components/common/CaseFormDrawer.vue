<template>
  <a-drawer
    :open="open"
    :title="isEdit ? '编辑用例' : '新建用例'"
    width="760"
    :destroy-on-close="true"
    @close="emit('close')"
  >
    <a-form :model="form" layout="vertical" ref="formRef">
      <!-- ── 基本信息 ───────────────────────────────── -->
      <a-divider orientation="left">基本信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item label="用例名称" name="name" :rules="[{ required: true, message: '请输入用例名称' }]">
            <a-input v-model:value="form.name" placeholder="用例名称" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="用例类型" name="case_type">
            <a-select v-model:value="form.case_type" :disabled="isEdit">
              <a-select-option value="api">接口测试</a-select-option>
              <a-select-option value="web">Web UI</a-select-option>
              <a-select-option value="android">Android UI</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item label="标签">
        <a-select
          v-model:value="form.tags"
          mode="tags"
          placeholder="输入后回车添加标签（如 smoke、p0）"
          :token-separators="[',']"
        />
      </a-form-item>
      <a-form-item label="描述">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
      </a-form-item>

      <!-- ── 接口测试配置 ────────────────────────────── -->
      <template v-if="form.case_type === 'api'">
        <a-divider orientation="left">请求配置</a-divider>

        <!-- URL + Method -->
        <a-form-item label="请求地址" :rules="[{ required: true, message: '请输入 URL' }]">
          <a-input-group compact>
            <a-select v-model:value="cfg.method" style="width: 110px">
              <a-select-option v-for="m in HTTP_METHODS" :key="m" :value="m">{{ m }}</a-select-option>
            </a-select>
            <a-input v-model:value="cfg.url" style="width: calc(100% - 110px)" placeholder="https://api.example.com/v1/..." />
          </a-input-group>
        </a-form-item>

        <!-- Tabs: Headers / Params / Body / Auth -->
        <a-tabs v-model:activeKey="activeTab" size="small">
          <!-- Headers -->
          <a-tab-pane key="headers" tab="Headers">
            <KvEditor v-model:value="cfg.headers" />
          </a-tab-pane>

          <!-- Query Params -->
          <a-tab-pane key="params" tab="Params">
            <KvEditor v-model:value="cfg.params" />
          </a-tab-pane>

          <!-- Body -->
          <a-tab-pane key="body" tab="Body">
            <a-radio-group v-model:value="cfg.body_type" size="small" style="margin-bottom: 8px">
              <a-radio-button value="none">None</a-radio-button>
              <a-radio-button value="json">JSON</a-radio-button>
              <a-radio-button value="form">Form</a-radio-button>
              <a-radio-button value="raw">Raw</a-radio-button>
            </a-radio-group>
            <KvEditor v-if="cfg.body_type === 'form'" v-model:value="formBody" />
            <a-textarea
              v-else-if="cfg.body_type !== 'none'"
              v-model:value="cfg.body"
              :rows="8"
              placeholder='{"key": "value"}'
              style="font-family: monospace; font-size: 13px"
            />
          </a-tab-pane>

          <!-- Auth -->
          <a-tab-pane key="auth" tab="Auth">
            <a-form-item label="认证方式">
              <a-select v-model:value="cfg.auth.type" style="width: 160px">
                <a-select-option value="none">无</a-select-option>
                <a-select-option value="bearer">Bearer Token</a-select-option>
                <a-select-option value="basic">Basic Auth</a-select-option>
                <a-select-option value="apikey">API Key</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="cfg.auth.type === 'bearer'">
              <a-form-item label="Token">
                <a-input v-model:value="cfg.auth.token" placeholder="支持 {{variable}} 变量" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'basic'">
              <a-form-item label="用户名">
                <a-input v-model:value="cfg.auth.username" />
              </a-form-item>
              <a-form-item label="密码">
                <a-input-password v-model:value="cfg.auth.password" />
              </a-form-item>
            </template>
            <template v-if="cfg.auth.type === 'apikey'">
              <a-form-item label="Header 名称">
                <a-input v-model:value="cfg.auth.header" placeholder="X-API-Key" />
              </a-form-item>
              <a-form-item label="Key 值">
                <a-input v-model:value="cfg.auth.value" />
              </a-form-item>
            </template>
          </a-tab-pane>
        </a-tabs>

        <!-- 超时 -->
        <a-form-item label="超时时间（秒）" style="margin-top: 16px">
          <a-input-number v-model:value="cfg.timeout" :min="1" :max="300" style="width: 120px" />
        </a-form-item>

        <!-- ── 断言 ────────────────────────────────── -->
        <a-divider orientation="left">断言</a-divider>
        <div v-for="(a, i) in cfg.assertions" :key="i" class="assertion-row">
          <a-select v-model:value="a.target" style="width: 130px" placeholder="断言对象">
            <a-select-option value="status_code">状态码</a-select-option>
            <a-select-option value="body">响应体</a-select-option>
            <a-select-option value="header">响应头</a-select-option>
            <a-select-option value="duration">响应时间(ms)</a-select-option>
          </a-select>
          <a-input
            v-if="a.target === 'body' || a.target === 'header'"
            v-model:value="a.expression"
            placeholder="JSONPath / Header名"
            style="width: 160px"
          />
          <a-select v-model:value="a.operator" style="width: 110px" placeholder="条件">
            <a-select-option value="eq">等于</a-select-option>
            <a-select-option value="contains">包含</a-select-option>
            <a-select-option value="gt">大于</a-select-option>
            <a-select-option value="lt">小于</a-select-option>
            <a-select-option value="exists">存在</a-select-option>
          </a-select>
          <a-input
            v-if="a.operator !== 'exists'"
            v-model:value="a.expected"
            placeholder="期望值"
            style="flex: 1"
          />
          <MinusCircleOutlined class="remove-btn" @click="cfg.assertions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="addAssertion">
          <PlusOutlined /> 添加断言
        </a-button>

        <!-- ── 变量提取 ─────────────────────────────── -->
        <a-divider orientation="left">变量提取</a-divider>
        <div v-for="(e, i) in cfg.extractions" :key="i" class="assertion-row">
          <a-input v-model:value="e.variable" placeholder="变量名" style="width: 140px" />
          <span style="padding: 0 8px; color: #999">=</span>
          <a-input v-model:value="e.expression" placeholder="JSONPath（如 $.data.token）" style="flex: 1" />
          <MinusCircleOutlined class="remove-btn" @click="cfg.extractions.splice(i, 1)" />
        </div>
        <a-button type="dashed" size="small" @click="cfg.extractions.push({ variable: '', expression: '' })">
          <PlusOutlined /> 添加变量提取
        </a-button>
      </template>

      <!-- ── Web / Android 占位 ────────────────────── -->
      <template v-else>
        <a-alert
          :message="`${form.case_type === 'web' ? 'Web UI' : 'Android UI'} 用例配置将在后续阶段实现`"
          type="info"
          show-icon
          style="margin-top: 16px"
        />
      </template>
    </a-form>

    <template #footer>
      <a-space style="float: right">
        <a-button @click="emit('close')">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons-vue'
import { caseApi } from '@/api'
import KvEditor from '@/components/common/KvEditor.vue'

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

const props = defineProps<{
  open: boolean
  moduleId: number | null
  editCase?: any
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const isEdit = ref(false)
const saving = ref(false)
const activeTab = ref('headers')
const formRef = ref()

// 基本信息
const form = reactive({
  name: '',
  description: '',
  case_type: 'api',
  tags: [] as string[],
})

// 接口测试配置
const cfg = reactive({
  url: '',
  method: 'GET',
  headers: {} as Record<string, string>,
  params: {} as Record<string, string>,
  body_type: 'none' as 'none' | 'json' | 'form' | 'raw',
  body: '',
  auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
  timeout: 30,
  assertions: [] as any[],
  extractions: [] as any[],
})
const formBody = ref<Record<string, string>>({})

watch(() => props.open, (v) => {
  if (!v) return
  if (props.editCase) {
    isEdit.value = true
    const c = props.editCase
    form.name = c.name
    form.description = c.description ?? ''
    form.case_type = c.case_type
    form.tags = c.tags ?? []
    const step = c.config?.steps?.[0] ?? c.config ?? {}
    const bodyType = step.body_type ?? 'none'
    if (bodyType === 'form') {
      if (step.body && typeof step.body === 'object' && !Array.isArray(step.body)) {
        formBody.value = { ...step.body }
      } else if (typeof step.body === 'string' && step.body.trim()) {
        try {
          const parsed = JSON.parse(step.body)
          formBody.value = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
        } catch {
          formBody.value = {}
        }
      } else {
        formBody.value = {}
      }
    } else {
      formBody.value = {}
    }

    Object.assign(cfg, {
      url: step.url ?? '',
      method: step.method ?? 'GET',
      headers: step.headers ?? {},
      params: step.params ?? {},
      body_type: bodyType,
      body: typeof step.body === 'string' ? step.body : JSON.stringify(step.body ?? '', null, 2),
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '', ...step.auth },
      timeout: step.timeout ?? 30,
      assertions: step.assertions ? [...step.assertions] : [],
      extractions: step.extractions ? [...step.extractions] : [],
    })
  } else {
    isEdit.value = false
    form.name = ''
    form.description = ''
    form.case_type = 'api'
    form.tags = []
    Object.assign(cfg, {
      url: '', method: 'GET', headers: {}, params: {},
      body_type: 'none', body: '',
      auth: { type: 'none', token: '', username: '', password: '', header: '', value: '' },
      timeout: 30, assertions: [], extractions: [],
    })
    formBody.value = {}
  }
})

function addAssertion() {
  cfg.assertions.push({ target: 'status_code', operator: 'eq', expected: '200', expression: '' })
}

function buildConfig() {
  let body: any = cfg.body_type === 'form' ? { ...formBody.value } : cfg.body
  if (cfg.body_type === 'json' && typeof body === 'string') {
    try { body = JSON.parse(body) } catch { /* 保持字符串 */ }
  }
  return {
    steps: [{
      name: form.name,
      url: cfg.url,
      method: cfg.method,
      headers: cfg.headers,
      params: cfg.params,
      body_type: cfg.body_type,
      body: cfg.body_type === 'none' ? null : body,
      auth: cfg.auth,
      timeout: cfg.timeout,
      assertions: cfg.assertions,
      extractions: cfg.extractions,
    }],
  }
}

async function handleSave() {
  try { await formRef.value?.validate() } catch { return }
  if (form.case_type === 'api' && !cfg.url) {
    message.warning('请输入请求地址')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description,
      case_type: form.case_type,
      tags: form.tags,
      module_id: props.moduleId!,
      config: buildConfig(),
    }
    if (isEdit.value) {
      await caseApi.update(props.editCase.id, { name: payload.name, description: payload.description, tags: payload.tags, config: payload.config })
    } else {
      await caseApi.create(payload)
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.assertion-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
}
.remove-btn {
  color: #ff4d4f;
  cursor: pointer;
  flex-shrink: 0;
}
</style>
