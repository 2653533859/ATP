<template>
  <div class="page-shell hermes-page">
    <section class="hermes-hero">
      <div class="hero-copy">
        <p class="eyebrow"><RobotOutlined /> {{ t('hermes.eyebrow') }}</p>
        <div class="hero-title-row">
          <h1>{{ t('hermes.title') }}</h1>
          <span class="hero-chip">OBSERVE → EXPLAIN → PLAN</span>
        </div>
        <p class="hero-subtitle">{{ t('hermes.subtitle') }}</p>
        <div class="hero-status">
          <span class="status-dot" />
          <span>{{ selectedProjectName || t('hermes.no_project') }}</span>
          <span class="status-divider" />
          <span class="status-note">{{ t('hermes.traceable_status') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label for="hermes-project">{{ t('hermes.project_label') }}</label>
        <a-select
          id="hermes-project"
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :placeholder="t('hermes.project_placeholder')"
          @change="handleProjectChange"
        />
        <a-button :loading="loading" @click="refreshWorkbench">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </div>
    </section>

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
      <section class="context-strip" :aria-label="t('hermes.context_aria')">
        <div class="context-intro">
          <span class="section-kicker">{{ t('hermes.context_kicker') }}</span>
          <strong>{{ selectedProjectName }}</strong>
          <span>{{ t('hermes.context_description') }}</span>
        </div>
        <div class="context-metrics">
          <span><b>{{ moduleCount }}</b> {{ t('hermes.context_modules') }}</span>
          <span><b>{{ cases.length }}</b> {{ t('hermes.context_cases') }}</span>
          <span><b>{{ failedTasks.length }}</b> {{ t('hermes.context_failures') }}</span>
        </div>
      </section>

      <div class="assistant-layout">
        <section class="conversation-card" aria-live="polite">
          <header class="conversation-header">
            <div>
              <span class="section-kicker">HERMES / PROJECT COPILOT</span>
              <h2>{{ t('hermes.conversation_title') }}</h2>
            </div>
            <a-tag color="green"><span class="tag-dot" /> {{ t('hermes.data_bound') }}</a-tag>
          </header>

          <div class="message-list" role="log" :aria-label="t('hermes.message_list_aria')">
            <article v-for="message in messages" :key="message.id" class="message" :class="`message-${message.role}`">
              <div class="message-avatar" aria-hidden="true">
                <span v-if="message.role === 'assistant'">H</span>
                <span v-else>你</span>
              </div>
              <div class="message-body">
                <div class="message-meta">
                  <strong>{{ message.role === 'assistant' ? 'Hermes' : t('hermes.you') }}</strong>
                  <span>{{ formatTime(message.createdAt) }}</span>
                </div>
                <p class="message-text">{{ message.text }}</p>
                <div v-if="message.taskIds?.length" class="message-task-list">
                  <button
                    v-for="taskId in message.taskIds"
                    :key="taskId"
                    type="button"
                    class="message-task"
                    @click="selectFailureTask(taskId)"
                  >
                    <span class="task-status" />
                    <span>{{ taskName(taskId) }}</span>
                    <ArrowRightOutlined />
                  </button>
                </div>
                <div v-if="message.sources?.length" class="source-list">
                  <span class="source-label">{{ t('hermes.sources') }}</span>
                  <button
                    v-for="source in message.sources"
                    :key="`${message.id}-${source.label}`"
                    type="button"
                    class="source-link"
                    @click="openSource(source)"
                  >
                    {{ source.label }} <ArrowRightOutlined />
                  </button>
                </div>
              </div>
            </article>
            <div v-if="diagnosing" class="thinking-row">
              <span class="thinking-pulse" />
              <span>{{ t('hermes.diagnosing') }}</span>
            </div>
            <div v-if="querying" class="thinking-row">
              <span class="thinking-pulse" />
              <span>{{ t('hermes.querying') }}</span>
            </div>
          </div>

          <div class="prompt-stations">
            <span class="section-kicker">{{ t('hermes.prompt_kicker') }}</span>
            <div class="prompt-grid">
              <button
                v-for="prompt in promptOptions"
                :key="prompt.key"
                type="button"
                class="prompt-card"
                :disabled="loading || diagnosing || querying"
                @click="askPrompt(prompt.key)"
              >
                <span class="prompt-icon" :class="`prompt-icon-${prompt.key}`">{{ prompt.mark }}</span>
                <span>
                  <strong>{{ prompt.title }}</strong>
                  <small>{{ prompt.description }}</small>
                </span>
                <ArrowRightOutlined />
              </button>
            </div>
          </div>

          <form class="composer" @submit.prevent="submitPrompt">
            <input
              v-model="inputText"
              :disabled="loading || diagnosing || querying"
              :placeholder="t('hermes.input_placeholder')"
              :aria-label="t('hermes.input_aria')"
            />
            <a-button type="primary" html-type="submit" :disabled="!inputText.trim() || loading || diagnosing || querying">
              {{ t('hermes.send') }} <ArrowRightOutlined />
            </a-button>
          </form>
          <p class="composer-note"><BulbOutlined /> {{ t('hermes.composer_note') }}</p>
        </section>

        <aside class="evidence-column">
          <section class="evidence-card quality-card">
            <div class="card-heading">
              <div>
                <span class="section-kicker">{{ t('hermes.quality_kicker') }}</span>
                <h2>{{ t('hermes.quality_title') }}</h2>
              </div>
              <CheckCircleOutlined />
            </div>
            <div class="quality-score">
              <strong>{{ qualityScore }}</strong><span>/100</span>
            </div>
            <div class="quality-bar"><span :style="{ width: `${qualityScore}%` }" /></div>
            <div class="quality-grid">
              <div><span>{{ t('hermes.quality_pass_rate') }}</span><b>{{ passRate }}%</b></div>
              <div><span>{{ t('hermes.quality_runs') }}</span><b>{{ totalRuns }}</b></div>
              <div><span>{{ t('hermes.quality_coverage') }}</span><b>{{ coverageRate }}%</b></div>
              <div><span>{{ t('hermes.quality_defects') }}</span><b>{{ openDefects }}</b></div>
            </div>
            <button type="button" class="text-action" @click="askPrompt('quality')">
              {{ t('hermes.ask_quality') }} <ArrowRightOutlined />
            </button>
          </section>

          <section class="evidence-card failure-card">
            <div class="card-heading">
              <div>
                <span class="section-kicker">{{ t('hermes.failure_kicker') }}</span>
                <h2>{{ t('hermes.failure_title') }}</h2>
              </div>
              <ExclamationCircleOutlined />
            </div>
            <p class="card-description">{{ t('hermes.failure_description') }}</p>
            <div v-if="failedTasks.length" class="failure-list">
              <div v-for="task in failedTasks.slice(0, 5)" :key="task.id" class="failure-row" :class="{ selected: selectedTaskId === task.id }">
                <button type="button" class="failure-main" @click="selectFailureTask(task.id)">
                  <span class="failure-mark" />
                  <span class="failure-info">
                    <strong>{{ task.name }}</strong>
                    <small>{{ task.task_type }} · {{ formatTime(task.created_at) }}</small>
                  </span>
                </button>
                <button type="button" class="diagnose-action" :disabled="diagnosing" @click="explainFailure(task)">
                  {{ t('hermes.explain') }}
                </button>
              </div>
            </div>
            <a-empty v-else :description="t('hermes.no_failures')" />
            <div class="failure-footer">
              <a-button type="link" @click="openTaskCenter">{{ t('hermes.open_task_center') }}</a-button>
              <a-button type="link" @click="openRuns">{{ t('hermes.open_runs') }}</a-button>
            </div>
          </section>
        </aside>
      </div>

      <section v-if="diagnosis" class="diagnosis-result">
        <div class="diagnosis-heading">
          <div>
            <span class="section-kicker">{{ t('hermes.diagnosis_kicker') }}</span>
            <h2>{{ t('hermes.diagnosis_title') }}</h2>
          </div>
          <a-tag :color="diagnosis.result.status === 'done' ? 'green' : 'orange'">{{ diagnosis.result.source }}</a-tag>
        </div>
        <p class="diagnosis-summary">{{ diagnosis.result.summary }}</p>
        <div v-if="diagnosis.result.repair_suggestions.length" class="suggestion-grid">
          <div v-for="suggestion in diagnosis.result.repair_suggestions" :key="`${diagnosis.taskId}-${suggestion.step_index}`" class="suggestion-card">
            <span>{{ t('hermes.suggestion_step', { index: suggestion.step_index + 1 }) }}</span>
            <strong>{{ suggestion.step_name }}</strong>
            <p>{{ suggestion.suggested_change }}</p>
            <small>{{ suggestion.evidence }}</small>
          </div>
        </div>
        <div class="source-list diagnosis-source">
          <span class="source-label">{{ t('hermes.sources') }}</span>
          <button type="button" class="source-link" @click="openTaskById(diagnosis.taskId)">
            {{ t('hermes.run_detail_source') }} <ArrowRightOutlined />
          </button>
        </div>
      </section>

      <section v-if="planDraft" class="plan-draft-card">
        <div class="plan-draft-heading">
          <div>
            <span class="section-kicker">{{ t('hermes.plan_kicker') }}</span>
            <h2>{{ t('hermes.plan_title') }}</h2>
            <p>{{ t('hermes.plan_description') }}</p>
          </div>
          <a-button type="primary" @click="openPlans"><ArrowRightOutlined /> {{ t('hermes.open_plans') }}</a-button>
        </div>
        <div class="plan-form-grid">
          <label>
            <span>{{ t('hermes.plan_name') }}</span>
            <input v-model="planDraft.name" />
          </label>
          <label>
            <span>{{ t('hermes.plan_objective') }}</span>
            <textarea v-model="planDraft.objective" rows="3" />
          </label>
        </div>
        <div class="plan-points">
          <div class="points-heading">
            <span>{{ t('hermes.plan_points') }}</span>
            <button type="button" class="text-action" @click="addPlanPoint"><PlusOutlined /> {{ t('hermes.add_point') }}</button>
          </div>
          <div v-for="(_, index) in planDraft.testPoints" :key="`point-${index}`" class="point-row">
            <span>{{ String(index + 1).padStart(2, '0') }}</span>
            <input v-model="planDraft.testPoints[index]" />
            <button type="button" class="icon-action" :aria-label="t('hermes.remove_point')" @click="removePlanPoint(index)"><CloseOutlined /></button>
          </div>
        </div>
        <p class="draft-note"><BulbOutlined /> {{ t('hermes.plan_draft_note') }}</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRightOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  CloseOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
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
  type FailureDiagnosisResult,
  type ModuleTreeItem,
  type ProjectItem,
  type WorkbenchTaskItem,
  type ReportOverviewItem,
} from '@/api'

type HermesSource = { label: string; path: string }
type HermesMessage = {
  id: number
  role: 'assistant' | 'user'
  text: string
  createdAt: string
  sources?: HermesSource[]
  taskIds?: string[]
}
type PromptKey = 'failed_tasks' | 'explain_failure' | 'test_plan' | 'quality'
type PlanDraft = { name: string; objective: string; testPoints: string[] }

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
const messages = ref<HermesMessage[]>([])
const inputText = ref('')
const selectedTaskId = ref<string | null>(null)
const diagnosis = ref<{ taskId: string; result: FailureDiagnosisResult } | null>(null)
const planDraft = ref<PlanDraft | null>(null)
const loading = ref(false)
const diagnosing = ref(false)
const querying = ref(false)
const loadError = ref('')
let loadSequence = 0
let projectsSequence = 0
let messageSequence = 0

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const moduleCount = computed(() => flattenModules(modules.value).length)
const totalRuns = computed(() => reportOverview.value?.total_runs ?? 0)
const passRate = computed(() => Math.round(Number(reportOverview.value?.pass_rate ?? 0)))
const qualityScore = computed(() => Math.round(Number(reportOverview.value?.quality_score ?? passRate.value)))
const coverageRate = computed(() => Math.round(Number(reportOverview.value?.coverage_rate ?? 0)))
const openDefects = computed(() => reportOverview.value?.open_defects ?? 0)
const promptOptions = computed(() => [
  { key: 'failed_tasks' as const, mark: '!', title: t('hermes.prompts.failed_tasks'), description: t('hermes.prompts.failed_tasks_hint') },
  { key: 'explain_failure' as const, mark: '?', title: t('hermes.prompts.explain_failure'), description: t('hermes.prompts.explain_failure_hint') },
  { key: 'test_plan' as const, mark: '+', title: t('hermes.prompts.test_plan'), description: t('hermes.prompts.test_plan_hint') },
  { key: 'quality' as const, mark: '%', title: t('hermes.prompts.quality'), description: t('hermes.prompts.quality_hint') },
])

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(items: ModuleTreeItem[]): ModuleTreeItem[] {
  return items.flatMap((item) => [item, ...flattenModules(item.children || [])])
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : t('hermes.not_available')
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
  messages.value = [{
    id: ++messageSequence,
    role: 'assistant',
    text: t('hermes.welcome', { project: selectedProjectName.value }),
    createdAt: new Date().toISOString(),
    sources: [source(t('hermes.source_reports'), '/reports'), source(t('hermes.source_tasks'), '/tasks')],
  }]
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
  loadError.value = failures.join('；')
  resetConversation()
  loading.value = false
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

function appendMessage(role: HermesMessage['role'], text: string, sources?: HermesSource[], taskIds?: string[]) {
  messages.value.push({
    id: ++messageSequence,
    role,
    text,
    createdAt: new Date().toISOString(),
    sources,
    taskIds,
  })
}

function taskName(taskId: string) {
  return failedTasks.value.find((task) => task.id === taskId)?.name || taskId
}

function selectedFailureTask() {
  return failedTasks.value.find((task) => task.id === selectedTaskId.value) || failedTasks.value[0]
}

function selectFailureTask(taskId: string) {
  selectedTaskId.value = taskId
}

function openSource(item: HermesSource) {
  void router.push(item.path)
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
  void router.push(source(t('hermes.source_plans'), '/plans').path)
}

async function queryHermes(text: string) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  querying.value = true
  try {
    const result = await hermesApi.query({ project_id: projectId, query: text, limit: 8 })
    const sources = result.sources.map((item) => ({
      label: [item.source_ref || item.source_type, item.title].join(' · '),
      path: item.path,
    }))
    appendMessage('assistant', result.answer, sources)
  } catch (error) {
    appendMessage('assistant', t('hermes.query_failed', { error: errorMessage(error, t('hermes.query_unavailable')) }))
  } finally {
    querying.value = false
  }
}

function addPlanPoint() {
  if (planDraft.value) planDraft.value.testPoints.push(t('hermes.default_plan_point'))
}

function removePlanPoint(index: number) {
  if (planDraft.value && planDraft.value.testPoints.length > 1) planDraft.value.testPoints.splice(index, 1)
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
  const moduleNames = flattenModules(modules.value).slice(0, 4).map((item) => item.name)
  const pointSeed = moduleNames.length
    ? moduleNames.map((name) => t('hermes.plan_point_module', { name }))
    : [t('hermes.default_plan_point')]
  planDraft.value = {
    name: t('hermes.plan_default_name', { project: selectedProjectName.value }),
    objective: t('hermes.plan_default_objective', { cases: cases.value.length, passRate: passRate.value }),
    testPoints: [...pointSeed, t('hermes.plan_point_failure', { count: failedTasks.value.length })],
  }
  appendMessage('assistant', t('hermes.answers.plan', { count: pointSeed.length }), [source(t('hermes.source_cases'), '/cases'), source(t('hermes.source_plans'), '/plans')])
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
  if (key === 'failed_tasks') buildFailedTaskAnswer()
  else if (key === 'quality') buildQualityAnswer()
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
  if (key) await executeIntent(key)
  else await queryHermes(text)
}

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

.hermes-hero {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 28px;
  overflow: hidden;
  min-height: 200px;
  padding: 28px 32px;
  color: #fff;
  border-radius: var(--radius-xl);
  border: 1px solid rgba(137, 126, 255, 0.25);
  background:
    radial-gradient(circle at 85% 20%, rgba(90, 75, 254, .35), transparent 35%),
    radial-gradient(circle at 15% 90%, rgba(64, 235, 227, .25), transparent 30%),
    linear-gradient(130deg, #1d1a2c 0%, #0b0a12 60%, #1d1a2c 100%);
  box-shadow: 0 16px 40px rgba(0, 0, 0, .25);
}

.hermes-hero::after {
  position: absolute;
  right: 30%;
  bottom: -60px;
  width: 160px;
  height: 160px;
  content: '';
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 50%;
  box-shadow: 0 0 0 20px rgba(255, 255, 255, .03), 0 0 0 40px rgba(255, 255, 255, .015);
}

.hero-copy,
.hero-controls {
  position: relative;
  z-index: 1;
}

.hero-copy {
  max-width: 720px;
}

.eyebrow,
.section-kicker {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #897eff;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 10px;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: clamp(24px, 3.5vw, 36px);
  font-weight: 700;
  letter-spacing: -.03em;
  color: #ffffff;
}

.hero-chip {
  padding: 4px 10px;
  color: #897eff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
  border: 1px solid rgba(137, 126, 255, .3);
  border-radius: var(--radius-full);
  background: rgba(90, 75, 254, 0.15);
}

.hero-subtitle {
  max-width: 630px;
  margin: 10px 0 18px;
  color: rgba(255, 255, 255, .8);
  line-height: 1.6;
  font-size: 13px;
}

.hero-status {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #e0e7ff;
  font-size: 12px;
  font-weight: 600;
}

.status-dot,
.tag-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-success);
  box-shadow: 0 0 8px rgba(74, 225, 145, .6);
}

