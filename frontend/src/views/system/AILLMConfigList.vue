<template>
  <div class="page-shell system-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.ai_llm.title') }}</h2>
      </div>
      <a-button type="primary" @click="openCreate">{{ t('system_pages.ai_llm.new') }}</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-card class="table-panel" :bordered="false">
      <a-table
        :data-source="configs"
        :columns="columns"
        :locale="{ emptyText: t('common.no_data') }"
        :pagination="{ pageSize: 20 }"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'provider'">
            <a-tag :color="providerColor(record.provider)">{{ providerLabel(record.provider) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'enabled'">
            <a-tag :color="record.enabled ? 'green' : 'default'">
              {{ record.enabled ? t('common.enabled') : t('common.disabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'has_api_key'">
            <a-tag :color="record.has_api_key ? 'blue' : 'red'">
              {{ record.has_api_key ? t('system_pages.ai_llm.has_key') : t('system_pages.ai_llm.no_key') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'supports_vision'">
            <a-tag :color="record.supports_vision ? 'geekblue' : 'default'">
              {{ record.supports_vision ? t('common.enabled') : t('common.disabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(asConfig(record))">{{ t('common.edit') }}</a-button>
            <a-popconfirm
              :title="t('system_pages.ai_llm.confirm_delete', { name: record.name })"
              :ok-text="t('common.delete')"
              :cancel-text="t('common.cancel')"
              @confirm="handleDelete(record.id)"
            >
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
      </a-card>
    </a-spin>

    <a-modal
      v-model:open="showModal"
      :title="editing ? t('system_pages.ai_llm.edit_title', { name: editing.name }) : t('system_pages.ai_llm.new_full')"
      :confirm-loading="saving"
      :cancel-text="t('common.cancel')"
      :ok-text="t('common.ok')"
      width="720px"
      centered
      @ok="handleSave"
      @cancel="resetForm"
    >
      <div class="llm-modal-body">
        <a-form layout="vertical" class="llm-config-form">
          <a-row :gutter="16">
            <a-col :xs="24" :sm="12">
              <a-form-item :label="t('common.name')" required>
                <a-input v-model:value="form.name" :placeholder="t('system_pages.ai_llm.name_placeholder')" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item :label="t('system_pages.ai_llm.provider_label')" required>
                <a-select
                  v-model:value="form.provider"
                  :options="providerOptions"
                  option-label-prop="label"
                  :placeholder="t('system_pages.ai_llm.provider_placeholder')"
                  @change="handleProviderChange"
                >
                  <template #option="{ label, desc }">
                    <div class="provider-option-item">
                      <span class="provider-option-title">{{ label }}</span>
                      <span class="provider-option-desc">{{ desc }}</span>
                    </div>
                  </template>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="16">
            <a-col :xs="24" :sm="12">
              <a-form-item
                :label="editing ? t('system_pages.ai_llm.api_key_new') : t('system_pages.ai_llm.api_key_label')"
                :required="!editing && form.provider !== 'ollama'"
              >
                <a-input-password
                  v-model:value="form.api_key"
                  :placeholder="currentApiKeyPlaceholder"
                  autocomplete="new-password"
                />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item
                :label="t('system_pages.ai_llm.base_url_label')"
                :required="form.provider === 'openai_compatible'"
              >
                <a-input
                  v-model:value="form.endpoint"
                  :placeholder="currentEndpointPlaceholder"
                />
              </a-form-item>
            </a-col>
          </a-row>
          <div v-if="providerEndpointHint" class="endpoint-hint-banner">{{ providerEndpointHint }}</div>

          <a-form-item :label="t('system_pages.ai_llm.model_name')" required>
            <div class="model-picker">
              <a-auto-complete
                v-model:value="form.model_name"
                :options="modelSelectOptions"
                :placeholder="currentModelPlaceholder"
                class="model-picker-input"
                @select="handleModelSelect"
              />
              <a-button :loading="discoveringModels" @click="handleDiscoverModels">
                {{ t('system_pages.ai_llm.fetch_models') }}
              </a-button>
              <a-button :loading="testingConnection" @click="handleTestConnection">
                {{ t('system_pages.ai_llm.test_connection') }}
              </a-button>
            </div>
            <div v-if="modelOptions.length" class="model-picker-hint">
              {{ t('system_pages.ai_llm.models_loaded', { count: modelOptions.length }) }}
            </div>
          </a-form-item>

          <a-row :gutter="16">
            <a-col :xs="24" :sm="12">
              <a-form-item :label="t('system_pages.ai_llm.thinking_label')">
                <a-select
                  v-model:value="thinkingMode"
                  :options="thinkingModeOptions"
                  @change="handleThinkingModeChange"
                />
                <div class="field-sub-hint">{{ reasoningCapabilityHint }}</div>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <div class="switch-panel">
                <div class="switch-row">
                  <span class="switch-label">{{ t('common.enabled') }}</span>
                  <a-switch v-model:checked="form.enabled" />
                </div>
                <div class="switch-row">
                  <span class="switch-label">{{ t('system_pages.ai_llm.vision_label') }}</span>
                  <a-switch v-model:checked="form.supports_vision" />
                </div>
                <div
                  v-if="selectedModelOption?.supports_vision === false"
                  class="capability-warning-line"
                >
                  {{ t('system_pages.ai_llm.vision_not_detected') }}
                </div>
                <div v-else class="field-sub-hint">
                  {{
                    selectedModelOption?.supports_vision === true
                      ? t('system_pages.ai_llm.vision_detected')
                      : t('system_pages.ai_llm.vision_hint')
                  }}
                </div>
              </div>
            </a-col>
          </a-row>

          <a-form-item>
            <template #label>
              <div class="label-with-action">
                <span>{{ t('system_pages.ai_llm.default_params') }}</span>
                <a-button
                  size="small"
                  type="link"
                  style="padding: 0; height: auto"
                  @click="defaultParamsText = tryFormatJson(defaultParamsText)"
                >
                  <FormatPainterOutlined /> 格式化 JSON
                </a-button>
              </div>
            </template>
            <a-textarea
              v-model:value="defaultParamsText"
              :rows="3"
              placeholder='{"temperature": 0.4}'
              class="json-textarea"
            />
            <span v-if="defaultParamsError" style="color: var(--c-error); font-size: 12px">
              {{ defaultParamsError }}
            </span>
            <a-alert
              type="info"
              show-icon
              :message="t('system_pages.ai_llm.params_hint')"
              style="margin-top: 8px"
            />
          </a-form-item>

          <a-form-item :label="t('common.description')" style="margin-bottom: 0">
            <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('system_pages.ai_llm.desc_placeholder')" />
          </a-form-item>
        </a-form>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { FormatPainterOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { tryFormatJson } from '@/utils/jsonFormat'
import {
  aiLLMConfigApi,
  type AILLMConfigItem,
  type AILLMModelOption,
  type LLMProvider,
} from '@/api'

// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asConfig = (record: unknown) => record as AILLMConfigItem

const { t } = useI18n()

interface FormState {
  name: string
  provider: LLMProvider
  api_key: string
  endpoint: string
  model_name: string
  enabled: boolean
  supports_vision: boolean
  description: string
}

type ThinkingMode = '' | 'thinking' | 'enable_thinking' | 'reasoning_effort_low' | 'reasoning_effort_medium' | 'reasoning_effort_high'

const THINKING_PARAM_KEYS = ['thinking', 'enable_thinking', 'reasoning_effort'] as const

const configs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const editing = ref<AILLMConfigItem | null>(null)
const defaultParamsText = ref('{}')
const defaultParamsError = ref('')
const thinkingMode = ref<ThinkingMode>('')
const thinkingModeDirty = ref(false)
const modelOptions = ref<AILLMModelOption[]>([])
const discoveringModels = ref(false)
const testingConnection = ref(false)

const form = ref<FormState>({
  name: '',
  provider: 'openai_compatible',
  api_key: '',
  endpoint: '',
  model_name: '',
  enabled: true,
  supports_vision: false,
  description: '',
})

const providerOptions = computed(() => [
  {
    label: t('system_pages.ai_llm.providers.openai_compatible'),
    value: 'openai_compatible',
    desc: t('system_pages.ai_llm.provider_desc.openai_compatible'),
  },
  {
    label: t('system_pages.ai_llm.providers.openai_responses'),
    value: 'openai_responses',
    desc: t('system_pages.ai_llm.provider_desc.openai_responses'),
  },
  {
    label: t('system_pages.ai_llm.providers.anthropic'),
    value: 'anthropic',
    desc: t('system_pages.ai_llm.provider_desc.anthropic'),
  },
])

const providerLabelMap = computed<Record<LLMProvider, string>>(() => ({
  openai_compatible: t('system_pages.ai_llm.providers.openai_compatible'),
  openai_responses: t('system_pages.ai_llm.providers.openai_responses'),
  anthropic: t('system_pages.ai_llm.providers.anthropic'),
  deepseek: 'DeepSeek',
  claude: 'Anthropic',
  openai: 'OpenAI',
  qwen: t('system_pages.ai_llm.providers.qwen'),
  ollama: 'Ollama',
}))

const providerColorMap: Record<LLMProvider, string> = {
  openai_compatible: 'blue',
  openai_responses: 'geekblue',
  anthropic: 'purple',
  deepseek: 'cyan',
  claude: 'purple',
  openai: 'geekblue',
  qwen: 'orange',
  ollama: 'green',
}

const modelSelectOptions = computed(() => modelOptions.value.map((model) => {
  const capabilities = [
    model.supports_vision ? t('system_pages.ai_llm.vision_badge') : '',
    model.supports_reasoning ? t('system_pages.ai_llm.reasoning_badge') : '',
  ].filter(Boolean)
  const suffix = capabilities.length ? ` · ${capabilities.join(' / ')}` : ''
  return { value: model.id, label: `${model.label}${suffix}` }
}))

const selectedModelOption = computed(() =>
  modelOptions.value.find((model) => model.id === form.value.model_name),
)

const thinkingModeOptions = computed(() => [
  { value: '', label: t('system_pages.ai_llm.thinking_options.off') },
  { value: 'thinking', label: t('system_pages.ai_llm.thinking_options.thinking') },
  { value: 'enable_thinking', label: t('system_pages.ai_llm.thinking_options.enable_thinking') },
  { value: 'reasoning_effort_low', label: t('system_pages.ai_llm.thinking_options.low') },
  { value: 'reasoning_effort_medium', label: t('system_pages.ai_llm.thinking_options.medium') },
  { value: 'reasoning_effort_high', label: t('system_pages.ai_llm.thinking_options.high') },
])

const reasoningCapabilityHint = computed(() => {
  if (selectedModelOption.value?.supports_reasoning === true) {
    return t('system_pages.ai_llm.reasoning_supported')
  }
  if (selectedModelOption.value?.supports_reasoning === false) {
    return t('system_pages.ai_llm.reasoning_not_detected')
  }
  return t('system_pages.ai_llm.reasoning_unknown')
})

const currentApiKeyPlaceholder = computed(() => {
  if (editing.value) return t('system_pages.ai_llm.api_key_keep_placeholder')
  if (form.value.provider === 'ollama') return t('system_pages.ai_llm.api_key_ollama_placeholder')
  return t('system_pages.ai_llm.api_key_placeholder')
})

const currentEndpointPlaceholder = computed(() => {
  const map: Partial<Record<LLMProvider, string>> = {
    openai_compatible: 'https://your-gateway.example.com/v1',
    openai_responses: 'https://api.openai.com',
    anthropic: 'https://api.anthropic.com',
  }
  return map[form.value.provider] || t('system_pages.ai_llm.endpoint_placeholder')
})

const currentModelPlaceholder = computed(() => {
  const map: Partial<Record<LLMProvider, string>> = {
    openai_compatible: 'gpt-4o-mini / deepseek-chat / qwen-plus',
    openai_responses: 'gpt-4.1 / o4-mini',
    anthropic: 'claude-3-7-sonnet-latest',
  }
  return map[form.value.provider] || t('system_pages.ai_llm.model_placeholder')
})

const providerEndpointHint = computed(() => {
  if (form.value.provider === 'anthropic' || form.value.provider === 'claude') {
    return t('system_pages.ai_llm.claude_endpoint_hint')
  }
  if (form.value.provider === 'openai_responses') return t('system_pages.ai_llm.openai_endpoint_hint')
  if (form.value.provider === 'openai_compatible') return t('system_pages.ai_llm.openai_compatible_endpoint_hint')
  return t('system_pages.ai_llm.compatible_endpoint_hint')
})

const providerLabel = (p: LLMProvider) => providerLabelMap.value[p] ?? p
const providerColor = (p: LLMProvider) => providerColorMap[p] ?? 'default'

const columns = computed(() => [
  { title: t('system_pages.ai_llm.columns.name'), dataIndex: 'name', key: 'name' },
  { title: t('system_pages.ai_llm.columns.provider'), key: 'provider' },
  { title: t('system_pages.ai_llm.columns.model'), dataIndex: 'model_name', key: 'model_name' },
  { title: t('system_pages.ai_llm.base_url_label'), dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
  { title: t('system_pages.ai_llm.columns.api_key'), key: 'has_api_key', width: 100 },
  { title: t('system_pages.ai_llm.columns.vision'), dataIndex: 'supports_vision', key: 'supports_vision', width: 90 },
  { title: t('system_pages.ai_llm.columns.status'), key: 'enabled', width: 80 },
  { title: t('system_pages.ai_llm.columns.description'), dataIndex: 'description', key: 'description', ellipsis: true },
  { title: t('system_pages.ai_llm.columns.action'), key: 'action', width: 140 },
])

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

async function loadConfigs() {
  loading.value = true
  try {
    configs.value = await aiLLMConfigApi.list()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.ai_llm.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

const LEGACY_PROVIDER_DEFAULTS: Partial<Record<LLMProvider, { provider: LLMProvider; endpoint: string }>> = {
  claude: { provider: 'anthropic', endpoint: 'https://api.anthropic.com' },
  deepseek: { provider: 'openai_compatible', endpoint: 'https://api.deepseek.com' },
  openai: { provider: 'openai_compatible', endpoint: 'https://api.openai.com/v1' },
  qwen: { provider: 'openai_compatible', endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ollama: { provider: 'openai_compatible', endpoint: 'http://localhost:11434/v1' },
}

function resetForm() {
  editing.value = null
  defaultParamsText.value = '{}'
  defaultParamsError.value = ''
  thinkingMode.value = ''
  thinkingModeDirty.value = false
  modelOptions.value = []
  form.value = {
    name: '',
    provider: 'openai_compatible',
    api_key: '',
    endpoint: '',
    model_name: '',
    enabled: true,
    supports_vision: false,
    description: '',
  }
}

function openCreate() {
  resetForm()
  showModal.value = true
}

function openEdit(record: AILLMConfigItem) {
  editing.value = record
  defaultParamsText.value = JSON.stringify(record.default_params ?? {}, null, 2)
  defaultParamsError.value = ''
  thinkingMode.value = inferThinkingMode(record.default_params ?? {})
  thinkingModeDirty.value = false
  modelOptions.value = []
  const mapped = LEGACY_PROVIDER_DEFAULTS[record.provider]
  form.value = {
    name: record.name,
    provider: mapped ? mapped.provider : record.provider,
    api_key: '',
    endpoint: record.endpoint ?? (mapped?.endpoint ?? ''),
    model_name: record.model_name,
    enabled: record.enabled,
    supports_vision: record.supports_vision,
    description: record.description ?? '',
  }
  showModal.value = true
}

function handleProviderChange() {
  modelOptions.value = []
  form.value.model_name = ''
  form.value.supports_vision = false
  thinkingMode.value = ''
  thinkingModeDirty.value = false
}

function handleModelSelect(value: unknown) {
  if (typeof value !== 'string') return
  form.value.model_name = value
  const option = modelOptions.value.find((model) => model.id === value)
  form.value.supports_vision = option?.supports_vision === true
}

function inferThinkingMode(params: Record<string, unknown>): ThinkingMode {
  if (params.thinking === true) return 'thinking'
  if (params.enable_thinking === true) return 'enable_thinking'
  if (params.reasoning_effort === 'low') return 'reasoning_effort_low'
  if (params.reasoning_effort === 'medium') return 'reasoning_effort_medium'
  if (params.reasoning_effort === 'high') return 'reasoning_effort_high'
  return ''
}

function applyThinkingMode(params: Record<string, unknown>) {
  for (const key of THINKING_PARAM_KEYS) delete params[key]
  if (thinkingMode.value === 'thinking') params.thinking = true
  if (thinkingMode.value === 'enable_thinking') params.enable_thinking = true
  if (thinkingMode.value.startsWith('reasoning_effort_')) {
    params.reasoning_effort = thinkingMode.value.replace('reasoning_effort_', '')
  }
}

function parseDefaultParamsText(): Record<string, unknown> | null {
  const text = (defaultParamsText.value ?? '').trim()
  if (!text) return {}
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
      defaultParamsError.value = t('system_pages.ai_llm.msg.params_object_required')
      return null
    }
    defaultParamsError.value = ''
    return parsed as Record<string, unknown>
  } catch (e) {
    defaultParamsError.value = t('system_pages.ai_llm.msg.params_parse_failed')
    return null
  }
}

function handleThinkingModeChange(value: unknown) {
  thinkingMode.value = typeof value === 'string' && thinkingModeOptions.value.some((option) => option.value === value)
    ? value as ThinkingMode
    : ''
  thinkingModeDirty.value = true
  const params = parseDefaultParamsText()
  if (params === null) return
  applyThinkingMode(params)
  defaultParamsText.value = JSON.stringify(params, null, 2)
}

async function handleDiscoverModels() {
  const apiKey = form.value.api_key.trim()
  if (!editing.value && form.value.provider !== 'ollama' && !apiKey) {
    message.warning(t('system_pages.ai_llm.msg.api_key_required'))
    return
  }

  discoveringModels.value = true
  try {
    const result = await aiLLMConfigApi.discoverModels({
      config_id: editing.value?.id,
      provider: form.value.provider,
      api_key: apiKey || undefined,
      endpoint: form.value.endpoint.trim() || null,
    })
    modelOptions.value = result.models
    if (!result.models.length) {
      message.warning(t('system_pages.ai_llm.msg.no_models'))
    } else {
      message.success(t('system_pages.ai_llm.msg.models_loaded', { count: result.models.length }))
    }
  } catch (error: unknown) {
    message.error(errorMessage(error, t('system_pages.ai_llm.msg.models_load_failed')))
  } finally {
    discoveringModels.value = false
  }
}

async function handleTestConnection() {
  if (!form.value.model_name.trim()) {
    message.warning(t('system_pages.ai_llm.msg.required'))
    return
  }
  const apiKey = form.value.api_key.trim()
  if (!editing.value && form.value.provider !== 'ollama' && !apiKey) {
    message.warning(t('system_pages.ai_llm.msg.api_key_required'))
    return
  }
  const params = parseDefaultParams()
  if (params === null) return

  testingConnection.value = true
  try {
    const result = await aiLLMConfigApi.testConnection({
      config_id: editing.value?.id,
      provider: form.value.provider,
      api_key: apiKey || undefined,
      endpoint: form.value.endpoint.trim() || null,
      model_name: form.value.model_name.trim(),
      default_params: params,
    })
    message.success(t('system_pages.ai_llm.msg.connection_success', { latency: result.latency_ms }))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('system_pages.ai_llm.msg.connection_failed')))
  } finally {
    testingConnection.value = false
  }
}

function parseDefaultParams(): Record<string, unknown> | null {
  const params = parseDefaultParamsText()
  if (params !== null && thinkingModeDirty.value) applyThinkingMode(params)
  return params
}

async function handleSave() {
  if (!form.value.name.trim() || !form.value.model_name.trim()) {
    message.warning(t('system_pages.ai_llm.msg.required'))
    return
  }
  if (!editing.value && form.value.provider !== 'ollama' && !form.value.api_key.trim()) {
    message.warning(t('system_pages.ai_llm.msg.api_key_required'))
    return
  }
  if (form.value.provider === 'openai_compatible' && !form.value.endpoint.trim()) {
    message.warning(t('system_pages.ai_llm.msg.compatible_endpoint_required'))
    return
  }
  const params = parseDefaultParams()
  if (params === null) return

  saving.value = true
  try {
    if (editing.value) {
      const payload: Record<string, unknown> = {
        name: form.value.name.trim(),
        provider: form.value.provider,
        endpoint: form.value.endpoint.trim() || null,
        model_name: form.value.model_name.trim(),
        default_params: params,
        enabled: form.value.enabled,
        supports_vision: form.value.supports_vision,
        description: form.value.description.trim() || null,
      }
      if (form.value.api_key.trim()) {
        payload.api_key = form.value.api_key.trim()
      }
      await aiLLMConfigApi.update(editing.value.id, payload)
      message.success(t('system_pages.ai_llm.msg.update_success'))
    } else {
      await aiLLMConfigApi.create({
        name: form.value.name.trim(),
        provider: form.value.provider,
        api_key: form.value.api_key.trim(),
        endpoint: form.value.endpoint.trim() || null,
        model_name: form.value.model_name.trim(),
        default_params: params,
        enabled: form.value.enabled,
        supports_vision: form.value.supports_vision,
        description: form.value.description.trim() || null,
      })
      message.success(t('system_pages.ai_llm.msg.create_success'))
    }
    showModal.value = false
    resetForm()
    await loadConfigs()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.ai_llm.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await aiLLMConfigApi.delete(id)
    message.success(t('system_pages.ai_llm.msg.delete_success'))
    await loadConfigs()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.ai_llm.msg.delete_failed')))
  }
}

onMounted(loadConfigs)
</script>

<style scoped>
.llm-modal-body {
  max-height: 70vh;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 6px;
}

.llm-config-form :deep(.ant-form-item) {
  margin-bottom: 14px;
}

.llm-config-form :deep(.ant-form-item-label > label) {
  width: 100%;
  font-weight: 500;
}

.label-with-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.provider-option-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.provider-option-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text, #1e293b);
  line-height: 1.3;
}

.provider-option-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.3;
}

.endpoint-hint-banner {
  margin: -6px 0 14px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--c-bg-subtle, #f8fafc);
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.model-picker {
  display: flex;
  gap: 8px;
}

.model-picker-input {
  flex: 1;
  min-width: 0;
}

.model-picker-hint,
.field-sub-hint {
  color: #64748b;
  font-size: 12px;
  margin-top: 6px;
  line-height: 1.5;
}

.switch-panel {
  padding: 10px 12px;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}

.switch-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text, #1e293b);
}

.capability-warning-line {
  margin-top: 6px;
  color: var(--c-warning, #d48806);
  font-size: 12px;
  line-height: 1.5;
}

.json-textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}
</style>
