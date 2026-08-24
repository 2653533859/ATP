<template>
  <div class="page-shell ai-workbench">
    <section class="ai-hero">
      <div class="hero-copy">
        <div class="eyebrow"><RobotOutlined /> {{ t('ai_workbench.eyebrow') }}</div>
        <div class="hero-title-row">
          <h1>{{ t('ai_workbench.title') }}</h1>
          <span class="hero-chip">CONTEXT → DRAFT → REVIEW</span>
        </div>
        <p>{{ t('ai_workbench.subtitle') }}</p>
        <div class="hero-rail">
          <span class="live-dot" :class="{ muted: modelState === 'unconfigured' }" />
          <span>{{ modelStatusLabel }}</span>
          <span class="rail-separator" />
          <span class="rail-muted">{{ selectedProjectName || t('ai_workbench.no_project') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label>{{ t('ai_workbench.project_label') }}</label>
        <a-select
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :placeholder="t('ai_workbench.project_placeholder')"
          @change="handleProjectChange"
        />
        <div class="hero-control-row">
          <a-button :loading="loading" @click="refreshWorkbench"><ReloadOutlined /> {{ t('common.refresh') }}</a-button>
          <a-button v-if="isAdmin" type="link" @click="openModelConfig"><SettingOutlined /> {{ t('ai_workbench.model_config') }}</a-button>
        </div>
      </div>
    </section>

    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('ai_workbench.readonly_title')"
      :description="t('ai_workbench.readonly_description')"
    />
    <a-alert
      v-if="loadError"
      class="load-alert"
      type="warning"
      show-icon
      :message="t('ai_workbench.load_warning')"
      :description="loadError"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('ai_workbench.select_project_hint')" />

    <template v-else>
      <section class="signal-grid" :aria-label="t('ai_workbench.summary_aria')">
        <div class="signal-card signal-card-violet">
          <span class="signal-label">{{ t('ai_workbench.signals.context_assets') }}</span>
          <strong>{{ contextAssetCount }}</strong>
          <span class="signal-note">{{ t('ai_workbench.signals.context_note', { datasets: datasets.length, mocks: mockRules.length }) }}</span>
        </div>
        <div class="signal-card signal-card-blue">
          <span class="signal-label">{{ t('ai_workbench.signals.generated_drafts') }}</span>
          <strong>{{ generatedDraftLabel }}</strong>
          <span class="signal-note">{{ generationNote }}</span>
        </div>
        <div class="signal-card signal-card-amber">
          <span class="signal-label">{{ t('ai_workbench.signals.coverage_gaps') }}</span>
          <strong>{{ coverageGapCount }}</strong>
          <span class="signal-note">{{ t('ai_workbench.signals.coverage_note') }}</span>
        </div>
        <div class="signal-card signal-card-green">
          <span class="signal-label">{{ t('ai_workbench.signals.run_quality') }}</span>
          <strong>{{ passRate }}%</strong>
          <span class="signal-note">{{ t('ai_workbench.signals.run_quality_note', { count: overview?.total_runs ?? 0 }) }}</span>
        </div>
      </section>

      <section class="context-rail panel">
        <div class="context-rail-heading">
          <div>
            <div class="panel-kicker">{{ t('ai_workbench.context_kicker') }}</div>
            <h2>{{ t('ai_workbench.context_title') }}</h2>
          </div>
          <span class="context-rail-note"><SafetyCertificateOutlined /> {{ t('ai_workbench.context_note') }}</span>
        </div>
        <div class="context-chip-row">
          <span class="context-chip" :class="{ empty: modelState === 'unconfigured' }"><BulbOutlined /> {{ modelStatusLabel }}</span>
          <span class="context-chip"><DatabaseOutlined /> {{ t('ai_workbench.dataset_chip', { count: datasets.length }) }}</span>
          <span class="context-chip"><BranchesOutlined /> {{ t('ai_workbench.mock_chip', { count: mockRules.length }) }}</span>
          <span class="context-chip"><AppstoreOutlined /> {{ t('ai_workbench.module_chip', { count: flatModules.length }) }}</span>
        </div>
      </section>

      <section class="ai-grid">
        <aside class="prompt-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('ai_workbench.generation_kicker') }}</div>
              <h2>{{ t('ai_workbench.generation_title') }}</h2>
            </div>
            <span class="panel-index">01</span>
          </div>
          <p class="panel-description">{{ t('ai_workbench.generation_description') }}</p>
          <div class="generation-list">
            <button
              type="button"
              class="generation-card generation-card-violet"
              :disabled="!canGenerate || !firstModuleId"
              @click="openCaseGeneration"
            >
              <span class="generation-icon"><FileSearchOutlined /></span>
              <span class="generation-copy">
                <strong>{{ t('ai_workbench.generate_cases') }}</strong>
                <small>{{ firstModuleId ? t('ai_workbench.generate_cases_hint') : t('ai_workbench.no_module_hint') }}</small>
              </span>
              <ArrowRightOutlined class="generation-arrow" />
            </button>
            <button
              type="button"
              class="generation-card generation-card-blue"
              :disabled="!canGenerate"
              @click="openDatasetGeneration"
            >
              <span class="generation-icon"><DatabaseOutlined /></span>
              <span class="generation-copy">
                <strong>{{ t('ai_workbench.generate_dataset') }}</strong>
                <small>{{ t('ai_workbench.generate_dataset_hint') }}</small>
              </span>
              <ArrowRightOutlined class="generation-arrow" />
            </button>
            <button
              type="button"
              class="generation-card generation-card-green"
              :disabled="!canGenerate"
              @click="openMockGeneration"
            >
              <span class="generation-icon"><BranchesOutlined /></span>
              <span class="generation-copy">
                <strong>{{ t('ai_workbench.generate_mock') }}</strong>
                <small>{{ t('ai_workbench.generate_mock_hint') }}</small>
              </span>
              <ArrowRightOutlined class="generation-arrow" />
            </button>
          </div>
          <div class="draft-note"><CheckCircleOutlined /> {{ t('ai_workbench.draft_note') }}</div>
        </aside>

        <main class="signal-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('ai_workbench.signal_kicker') }}</div>
              <h2>{{ t('ai_workbench.signal_title') }}</h2>
            </div>
            <span class="period-chip">{{ t('ai_workbench.last_30_days') }}</span>
          </div>
          <p class="panel-description">{{ t('ai_workbench.signal_description') }}</p>
          <div v-if="funnel" class="funnel-grid">
            <div v-for="item in funnelItems" :key="item.key" class="funnel-item">
              <div class="funnel-item-head"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
              <div class="funnel-track"><span :style="{ width: `${funnelWidth(item.value)}%` }" /></div>
            </div>
          </div>
          <div v-else class="restricted-panel">
            <LockOutlined />
            <span>{{ isAdmin ? t('ai_workbench.signal_unavailable') : t('ai_workbench.admin_signal_hint') }}</span>
          </div>
          <div class="hotspot-heading">
            <span>{{ t('ai_workbench.hotspot_title') }}</span>
            <a-button type="link" size="small" @click="openRuns">{{ t('ai_workbench.view_runs') }} →</a-button>
          </div>
          <div v-if="failureTop.length" class="hotspot-list">
            <button v-for="item in failureTop.slice(0, 4)" :key="`${item.case_id}-${item.case_type}`" type="button" class="hotspot-row" @click="openCases">
              <span class="hotspot-rank">{{ item.failure_count }}</span>
              <span class="hotspot-copy"><strong>{{ item.case_name }}</strong><small>{{ item.case_type }} · {{ t('ai_workbench.failure_count', { count: item.failure_count }) }}</small></span>
              <ArrowRightOutlined />
            </button>
          </div>
          <a-empty v-else :description="t('ai_workbench.no_hotspots')" />
        </main>

        <aside class="context-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('ai_workbench.model_kicker') }}</div>
              <h2>{{ t('ai_workbench.model_title') }}</h2>
            </div>
            <span class="model-state-dot" :class="`state-${modelState}`" />
          </div>
          <div class="model-card" :class="`model-${modelState}`">
            <span class="model-label">{{ t('ai_workbench.project_model') }}</span>
            <strong>{{ modelName }}</strong>
            <small>{{ modelDescription }}</small>
          </div>
          <div class="context-stat-list">
            <div><span>{{ t('ai_workbench.context_dataset') }}</span><strong>{{ datasets.length }}</strong></div>
            <div><span>{{ t('ai_workbench.context_mock') }}</span><strong>{{ mockRules.length }}</strong></div>
            <div><span>{{ t('ai_workbench.context_modules') }}</span><strong>{{ flatModules.length }}</strong></div>
          </div>
          <a-button v-if="isAdmin" type="link" class="context-action" @click="openModelConfig">{{ t('ai_workbench.manage_model') }} →</a-button>
          <p class="context-footnote">{{ t('ai_workbench.model_scope_note') }}</p>
        </aside>
      </section>

      <section class="lower-grid">
        <main class="failure-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('ai_workbench.diagnosis_kicker') }}</div>
              <h2>{{ t('ai_workbench.diagnosis_title') }}</h2>
            </div>
            <a-button type="link" size="small" @click="openRuns">{{ t('ai_workbench.open_task_center') }} →</a-button>
          </div>
          <p class="panel-description">{{ t('ai_workbench.diagnosis_description') }}</p>
          <div v-if="failedTasks.length" class="failure-list">
            <div v-for="task in failedTasks.slice(0, 6)" :key="task.id" class="failure-row">
              <span class="failure-icon"><WarningOutlined /></span>
              <div class="failure-copy"><strong>{{ task.name }}</strong><small>{{ task.task_type }} · {{ formatTime(task.created_at) }}</small></div>
              <span class="failure-message">{{ task.error_message || t('ai_workbench.failure_without_message') }}</span>
              <a-button size="small" @click="openTask(task)">{{ t('ai_workbench.open_diagnosis') }}</a-button>
            </div>
          </div>
          <a-empty v-else :description="t('ai_workbench.no_failures')" />
        </main>

        <aside class="healing-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('ai_workbench.healing_kicker') }}</div>
              <h2>{{ t('ai_workbench.healing_title') }}</h2>
            </div>
            <ExperimentOutlined />
          </div>
          <p class="panel-description">{{ t('ai_workbench.healing_description') }}</p>
          <template v-if="healingStats">
            <div class="healing-rate"><strong>{{ healingStats.adopted_rate }}%</strong><span>{{ t('ai_workbench.adopted_rate') }}</span></div>
            <div class="healing-meter"><span :style="{ width: `${Math.min(100, Math.max(0, healingStats.adopted_rate))}%` }" /></div>
            <div class="healing-counts"><span>{{ t('ai_workbench.adopted_count', { count: healingStats.adopted_count }) }}</span><span>{{ t('ai_workbench.example_count', { count: healingStats.high_quality_example_count }) }}</span></div>
            <a-button v-if="isAdmin" type="link" class="context-action" @click="openHealingStats">{{ t('ai_workbench.open_healing_stats') }} →</a-button>
          </template>
          <div v-else class="restricted-panel healing-restricted"><LockOutlined /><span>{{ isAdmin ? t('ai_workbench.healing_unavailable') : t('ai_workbench.admin_signal_hint') }}</span></div>
        </aside>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  ArrowRightOutlined,
  BranchesOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  LockOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  aiCaseGenerationApi,
  aiHealingStatsApi,
  aiLLMConfigApi,
  caseApi,
  datasetApi,
  mockRuleApi,
  projectApi,
  statisticsApi,
  workbenchApi,
  type AICaseFunnelStats,
  type AIHealingStats,
  type AILLMConfigItem,
  type DatasetListItem,
  type MockRuleItem,
  type ModuleTreeItem,
  type ProjectItem,
  type WorkbenchTaskItem,
} from '@/api'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type FailureHotspot = {
  case_id: number
  project_id: number
  module_id: number
  case_name: string
  case_type: string
  failure_count: number
}
type ErrorLike = { response?: { data?: { detail?: unknown } }; message?: unknown }

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const modules = ref<ModuleTreeItem[]>([])
const datasets = ref<DatasetListItem[]>([])
const mockRules = ref<MockRuleItem[]>([])
const cases = ref<Array<{ automation_status?: string | null }>>([])
const failedTasks = ref<WorkbenchTaskItem[]>([])
const failureTop = ref<FailureHotspot[]>([])
const overview = ref<{ total_cases: number; total_runs: number; pass_rate: number; recent_runs_7d: number } | null>(null)
const funnel = ref<AICaseFunnelStats | null>(null)
const healingStats = ref<AIHealingStats | null>(null)
const modelConfigs = ref<AILLMConfigItem[]>([])
const loading = ref(false)
const loadError = ref('')
let loadSequence = 0
let projectsLoadSequence = 0

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const isAdmin = computed(() => auth.user?.role === 'admin')
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const canGenerate = computed(() => canModify.value && !['unconfigured', 'disabled'].includes(modelState.value))
const flatModules = computed(() => flattenModules(modules.value))
const firstModuleId = computed(() => flatModules.value[0]?.id ?? null)
const contextAssetCount = computed(() => datasets.value.length + mockRules.value.length)
const coverageGapCount = computed(() => cases.value.filter((item) => item.automation_status !== 'auto').length)
const passRate = computed(() => Math.round(Number(overview.value?.pass_rate ?? 0)))
const generatedDraftLabel = computed(() => funnel.value ? String(funnel.value.generated_drafts) : '—')
const generationNote = computed(() => funnel.value
  ? t('ai_workbench.signals.generated_note', { saved: funnel.value.saved_drafts })
  : t('ai_workbench.admin_signal_short'))
const linkedModel = computed(() => modelConfigs.value.find((config) => config.id === selectedProject.value?.ai_llm_config_id))
const modelState = computed<'ready' | 'disabled' | 'unconfigured' | 'unknown'>(() => {
  if (!selectedProject.value?.ai_llm_config_id) return 'unconfigured'
  if (!isAdmin.value) return 'unknown'
  if (!linkedModel.value) return 'unknown'
  return linkedModel.value.enabled ? 'ready' : 'disabled'
})
const modelStatusLabel = computed(() => {
  if (modelState.value === 'ready') return t('ai_workbench.model_ready')
  if (modelState.value === 'disabled') return t('ai_workbench.model_disabled')
  if (modelState.value === 'unconfigured') return t('ai_workbench.model_unconfigured')
  return t('ai_workbench.model_bound')
})
const modelName = computed(() => linkedModel.value?.name || (selectedProject.value?.ai_llm_config_id ? t('ai_workbench.model_bound') : t('ai_workbench.model_unconfigured')))
const modelDescription = computed(() => {
  if (linkedModel.value) return `${linkedModel.value.provider} / ${linkedModel.value.model_name}`
  return modelState.value === 'unconfigured' ? t('ai_workbench.model_unconfigured_hint') : t('ai_workbench.model_visibility_hint')
})
const funnelItems = computed(() => [
  { key: 'sessions', label: t('ai_workbench.funnel_sessions'), value: funnel.value?.generated_sessions ?? 0 },
  { key: 'drafts', label: t('ai_workbench.funnel_drafts'), value: funnel.value?.generated_drafts ?? 0 },
  { key: 'saved', label: t('ai_workbench.funnel_saved'), value: funnel.value?.saved_drafts ?? 0 },
])

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(items: ModuleTreeItem[]): ModuleTreeItem[] {
  return items.flatMap((item) => [item, ...flattenModules(item.children || [])])
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return error instanceof Error ? error.message : fallback
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '—'
}

function funnelWidth(value: number) {
  const max = Math.max(...funnelItems.value.map((item) => item.value), 1)
  return Math.max(value ? 8 : 0, Math.round((value / max) * 100))
}

function clearProjectData() {
  modules.value = []
  datasets.value = []
  mockRules.value = []
  cases.value = []
  failedTasks.value = []
  failureTop.value = []
  overview.value = null
  funnel.value = null
  healingStats.value = null
  modelConfigs.value = []
}

function syncRoute() {
  void router.replace({ query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

async function loadProjectData() {
  const projectId = selectedProjectId.value
  const sequence = ++loadSequence
  clearProjectData()
  loadError.value = ''
  if (!projectId) {
    loading.value = false
    return
  }

  loading.value = true
  const baseResults = await Promise.allSettled([
    projectApi.getModules(projectId),
    caseApi.list({ project_id: projectId }),
    datasetApi.list(projectId),
    mockRuleApi.list({ project_id: projectId }),
    statisticsApi.overview({ project_id: projectId, days: 30 }),
    statisticsApi.failureTop({ project_id: projectId, days: 30, top: 8 }),
    workbenchApi.tasks({ project_id: projectId, limit: 60 }),
  ])
  if (sequence !== loadSequence) return
  const failures: string[] = []
  const [moduleResult, caseResult, datasetResult, mockResult, overviewResult, failureResult, taskResult] = baseResults
  if (moduleResult.status === 'fulfilled') modules.value = moduleResult.value
  else failures.push(t('ai_workbench.load_modules_failed'))
  if (caseResult.status === 'fulfilled') cases.value = caseResult.value
  else failures.push(t('ai_workbench.load_cases_failed'))
  if (datasetResult.status === 'fulfilled') datasets.value = datasetResult.value
  else failures.push(t('ai_workbench.load_datasets_failed'))
  if (mockResult.status === 'fulfilled') mockRules.value = mockResult.value
  else failures.push(t('ai_workbench.load_mocks_failed'))
  if (overviewResult.status === 'fulfilled') overview.value = overviewResult.value
  else failures.push(t('ai_workbench.load_overview_failed'))
  if (failureResult.status === 'fulfilled') failureTop.value = failureResult.value
  else failures.push(t('ai_workbench.load_failures_failed'))
  if (taskResult.status === 'fulfilled') {
    failedTasks.value = taskResult.value.items.filter((item) => ['failed', 'error'].includes(item.status))
  } else failures.push(t('ai_workbench.load_tasks_failed'))

  if (isAdmin.value) {
    const [funnelSettled, healingSettled, modelSettled] = await Promise.all([
      Promise.allSettled([aiCaseGenerationApi.getFunnelStats({ project_id: projectId, days: 30 })]),
      Promise.allSettled([aiHealingStatsApi.getStats({ days: 30 })]),
      Promise.allSettled([aiLLMConfigApi.list()]),
    ])
    if (sequence !== loadSequence) return
    const funnelResult = funnelSettled[0]
    const healingResult = healingSettled[0]
    const modelResult = modelSettled[0]
    if (funnelResult.status === 'fulfilled') funnel.value = funnelResult.value
    if (healingResult.status === 'fulfilled') healingStats.value = healingResult.value
    if (modelResult.status === 'fulfilled') modelConfigs.value = modelResult.value
    if ([funnelResult, healingResult, modelResult].some((result) => result.status === 'rejected')) {
      failures.push(t('ai_workbench.load_optional_failed'))
    }
  }
  loadError.value = failures.length ? failures.join('；') : ''
  loading.value = false
}

async function loadProjects() {
  const sequence = ++projectsLoadSequence
  loading.value = true
  try {
    const nextProjects = await projectApi.list()
    if (sequence !== projectsLoadSequence) return
    projects.value = nextProjects
    if (!selectedProjectId.value || !projects.value.some((project) => project.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
    }
    syncRoute()
    await loadProjectData()
  } catch (error: unknown) {
    if (sequence !== projectsLoadSequence) return
    loadSequence += 1
    clearProjectData()
    message.error(errorMessage(error, t('ai_workbench.load_projects_failed')))
  } finally {
    if (sequence === projectsLoadSequence && !selectedProjectId.value) loading.value = false
  }
}

async function handleProjectChange(value: unknown) {
  selectedProjectId.value = positiveInt(value)
  syncRoute()
  await loadProjectData()
}

async function refreshWorkbench() {
  await loadProjects()
}

function openCaseGeneration() {
  if (!selectedProjectId.value || !firstModuleId.value || !canGenerate.value) return
  void router.push({ name: 'cases', query: { project_id: String(selectedProjectId.value), module_id: String(firstModuleId.value), ai_generate: '1' } })
}

function openCases() {
  if (!selectedProjectId.value) return
  void router.push({ path: '/cases', query: { project_id: String(selectedProjectId.value) } })
}

function openDatasetGeneration() {
  if (!selectedProjectId.value || !canGenerate.value) return
  void router.push({ path: '/system/datasets', query: { project_id: String(selectedProjectId.value) } })
}

function openMockGeneration() {
  if (!selectedProjectId.value || !canGenerate.value) return
  void router.push({ path: '/mock-rules', query: { project_id: String(selectedProjectId.value) } })
}

function openRuns() {
  void router.push({ path: '/tasks', query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

function openTask(task: WorkbenchTaskItem) {
  void router.push(task.detail_path || `/runs/${task.run_id}`)
}

function openModelConfig() {
  void router.push('/system/ai-llm-configs')
}

function openHealingStats() {
  void router.push('/system/ai-healing-stats')
}

onMounted(() => { void loadProjects() })
</script>

<style scoped>
.ai-workbench { --ai-ink: #20242e; --ai-muted: #7c8491; --ai-line: #e5e4e8; --ai-panel: #fff; --ai-violet: #7e62d5; --ai-blue: #4f91d6; --ai-green: #45aa96; --ai-amber: #d39b43; --ai-red: #ce6c72; color: var(--ai-ink); }
.ai-hero { display: flex; justify-content: space-between; gap: 28px; min-height: 195px; padding: 32px 34px; border-radius: 13px; background: radial-gradient(circle at 76% 24%, rgba(126, 98, 213, .28), transparent 30%), linear-gradient(125deg, #211f31 0%, #302744 56%, #183d40 100%); color: #fff; box-shadow: 0 12px 25px rgba(42, 37, 60, .15); }
.hero-copy { min-width: 0; }.eyebrow, .panel-kicker { color: #a89ce6; font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }.eyebrow { display: flex; align-items: center; gap: 7px; }.hero-title-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 8px 0 7px; }.ai-hero h1 { margin: 0; color: #fff; font-size: 31px; letter-spacing: -.05em; }.hero-chip { padding: 4px 8px; border: 1px solid rgba(190, 176, 250, .42); border-radius: 4px; color: #ddd6ff; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; letter-spacing: .04em; }.ai-hero p { max-width: 700px; margin: 0; color: #ddd9e8; line-height: 1.7; }.hero-rail { display: flex; align-items: center; gap: 9px; margin-top: 21px; color: #f0edfb; font-size: 12px; font-weight: 650; }.live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #7dd7bc; box-shadow: 0 0 0 4px rgba(125, 215, 188, .14); }.live-dot.muted { background: var(--ai-amber); box-shadow: 0 0 0 4px rgba(211, 155, 67, .14); }.rail-separator { width: 28px; height: 1px; background: rgba(241, 237, 251, .28); }.rail-muted { color: #b9b3ca; font-weight: 500; }.hero-controls { width: 255px; flex: 0 0 255px; }.hero-controls label { display: block; margin-bottom: 7px; color: #c9c2da; font-size: 11px; font-weight: 700; }.hero-controls :deep(.ant-select-selector) { border-color: #716884 !important; background: rgba(255, 255, 255, .09) !important; color: #fff !important; }.hero-controls :deep(.ant-select-selection-placeholder), .hero-controls :deep(.ant-select-selection-item) { color: #fff !important; }.hero-control-row { display: flex; align-items: center; justify-content: space-between; margin-top: 13px; }.hero-control-row .ant-btn { color: #ded8eb; }
.readonly-alert, .load-alert { margin-top: 14px; }.signal-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }.signal-card { min-height: 106px; padding: 17px 18px; border: 1px solid var(--ai-line); border-radius: 10px; background: var(--ai-panel); box-shadow: 0 7px 18px rgba(49, 46, 64, .045); }.signal-card-violet { border-top: 3px solid var(--ai-violet); }.signal-card-blue { border-top: 3px solid var(--ai-blue); }.signal-card-amber { border-top: 3px solid var(--ai-amber); }.signal-card-green { border-top: 3px solid var(--ai-green); }.signal-label { display: block; color: var(--ai-muted); font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }.signal-card strong { display: block; margin-top: 8px; font-size: 28px; letter-spacing: -.05em; }.signal-note { display: block; margin-top: 5px; color: #9b9da7; font-size: 11px; }
.panel { min-width: 0; border: 1px solid var(--ai-line); border-radius: 12px; background: var(--ai-panel); box-shadow: 0 8px 20px rgba(49, 46, 64, .045); }.context-rail { margin-bottom: 14px; padding: 16px 19px; }.context-rail-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 15px; }.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.panel h2 { margin: 5px 0 7px; font-size: 18px; letter-spacing: -.035em; }.panel-description { margin: 0 0 14px; color: var(--ai-muted); font-size: 11px; line-height: 1.65; }.context-rail-note { color: #8f879f; font-size: 10px; }.context-chip-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 11px; }.context-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 8px; border: 1px solid #d8d2ec; border-radius: 5px; background: #faf9ff; color: #65558d; font-size: 10px; }.context-chip.empty { border-color: #ebc7c9; background: #fff8f8; color: #b05e64; }.ai-grid { display: grid; grid-template-columns: 285px minmax(0, 1fr) 258px; gap: 14px; align-items: start; }.prompt-panel, .signal-panel, .context-panel, .failure-panel, .healing-panel { padding: 19px; }.panel-index, .period-chip { color: #9a91ad; font-family: ui-monospace, monospace; font-size: 10px; }.generation-list { display: grid; gap: 7px; }.generation-card { display: flex; align-items: center; gap: 9px; width: 100%; min-height: 65px; padding: 10px; border: 1px solid #e8e5ed; border-radius: 8px; background: #faf9fb; color: var(--ai-ink); cursor: pointer; text-align: left; transition: border-color .16s ease, transform .16s ease, box-shadow .16s ease; }.generation-card:hover:not(:disabled), .generation-card:focus-visible:not(:disabled) { transform: translateX(2px); box-shadow: 0 7px 14px rgba(73, 59, 105, .08); }.generation-card:disabled { cursor: not-allowed; opacity: .47; }.generation-card-violet:hover:not(:disabled), .generation-card-violet:focus-visible:not(:disabled) { border-color: #ad9ae2; }.generation-card-blue:hover:not(:disabled), .generation-card-blue:focus-visible:not(:disabled) { border-color: #91bee5; }.generation-card-green:hover:not(:disabled), .generation-card-green:focus-visible:not(:disabled) { border-color: #8acdbd; }.generation-icon { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; width: 27px; height: 27px; border-radius: 6px; background: #eeeafd; color: var(--ai-violet); }.generation-card-blue .generation-icon { background: #eaf4fd; color: var(--ai-blue); }.generation-card-green .generation-icon { background: #e8f7f2; color: var(--ai-green); }.generation-copy { min-width: 0; flex: 1; }.generation-copy strong, .generation-copy small { display: block; }.generation-copy strong { font-size: 12px; }.generation-copy small { margin-top: 3px; color: var(--ai-muted); font-size: 10px; line-height: 1.4; }.generation-arrow { color: #aaa3b3; font-size: 11px; }.draft-note { display: flex; gap: 6px; margin-top: 14px; padding-top: 11px; border-top: 1px solid #efedf1; color: #7e738f; font-size: 10px; line-height: 1.5; }
.funnel-grid { display: grid; gap: 13px; margin-top: 20px; }.funnel-item-head { display: flex; justify-content: space-between; gap: 10px; color: var(--ai-muted); font-size: 11px; }.funnel-item-head strong { color: var(--ai-ink); font-family: ui-monospace, monospace; }.funnel-track { height: 8px; margin-top: 6px; overflow: hidden; border-radius: 4px; background: #f0eef3; }.funnel-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--ai-violet), #af96e7); }.funnel-item:nth-child(2) .funnel-track span { background: linear-gradient(90deg, var(--ai-blue), #9ed0f1); }.funnel-item:nth-child(3) .funnel-track span { background: linear-gradient(90deg, var(--ai-green), #94d8c7); }.restricted-panel { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 94px; margin-top: 18px; padding: 14px; border: 1px dashed #d9d4df; border-radius: 8px; background: #fbfafc; color: #938c9b; font-size: 11px; line-height: 1.5; text-align: center; }.hotspot-heading { display: flex; align-items: center; justify-content: space-between; margin-top: 22px; padding-top: 13px; border-top: 1px solid #efedf1; color: #61566f; font-size: 11px; font-weight: 750; }.hotspot-list { display: grid; gap: 2px; margin-top: 6px; }.hotspot-row { display: flex; align-items: center; gap: 9px; width: 100%; padding: 8px 2px; border: 0; border-bottom: 1px solid #f0eef1; background: transparent; color: var(--ai-ink); cursor: pointer; text-align: left; }.hotspot-row:hover, .hotspot-row:focus-visible { color: var(--ai-violet); }.hotspot-rank { display: inline-flex; align-items: center; justify-content: center; width: 21px; height: 21px; border-radius: 50%; background: #fff1e2; color: #b17a2b; font-family: ui-monospace, monospace; font-size: 10px; }.hotspot-copy { min-width: 0; flex: 1; }.hotspot-copy strong, .hotspot-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.hotspot-copy strong { font-size: 11px; }.hotspot-copy small { margin-top: 2px; color: var(--ai-muted); font-size: 9px; }
.model-state-dot { width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: #b6b1bc; }.state-ready { background: var(--ai-green); box-shadow: 0 0 0 4px rgba(69, 170, 150, .12); }.state-disabled, .state-unconfigured { background: var(--ai-red); }.state-unknown { background: var(--ai-amber); }.model-card { display: grid; gap: 5px; margin-top: 12px; padding: 13px; border: 1px solid #e4e1e9; border-radius: 8px; background: #fbfafc; }.model-card.model-ready { border-color: #b9dfd3; background: #f2fbf8; }.model-card.model-disabled, .model-card.model-unconfigured { border-color: #ecc8ca; background: #fff7f7; }.model-label { color: var(--ai-muted); font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }.model-card strong { font-size: 13px; }.model-card small { color: var(--ai-muted); font-size: 10px; line-height: 1.4; }.context-stat-list { display: grid; gap: 7px; margin-top: 15px; }.context-stat-list div { display: flex; justify-content: space-between; padding-bottom: 7px; border-bottom: 1px solid #f0eef1; color: var(--ai-muted); font-size: 10px; }.context-stat-list strong { color: var(--ai-ink); font-family: ui-monospace, monospace; }.context-action { padding-left: 0; margin-top: 8px; }.context-footnote { margin: 14px 0 0; color: #9993a2; font-size: 10px; line-height: 1.5; }
.lower-grid { display: grid; grid-template-columns: minmax(0, 1fr) 285px; gap: 14px; margin-top: 14px; }.failure-list { display: grid; gap: 4px; }.failure-row { display: flex; align-items: center; gap: 9px; min-width: 0; padding: 9px 0; border-bottom: 1px solid #f0eef1; }.failure-icon { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; width: 25px; height: 25px; border-radius: 6px; background: #fff1e2; color: var(--ai-amber); }.failure-copy { min-width: 135px; max-width: 220px; }.failure-copy strong, .failure-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.failure-copy strong { font-size: 11px; }.failure-copy small { margin-top: 2px; color: var(--ai-muted); font-size: 9px; }.failure-message { min-width: 0; flex: 1; overflow: hidden; color: #9993a2; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.healing-rate { display: flex; align-items: baseline; gap: 7px; margin-top: 12px; }.healing-rate strong { color: var(--ai-green); font-family: ui-monospace, monospace; font-size: 28px; }.healing-rate span { color: var(--ai-muted); font-size: 10px; }.healing-meter { height: 8px; margin-top: 11px; overflow: hidden; border-radius: 4px; background: #edf1ef; }.healing-meter span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--ai-green), #9bd4c6); }.healing-counts { display: flex; flex-wrap: wrap; gap: 8px 12px; margin-top: 10px; color: var(--ai-muted); font-size: 10px; }.healing-restricted { min-height: 115px; margin-top: 5px; }.period-chip { padding: 4px 7px; border: 1px solid #e6e1ec; border-radius: 4px; }.ai-workbench button:focus-visible, .ai-workbench .ant-btn:focus-visible { outline: 2px solid #8b72de; outline-offset: 2px; }
@media (max-width: 1180px) { .ai-grid { grid-template-columns: 250px minmax(0, 1fr); }.context-panel { grid-column: 1 / -1; }.context-panel .context-stat-list { grid-template-columns: repeat(3, 1fr); }.context-panel .context-footnote { max-width: 660px; } }
@media (max-width: 840px) { .ai-hero { display: block; }.hero-controls { width: auto; margin-top: 24px; }.hero-control-row { justify-content: flex-start; gap: 18px; }.signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.ai-grid, .lower-grid { grid-template-columns: 1fr; }.context-panel { grid-column: auto; }.failure-copy { min-width: 110px; max-width: 180px; } }
@media (max-width: 520px) { .ai-hero { padding: 24px 20px; }.ai-hero h1 { font-size: 26px; }.signal-grid { grid-template-columns: 1fr; }.context-rail-heading { display: block; }.context-rail-note { display: block; margin-top: 7px; }.context-panel .context-stat-list { grid-template-columns: 1fr; }.failure-message { display: none; }.failure-row { flex-wrap: wrap; }.failure-row .ant-btn { margin-left: 34px; } }
@media (prefers-reduced-motion: reduce) { .generation-card { transition: none; }.generation-card:hover:not(:disabled), .generation-card:focus-visible:not(:disabled) { transform: none; } }
</style>
