<template>
  <div class="page-shell bug-tracker-page">
    <div>
      <h2 class="page-title">{{ t('system_pages.bug_tracker.title') }}</h2>
      <div class="page-subtitle">{{ t('system_pages.bug_tracker.subtitle') }}</div>
    </div>
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('mobile_special.select_project')"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadTrackers"
        />
      </a-space>
      <a-button type="primary" :disabled="!projectId" @click="openCreate">
        <PlusOutlined /> {{ t('system_pages.bug_tracker.add') }}
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="trackers"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tracker_type'">
          <a-tag :color="typeColor(record.tracker_type)">{{ typeLabel(record.tracker_type) }}</a-tag>
        </template>
        <template v-if="column.key === 'is_enabled'">
          <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? t('common.enabled') : t('common.disabled') }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" :loading="testingId === record.id" @click="handleTestConnection(record)">{{ t('system_pages.bug_tracker.test_connection') }}</a-button>
            <a-button type="link" size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('common.confirm_delete')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? t('system_pages.bug_tracker.edit') : t('system_pages.bug_tracker.add')"
      :confirm-loading="saving"
      width="560px"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')">
          <a-input v-model:value="form.name" :placeholder="t('system_pages.bug_tracker.name_placeholder')" />
        </a-form-item>

        <a-form-item :label="t('system_pages.bug_tracker.platform_type')">
          <a-select v-model:value="form.tracker_type" :disabled="isEdit" style="width: 100%">
            <a-select-option value="jira">Jira</a-select-option>
            <a-select-option value="zentao">{{ t('system_pages.bug_tracker.types.zentao') }}</a-select-option>
            <a-select-option value="github">GitHub Issues</a-select-option>
          </a-select>
        </a-form-item>

        <template v-if="form.tracker_type === 'jira'">
          <a-form-item :label="t('system_pages.bug_tracker.jira_url')">
            <a-input v-model:value="jiraBaseUrl" placeholder="https://xxx.atlassian.net" />
          </a-form-item>
          <a-form-item :label="t('system_pages.bug_tracker.email')">
            <a-input v-model:value="jiraEmail" placeholder="user@example.com" />
          </a-form-item>
          <a-form-item label="API Token">
            <a-input-password v-model:value="jiraToken" placeholder="Jira API Token" />
          </a-form-item>
          <a-form-item :label="t('system_pages.bug_tracker.project_key')">
            <a-input v-model:value="jiraProjectKey" placeholder="ATP" />
          </a-form-item>
        </template>

        <template v-if="form.tracker_type === 'zentao'">
          <a-form-item :label="t('system_pages.bug_tracker.zentao_url')">
            <a-input v-model:value="zentaoBaseUrl" placeholder="http://zentao.xxx.com" />
          </a-form-item>
          <a-form-item :label="t('system_pages.bug_tracker.account')">
            <a-input v-model:value="zentaoAccount" placeholder="admin" />
          </a-form-item>
          <a-form-item :label="t('system_pages.bug_tracker.password')">
            <a-input-password v-model:value="zentaoPassword" :placeholder="t('system_pages.bug_tracker.password')" />
          </a-form-item>
          <a-form-item :label="t('system_pages.bug_tracker.product_id')">
            <a-input-number v-model:value="zentaoProductId" :min="1" style="width: 100%" placeholder="1" />
          </a-form-item>
        </template>

        <template v-if="form.tracker_type === 'github'">
          <a-form-item label="Owner">
            <a-input v-model:value="githubOwner" placeholder="octo-org" />
          </a-form-item>
          <a-form-item label="Repo">
            <a-input v-model:value="githubRepo" placeholder="atp" />
          </a-form-item>
          <a-form-item label="Token">
            <a-input-password v-model:value="githubToken" placeholder="GitHub Personal Access Token" />
          </a-form-item>
          <a-form-item label="API Base URL">
            <a-input v-model:value="githubBaseUrl" placeholder="https://api.github.com" />
          </a-form-item>
        </template>

        <a-form-item :label="t('system_pages.bug_tracker.field_mapping')">
          <a-textarea
            v-model:value="fieldMappingText"
            :rows="6"
            placeholder='{"priority":"High","labels":["automation"],"components":["QA"],"custom_fields":{}}'
          />
        </a-form-item>

        <a-form-item :label="t('common.enabled')">
          <a-switch v-model:checked="form.is_enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { AxiosError } from 'axios'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { bugTrackerApi, projectApi, type BugTrackerItem, type BugTrackerType, type ProjectItem } from '@/api'

