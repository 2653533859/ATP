<template>
  <div class="mock-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          placeholder="选择项目"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadRules"
        />
      </a-space>
      <a-space>
        <a-button :disabled="!projectId" @click="handleExportRules">
          导出规则
        </a-button>
        <a-upload :show-upload-list="false" accept="application/json" :before-upload="beforeImportRules">
          <a-button :disabled="!projectId">导入规则</a-button>
        </a-upload>
        <a-button :disabled="!projectId" @click="openLogs">
          <UnorderedListOutlined /> 请求日志
        </a-button>
        <a-button type="primary" :disabled="!projectId" @click="openCreate">
          <PlusOutlined /> 添加 Mock 规则
        </a-button>
      </a-space>
    </div>

    <a-alert
      v-if="projectId"
      type="info"
      show-icon
      style="margin-bottom: 0"
      :message="`Mock 服务地址：${mockBaseUrl}`"
    >
      <template #description>
        在测试用例中将请求地址指向此前缀即可使用 Mock 响应。支持路径模板如 <code>/api/users/{id}</code>，也支持按 query/header/body 条件分流响应。
      </template>
    </a-alert>

    <a-table
      :columns="columns"
      :data-source="rules"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'method'">
          <a-tag :color="methodColor(record.method)">{{ record.method }}</a-tag>
        </template>
        <template v-if="column.key === 'status_code'">
          <a-tag :color="record.status_code < 400 ? 'green' : 'red'">{{ record.status_code }}</a-tag>
        </template>
        <template v-if="column.key === 'conditions'">
          <span>{{ formatConditions(record.match_conditions) }}</span>
        </template>
        <template v-if="column.key === 'render_template'">
          <a-tag :color="record.render_template ? 'blue' : 'default'">{{ record.render_template ? '开启' : '关闭' }}</a-tag>
        </template>
        <template v-if="column.key === 'record_requests'">
          <a-tag :color="record.record_requests ? 'purple' : 'default'">{{ record.record_requests ? '开启' : '关闭' }}</a-tag>
        </template>
        <template v-if="column.key === 'is_enabled'">
          <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? '启用' : '禁用' }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-button type="link" size="small" @click="handleCopy(record)">复制</a-button>
            <a-popconfirm title="确认删除？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? '编辑 Mock 规则' : '添加 Mock 规则'"
      :confirm-loading="saving"
      width="720px"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item label="规则名称">
          <a-input v-model:value="form.name" placeholder="如：模拟支付成功" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="HTTP 方法">
              <a-select v-model:value="form.method" style="width: 100%">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="PATCH">PATCH</a-select-option>
                <a-select-option value="ANY">ANY（任意方法）</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item label="请求路径">
              <a-input v-model:value="form.path" placeholder="/api/users/{id}" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="响应状态码">
              <a-input-number v-model:value="form.status_code" :min="100" :max="599" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="模拟延迟 (ms)">
              <a-input-number v-model:value="form.delay_ms" :min="0" :max="30000" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="启用">
              <a-switch v-model:checked="form.is_enabled" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="模板渲染">
              <a-switch v-model:checked="form.render_template" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="录制请求样本">
              <a-switch v-model:checked="form.record_requests" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" style="font-size: 13px">条件响应</a-divider>
        <a-form-item label="Query 条件 (JSON)">
          <a-textarea v-model:value="queryConditionsText" :rows="2" class="code-textarea" placeholder='{"scene": "success"}' />
        </a-form-item>
        <a-form-item label="Header 条件 (JSON)">
          <a-textarea v-model:value="headerConditionsText" :rows="2" class="code-textarea" placeholder='{"x-env": "test"}' />
        </a-form-item>
        <a-form-item label="Body 条件 (JSON)">
          <a-textarea v-model:value="bodyConditionsText" :rows="2" class="code-textarea" placeholder='{"status": "paid"}' />
        </a-form-item>

        <a-form-item label="响应头 (JSON)">
          <a-textarea
            v-model:value="headersText"
            :rows="2"
            class="code-textarea"
            placeholder='{"Content-Type": "application/json"}'
          />
        </a-form-item>

        <a-form-item>
          <template #label>
            <span>响应体</span>
            <a-button type="link" size="small" style="margin-left: 8px" @click="formatResponseBody">格式化 JSON</a-button>
          </template>
          <a-textarea
            v-model:value="form.response_body"
            :rows="8"
            class="code-textarea"
            placeholder='{"code": 0, "message": "success"}'
          />
          <div style="margin-top: 8px; color: #888; font-size: 12px">
            模板开启后，可使用 <code>{{ '{{query.xxx}}' }}</code> / <code>{{ '{{headers.xxx}}' }}</code> / <code>{{ '{{body.xxx}}' }}</code> 引用请求数据。
          </div>
        </a-form-item>

        <a-form-item v-if="isEdit && form.record_requests" label="已录制样本">
          <a-textarea :value="JSON.stringify(currentSamples, null, 2)" :rows="6" class="code-textarea" readonly />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:open="logsOpen"
      title="Mock 请求日志"
      width="600"
      :extra="undefined"
    >
      <a-button style="margin-bottom: 12px" size="small" @click="refreshLogs">刷新</a-button>
      <a-table
        :columns="logColumns"
        :data-source="logs"
        row-key="timestamp"
        size="small"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'method'">
            <a-tag :color="methodColor(record.method)">{{ record.method }}</a-tag>
          </template>
          <template v-if="column.key === 'matched'">
            <a-tag :color="record.matched ? 'green' : 'red'">{{ record.matched ? '命中' : '未命中' }}</a-tag>
          </template>
          <template v-if="column.key === 'timestamp'">
            {{ record.timestamp?.slice(11, 19) }}
          </template>
        </template>
      </a-table>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, UnorderedListOutlined } from '@ant-design/icons-vue'
