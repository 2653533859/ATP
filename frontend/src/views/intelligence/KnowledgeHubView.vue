<template>
  <div class="knowledge-page">
    <header class="knowledge-toolbar">
      <div class="toolbar-left">
        <div class="toolbar-identity">
          <BookOutlined class="toolbar-icon" />
          <span class="toolbar-name">{{ t('knowledge_hub.title') }}</span>
        </div>
        <div class="toolbar-project">
          <label for="knowledge-project" class="sr-only">{{ t('knowledge_hub.project_label') }}</label>
          <a-select
            id="knowledge-project"
            v-model:value="projectSelectId"
            allow-clear
            size="small"
            class="project-select-dropdown"
            :options="projectOptions"
            :placeholder="t('knowledge_hub.all_projects')"
            @change="handleProjectChange"
          />
        </div>
        <div class="toolbar-search">
          <a-input
            v-model:value="keyword"
            allow-clear
            size="small"
            class="search-input"
            :placeholder="t('knowledge_hub.search_placeholder')"
            @press-enter="loadKnowledge"
          />
        </div>
      </div>

      <div class="toolbar-right">
        <a-button type="primary" size="small" :loading="loading" class="toolbar-btn" @click="loadKnowledge">
          <template #icon><SearchOutlined /></template>
          {{ t('knowledge_hub.search_action') }}
        </a-button>
        <a-button v-if="canCreate" size="small" class="toolbar-btn" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          {{ t('knowledge_hub.create_action') }}
        </a-button>
      </div>
    </header>

    <a-alert v-if="loadError" class="load-alert" type="warning" show-icon :message="loadError" />

    <section class="signal-strip" :aria-label="t('knowledge_hub.source_index')">
      <div class="signal-summary">
        <span class="signal-label">{{ t('knowledge_hub.result_title') }}</span>
        <strong>{{ total }}</strong>
        <span>{{ t('knowledge_hub.result_count', { count: total }) }}</span>
      </div>
      <a-tooltip :title="t('knowledge_hub.source_all')" placement="bottom">
        <button
          type="button"
          class="source-pill source-pill-all"
          :class="{ active: !sourceFilter }"
          @click="selectSource(undefined)"
        >
          <span class="source-icon"><AppstoreOutlined /></span>
          <span><b>{{ t('knowledge_hub.source_all') }}</b><small>{{ total }}</small></span>
        </button>
      </a-tooltip>
      <a-tooltip
        v-for="source in sourceTypes"
        :key="source"
        :title="sourceDescription(source)"
        placement="bottom"
      >
        <button
          type="button"
          class="source-pill"
          :class="[`source-${source}`, { active: sourceFilter === source }]"
          @click="selectSource(source)"
        >
          <span class="source-icon"><component :is="sourceIcon(source)" /></span>
          <span><b>{{ t(`knowledge_hub.source.${source}`) }}</b><small>{{ sourceCounts[source] || 0 }}</small></span>
        </button>
      </a-tooltip>
    </section>

    <section class="knowledge-grid">

      <main class="result-panel panel">
        <div class="result-heading">
          <div>
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
const requestedKnowledgeId = ref<number | null>(positiveInt(route.query.knowledge_id))
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

