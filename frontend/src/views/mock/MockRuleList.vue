<template>
  <div class="page-shell mock-page">
    <div>
      <h2 class="page-title">{{ t('mock.title') }}</h2>
      <div class="page-subtitle">{{ t('mock.subtitle') }}</div>
    </div>
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('mock.select_project')"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadRules"
        />
      </a-space>
      <a-space>
        <a-button :disabled="!projectId" @click="handleExportRules">
          {{ t('mock.export_rules') }}
        </a-button>
        <a-upload :show-upload-list="false" accept="application/json" :before-upload="beforeImportRules">
          <a-button :disabled="!projectId">{{ t('mock.import_rules') }}</a-button>
        </a-upload>
        <a-button :disabled="!projectId" @click="openLogs">
          <UnorderedListOutlined /> {{ t('mock.request_logs') }}
        </a-button>
        <a-button :disabled="!projectId || !selectedRuleIds.length" @click="openAIGeneration()">
          <ThunderboltOutlined /> {{ t('mock.ai_generate_selected') }}
        </a-button>
        <a-button :disabled="!projectId" @click="openAIMockGeneration()">
          <ThunderboltOutlined /> {{ t('mock.ai_generate_mock') }}
        </a-button>
        <a-button type="primary" :disabled="!projectId" @click="openCreate">
          <PlusOutlined /> {{ t('mock.add_rule') }}
        </a-button>
      </a-space>
    </div>

    <a-alert
      v-if="projectId"
      type="info"
      show-icon
      style="margin-bottom: 0"
      :message="t('mock.service_url', { url: mockBaseUrl })"
    >
      <template #description>
        {{ t('mock.service_desc_prefix') }} <code>/api/users/{id}</code>{{ t('mock.service_desc_suffix') }}
      </template>
    </a-alert>

    <a-table
      :columns="columns"
      :data-source="rules"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20 }"
      :scroll="{ x: 1640 }"
      :row-selection="{
        selectedRowKeys: selectedRuleIds,
        onChange: handleRuleSelectionChange,
      }"
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
          <a-tag :color="record.render_template ? 'blue' : 'default'">{{ record.render_template ? t('common.enabled') : t('common.disabled') }}</a-tag>
        </template>
        <template v-if="column.key === 'record_requests'">
          <a-tag :color="record.record_requests ? 'purple' : 'default'">{{ record.record_requests ? t('common.enabled') : t('common.disabled') }}</a-tag>
        </template>
        <template v-if="column.key === 'is_enabled'">
          <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? t('common.enabled') : t('common.disabled') }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openAIGeneration(asRule(record))">
              <ThunderboltOutlined />{{ t('mock.ai_generate') }}
            </a-button>
            <a-button type="link" size="small" @click="openAIMockGeneration(asRule(record))">
              <ThunderboltOutlined />{{ t('mock.ai_generate_mock_short') }}
            </a-button>
            <a-button type="link" size="small" @click="openEdit(asRule(record))">{{ t('common.edit') }}</a-button>
            <a-button type="link" size="small" @click="handleCopy(asRule(record))">{{ t('mock.copy') }}</a-button>
            <a-popconfirm :title="t('common.confirm_delete')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="aiMockGenerateOpen"
      :title="t('mock.ai_generate_mock_title')"
      :confirm-loading="aiMockGenerating"
      :ok-text="t('mock.ai_generate_confirm')"
      @ok="generateAIMockRules"
    >
      <a-alert
        type="info"
        show-icon
        :message="t('mock.ai_generate_hint')"
        :description="t('mock.ai_generate_review_hint')"
        style="margin-bottom: 16px"
      />
      <a-form layout="vertical">
        <a-form-item :label="t('mock.ai_rule_count')">
          <a-input-number v-model:value="aiMockRuleCount" :min="1" :max="20" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('mock.ai_requirement')">
          <a-textarea v-model:value="aiMockRequirement" :rows="5" :placeholder="t('mock.ai_requirement_placeholder')" />
        </a-form-item>
      </a-form>
      <div v-if="aiMockSourceRuleIds.length" style="color: var(--c-text-tertiary); font-size: 12px">
        {{ t('mock.ai_source_rules', { count: aiMockSourceRuleIds.length }) }}
      </div>
    </a-modal>

    <a-modal
      v-model:open="aiMockPreviewOpen"
      :title="t('mock.ai_preview_title')"
      :confirm-loading="aiMockSaving"
      :ok-text="t('mock.ai_save_confirm')"
      width="760px"
      @ok="saveAIMockRules"
    >
      <a-alert
        v-if="aiMockWarnings.length"
        type="warning"
        show-icon
        :message="aiMockWarnings.join('；')"
        style="margin-bottom: 12px"
      />
      <div style="margin-bottom: 8px; color: var(--c-text-secondary); font-size: 12px">
        {{ t('mock.ai_preview_hint') }}
      </div>
      <a-textarea v-model:value="aiMockPreviewText" :rows="18" class="code-textarea" />
    </a-modal>

    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? t('mock.edit_rule') : t('mock.add_rule')"
      :confirm-loading="saving"
      width="720px"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('mock.form.name')">
          <a-input v-model:value="form.name" :placeholder="t('mock.placeholders.name')" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('mock.form.method')">
              <a-select v-model:value="form.method" style="width: 100%">
                <a-select-option value="GET">GET</a-select-option>
                <a-select-option value="POST">POST</a-select-option>
                <a-select-option value="PUT">PUT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="PATCH">PATCH</a-select-option>
                <a-select-option value="ANY">{{ t('mock.any_method') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="16">
            <a-form-item :label="t('mock.form.path')">
              <a-input v-model:value="form.path" placeholder="/api/users/{id}" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('mock.form.status_code')">
              <a-input-number v-model:value="form.status_code" :min="100" :max="599" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('mock.form.delay_ms')">
              <a-input-number v-model:value="form.delay_ms" :min="0" :max="30000" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('common.enabled')">
              <a-switch v-model:checked="form.is_enabled" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('mock.form.render_template')">
              <a-switch v-model:checked="form.render_template" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('mock.form.record_requests')">
              <a-switch v-model:checked="form.record_requests" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" style="font-size: 13px">{{ t('mock.form.conditional_response') }}</a-divider>
        <a-form-item :label="t('mock.form.query_conditions')">
          <a-textarea v-model:value="queryConditionsText" :rows="2" class="code-textarea" placeholder='{"scene": "success"}' />
        </a-form-item>
        <a-form-item :label="t('mock.form.header_conditions')">
          <a-textarea v-model:value="headerConditionsText" :rows="2" class="code-textarea" placeholder='{"x-env": "test"}' />
        </a-form-item>
        <a-form-item :label="t('mock.form.body_conditions')">
          <a-textarea v-model:value="bodyConditionsText" :rows="2" class="code-textarea" placeholder='{"status": "paid"}' />
        </a-form-item>

        <a-form-item :label="t('mock.form.response_headers')">
          <a-textarea
            v-model:value="headersText"
            :rows="2"
            class="code-textarea"
            placeholder='{"Content-Type": "application/json"}'
          />
        </a-form-item>

        <a-form-item>
          <template #label>
            <span>{{ t('mock.form.response_body') }}</span>
            <a-button type="link" size="small" style="margin-left: 8px" @click="formatResponseBody">{{ t('mock.format_json') }}</a-button>
          </template>
          <a-textarea
            v-model:value="(form.response_body as string | undefined)"
            :rows="8"
            class="code-textarea"
            placeholder='{"code": 0, "message": "success"}'
          />
          <div style="margin-top: 8px; color: var(--c-text-tertiary); font-size: 12px">
            {{ t('mock.template_hint_prefix') }} <code v-pre>{{query.xxx}}</code> / <code v-pre>{{headers.xxx}}</code> / <code v-pre>{{body.xxx}}</code> {{ t('mock.template_hint_suffix') }}
          </div>
        </a-form-item>

        <a-form-item v-if="isEdit && form.record_requests" :label="t('mock.form.recorded_samples')">
          <a-textarea :value="JSON.stringify(currentSamples, null, 2)" :rows="6" class="code-textarea" readonly />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:open="logsOpen"
      :title="t('mock.request_logs')"
      width="600"
      :extra="undefined"
    >
      <a-button style="margin-bottom: 12px" size="small" @click="refreshLogs">{{ t('common.refresh') }}</a-button>
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
            <a-tag :color="record.matched ? 'green' : 'red'">{{ record.matched ? t('mock.matched') : t('mock.not_matched') }}</a-tag>
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
import { PlusOutlined, ThunderboltOutlined, UnorderedListOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { mockRuleApi, projectApi, type MockAIGeneratedRule, type MockRuleItem, type ProjectItem } from '@/api'
import { getBackendOrigin } from '@/api/http'
import { buildCasesQuery } from '@/utils/caseNavigation'
// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asRule = (record: unknown) => record as MockRuleRecord

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

type MockLogRecord = Record<string, unknown>
type TableTextRender = { text?: string | number | null }

const { t } = useI18n()
const router = useRouter()
const rules = ref<MockRuleRecord[]>([])
const loading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const selectedRuleIds = ref<number[]>([])

const aiMockGenerateOpen = ref(false)
const aiMockPreviewOpen = ref(false)
const aiMockGenerating = ref(false)
const aiMockSaving = ref(false)
const aiMockRequirement = ref('')
const aiMockRuleCount = ref(1)
const aiMockSourceRuleIds = ref<number[]>([])
const aiMockPreviewText = ref('[]')
const aiMockWarnings = ref<string[]>([])

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
const logs = ref<MockLogRecord[]>([])
const currentSamples = ref<Array<Record<string, unknown>>>([])

const mockBaseUrl = computed(() =>
  projectId.value ? `${getBackendOrigin()}/mock/${projectId.value}` : '',
)

const columns = computed(() => [
  { title: t('mock.columns.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('mock.columns.method'), key: 'method', width: 90 },
  { title: t('mock.columns.path'), dataIndex: 'path', key: 'path', ellipsis: true },
  { title: t('mock.columns.conditions'), key: 'conditions', width: 180 },
  { title: t('mock.columns.version'), dataIndex: 'version', key: 'version', width: 70 },
  { title: t('mock.columns.template'), key: 'render_template', width: 70 },
  { title: t('mock.columns.recording'), key: 'record_requests', width: 70 },
  { title: t('mock.columns.status_code'), key: 'status_code', width: 80 },
  { title: t('mock.columns.delay'), dataIndex: 'delay_ms', width: 80, customRender: ({ text }: TableTextRender) => `${text ?? 0}ms` },
  { title: t('mock.columns.status'), key: 'is_enabled', width: 70 },
  { title: t('mock.columns.updated_at'), dataIndex: 'updated_at', width: 170,
    customRender: ({ text }: TableTextRender) => typeof text === 'string' ? text.slice(0, 19).replace('T', ' ') : '-' },
  { title: t('mock.columns.action'), key: 'action', width: 420, fixed: 'right' as const },
])

const logColumns = computed(() => [
  { title: t('mock.log_columns.method'), key: 'method', width: 80 },
  { title: t('mock.log_columns.path'), dataIndex: 'path', key: 'path', ellipsis: true },
  { title: t('mock.log_columns.status'), key: 'matched', width: 80 },
  { title: t('mock.log_columns.rule'), dataIndex: 'rule_name', key: 'rule_name', ellipsis: true },
  { title: t('mock.log_columns.status_code'), dataIndex: 'status_code', width: 70 },
  { title: t('mock.log_columns.time'), key: 'timestamp', width: 80 },
])

function getErrorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
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
  return parts.length ? parts.join(' / ') : t('mock.no_conditions')
}

function formatResponseBody() {
  if (!form.value.response_body) return
  try {
    const parsed = JSON.parse(form.value.response_body)
    form.value.response_body = JSON.stringify(parsed, null, 2)
  } catch {
    message.warning(t('mock.msg.response_body_invalid_json'))
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
    throw new Error(t('mock.msg.field_json_invalid', { field: fieldName }))
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
    projectOptions.value = projects.map((p: ProjectItem) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadRules() {
  selectedRuleIds.value = []
  if (!projectId.value) { rules.value = []; return }
  loading.value = true
  try {
    rules.value = await mockRuleApi.list({ project_id: projectId.value })
  } catch {
    rules.value = []
    message.error(getErrorMessage(undefined, t('mock.msg.load_failed')))
  }
  finally { loading.value = false }
}

const MAX_AI_MOCK_RULES = 20

function handleRuleSelectionChange(keys: (string | number)[]) {
  const normalized = [...new Set(keys.map((key) => Number(key)).filter((key) => Number.isInteger(key) && key > 0))]
  if (normalized.length > MAX_AI_MOCK_RULES) {
    selectedRuleIds.value = normalized.slice(0, MAX_AI_MOCK_RULES)
    message.warning(t('mock.ai_generate_max_rules', { count: MAX_AI_MOCK_RULES }))
    return
  }
  selectedRuleIds.value = normalized
}

function openAIGeneration(record?: MockRuleRecord) {
  if (!projectId.value) return
  const ruleIds = record ? [record.id] : selectedRuleIds.value
  if (!ruleIds.length) return
  void router.push({
    name: 'cases',
    query: buildCasesQuery({
      projectId: projectId.value,
      aiGenerate: true,
      aiMockRuleIds: ruleIds,
    }),
  })
}

function openAIMockGeneration(record?: MockRuleRecord) {
  if (!projectId.value) return
  aiMockSourceRuleIds.value = record ? [record.id] : [...selectedRuleIds.value]
  aiMockRequirement.value = ''
  aiMockRuleCount.value = 1
  aiMockWarnings.value = []
  aiMockGenerateOpen.value = true
}

async function generateAIMockRules() {
  if (!projectId.value) return
  aiMockGenerating.value = true
  try {
    const result = await mockRuleApi.aiGenerate({
      project_id: projectId.value,
      rule_ids: aiMockSourceRuleIds.value,
      requirement: aiMockRequirement.value,
      rule_count: aiMockRuleCount.value,
    })
    aiMockPreviewText.value = JSON.stringify(result.rules, null, 2)
    aiMockWarnings.value = result.warnings || []
    aiMockGenerateOpen.value = false
    aiMockPreviewOpen.value = true
    message.success(t('mock.ai_generate_success'))
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('mock.ai_generate_failed')))
  } finally {
    aiMockGenerating.value = false
  }
}

function parseAIMockPreview(): MockAIGeneratedRule[] {
  let parsed: unknown
  try {
    parsed = JSON.parse(aiMockPreviewText.value)
  } catch {
    throw new Error(t('mock.ai_preview_invalid'))
  }
  if (!Array.isArray(parsed) || !parsed.length) {
    throw new Error(t('mock.ai_preview_array_required'))
  }
  return parsed.map((item) => {
    if (!item || typeof item !== 'object') throw new Error(t('mock.ai_preview_item_invalid'))
    const rule = item as Partial<MockAIGeneratedRule>
    if (!rule.name || !rule.path) throw new Error(t('mock.ai_preview_required'))
    return {
      name: String(rule.name),
      method: String(rule.method || 'GET').toUpperCase(),
      path: String(rule.path).startsWith('/') ? String(rule.path) : `/${String(rule.path)}`,
      status_code: Number(rule.status_code || 200),
      response_headers: (rule.response_headers || {}) as Record<string, string>,
      response_body: rule.response_body == null ? null : String(rule.response_body),
      match_conditions: (rule.match_conditions || { query: {}, headers: {}, body: {} }) as Record<string, Record<string, string>>,
      delay_ms: Number(rule.delay_ms || 0),
      is_enabled: rule.is_enabled !== false,
      render_template: rule.render_template === true,
      record_requests: rule.record_requests === true,
    }
  })
}

async function saveAIMockRules() {
  if (!projectId.value) return
  let generatedRules: MockAIGeneratedRule[]
  try {
    generatedRules = parseAIMockPreview()
  } catch (error: unknown) {
    message.warning(getErrorMessage(error, t('mock.ai_preview_invalid')))
    return
  }
  aiMockSaving.value = true
  try {
    for (const rule of generatedRules) {
      await mockRuleApi.create({ ...rule, project_id: projectId.value })
    }
    aiMockPreviewOpen.value = false
    message.success(t('mock.ai_save_success', { count: generatedRules.length }))
    void loadRules()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('mock.msg.save_failed')))
  } finally {
    aiMockSaving.value = false
  }
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
    name: t('mock.copy_name', { name: record.name }),
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
  if (!form.value.name) { message.warning(t('mock.msg.name_required')); return }
  if (!form.value.path) { message.warning(t('mock.msg.path_required')); return }

  let parsedHeaders: Record<string, string> = {}
  let matchConditions: MatchConditions
  try {
    parsedHeaders = parseJsonObject(headersText.value, t('mock.form.response_headers_short'))
    matchConditions = {
      query: parseJsonObject(queryConditionsText.value, t('mock.form.query_conditions_short')),
      headers: parseJsonObject(headerConditionsText.value, t('mock.form.header_conditions_short')),
      body: parseJsonObject(bodyConditionsText.value, t('mock.form.body_conditions_short')),
    }
  } catch (error: unknown) {
    message.warning(getErrorMessage(error, t('mock.msg.json_invalid')))
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
    message.success(isEdit.value ? t('mock.msg.update_success') : t('mock.msg.create_success'))
    formOpen.value = false
    void loadRules()
  } catch {
    message.error(getErrorMessage(undefined, t('mock.msg.save_failed')))
  }
  finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await mockRuleApi.delete(id)
    message.success(t('mock.msg.delete_success'))
    void loadRules()
  } catch {
    message.error(getErrorMessage(undefined, t('mock.msg.delete_failed')))
  }
}

async function handleExportRules() {
  if (!projectId.value) return
  try {
    const result = await mockRuleApi.exportRules(projectId.value)
    downloadJson(result, `mock-rules-project-${projectId.value}.json`)
    message.success(t('mock.msg.export_success'))
  } catch {
    message.error(getErrorMessage(undefined, t('mock.msg.export_failed')))
  }
}

async function beforeImportRules(file: File) {
  if (!projectId.value) return false
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const rules = Array.isArray(data.rules) ? data.rules : []
    if (rules.length === 0) {
      message.warning(t('mock.msg.import_empty'))
      return false
    }
    await mockRuleApi.importRules({ project_id: projectId.value, rules })
    message.success(t('mock.msg.import_success'))
    void loadRules()
  } catch {
    message.error(getErrorMessage(undefined, t('mock.msg.import_failed')))
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
    message.error(getErrorMessage(undefined, t('mock.msg.load_logs_failed')))
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
