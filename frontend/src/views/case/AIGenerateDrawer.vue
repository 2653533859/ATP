<template>
  <a-drawer
    :open="open"
    :title="t('case.ai.title')"
    width="900px"
    :destroy-on-close="true"
    @close="$emit('close')"
  >
    <a-alert
      v-if="moduleId == null"
      type="warning"
      :message="t('case.ai.select_module_alert')"
      style="margin-bottom: 16px"
    />

    <a-card :title="t('case.ai.source_title')" size="small" style="margin-bottom: 16px">
      <a-radio-group v-model:value="sourceType" style="margin-bottom: 8px">
        <a-radio value="openapi">{{ t('case.ai.source_types.openapi') }}</a-radio>
        <a-radio value="postman">{{ t('case.ai.source_types.postman') }}</a-radio>
        <a-radio value="curl">{{ t('case.ai.curl_command') }}</a-radio>
        <a-radio value="sample">{{ t('case.ai.interface_sample') }}</a-radio>
        <a-radio value="natural">{{ t('case.ai.natural_language') }}</a-radio>
      </a-radio-group>
      <a-alert
        v-if="sourceType === 'natural'"
        type="info"
        :message="t('case.ai.natural_hint')"
        style="margin-bottom: 8px"
      />
      <a-textarea
        v-else
        v-model:value="schemaText"
        :rows="6"
        :placeholder="placeholderForType"
      />
      <div v-if="sourceType !== 'natural'" style="margin-top: 8px; display: flex; gap: 8px; align-items: center">
        <a-button :loading="parsing" :disabled="!schemaText.trim()" @click="handleParse">
          {{ t('case.ai.parse') }}
        </a-button>
        <a-button v-if="parsedEndpoints.length" size="small" @click="clearParsed">
          {{ t('case.ai.clear_parsed') }}
        </a-button>
        <a-button
          v-if="parsedEndpoints.length"
          size="small"
          :loading="importing"
          :disabled="!selectedEndpointKeys.length || !moduleId"
          @click="handleImportSelected"
        >
          {{ t('case.ai.import_selected') }}
        </a-button>
        <span style="color: #888">
          {{ t('case.ai.parse_hint') }}
        </span>
        <a-select
          v-if="sourceType === 'openapi'"
          v-model:value="externalRefPolicy"
          size="small"
          style="width: 170px"
          :aria-label="t('case.ai.external_ref_policy_label')"
        >
          <a-select-option value="warn">{{ t('case.ai.external_ref_policy_warn') }}</a-select-option>
          <a-select-option value="reject">{{ t('case.ai.external_ref_policy_reject') }}</a-select-option>
        </a-select>
      </div>
      <div v-if="sourceType === 'openapi'" class="generation-context-hint">
        {{ t('case.ai.external_ref_policy_hint') }}
      </div>
      <a-alert
        v-for="(w, idx) in parseWarnings"
        :key="idx"
        type="warning"
        :message="w"
        style="margin-top: 8px"
      />
    </a-card>

    <a-card v-if="parsedEndpoints.length" :title="t('case.ai.select_endpoint_title')" size="small" style="margin-bottom: 16px">
      <a-table
        :data-source="parsedEndpoints"
        :columns="endpointColumns"
        :pagination="false"
        size="small"
        row-key="rowKey"
        :row-selection="{
          selectedRowKeys: selectedEndpointKeys,
          onChange: (keys: (string | number)[]) => (selectedEndpointKeys = keys as string[]),
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'method'">
            <a-tag :color="methodColor(record.method)">{{ record.method }}</a-tag>
          </template>
        </template>
      </a-table>
      <div style="margin-top: 8px; color: #888">
        {{ t('case.ai.selected_endpoint_count', { selected: selectedEndpointKeys.length, total: parsedEndpoints.length }) }}
      </div>
    </a-card>

    <a-card :title="t('case.ai.params_title')" size="small" style="margin-bottom: 16px">
      <a-form layout="vertical">
        <a-form-item :label="t('case.ai.requirement_label')">
          <a-textarea
            v-model:value="userRequirement"
            :rows="4"
            :placeholder="t('case.ai.requirement_placeholder')"
          />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('case.ai.dataset_label')">
              <a-select
                v-model:value="datasetId"
                allow-clear
                :loading="contextLoading"
                :options="datasetOptions"
                :placeholder="t('case.ai.dataset_placeholder')"
                @change="handleDatasetChange"
              />
              <div class="generation-context-hint">{{ t('case.ai.dataset_hint') }}</div>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('case.ai.mock_rules_label')">
              <a-select
                v-model:value="mockRuleIds"
                mode="multiple"
                allow-clear
                :loading="contextLoading"
                :options="mockRuleOptions"
                :placeholder="t('case.ai.mock_rules_placeholder')"
                :max-tag-count="2"
                :max-count="MAX_AI_MOCK_RULES"
                @change="handleMockRuleChange"
              />
              <div class="generation-context-hint">{{ t('case.ai.mock_rules_hint') }}</div>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="6">
            <a-form-item :label="t('case.ai.case_type')">
              <a-select v-model:value="caseType" :options="caseTypeOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item :label="t('case.filters.priority')">
              <a-select v-model:value="priority" :options="priorityOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item :label="t('case.ai.case_level')">
              <a-select v-model:value="caseLevel" :options="caseLevelOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item :label="t('case.ai.max_cases')">
              <a-input-number
                v-model:value="maxCases"
                :min="1"
                :max="20"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <div>
          <a-button
            type="primary"
            :loading="generating"
            :disabled="!canGenerate"
            @click="handleGenerate"
          >
            {{ t('case.ai.generate_drafts') }}
          </a-button>
          <span v-if="!canGenerate" style="margin-left: 12px; color: #faad14">
            {{ t('case.ai.generate_disabled_hint') }}
          </span>
        </div>
        <a-alert
          v-for="(w, idx) in generateWarnings"
          :key="idx"
          type="warning"
          :message="w"
          style="margin-top: 8px"
        />
      </a-form>
    </a-card>

    <a-card
      v-if="drafts.length"
      :title="t('case.ai.drafts_title', { count: drafts.length })"
      size="small"
      style="margin-bottom: 16px"
    >
      <a-table
        :data-source="draftRows"
        :columns="draftColumns"
        :pagination="false"
        size="small"
        row-key="rowKey"
        :row-selection="{
          selectedRowKeys: selectedDraftKeys,
          onChange: (keys: (string | number)[]) => (selectedDraftKeys = keys as string[]),
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'draftAction'">
            <a-button type="link" size="small" @click="openDraftEditor(asDraft(record))">
              {{ t('common.edit') }}
            </a-button>
          </template>
        </template>
        <template #expandedRowRender="{ record }">
          <div style="padding: 8px 0; background: #fafafa">
            <p v-if="record.description"><b>{{ t('case.ai.description_prefix') }}</b>{{ record.description }}</p>
            <p v-if="record.preconditions?.length">
              <b>{{ t('case.ai.preconditions_prefix') }}</b>{{ (record.preconditions as string[]).join(t('case.ai.list_separator')) }}
            </p>
            <a-table
              :data-source="record.steps"
              :columns="stepColumns"
              :pagination="false"
              size="small"
              row-key="action"
            />
          </div>
        </template>
      </a-table>
      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: center">
        <a-button
          type="primary"
          :loading="saving"
          :disabled="!selectedDraftKeys.length || !moduleId"
          @click="handleSaveSelected"
        >
          {{ t('case.ai.save_selected', { count: selectedDraftKeys.length }) }}
        </a-button>
        <a-button @click="resetGeneration">{{ t('case.ai.clear_drafts') }}</a-button>
      </div>
    </a-card>
  </a-drawer>

  <a-modal
    v-model:open="draftEditorOpen"
    :title="t('case.ai.edit_draft_title')"
    :ok-text="t('common.save')"
    :cancel-text="t('common.cancel')"
    width="760px"
    @ok="saveDraftEditor"
  >
    <a-form layout="vertical">
      <a-form-item :label="t('common.name')" required>
        <a-input v-model:value="draftEditor.name" />
      </a-form-item>
      <a-form-item :label="t('case.detail.summary')">
        <a-input v-model:value="(draftEditor.summary as string | undefined)" />
      </a-form-item>
      <a-form-item :label="t('common.description')">
        <a-textarea v-model:value="(draftEditor.description as string | undefined)" :rows="3" />
      </a-form-item>
      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item :label="t('case.filters.priority')">
            <a-select v-model:value="draftEditor.priority" :options="priorityOptions" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.ai.case_level')">
            <a-select v-model:value="draftEditor.case_level" :options="caseLevelOptions" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('case.ai.case_type')">
            <a-select v-model:value="draftEditor.case_type" :options="caseTypeOptions" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('case.detail.tags')">
        <a-select
          v-model:value="draftEditor.tags"
          mode="tags"
          :placeholder="t('case.drawer.tags_placeholder_simple')"
          style="width: 100%"
        />
      </a-form-item>
      <a-form-item :label="t('case.ai.steps_json')">
        <a-textarea
          v-model:value="draftEditorStepsJson"
          :rows="8"
          :placeholder="t('case.ai.steps_json_placeholder')"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  aiCaseGenerationApi,
  caseApi,
  datasetApi,
  mockRuleApi,
  type AICaseDraft,
  type AICaseGenerationSource,
  type AICaseStepDraft,
  type AIEndpointSummary,
  type CaseImportResult,
  type CaseSavePayload,
  type DatasetListItem,
  type MockRuleItem,
  type CaseLevel,
  type CasePriority,
  type CaseType,
  type SchemaSourceType,
} from '@/api'

