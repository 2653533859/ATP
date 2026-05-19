<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <h2 style="margin: 0">{{ t('system_pages.ai_llm.title') }}</h2>
      <span style="color: #888">
        {{ t('system_pages.ai_llm.subtitle') }}
      </span>
      <a-button type="primary" @click="openCreate">{{ t('system_pages.ai_llm.new') }}</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-table
        :data-source="configs"
        :columns="columns"
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
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
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
    </a-spin>

    <a-modal
      v-model:open="showModal"
      :title="editing ? t('system_pages.ai_llm.edit_title', { name: editing.name }) : t('system_pages.ai_llm.new_full')"
      :confirm-loading="saving"
      width="600px"
      @ok="handleSave"
      @cancel="resetForm"
    >
      <a-form :label-col="{ span: 6 }" layout="horizontal">
        <a-form-item :label="t('common.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('system_pages.ai_llm.name_placeholder')" />
        </a-form-item>
        <a-form-item label="Provider" required>
          <a-select
            v-model:value="form.provider"
            :options="providerOptions"
            :placeholder="t('system_pages.ai_llm.provider_placeholder')"
          />
        </a-form-item>
        <a-form-item :label="editing ? t('system_pages.ai_llm.api_key_new') : 'API Key'" :required="!editing">
          <a-input-password
            v-model:value="form.api_key"
            :placeholder="editing ? t('system_pages.ai_llm.api_key_keep_placeholder') : t('system_pages.ai_llm.api_key_placeholder')"
            autocomplete="new-password"
          />
        </a-form-item>
        <a-form-item label="Endpoint">
          <a-input
            v-model:value="form.endpoint"
            :placeholder="t('system_pages.ai_llm.endpoint_placeholder')"
          />
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.model_name')" required>
          <a-input v-model:value="form.model_name" :placeholder="t('system_pages.ai_llm.model_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.ai_llm.default_params')">
          <a-textarea
            v-model:value="defaultParamsText"
            :rows="3"
            placeholder='{"temperature": 0.4}'
          />
          <span v-if="defaultParamsError" style="color: #f5222d; font-size: 12px">
            {{ defaultParamsError }}
          </span>
        </a-form-item>
        <a-form-item :label="t('common.enabled')">
          <a-switch v-model:checked="form.enabled" />
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
  type LLMProvider,
} from '@/api'

const { t } = useI18n()

interface FormState {
  name: string
  provider: LLMProvider
  api_key: string
  endpoint: string
  model_name: string
  enabled: boolean
  description: string
}

const configs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const editing = ref<AILLMConfigItem | null>(null)
const defaultParamsText = ref('{}')
const defaultParamsError = ref('')

const form = ref<FormState>({
  name: '',
  provider: 'deepseek',
  api_key: '',
  endpoint: '',
  model_name: '',
  enabled: true,
  description: '',
})

const providerOptions = computed(() => [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Claude (Anthropic)', value: 'claude' },
  { label: 'OpenAI', value: 'openai' },
  { label: t('system_pages.ai_llm.providers.qwen_full'), value: 'qwen' },
  { label: t('system_pages.ai_llm.providers.ollama_full'), value: 'ollama' },
])

const providerLabelMap: Record<LLMProvider, string> = {
  deepseek: 'DeepSeek',
  claude: 'Claude',
  openai: 'OpenAI',
  qwen: t('system_pages.ai_llm.providers.qwen'),
  ollama: 'Ollama',
}

const providerColorMap: Record<LLMProvider, string> = {
  deepseek: 'cyan',
  claude: 'purple',
  openai: 'geekblue',
  qwen: 'orange',
  ollama: 'green',
}

const providerLabel = (p: LLMProvider) => providerLabelMap[p] ?? p
const providerColor = (p: LLMProvider) => providerColorMap[p] ?? 'default'

const columns = computed(() => [
  { title: t('system_pages.ai_llm.columns.name'), dataIndex: 'name', key: 'name' },
  { title: 'Provider', key: 'provider' },
  { title: 'Model', dataIndex: 'model_name', key: 'model_name' },
  { title: 'Endpoint', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
  { title: 'API Key', key: 'has_api_key', width: 100 },
  { title: t('system_pages.ai_llm.columns.status'), key: 'enabled', width: 80 },
  { title: t('system_pages.ai_llm.columns.description'), dataIndex: 'description', key: 'description', ellipsis: true },
  { title: t('system_pages.ai_llm.columns.action'), key: 'action', width: 140 },
])

async function loadConfigs() {
  loading.value = true
  try {
    configs.value = await aiLLMConfigApi.list()
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? t('system_pages.ai_llm.msg.load_failed'))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editing.value = null
  defaultParamsText.value = '{}'
  defaultParamsError.value = ''
  form.value = {
    name: '',
    provider: 'deepseek',
    api_key: '',
    endpoint: '',
    model_name: '',
    enabled: true,
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
  form.value = {
    name: record.name,
    provider: record.provider,
    api_key: '',
    endpoint: record.endpoint ?? '',
    model_name: record.model_name,
    enabled: record.enabled,
    description: record.description ?? '',
  }
  showModal.value = true
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
  if (!editing.value && !form.value.api_key.trim()) {
    message.warning(t('system_pages.ai_llm.msg.api_key_required'))
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
        description: form.value.description.trim() || null,
      })
      message.success(t('system_pages.ai_llm.msg.create_success'))
    }
    showModal.value = false
    resetForm()
    await loadConfigs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? t('system_pages.ai_llm.msg.save_failed'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await aiLLMConfigApi.delete(id)
    message.success(t('system_pages.ai_llm.msg.delete_success'))
    await loadConfigs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? t('system_pages.ai_llm.msg.delete_failed'))
  }
}

onMounted(loadConfigs)
</script>
