<template>
  <div class="page-shell hermes-page">
    <header class="hermes-toolbar">
      <div class="toolbar-left">
        <div class="toolbar-identity">
          <RobotOutlined class="toolbar-icon" />
          <span class="toolbar-name">Hermes 智能助手</span>
        </div>
        <div class="toolbar-sep">/</div>
        <div class="toolbar-project">
          <label for="hermes-project" class="sr-only">{{ t('hermes.project_label') }}</label>
          <a-select
            id="hermes-project"
            v-model:value="projectSelectId"
            :options="projectOptions"
            allow-clear
            size="small"
            class="project-select-dropdown"
            :placeholder="t('hermes.project_placeholder')"
            @change="handleProjectChange"
          />
        </div>
        <div v-if="selectedProjectId" class="toolbar-chips">
          <span class="toolbar-chip"><b>{{ moduleCount }}</b> 模块</span>
          <span class="toolbar-chip"><b>{{ cases.length }}</b> 用例</span>
          <span class="toolbar-chip chip-fail"><b>{{ failedTasks.length }}</b> 失败任务</span>
        </div>
      </div>

      <div class="toolbar-right">
        <a-button size="small" :loading="loading" class="toolbar-btn" @click="refreshWorkbench">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
        <a-button v-if="selectedProjectId" type="primary" size="small" class="toolbar-btn primary-btn" @click="resetConversation">
          + 新会话
        </a-button>
      </div>
    </header>

    <a-alert
      v-if="loadError"
      class="load-alert"
      type="warning"
      show-icon
      :message="t('hermes.load_warning')"
      :description="loadError"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('hermes.select_project_hint')" />

    <template v-else>

      <HermesGovernancePanel v-if="governanceSummary" :summary="governanceSummary" />

      <HermesConversationContextPanel
        v-model:source-types="sourceTypes"
        v-model:date-range="dateRange"
        v-model:context-budget="contextBudget"
        :short-conversation-id="shortConversationId"
        :source-type-options="sourceTypeOptions"
        :context-budget-options="contextBudgetOptions"
        :history-used="historyUsed"
        :history-omitted="historyOmitted"
        :context-chars="contextChars"
        @new-conversation="startNewConversation"
      />

      <div class="assistant-layout">
        <HermesConversationPanel
          v-model:input-text="inputText"
          :messages="messages"
          :prompt-options="promptOptions"
          :task-names="failedTaskNames"
          :loading="loading"
          :diagnosing="diagnosing"
          :querying="querying"
          @select-task="selectFailureTask"
          @open-source="openSource"
          @rate-message="rateMessage"
          @ask-prompt="askPrompt"
          @submit="submitPrompt"
        />

        <HermesEvidencePanel
          :quality-score="qualityScore"
          :pass-rate="passRate"
          :total-runs="totalRuns"
          :coverage-rate="coverageRate"
          :open-defects="openDefects"
          :failed-tasks="failedTasks"
          :selected-task-id="selectedTaskId"
          :diagnosing="diagnosing"
          @ask-quality="askPrompt('quality')"
          @select-task="selectFailureTask"
          @explain-failure="explainFailure"
          @open-task-center="openTaskCenter"
          @open-runs="openRuns"
        />
      </div>

      <HermesDiagnosisPanel v-if="diagnosis" :diagnosis="diagnosis" @open-task="openTaskById" />

      <HermesPlanDraftPanel
        v-model:draft="planDraft"
        :saving="savingDraft"
        :confirmed="draftConfirmed"
        :changed-count="draftChangedCount"
        :selected-module-count="selectedDraftModuleCount"
        :selected-case-count="selectedDraftCaseCount"
        :selected-regression-count="selectedDraftRegressionCount"
        :failed-task-count="failedTasks.length"
        :diff-rows="planDraftDiffRows"
        @save="savePlanDraft"
        @confirm="confirmPlanDraft"
        @add-point="addPlanPoint"
        @remove-point="removePlanPoint"
        @open-path="openPath"
        @open-source="openSource"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  ReloadOutlined,
  RobotOutlined,
} from '@ant-design/icons-vue'
import {
  caseApi,
  hermesApi,
  projectApi,
  reportApi,
  runApi,
  statisticsApi,
  workbenchApi,
  type HermesGovernanceSummary,
  type HermesOrchestrationResult,
  type HermesSourceType,
  type HermesQueryResult,
  type ModuleTreeItem,
  type ProjectItem,
  type WorkbenchTaskItem,
  type ReportOverviewItem,
} from '@/api'
import type { Dayjs } from 'dayjs'
import HermesConversationContextPanel from './components/HermesConversationContextPanel.vue'
import HermesConversationPanel from './components/HermesConversationPanel.vue'
import HermesDiagnosisPanel from './components/HermesDiagnosisPanel.vue'
import HermesEvidencePanel from './components/HermesEvidencePanel.vue'
import HermesGovernancePanel from './components/HermesGovernancePanel.vue'
import HermesPlanDraftPanel from './components/HermesPlanDraftPanel.vue'
import type {
  HermesDiagnosis,
  HermesMessage,
  HermesPromptKey as PromptKey,
  HermesSource,
} from './components/hermesPanelTypes'
import {
  useHermesPlanDraft,
  type DraftCase,
  type DraftModule,
  type DraftRegressionItem,
  type PlanDraft,
} from './composables/useHermesPlanDraft'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const modules = ref<ModuleTreeItem[]>([])
const cases = ref<Array<{ id?: number; name?: string; automation_status?: string | null }>>([])
const failedTasks = ref<WorkbenchTaskItem[]>([])
const reportOverview = ref<ReportOverviewItem | null>(null)
const failureHotspots = ref<Array<{ case_name: string; failure_count: number }>>([])
const governanceSummary = ref<HermesGovernanceSummary | null>(null)
const messages = ref<HermesMessage[]>([])
const sessionId = ref<number | null>(null)
const savingDraft = ref(false)
const inputText = ref('')
const selectedTaskId = ref<string | null>(null)
const diagnosis = ref<HermesDiagnosis | null>(null)
const planDraft = ref<PlanDraft | null>(null)
const draftConfirmed = ref(false)
const loading = ref(false)
const diagnosing = ref(false)
const querying = ref(false)
const loadError = ref('')
const conversationId = ref('')
const sourceTypes = ref<HermesSourceType[]>([])
const dateRange = ref<[Dayjs, Dayjs] | undefined>(undefined)
const contextBudget = ref(6_000)
const historyUsed = ref(0)
const historyOmitted = ref(0)
const contextChars = ref(0)
const {
  selectedModuleCount: selectedDraftModuleCount,
  selectedCaseCount: selectedDraftCaseCount,
  selectedRegressionCount: selectedDraftRegressionCount,
  diffRows: planDraftDiffRows,
  changedCount: draftChangedCount,
  addPoint: addPlanPoint,
  removePoint: removePlanPoint,
  buildHandoff: buildPlanDraftHandoff,
} = useHermesPlanDraft(planDraft)
let loadSequence = 0
let projectsSequence = 0
let messageSequence = 0
let querySequence = 0

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const moduleCount = computed(() => flattenModules(modules.value).length)
const totalRuns = computed(() => reportOverview.value?.total_runs ?? 0)
const passRate = computed(() => Math.round(Number(reportOverview.value?.pass_rate ?? 0)))
const qualityScore = computed(() => Math.round(Number(reportOverview.value?.quality_score ?? passRate.value)))
const coverageRate = computed(() => Math.round(Number(reportOverview.value?.coverage_rate ?? 0)))
const openDefects = computed(() => reportOverview.value?.open_defects ?? 0)
const failedTaskNames = computed(() => Object.fromEntries(failedTasks.value.map((task) => [task.id, task.name])))
const promptOptions = computed(() => [
  { key: 'failed_tasks' as const, mark: '!', title: t('hermes.prompts.failed_tasks'), description: t('hermes.prompts.failed_tasks_hint') },
  { key: 'explain_failure' as const, mark: '?', title: t('hermes.prompts.explain_failure'), description: t('hermes.prompts.explain_failure_hint') },
  { key: 'test_plan' as const, mark: '+', title: t('hermes.prompts.test_plan'), description: t('hermes.prompts.test_plan_hint') },
  { key: 'quality' as const, mark: '%', title: t('hermes.prompts.quality'), description: t('hermes.prompts.quality_hint') },
])
const sourceTypeOptions = computed(() => [
  { label: t('hermes.source_types.knowledge'), value: 'knowledge' as const },
  { label: t('hermes.source_types.requirement'), value: 'requirement' as const },
  { label: t('hermes.source_types.case'), value: 'case' as const },
])
const contextBudgetOptions = computed(() => [
  { label: t('hermes.context_budget_option', { chars: 4_000 }), value: 4_000 },
  { label: t('hermes.context_budget_option', { chars: 6_000 }), value: 6_000 },
  { label: t('hermes.context_budget_option', { chars: 8_000 }), value: 8_000 },
  { label: t('hermes.context_budget_option', { chars: 12_000 }), value: 12_000 },
])
const shortConversationId = computed(() => conversationId.value.slice(-8) || '—')

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(items: ModuleTreeItem[]): ModuleTreeItem[] {
  return items.flatMap((item) => [item, ...flattenModules(item.children || [])])
}