const trackers = ref<BugTrackerItem[]>([])
const { t } = useI18n()
const loading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const testingId = ref<number | null>(null)

const form = ref<{ name: string; tracker_type: BugTrackerType; is_enabled: boolean }>({
  name: '', tracker_type: 'jira', is_enabled: true,
})

const jiraBaseUrl = ref('')
const jiraEmail = ref('')
const jiraToken = ref('')
const jiraProjectKey = ref('')
const githubOwner = ref('')
const githubRepo = ref('')
const githubToken = ref('')
const githubBaseUrl = ref('https://api.github.com')
const fieldMappingText = ref('{\n  "priority": "High",\n  "labels": ["automation", "atp"],\n  "components": ["QA"],\n  "custom_fields": {}\n}')

const zentaoBaseUrl = ref('')
const zentaoAccount = ref('')
const zentaoPassword = ref('')
const zentaoProductId = ref<number | undefined>(undefined)

const columns = computed(() => [
  { title: t('common.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('system_pages.bug_tracker.platform'), key: 'tracker_type', width: 100 },
  { title: t('common.status'), key: 'is_enabled', width: 80 },
  { title: t('common.updated_at'), dataIndex: 'updated_at', width: 170,
    customRender: ({ text }: { text?: string | null }) => text?.slice(0, 19).replace('T', ' ') ?? '-' },
  { title: t('common.action'), key: 'action', width: 140, fixed: 'right' as const },
])

function getErrorMessage(error: unknown, fallback: string) {
  const axiosError = error as AxiosError<{ detail?: string; message?: string }>
  const detail = axiosError?.response?.data?.detail || axiosError?.response?.data?.message
  if (typeof detail === 'string' && detail) return detail
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'string' && error) return error
  return fallback
}

function typeLabel(type: string) {
  return { jira: 'Jira', zentao: t('system_pages.bug_tracker.types.zentao'), github: 'GitHub Issues' }[type] ?? type
}
function typeColor(type: string) {
  return { jira: 'blue', zentao: 'green', github: 'black' }[type] ?? 'default'
}

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: ProjectItem) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadTrackers() {
  if (!projectId.value) { trackers.value = []; return }
  loading.value = true
  try {
    trackers.value = await bugTrackerApi.list({ project_id: projectId.value })
  } catch (error) {
    trackers.value = []
    message.error(getErrorMessage(error, t('system_pages.bug_tracker.msg.load_failed')))
  }
  finally { loading.value = false }
}

function resetFields() {
  jiraBaseUrl.value = ''
  jiraEmail.value = ''
  jiraToken.value = ''
  jiraProjectKey.value = ''
  githubOwner.value = ''
  githubRepo.value = ''
  githubToken.value = ''
  githubBaseUrl.value = 'https://api.github.com'
  fieldMappingText.value = '{\n  "priority": "High",\n  "labels": ["automation", "atp"],\n  "components": ["QA"],\n  "custom_fields": {}\n}'
  zentaoBaseUrl.value = ''
  zentaoAccount.value = ''
  zentaoPassword.value = ''
  zentaoProductId.value = undefined
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', tracker_type: 'jira', is_enabled: true }
  resetFields()
  formOpen.value = true
}

function openEdit(record: BugTrackerItem) {
  isEdit.value = true
  editingId.value = record.id
  form.value = { name: record.name, tracker_type: record.tracker_type, is_enabled: record.is_enabled }
  resetFields()
  const cfg = (record.config || {}) as Record<string, unknown>
  const fieldMapping = record.field_mapping || {}
  fieldMappingText.value = JSON.stringify(fieldMapping, null, 2)
  if (record.tracker_type === 'jira') {
    jiraBaseUrl.value = typeof cfg.base_url === 'string' ? cfg.base_url : ''
    jiraEmail.value = typeof cfg.email === 'string' ? cfg.email : ''
    jiraToken.value = typeof cfg.api_token === 'string' ? cfg.api_token : ''
    jiraProjectKey.value = typeof cfg.project_key === 'string' ? cfg.project_key : ''
  } else if (record.tracker_type === 'zentao') {
    zentaoBaseUrl.value = typeof cfg.base_url === 'string' ? cfg.base_url : ''
    zentaoAccount.value = typeof cfg.account === 'string' ? cfg.account : ''
    zentaoPassword.value = typeof cfg.password === 'string' ? cfg.password : ''
    zentaoProductId.value = typeof cfg.product_id === 'number' ? cfg.product_id : undefined
  } else if (record.tracker_type === 'github') {
    githubOwner.value = typeof cfg.owner === 'string' ? cfg.owner : ''
    githubRepo.value = typeof cfg.repo === 'string' ? cfg.repo : ''
    githubToken.value = typeof cfg.token === 'string' ? cfg.token : ''
    githubBaseUrl.value = typeof cfg.base_url === 'string' ? cfg.base_url : 'https://api.github.com'
  }
  formOpen.value = true
}

