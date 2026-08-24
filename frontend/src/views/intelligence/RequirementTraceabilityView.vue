<template>
  <div class="page-shell requirement-page">
    <section class="requirement-hero">
      <div class="hero-copy">
        <p class="eyebrow"><LinkOutlined /> {{ t('requirement_trace.eyebrow') }}</p>
        <div class="hero-title-row">
          <h1>{{ t('requirement_trace.title') }}</h1>
          <span class="hero-chip">NEED → ACCEPT → TEST</span>
        </div>
        <p class="hero-subtitle">{{ t('requirement_trace.subtitle') }}</p>
        <div class="hero-rail">
          <span class="signal-dot" :class="{ muted: !selectedProjectId }" />
          <span>{{ selectedProjectName || t('requirement_trace.no_project') }}</span>
          <span class="rail-divider" />
          <span class="rail-muted">{{ t('requirement_trace.traceable_status') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label for="requirement-project">{{ t('requirement_trace.project_label') }}</label>
        <a-select
          id="requirement-project"
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :placeholder="t('requirement_trace.project_placeholder')"
          @change="handleProjectChange"
        />
        <div class="hero-control-row">
          <a-button :loading="loading" @click="refreshProject"><ReloadOutlined /> {{ t('common.refresh') }}</a-button>
          <a-button type="primary" :disabled="!selectedProjectId || !canModify" @click="openCreate">
            <PlusOutlined /> {{ t('requirement_trace.new_requirement') }}
          </a-button>
        </div>
      </div>
    </section>

    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('requirement_trace.readonly_title')"
      :description="t('requirement_trace.readonly_description')"
    />
    <a-alert
      v-if="loadError"
      class="load-alert"
      type="warning"
      show-icon
      :message="t('requirement_trace.load_warning')"
      :description="loadError"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('requirement_trace.select_project_hint')" />

    <template v-else>
      <section class="signal-grid" :aria-label="t('requirement_trace.summary_aria')">
        <div class="signal-card signal-card-coral">
          <span class="signal-label">{{ t('requirement_trace.signals.total') }}</span>
          <strong>{{ requirements.length }}</strong>
          <span class="signal-note">{{ t('requirement_trace.signals.total_note') }}</span>
        </div>
        <div class="signal-card signal-card-teal">
          <span class="signal-label">{{ t('requirement_trace.signals.coverage') }}</span>
          <strong>{{ coverageAverage }}%</strong>
          <span class="signal-note">{{ t('requirement_trace.signals.coverage_note') }}</span>
        </div>
        <div class="signal-card signal-card-violet">
          <span class="signal-label">{{ t('requirement_trace.signals.linked') }}</span>
          <strong>{{ linkedCaseTotal }}</strong>
          <span class="signal-note">{{ t('requirement_trace.signals.linked_note') }}</span>
        </div>
        <div class="signal-card signal-card-ink">
          <span class="signal-label">{{ t('requirement_trace.signals.gaps') }}</span>
          <strong>{{ uncoveredRequirementCount }}</strong>
          <span class="signal-note">{{ t('requirement_trace.signals.gaps_note') }}</span>
        </div>
      </section>

      <section class="trace-grid">
        <aside class="requirement-list-panel panel">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">REQUIREMENT REGISTER</span>
              <h2>{{ t('requirement_trace.list_title') }}</h2>
            </div>
            <span class="panel-index">01</span>
          </div>
          <div class="filter-row">
            <a-input v-model:value="keyword" allow-clear :placeholder="t('requirement_trace.keyword_placeholder')" @change="scheduleFilter" @press-enter="loadRequirements" />
            <a-select v-model:value="statusFilter" allow-clear :placeholder="t('requirement_trace.status_placeholder')" :options="statusOptions" @change="loadRequirements" />
          </div>
          <div class="list-meta">
            <span>{{ t('requirement_trace.list_count', { count: requirements.length }) }}</span>
            <a-button type="text" size="small" :loading="loadingRequirements" @click="loadRequirements"><ReloadOutlined /></a-button>
          </div>
          <div v-if="loadingRequirements" class="list-loading"><a-spin size="small" /></div>
          <div v-else-if="!requirements.length" class="list-empty">
            <FileSearchOutlined />
            <strong>{{ t('requirement_trace.empty_title') }}</strong>
            <span>{{ t('requirement_trace.empty_description') }}</span>
            <a-button v-if="canModify" type="link" @click="openCreate">{{ t('requirement_trace.empty_action') }} →</a-button>
          </div>
          <div v-else class="requirement-list">
            <button
              v-for="item in requirements"
              :key="item.id"
              type="button"
              class="requirement-row"
              :class="{ active: item.id === selectedRequirementId }"
              @click="selectRequirement(item.id)"
            >
              <div class="row-topline">
                <span class="requirement-code">{{ item.requirement_code || `REQ-${item.id}` }}</span>
                <a-tag :color="priorityColor(item.priority)">{{ item.priority }}</a-tag>
              </div>
              <strong>{{ item.title }}</strong>
              <span class="row-description">{{ item.description || t('requirement_trace.no_description') }}</span>
              <div class="row-footer">
                <span>{{ t(`requirement_trace.status.${item.status}`) }}</span>
                <span>{{ item.linked_case_count }} {{ t('requirement_trace.case_unit') }}</span>
                <span class="row-coverage">{{ item.coverage_rate }}%</span>
              </div>
            </button>
          </div>
        </aside>

        <main class="detail-panel panel">
          <div v-if="loadingDetail" class="detail-loading"><a-spin /></div>
          <a-empty v-else-if="!selectedRequirement" :description="t('requirement_trace.select_requirement_hint')" />
          <template v-else>
            <div class="detail-heading">
              <div>
                <div class="detail-kicker">
                  <span>{{ selectedRequirement.requirement_code || `REQ-${selectedRequirement.id}` }}</span>
                  <span>·</span>
                  <span>{{ t('requirement_trace.version', { version: selectedRequirement.version }) }}</span>
                </div>
                <h2>{{ selectedRequirement.title }}</h2>
                <p>{{ selectedRequirement.description || t('requirement_trace.no_description') }}</p>
              </div>
              <div class="detail-actions">
                <a-tag :color="statusColor(selectedRequirement.status)">{{ t(`requirement_trace.status.${selectedRequirement.status}`) }}</a-tag>
                <a-button v-if="canModify" type="text" @click="openEdit"><EditOutlined /> {{ t('common.edit') }}</a-button>
                <a-popconfirm v-if="canModify" :title="t('requirement_trace.delete_confirm')" @confirm="deleteRequirement">
                  <a-button type="text" danger><DeleteOutlined /></a-button>
                </a-popconfirm>
              </div>
            </div>

            <div class="coverage-band">
              <div class="coverage-copy">
                <span class="panel-kicker">ACCEPTANCE COVERAGE</span>
                <strong>{{ selectedRequirement.coverage_rate }}%</strong>
                <span>{{ t('requirement_trace.coverage_summary', { covered: selectedRequirement.covered_criterion_count, total: selectedRequirement.acceptance_criteria.length }) }}</span>
              </div>
              <a-progress :percent="selectedRequirement.coverage_rate" :show-info="false" stroke-color="#0f9b8e" />
              <div class="coverage-metrics">
                <span><b>{{ selectedRequirement.acceptance_criteria.length }}</b> {{ t('requirement_trace.criteria_unit') }}</span>
                <span><b>{{ selectedRequirement.links.length }}</b> {{ t('requirement_trace.case_unit') }}</span>
              </div>
            </div>

            <section class="detail-section">
              <div class="section-heading">
                <div>
                  <span class="section-kicker">02 / ACCEPTANCE</span>
                  <h3>{{ t('requirement_trace.criteria_title') }}</h3>
                </div>
                <span class="section-note">{{ t('requirement_trace.criteria_note') }}</span>
              </div>
              <div v-if="selectedRequirement.acceptance_criteria.length" class="criteria-list">
                <div v-for="criterion in selectedRequirement.acceptance_criteria" :key="criterion.id" class="criterion-row" :class="{ covered: coveredCriterionIds.has(criterion.id) }">
                  <span class="criterion-id">{{ criterion.id }}</span>
                  <span class="criterion-text">{{ criterion.text }}</span>
                  <a-tag :color="coveredCriterionIds.has(criterion.id) ? 'green' : 'orange'">
                    {{ coveredCriterionIds.has(criterion.id) ? t('requirement_trace.covered') : t('requirement_trace.uncovered') }}
                  </a-tag>
                </div>
              </div>
              <a-empty v-else :description="t('requirement_trace.no_criteria')" />
            </section>

            <section class="detail-section linked-section">
              <div class="section-heading">
                <div>
                  <span class="section-kicker">03 / TRACE LINKS</span>
                  <h3>{{ t('requirement_trace.links_title') }}</h3>
                </div>
                <a-button v-if="canModify" type="primary" ghost size="small" @click="openLinkEditor"><PlusOutlined /> {{ t('requirement_trace.link_case') }}</a-button>
              </div>
              <div v-if="selectedRequirement.links.length" class="link-list">
                <div v-for="link in selectedRequirement.links" :key="link.id" class="link-row">
                  <div class="link-mark"><CheckCircleOutlined /></div>
                  <div class="link-copy">
                    <strong>{{ link.case_name }}</strong>
                    <span>{{ link.case_code }} · {{ link.module_name }} · {{ link.case_type }}</span>
                    <small>{{ link.criterion_ids.length ? link.criterion_ids.join(' / ') : t('requirement_trace.all_criteria') }}</small>
                  </div>
                  <a-tag>{{ t(`requirement_trace.relations.${link.relation_type}`) }}</a-tag>
                  <a-button v-if="canModify" type="text" danger size="small" @click="unlinkCase(link.id)"><DeleteOutlined /></a-button>
                </div>
              </div>
              <div v-else class="link-empty"><LinkOutlined /><span>{{ t('requirement_trace.no_links') }}</span></div>
            </section>
          </template>
        </main>

        <aside class="impact-panel panel">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">IMPACT RADAR</span>
              <h2>{{ t('requirement_trace.impact_title') }}</h2>
            </div>
            <span class="radar-icon"><AimOutlined /></span>
          </div>
          <template v-if="selectedRequirement && impact">
            <div class="impact-level" :class="`impact-${impact.impact_level}`">
              <span class="impact-pulse" />
              <div><strong>{{ t(`requirement_trace.impact.${impact.impact_level}`) }}</strong><small>{{ t('requirement_trace.impact_level') }}</small></div>
            </div>
            <div class="impact-stat-row">
              <div><span>{{ t('requirement_trace.impact_covered') }}</span><strong>{{ impact.criteria_covered }}/{{ impact.criteria_total }}</strong></div>
              <div><span>{{ t('requirement_trace.impact_candidates') }}</span><strong>{{ impact.candidate_cases.length }}</strong></div>
            </div>
            <div class="impact-block">
              <div class="block-heading"><span>{{ t('requirement_trace.uncovered_title') }}</span><b>{{ impact.uncovered_criteria.length }}</b></div>
              <div v-if="impact.uncovered_criteria.length" class="uncovered-list">
                <div v-for="criterion in impact.uncovered_criteria.slice(0, 5)" :key="criterion.id"><span>{{ criterion.id }}</span>{{ criterion.text }}</div>
              </div>
              <span v-else class="good-note"><CheckCircleOutlined /> {{ t('requirement_trace.no_uncovered') }}</span>
            </div>
            <div class="impact-block">
              <div class="block-heading"><span>{{ t('requirement_trace.candidates_title') }}</span><b>{{ impact.candidate_cases.length }}</b></div>
              <div v-if="impact.candidate_cases.length" class="candidate-list">
                <button v-for="candidate in impact.candidate_cases.slice(0, 5)" :key="candidate.case_id" type="button" class="candidate-row" @click="openCases(candidate.case_id)">
                  <span class="candidate-copy"><strong>{{ candidate.case_name }}</strong><small>{{ candidate.module_name }} · {{ candidate.match_terms.join(' / ') }}</small></span>
                  <ArrowRightOutlined />
                </button>
              </div>
              <span v-else class="muted-note">{{ t('requirement_trace.no_candidates') }}</span>
            </div>
          </template>
          <a-empty v-else :description="t('requirement_trace.impact_hint')" />
        </aside>
      </section>
    </template>

    <a-drawer v-model:open="editorOpen" :title="editingId ? t('requirement_trace.edit_title') : t('requirement_trace.create_title')" :width="560" destroy-on-close>
      <div class="editor-intro"><span class="editor-number">{{ editingId ? 'EDIT' : 'DRAFT' }}</span><p>{{ t('requirement_trace.editor_intro') }}</p></div>
      <section v-if="!editingId" class="parse-box">
        <div class="drawer-section-heading"><strong>{{ t('requirement_trace.parse_title') }}</strong><span>{{ t('requirement_trace.parse_hint') }}</span></div>
        <a-textarea v-model:value="parseText" :rows="5" :placeholder="t('requirement_trace.parse_placeholder')" />
        <a-button class="parse-button" :loading="parsing" :disabled="!parseText.trim()" @click="parseDraft"><FileSearchOutlined /> {{ t('requirement_trace.parse_action') }}</a-button>
      </section>
      <a-form layout="vertical" class="requirement-form">
        <a-form-item :label="t('requirement_trace.form_title')" required>
          <a-input v-model:value="draft.title" :maxlength="256" />
        </a-form-item>
        <a-form-item :label="t('requirement_trace.form_description')">
          <a-textarea v-model:value="draft.description" :rows="4" :maxlength="20000" />
        </a-form-item>
        <div class="form-row">
          <a-form-item :label="t('requirement_trace.form_priority')"><a-select v-model:value="draft.priority" :options="priorityOptions" /></a-form-item>
          <a-form-item :label="t('requirement_trace.form_status')"><a-select v-model:value="draft.status" :options="statusOptions" /></a-form-item>
        </div>
        <div class="criteria-editor-heading"><strong>{{ t('requirement_trace.form_criteria') }}</strong><a-button type="link" size="small" @click="addCriterion"><PlusOutlined /> {{ t('requirement_trace.add_criterion') }}</a-button></div>
        <div v-for="(criterion, index) in draft.acceptance_criteria" :key="criterion.id || index" class="criterion-editor-row">
          <a-input v-model:value="criterion.id" class="criterion-id-input" :placeholder="`AC-${index + 1}`" />
          <a-input v-model:value="criterion.text" :placeholder="t('requirement_trace.criterion_placeholder')" />
          <a-button type="text" danger @click="removeCriterion(index)"><DeleteOutlined /></a-button>
        </div>
        <a-empty v-if="!draft.acceptance_criteria.length" :description="t('requirement_trace.no_criteria_editor')" />
      </a-form>
      <template #footer>
        <div class="drawer-footer"><a-button @click="editorOpen = false">{{ t('common.cancel') }}</a-button><a-button type="primary" :loading="saving" :disabled="!draft.title.trim()" @click="saveRequirement">{{ t('common.save') }}</a-button></div>
      </template>
    </a-drawer>

    <a-drawer v-model:open="linkEditorOpen" :title="t('requirement_trace.link_editor_title')" :width="480" destroy-on-close>
      <div class="link-editor-intro"><LinkOutlined /><p>{{ t('requirement_trace.link_editor_intro') }}</p></div>
      <a-form layout="vertical">
        <a-form-item :label="t('requirement_trace.case_select_label')" required>
          <a-select v-model:value="linkDraft.case_id" show-search :options="caseOptions" :filter-option="filterCaseOption" :placeholder="t('requirement_trace.case_select_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('requirement_trace.relation_label')"><a-select v-model:value="linkDraft.relation_type" :options="relationOptions" /></a-form-item>
        <a-form-item v-if="selectedRequirement?.acceptance_criteria.length" :label="t('requirement_trace.criteria_select_label')">
          <a-checkbox-group v-model:value="linkDraft.criterion_ids" class="criteria-check-list">
            <a-checkbox v-for="criterion in selectedRequirement.acceptance_criteria" :key="criterion.id" :value="criterion.id">{{ criterion.id }} · {{ criterion.text }}</a-checkbox>
          </a-checkbox-group>
          <span class="field-hint">{{ t('requirement_trace.criteria_select_hint') }}</span>
        </a-form-item>
        <a-form-item :label="t('requirement_trace.link_note_label')"><a-textarea v-model:value="linkDraft.note" :rows="3" :placeholder="t('requirement_trace.link_note_placeholder')" /></a-form-item>
      </a-form>
      <template #footer>
        <div class="drawer-footer"><a-button @click="linkEditorOpen = false">{{ t('common.cancel') }}</a-button><a-button type="primary" :loading="linking" :disabled="!linkDraft.case_id" @click="linkCase">{{ t('requirement_trace.save_link') }}</a-button></div>
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
  AimOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  FileSearchOutlined,
  LinkOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  caseApi,
  projectApi,
  requirementsApi,
  type CasePriority,
  type CaseSummaryItem,
  type ProjectItem,
  type RequirementDetailItem,
  type RequirementImpactItem,
  type RequirementListItem,
  type RequirementRelationType,
  type RequirementStatusType,
} from '@/api'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type DraftCriterion = { id?: string; text: string; priority: CasePriority; status: 'draft' | 'approved' }
type RequirementDraft = { title: string; description: string; priority: CasePriority; status: RequirementStatusType; acceptance_criteria: DraftCriterion[] }

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const requirements = ref<RequirementListItem[]>([])
const cases = ref<CaseSummaryItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const requestedRequirementId = ref<number | null>(positiveInt(route.query.requirement_id))
const selectedRequirementId = ref<number | null>(null)
const selectedRequirement = ref<RequirementDetailItem | null>(null)
const impact = ref<RequirementImpactItem | null>(null)
const keyword = ref('')
const statusFilter = ref<RequirementStatusType | undefined>(undefined)
const loading = ref(false)
const loadingRequirements = ref(false)
const loadingDetail = ref(false)
const parsing = ref(false)
const saving = ref(false)
const linking = ref(false)
const loadError = ref('')
const editorOpen = ref(false)
const linkEditorOpen = ref(false)
const editingId = ref<number | null>(null)
const parseText = ref('')
const draft = ref<RequirementDraft>(emptyDraft())
const linkDraft = ref<{ case_id?: number; relation_type: RequirementRelationType; criterion_ids: string[]; note: string }>({
  relation_type: 'covers',
  criterion_ids: [],
  note: '',
})
let loadSequence = 0
let detailSequence = 0
let filterTimer: ReturnType<typeof setTimeout> | undefined

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const coverageAverage = computed(() => requirements.value.length ? Math.round(requirements.value.reduce((sum, item) => sum + item.coverage_rate, 0) / requirements.value.length) : 0)
const linkedCaseTotal = computed(() => requirements.value.reduce((sum, item) => sum + item.linked_case_count, 0))
const uncoveredRequirementCount = computed(() => requirements.value.filter((item) => item.coverage_rate < 100).length)
const coveredCriterionIds = computed(() => new Set(selectedRequirement.value?.links.flatMap((link) => link.criterion_ids) || []))
const statusOptions = computed(() => (['draft', 'active', 'archived'] as RequirementStatusType[]).map((value) => ({ label: t(`requirement_trace.status.${value}`), value })))
const priorityOptions = computed(() => (['P0', 'P1', 'P2', 'P3'] as CasePriority[]).map((value) => ({ label: value, value })))
const relationOptions = computed(() => (['covers', 'validates'] as RequirementRelationType[]).map((value) => ({ label: t(`requirement_trace.relations.${value}`), value })))
const caseOptions = computed(() => cases.value.map((item) => ({ label: `${item.case_code} · ${item.name}`, value: item.id })))

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function emptyDraft(): RequirementDraft {
  return { title: '', description: '', priority: 'P2', status: 'draft', acceptance_criteria: [{ id: 'AC-1', text: '', priority: 'P2', status: 'draft' }] }
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

function scheduleFilter() {
  if (filterTimer) clearTimeout(filterTimer)
  filterTimer = setTimeout(() => { void loadRequirements() }, 250)
}

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await projectApi.list()
    if (!selectedProjectId.value || !projects.value.some((project) => project.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
      syncRoute()
    }
    await loadProjectData()
  } catch (error) {
    loadError.value = errorMessage(error, t('requirement_trace.projects_load_failed'))
  } finally {
    loading.value = false
  }
}

async function loadProjectData() {
  const projectId = selectedProjectId.value
  const sequence = ++loadSequence
  loadError.value = ''
  requirements.value = []
  cases.value = []
  selectedRequirementId.value = null
  selectedRequirement.value = null
  impact.value = null
  if (!projectId) return
  loading.value = true
  const [requirementsResult, casesResult] = await Promise.allSettled([
    requirementsApi.list({ project_id: projectId, status: statusFilter.value, keyword: keyword.value.trim() || undefined }),
    caseApi.list({ project_id: projectId }),
  ])
  if (sequence !== loadSequence) return
  const failures: string[] = []
  if (requirementsResult.status === 'fulfilled') {
    requirements.value = requirementsResult.value.items
    const requested = requestedRequirementId.value
    const initialRequirement = requested && requirements.value.some((item) => item.id === requested)
      ? requested
      : requirements.value[0]?.id
    if (initialRequirement) {
      await selectRequirement(initialRequirement)
      if (requested === initialRequirement) requestedRequirementId.value = null
    }
  } else failures.push(t('requirement_trace.requirements_load_failed'))
  if (casesResult.status === 'fulfilled') cases.value = casesResult.value
  else failures.push(t('requirement_trace.cases_load_failed'))
  loadError.value = failures.join('；')
  loading.value = false
}

async function loadRequirements() {
  if (!selectedProjectId.value) return
  loadingRequirements.value = true
  try {
    const result = await requirementsApi.list({ project_id: selectedProjectId.value, status: statusFilter.value, keyword: keyword.value.trim() || undefined })
    requirements.value = result.items
    if (selectedRequirementId.value && requirements.value.some((item) => item.id === selectedRequirementId.value)) await selectRequirement(selectedRequirementId.value)
    else if (requirements.value[0]) await selectRequirement(requirements.value[0].id)
    else { selectedRequirementId.value = null; selectedRequirement.value = null; impact.value = null }
  } catch (error) {
    loadError.value = errorMessage(error, t('requirement_trace.requirements_load_failed'))
  } finally {
    loadingRequirements.value = false
  }
}

async function selectRequirement(id: number) {
  selectedRequirementId.value = id
  const sequence = ++detailSequence
  loadingDetail.value = true
  try {
    const [detailResult, impactResult] = await Promise.allSettled([requirementsApi.get(id), requirementsApi.impact(id)])
    if (sequence !== detailSequence) return
    if (detailResult.status === 'fulfilled') selectedRequirement.value = detailResult.value
    else throw detailResult.reason
    impact.value = impactResult.status === 'fulfilled' ? impactResult.value : null
  } catch (error) {
    message.error(errorMessage(error, t('requirement_trace.detail_load_failed')))
  } finally {
    if (sequence === detailSequence) loadingDetail.value = false
  }
}

async function handleProjectChange(value?: unknown) {
  selectedProjectId.value = positiveInt(value)
  syncRoute()
  await loadProjectData()
}

async function refreshProject() {
  await loadProjectData()
}

function openCreate() {
  editingId.value = null
  parseText.value = ''
  draft.value = emptyDraft()
  editorOpen.value = true
}

function openEdit() {
  if (!selectedRequirement.value) return
  editingId.value = selectedRequirement.value.id
  parseText.value = ''
  draft.value = {
    title: selectedRequirement.value.title,
    description: selectedRequirement.value.description || '',
    priority: selectedRequirement.value.priority,
    status: selectedRequirement.value.status,
    acceptance_criteria: selectedRequirement.value.acceptance_criteria.map((criterion) => ({ ...criterion })),
  }
  editorOpen.value = true
}

function addCriterion() {
  draft.value.acceptance_criteria.push({ id: `AC-${draft.value.acceptance_criteria.length + 1}`, text: '', priority: 'P2', status: 'draft' })
}

function removeCriterion(index: number) {
  draft.value.acceptance_criteria.splice(index, 1)
}

async function parseDraft() {
  if (!selectedProjectId.value || !parseText.value.trim()) return
  parsing.value = true
  try {
    const result = await requirementsApi.parse({ project_id: selectedProjectId.value, text: parseText.value.trim() })
    draft.value = {
      title: result.title,
      description: result.description,
      priority: 'P2',
      status: 'draft',
      acceptance_criteria: result.acceptance_criteria.map((criterion) => ({ ...criterion })),
    }
    if (result.warnings.length) message.info(result.warnings[0])
  } catch (error) {
    message.error(errorMessage(error, t('requirement_trace.parse_failed')))
  } finally {
    parsing.value = false
  }
}

async function saveRequirement() {
  if (!selectedProjectId.value || !draft.value.title.trim()) return
  saving.value = true
  const criteria = draft.value.acceptance_criteria.filter((criterion) => criterion.text.trim()).map((criterion) => ({ ...criterion, text: criterion.text.trim() }))
  try {
    const body = { ...draft.value, title: draft.value.title.trim(), description: draft.value.description.trim() || null, acceptance_criteria: criteria }
    if (editingId.value) await requirementsApi.update(editingId.value, body)
    else await requirementsApi.create({ project_id: selectedProjectId.value, ...body })
    message.success(t('requirement_trace.save_success'))
    editorOpen.value = false
    await loadRequirements()
  } catch (error) {
    message.error(errorMessage(error, t('requirement_trace.save_failed')))
  } finally {
    saving.value = false
  }
}

async function deleteRequirement() {
  if (!selectedRequirement.value) return
  try {
    await requirementsApi.delete(selectedRequirement.value.id)
    message.success(t('requirement_trace.delete_success'))
    await loadRequirements()
  } catch (error) {
    message.error(errorMessage(error, t('requirement_trace.delete_failed')))
  }
}

function openLinkEditor() {
  linkDraft.value = { relation_type: 'covers', criterion_ids: [], note: '' }
  linkEditorOpen.value = true
}

function filterCaseOption(input: string, option?: { label?: string }) {
  return String(option?.label || '').toLowerCase().includes(input.toLowerCase())
}

async function linkCase() {
  const caseId = linkDraft.value.case_id
  if (!selectedRequirement.value || !caseId) return
  linking.value = true
  try {
    await requirementsApi.linkCase(selectedRequirement.value.id, { ...linkDraft.value, case_id: caseId })
    message.success(t('requirement_trace.link_success'))
    linkEditorOpen.value = false
    await Promise.all([selectRequirement(selectedRequirement.value.id), loadRequirements()])
  } catch (error) {
    message.error(errorMessage(error, t('requirement_trace.link_failed')))
  } finally {
    linking.value = false
  }
}

async function unlinkCase(linkId: number) {
  if (!selectedRequirement.value) return
  try {
    await requirementsApi.unlinkCase(selectedRequirement.value.id, linkId)
    message.success(t('requirement_trace.unlink_success'))
    await Promise.all([selectRequirement(selectedRequirement.value.id), loadRequirements()])
  } catch (error) {
    message.error(errorMessage(error, t('requirement_trace.unlink_failed')))
  }
}

function openCases(caseId?: number) {
  void router.push({ path: '/cases', query: { project_id: String(selectedProjectId.value), ...(caseId ? { case_id: String(caseId) } : {}) } })
}

function statusColor(value: RequirementStatusType) {
  return value === 'active' ? 'green' : value === 'archived' ? 'default' : 'orange'
}

function priorityColor(value: CasePriority) {
  return value === 'P0' ? 'red' : value === 'P1' ? 'volcano' : value === 'P2' ? 'gold' : 'blue'
}

onMounted(() => { void loadProjects() })
</script>

<style scoped>
.requirement-page { --ink: #242227; --muted: #77717b; --paper: #fbfaf6; --line: #e9e4de; --coral: #e67461; --teal: #0f9b8e; --violet: #7460cf; color: var(--ink); }
.requirement-hero { display: flex; justify-content: space-between; gap: 32px; padding: 28px 32px; border-radius: 24px; background: #292334; color: #fff; box-shadow: 0 18px 38px rgba(45, 35, 54, .16); }
.hero-copy { min-width: 0; } .eyebrow, .panel-kicker, .section-kicker { margin: 0; color: #b4a9c7; font-size: 11px; letter-spacing: .16em; font-weight: 700; }
.eyebrow { display: flex; gap: 8px; align-items: center; } .hero-title-row { display: flex; align-items: center; gap: 14px; margin-top: 8px; } h1 { margin: 0; font-size: 32px; letter-spacing: -.04em; } .hero-title-row h1 { color: #fff; }
.hero-chip { padding: 5px 9px; border: 1px solid rgba(255,255,255,.22); border-radius: 99px; color: #d5cadf; font-size: 10px; letter-spacing: .1em; } .hero-subtitle { max-width: 690px; margin: 10px 0 16px; color: #d8d1df; line-height: 1.7; }
.hero-rail { display: flex; align-items: center; gap: 9px; color: #f8efe9; font-size: 13px; } .signal-dot { width: 8px; height: 8px; border-radius: 50%; background: #45c7a7; box-shadow: 0 0 0 5px rgba(69,199,167,.15); } .signal-dot.muted { background: #8f8798; box-shadow: none; } .rail-divider { width: 1px; height: 14px; background: rgba(255,255,255,.25); } .rail-muted { color: #ada4b7; }
.hero-controls { display: flex; flex: 0 0 300px; flex-direction: column; justify-content: center; gap: 8px; } .hero-controls label { color: #cfc5d8; font-size: 12px; } .hero-control-row { display: flex; gap: 8px; margin-top: 8px; } .hero-control-row .ant-btn { flex: 1; }
.readonly-alert, .load-alert { margin-top: 16px; } .project-empty { margin-top: 42px; padding: 72px 20px; background: var(--paper); border: 1px solid var(--line); border-radius: 18px; }
.signal-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 18px 0; } .signal-card { position: relative; min-height: 112px; overflow: hidden; padding: 18px 20px; border: 1px solid var(--line); border-radius: 17px; background: #fff; } .signal-card::after { position: absolute; right: -15px; bottom: -38px; width: 110px; height: 110px; border-radius: 50%; content: ''; opacity: .13; } .signal-card-coral::after { background: var(--coral); } .signal-card-teal::after { background: var(--teal); } .signal-card-violet::after { background: var(--violet); } .signal-card-ink::after { background: var(--ink); } .signal-label { display: block; color: var(--muted); font-size: 12px; } .signal-card strong { display: block; margin: 9px 0 4px; font-size: 27px; letter-spacing: -.05em; } .signal-note { color: #99929a; font-size: 11px; }
.trace-grid { display: grid; grid-template-columns: minmax(255px, .75fr) minmax(430px, 1.55fr) minmax(255px, .8fr); gap: 16px; align-items: start; } .panel { border: 1px solid var(--line); border-radius: 18px; background: #fff; box-shadow: 0 7px 22px rgba(43,34,41,.04); } .requirement-list-panel, .impact-panel { min-height: 620px; padding: 20px; } .detail-panel { min-height: 620px; padding: 26px; }
.panel-head, .section-heading, .detail-heading, .list-meta, .row-topline, .row-footer, .impact-stat-row, .block-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; } .panel-head h2, .section-heading h3, .detail-heading h2 { margin: 5px 0 0; } .panel-head h2 { font-size: 19px; } .panel-index { color: #c9c1c7; font-size: 12px; font-weight: 700; } .filter-row { display: grid; gap: 8px; margin: 20px 0 12px; } .list-meta { padding-bottom: 9px; color: #9a939b; font-size: 11px; border-bottom: 1px solid var(--line); } .list-loading, .detail-loading { display: grid; place-items: center; min-height: 260px; } .requirement-list { display: grid; gap: 7px; margin-top: 8px; } .requirement-row { width: 100%; padding: 12px; border: 1px solid transparent; border-radius: 12px; background: transparent; color: var(--ink); text-align: left; cursor: pointer; transition: border-color .2s, background .2s; } .requirement-row:hover { border-color: #d9d0ec; background: #fcfaff; } .requirement-row.active { border-color: #bfb1e8; background: #f6f2ff; box-shadow: inset 3px 0 0 var(--violet); } .row-topline { margin-bottom: 7px; } .requirement-code { color: var(--violet); font-size: 10px; font-weight: 700; letter-spacing: .05em; } .requirement-row strong { display: block; overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; } .row-description { display: block; overflow: hidden; margin-top: 5px; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; } .row-footer { margin-top: 11px; color: #a29ba1; font-size: 10px; } .row-coverage { color: var(--teal); font-weight: 700; } .list-empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 72px 14px 24px; color: var(--muted); text-align: center; } .list-empty > :first-child { color: var(--violet); font-size: 25px; } .list-empty strong { color: var(--ink); }
.detail-kicker { display: flex; gap: 8px; color: var(--violet); font-size: 11px; font-weight: 700; letter-spacing: .08em; } .detail-heading h2 { font-size: 25px; letter-spacing: -.035em; } .detail-heading p { max-width: 680px; margin: 8px 0 0; color: var(--muted); line-height: 1.65; white-space: pre-line; } .detail-actions { display: flex; align-items: center; gap: 8px; } .coverage-band { display: grid; grid-template-columns: 1fr minmax(110px, 1.1fr); gap: 8px 24px; align-items: center; margin: 24px 0 28px; padding: 17px; border-radius: 15px; background: #f5faf8; } .coverage-copy { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px; } .coverage-copy .panel-kicker { flex-basis: 100%; color: var(--teal); } .coverage-copy strong { font-size: 25px; } .coverage-copy > span:last-child { color: var(--muted); font-size: 11px; } .coverage-band .ant-progress { grid-column: 2; } .coverage-metrics { display: flex; gap: 20px; color: var(--muted); font-size: 11px; } .coverage-metrics b { color: var(--ink); }
.detail-section { margin-top: 27px; } .section-heading { align-items: flex-end; padding-bottom: 11px; border-bottom: 1px solid var(--line); } .section-heading h3 { font-size: 16px; } .section-note { color: #a098a0; font-size: 11px; } .criteria-list, .link-list { display: grid; gap: 7px; margin-top: 11px; } .criterion-row { display: grid; grid-template-columns: 50px 1fr auto; gap: 10px; align-items: center; padding: 11px 12px; border: 1px solid #eee8e3; border-radius: 10px; } .criterion-row.covered { border-color: #cbe9e1; background: #f8fcfb; } .criterion-id { color: var(--violet); font-size: 11px; font-weight: 700; } .criterion-text { color: #4a454b; font-size: 12px; line-height: 1.5; } .link-row { display: flex; align-items: center; gap: 10px; padding: 11px 0; border-bottom: 1px solid #f0ece8; } .link-mark { color: var(--teal); } .link-copy { display: grid; flex: 1; min-width: 0; gap: 3px; } .link-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .link-copy span, .link-copy small { overflow: hidden; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; } .link-empty { display: flex; justify-content: center; gap: 8px; padding: 35px 0; color: #a29aa2; font-size: 12px; }
.impact-panel .panel-head { margin-bottom: 25px; } .radar-icon { display: grid; place-items: center; width: 33px; height: 33px; border-radius: 10px; background: #f3f0fd; color: var(--violet); } .impact-level { display: flex; align-items: center; gap: 11px; padding: 14px; border-radius: 13px; } .impact-level.impact-high { background: #fff2ed; color: #c65543; } .impact-level.impact-medium { background: #fff9e9; color: #ac7a16; } .impact-level.impact-low { background: #effaf7; color: #168676; } .impact-pulse { width: 10px; height: 10px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 5px color-mix(in srgb, currentColor 15%, transparent); } .impact-level div { display: grid; gap: 2px; } .impact-level small { opacity: .75; font-size: 10px; } .impact-stat-row { margin: 17px 0; } .impact-stat-row div { display: grid; gap: 3px; } .impact-stat-row span { color: var(--muted); font-size: 11px; } .impact-stat-row strong { font-size: 20px; } .impact-block { padding: 16px 0; border-top: 1px solid var(--line); } .block-heading { color: var(--muted); font-size: 12px; } .block-heading b { color: var(--ink); } .uncovered-list, .candidate-list { display: grid; gap: 8px; margin-top: 13px; } .uncovered-list div { display: flex; gap: 7px; color: #625b63; font-size: 11px; line-height: 1.5; } .uncovered-list span { flex: 0 0 auto; color: var(--coral); font-weight: 700; } .good-note, .muted-note { display: flex; gap: 6px; margin-top: 14px; color: var(--teal); font-size: 11px; } .muted-note { color: #a29aa2; } .candidate-row { display: flex; align-items: center; gap: 8px; padding: 9px; border: 1px solid #eee9e5; border-radius: 9px; background: #fff; color: var(--ink); text-align: left; cursor: pointer; } .candidate-row:hover { border-color: #c9bee9; background: #fcfaff; } .candidate-copy { display: grid; flex: 1; min-width: 0; gap: 3px; } .candidate-copy strong, .candidate-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .candidate-copy small { color: var(--muted); font-size: 10px; }
.editor-intro, .link-editor-intro { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 19px; padding: 13px; border-radius: 12px; background: #f8f5ff; color: #6c6190; } .editor-intro p, .link-editor-intro p { margin: 0; font-size: 12px; line-height: 1.6; } .editor-number { color: var(--violet); font-size: 11px; font-weight: 800; letter-spacing: .1em; } .parse-box { margin-bottom: 22px; padding: 15px; border: 1px dashed #c6b9ed; border-radius: 14px; background: #fcfaff; } .drawer-section-heading { display: flex; flex-direction: column; gap: 3px; margin-bottom: 10px; } .drawer-section-heading span { color: var(--muted); font-size: 11px; } .parse-button { margin-top: 10px; } .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; } .criteria-editor-heading { display: flex; justify-content: space-between; align-items: center; margin: 2px 0 9px; } .criterion-editor-row { display: grid; grid-template-columns: 70px 1fr 30px; gap: 6px; margin-bottom: 8px; } .criterion-id-input { color: var(--violet); } .drawer-footer { display: flex; justify-content: flex-end; gap: 8px; } .criteria-check-list { display: grid; gap: 9px; } .criteria-check-list .ant-checkbox-wrapper { line-height: 1.5; } .field-hint { display: block; margin-top: 8px; color: var(--muted); font-size: 11px; }
@media (max-width: 1200px) { .trace-grid { grid-template-columns: minmax(240px, .8fr) minmax(430px, 1.5fr); } .impact-panel { grid-column: 1 / -1; min-height: auto; } .impact-panel .impact-block { display: inline-block; width: 48%; vertical-align: top; margin-right: 1%; } }
@media (max-width: 780px) { .requirement-hero { flex-direction: column; padding: 22px; } .hero-controls { flex-basis: auto; } .signal-grid { grid-template-columns: 1fr 1fr; } .trace-grid { grid-template-columns: 1fr; } .detail-panel { grid-row: 1; } .requirement-list-panel { grid-row: 2; min-height: auto; } .impact-panel { grid-column: auto; grid-row: 3; } .detail-heading { flex-direction: column; align-items: flex-start; } .coverage-band { grid-template-columns: 1fr; } .coverage-band .ant-progress { grid-column: 1; } .form-row { grid-template-columns: 1fr; gap: 0; } }
@media (prefers-reduced-motion: reduce) { .requirement-row, .candidate-row { transition: none; } }
</style>
