<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('project.title') }}</h2>
        <div class="page-subtitle">{{ t('project.subtitle') }}</div>
      </div>
      <a-button type="primary" @click="openCreate">{{ t('project.new') }}</a-button>
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
          <a-card hoverable :title="p.name" @click="router.push(buildProjectCasesLocation(p.id))">
            <p>{{ p.description || t('project.no_description') }}</p>
            <p style="color: var(--c-text-tertiary); font-size: 12px">
              {{ t('project.ai_model_label', { model: llmConfigLabel(p.ai_llm_config_id) }) }}
            </p>
            <template #extra>
              <a-button type="link" @click.stop="openMembers(p)">{{ t('project.members') }}</a-button>
              <a-button type="link" @click.stop="openEdit(p)">{{ t('common.edit') }}</a-button>
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

    <MemberManageDrawer
      :open="memberDrawerOpen"
      :project-id="memberProjectId"
      :project-name="memberProjectName"
      @close="memberDrawerOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { aiLLMConfigApi, projectApi, type AILLMConfigItem, type ProjectItem } from '@/api'
import MemberManageDrawer from './MemberManageDrawer.vue'
import { getProjectErrorMessage } from './project-errors'
import { buildProjectCasesLocation } from '@/utils/caseNavigation'

const router = useRouter()
const { t } = useI18n()

const memberDrawerOpen = ref(false)
const memberProjectId = ref<number | null>(null)
const memberProjectName = ref<string | null>(null)

function openMembers(p: ProjectItem) {
  memberProjectId.value = p.id
  memberProjectName.value = p.name
  memberDrawerOpen.value = true
}
const projects = ref<ProjectItem[]>([])
const llmConfigs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const editingId = ref<number | null>(null)
const keyword = ref('')
const form = reactive<{
  name: string
  description: string
  ai_llm_config_id: number | null
}>({ name: '', description: '', ai_llm_config_id: null })

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

async function handleDelete(id: number) {
  try {
    await projectApi.delete(id)
    message.success(t('project.msg.delete_success'))
    await loadProjects()
  } catch (error) {
    message.error(getProjectErrorMessage(error, t('project.msg.delete_failed')))
  }
}

onMounted(() => {
  loadProjects()
  loadLLMConfigs()
})
</script>
