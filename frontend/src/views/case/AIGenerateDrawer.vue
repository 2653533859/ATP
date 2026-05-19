<template>
  <a-drawer
    :open="open"
    title="AI 生成用例"
    width="900px"
    :destroy-on-close="true"
    @close="$emit('close')"
  >
    <a-alert
      v-if="moduleId == null"
      type="warning"
      message="请先在左侧选择目标模块，再使用 AI 生成"
      style="margin-bottom: 16px"
    />

    <!-- Step 1: 解析接口文档 -->
    <a-card title="① 提供接口来源（可选）" size="small" style="margin-bottom: 16px">
      <a-radio-group v-model:value="sourceType" style="margin-bottom: 8px">
        <a-radio value="openapi">OpenAPI</a-radio>
        <a-radio value="postman">Postman Collection</a-radio>
        <a-radio value="curl">cURL 命令</a-radio>
      </a-radio-group>
      <a-textarea
        v-model:value="schemaText"
        :rows="6"
        :placeholder="placeholderForType"
      />
      <div style="margin-top: 8px; display: flex; gap: 8px; align-items: center">
        <a-button :loading="parsing" :disabled="!schemaText.trim()" @click="handleParse">
          解析接口
        </a-button>
        <a-button v-if="parsedEndpoints.length" size="small" @click="clearParsed">
          清空已解析
        </a-button>
        <span style="color: #888">
          解析后可勾选接口提供给 AI；不提供接口也可仅凭「需求描述」生成
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

    <a-card v-if="parsedEndpoints.length" title="② 选择接口" size="small" style="margin-bottom: 16px">
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
        已选 {{ selectedEndpointKeys.length }} / {{ parsedEndpoints.length }} 个接口
      </div>
    </a-card>

    <a-card title="③ 业务需求 & 生成参数" size="small" style="margin-bottom: 16px">
      <a-form layout="vertical">
        <a-form-item label="业务需求（推荐：补充覆盖场景、约束、目标用户）">
          <a-textarea
            v-model:value="userRequirement"
            :rows="4"
            placeholder="例如：登录接口，包含正常登录、密码错误、账户锁定、记住我等场景"
          />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="6">
            <a-form-item label="用例类型">
              <a-select v-model:value="caseType" :options="caseTypeOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="优先级">
              <a-select v-model:value="priority" :options="priorityOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="用例分级">
              <a-select v-model:value="caseLevel" :options="caseLevelOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="生成条数">
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
            生成草稿
          </a-button>
          <span v-if="!canGenerate" style="margin-left: 12px; color: #faad14">
            需要先选择模块，并提供接口或需求描述
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
      :title="`④ 草稿（${drafts.length} 条）`"
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
            <p v-if="record.description"><b>描述：</b>{{ record.description }}</p>
            <p v-if="record.preconditions?.length">
              <b>前置条件：</b>{{ (record.preconditions as string[]).join('；') }}
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
          保存选中 ({{ selectedDraftKeys.length }})
        </a-button>
        <a-button @click="resetGeneration">清空草稿</a-button>
      </div>
    </a-card>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
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
      return '粘贴 OpenAPI 3.x JSON 或 YAML 文档（包含 paths）'
    case 'postman':
      return '粘贴 Postman Collection v2.1 导出的 JSON'
    case 'curl':
      return '粘贴单条 cURL 命令，例如：\ncurl -X POST "https://api.example.com/login" -H "..." --data \'{"x":1}\''
    default:
      return ''
  }
})

const caseTypeOptions = [
  { label: 'API', value: 'api' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
  { label: 'gRPC', value: 'grpc' },
  { label: 'Web UI', value: 'web' },
  { label: 'Android UI', value: 'android' },
]
const priorityOptions = ['P0', 'P1', 'P2', 'P3'].map((v) => ({ label: v, value: v }))
const caseLevelOptions = [
  { label: '冒烟', value: 'smoke' },
  { label: '核心', value: 'core' },
  { label: '回归', value: 'regression' },
  { label: '扩展', value: 'extended' },
]

const endpointColumns = [
  { title: 'Method', key: 'method', dataIndex: 'method', width: 90 },
  { title: 'Path', key: 'path', dataIndex: 'path' },
  { title: '摘要', key: 'summary', dataIndex: 'summary', ellipsis: true },
]

const draftColumns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '摘要', dataIndex: 'summary', key: 'summary', ellipsis: true },
  { title: '步骤数', key: 'stepCount', width: 80, customRender: ({ record }: any) => record.steps?.length ?? 0 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
]

const stepColumns = [
  { title: '#', key: 'idx', width: 50, customRender: ({ index }: any) => index + 1 },
  { title: '动作', dataIndex: 'action', key: 'action' },
  { title: '测试数据', dataIndex: 'test_data', key: 'test_data', ellipsis: true },
  { title: '期望结果', dataIndex: 'expected_result', key: 'expected_result', ellipsis: true },
]

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
      message.warning('未解析到任何接口')
    } else {
      message.success(`已解析 ${parsedEndpoints.value.length} 个接口`)
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '解析失败')
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
    message.warning('请先选择项目与模块')
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
      message.warning('AI 未生成有效用例，请调整需求或换一组接口')
    } else {
      message.success(`AI 生成 ${drafts.value.length} 条草稿`)
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '生成失败')
  } finally {
    generating.value = false
  }
}

async function handleSaveSelected() {
  if (props.moduleId == null) {
    message.warning('未选择模块')
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
      failures.push(`${draft.name}: ${e?.response?.data?.detail ?? '保存失败'}`)
    }
  }
  saving.value = false
  if (succeeded) {
    message.success(`保存成功 ${succeeded} 条`)
    emit('saved')
  }
  if (failures.length) {
    message.error(`部分失败：${failures.slice(0, 2).join('；')}${failures.length > 2 ? ' …' : ''}`)
  }
  if (succeeded && !failures.length) {
    emit('close')
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      // 打开时不清空，保留上次输入便于继续；切换抽屉关闭后再清空
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