.status-divider {
  width: 1px;
  height: 14px;
  margin: 0 4px;
  background: rgba(255, 255, 255, .25);
}

.status-note {
  color: rgba(255, 255, 255, .6);
}

.hero-controls {
  display: flex;
  flex: 0 0 240px;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
  justify-content: center;
}

.hero-controls label {
  color: rgba(255, 255, 255, .7);
  font-size: 12px;
  font-weight: 600;
}

.hero-controls :deep(.ant-select-selector) {
  color: #fff !important;
  background: rgba(255, 255, 255, .12) !important;
  border-color: rgba(255, 255, 255, .25) !important;
  border-radius: var(--radius-md) !important;
}

.hero-controls :deep(.ant-select-selection-placeholder),
.hero-controls :deep(.ant-select-selection-item),
.hero-controls :deep(.ant-select-arrow) {
  color: rgba(255, 255, 255, .9) !important;
}

.hero-controls :deep(.ant-btn) {
  color: #fff;
  border-color: rgba(255, 255, 255, .25);
  background: rgba(255, 255, 255, .12);
  border-radius: var(--radius-md);
}

.load-alert,
.project-empty {
  border-radius: var(--radius-lg);
}

.context-strip,
.conversation-card,
.evidence-card,
.diagnosis-result,
.plan-draft-card {
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
.context-metrics,
.card-heading,
.diagnosis-heading,
.plan-draft-heading,
.points-heading {
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

.conversation-card,
.evidence-card,
.diagnosis-result,
.plan-draft-card {
  border-radius: var(--radius-lg);
}

.conversation-card {
  min-width: 0;
  overflow: hidden;
}

.conversation-header,
.prompt-stations,
.composer {
  padding: 18px 22px;
}

.conversation-header,
.card-heading,
.diagnosis-heading,
.plan-draft-heading {
  justify-content: space-between;
  gap: 16px;
}

.conversation-header {
  border-bottom: 1px solid var(--c-border);
}

h2 {
  margin-bottom: 0;
  color: var(--c-text);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -.02em;
}

.conversation-header h2,
.card-heading h2,
.diagnosis-heading h2,
.plan-draft-heading h2 {
  margin-top: 4px;
}

.conversation-header :deep(.ant-tag) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  border-radius: var(--radius-full);
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 340px;
  max-height: 580px;
  padding: 22px;
  overflow: auto;
  background: var(--c-bg-subtle);
}

.message {
  display: flex;
  gap: 12px;
  max-width: 90%;
}

.message-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  display: grid;
  flex: 0 0 32px;
  place-items: center;
  width: 32px;
  height: 32px;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #40ebe3 0%, #4a51ff 100%);
  box-shadow: 0 2px 8px rgba(127, 105, 255, 0.35);
}

