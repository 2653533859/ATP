<template>
  <div class="page-shell" style="display: flex; flex-direction: column; height: 100%">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.environment.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.environment.subtitle') }}</div>
      </div>
      <a-space>
        <a-select
          v-model:value="selectedProjectId"
          :placeholder="t('mobile_special.select_project')"
          style="width: 220px"
          :options="projectOptions"
          @change="onProjectChange"
        />
        <a-button type="primary" :disabled="!selectedProjectId" @click="showCreateModal = true">
          {{ t('system_pages.environment.new') }}
        </a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <div v-if="!selectedProjectId">
        <a-empty :description="t('system_pages.environment.select_project_first')" />
      </div>

      <div v-else style="display: flex; gap: 16px; min-height: 400px">
        <!-- Left: environment list -->
        <a-card :title="t('system_pages.environment.list_title')" style="width: 280px; flex-shrink: 0">
          <a-empty v-if="environments.length === 0" :description="t('system_pages.environment.no_environments')" />
          <a-list v-else :data-source="environments" size="small">
            <template #renderItem="{ item }">
              <a-list-item
                style="cursor: pointer; padding: 8px 12px"
                :style="{ background: selectedEnvId === item.id ? 'var(--c-primary-soft)' : 'transparent' }"
                @click="selectEnv(item)"
              >
                <a-list-item-meta :title="item.name" :description="item.description || t('system_pages.environment.no_description')" />
                <template #actions>
                  <a-button type="link" size="small" @click.stop="openEditModal(item)">{{ t('common.edit') }}</a-button>
                  <a-popconfirm
                    :title="t('system_pages.environment.confirm_delete')"
                    @confirm="handleDeleteEnv(item.id)"
                  >
                    <a-button type="link" size="small" danger @click.stop>{{ t('common.delete') }}</a-button>
                  </a-popconfirm>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>

        <!-- Right: variable editor -->
        <a-card
          style="flex: 1"
          :title="selectedEnv ? t('system_pages.environment.variables_for', { name: selectedEnv.name }) : t('system_pages.environment.variables_title')"
        >
          <template v-if="!selectedEnvId">
            <a-empty :description="t('system_pages.environment.select_env_first')" />
          </template>
          <template v-else>
            <a-spin :spinning="varsLoading">
              <div style="margin-bottom: 12px">
                <a-button type="dashed" @click="addVariable">{{ t('system_pages.environment.add_variable') }}</a-button>
              </div>
              <a-table
                :data-source="editingVars"
                :columns="varColumns"
                :pagination="false"
                row-key="_idx"
                size="small"
              >
                <template #bodyCell="{ column, record, index }">
                  <template v-if="column.key === 'key'">
                    <a-input v-model:value="record.key" :placeholder="t('system_pages.environment.key_placeholder')" />
                  </template>
                  <template v-else-if="column.key === 'value'">
                    <a-input-password
                      v-if="record.is_secret"
                      v-model:value="record.value"
                      :placeholder="record._wasSecret ? t('system_pages.environment.keep_secret_placeholder') : t('system_pages.environment.value_placeholder')"
                    />
                    <a-input v-else v-model:value="record.value" :placeholder="t('system_pages.environment.value_placeholder')" />
                  </template>
                  <template v-else-if="column.key === 'is_secret'">
                    <a-switch v-model:checked="record.is_secret" />
                  </template>
                  <template v-else-if="column.key === 'action'">
                    <a-button type="link" danger size="small" @click="removeVariable(index)">
                      {{ t('common.delete') }}
                    </a-button>
                  </template>
                </template>
              </a-table>
              <div style="margin-top: 12px; text-align: right">
                <a-button type="primary" :loading="saving" @click="handleSaveVars">
                  {{ t('system_pages.environment.save_variables') }}
                </a-button>
              </div>
            </a-spin>
          </template>
        </a-card>
      </div>
    </a-spin>

    <!-- Create/Edit modal -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingEnv ? t('system_pages.environment.edit') : t('system_pages.environment.new')"
      :confirm-loading="envSaving"
      @ok="handleSaveEnv"
      @cancel="resetEnvForm"
    >
      <a-form :label-col="{ span: 5 }">
        <a-form-item :label="t('common.name')">
          <a-input v-model:value="envForm.name" :placeholder="t('system_pages.environment.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-textarea v-model:value="envForm.description" :rows="3" :placeholder="t('system_pages.environment.desc_placeholder')" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  projectApi,
  environmentApi,
  type ProjectItem,
  type EnvironmentItem,
} from '@/api'

const { t } = useI18n()