import { mockRuleApi, projectApi, type MockRuleItem } from '@/api'
import { getBackendOrigin } from '@/api/http'

type MatchConditions = {
  query: Record<string, string>
  headers: Record<string, string>
  body: Record<string, string>
}

interface MockRuleRecord extends MockRuleItem {}

interface MockRuleForm {
  name: string
  method: string
  path: string
  status_code: number
  delay_ms: number
  is_enabled: boolean
  render_template: boolean
  record_requests: boolean
  response_body: string | null
}

const rules = ref<MockRuleRecord[]>([])
const loading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const defaultForm = (): MockRuleForm => ({
  name: '', method: 'GET', path: '', status_code: 200,
  delay_ms: 0, is_enabled: true, render_template: false, record_requests: false, response_body: null,
})
const form = ref<MockRuleForm>(defaultForm())
const headersText = ref('{}')
const queryConditionsText = ref('{}')
const headerConditionsText = ref('{}')
const bodyConditionsText = ref('{}')

const logsOpen = ref(false)
const logs = ref<any[]>([])
const currentSamples = ref<Array<Record<string, unknown>>>([])

const mockBaseUrl = computed(() =>
  projectId.value ? `${getBackendOrigin()}/mock/${projectId.value}` : '',
)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '方法', key: 'method', width: 90 },
  { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
  { title: '条件', key: 'conditions', width: 180 },
  { title: '版本', dataIndex: 'version', key: 'version', width: 70 },
  { title: '模板', key: 'render_template', width: 70 },
  { title: '录制', key: 'record_requests', width: 70 },
  { title: '状态码', key: 'status_code', width: 80 },
  { title: '延迟', dataIndex: 'delay_ms', width: 80, customRender: ({ text }: any) => `${text}ms` },
  { title: '状态', key: 'is_enabled', width: 70 },
  { title: '更新时间', dataIndex: 'updated_at', width: 170,
    customRender: ({ text }: any) => text?.slice(0, 19).replace('T', ' ') },
  { title: '操作', key: 'action', width: 160, fixed: 'right' as const },
]

const logColumns = [
  { title: '方法', key: 'method', width: 80 },
  { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
  { title: '状态', key: 'matched', width: 80 },
  { title: '规则', dataIndex: 'rule_name', key: 'rule_name', ellipsis: true },
  { title: '响应码', dataIndex: 'status_code', width: 70 },
  { title: '时间', key: 'timestamp', width: 80 },
]

function getErrorMessage(error: unknown, fallback: string) {
  return typeof error === 'string' ? error : fallback
}

function methodColor(m: string) {
  const map: Record<string, string> = {
    GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red', PATCH: 'purple', ANY: 'default',
  }
  return map[m] ?? 'default'
}

function formatConditions(conditions?: MatchConditions) {
  const parts: string[] = []
  if (conditions?.query && Object.keys(conditions.query).length) parts.push(`Q:${Object.keys(conditions.query).length}`)
  if (conditions?.headers && Object.keys(conditions.headers).length) parts.push(`H:${Object.keys(conditions.headers).length}`)
  if (conditions?.body && Object.keys(conditions.body).length) parts.push(`B:${Object.keys(conditions.body).length}`)
  return parts.length ? parts.join(' / ') : '无条件'
}

function formatResponseBody() {
  if (!form.value.response_body) return
  try {
    const parsed = JSON.parse(form.value.response_body)
    form.value.response_body = JSON.stringify(parsed, null, 2)
  } catch {
    message.warning('响应体不是合法的 JSON，无法格式化')
  }
}

function parseJsonObject(text: string, fieldName: string) {
  try {
    const value = JSON.parse(text || '{}')
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      throw new Error(fieldName)
    }
    return value as Record<string, string>
  } catch {
    throw new Error(`${fieldName} JSON 格式不正确`)
  }
}