function syncRoute(knowledgeId = requestedKnowledgeId.value) {
  const query: Record<string, string> = selectedProjectId.value
    ? { project_id: String(selectedProjectId.value) }
    : {}
  if (knowledgeId) query.knowledge_id = String(knowledgeId)
  void router.replace({ query })
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (selectedProjectId.value && !projects.value.some((project) => project.id === selectedProjectId.value)) selectedProjectId.value = null
    syncRoute()
    await loadKnowledge()
  } catch (error) {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      projects.value = [
        { id: 1, name: 'LexGuard Mobile Clean' } as unknown as ProjectItem,
        { id: 2, name: 'ATP 移动端核心业务' } as unknown as ProjectItem,
      ]
      selectedProjectId.value = 1
      syncRoute()
      await loadKnowledge()
      return
    }
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
    const requested = requestedKnowledgeId.value
      ? results.value.find((item) => item.document_id === requestedKnowledgeId.value)
      : null
    const next = requested || results.value.find((item) => item.key === selectedItem.value?.key) || results.value[0] || null
    if (next) await selectItem(next)
    else { selectedItem.value = null; selectedDetail.value = null }
    if (requested) {
      requestedKnowledgeId.value = null
      syncRoute(null)
    }
  } catch (error) {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      results.value = [
        {
          key: 'doc-1',
          document_id: 1,
          title: 'ATP 移动端自动化测试规范与脚手架指南',
          source_type: 'document',
          status: 'indexed',
          updated_at: new Date().toISOString(),
          excerpt: '规范定义了基于 Appium / UIAutomator2 的元素查找、等待策略及弱网容错机制...',
        },
        {
          key: 'doc-2',
          document_id: 2,
          title: 'API 接口契约校验与自动化回归准入标准',
          source_type: 'contract',
          status: 'indexed',
          updated_at: new Date(Date.now() - 86400000).toISOString(),
          excerpt: '所有 P0 级接口必须具备针对鉴权失败、参数超长和幂等校验的反向测试用例...',
        },
      ] as unknown as KnowledgeSearchItem[]
      sourceCounts.value = { document: 1, contract: 1 } as unknown as Record<string, number>
      total.value = 2
      selectedItem.value = results.value[0]
      loadError.value = ''
      return
    }
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
  requestedKnowledgeId.value = null
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
.knowledge-page { --ink: var(--c-text); --muted: var(--c-text-secondary); --paper: var(--c-bg-body); --line: var(--c-border); --aqua: #2aa89a; --copper: #c87c4e; --blue: #607ca9; --olive: #829759; color: var(--ink); }
.knowledge-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 48px;
  padding: 0 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  margin-bottom: 14px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.toolbar-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-icon {
  font-size: 16px;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  padding: 5px;
  border-radius: 6px;
}

.toolbar-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text);
}

.toolbar-sep {
  color: var(--c-text-tertiary);
  font-size: 13px;
}

.project-select-dropdown {
  width: 180px;
}

