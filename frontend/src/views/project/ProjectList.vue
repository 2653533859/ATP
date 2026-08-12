<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('project.title') }}</h2>
        <div class="page-subtitle">{{ t('project.subtitle') }}</div>
      </div>
      <a-space>
        <a-upload :show-upload-list="false" accept=".json" :before-upload="handleImportFile">
          <a-button>{{ t('project.import') }}</a-button>
        </a-upload>
        <a-button type="primary" @click="openCreate">{{ t('project.new') }}</a-button>
      </a-space>
    </div>

    <a-row :gutter="12" class="page-summary">
      <a-col :span="8"><a-card size="small"><a-statistic :title="t('project.summary.total')" :value="projects.length" /></a-card></a-col>
      <a-col :span="8"><a-card size="small"><a-statistic :title="t('project.summary.ai_bound')" :value="aiBoundCount" /></a-card></a-col>
      <a-col :span="8"><a-card size="small"><a-statistic :title="t('project.summary.unbound')" :value="projects.length - aiBoundCount" /></a-card></a-col>
    </a-row>

    <div class="page-toolbar">
      <a-input-search
        v-model:value="keyword"
        :placeholder="t('project.search_placeholder')"
        allow-clear
        style="width: 320px"
      />
      <span class="muted-text">{{ t('project.card_hint') }}</span>
    </div>

    <a-spin :spinning="loading">
      <a-row :gutter="[16, 16]">
        <a-col v-for="p in filteredProjects" :key="p.id" :span="8">
          <a-card hoverable @click="router.push({ name: 'project-overview', params: { projectId: p.id } })">
            <template #title>
              <a-space>
                <span>{{ p.name }}</span>
                <a-tag :color="p.status === 'active' ? 'green' : 'default'">
                  {{ p.status === 'active' ? t('project.status.active') : t('project.status.archived') }}
                </a-tag>
              </a-space>
            </template>
            <p>{{ p.description || t('project.no_description') }}</p>
            <p style="color: var(--c-text-tertiary); font-size: 12px">
              {{ t('project.ai_model_label', { model: llmConfigLabel(p.ai_llm_config_id) }) }}
            </p>
            <template #extra>
              <a-button type="link" @click.stop="openMembers(p)">{{ t('project.members') }}</a-button>
              <a-button
                type="link"
                :disabled="p.status === 'archived'"
                :title="p.status === 'archived' ? t('project.archived_action_hint') : undefined"
                @click.stop="openEdit(p)"
              >
                {{ t('common.edit') }}
              </a-button>
              <a-button
                type="link"
                :disabled="p.status === 'archived'"
                :title="p.status === 'archived' ? t('project.archived_action_hint') : undefined"
                @click.stop="openCopy(p)"
              >
                {{ t('project.copy') }}
              </a-button>
              <a-button type="link" @click.stop="handleExport(p)">{{ t('project.export') }}</a-button>
              <a-popconfirm
                v-if="p.status === 'active'"
                :title="t('project.archive_confirm')"
                :ok-text="t('project.archive')"
                :cancel-text="t('common.cancel')"
                @confirm="handleArchive(p.id)"
              >
                <a-button type="link" @click.stop>{{ t('project.archive') }}</a-button>
              </a-popconfirm>
              <a-button v-else type="link" @click.stop="handleRestore(p.id)">{{ t('project.restore') }}</a-button>
              <a-button type="link" danger @click.stop="handleDelete(p.id)">{{ t('common.delete') }}</a-button>
            </template>
          </a-card>
        </a-col>
      </a-row>
      <a-empty v-if="!loading && filteredProjects.length === 0" :description="t('project.empty')" />
    </a-spin>

    <a-modal
      v-model:open="showModal"
      :title="editingId ? t('project.edit') : t('project.new')"
      :confirm-loading="saving"
      :mask-closable="!saving"
      :keyboard="!saving"
      @ok="handleSave"
      @cancel="handleCancel"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('project.name')" required>
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item v-if="!editingId" :label="t('project.template')">
          <a-select v-model:value="form.template" :options="templateOptions" />
          <span style="color: var(--c-text-tertiary); font-size: 12px">
            {{ t('project.template_hint') }}
          </span>
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-textarea v-model:value="form.description" :rows="3" />
        </a-form-item>
        <a-form-item :label="t('project.ai_model_config')">
          <a-select
            v-model:value="(form.ai_llm_config_id as number | undefined)"
            :placeholder="t('project.no_ai_model')"
            allow-clear
            :options="llmOptions"
          />
          <span style="color: var(--c-text-tertiary); font-size: 12px">
            {{ t('project.ai_model_hint') }}
          </span>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="copyModalOpen"
      :title="t('project.copy_title')"
      :confirm-loading="copying"
      @ok="handleCopy"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('project.copy_name')" required>
          <a-input v-model:value="copyName" />
        </a-form-item>
      </a-form>
      <span style="color: var(--c-text-tertiary); font-size: 12px">
        {{ t('project.copy_hint') }}
      </span>
    </a-modal>

    <a-modal
      v-model:open="importModalOpen"
      :title="t('project.import_title')"
      :confirm-loading="importing"
      :ok-button-props="{ disabled: !importPreview?.valid }"
      @ok="handleImport"
      @cancel="resetImport"
    >
      <p>{{ t('project.import_file', { name: importFileName }) }}</p>
      <a-form layout="vertical">
        <a-form-item :label="t('project.import_policy')">
          <a-select v-model:value="importPolicy" @change="refreshImportPreview">
            <a-select-option value="fail">{{ t('project.import_policy_fail') }}</a-select-option>
            <a-select-option value="rename">{{ t('project.import_policy_rename') }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
      <a-alert
        v-if="importPreview"
        :type="importPreview.valid ? 'success' : 'warning'"
        :message="t('project.import_preview')"
        :description="importPreview.conflicts.length ? importPreview.conflicts.join('；') : t('project.import_no_conflict')"
        show-icon
      />
      <a-alert
        v-if="importPreview?.warnings.length"
        style="margin-top: 12px"
        type="info"
        :message="importPreview.warnings.join('；')"
        show-icon
      />
    </a-modal>

    <MemberManageDrawer
      :open="memberDrawerOpen"
      :project-id="memberProjectId"
      :project-name="memberProjectName"
      :project-status="memberProjectStatus"
      @close="memberDrawerOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  aiLLMConfigApi,
  projectApi,
  type AILLMConfigItem,
  type ProjectExportPayload,
  type ProjectImportPreview,
  type ProjectItem,
  type ProjectTemplate,
} from '@/api'
import MemberManageDrawer from './MemberManageDrawer.vue'
import { getProjectErrorMessage } from './project-errors'