function newConversationId() {
  const randomPart = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `hermes-${selectedProjectId.value || 'none'}-${randomPart}`
}

function isConversationId(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9._:-]{8,80}$/.test(value)
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const response = (error as { response?: { data?: { detail?: unknown } }; message?: unknown }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
    if (typeof (error as { message?: unknown }).message === 'string') return String((error as { message: string }).message)
  }
  return error instanceof Error ? error.message : fallback
}

function source(label: string, path: string): HermesSource {
  const projectId = selectedProjectId.value
  const separator = path.includes('?') ? '&' : '?'
  return { label, path: projectId ? `${path}${separator}project_id=${projectId}` : path }
}

function resetConversation() {
  querySequence += 1
  querying.value = false
  conversationId.value = newConversationId()
  historyUsed.value = 0
  historyOmitted.value = 0
  contextChars.value = 0
  messages.value = [{
    id: ++messageSequence,
    role: 'assistant',
    text: t('hermes.welcome', { project: selectedProjectName.value }),
    createdAt: new Date().toISOString(),
    sources: [source(t('hermes.source_reports'), '/reports'), source(t('hermes.source_tasks'), '/tasks')],
    isWelcome: true,
  }]
}

function startNewConversation() {
  sessionId.value = null
  resetConversation()
}

function clearProjectData() {
  modules.value = []
  cases.value = []
  failedTasks.value = []
  reportOverview.value = null
  failureHotspots.value = []
  selectedTaskId.value = null
  diagnosis.value = null
  planDraft.value = null
  governanceSummary.value = null
  sessionId.value = null
  draftConfirmed.value = false
  resetConversation()
}