.message-user .message-avatar {
  color: #fff;
  background: linear-gradient(135deg, #5a4bfe, #897eff);
  box-shadow: 0 2px 8px rgba(90, 75, 254, 0.35);
}

.message-body {
  min-width: 0;
}

.message-meta {
  display: flex;
  gap: 9px;
  align-items: baseline;
  margin-bottom: 5px;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.message-meta strong {
  color: var(--c-text);
  font-size: 12px;
  font-weight: 600;
}

.message-text {
  margin-bottom: 0;
  padding: 12px 16px;
  color: var(--c-text);
  line-height: 1.65;
  font-size: 13px;
  border: 1px solid var(--c-border);
  border-radius: 4px 16px 16px 16px;
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-xs);
}

.message-user .message-text {
  border-color: var(--c-primary-glow);
  border-radius: 16px 4px 16px 16px;
  background: var(--c-primary-soft);
  color: var(--c-text);
}

.message-task-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 10px;
}

.message-task,
.source-link,
.text-action,
.icon-action,
.diagnose-action,
.failure-main {
  border: 0;
  cursor: pointer;
  background: transparent;
}

.message-task {
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(440px, 100%);
  padding: 8px 12px;
  color: var(--c-text);
  text-align: left;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
  transition: all 0.15s ease;
}

