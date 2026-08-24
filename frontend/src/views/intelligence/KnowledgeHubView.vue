<template>
  <div class="knowledge-page">
    <section class="knowledge-hero">
      <div class="hero-copy">
        <p class="eyebrow"><BookOutlined /> {{ t('knowledge_hub.eyebrow') }}</p>
        <div class="hero-title-row">
          <h1>{{ t('knowledge_hub.title') }}</h1>
          <span class="hero-chip">EVIDENCE / SOURCE / SCOPE</span>
        </div>
        <p class="hero-subtitle">{{ t('knowledge_hub.subtitle') }}</p>
        <div class="hero-rail">
          <span class="signal-dot" :class="{ muted: !keyword.trim() }" />
          <span>{{ keyword.trim() || t('knowledge_hub.all_projects') }}</span>
          <span class="rail-divider" />
          <span class="rail-muted">{{ t('knowledge_hub.reader_project') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label for="knowledge-project">{{ t('knowledge_hub.project_label') }}</label>
        <a-select
          id="knowledge-project"
          v-model:value="projectSelectId"
          allow-clear
          :options="projectOptions"
          :placeholder="t('knowledge_hub.all_projects')"
          @change="handleProjectChange"
        />
        <div class="search-box">
          <SearchOutlined />
          <a-input
            v-model:value="keyword"
            allow-clear
            :placeholder="t('knowledge_hub.search_placeholder')"
            @press-enter="loadKnowledge"
          />
          <a-button type="primary" :loading="loading" @click="loadKnowledge">{{ t('knowledge_hub.search_action') }}</a-button>
        </div>
      </div>
    </section>

    <a-alert v-if="loadError" class="load-alert" type="warning" show-icon :message="loadError" />

    <section class="signal-strip" :aria-label="t('knowledge_hub.source_index')">
      <div class="signal-summary">
        <span class="signal-label">{{ t('knowledge_hub.result_title') }}</span>
        <strong>{{ total }}</strong>
        <span>{{ t('knowledge_hub.result_count', { count: total }) }}</span>
      </div>
      <button
        type="button"
        class="source-pill source-pill-all"
        :class="{ active: !sourceFilter }"
        @click="selectSource(undefined)"
      >
        <span class="source-icon"><AppstoreOutlined /></span>
        <span><b>{{ t('knowledge_hub.source_all') }}</b><small>{{ total }}</small></span>
      </button>
      <button
        v-for="source in sourceTypes"
        :key="source"
        type="button"
        class="source-pill"
        :class="[`source-${source}`, { active: sourceFilter === source }]"
        @click="selectSource(source)"
      >
        <span class="source-icon"><component :is="sourceIcon(source)" /></span>
        <span><b>{{ t(`knowledge_hub.source.${source}`) }}</b><small>{{ sourceCounts[source] || 0 }}</small></span>
      </button>
    </section>

    <section class="knowledge-grid">
      <aside class="source-panel panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">SOURCE INDEX</span>
            <h2>{{ t('knowledge_hub.source_index') }}</h2>
          </div>
          <span class="index-mark">A</span>
        </div>
        <p class="panel-description">{{ t('knowledge_hub.source_index_hint') }}</p>
        <div class="source-list">
          <button
            v-for="source in sourceTypes"
            :key="`index-${source}`"
            type="button"
            class="source-row"
            :class="{ active: sourceFilter === source }"
            @click="selectSource(sourceFilter === source ? undefined : source)"
          >
            <span class="source-row-icon" :class="`source-${source}`"><component :is="sourceIcon(source)" /></span>
            <span class="source-row-copy"><strong>{{ t(`knowledge_hub.source.${source}`) }}</strong><small>{{ sourceDescription(source) }}</small></span>
            <b>{{ sourceCounts[source] || 0 }}</b>
          </button>
        </div>
        <div class="scope-note">
          <GlobalOutlined />
          <span>{{ t('knowledge_hub.reader_global') }}</span>
        </div>
        <a-button v-if="canCreate" class="new-entry-button" block @click="openCreate"><PlusOutlined /> {{ t('knowledge_hub.new_entry') }}</a-button>
      </aside>

      <main class="result-panel panel">
        <div class="result-heading">
          <div>
            <span class="panel-kicker">KNOWLEDGE STREAM</span>
            <h2>{{ t('knowledge_hub.result_title') }}</h2>
          </div>
          <div class="result-actions">
            <a-select v-model:value="statusFilter" allow-clear size="small" :options="statusOptions" :placeholder="t('knowledge_hub.status_filter')" @change="loadKnowledge" />
            <a-button type="text" size="small" :loading="loading" @click="loadKnowledge"><ReloadOutlined /></a-button>
          </div>
        </div>
        <div class="result-meta">
          <span>{{ t('knowledge_hub.result_count', { count: total }) }}</span>
          <span v-if="sourceFilter" class="active-filter">{{ t(`knowledge_hub.source.${sourceFilter}`) }}</span>
        </div>
        <div v-if="loading" class="result-loading"><a-spin /></div>
        <div v-else-if="!results.length" class="result-empty">
          <SearchOutlined />
          <strong>{{ t('knowledge_hub.no_results_title') }}</strong>
          <span>{{ t('knowledge_hub.no_results_description') }}</span>
          <a-button v-if="canCreate" type="link" @click="openCreate">{{ t('knowledge_hub.empty_action') }} →</a-button>
        </div>
        <div v-else class="result-list">
          <article
            v-for="item in results"
            :key="item.key"
            class="result-card"
            :class="{ selected: item.key === selectedItem?.key, 'built-in': !item.is_editable }"
            tabindex="0"
            @click="selectItem(item)"
            @keydown.enter="selectItem(item)"
          >
            <div class="result-card-spine" :class="`source-${item.source_type}`" />
            <div class="result-card-body">
              <div class="result-topline">
                <span class="result-source"><component :is="sourceIcon(item.source_type)" /> {{ t(`knowledge_hub.source.${item.source_type}`) }}</span>
                <a-tag v-if="item.is_editable" color="green">{{ t('knowledge_hub.editable') }}</a-tag>
                <a-tag v-else>{{ t('knowledge_hub.read_only') }}</a-tag>
              </div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.excerpt || t('knowledge_hub.reader_hint') }}</p>
              <div class="result-footer">
                <span><GlobalOutlined v-if="item.is_global" /><FolderOpenOutlined v-else /> {{ item.is_global ? t('knowledge_hub.global') : item.project_name || t('knowledge_hub.project') }}</span>
                <span v-if="item.match_terms.length">{{ t('knowledge_hub.match_terms', { terms: item.match_terms.join(' / ') }) }}</span>
                <span>{{ formatTime(item.updated_at) }}</span>
              </div>
            </div>
            <ArrowRightOutlined class="result-arrow" />
          </article>
        </div>
      </main>

      <aside class="reader-panel panel">
        <template v-if="selectedItem">
          <div class="reader-heading">
            <span class="panel-kicker">EVIDENCE READER</span>
            <div class="reader-actions">
              <a-button v-if="selectedDetail?.is_editable" type="text" size="small" @click="openEdit"><EditOutlined /> {{ t('knowledge_hub.edit') }}</a-button>
              <a-popconfirm v-if="selectedDetail?.is_editable && selectedDetail.document_id" :title="t('knowledge_hub.delete_confirm')" @confirm="deleteEntry">
                <a-button type="text" danger size="small"><DeleteOutlined /></a-button>
              </a-popconfirm>
            </div>
          </div>
          <div class="reader-source-line">
            <span class="source-row-icon" :class="`source-${selectedItem.source_type}`"><component :is="sourceIcon(selectedItem.source_type)" /></span>
            <span>{{ t(`knowledge_hub.source.${selectedItem.source_type}`) }}</span>
            <a-tag v-if="selectedItem.is_global" color="blue">{{ t('knowledge_hub.global') }}</a-tag>
          </div>
          <h2>{{ selectedItem.title }}</h2>
          <div v-if="loadingDetail" class="reader-loading"><a-spin size="small" /></div>
          <template v-else>
            <p v-if="selectedDetail?.summary" class="reader-summary">{{ selectedDetail.summary }}</p>
            <div class="reader-content">{{ selectedDetail?.content || selectedItem.excerpt }}</div>
            <div v-if="selectedItem.tags.length" class="reader-tags"><a-tag v-for="tag in selectedItem.tags" :key="tag">{{ tag }}</a-tag></div>
            <dl class="reader-meta">
              <div><dt>{{ t('knowledge_hub.status_filter') }}</dt><dd>{{ statusLabel(selectedItem.status) }}</dd></div>
              <div><dt>{{ t('knowledge_hub.reader_version', { version: selectedDetail?.version || 1 }) }}</dt><dd>{{ formatTime(selectedItem.updated_at) }}</dd></div>
              <div v-if="selectedItem.source_ref"><dt>{{ t('knowledge_hub.source_ref') }}</dt><dd>{{ selectedItem.source_ref }}</dd></div>
            </dl>
            <a-button v-if="selectedItem.target_path" class="open-source-button" block @click="openSource(selectedItem)"><LinkOutlined /> {{ t('knowledge_hub.open_source') }}</a-button>
            <p class="scope-note reader-scope"><GlobalOutlined v-if="selectedItem.is_global" /><LockOutlined v-else /> {{ selectedItem.is_global ? t('knowledge_hub.reader_global') : t('knowledge_hub.reader_project') }}</p>
          </template>
        </template>
        <a-empty v-else :description="t('knowledge_hub.reader_hint')" />
      </aside>
    </section>

    <a-drawer v-model:open="editorOpen" :title="editingId ? t('knowledge_hub.edit_title') : t('knowledge_hub.create_title')" :width="560" destroy-on-close>
      <div class="editor-note"><SafetyCertificateOutlined /><span>{{ t('knowledge_hub.editor_hint') }}</span></div>
      <a-form layout="vertical">
        <a-form-item v-if="!editingId" :label="t('knowledge_hub.form_scope')" required>
          <a-select v-model:value="scopeSelection" :options="scopeOptions" :disabled="!isAdmin" @change="handleScopeChange" />
        </a-form-item>
        <a-form-item :label="t('knowledge_hub.form_source')" required><a-select v-model:value="form.source_type" :options="sourceOptions" /></a-form-item>
        <a-form-item :label="t('knowledge_hub.form_title')" required><a-input v-model:value="form.title" :maxlength="256" /></a-form-item>
        <a-form-item :label="t('knowledge_hub.form_summary')"><a-textarea v-model:value="form.summary" :rows="2" :maxlength="2000" :placeholder="t('knowledge_hub.summary_placeholder')" /></a-form-item>
        <a-form-item :label="t('knowledge_hub.form_content')" required><a-textarea v-model:value="form.content" :rows="10" :maxlength="50000" :placeholder="t('knowledge_hub.content_placeholder')" /></a-form-item>
        <a-form-item :label="t('knowledge_hub.form_source_ref')"><a-input v-model:value="form.source_ref" :placeholder="t('knowledge_hub.source_ref_placeholder')" /></a-form-item>
        <a-form-item :label="t('knowledge_hub.form_tags')"><a-select v-model:value="form.tags" mode="tags" :placeholder="t('knowledge_hub.tags_placeholder')" /></a-form-item>
        <a-form-item :label="t('knowledge_hub.form_status')"><a-select v-model:value="form.status" :options="statusOptions" /></a-form-item>
      </a-form>
      <template #footer>
        <div class="drawer-footer"><a-button @click="editorOpen = false">{{ t('knowledge_hub.cancel') }}</a-button><a-button type="primary" :loading="saving" :disabled="!form.title.trim() || !form.content.trim()" @click="saveEntry">{{ t('knowledge_hub.save') }}</a-button></div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  ArrowRightOutlined,
  BookOutlined,
  BulbOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  GlobalOutlined,
  LinkOutlined,
  LockOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import {
  knowledgeApi,
  projectApi,
  type KnowledgeDetailItem,
  type KnowledgeSavePayload,
  type KnowledgeSearchItem,
  type KnowledgeSourceType,
  type KnowledgeStatusType,
  type ProjectItem,
} from '@/api'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type KnowledgeForm = {
  project_id: number | undefined
  source_type: KnowledgeSourceType
  title: string
  summary: string
  content: string
  source_ref: string
  tags: string[]
  status: KnowledgeStatusType
}
type KnowledgeScopeValue = number | '__global__'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const projects = ref<ProjectItem[]>([])
const results = ref<KnowledgeSearchItem[]>([])
const sourceCounts = ref<Record<string, number>>({})
const total = ref(0)
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const keyword = ref('')
const sourceFilter = ref<KnowledgeSourceType | undefined>(undefined)
const statusFilter = ref<KnowledgeStatusType | undefined>(undefined)
const selectedItem = ref<KnowledgeSearchItem | null>(null)
const selectedDetail = ref<KnowledgeDetailItem | null>(null)
const loadError = ref('')
const loading = ref(false)
const loadingDetail = ref(false)
const saving = ref(false)
const editorOpen = ref(false)
const editingId = ref<number | null>(null)
const form = ref<KnowledgeForm>(emptyForm())
const scopeSelection = ref<KnowledgeScopeValue | undefined>(selectedProjectId.value ?? '__global__')
let loadSequence = 0
let detailSequence = 0