function syncRoute() {
  void router.replace({ query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

async function loadProjectData() {
  const projectId = selectedProjectId.value
  const sequence = ++loadSequence
  loadError.value = ''
  clearProjectData()
  if (!projectId) {
    loading.value = false
    return
  }
  loading.value = true
  const results = await Promise.allSettled([
    projectApi.getModules(projectId),
    caseApi.list({ project_id: projectId }),
    workbenchApi.tasks({ project_id: projectId, limit: 100 }),
    reportApi.overview({ project_id: projectId, days: 30, recent_limit: 20 }),
    statisticsApi.failureTop({ project_id: projectId, days: 30, top: 8 }),
  ])
  if (sequence !== loadSequence) return
  const failures: string[] = []
  const [moduleResult, caseResult, taskResult, reportResult, hotspotResult] = results
  if (moduleResult.status === 'fulfilled') modules.value = moduleResult.value
  else failures.push(t('hermes.load_modules_failed'))
  if (caseResult.status === 'fulfilled') cases.value = caseResult.value
  else failures.push(t('hermes.load_cases_failed'))
  if (taskResult.status === 'fulfilled') {
    failedTasks.value = taskResult.value.items.filter((item) => ['failed', 'error'].includes(item.status))
  } else failures.push(t('hermes.load_tasks_failed'))
  if (reportResult.status === 'fulfilled') reportOverview.value = reportResult.value
  else failures.push(t('hermes.load_report_failed'))
  if (hotspotResult.status === 'fulfilled') failureHotspots.value = hotspotResult.value
  else failures.push(t('hermes.load_hotspots_failed'))
  if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
    failedTasks.value = [
      {
        id: 'task-101',
        name: 'PJX110 手机端冷启动测试',
        detail_path: '/mobile-special/reports/101',
        status: 'failed',
        error_message: 'Cold start duration exceeded limit: 2450ms > 1800ms',
        created_at: '2026-09-07T14:30:00Z',
      } as unknown as WorkbenchTaskItem,
      {
        id: 'task-102',
        name: 'MIX 3 短信验证码识别回放',
        detail_path: '/mobile-special/reports/102',
        status: 'error',
        error_message: 'ADB connection timeout while waiting for UIAutomator dump',
        created_at: '2026-09-07T14:40:00Z',
      } as unknown as WorkbenchTaskItem,
    ]
    reportOverview.value = {
      days: 30,
      total_cases: 120,
      executed_cases: 110,
      passed_runs: 118,
      failed_runs: 8,
      error_runs: 2,
      total_runs: 128,
      pass_rate: 92,
      quality_score: 88,
      coverage_rate: 85,
      open_defects: 3,
      recent_runs: [],
    } as unknown as ReportOverviewItem
    modules.value = [
      { id: 1, name: '用户与登录模块', children: [] } as unknown as (typeof modules.value)[number],
      { id: 2, name: '设备自动化管理', children: [] } as unknown as (typeof modules.value)[number],
    ]
    cases.value = [
      { id: 1, name: '用户冷启动正常进入主界面' } as unknown as (typeof cases.value)[number],
      { id: 2, name: '设备拔插重连与状态同步' } as unknown as (typeof cases.value)[number],
    ]
    loadError.value = ''
  } else {
    loadError.value = failures.join('；')
  }
  resetConversation()
  try {
    const sessions = await hermesApi.sessions(projectId)
    if (sequence !== loadSequence || selectedProjectId.value !== projectId) return
    const latest = sessions[0]
    if (latest) {
      sessionId.value = latest.id
      const storedConversationId = latest.context_filters?.conversation_id
      if (isConversationId(storedConversationId)) conversationId.value = storedConversationId
      const restored = latest.messages
        .map((item, index): HermesMessage | null => {
          const role = item.role === 'assistant' ? 'assistant' : item.role === 'user' ? 'user' : null
          if (!role || typeof item.content !== 'string') return null
          const storedSources = Array.isArray(item.sources) ? item.sources : []
          return {
            id: ++messageSequence,
            role,
            text: item.content,
            createdAt: typeof item.at === 'string' ? item.at : latest.updated_at,
            sources: storedSources.map((entry) => {
              const sourceItem = entry as Record<string, unknown>
              return { label: String(sourceItem.source_ref || sourceItem.title || sourceItem.source_type || 'source'), path: String(sourceItem.path || '/') }
            }),
            mode: item.mode as HermesQueryResult['mode'] | undefined,
            toolSteps: Array.isArray(item.tool_steps)
              ? item.tool_steps
                .filter((step): step is Record<string, unknown> => typeof step === 'object' && step !== null)
                .map((step) => ({ tool: String(step.tool || ''), status: String(step.status || '') }))
                .filter((step) => step.tool && step.status)
              : undefined,
            backendIndex: role === 'assistant' && !['orchestration_clarification', 'orchestration_cancellation'].includes(String(item.kind))
              ? index
              : undefined,
          }
        })
        .filter((item): item is HermesMessage => item !== null)
      if (restored.length) messages.value = restored
    }
  } catch {
    failures.push(t('hermes.load_sessions_failed'))
  }
  if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA !== 'true') {
    loadError.value = failures.join('；')
  }
  loading.value = false
  await loadGovernance(projectId)
}

async function loadGovernance(projectId: number) {
  const sequence = loadSequence
  try {
    const summary = await hermesApi.governance(projectId)
    if (sequence === loadSequence && selectedProjectId.value === projectId) governanceSummary.value = summary
  } catch {
    if (sequence === loadSequence && selectedProjectId.value === projectId) governanceSummary.value = null
  }
}

async function loadProjects() {
  const sequence = ++projectsSequence
  loading.value = true
  try {
    const nextProjects = await projectApi.list()
    if (sequence !== projectsSequence) return
    projects.value = nextProjects
    if (!selectedProjectId.value || !projects.value.some((project) => project.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
      syncRoute()
    }
    await loadProjectData()
  } catch (error) {
    if (sequence === projectsSequence) {
      if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
        projects.value = [
          { id: 1, name: 'LexGuard Mobile Clean', description: '移动端核心测试项目' } as unknown as (typeof projects.value)[number],
          { id: 2, name: 'ATP 移动端核心业务', description: 'ATP 核心自动化业务' } as unknown as (typeof projects.value)[number],
        ]
        selectedProjectId.value = 1
        projectSelectId.value = 1
        await loadProjectData()
        loading.value = false
        return
      }
      loadError.value = errorMessage(error, t('hermes.load_projects_failed'))
      loading.value = false
    }
  }
}

async function handleProjectChange(value?: unknown) {
  selectedProjectId.value = positiveInt(value)
  syncRoute()
  await loadProjectData()
}

async function refreshWorkbench() {
  await loadProjectData()
}

function appendMessage(
  role: HermesMessage['role'],
  text: string,
  sources?: HermesSource[],
  taskIds?: string[],
  mode?: HermesQueryResult['mode'],
  toolSteps?: Array<{ tool: string; status: string }>,
) {
  messages.value.push({
    id: ++messageSequence,
    role,
    text,
    createdAt: new Date().toISOString(),
    sources,
    taskIds,
    mode,
    toolSteps,
    isWelcome: false,
  })
}
function conversationHistory() {
  return messages.value
    .filter((message) => !message.isWelcome && message.text.trim())
    .slice(-12)
    .map((message) => ({ role: message.role, content: message.text }))
}

function selectedFailureTask() {
  return failedTasks.value.find((task) => task.id === selectedTaskId.value) || failedTasks.value[0]
}

function selectFailureTask(taskId: string) {
  selectedTaskId.value = taskId
}

function openSource(item: HermesSource) {
  openPath(item.path)
}

function openPath(path: string) {
  void router.push(path)
}

function openTaskById(taskId: string) {
  const task = failedTasks.value.find((item) => item.id === taskId)
  if (task) void router.push(task.detail_path)
}

function openTaskCenter() {
  void router.push(source(t('hermes.source_tasks'), '/tasks').path)
}

function openRuns() {
  void router.push(source(t('hermes.source_runs'), '/runs').path)
}

function openPlans() {
  if (planDraft.value && !draftConfirmed.value) return
  if (planDraft.value && selectedProjectId.value) {
    const handoff = buildPlanDraftHandoff(selectedProjectId.value)
    if (!handoff) return
    void router.push({
      path: '/plans',
      query: { project_id: String(selectedProjectId.value), hermes_draft: '1' },
      state: { hermesPlanDraft: handoff },
    })
    return
  }
  void router.push(source(t('hermes.source_plans'), '/plans').path)
}

function confirmPlanDraft() {
  if (!planDraft.value) return
  draftConfirmed.value = true
  appendMessage('assistant', t('hermes.answers.plan_confirmed'), planDraft.value.sources)
  openPlans()
}

async function queryHermes(text: string, history = conversationHistory()) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  const requestConversationId = conversationId.value
  const requestSequence = ++querySequence
  querying.value = true
  try {
    const range = dateRange.value
    const result = await hermesApi.query({
      project_id: projectId,
      query: text,
      limit: 8,
      conversation_id: requestConversationId,
      history,
      source_types: [...sourceTypes.value],
      updated_from: range?.[0]?.format('YYYY-MM-DD'),
      updated_to: range?.[1]?.format('YYYY-MM-DD'),
      context_budget: contextBudget.value,
      session_id: sessionId.value ?? undefined,
    })
    if (
      querySequence !== requestSequence
      || selectedProjectId.value !== projectId
      || conversationId.value !== requestConversationId
    ) return
    sessionId.value = result.session_id
    conversationId.value = result.conversation_id
    historyUsed.value = result.history_used
    historyOmitted.value = result.history_omitted
    contextChars.value = result.context_chars
    const sources = result.sources.map((item) => ({
      label: [item.source_ref || item.source_type, item.title].join(' · '),
      path: item.path,
    }))
    appendMessage('assistant', result.answer, sources, undefined, result.mode)
    messages.value[messages.value.length - 1].backendIndex = result.message_index
  } catch (error) {
    if (
      querySequence !== requestSequence
      || selectedProjectId.value !== projectId
      || conversationId.value !== requestConversationId
    ) return
    appendMessage('assistant', t('hermes.query_failed', { error: errorMessage(error, t('hermes.query_unavailable')) }))
  } finally {
    if (querySequence === requestSequence) querying.value = false
  }
}

