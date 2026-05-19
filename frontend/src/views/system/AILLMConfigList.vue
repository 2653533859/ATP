<template>
  <div style="display: flex; flex-direction: column; height: 100%">
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <h2 style="margin: 0">AI 模型配置</h2>
      <span style="color: #888">
        管理大模型 API Key 与端点，项目通过此配置调用 AI 用例生成
      </span>
      <a-button type="primary" @click="openCreate">新建配置</a-button>
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
              {{ record.enabled ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'has_api_key'">
            <a-tag :color="record.has_api_key ? 'blue' : 'red'">
              {{ record.has_api_key ? '已录入' : '未录入' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm
              :title="`确认删除配置 ${record.name}？`"
              ok-text="删除"
              cancel-text="取消"
              @confirm="handleDelete(record.id)"
            >
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-spin>

    <a-modal
      v-model:open="showModal"
      :title="editing ? `编辑配置: ${editing.name}` : '新建 AI 模型配置'"
      :confirm-loading="saving"
      width="600px"
      @ok="handleSave"
      @cancel="resetForm"
    >
      <a-form :label-col="{ span: 6 }" layout="horizontal">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="例如 deepseek-prod" />
        </a-form-item>
        <a-form-item label="Provider" required>
          <a-select
            v-model:value="form.provider"
            :options="providerOptions"
            placeholder="选择模型供应商"
          />
        </a-form-item>
        <a-form-item :label="editing ? '新 API Key' : 'API Key'" :required="!editing">
          <a-input-password
            v-model:value="form.api_key"
            :placeholder="editing ? '留空表示不修改现有 Key' : 'sk-... 或服务商 Token'"
            autocomplete="new-password"
          />
        </a-form-item>
        <a-form-item label="Endpoint">
          <a-input
            v-model:value="form.endpoint"
            placeholder="留空使用默认（如 https://api.deepseek.com）"
          />
        </a-form-item>
        <a-form-item label="Model 名称" required>
          <a-input v-model:value="form.model_name" placeholder="例如 deepseek-chat" />
        </a-form-item>
        <a-form-item label="默认参数 JSON">
          <a-textarea
            v-model:value="defaultParamsText"
            :rows="3"
            placeholder='{"temperature": 0.4}'
          />
          <span v-if="defaultParamsError" style="color: #f5222d; font-size: 12px">
            {{ defaultParamsError }}
          </span>
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选说明" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  aiLLMConfigApi,
  type AILLMConfigItem,
  type LLMProvider,
} from '@/api'

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

const providerOptions = [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Claude (Anthropic)', value: 'claude' },
  { label: 'OpenAI', value: 'openai' },
  { label: '通义千问 (Qwen / DashScope)', value: 'qwen' },
  { label: '本地部署 (Ollama)', value: 'ollama' },
]

const providerLabelMap: Record<LLMProvider, string> = {
  deepseek: 'DeepSeek',
  claude: 'Claude',
  openai: 'OpenAI',
  qwen: '通义千问',
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
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: 'Provider', key: 'provider' },
  { title: 'Model', dataIndex: 'model_name', key: 'model_name' },
  { title: 'Endpoint', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
  { title: 'API Key', key: 'has_api_key', width: 100 },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', key: 'action', width: 140 },
])

async function loadConfigs() {
  loading.value = true
  try {
    configs.value = await aiLLMConfigApi.list()
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '加载失败')
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
      defaultParamsError.value = '默认参数必须是 JSON 对象'
      return null
    }
    defaultParamsError.value = ''
    return parsed as Record<string, unknown>
  } catch (e) {
    defaultParamsError.value = '默认参数 JSON 解析失败'
    return null
  }
}

async function handleSave() {
  if (!form.value.name.trim() || !form.value.model_name.trim()) {
    message.warning('请填写名称与 Model 名称')
    return
  }
  if (!editing.value && !form.value.api_key.trim()) {
    message.warning('请输入 API Key')
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
      message.success('更新成功')
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
      message.success('创建成功')
    }
    showModal.value = false
    resetForm()
    await loadConfigs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await aiLLMConfigApi.delete(id)
    message.success('已删除')
    await loadConfigs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '删除失败')
  }
}

onMounted(loadConfigs)
</script>