const sourceTypes: KnowledgeSourceType[] = ['standard', 'solution', 'runbook', 'experience', 'defect', 'requirement', 'execution']
const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const isAdmin = computed(() => auth.user?.role === 'admin')
const canModifyProject = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const canCreate = computed(() => isAdmin.value || Boolean(selectedProjectId.value && canModifyProject.value))
const sourceOptions = computed(() => sourceTypes.slice(0, 4).map((value) => ({ label: t(`knowledge_hub.source.${value}`), value })))
const statusOptions = computed(() => (['draft', 'published', 'archived'] as KnowledgeStatusType[]).map((value) => ({ label: t(`knowledge_hub.status.${value}`), value })))
const scopeOptions = computed(() => [
  ...(isAdmin.value ? [{ label: t('knowledge_hub.form_scope_global'), value: '__global__' as const }] : []),
  ...projects.value.filter((project) => isAdmin.value || canEditProjectByRole(auth.user?.role, project.current_user_role)).map((project) => ({ label: project.name, value: project.id })),
])

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function emptyForm(projectId = selectedProjectId.value): KnowledgeForm {
  return { project_id: projectId ?? undefined, source_type: 'experience', title: '', summary: '', content: '', source_ref: '', tags: [], status: 'draft' }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const response = (error as { response?: { data?: { detail?: unknown } }; message?: unknown }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
    if (typeof (error as { message?: unknown }).message === 'string') return String((error as { message: string }).message)
  }
  return error instanceof Error ? error.message : fallback
}