async function orchestratePrompt(text: string): Promise<boolean> {
  const projectId = selectedProjectId.value
  if (!projectId) return false
  const requestConversationId = conversationId.value
  const requestSequence = ++querySequence
  querying.value = true
  try {
    const result: HermesOrchestrationResult = await hermesApi.orchestrate({
      project_id: projectId,
      query: text,
      conversation_id: requestConversationId,
      session_id: sessionId.value ?? undefined,
    })
    if (
      querySequence !== requestSequence
      || selectedProjectId.value !== projectId
      || conversationId.value !== requestConversationId
    ) return true
    if (result.status === 'no_match') return false
    if (result.status === 'needs_input') {
      sessionId.value = result.session_id ?? sessionId.value
      appendMessage('assistant', result.clarification || result.answer)
      return true
    }
    if (result.status === 'cancelled') {
      sessionId.value = result.session_id ?? sessionId.value
      appendMessage('assistant', result.answer)
      return true
    }
    sessionId.value = result.session_id ?? sessionId.value
    const sources = result.steps.flatMap((step) => step.evidence.map((item) => ({
      label: [item.source_ref, item.title].filter(Boolean).join(' · '),
      path: item.path,
    })))
    appendMessage(
      'assistant',
      result.answer,
      sources,
      undefined,
      undefined,
      result.steps.map((step) => ({ tool: step.tool, status: step.status })),
    )
    messages.value[messages.value.length - 1].backendIndex = result.message_index ?? undefined
    return true
  } catch {
    if (
      querySequence !== requestSequence
      || selectedProjectId.value !== projectId
      || conversationId.value !== requestConversationId
    ) return true
    return false
  } finally {
    if (querySequence === requestSequence) querying.value = false
  }
}