function downloadJson(content: object, filename: string) {
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: any) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadRules() {
  if (!projectId.value) { rules.value = []; return }
  loading.value = true
  try {
    rules.value = await mockRuleApi.list({ project_id: projectId.value })
  } catch {
    rules.value = []
    message.error(getErrorMessage(undefined, '加载 Mock 规则失败'))
  }
  finally { loading.value = false }
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = defaultForm()
  currentSamples.value = []
  headersText.value = '{}'
  queryConditionsText.value = '{}'
  headerConditionsText.value = '{}'
  bodyConditionsText.value = '{}'
  formOpen.value = true
}

function openEdit(record: MockRuleRecord) {
  isEdit.value = true
  editingId.value = record.id
  form.value = {
    name: record.name,
    method: record.method,
    path: record.path,
    status_code: record.status_code,
    delay_ms: record.delay_ms,
    is_enabled: record.is_enabled,
    render_template: record.render_template,
    record_requests: record.record_requests,
    response_body: record.response_body,
  }
  currentSamples.value = record.recorded_samples || []
  headersText.value = JSON.stringify(record.response_headers || {}, null, 2)
  queryConditionsText.value = JSON.stringify(record.match_conditions?.query || {}, null, 2)
  headerConditionsText.value = JSON.stringify(record.match_conditions?.headers || {}, null, 2)
  bodyConditionsText.value = JSON.stringify(record.match_conditions?.body || {}, null, 2)
  formOpen.value = true
}

function handleCopy(record: MockRuleRecord) {
  isEdit.value = false
  editingId.value = null
  form.value = {
    name: record.name + ' (副本)',
    method: record.method,
    path: record.path,
    status_code: record.status_code,
    delay_ms: record.delay_ms,
    is_enabled: record.is_enabled,
    render_template: record.render_template,
    record_requests: record.record_requests,
    response_body: record.response_body,
  }
  currentSamples.value = []
  headersText.value = JSON.stringify(record.response_headers || {}, null, 2)
  queryConditionsText.value = JSON.stringify(record.match_conditions?.query || {}, null, 2)
  headerConditionsText.value = JSON.stringify(record.match_conditions?.headers || {}, null, 2)
  bodyConditionsText.value = JSON.stringify(record.match_conditions?.body || {}, null, 2)
  formOpen.value = true
}

async function handleSave() {
  if (!form.value.name) { message.warning('请输入规则名称'); return }
  if (!form.value.path) { message.warning('请输入请求路径'); return }

  let parsedHeaders: Record<string, string> = {}
  let matchConditions: MatchConditions
  try {
    parsedHeaders = parseJsonObject(headersText.value, '响应头')
    matchConditions = {
      query: parseJsonObject(queryConditionsText.value, 'Query 条件'),
      headers: parseJsonObject(headerConditionsText.value, 'Header 条件'),
      body: parseJsonObject(bodyConditionsText.value, 'Body 条件'),
    }
  } catch (error: any) {
    message.warning(error.message || 'JSON 格式不正确')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      method: form.value.method,
      path: form.value.path.startsWith('/') ? form.value.path : '/' + form.value.path,
      status_code: form.value.status_code,
      response_headers: parsedHeaders,
      response_body: form.value.response_body || null,
      match_conditions: matchConditions,
      delay_ms: form.value.delay_ms,
      is_enabled: form.value.is_enabled,
      render_template: form.value.render_template,
      record_requests: form.value.record_requests,
    }
    if (isEdit.value) {
      await mockRuleApi.update(editingId.value!, payload)
    } else {
      await mockRuleApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    formOpen.value = false
    void loadRules()
  } catch {
    message.error(getErrorMessage(undefined, '保存失败'))
  }
  finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await mockRuleApi.delete(id)
    message.success('已删除')
    void loadRules()
  } catch {
    message.error(getErrorMessage(undefined, '删除失败'))
  }
}

async function handleExportRules() {
  if (!projectId.value) return
  try {
    const result = await mockRuleApi.exportRules(projectId.value)
    downloadJson(result, `mock-rules-project-${projectId.value}.json`)
    message.success('导出成功')
  } catch {
    message.error(getErrorMessage(undefined, '导出失败'))
  }
}

async function beforeImportRules(file: File) {
  if (!projectId.value) return false
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const rules = Array.isArray(data.rules) ? data.rules : []
    if (rules.length === 0) {
      message.warning('导入文件中没有可用的规则')
      return false
    }
    await mockRuleApi.importRules({ project_id: projectId.value, rules })
    message.success('导入成功')
    void loadRules()
  } catch {
    message.error(getErrorMessage(undefined, '导入失败，请检查 JSON 格式'))
  }
  return false
}

async function openLogs() {
  logsOpen.value = true
  await refreshLogs()
}

async function refreshLogs() {
  if (!projectId.value) return
  try {
    logs.value = await mockRuleApi.logs(projectId.value)
  } catch {
    message.error(getErrorMessage(undefined, '加载日志失败'))
  }
}
</script>

<style scoped>
.mock-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.code-textarea {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}
</style>
