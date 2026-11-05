<template>
  <div class="page-shell ai-workbench">
    <header class="ai-toolbar">
      <div class="toolbar-left">
        <div class="toolbar-identity">
          <RobotOutlined class="toolbar-icon" />
          <div class="toolbar-copy">
            <span class="toolbar-name">{{ t('ai_workbench.title') }}</span>
            <span class="toolbar-subtitle">{{ t('ai_workbench.subtitle') }}</span>
          </div>
        </div>
        <div class="toolbar-project">
          <label class="sr-only">{{ t('ai_workbench.project_label') }}</label>
          <a-select
            v-model:value="projectSelectId"
            :options="projectOptions"
            allow-clear
            size="small"
            class="project-select-dropdown"
            :placeholder="t('ai_workbench.project_placeholder')"
            @change="handleProjectChange"
          />
          <span class="model-status">
            <span class="status-dot" :class="`state-${modelState}`" />
            <span>{{ modelStatusLabel }}</span>
          </span>
        </div>
      </div>

      <div class="toolbar-right">
        <a-button size="small" :loading="loading" @click="refreshWorkbench">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
        <a-button v-if="isAdmin" size="small" @click="openModelConfig">
          <SettingOutlined /> {{ t('ai_workbench.model_config') }}
        </a-button>
      </div>
    </header>

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
      <section class="stat-strip" :aria-label="t('ai_workbench.summary_aria')">
        <div class="stat-card">
          <span class="stat-label">{{ t('ai_workbench.signals.context_assets') }}</span>
          <strong class="stat-value">{{ contextAssetCount }}</strong>
          <span class="stat-note">{{ t('ai_workbench.signals.context_note', { datasets: datasets.length, mocks: mockRules.length }) }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">{{ t('ai_workbench.signals.generated_drafts') }}</span>
          <strong class="stat-value">{{ generatedDraftLabel }}</strong>
          <span class="stat-note">{{ generationNote }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">{{ t('ai_workbench.signals.coverage_gaps') }}</span>
          <strong class="stat-value">{{ coverageGapCount }}</strong>
          <span class="stat-note">{{ t('ai_workbench.signals.coverage_note') }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">{{ t('ai_workbench.signals.run_quality') }}</span>
          <strong class="stat-value">{{ passRate }}%</strong>
          <span class="stat-note">{{ t('ai_workbench.signals.run_quality_note', { count: overview?.total_runs ?? 0 }) }}</span>
        </div>
      </section>

      <section class="workbench-grid">
        <div class="workbench-main">
          <section class="panel generation-panel">
            <div class="panel-head">
              <h2>{{ t('ai_workbench.generation_title') }}</h2>
            </div>
            <div class="generation-list">
              <button
                type="button"
                class="generation-card"
                :disabled="!canGenerate || !firstModuleId"
                @click="openCaseGeneration"
              >
                <span class="generation-top">
                  <span class="generation-icon"><FileSearchOutlined /></span>
                  <ArrowRightOutlined class="generation-arrow" />
                </span>
                <strong>{{ t('ai_workbench.generate_cases') }}</strong>
                <small>{{ firstModuleId ? t('ai_workbench.generate_cases_hint') : t('ai_workbench.no_module_hint') }}</small>
              </button>
              <button type="button" class="generation-card" :disabled="!canGenerate" @click="openDatasetGeneration">
                <span class="generation-top">
                  <span class="generation-icon"><DatabaseOutlined /></span>
                  <ArrowRightOutlined class="generation-arrow" />
                </span>
                <strong>{{ t('ai_workbench.generate_dataset') }}</strong>
                <small>{{ t('ai_workbench.generate_dataset_hint') }}</small>
              </button>
              <button type="button" class="generation-card" :disabled="!canGenerate" @click="openMockGeneration">
                <span class="generation-top">
                  <span class="generation-icon"><BranchesOutlined /></span>
                  <ArrowRightOutlined class="generation-arrow" />
                </span>
                <strong>{{ t('ai_workbench.generate_mock') }}</strong>
                <small>{{ t('ai_workbench.generate_mock_hint') }}</small>
              </button>
            </div>
            <div class="context-meta">
              <span>{{ t('ai_workbench.dataset_chip', { count: datasets.length }) }}</span>
              <span>{{ t('ai_workbench.mock_chip', { count: mockRules.length }) }}</span>
              <span>{{ t('ai_workbench.module_chip', { count: flatModules.length }) }}</span>
            </div>
            <div class="draft-note"><CheckCircleOutlined /> {{ t('ai_workbench.draft_note') }}</div>
          </section>

          <section class="panel failure-panel">
            <div class="panel-head">
              <h2>{{ t('ai_workbench.diagnosis_title') }}</h2>
              <a-button type="link" size="small" class="panel-link" @click="openRuns">{{ t('ai_workbench.open_task_center') }} →</a-button>
            </div>
            <div v-if="failedTasks.length" class="failure-list">
              <div v-for="task in failedTasks.slice(0, 6)" :key="task.id" class="failure-row">
                <WarningOutlined class="failure-icon" />
                <div class="failure-copy">
                  <strong>{{ task.name }}</strong>
                  <small>{{ task.task_type }} · {{ formatTime(task.created_at) }}</small>
                </div>
                <span class="failure-message">{{ task.error_message || t('ai_workbench.failure_without_message') }}</span>
                <a-button size="small" @click="openTask(task)">{{ t('ai_workbench.open_diagnosis') }}</a-button>
              </div>
            </div>
            <a-empty v-else :description="t('ai_workbench.no_failures')" />
          </section>
        </div>

        <aside class="workbench-side">
          <section class="panel model-panel">
            <div class="panel-head">
              <h2>{{ t('ai_workbench.model_title') }}</h2>
              <span class="status-dot" :class="`state-${modelState}`" />
            </div>
            <div class="model-card">
              <span class="model-label">{{ t('ai_workbench.project_model') }}</span>
              <strong>{{ modelName }}</strong>
              <small>{{ modelDescription }}</small>
            </div>
            <a-button v-if="isAdmin" type="link" size="small" class="panel-link" @click="openModelConfig">{{ t('ai_workbench.manage_model') }} →</a-button>
            <p class="panel-footnote">{{ t('ai_workbench.model_scope_note') }}</p>
          </section>

          <section class="panel signal-panel">
            <div class="panel-head">
              <h2>{{ t('ai_workbench.signal_title') }}</h2>
              <span class="period-note">{{ t('ai_workbench.last_30_days') }}</span>
            </div>
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
              <a-button type="link" size="small" class="panel-link" @click="openRuns">{{ t('ai_workbench.view_runs') }} →</a-button>
            </div>
            <div v-if="failureTop.length" class="hotspot-list">
              <button v-for="item in failureTop.slice(0, 4)" :key="`${item.case_id}-${item.case_type}`" type="button" class="hotspot-row" @click="openCases">
                <span class="hotspot-rank">{{ item.failure_count }}</span>
                <span class="hotspot-copy"><strong>{{ item.case_name }}</strong><small>{{ item.case_type }}</small></span>
                <ArrowRightOutlined />
              </button>
            </div>
            <a-empty v-else :description="t('ai_workbench.no_hotspots')" />
          </section>

          <section class="panel healing-panel">
            <div class="panel-head">
              <h2>{{ t('ai_workbench.healing_title') }}</h2>
            </div>
            <template v-if="healingStats">
              <div class="healing-rate"><strong>{{ healingStats.adopted_rate }}%</strong><span>{{ t('ai_workbench.adopted_rate') }}</span></div>
              <div class="healing-meter"><span :style="{ width: `${Math.min(100, Math.max(0, healingStats.adopted_rate))}%` }" /></div>
              <div class="healing-counts">
                <span>{{ t('ai_workbench.adopted_count', { count: healingStats.adopted_count }) }}</span>
                <span>{{ t('ai_workbench.example_count', { count: healingStats.high_quality_example_count }) }}</span>
              </div>
              <div v-if="isAdmin" class="healing-links">
                <a-button type="link" size="small" class="panel-link" @click="openHealingStats">{{ t('ai_workbench.open_healing_stats') }} →</a-button>
                <a-button type="link" size="small" class="panel-link" @click="openHealingExamples">{{ t('ai_workbench.open_healing_examples') }} →</a-button>
              </div>
            </template>
            <div v-else class="restricted-panel">
              <LockOutlined />
              <span>{{ isAdmin ? t('ai_workbench.healing_unavailable') : t('ai_workbench.admin_signal_hint') }}</span>
            </div>
          </section>
        </aside>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowRightOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  LockOutlined,
  ReloadOutlined,
  RobotOutlined,
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

function openHealingExamples() {
  void router.push('/system/healing-examples')
}

onMounted(() => { void loadProjects() })
</script>

<style scoped>
.ai-workbench {
  color: var(--c-text);
}

/* 工具栏 */
.ai-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  padding: 12px 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.toolbar-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  min-width: 0;
  flex: 1;
}

.toolbar-identity {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-icon {
  padding: 7px;
  font-size: 17px;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: var(--radius-sm);
}

.toolbar-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.toolbar-name {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--c-text);
}

.toolbar-subtitle {
  max-width: 560px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--c-text-tertiary);
}

.toolbar-project {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.project-select-dropdown {
  width: 200px;
}

.model-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-secondary);
  white-space: nowrap;
}