async function rateMessage(item: HermesMessage, rating: 'helpful' | 'not_helpful') {
  if (!sessionId.value || item.backendIndex == null || !selectedProjectId.value) return
  await hermesApi.feedback(sessionId.value, { project_id: selectedProjectId.value, message_index: item.backendIndex, rating })
  message.success(t('hermes.feedback_saved'))
}

async function savePlanDraft() {
  if (!selectedProjectId.value || !planDraft.value) return
  savingDraft.value = true
  try {
    const currentSessionId = sessionId.value ?? (await hermesApi.createSession(selectedProjectId.value, t('hermes.conversation_title'))).id
    sessionId.value = currentSessionId
    const draft = await hermesApi.createDraft(currentSessionId, {
      project_id: selectedProjectId.value,
      draft_type: 'test_plan',
      payload: planDraft.value,
      sources: planDraft.value.sources.map((item) => ({ path: item.path })),
    })
    Modal.confirm({
      title: t('hermes.confirm_draft_title'),
      content: t('hermes.confirm_draft_content'),
      async onOk() {
        const result = await hermesApi.confirmDraft(currentSessionId, { project_id: selectedProjectId.value!, draft_id: draft.id, confirmation: 'CONFIRM' })
        draftConfirmed.value = true
        message.success(t('hermes.draft_saved', { id: result.plan_id }))
      },
    })
  } finally {
    savingDraft.value = false
  }
}

