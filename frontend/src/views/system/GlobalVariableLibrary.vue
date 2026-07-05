<template>
  <div class="page-shell system-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.global_variable.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.global_variable.subtitle') }}</div>
      </div>
      <a-space>
        <a-select
          v-model:value="selectedScope"
          style="width: 140px"
          :options="scopeOptions"
          @change="onScopeChange"
        />
        <a-select
          v-if="selectedScope === 'project'"
          v-model:value="selectedProjectId"
          :placeholder="t('mobile_special.select_project')"
          style="width: 220px"
          :options="projectOptions"
          @change="loadVariables"
        />
        <a-button type="primary" :disabled="!canCreate" @click="openCreate">
          {{ t('system_pages.global_variable.new') }}
        </a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <a-card class="table-panel" :bordered="false">
      <a-table
        :data-source="variables"
        :columns="columns"
        :pagination="{ pageSize: 20 }"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'key'">
            <code style="font-size: 13px">{{ record.key }}</code>
          </template>
          <template v-else-if="column.key === 'value'">
            <span v-if="record.is_secret">
              <span>{{ revealedValues[record.id] ?? record.value }}</span>
              <a-button type="link" size="small" @click="toggleReveal(record)">
                {{ revealedValues[record.id] ? t('system_pages.global_variable.hide') : t('system_pages.global_variable.show') }}
              </a-button>
            </span>
            <span v-else>{{ record.value }}</span>
          </template>
          <template v-else-if="column.key === 'is_secret'">
            <a-tag :color="record.is_secret ? 'red' : 'default'">
              {{ record.is_secret ? t('common.yes') : t('common.no') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'scope_type'">
            <a-tag>{{ record.scope_type === 'global' ? t('system_pages.global_variable.global') : t('system_pages.global_variable.project') }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('system_pages.global_variable.confirm_delete')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
      </a-card>
    </a-spin>

    <!-- Create/Edit Modal -->
    <a-modal
      v-model:open="showModal"
      :title="editingVar ? t('system_pages.global_variable.edit') : t('system_pages.global_variable.new')"
      :confirm-loading="saving"
      @ok="handleSave"
      @cancel="resetForm"
    >
      <a-form :label-col="{ span: 5 }" layout="horizontal">
        <a-form-item :label="t('common.name')" required>
          <a-input v-model:value="form.key" :placeholder="t('system_pages.global_variable.key_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.global_variable.value')" required>
          <a-input-password v-model:value="form.value" :placeholder="t('system_pages.global_variable.value_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.global_variable.secret_storage')">
          <a-switch v-model:checked="form.is_secret" />
          <span style="margin-left: 8px; color: var(--c-text-tertiary)">{{ t('system_pages.global_variable.secret_hint') }}</span>
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('system_pages.global_variable.desc_placeholder')" />
        </a-form-item>
        <a-form-item v-if="selectedScope === 'project'" :label="t('common.project')" required>
          <a-select
            v-model:value="form.project_id"
            :placeholder="t('system_pages.global_variable.select_project')"
            :options="projectOptions"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { globalVariableApi, projectApi, type GlobalVariableItem, type ProjectItem, type ScopeType } from '@/api'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const variables = ref<GlobalVariableItem[]>([])
const projects = ref<ProjectItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const selectedScope = ref<'global' | 'project'>('global')
const selectedProjectId = ref<number | null>(null)
const revealedValues = ref<Record<number, string>>({})

const scopeOptions = computed(() => [
  { label: t('system_pages.global_variable.global'), value: 'global' },
  { label: t('system_pages.global_variable.project'), value: 'project' },
])

const canCreate = computed(() => {
  return selectedScope.value === 'global' || selectedProjectId.value !== null
})

const columns = computed(() => [
  { title: t('system_pages.global_variable.columns.key'), key: 'key', dataIndex: 'key', width: '25%' },
  { title: t('system_pages.global_variable.columns.value'), key: 'value', dataIndex: 'value', width: '30%' },
  { title: t('system_pages.global_variable.columns.secret'), key: 'is_secret', dataIndex: 'is_secret', width: '8%' },
  { title: t('system_pages.global_variable.columns.type'), key: 'scope_type', dataIndex: 'scope_type', width: '10%' },
  { title: t('system_pages.global_variable.columns.description'), key: 'description', dataIndex: 'description', ellipsis: true },
  { title: t('system_pages.global_variable.columns.action'), key: 'action', width: '12%' },
])

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

// Form state
const showModal = ref(false)
const editingVar = ref<GlobalVariableItem | null>(null)
const form = ref({
  key: '',
  value: '',
  is_secret: false,
  description: '',
  project_id: null as number | null,
  scope_type: 'global' as ScopeType,
})

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p) => ({ label: p.name, value: p.id }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.global_variable.msg.load_projects_failed')))
  }
  await loadVariables()
})

async function loadVariables() {
  loading.value = true
  try {
    const params: { scope_type: ScopeType; project_id?: number } = { scope_type: selectedScope.value }
    if (selectedScope.value === 'project' && selectedProjectId.value) {
      params.project_id = selectedProjectId.value
    }
    variables.value = await globalVariableApi.list(params)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.global_variable.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

function onScopeChange() {
  if (selectedScope.value === 'global') {
    selectedProjectId.value = null
  }
  revealedValues.value = {}
  loadVariables()
}

async function toggleReveal(record: GlobalVariableItem) {
  if (revealedValues.value[record.id]) {
    const nextValues = { ...revealedValues.value }
    delete nextValues[record.id]
    revealedValues.value = nextValues
    return
  }
  try {
    const detail = await globalVariableApi.get(record.id, { reveal_secret: true })
    revealedValues.value = { ...revealedValues.value, [record.id]: detail.value }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.global_variable.msg.reveal_failed')))
  }
}

function openCreate() {
  editingVar.value = null
  form.value = {
    key: '',
    value: '',
    is_secret: false,
    description: '',
    project_id: selectedProjectId.value,
    scope_type: selectedScope.value,
  }
  showModal.value = true
}

function openEdit(record: GlobalVariableItem) {
  editingVar.value = record
  form.value = {
    key: record.key,
    value: '', // Don't prefill encrypted value
    is_secret: record.is_secret,
    description: record.description || '',
    project_id: record.project_id ?? null,
    scope_type: record.scope_type,
  }
  showModal.value = true
}

function resetForm() {
  editingVar.value = null
  form.value = { key: '', value: '', is_secret: false, description: '', project_id: null, scope_type: 'global' }
}

async function handleSave() {
  if (!form.value.key.trim()) {
    message.warning(t('system_pages.global_variable.msg.key_required'))
    return
  }
  if (!form.value.value.trim()) {
    message.warning(t('system_pages.global_variable.msg.value_required'))
    return
  }
  saving.value = true
  try {
    const data = {
      key: form.value.key.trim(),
      value_encrypted: form.value.value,
      is_secret: form.value.is_secret,
      description: form.value.description.trim() || undefined,
      scope_type: form.value.scope_type,
      project_id: form.value.project_id,
    }
    if (editingVar.value) {
      await globalVariableApi.update(editingVar.value.id, data)
      message.success(t('system_pages.global_variable.msg.update_success'))
    } else {
      await globalVariableApi.create(data)
      message.success(t('system_pages.global_variable.msg.create_success'))
    }
    showModal.value = false
    resetForm()
    await loadVariables()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.global_variable.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await globalVariableApi.delete(id)
    message.success(t('system_pages.global_variable.msg.delete_success'))
    await loadVariables()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.global_variable.msg.delete_failed')))
  }
}
</script>
