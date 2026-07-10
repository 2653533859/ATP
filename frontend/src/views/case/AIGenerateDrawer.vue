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
        <a-radio value="openapi">OpenAPI</a-radio>
        <a-radio value="postman">Postman Collection</a-radio>
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
        <span style="color: #888">
          {{ t('case.ai.parse_hint') }}
        </span>
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
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  aiCaseGenerationApi,
  caseApi,
  type AICaseDraft,
  type AICaseStepDraft,
  type AIEndpointSummary,
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
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const { t } = useI18n()

const sourceType = ref<GenerationSourceType>('openapi')
const schemaText = ref('')
const parsing = ref(false)
const parsedEndpoints = ref<(AIEndpointSummary & { rowKey: string })[]>([])
const selectedEndpointKeys = ref<string[]>([])
const parseWarnings = ref<string[]>([])

const userRequirement = ref('')
const caseType = ref<CaseType>('api')
const priority = ref<CasePriority>('P2')
const caseLevel = ref<CaseLevel>('regression')
const maxCases = ref(5)

const generating = ref(false)
const generateWarnings = ref<string[]>([])
const drafts = ref<AICaseDraft[]>([])
const selectedDraftKeys = ref<string[]>([])

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

const caseTypeOptions = computed(() => [
  { label: t('case.types.api'), value: 'api' },
  { label: t('case.types.graphql'), value: 'graphql' },
  { label: t('case.types.websocket'), value: 'websocket' },
  { label: t('case.types.grpc'), value: 'grpc' },
  { label: t('case.types.web'), value: 'web' },
  { label: t('case.types.android'), value: 'android' },
])
const priorityOptions = ['P0', 'P1', 'P2', 'P3'].map((v) => ({ label: v, value: v }))
const caseLevelOptions = computed(() => [
  { label: t('case.levels.smoke'), value: 'smoke' },
  { label: t('case.levels.core'), value: 'core' },
  { label: t('case.levels.regression'), value: 'regression' },
  { label: t('case.levels.extended'), value: 'extended' },
])

const endpointColumns = computed(() => [
  { title: 'Method', key: 'method', dataIndex: 'method', width: 90 },
  { title: 'Path', key: 'path', dataIndex: 'path' },
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

function resetGeneration() {
  drafts.value = []
  selectedDraftKeys.value = []
  generateWarnings.value = []
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
    })
    drafts.value = result.drafts ?? []
    selectedDraftKeys.value = drafts.value.map((_, i) => String(i))
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
  let succeeded = 0
  const failures: string[] = []
  for (const draft of targets) {
    try {
      await caseApi.create({
        name: draft.name,
        description: draft.description ?? undefined,
        summary: draft.summary ?? undefined,
        case_type: draft.case_type,
        module_id: props.moduleId!,
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
        },
      })
      succeeded += 1
    } catch (e: unknown) {
      failures.push(`${draft.name}: ${errorMessage(e, t('case.ai.msg.save_failed'))}`)
    }
  }
  saving.value = false
  if (succeeded) {
    message.success(t('case.ai.msg.save_success', { count: succeeded }))
    emit('saved')
  }
  if (failures.length) {
    message.error(t('case.ai.msg.partial_failed', {
      failures: failures.slice(0, 2).join(t('case.ai.list_separator')),
      more: failures.length > 2 ? ' ...' : '',
    }))
  }
  if (succeeded && !failures.length) {
    emit('close')
  }
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
  () => props.open,
  (val) => {
    if (val) {
      // Keep current input while open so users can continue editing.
    } else {
      schemaText.value = ''
      parsedEndpoints.value = []
      selectedEndpointKeys.value = []
      parseWarnings.value = []
      userRequirement.value = ''
      resetGeneration()
    }
  },
)
</script>