function syncRoute() {
  void router.replace({ query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (selectedProjectId.value && !projects.value.some((project) => project.id === selectedProjectId.value)) selectedProjectId.value = null
    syncRoute()
    await loadKnowledge()
  } catch (error) {
    loadError.value = errorMessage(error, t('knowledge_hub.load_projects_failed'))
  }
}

async function loadKnowledge() {
  const sequence = ++loadSequence
  loading.value = true
  loadError.value = ''
  try {
    const result = await knowledgeApi.list({
      project_id: selectedProjectId.value ?? undefined,
      keyword: keyword.value.trim() || undefined,
      source_type: sourceFilter.value,
      status: statusFilter.value,
    })
    if (sequence !== loadSequence) return
    results.value = result.items
    sourceCounts.value = result.source_counts
    total.value = result.total
    const next = results.value.find((item) => item.key === selectedItem.value?.key) || results.value[0] || null
    if (next) await selectItem(next)
    else { selectedItem.value = null; selectedDetail.value = null }
  } catch (error) {
    if (sequence === loadSequence) loadError.value = errorMessage(error, t('knowledge_hub.load_failed'))
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function selectItem(item: KnowledgeSearchItem) {
  selectedItem.value = item
  selectedDetail.value = null
  const sequence = ++detailSequence
  if (!item.document_id) return
  loadingDetail.value = true
  try {
    const detail = await knowledgeApi.get(item.document_id)
    if (sequence === detailSequence) selectedDetail.value = detail
  } catch (error) {
    if (sequence === detailSequence) message.error(errorMessage(error, t('knowledge_hub.detail_failed')))
  } finally {
    if (sequence === detailSequence) loadingDetail.value = false
  }
}

async function handleProjectChange(value?: unknown) {
  selectedProjectId.value = positiveInt(value)
  syncRoute()
  await loadKnowledge()
}

function selectSource(value?: KnowledgeSourceType) {
  sourceFilter.value = value
  void loadKnowledge()
}

function openCreate() {
  if (!canCreate.value) {
    if (isAdmin.value) message.info(t('knowledge_hub.global_create_admin'))
    return
  }
  editingId.value = null
  form.value = emptyForm()
  scopeSelection.value = selectedProjectId.value ?? '__global__'
  editorOpen.value = true
}

function openEdit() {
  if (!selectedDetail.value?.is_editable || !selectedDetail.value.document_id) return
  editingId.value = selectedDetail.value.document_id
  form.value = {
    project_id: selectedDetail.value.project_id ?? undefined,
    source_type: selectedDetail.value.source_type,
    title: selectedDetail.value.title,
    summary: selectedDetail.value.summary || '',
    content: selectedDetail.value.content,
    source_ref: selectedDetail.value.source_ref || '',
    tags: [...selectedDetail.value.tags],
    status: (['draft', 'published', 'archived'].includes(selectedDetail.value.status) ? selectedDetail.value.status : 'draft') as KnowledgeStatusType,
  }
  scopeSelection.value = selectedDetail.value.project_id ?? '__global__'
  editorOpen.value = true
}

function handleScopeChange(value?: unknown) {
  scopeSelection.value = value === '__global__' ? '__global__' : positiveInt(value) ?? undefined
  form.value.project_id = scopeSelection.value === '__global__' ? undefined : scopeSelection.value
}

async function saveEntry() {
  if (!form.value.title.trim() || !form.value.content.trim()) return
  saving.value = true
  try {
    const body: KnowledgeSavePayload = {
      project_id: editingId.value ? undefined : form.value.project_id,
      source_type: form.value.source_type,
      title: form.value.title.trim(),
      summary: form.value.summary.trim() || null,
      content: form.value.content.trim(),
      source_ref: form.value.source_ref.trim() || null,
      tags: [...new Set(form.value.tags.filter((tag) => tag.trim()).map((tag) => tag.trim()))],
      status: form.value.status,
    }
    if (editingId.value) await knowledgeApi.update(editingId.value, body)
    else await knowledgeApi.create(body)
    message.success(t('knowledge_hub.save_success'))
    editorOpen.value = false
    await loadKnowledge()
  } catch (error) {
    message.error(errorMessage(error, t('knowledge_hub.save_failed')))
  } finally {
    saving.value = false
  }
}

async function deleteEntry() {
  if (!selectedDetail.value?.document_id) return
  try {
    await knowledgeApi.delete(selectedDetail.value.document_id)
    message.success(t('knowledge_hub.delete_success'))
    await loadKnowledge()
  } catch (error) {
    message.error(errorMessage(error, t('knowledge_hub.delete_failed')))
  }
}

function openSource(item: KnowledgeSearchItem) {
  if (item.target_path) void router.push(item.target_path)
}

function sourceIcon(source: KnowledgeSourceType) {
  if (source === 'standard' || source === 'runbook') return FileTextOutlined
  if (source === 'solution' || source === 'experience') return BulbOutlined
  if (source === 'defect') return ExperimentOutlined
  if (source === 'requirement') return BookOutlined
  return SearchOutlined
}

function sourceDescription(source: KnowledgeSourceType) {
  const descriptions: Record<KnowledgeSourceType, string> = {
    standard: t('knowledge_hub.source_desc.standard'),
    defect: t('knowledge_hub.source_desc.defect'),
    solution: t('knowledge_hub.source_desc.solution'),
    runbook: t('knowledge_hub.source_desc.runbook'),
    experience: t('knowledge_hub.source_desc.experience'),
    requirement: t('knowledge_hub.source_desc.requirement'),
    execution: t('knowledge_hub.source_desc.execution'),
  }
  return descriptions[source]
}

function statusLabel(status: string) {
  const known = ['draft', 'published', 'archived', 'open', 'in_progress', 'resolved', 'closed', 'failed', 'error']
  return known.includes(status) ? t(`knowledge_hub.status.${status}`) : status
}

function formatTime(value: string) {
  return new Date(value).toLocaleString(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => { void loadProjects() })
</script>

<style scoped>
.knowledge-page { --ink: #1e282a; --muted: #748083; --paper: #f5f5ef; --line: #e2e6e1; --aqua: #2aa89a; --copper: #c87c4e; --blue: #607ca9; --olive: #829759; color: var(--ink); }
.knowledge-hero { display: flex; justify-content: space-between; gap: 34px; padding: 30px 34px; border-radius: 22px; background: #202d30; color: #fff; box-shadow: 0 18px 40px rgba(25, 44, 45, .16); }
.hero-copy { min-width: 0; } .eyebrow, .panel-kicker { margin: 0; color: #8fd5c8; font-size: 10px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; } .eyebrow { display: flex; align-items: center; gap: 8px; }
.hero-title-row { display: flex; flex-wrap: wrap; align-items: center; gap: 13px; margin-top: 8px; } h1 { margin: 0; color: #fff; font-size: 32px; letter-spacing: -.05em; } .hero-chip { padding: 5px 9px; border: 1px solid rgba(143, 213, 200, .38); border-radius: 3px; color: #b9e8df; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; letter-spacing: .05em; }
.hero-subtitle { max-width: 710px; margin: 10px 0 17px; color: #d3e1df; line-height: 1.75; } .hero-rail { display: flex; align-items: center; gap: 9px; color: #eef9f6; font-size: 12px; } .signal-dot { width: 8px; height: 8px; border-radius: 50%; background: #8fd5c8; box-shadow: 0 0 0 5px rgba(143, 213, 200, .15); } .signal-dot.muted { background: #7e8d8c; box-shadow: none; } .rail-divider { width: 26px; height: 1px; background: rgba(255, 255, 255, .25); } .rail-muted { color: #a9bfbb; }
.hero-controls { display: flex; flex: 0 0 350px; flex-direction: column; justify-content: center; gap: 8px; } .hero-controls label { color: #b8cbc8; font-size: 11px; font-weight: 700; } .hero-controls :deep(.ant-select-selector) { border-color: #607478 !important; background: rgba(255, 255, 255, .08) !important; color: #fff !important; } .hero-controls :deep(.ant-select-selection-placeholder), .hero-controls :deep(.ant-select-selection-item) { color: #fff !important; }
.search-box { display: flex; align-items: center; gap: 8px; margin-top: 6px; padding: 4px 4px 4px 11px; border: 1px solid #607478; border-radius: 8px; background: rgba(255, 255, 255, .08); } .search-box > .anticon { color: #9ccdc5; } .search-box :deep(.ant-input) { flex: 1; min-width: 0; padding: 4px 0; border: 0; background: transparent; color: #fff; box-shadow: none; } .search-box :deep(.ant-input::placeholder) { color: #afc0be; }
.load-alert { margin-top: 16px; }
.signal-strip { display: flex; align-items: stretch; gap: 10px; margin: 18px 0; overflow-x: auto; } .signal-summary { display: flex; min-width: 150px; flex-direction: column; justify-content: center; padding: 8px 17px; border-right: 1px solid var(--line); } .signal-label { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; } .signal-summary strong { margin: 3px 0; font-size: 25px; letter-spacing: -.05em; } .signal-summary > span:last-child { color: #a0a9a8; font-size: 10px; }
.source-pill { display: flex; min-width: 137px; align-items: center; gap: 9px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 9px; background: #fff; color: var(--ink); text-align: left; cursor: pointer; transition: border-color .2s, transform .2s, box-shadow .2s; } .source-pill:hover, .source-pill.active { border-color: var(--aqua); box-shadow: 0 5px 13px rgba(42, 168, 154, .12); transform: translateY(-1px); } .source-pill > span:last-child { display: grid; gap: 2px; } .source-pill b { font-size: 11px; white-space: nowrap; } .source-pill small { color: var(--muted); font-size: 10px; } .source-icon, .source-row-icon { display: grid; place-items: center; flex: 0 0 auto; width: 28px; height: 28px; border-radius: 7px; background: #eef4f2; color: var(--aqua); } .source-pill-all .source-icon { background: #eef0f8; color: var(--blue); }
.source-standard .source-icon, .source-row-icon.source-standard { background: #eef0f8; color: var(--blue); } .source-solution .source-icon, .source-row-icon.source-solution { background: #fff4e8; color: var(--copper); } .source-runbook .source-icon, .source-row-icon.source-runbook { background: #eef4f2; color: var(--aqua); } .source-experience .source-icon, .source-row-icon.source-experience { background: #f2f4e8; color: var(--olive); } .source-defect .source-icon, .source-row-icon.source-defect { background: #fff0eb; color: #c95d4c; } .source-requirement .source-icon, .source-row-icon.source-requirement { background: #f1eef9; color: #7a67ae; } .source-execution .source-icon, .source-row-icon.source-execution { background: #edf2f4; color: #56717d; }
.knowledge-grid { display: grid; grid-template-columns: minmax(225px, .72fr) minmax(420px, 1.48fr) minmax(270px, .9fr); gap: 15px; align-items: start; } .panel { border: 1px solid var(--line); border-radius: 16px; background: #fff; box-shadow: 0 7px 22px rgba(31, 49, 50, .045); } .source-panel, .reader-panel { min-height: 650px; padding: 20px; } .result-panel { min-height: 650px; padding: 22px 20px; }
.panel-heading, .result-heading, .reader-heading, .result-footer, .result-topline { display: flex; align-items: center; justify-content: space-between; gap: 10px; } .panel-heading h2, .result-heading h2 { margin: 4px 0 0; font-size: 19px; letter-spacing: -.03em; } .index-mark { color: #c8d3d0; font-size: 12px; font-weight: 800; } .panel-description { margin: 13px 0 18px; color: var(--muted); font-size: 11px; line-height: 1.65; }
.source-list { display: grid; gap: 5px; } .source-row { display: flex; align-items: center; gap: 9px; width: 100%; padding: 9px 8px; border: 1px solid transparent; border-radius: 9px; background: transparent; color: var(--ink); text-align: left; cursor: pointer; } .source-row:hover, .source-row.active { border-color: #c9e6e0; background: #f4fbf9; } .source-row-copy { display: grid; flex: 1; min-width: 0; gap: 3px; } .source-row-copy strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; } .source-row-copy small { overflow: hidden; color: var(--muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; } .source-row > b { color: var(--muted); font-size: 11px; }
.scope-note { display: flex; gap: 7px; margin-top: 22px; padding-top: 15px; border-top: 1px solid var(--line); color: var(--muted); font-size: 10px; line-height: 1.55; } .scope-note .anticon { flex: 0 0 auto; color: var(--aqua); } .new-entry-button { margin-top: 20px; border-color: #aeddd5; color: #207d73; }
.result-actions { display: flex; align-items: center; gap: 7px; } .result-actions .ant-select { width: 120px; } .result-meta { display: flex; gap: 9px; align-items: center; min-height: 35px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 11px; } .active-filter { padding: 3px 7px; border-radius: 4px; background: #edf7f5; color: #258b80; }
.result-loading, .reader-loading { display: grid; min-height: 260px; place-items: center; } .result-empty { display: flex; min-height: 410px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--muted); text-align: center; } .result-empty > :first-child { color: var(--aqua); font-size: 28px; } .result-empty strong { color: var(--ink); }
.result-list { display: grid; gap: 8px; padding-top: 12px; } .result-card { position: relative; display: flex; gap: 12px; min-height: 117px; overflow: hidden; padding: 13px 12px 12px 15px; border: 1px solid #edf0ed; border-radius: 10px; outline: none; background: #fff; cursor: pointer; transition: border-color .2s, background .2s, box-shadow .2s, transform .2s; } .result-card:hover, .result-card:focus-visible { border-color: #aadbd3; background: #fbfefd; box-shadow: 0 8px 18px rgba(42, 168, 154, .09); transform: translateY(-1px); } .result-card.selected { border-color: #73c8bc; background: #f6fcfa; } .result-card-spine { flex: 0 0 3px; min-height: 82px; border-radius: 99px; background: var(--aqua); } .result-card-spine.source-standard { background: var(--blue); } .result-card-spine.source-solution { background: var(--copper); } .result-card-spine.source-experience { background: var(--olive); } .result-card-spine.source-defect { background: #c95d4c; } .result-card-spine.source-requirement { background: #7a67ae; } .result-card-spine.source-execution { background: #56717d; } .result-card-body { flex: 1; min-width: 0; } .result-source { display: flex; align-items: center; gap: 5px; color: #4d8c84; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; } .result-card h3 { overflow: hidden; margin: 8px 0 5px; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; } .result-card p { display: -webkit-box; overflow: hidden; margin: 0; color: var(--muted); font-size: 11px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; } .result-footer { justify-content: flex-start; margin-top: 10px; color: #9ba5a3; font-size: 9px; } .result-footer span { overflow: hidden; max-width: 48%; text-overflow: ellipsis; white-space: nowrap; } .result-footer span:last-child { margin-left: auto; } .result-arrow { align-self: center; color: #b6c5c2; }
.reader-panel { background: var(--paper); } .reader-heading { align-items: flex-start; } .reader-actions { display: flex; gap: 2px; } .reader-source-line { display: flex; align-items: center; gap: 8px; margin-top: 24px; color: #4d8c84; font-size: 11px; font-weight: 700; } .reader-panel h2 { margin: 12px 0 9px; font-size: 22px; line-height: 1.25; letter-spacing: -.04em; } .reader-summary { padding: 11px 12px; border-left: 3px solid var(--aqua); background: #eaf6f3; color: #4d6764; font-size: 11px; line-height: 1.65; } .reader-content { max-height: 390px; overflow: auto; padding: 13px; border: 1px solid #e2e9e5; border-radius: 8px; background: #fff; color: #4d5757; font-size: 12px; line-height: 1.75; white-space: pre-line; } .reader-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 13px; } .reader-meta { display: grid; gap: 8px; margin: 19px 0 0; } .reader-meta div { display: flex; justify-content: space-between; gap: 10px; padding-bottom: 7px; border-bottom: 1px solid #e0e5e1; } .reader-meta dt { color: var(--muted); font-size: 10px; } .reader-meta dd { overflow: hidden; margin: 0; color: var(--ink); font-size: 10px; text-align: right; text-overflow: ellipsis; white-space: nowrap; } .open-source-button { margin-top: 16px; border-color: #a7d8d0; color: #278b80; } .reader-scope { margin-top: 16px; }
.editor-note { display: flex; gap: 9px; margin-bottom: 20px; padding: 12px; border-radius: 9px; background: #eaf6f3; color: #3f8178; font-size: 11px; line-height: 1.6; } .editor-note .anticon { flex: 0 0 auto; margin-top: 2px; } .drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 1240px) { .knowledge-grid { grid-template-columns: minmax(220px, .7fr) minmax(420px, 1.5fr); } .reader-panel { grid-column: 1 / -1; min-height: auto; } .reader-content { max-height: 250px; } }
@media (max-width: 800px) { .knowledge-hero { flex-direction: column; padding: 23px; } .hero-controls { flex-basis: auto; } .signal-strip { margin-right: -12px; } .knowledge-grid { grid-template-columns: 1fr; } .source-panel, .reader-panel, .result-panel { min-height: auto; } .source-panel { order: 2; } .result-panel { order: 1; } .reader-panel { grid-column: auto; order: 3; } .result-heading { align-items: flex-start; flex-direction: column; } .result-actions { width: 100%; } .result-actions .ant-select { flex: 1; width: auto; } }
@media (prefers-reduced-motion: reduce) { .source-pill, .result-card { transition: none; } }
</style>