function buildConfig(): Record<string, unknown> {
  if (form.value.tracker_type === 'jira') {
    return {
      base_url: jiraBaseUrl.value,
      email: jiraEmail.value,
      api_token: jiraToken.value,
      project_key: jiraProjectKey.value,
    }
  } else if (form.value.tracker_type === 'zentao') {
    return {
      base_url: zentaoBaseUrl.value,
      account: zentaoAccount.value,
      password: zentaoPassword.value,
      product_id: zentaoProductId.value,
    }
  } else if (form.value.tracker_type === 'github') {
    return {
      base_url: githubBaseUrl.value || 'https://api.github.com',
      owner: githubOwner.value,
      repo: githubRepo.value,
      token: githubToken.value,
    }
  }
  return {}
}

function buildFieldMapping(): Record<string, unknown> {
  try {
    const parsed = JSON.parse(fieldMappingText.value || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    throw new Error(t('system_pages.bug_tracker.msg.field_mapping_invalid'))
  }
}

function validateConfig() {
  const config = buildConfig()
  if (form.value.tracker_type === 'jira') {
    if (!jiraBaseUrl.value || !jiraEmail.value || !jiraProjectKey.value || !jiraToken.value) {
      throw new Error(t('system_pages.bug_tracker.msg.jira_required'))
    }
  } else if (form.value.tracker_type === 'zentao') {
    if (!zentaoBaseUrl.value || !zentaoAccount.value || !zentaoPassword.value || !zentaoProductId.value) {
      throw new Error(t('system_pages.bug_tracker.msg.zentao_required'))
    }
  } else if (form.value.tracker_type === 'github') {
    if (!githubOwner.value || !githubRepo.value || !githubToken.value) {
      throw new Error(t('system_pages.bug_tracker.msg.github_required'))
    }
  }
  return config
}

async function handleSave() {
  if (!projectId.value && !isEdit.value) { message.warning(t('system_pages.bug_tracker.msg.select_project')); return }
  if (!form.value.name) { message.warning(t('system_pages.bug_tracker.msg.name_required')); return }
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      tracker_type: form.value.tracker_type,
      config: validateConfig(),
      field_mapping: buildFieldMapping(),
      is_enabled: form.value.is_enabled,
    }
    if (isEdit.value) {
      await bugTrackerApi.update(editingId.value!, payload)
    } else {
      await bugTrackerApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? t('system_pages.bug_tracker.msg.update_success') : t('system_pages.bug_tracker.msg.create_success'))
    formOpen.value = false
    void loadTrackers()
  } catch (error) {
    message.error(getErrorMessage(error, t('system_pages.bug_tracker.msg.save_failed')))
  }
  finally { saving.value = false }
}

async function handleTestConnection(record: BugTrackerItem) {
  testingId.value = record.id
  try {
    const result = await bugTrackerApi.testConnection({
      tracker_id: record.id,
      tracker_type: record.tracker_type,
      config: {},
    })
    if (result.ok) {
      message.success(result.message)
    } else {
      message.error(result.message)
    }
  } catch (error) {
    message.error(getErrorMessage(error, t('system_pages.bug_tracker.msg.test_failed')))
  } finally {
    testingId.value = null
  }
}

async function handleDelete(id: number) {
  try {
    await bugTrackerApi.delete(id)
    message.success(t('system_pages.bug_tracker.msg.delete_success'))
    void loadTrackers()
  } catch (error) {
    message.error(getErrorMessage(error, t('system_pages.bug_tracker.msg.delete_failed')))
  }
}
</script>

<style scoped>
.bug-tracker-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