function buildFailedTaskAnswer() {
  if (!failedTasks.value.length) {
    appendMessage('assistant', t('hermes.answers.no_failed_tasks'), [source(t('hermes.source_runs'), '/runs')])
    return
  }
  appendMessage(
    'assistant',
    t('hermes.answers.failed_tasks', { count: failedTasks.value.length }),
    [source(t('hermes.source_tasks'), '/tasks'), source(t('hermes.source_reports'), '/reports')],
    failedTasks.value.slice(0, 5).map((task) => task.id),
  )
}

function buildQualityAnswer() {
  const hotspots = failureHotspots.value.slice(0, 3).map((item) => `${item.case_name}（${item.failure_count}）`).join('、')
  appendMessage(
    'assistant',
    t('hermes.answers.quality', {
      score: qualityScore.value,
      passRate: passRate.value,
      runs: totalRuns.value,
      hotspots: hotspots || t('hermes.answers.no_hotspots'),
    }),
    [source(t('hermes.source_reports'), '/reports'), source(t('hermes.source_statistics'), '/dashboard')],
  )
}

function buildPlanDraft() {
  const moduleDrafts: DraftModule[] = flattenModules(modules.value).slice(0, 8).map((item) => ({
    id: item.id,
    name: item.name,
    selected: true,
    path: source(t('hermes.source_cases'), `/cases?module_id=${item.id}`).path,
  }))
  const caseDrafts: DraftCase[] = cases.value
    .map((item) => ({ id: positiveInt(item.id), name: item.name || '' }))
    .filter((item): item is { id: number; name: string } => item.id !== null)
    .slice(0, 8)
    .map((item) => ({
      id: item.id,
      title: item.name,
      expected: t('hermes.case_draft_expected', { name: item.name }),
      selected: true,
      path: source(t('hermes.source_cases'), `/cases?case_id=${item.id}`).path,
    }))
  const regressionScope: DraftRegressionItem[] = failedTasks.value.slice(0, 8).map((item) => ({
    taskId: item.id,
    name: item.name,
    reason: item.error_message || t('hermes.plan_regression_default_reason'),
    selected: true,
    path: item.detail_path,
  }))
  const moduleNames = moduleDrafts.filter((item) => item.selected).map((item) => item.name)
  const pointSeed = moduleNames.length
    ? moduleNames.map((name) => t('hermes.plan_point_module', { name }))
    : [t('hermes.default_plan_point')]
  const sources = [
    source(t('hermes.source_cases'), '/cases'),
    source(t('hermes.source_tasks'), '/tasks'),
    source(t('hermes.source_reports'), '/reports'),
    source(t('hermes.source_statistics'), '/dashboard'),
  ]
  const draft: PlanDraft = {
    name: t('hermes.plan_default_name', { project: selectedProjectName.value }),
    objective: t('hermes.plan_default_objective', { cases: cases.value.length, passRate: passRate.value }),
    testPoints: [...pointSeed, t('hermes.plan_point_failure', { count: failedTasks.value.length })],
    scopeModules: moduleDrafts,
    caseDrafts,
    regressionScope,
    sources,
    baseline: {
      name: t('hermes.plan_default_name', { project: selectedProjectName.value }),
      objective: t('hermes.plan_default_objective', { cases: cases.value.length, passRate: passRate.value }),
      testPoints: [...pointSeed, t('hermes.plan_point_failure', { count: failedTasks.value.length })],
      moduleNames,
      caseTitles: caseDrafts.filter((item) => item.selected).map((item) => item.title),
      regressionTaskIds: regressionScope.filter((item) => item.selected).map((item) => item.taskId),
      regressionTaskNames: regressionScope.filter((item) => item.selected).map((item) => item.name),
    },
  }
  planDraft.value = draft
  draftConfirmed.value = false
  appendMessage('assistant', t('hermes.answers.plan', { count: pointSeed.length }), [...sources, source(t('hermes.source_plans'), '/plans')])
}