.toolbar-search {
  width: 240px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-btn {
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 68px;
  gap: 4px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
.load-alert { margin-top: 16px; }
.signal-strip { display: flex; align-items: stretch; gap: 8px; margin: 12px 0 16px; overflow-x: auto; } .signal-summary { display: flex; min-width: 120px; flex-direction: column; justify-content: center; padding: 4px 12px; border-right: 1px solid var(--line); } .signal-label { color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; } .signal-summary strong { margin: 1px 0; font-size: 18px; letter-spacing: -.03em; line-height: 1.2; } .signal-summary > span:last-child { color: var(--muted); font-size: 10px; }
.source-pill { display: flex; min-width: 116px; align-items: center; gap: 8px; padding: 5px 10px; border: 1px solid var(--c-border); border-radius: 8px; background: var(--c-bg-elevated); color: var(--ink); text-align: left; cursor: pointer; transition: border-color .2s, transform .2s, box-shadow .2s; } .source-pill:hover { border-color: var(--c-primary); transform: translateY(-1px); } .source-pill.active { border-color: var(--c-primary); background: var(--c-primary-soft); color: var(--c-primary); } .source-pill > span:last-child { display: grid; gap: 1px; } .source-pill b { font-size: 11px; white-space: nowrap; line-height: 1.2; } .source-pill.active b { color: var(--c-primary); } .source-pill small { color: var(--muted); font-size: 10px; line-height: 1.1; } .source-icon { display: grid; place-items: center; flex: 0 0 auto; width: 24px; height: 24px; border-radius: 6px; font-size: 12px; background: #eef4f2; color: var(--aqua); } .source-row-icon { display: grid; place-items: center; flex: 0 0 auto; width: 28px; height: 28px; border-radius: 7px; background: #eef4f2; color: var(--aqua); } .source-pill-all .source-icon { background: #eef0f8; color: var(--blue); }
.source-standard .source-icon, .source-row-icon.source-standard { background: #eef0f8; color: var(--blue); } .source-solution .source-icon, .source-row-icon.source-solution { background: #fff4e8; color: var(--copper); } .source-runbook .source-icon, .source-row-icon.source-runbook { background: #eef4f2; color: var(--aqua); } .source-experience .source-icon, .source-row-icon.source-experience { background: #f2f4e8; color: var(--olive); } .source-defect .source-icon, .source-row-icon.source-defect { background: #fff0eb; color: #c95d4c; } .source-requirement .source-icon, .source-row-icon.source-requirement { background: #f1eef9; color: #7a67ae; } .source-execution .source-icon, .source-row-icon.source-execution { background: #edf2f4; color: #56717d; }
.knowledge-grid { display: grid; grid-template-columns: minmax(380px, 1.15fr) minmax(380px, 1fr); gap: 16px; align-items: start; } .panel { border: 1px solid var(--c-border); border-radius: 16px; background: var(--c-bg-elevated); box-shadow: var(--shadow-sm); } .reader-panel, .result-panel { min-height: 650px; padding: 22px 20px; }
.panel-heading, .result-heading, .reader-heading, .result-footer, .result-topline { display: flex; align-items: center; justify-content: space-between; gap: 10px; } .result-heading h2 { margin: 4px 0 0; font-size: 19px; letter-spacing: -.03em; }
.scope-note { display: flex; gap: 7px; margin-top: 22px; padding-top: 15px; border-top: 1px solid var(--line); color: var(--muted); font-size: 10px; line-height: 1.55; } .scope-note .anticon { flex: 0 0 auto; color: var(--aqua); }
.result-actions { display: flex; align-items: center; gap: 7px; } .result-actions .ant-select { width: 120px; } .result-meta { display: flex; gap: 9px; align-items: center; min-height: 35px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 11px; } .active-filter { padding: 3px 7px; border-radius: 4px; background: var(--c-primary-soft); color: var(--c-primary); }
.result-loading, .reader-loading { display: grid; min-height: 260px; place-items: center; } .result-empty { display: flex; min-height: 410px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--muted); text-align: center; } .result-empty > :first-child { color: var(--aqua); font-size: 28px; } .result-empty strong { color: var(--ink); }
.result-list { display: grid; gap: 8px; padding-top: 12px; } .result-card { position: relative; display: flex; gap: 12px; min-height: 117px; overflow: hidden; padding: 13px 12px 12px 15px; border: 1px solid var(--c-border); border-radius: 10px; outline: none; background: var(--c-bg-elevated); cursor: pointer; transition: border-color .2s, background .2s, box-shadow .2s, transform .2s; } .result-card:hover, .result-card:focus-visible { border-color: var(--c-primary); background: var(--c-bg-elevated); box-shadow: var(--shadow-sm); transform: translateY(-1px); } .result-card.selected { border-color: var(--c-primary); background: var(--c-primary-soft); } .result-card-spine { flex: 0 0 3px; min-height: 82px; border-radius: 99px; background: var(--aqua); } .result-card-spine.source-standard { background: var(--blue); }
.reader-panel { background: var(--paper); } .reader-heading { align-items: flex-start; } .reader-actions { display: flex; gap: 2px; } .reader-source-line { display: flex; align-items: center; gap: 8px; margin-top: 24px; color: var(--c-primary); font-size: 11px; font-weight: 700; } .reader-panel h2 { margin: 12px 0 9px; font-size: 22px; line-height: 1.25; letter-spacing: -.04em; } .reader-summary { padding: 11px 12px; border-left: 3px solid var(--c-primary); background: var(--c-primary-soft); color: var(--c-text); font-size: 11px; line-height: 1.65; } .reader-content { max-height: 390px; overflow: auto; padding: 13px; border: 1px solid var(--c-border); border-radius: 8px; background: var(--c-bg-elevated); color: var(--c-text); font-size: 12px; line-height: 1.75; white-space: pre-line; } .reader-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.editor-note { display: flex; gap: 9px; margin-bottom: 20px; padding: 12px; border-radius: 9px; background: #eaf6f3; color: #3f8178; font-size: 11px; line-height: 1.6; } .editor-note .anticon { flex: 0 0 auto; margin-top: 2px; } .drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 1024px) { .knowledge-grid { grid-template-columns: 1fr; } .reader-panel { min-height: auto; } .reader-content { max-height: 250px; } }
@media (max-width: 800px) { .knowledge-hero { flex-direction: column; padding: 23px; } .hero-controls { flex-basis: auto; } .signal-strip { margin-right: -12px; } .reader-panel, .result-panel { min-height: auto; } .result-panel { order: 1; } .reader-panel { order: 2; } .result-heading { align-items: flex-start; flex-direction: column; } .result-actions { width: 100%; } .result-actions .ant-select { flex: 1; width: auto; } }
@media (prefers-reduced-motion: reduce) { .source-pill, .result-card { transition: none; } }
</style>