// a-table #bodyCell 的 record 是 Record<string, any>；草稿行类型在此断言收窄
const asDraft = (record: unknown) => record as AICaseDraft & { rowKey?: string }

type GenerationSourceType = SchemaSourceType | 'natural'

const props = defineProps<{
  open: boolean
  projectId: number | null
  moduleId: number | null
  allowedCaseTypes?: CaseType[]
  initialDatasetId?: number | null
  initialDatasetVersion?: number | null
  initialMockRuleIds?: number[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const { t } = useI18n()

const sourceType = ref<GenerationSourceType>('openapi')
const schemaText = ref('')
const externalRefPolicy = ref<'warn' | 'reject'>('warn')
const parsing = ref(false)
const importing = ref(false)
const parsedEndpoints = ref<(AIEndpointSummary & { rowKey: string })[]>([])
const selectedEndpointKeys = ref<string[]>([])
const parseWarnings = ref<string[]>([])

const userRequirement = ref('')
const caseType = ref<CaseType>('api')
const priority = ref<CasePriority>('P2')
const caseLevel = ref<CaseLevel>('regression')
const maxCases = ref(5)
const MAX_AI_MOCK_RULES = 20
const datasetId = ref<number | undefined>(undefined)
const datasetVersion = ref<number | null>(null)
const mockRuleIds = ref<number[]>([])
const availableDatasets = ref<DatasetListItem[]>([])
const availableMockRules = ref<MockRuleItem[]>([])
const contextLoading = ref(false)

const generating = ref(false)
const generateWarnings = ref<string[]>([])
const drafts = ref<AICaseDraft[]>([])
const selectedDraftKeys = ref<string[]>([])
const generationSource = ref<AICaseGenerationSource | null>(null)

const saving = ref(false)
const draftEditorOpen = ref(false)
const draftEditorIndex = ref<number | null>(null)
const draftEditorStepsJson = ref('')
const draftEditor = ref<AICaseDraft>({
  name: '',
  summary: '',
  description: '',
  case_type: 'api',
  priority: 'P2',
  case_level: 'regression',
  tags: [],
  preconditions: [],
  postconditions: [],
  steps: [],
  config: {},
})

type DraftRecordRender = { record: AICaseDraft }
type TableIndexRender = { index: number }
type ErrorLike = {
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
  }
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return fallback
}

const placeholderForType = computed(() => {
  switch (sourceType.value) {
    case 'openapi':
      return t('case.ai.placeholders.openapi')
    case 'postman':
      return t('case.ai.placeholders.postman')
    case 'curl':
      return t('case.ai.placeholders.curl')
    case 'sample':
      return t('case.ai.placeholders.sample')
    case 'natural':
      return t('case.ai.requirement_placeholder')
    default:
      return ''
  }
})

const caseTypeOptions = computed<Array<{ label: string; value: CaseType }>>(() => ([
  { label: t('case.types.api'), value: 'api' },
  { label: t('case.types.graphql'), value: 'graphql' },
  { label: t('case.types.websocket'), value: 'websocket' },
  { label: t('case.types.grpc'), value: 'grpc' },
  { label: t('case.types.web'), value: 'web' },
  { label: t('case.types.android'), value: 'android' },
] as Array<{ label: string; value: CaseType }>).filter((item) => !props.allowedCaseTypes?.length || props.allowedCaseTypes.includes(item.value)))
const priorityOptions = ['P0', 'P1', 'P2', 'P3'].map((v) => ({ label: v, value: v }))
const caseLevelOptions = computed(() => [
  { label: t('case.levels.smoke'), value: 'smoke' },
  { label: t('case.levels.core'), value: 'core' },
  { label: t('case.levels.regression'), value: 'regression' },
  { label: t('case.levels.extended'), value: 'extended' },
])

const datasetOptions = computed(() => availableDatasets.value.map((dataset) => ({
  label: `${dataset.name} (${dataset.row_count})`,
  value: dataset.id,
})))

const mockRuleOptions = computed(() => availableMockRules.value.map((rule) => ({
  label: `${rule.method} ${rule.path} · ${rule.name}`,
  value: rule.id,
})))

const endpointColumns = computed(() => [
  { title: t('case.ai.endpoint_columns.method'), key: 'method', dataIndex: 'method', width: 90 },
  { title: t('case.ai.endpoint_columns.path'), key: 'path', dataIndex: 'path' },
  { title: t('case.detail.summary'), key: 'summary', dataIndex: 'summary', ellipsis: true },
])

const draftColumns = computed(() => [
  { title: t('common.name'), dataIndex: 'name', key: 'name' },
  { title: t('case.detail.summary'), dataIndex: 'summary', key: 'summary', ellipsis: true },
  { title: t('case.ai.step_count'), key: 'stepCount', width: 80, customRender: ({ record }: DraftRecordRender) => record.steps?.length ?? 0 },
  { title: t('case.filters.priority'), dataIndex: 'priority', key: 'priority', width: 80 },
  { title: t('common.actions'), key: 'draftAction', width: 90 },
])

const stepColumns = computed(() => [
  { title: '#', key: 'idx', width: 50, customRender: ({ index }: TableIndexRender) => index + 1 },
  { title: t('case.ai.action'), dataIndex: 'action', key: 'action' },
  { title: t('case.detail.test_data'), dataIndex: 'test_data', key: 'test_data', ellipsis: true },
  { title: t('case.detail.expected_result'), dataIndex: 'expected_result', key: 'expected_result', ellipsis: true },
])

const draftRows = computed(() => drafts.value.map((d, i) => ({ ...d, rowKey: String(i) })))

const canGenerate = computed(() => {
  if (props.moduleId == null) return false
  if (selectedEndpointKeys.value.length > 0) return true
  return userRequirement.value.trim().length > 0
})

function methodColor(method: string) {
  const m = method.toUpperCase()
  if (m === 'GET') return 'blue'
  if (m === 'POST') return 'green'
  if (m === 'PUT' || m === 'PATCH') return 'orange'
  if (m === 'DELETE') return 'red'
  return 'default'
}

async function handleParse() {
  if (sourceType.value === 'natural') return
  parsing.value = true
  parseWarnings.value = []
  try {
    const result = await aiCaseGenerationApi.parseSchema({
      source_type: sourceType.value,
      content: schemaText.value,
      external_ref_policy: sourceType.value === 'openapi' ? externalRefPolicy.value : 'warn',
    })
    parsedEndpoints.value = result.endpoints.map((e, i) => ({
      ...e,
      rowKey: `${e.method}:${e.path}:${i}`,
    }))
    selectedEndpointKeys.value = parsedEndpoints.value.map((e) => e.rowKey)
    parseWarnings.value = result.warnings ?? []
    if (parsedEndpoints.value.length === 0) {
      message.warning(t('case.ai.msg.no_endpoints'))
    } else {
      message.success(t('case.ai.msg.parsed', { count: parsedEndpoints.value.length }))
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.ai.msg.parse_failed')))
  } finally {
    parsing.value = false
  }
}

function clearParsed() {
  parsedEndpoints.value = []
  selectedEndpointKeys.value = []
  parseWarnings.value = []
}

function endpointToCaseConfig(endpoint: AIEndpointSummary) {
  const base = (endpoint.base_url ?? '').replace(/\/$/, '')
  const path = endpoint.path.startsWith('/') ? endpoint.path : `/${endpoint.path}`
  const url = `${base}${path}`.replace(/\{([^}]+)\}/g, '{{\$1}}')
  const headers: Record<string, string> = {}
  const params: Record<string, string> = {}
  for (const parameter of endpoint.parameters ?? []) {
    const value = parameter.example == null ? `{{${parameter.name}}}` : String(parameter.example)
    if (parameter.location === 'header') headers[parameter.name] = value
    if (parameter.location === 'query') params[parameter.name] = value
  }
  const body = endpoint.request_body_example
  const bodyType = body == null ? 'none' : typeof body === 'object' ? 'json' : 'raw'
  const expectedStatus = endpoint.response_status ?? 200
  return {
    steps: [{
      name: endpoint.summary || `${endpoint.method} ${endpoint.path}`,
      url,
      method: endpoint.method.toUpperCase(),
      headers,
      params,
      body_type: bodyType,
      body: body ?? null,
      assertions: [{ target: 'status_code', operator: 'eq', expected: String(expectedStatus) }],
      extractions: [],
    }],
  }
}

async function importWithPreview(payloads: CaseSavePayload[]): Promise<CaseImportResult | null> {
  if (props.projectId == null) {
    message.warning(t('case.ai.msg.select_project_module'))
    return null
  }
  const preview = await caseApi.previewImport(props.projectId, payloads)
  if (preview.errors.length) {
    message.error(preview.errors.slice(0, 3).join(t('case.ai.list_separator')))
    return null
  }

  let policy: 'fail' | 'skip' = 'fail'
  if (preview.conflicts.length) {
    const conflictNames = preview.conflicts
      .slice(0, 5)
      .map((item) => item.name)
      .join(t('case.ai.list_separator'))
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: t('case.ai.msg.import_conflict_title', { count: preview.conflicts.length }),
        content: t('case.ai.msg.import_conflict_content', {
          names: conflictNames,
          more: preview.conflicts.length > 5 ? t('case.ai.msg.import_conflict_more') : '',
        }),
        okText: t('case.ai.msg.import_conflict_confirm'),
        cancelText: t('common.cancel'),
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
    if (!confirmed) return null
    policy = 'skip'
  }
  return caseApi.importCases(props.projectId, payloads, policy)
}

async function handleImportSelected() {
  if (props.moduleId == null) {
    message.warning(t('case.ai.msg.no_module'))
    return
  }
  const selected = new Set(selectedEndpointKeys.value)
  const targets = parsedEndpoints.value.filter((endpoint) => selected.has(endpoint.rowKey))
  if (!targets.length) return
  importing.value = true
  try {
    const result = await importWithPreview(targets.map((endpoint) => ({
      name: endpoint.summary || `${endpoint.method} ${endpoint.path}`,
      description: endpoint.description ?? undefined,
      case_type: 'api',
      module_id: props.moduleId!,
      priority: priority.value,
      case_level: caseLevel.value,
      tags: [...new Set(['imported', sourceType.value])],
      config: endpointToCaseConfig(endpoint),
      steps: [{
        action: `发送 ${endpoint.method.toUpperCase()} ${endpoint.path}`,
        expected_result: `返回 ${endpoint.response_status ?? 200} 状态码`,
        is_key_step: true,
      }],
    })))
    if (!result) return
    if (result.skipped_count) {
      message.warning(t('case.ai.msg.import_done_with_skips', { imported: result.imported, skipped: result.skipped_count }))
    } else {
      message.success(t('case.ai.msg.import_success', { count: result.imported }))
    }
    if (result.imported) emit('saved')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.ai.msg.import_failed')))
  } finally {
    importing.value = false
  }
}

function resetGeneration() {
  drafts.value = []
  selectedDraftKeys.value = []
  generateWarnings.value = []
  generationSource.value = null
  externalRefPolicy.value = 'warn'
}

function cloneDraft(draft: AICaseDraft): AICaseDraft {
  return {
    ...draft,
    tags: [...(draft.tags ?? [])],
    preconditions: [...(draft.preconditions ?? [])],
    postconditions: [...(draft.postconditions ?? [])],
    steps: (draft.steps ?? []).map((step) => ({ ...step })),
    config: { ...(draft.config ?? {}) },
  }
}

function openDraftEditor(record: AICaseDraft & { rowKey?: string }) {
  const index = Number(record.rowKey)
  if (!Number.isInteger(index) || !drafts.value[index]) return
  draftEditorIndex.value = index
  draftEditor.value = cloneDraft(drafts.value[index])
  draftEditorStepsJson.value = JSON.stringify(draftEditor.value.steps ?? [], null, 2)
  draftEditorOpen.value = true
}

function normalizeDraftSteps(raw: unknown): AICaseStepDraft[] {
  if (!Array.isArray(raw)) throw new Error(t('case.ai.msg.steps_json_array_required'))
  return raw.map((item) => {
    if (!item || typeof item !== 'object') {
      throw new Error(t('case.ai.msg.steps_json_object_required'))
    }
    const step = item as Partial<AICaseStepDraft>
    const action = String(step.action ?? '').trim()
    if (!action) throw new Error(t('case.ai.msg.steps_json_action_required'))
    return {
      action,
      test_data: step.test_data ?? null,
      expected_result: step.expected_result ?? null,
      is_key_step: Boolean(step.is_key_step),
      remarks: step.remarks ?? null,
    }
  })
}

function saveDraftEditor() {
  if (draftEditorIndex.value == null) return
  const name = draftEditor.value.name.trim()
  if (!name) {
    message.warning(t('case.ai.msg.name_required'))
    return
  }
  let steps: AICaseStepDraft[]
  try {
    steps = normalizeDraftSteps(JSON.parse(draftEditorStepsJson.value || '[]'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.ai.msg.steps_json_invalid')))
    return
  }
  drafts.value[draftEditorIndex.value] = {
    ...cloneDraft(draftEditor.value),
    name,
    steps,
  }
  draftEditorOpen.value = false
  message.success(t('common.saved'))
}

async function handleGenerate() {
  if (props.projectId == null || props.moduleId == null) {
    message.warning(t('case.ai.msg.select_project_module'))
    return
  }
  generating.value = true
  resetGeneration()
  try {
    const selectedSet = new Set(selectedEndpointKeys.value)
    const selectedEndpoints = parsedEndpoints.value
      .filter((e) => selectedSet.has(e.rowKey))
      .map(({ rowKey: _rowKey, ...rest }) => rest)
    const result = await aiCaseGenerationApi.generate({
      project_id: props.projectId,
      module_id: props.moduleId,
      endpoints: selectedEndpoints,
      user_requirement: userRequirement.value,
      case_type: caseType.value,
      priority: priority.value,
      case_level: caseLevel.value,
      max_cases: maxCases.value,
      dataset_id: datasetId.value ?? null,
      dataset_version: datasetVersion.value,
      mock_rule_ids: mockRuleIds.value,
    })
    drafts.value = result.drafts ?? []
    selectedDraftKeys.value = drafts.value.map((_, i) => String(i))
    generationSource.value = result.source ?? null
    generateWarnings.value = result.warnings ?? []
    if (!drafts.value.length) {
      message.warning(t('case.ai.msg.no_drafts'))
    } else {
      message.success(t('case.ai.msg.generated', { count: drafts.value.length }))
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.ai.msg.generate_failed')))
  } finally {
    generating.value = false
  }
}

async function handleSaveSelected() {
  if (props.moduleId == null) {
    message.warning(t('case.ai.msg.no_module'))
    return
  }
  const selectedSet = new Set(selectedDraftKeys.value)
  const targets = drafts.value.filter((_, i) => selectedSet.has(String(i)))
  if (!targets.length) return

  saving.value = true
  try {
    const result = await importWithPreview(targets.map((draft) => {
      const boundDatasetId = draft.dataset_id ?? datasetId.value ?? null
      const boundDatasetVersion = draft.dataset_version ?? datasetVersion.value
      return {
        name: draft.name,
        description: draft.description ?? undefined,
        summary: draft.summary ?? undefined,
        case_type: draft.case_type,
        module_id: props.moduleId!,
        dataset_id: boundDatasetId,
        dataset_version: boundDatasetVersion,
        tags: draft.tags ?? [],
        preconditions: draft.preconditions ?? [],
        postconditions: draft.postconditions ?? [],
        priority: draft.priority,
        case_level: draft.case_level,
        steps: (draft.steps ?? []).map((s) => ({
          action: s.action,
          test_data: s.test_data ?? null,
          expected_result: s.expected_result ?? null,
          is_key_step: !!s.is_key_step,
          remarks: s.remarks ?? null,
        })),
        config: {
          ...(draft.config ?? {}),
          _ai_generated: true,
          _ai_source: {
            ...(generationSource.value ?? {}),
            dataset_id: boundDatasetId,
            dataset_version: boundDatasetVersion,
            mock_rule_ids: [...new Set(mockRuleIds.value)],
          },
        },
      }
    }))
    if (!result) return
    if (result.skipped_count) {
      message.warning(t('case.ai.msg.import_done_with_skips', { imported: result.imported, skipped: result.skipped_count }))
    } else {
      message.success(t('case.ai.msg.save_success', { count: result.imported }))
    }
    if (result.imported) emit('saved')
    if (result.imported && !result.skipped_count) emit('close')
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.ai.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function loadGenerationContext() {
  if (props.projectId == null) return
  contextLoading.value = true
  try {
    const [datasets, mockRules] = await Promise.all([
      datasetApi.list(props.projectId),
      mockRuleApi.list({ project_id: props.projectId }),
    ])
    availableDatasets.value = datasets
    availableMockRules.value = mockRules
  } catch (error: unknown) {
    availableDatasets.value = []
    availableMockRules.value = []
    message.error(errorMessage(error, t('case.ai.context_load_failed')))
  } finally {
    contextLoading.value = false
  }
}

async function handleDatasetChange(value: unknown) {
  datasetVersion.value = null
  const datasetIdValue = typeof value === 'number' ? value : null
  if (datasetIdValue == null) return
  try {
    const versions = await datasetApi.listVersions(datasetIdValue)
    datasetVersion.value = versions[0]?.version ?? null
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.ai.context_load_failed')))
  }
}

function handleMockRuleChange(value: unknown) {
  const ids = Array.isArray(value)
    ? [...new Set(value.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item > 0))]
    : []
  if (ids.length > MAX_AI_MOCK_RULES) {
    mockRuleIds.value = ids.slice(0, MAX_AI_MOCK_RULES)
    message.warning(t('case.ai.mock_rules_max', { count: MAX_AI_MOCK_RULES }))
    return
  }
  mockRuleIds.value = ids
}

watch(
  sourceType,
  (value) => {
    if (value === 'natural') {
      clearParsed()
      parseWarnings.value = []
      return
    }
    resetGeneration()
  },
)

watch(
  caseTypeOptions,
  (options) => {
    if (options.length && !options.some((item) => item.value === caseType.value)) {
      caseType.value = options[0].value
    }
  },
  { immediate: true },
)

watch(
  () => props.open,
  (val) => {
    if (val) {
      datasetId.value = props.initialDatasetId ?? undefined
      datasetVersion.value = props.initialDatasetVersion ?? null
      mockRuleIds.value = [...(props.initialMockRuleIds ?? [])]
      void loadGenerationContext()
      if (datasetId.value != null && datasetVersion.value == null) {
        void handleDatasetChange(datasetId.value)
      }
    } else {
      schemaText.value = ''
      externalRefPolicy.value = 'warn'
      parsedEndpoints.value = []
      selectedEndpointKeys.value = []
      parseWarnings.value = []
      userRequirement.value = ''
      datasetId.value = undefined
      datasetVersion.value = null
      mockRuleIds.value = []
      availableDatasets.value = []
      availableMockRules.value = []
      resetGeneration()
    }
  },
)

watch(
  () => props.projectId,
  (value, previous) => {
    if (props.open && value !== previous) {
      datasetId.value = undefined
      datasetVersion.value = null
      mockRuleIds.value = []
      void loadGenerationContext()
    }
  },
)
</script>

<style scoped>
.generation-context-hint {
  margin-top: 4px;
  color: #888;
  font-size: 12px;
  line-height: 1.4;
}
</style>