type EditingVariable = {
  key: string
  value: string
  is_secret: boolean
  _idx: number
  _wasSecret: boolean
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

// -- Project selection --
const projects = ref<ProjectItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const selectedProjectId = ref<number | null>(null)

// -- Environment list --
const environments = ref<EnvironmentItem[]>([])
const selectedEnvId = ref<number | null>(null)
const selectedEnv = ref<EnvironmentItem | null>(null)
const loading = ref(false)

// -- Variable editor --
const editingVars = ref<EditingVariable[]>([])
const varsLoading = ref(false)
const saving = ref(false)
const envSaving = ref(false)
let varIdx = 0

const varColumns = computed(() => [
  { title: t('system_pages.environment.columns.key'), key: 'key', dataIndex: 'key', width: '30%' },
  { title: t('system_pages.environment.columns.value'), key: 'value', dataIndex: 'value', width: '35%' },
  { title: t('system_pages.environment.columns.secret'), key: 'is_secret', dataIndex: 'is_secret', width: '15%' },
  { title: t('system_pages.environment.columns.action'), key: 'action', width: '20%' },
])

// -- Create/Edit env form --
const showCreateModal = ref(false)
const editingEnv = ref<EnvironmentItem | null>(null)
const envForm = ref({ name: '', description: '' })

onMounted(async () => {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p) => ({ label: p.name, value: p.id }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.environment.msg.load_projects_failed')))
  }
})

async function onProjectChange() {
  selectedEnvId.value = null
  selectedEnv.value = null
  editingVars.value = []
  await loadEnvironments()
}

async function loadEnvironments() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    environments.value = await environmentApi.list(selectedProjectId.value)
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.environment.msg.load_envs_failed')))
  } finally {
    loading.value = false
  }
}

async function selectEnv(env: EnvironmentItem) {
  selectedEnvId.value = env.id
  selectedEnv.value = env
  await loadVariables()
}

async function loadVariables() {
  if (!selectedEnvId.value) return
  varsLoading.value = true
  try {
    const vars = await environmentApi.getVariables(selectedEnvId.value)
    editingVars.value = vars.map((v) => ({
      key: v.key,
      value: v.is_secret ? '' : v.value,
      is_secret: v.is_secret,
      _idx: varIdx++,
      _wasSecret: v.is_secret,
    }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.environment.msg.load_vars_failed')))
  } finally {
    varsLoading.value = false
  }
}

function addVariable() {
  editingVars.value = [
    ...editingVars.value,
    { key: '', value: '', is_secret: false, _idx: varIdx++, _wasSecret: false },
  ]
}

function removeVariable(index: number) {
  editingVars.value = editingVars.value.filter((_, i) => i !== index)
}

async function handleSaveVars() {
  if (!selectedEnvId.value) return
  const variables = editingVars.value
    .filter((v) => v.key.trim() !== '')
    .map((v) => ({ key: v.key.trim(), value: v.value, is_secret: v.is_secret }))

  // Check duplicate keys
  const keys = variables.map((v) => v.key)
  const duplicates = keys.filter((k, i) => keys.indexOf(k) !== i)
  if (duplicates.length > 0) {
    message.warning(t('system_pages.environment.msg.duplicate_keys', { keys: [...new Set(duplicates)].join(', ') }))
    return
  }

  // Warn about empty secret values
  const emptySecrets = editingVars.value.filter(
    (v) => v.is_secret && v._wasSecret && v.value.trim() === '' && v.key.trim() !== ''
  )
  if (emptySecrets.length > 0) {
    message.warning(t('system_pages.environment.msg.empty_secrets', { count: emptySecrets.length }))
    return
  }

  saving.value = true
  try {
    await environmentApi.saveVariables(selectedEnvId.value, { variables })
    message.success(t('system_pages.environment.msg.variables_saved'))
    await loadVariables()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.environment.msg.save_vars_failed')))
  } finally {
    saving.value = false
  }
}

// -- Environment CRUD --
function openEditModal(env: EnvironmentItem) {
  editingEnv.value = env
  envForm.value = { name: env.name, description: env.description || '' }
  showCreateModal.value = true
}

function resetEnvForm() {
  editingEnv.value = null
  envForm.value = { name: '', description: '' }
}

async function handleSaveEnv() {
  if (!envForm.value.name.trim()) {
    message.warning(t('system_pages.environment.new'))
    return
  }

  envSaving.value = true
  try {
    if (editingEnv.value) {
      await environmentApi.update(editingEnv.value.id, {
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim() || undefined,
      })
      message.success(t('system_pages.environment.msg.env_saved'))
    } else {
      await environmentApi.create({
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim() || undefined,
        project_id: selectedProjectId.value!,
      })
      message.success(t('system_pages.environment.msg.env_saved'))
    }
    showCreateModal.value = false
    resetEnvForm()
    await loadEnvironments()
    // Refresh selectedEnv if it was the one being edited
    if (selectedEnvId.value) {
      const updated = environments.value.find((e) => e.id === selectedEnvId.value)
      if (updated) {
        selectedEnv.value = updated
      }
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.environment.msg.save_env_failed')))
  } finally {
    envSaving.value = false
  }
}

async function handleDeleteEnv(id: number) {
  try {
    await environmentApi.delete(id)
    message.success(t('system_pages.environment.msg.env_deleted'))
    if (selectedEnvId.value === id) {
      selectedEnvId.value = null
      selectedEnv.value = null
      editingVars.value = []
    }
    await loadEnvironments()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.environment.msg.delete_env_failed')))
  }
}
</script>