.status-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-text-tertiary);
}

.status-dot.state-ready {
  background: var(--c-success);
}

.status-dot.state-disabled,
.status-dot.state-unconfigured {
  background: var(--c-error);
}

.status-dot.state-unknown {
  background: var(--c-warning);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
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

.readonly-alert,
.load-alert {
  margin: 0 0 var(--space-3);
}

.project-empty {
  margin: 60px 0;
}

/* 指标带 */
.stat-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.stat-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-secondary);
}

.stat-value {
  display: block;
  margin-top: 8px;
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--c-text);
}

.stat-note {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}

/* 双栏工作区 */
.workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: var(--space-3);
  align-items: start;
}

.workbench-main,
.workbench-side {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}

.panel {
  min-width: 0;
  padding: 18px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--c-text);
}

.panel-link {
  height: auto;
  padding: 0;
  font-size: 12px;
}

.panel-footnote {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-text-tertiary);
}

.period-note {
  font-size: 12px;
  color: var(--c-text-tertiary);
  white-space: nowrap;
}

/* 生成通道 */
.generation-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}

.generation-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 112px;
  padding: 14px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.generation-card:hover:not(:disabled),
.generation-card:focus-visible:not(:disabled) {
  border-color: var(--c-primary);
  box-shadow: var(--shadow-xs);
}

