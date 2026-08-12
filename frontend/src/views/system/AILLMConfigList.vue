<template>
  <div class="page-shell system-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.ai_llm.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.ai_llm.subtitle') }}</div>
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
      width="600px"
      @ok="handleSave"
      @cancel="resetForm"
    >
      <a-form :label-col="{ span: 6 }" layout="horizontal">
        <a-form-item :label="t('common.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('system_pages.ai_llm.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.provider_label')" required>
          <a-select
            v-model:value="form.provider"
            :options="providerOptions"
            :placeholder="t('system_pages.ai_llm.provider_placeholder')"
            @change="handleProviderChange"
          />
        </a-form-item>
        <a-form-item :label="editing ? t('system_pages.ai_llm.api_key_new') : t('system_pages.ai_llm.api_key_label')" :required="!editing">
          <a-input-password
            v-model:value="form.api_key"
            :placeholder="editing ? t('system_pages.ai_llm.api_key_keep_placeholder') : t('system_pages.ai_llm.api_key_placeholder')"
            autocomplete="new-password"
          />
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.base_url_label')">
          <a-input
            v-model:value="form.endpoint"
            :placeholder="t('system_pages.ai_llm.endpoint_placeholder')"
          />
          <div class="endpoint-hint">{{ providerEndpointHint }}</div>
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.model_name')" required>
          <div class="model-picker">
            <a-auto-complete
              v-model:value="form.model_name"
              :options="modelSelectOptions"
              :placeholder="t('system_pages.ai_llm.model_placeholder')"
              class="model-picker-input"
              @select="handleModelSelect"
            />
            <a-button :loading="discoveringModels" @click="handleDiscoverModels">
              {{ t('system_pages.ai_llm.fetch_models') }}
            </a-button>
          </div>
          <div v-if="modelOptions.length" class="model-picker-hint">
            {{ t('system_pages.ai_llm.models_loaded', { count: modelOptions.length }) }}
          </div>
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.default_params')">
          <a-textarea
            v-model:value="defaultParamsText"
            :rows="3"
            placeholder='{"temperature": 0.4}'
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
        <a-form-item :label="t('common.enabled')">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.vision_label')">
          <a-switch v-model:checked="form.supports_vision" />
          <span v-if="selectedModelOption?.supports_vision" class="capability-hint">
            {{ t('system_pages.ai_llm.vision_detected') }}
          </span>
          <span v-else class="capability-hint">
            {{ t('system_pages.ai_llm.vision_hint') }}
          </span>
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('system_pages.ai_llm.desc_placeholder')" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
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

const configs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const editing = ref<AILLMConfigItem | null>(null)
const defaultParamsText = ref('{}')
const defaultParamsError = ref('')
const modelOptions = ref<AILLMModelOption[]>([])
const discoveringModels = ref(false)

const form = ref<FormState>({
  name: '',
  provider: 'deepseek',
  api_key: '',
  endpoint: '',
  model_name: '',
  enabled: true,
  supports_vision: false,
  description: '',
})

const providerOptions = computed(() => [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Claude (Anthropic)', value: 'claude' },
  { label: 'OpenAI', value: 'openai' },
  { label: t('system_pages.ai_llm.providers.openai_compatible'), value: 'openai_compatible' },
  { label: t('system_pages.ai_llm.providers.qwen_full'), value: 'qwen' },
  { label: t('system_pages.ai_llm.providers.ollama_full'), value: 'ollama' },
])

const providerLabelMap: Record<LLMProvider, string> = {
  deepseek: 'DeepSeek',
  claude: 'Claude',
  openai: 'OpenAI',
  openai_compatible: 'OpenAI-compatible',
  qwen: t('system_pages.ai_llm.providers.qwen'),
  ollama: 'Ollama',
}

const providerColorMap: Record<LLMProvider, string> = {
  deepseek: 'cyan',
  claude: 'purple',
  openai: 'geekblue',
  openai_compatible: 'blue',
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

const providerEndpointHint = computed(() => {
  if (form.value.provider === 'ollama') return t('system_pages.ai_llm.ollama_endpoint_hint')
  if (form.value.provider === 'openai') return t('system_pages.ai_llm.openai_endpoint_hint')
  if (form.value.provider === 'openai_compatible') return t('system_pages.ai_llm.openai_compatible_endpoint_hint')
  return t('system_pages.ai_llm.compatible_endpoint_hint')
})

const providerLabel = (p: LLMProvider) => providerLabelMap[p] ?? p
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

function resetForm() {
  editing.value = null
  defaultParamsText.value = '{}'
  defaultParamsError.value = ''
  modelOptions.value = []
  form.value = {
    name: '',
    provider: 'deepseek',
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
  modelOptions.value = []
  form.value = {
    name: record.name,
    provider: record.provider,
    api_key: '',
    endpoint: record.endpoint ?? '',
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
}

function handleModelSelect(value: unknown) {
  if (typeof value !== 'string') return
  form.value.model_name = value
  const option = modelOptions.value.find((model) => model.id === value)
  form.value.supports_vision = option?.supports_vision === true
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

function parseDefaultParams(): Record<string, unknown> | null {
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
.model-picker {
  display: flex;
  gap: 8px;
}

.model-picker-input {
  flex: 1;
  min-width: 0;
}

.model-picker-hint,
.endpoint-hint,
.capability-hint {
  color: #98a2b3;
  font-size: 12px;
}

.endpoint-hint {
  margin-top: 4px;
  line-height: 1.5;
}

.capability-hint {
  margin-left: 8px;
}
</style>