async function explainFailure(task?: WorkbenchTaskItem) {
  const target = task || selectedFailureTask()
  if (!target) {
    appendMessage('assistant', t('hermes.answers.no_failed_tasks'))
    return
  }
  selectedTaskId.value = target.id
  appendMessage('user', t('hermes.user_explain', { name: target.name }))
  diagnosing.value = true
  try {
    const result = target.task_type === 'case'
      ? await runApi.generateFailureDiagnosis(target.run_id)
      : await workbenchApi.failureDiagnosis(target.task_type, target.run_id)
    diagnosis.value = { taskId: target.id, result }
    appendMessage('assistant', t('hermes.answers.diagnosis', { name: target.name, status: result.status }), [source(t('hermes.source_run_detail'), target.detail_path)])
  } catch (error) {
    appendMessage('assistant', t('hermes.answers.diagnosis_failed', { error: errorMessage(error, t('hermes.diagnosis_failed')) }), [source(t('hermes.source_run_detail'), target.detail_path)])
  } finally {
    diagnosing.value = false
  }
}

function intentFor(text: string): PromptKey | null {
  const value = text.toLowerCase()
  if (/计划|plan|回归|测试范围/.test(value)) return 'test_plan'
  if (/解释|原因|诊断|error|错误|失败原因/.test(value)) return 'explain_failure'
  if (/质量|通过率|指标|quality|分数/.test(value)) return 'quality'
  if (/失败|任务|异常|failed|task/.test(value)) return 'failed_tasks'
  return null
}