.generation-card:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.generation-card:focus-visible,
.hotspot-row:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

.generation-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.generation-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  font-size: 15px;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: var(--radius-sm);
}

.generation-arrow {
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.generation-card strong {
  font-size: 13px;
  font-weight: 600;
}

.generation-card small {
  font-size: 12px;
  line-height: 1.5;
  color: var(--c-text-tertiary);
}

.context-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border-subtle);
  font-size: 12px;
  color: var(--c-text-secondary);
}

.draft-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--c-text-tertiary);
}

.draft-note .anticon {
  margin-top: 2px;
  color: var(--c-success);
}

/* 信号面板 */
.funnel-grid {
  display: grid;
  gap: 12px;
}

.funnel-item-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: var(--c-text-secondary);
}

.funnel-item-head strong {
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-weight: 600;
  color: var(--c-text);
}

.funnel-track {
  height: 6px;
  margin-top: 6px;
  overflow: hidden;
  background: var(--c-bg-muted);
  border-radius: 999px;
}

.funnel-track span {
  display: block;
  height: 100%;
  background: var(--c-primary);
  border-radius: inherit;
  transition: width 0.3s ease;
}

.restricted-panel {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--c-bg-subtle);
  border: 1px dashed var(--c-border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  line-height: 1.5;
  color: var(--c-text-secondary);
}

.restricted-panel .anticon {
  flex: none;
  color: var(--c-text-tertiary);
}

.hotspot-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 16px 0 8px;
  padding-top: 14px;
  border-top: 1px solid var(--c-border-subtle);
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
}

.hotspot-list {
  display: grid;
  gap: 6px;
}

.hotspot-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease;
}

.hotspot-row:hover,
.hotspot-row:focus-visible {
  border-color: var(--c-border-strong);
  background: var(--c-bg-elevated);
}

.hotspot-rank {
  flex: none;
  min-width: 20px;
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  color: var(--c-text-secondary);
}

.hotspot-copy {
  flex: 1;
  min-width: 0;
}

.hotspot-copy strong,
.hotspot-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-copy strong {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text);
}

.hotspot-copy small {
  margin-top: 1px;
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.hotspot-row > .anticon {
  flex: none;
  font-size: 11px;
  color: var(--c-text-tertiary);
}

/* 项目模型 */
.model-card {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
}

.model-label {
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.model-card strong {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  overflow-wrap: anywhere;
}

.model-card small {
  font-size: 12px;
  color: var(--c-text-secondary);
  overflow-wrap: anywhere;
}

.model-panel .panel-link {
  margin-top: 10px;
}

/* 失败诊断 */
.failure-list {
  display: grid;
}

.failure-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 10px 0;
  border-bottom: 1px solid var(--c-border-subtle);
}

.failure-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.failure-icon {
  flex: none;
  font-size: 14px;
  color: var(--c-warning);
}

.failure-copy {
  flex: 0 1 230px;
  min-width: 0;
}

.failure-copy strong,
.failure-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.failure-copy strong {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
}

.failure-copy small {
  margin-top: 2px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.failure-message {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  color: var(--c-text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.failure-row .ant-btn {
  flex: none;
}

/* 自愈反馈 */
.healing-rate {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.healing-rate strong {
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--c-text);
}

.healing-rate span {
  font-size: 12px;
  color: var(--c-text-secondary);
}

.healing-meter {
  height: 6px;
  margin-top: 10px;
  overflow: hidden;
  background: var(--c-bg-muted);
  border-radius: 999px;
}

.healing-meter span {
  display: block;
  height: 100%;
  background: var(--c-success);
  border-radius: inherit;
  transition: width 0.3s ease;
}

.healing-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.healing-links {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 10px;
}

/* 响应式 */
@media (max-width: 1180px) {
  .workbench-grid {
    grid-template-columns: minmax(0, 1fr) 280px;
  }
}

@media (max-width: 1024px) {
  .workbench-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 840px) {
  .stat-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .toolbar-right {
    margin-left: auto;
  }
}

@media (max-width: 640px) {
  .failure-message {
    display: none;
  }
  .failure-row {
    flex-wrap: wrap;
  }
  .failure-copy {
    flex: 1 1 auto;
  }
}

@media (max-width: 520px) {
  .stat-strip {
    grid-template-columns: minmax(0, 1fr);
  }
  .project-select-dropdown {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .generation-card,
  .hotspot-row,
  .funnel-track span,
  .healing-meter span {
    transition: none;
  }
}
</style>
