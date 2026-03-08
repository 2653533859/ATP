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
        在测试用例中将请求地址指向此前缀即可使用 Mock 响应。支持路径模板如 <code>/api/users/{id}</code>
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

    <!-- 新建/编辑 Modal -->
    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? '编辑 Mock 规则' : '添加 Mock 规则'"
      :confirm-loading="saving"
      width="640px"
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
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 请求日志 Drawer -->
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
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, UnorderedListOutlined } from '@ant-design/icons-vue'
import { mockRuleApi, projectApi } from '@/api'
import { getBackendOrigin } from '@/api/http'

interface MockRuleRecord {
  id: number
  name: string
  method: string
  path: string
  status_code: number
  response_headers: Record<string, string>
  response_body: string | null
  delay_ms: number
  is_enabled: boolean
  updated_at?: string
}

interface MockRuleForm {
  name: string
  method: string
  path: string
  status_code: number
  delay_ms: number
  is_enabled: boolean
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
  delay_ms: 0, is_enabled: true, response_body: null,
})
const form = ref<MockRuleForm>(defaultForm())
const headersText = ref('{}')

// 请求日志
const logsOpen = ref(false)
const logs = ref<any[]>([])

const mockBaseUrl = computed(() =>
  projectId.value ? `${getBackendOrigin()}/mock/${projectId.value}` : '',
)

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '方法', key: 'method', width: 90 },
  { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
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

function methodColor(m: string) {
  const map: Record<string, string> = {
    GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red', PATCH: 'purple', ANY: 'default',
  }
  return map[m] ?? 'default'
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
  } catch { message.error('加载 Mock 规则失败') }
  finally { loading.value = false }
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = defaultForm()
  headersText.value = '{}'
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
    response_body: record.response_body,
  }
  headersText.value = JSON.stringify(record.response_headers || {}, null, 2)
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
    response_body: record.response_body,
  }
  headersText.value = JSON.stringify(record.response_headers || {}, null, 2)
  formOpen.value = true
}

async function handleSave() {
  if (!form.value.name) { message.warning('请输入规则名称'); return }
  if (!form.value.path) { message.warning('请输入请求路径'); return }

  let parsedHeaders: Record<string, string> = {}
  try {
    parsedHeaders = JSON.parse(headersText.value || '{}')
  } catch {
    message.warning('响应头 JSON 格式不正确')
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
      delay_ms: form.value.delay_ms,
      is_enabled: form.value.is_enabled,
    }
    if (isEdit.value) {
      await mockRuleApi.update(editingId.value!, payload)
    } else {
      await mockRuleApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    formOpen.value = false
    loadRules()
  } catch { message.error('保存失败') }
  finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await mockRuleApi.delete(id)
    message.success('已删除')
    loadRules()
  } catch { message.error('删除失败') }
}

async function openLogs() {
  logsOpen.value = true
  await refreshLogs()
}

async function refreshLogs() {
  if (!projectId.value) return
  try {
    logs.value = await mockRuleApi.logs(projectId.value)
  } catch { message.error('加载日志失败') }
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