.message-task:hover,
.source-link:hover,
.text-action:hover {
  color: var(--c-primary);
  border-color: var(--c-primary);
}

.message-task > span:nth-child(2) {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-status,
.failure-mark {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-error);
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.source-label {
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.source-link,
.text-action {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 0;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 600;
}

.thinking-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-left: 44px;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.thinking-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-ai);
  animation: pulse 1.1s ease-in-out infinite;
}

.prompt-stations {
  border-top: 1px solid var(--c-border);
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.prompt-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  color: var(--c-text);
  text-align: left;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  background: var(--c-bg-elevated);
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}

.prompt-card:hover:not(:disabled) {
  border-color: var(--c-ai);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.prompt-card:disabled {
  cursor: wait;
  opacity: .55;
}

.prompt-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  border-radius: var(--radius-sm);
  background: var(--c-ai);
}

.prompt-icon-explain_failure { background: var(--c-error); }
.prompt-icon-test_plan { background: var(--c-info); }
.prompt-icon-quality { background: var(--c-primary); }

.prompt-card strong,
.prompt-card small {
  display: block;
}

.prompt-card strong {
  font-size: 12px;
  font-weight: 600;
}

.prompt-card small {
  margin-top: 2px;
  overflow: hidden;
  color: var(--c-text-tertiary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-card > .anticon {
  color: var(--c-text-tertiary);
}

.composer {
  display: flex;
  gap: 10px;
  border-top: 1px solid var(--c-border);
}

.composer input,
.plan-form-grid input,
.plan-form-grid textarea,
.point-row input {
  min-width: 0;
  width: 100%;
  padding: 10px 14px;
  color: var(--c-text);
  font: inherit;
  font-size: 13px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  outline: none;
  background: var(--c-bg-elevated);
  transition: border-color .18s ease, box-shadow .18s ease;
}

.composer input:focus,
.plan-form-grid input:focus,
.plan-form-grid textarea:focus,
.point-row input:focus {
  border-color: var(--c-ai);
  box-shadow: 0 0 0 3px var(--c-ai-soft);
}

.composer .ant-btn {
  flex-shrink: 0;
  border-radius: var(--radius-md);
}

.composer-note,
.draft-note {
  margin: -6px 24px 16px;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.evidence-column {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.evidence-card {
  padding: 20px;
}

.card-heading :deep(.anticon) {
  color: var(--c-ai);
  font-size: 20px;
}

.failure-card .card-heading :deep(.anticon) {
  color: var(--c-error);
}

.quality-score {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 16px;
}

.quality-score strong {
  font-size: 38px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -.04em;
  color: var(--c-text);
}

.quality-score span {
  color: var(--c-text-tertiary);
  font-size: 13px;
}

.quality-bar {
  height: 6px;
  margin: 8px 0 16px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--c-bg-muted);
}

.quality-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #8b5cf6, #10b981);
  transition: width .35s ease;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border);
}

.quality-grid div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quality-grid span {
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.quality-grid b {
  font-size: 16px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--c-text);
}

.quality-card .text-action {
  margin-top: 16px;
}

.card-description {
  margin: 10px 0 14px;
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.failure-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.failure-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
  transition: all 0.15s ease;
}

.failure-row.selected {
  border-color: var(--c-ai);
  background: var(--c-ai-soft);
}

.failure-main {
  display: flex;
  flex: 1;
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 0;
  color: var(--c-text);
  text-align: left;
}

.failure-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}