const router = useRouter()
const { t } = useI18n()

const memberDrawerOpen = ref(false)
const memberProjectId = ref<number | null>(null)
const memberProjectName = ref<string | null>(null)
const memberProjectStatus = ref<ProjectItem['status'] | null>(null)

function openMembers(p: ProjectItem) {
  memberProjectId.value = p.id
  memberProjectName.value = p.name
  memberProjectStatus.value = p.status
  memberDrawerOpen.value = true
}
const projects = ref<ProjectItem[]>([])
const llmConfigs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const copyModalOpen = ref(false)
const copying = ref(false)
const copySource = ref<ProjectItem | null>(null)
const copyName = ref('')
const importModalOpen = ref(false)
const importing = ref(false)
const importPayload = ref<ProjectExportPayload | null>(null)
const importPreview = ref<ProjectImportPreview | null>(null)
const importPolicy = ref<'fail' | 'rename'>('fail')
const importFileName = ref('')
const editingId = ref<number | null>(null)
const keyword = ref('')
const form = reactive<{
  name: string
  description: string
  ai_llm_config_id: number | null
  template: ProjectTemplate
}>({ name: '', description: '', ai_llm_config_id: null, template: 'blank' })

const templateOptions = computed(() => [
  { label: t('project.templates.blank'), value: 'blank' },
  { label: t('project.templates.api'), value: 'api' },
  { label: t('project.templates.web'), value: 'web' },
  { label: t('project.templates.android'), value: 'android' },
  { label: t('project.templates.full'), value: 'full' },
])

const llmOptions = computed(() =>
  llmConfigs.value
    .filter((c) => c.enabled)
    .map((c) => ({ label: `${c.name} (${c.provider}/${c.model_name})`, value: c.id })),
)

const llmNameMap = computed(() => {
  const map = new Map<number, string>()
  llmConfigs.value.forEach((c) => map.set(c.id, c.name))
  return map
})

const filteredProjects = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return projects.value
  return projects.value.filter((project) =>
    [project.name, project.description ?? '', llmConfigLabel(project.ai_llm_config_id)]
      .some((value) => value.toLowerCase().includes(needle)),
  )
})

