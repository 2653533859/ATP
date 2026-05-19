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
      </a-radio-group>
      <a-textarea
        v-model:value="schemaText"
        :rows="6"
        :placeholder="placeholderForType"
      />
      <div style="margin-top: 8px; display: flex; gap: 8px; align-items: center">
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
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  aiCaseGenerationApi,
  caseApi,
  type AICaseDraft,
  type AIEndpointSummary,
  type CaseLevel,
  type CasePriority,
  type CaseType,
  type SchemaSourceType,
} from '@/api'

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

const sourceType = ref<SchemaSourceType>('openapi')
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

const placeholderForType = computed(() => {
  switch (sourceType.value) {
    case 'openapi':
      return t('case.ai.placeholders.openapi')
    case 'postman':
      return t('case.ai.placeholders.postman')
    case 'curl':
      return t('case.ai.placeholders.curl')
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
  { title: t('case.ai.step_count'), key: 'stepCount', width: 80, customRender: ({ record }: any) => record.steps?.length ?? 0 },
  { title: t('case.filters.priority'), dataIndex: 'priority', key: 'priority', width: 80 },
])

const stepColumns = computed(() => [
  { title: '#', key: 'idx', width: 50, customRender: ({ index }: any) => index + 1 },
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
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? t('case.ai.msg.parse_failed'))
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
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? t('case.ai.msg.generate_failed'))
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
        config: draft.config ?? {},
      })
      succeeded += 1
    } catch (e: any) {
      failures.push(`${draft.name}: ${e?.response?.data?.detail ?? t('case.ai.msg.save_failed')}`)
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