.failure-info strong,
.failure-info small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.failure-info strong {
  font-size: 12px;
  color: var(--c-text);
}

.failure-info small {
  color: var(--c-text-tertiary);
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
}

.diagnose-action {
  flex-shrink: 0;
  padding: 3px 6px;
  color: var(--c-ai);
  font-size: 11px;
  font-weight: 600;
}

.diagnose-action:hover:not(:disabled) {
  color: var(--c-text);
}

.failure-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  border-top: 1px solid var(--c-border);
}

.failure-footer :deep(.ant-btn) {
  padding-right: 0;
  padding-left: 0;
  font-size: 12px;
}

.diagnosis-result,
.plan-draft-card {
  padding: 22px 24px;
}

.diagnosis-result {
  border-left: 4px solid var(--c-error);
}

.diagnosis-summary,
.plan-draft-heading p {
  margin: 12px 0 0;
  color: var(--c-text-secondary);
  line-height: 1.6;
  font-size: 13px;
}

.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.suggestion-card {
  padding: 12px 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
}

.suggestion-card > span,
.suggestion-card small {
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.suggestion-card strong {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: var(--c-text);
}

.suggestion-card p {
  margin: 6px 0;
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.diagnosis-source {
  margin-top: 16px;
}

.plan-draft-card {
  border-top: 4px solid var(--c-success);
}

.plan-draft-heading {
  align-items: flex-start;
}

.plan-draft-heading p {
  margin-bottom: 0;
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.plan-form-grid {
  display: grid;
  grid-template-columns: .8fr 1.2fr;
  gap: 14px;
  margin-top: 18px;
}

.plan-form-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.plan-form-grid textarea {
  resize: vertical;
}

.plan-points {
  margin-top: 16px;
}

.points-heading {
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.point-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
}

.point-row > span {
  width: 24px;
  color: var(--c-ai);
  font-size: 11px;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
}

.icon-action {
  flex: 0 0 26px;
  width: 26px;
  height: 26px;
  color: var(--c-text-tertiary);
  border-radius: var(--radius-sm);
}

.icon-action:hover {
  color: var(--c-error);
  background: var(--c-error-soft);
}

.plan-draft-card .draft-note {
  margin: 14px 0 0;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
:deep(.ant-select-selector:focus-visible) {
  outline: 2px solid var(--c-ai);
  outline-offset: 2px;
}

@keyframes pulse {
  0%, 100% { opacity: .35; transform: scale(.8); }
  50% { opacity: 1; transform: scale(1.15); }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-pulse,
  .prompt-card,
  .quality-bar span {
    animation: none;
    transition: none;
  }
}

@media (max-width: 920px) {
  .assistant-layout {
    grid-template-columns: 1fr;
  }

  .evidence-column {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
}

@media (max-width: 680px) {
  .hermes-hero {
    display: block;
    padding: 22px 18px;
  }

  .hero-title-row,
  .context-strip,
  .plan-draft-heading {
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

  .evidence-column,
  .prompt-grid,
  .plan-form-grid {
    grid-template-columns: 1fr;
  }

  .conversation-header,
  .prompt-stations,
  .composer,
  .diagnosis-result,
  .plan-draft-card {
    padding-right: 16px;
    padding-left: 16px;
  }

  .message-list {
    padding: 16px;
  }

  .message {
    max-width: 100%;
  }

  .composer {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