const aiBoundCount = computed(() => projects.value.filter((project) => project.ai_llm_config_id != null).length)

function llmConfigLabel(id?: number | null): string {
  if (id == null) return t('project.unbound')
  return llmNameMap.value.get(id) ?? `#${id}`
}

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await projectApi.list()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

async function loadLLMConfigs() {
  try {
    llmConfigs.value = await aiLLMConfigApi.list()
  } catch (error: unknown) {
    // Non-admin users may receive 403; keep the form usable without the dropdown.
    const status = typeof error === 'object' && error !== null
      ? (error as { response?: { status?: number } }).response?.status
      : undefined
    if (status !== 403) {
      message.error(t('project.msg.load_ai_failed'))
    }
  }
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.description = ''
  form.ai_llm_config_id = null
  form.template = 'blank'
}

function openCreate() {
  resetForm()
  showModal.value = true
}

function openEdit(project: ProjectItem) {
  editingId.value = project.id
  form.name = project.name
  form.description = project.description ?? ''
  form.ai_llm_config_id = project.ai_llm_config_id ?? null
  showModal.value = true
}

function openCopy(project: ProjectItem) {
  copySource.value = project
  copyName.value = `${project.name} ${t('project.copy_suffix')}`
  copyModalOpen.value = true
}

function handleCancel() {
  if (saving.value) return
  showModal.value = false
  resetForm()
}

async function handleSave() {
  if (saving.value) return
  if (!form.name.trim()) {
    message.warning(t('project.msg.name_required'))
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await projectApi.update(editingId.value, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        ai_llm_config_id: form.ai_llm_config_id,
      })
      message.success(t('project.msg.update_success'))
    } else {
      await projectApi.create({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        ai_llm_config_id: form.ai_llm_config_id,
        template: form.template,
      })
      message.success(t('project.msg.create_success'))
    }
    showModal.value = false
    resetForm()
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function handleCopy() {
  if (copying.value || !copySource.value) return
  if (!copyName.value.trim()) {
    message.warning(t('project.msg.copy_name_required'))
    return
  }
  copying.value = true
  try {
    await projectApi.copy(copySource.value.id, { name: copyName.value.trim() })
    message.success(t('project.msg.copy_success'))
    copyModalOpen.value = false
    copySource.value = null
    copyName.value = ''
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.copy_failed')))
  } finally {
    copying.value = false
  }
}

async function handleExport(project: ProjectItem) {
  try {
    const payload = await projectApi.export(project.id)
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${project.name}-project.json`
    anchor.click()
    URL.revokeObjectURL(url)
    message.success(t('project.msg.export_success'))
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.export_failed')))
  }
}

async function handleImportFile(file: File) {
  try {
    importPayload.value = JSON.parse(await file.text()) as ProjectExportPayload
    importFileName.value = file.name
    importPolicy.value = 'fail'
    importModalOpen.value = true
    await refreshImportPreview()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.import_invalid')))
  }
  return false
}

async function refreshImportPreview() {
  if (!importPayload.value) return
  try {
    importPreview.value = await projectApi.previewImport({
      payload: importPayload.value,
      conflict_policy: importPolicy.value,
    })
  } catch (error) {
    importPreview.value = null
    message.error(getProjectErrorMessage(error, t('project.msg.import_failed')))
  }
}

function resetImport() {
  if (importing.value) return
  importModalOpen.value = false
  importPayload.value = null
  importPreview.value = null
  importFileName.value = ''
  importPolicy.value = 'fail'
}

async function handleImport() {
  if (importing.value || !importPayload.value || !importPreview.value?.valid) return
  importing.value = true
  try {
    await projectApi.importProject({
      payload: importPayload.value,
      conflict_policy: importPolicy.value,
    })
    message.success(t('project.msg.import_success'))
    // resetImport 会在导入中保护用户取消；请求成功后先释放保护，确保弹窗真正关闭并清空状态。
    importing.value = false
    resetImport()
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.import_failed')))
  } finally {
    importing.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await projectApi.delete(id)
    message.success(t('project.msg.delete_success'))
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.delete_failed')))
  }
}

async function handleArchive(id: number) {
  try {
    await projectApi.archive(id)
    message.success(t('project.msg.archive_success'))
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.archive_failed')))
  }
}

async function handleRestore(id: number) {
  try {
    await projectApi.restore(id)
    message.success(t('project.msg.restore_success'))
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.restore_failed')))
  }
}

onMounted(() => {
  loadProjects()
  loadLLMConfigs()
})
</script>