async function executeIntent(key: PromptKey) {
  if (key === 'failed_tasks') {
    if (sessionId.value && selectedProjectId.value) await hermesApi.tool(sessionId.value, 'failed_runs', { project_id: selectedProjectId.value, arguments: { limit: 20 } }).catch(() => undefined)
    buildFailedTaskAnswer()
  }
  else if (key === 'quality') {
    if (sessionId.value && selectedProjectId.value) await hermesApi.tool(sessionId.value, 'quality_summary', { project_id: selectedProjectId.value }).catch(() => undefined)
    buildQualityAnswer()
  }
  else if (key === 'test_plan') buildPlanDraft()
  else await explainFailure()
}

async function askPrompt(key: PromptKey) {
  const prompt = promptOptions.value.find((item) => item.key === key)
  if (!prompt) return
  appendMessage('user', prompt.title)
  await executeIntent(key)
}

async function submitPrompt() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  appendMessage('user', text)
  const key = intentFor(text)
  if (key === 'test_plan' || key === 'explain_failure') await executeIntent(key)
  else {
    const handled = await orchestratePrompt(text)
    if (!handled) {
      if (key) await executeIntent(key)
      else await queryHermes(text, conversationHistory().slice(0, -1))
    }
  }
}

watch(planDraft, () => {
  draftConfirmed.value = false
}, { deep: true, flush: 'sync' })

onMounted(async () => {
  await loadProjects()
})
</script>

<style scoped>
.hermes-page {
  --hermes-ink: var(--c-text);
  --hermes-violet: var(--c-ai);
  --hermes-mint: var(--c-success);
  --hermes-coral: var(--c-error);
  --hermes-paper: var(--c-bg-elevated);
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: var(--c-text);
}

.hermes-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 48px;
  padding: 0 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
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
  width: 200px;
}

.toolbar-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 6px;
}

.toolbar-chip {
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
  font-size: 11px;
}

.toolbar-chip b {
  color: var(--c-text);
  font-weight: 600;
}

.toolbar-chip.chip-fail {
  background: #fee2e2;
  color: #b91c1c;
}

.toolbar-chip.chip-fail b {
  color: #b91c1c;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-btn {
  border-radius: 6px;
}

.primary-btn {
  background: var(--c-primary);
  border-color: var(--c-primary);
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
.load-alert,
.project-empty {
  border-radius: var(--radius-lg);
}

.context-strip {
  border: 1px solid var(--c-border);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.context-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 20px;
  border-radius: var(--radius-lg);
}

.context-intro,
.context-metrics {
  display: flex;
  align-items: center;
}

.context-intro {
  flex-wrap: wrap;
  gap: 8px 12px;
}

.context-intro .section-kicker,
.section-kicker {
  color: var(--c-ai);
}

.context-intro strong {
  font-size: 15px;
  color: var(--c-text);
}

.context-intro > span:last-child {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.context-metrics {
  flex-wrap: wrap;
  gap: 16px;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.context-metrics b {
  margin-right: 4px;
  color: var(--c-text);
  font-size: 16px;
  font-family: 'JetBrains Mono', monospace;
}

.assistant-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(310px, .85fr);
  gap: 20px;
  align-items: start;
}


button:focus-visible,
input:focus-visible,
textarea:focus-visible,
:deep(.ant-select-selector:focus-visible) {
  outline: 2px solid var(--c-ai);
  outline-offset: 2px;
}

@media (max-width: 920px) {
  .assistant-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .hermes-hero {
    display: block;
    padding: 22px 18px;
  }

  .hero-title-row,
  .context-strip {
    display: block;
  }

  .hero-chip {
    display: inline-block;
    margin-top: 10px;
  }

  .hero-controls {
    margin-top: 20px;
  }

  .context-metrics {
    margin-top: 12px;
  }

}
</style>
