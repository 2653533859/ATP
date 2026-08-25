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
  --hermes-ink: #211b2f;
  --hermes-plum: #352849;
  --hermes-violet: #7358d8;
  --hermes-mint: #38b8a0;
  --hermes-coral: #e88d76;
  --hermes-paper: #fbfafc;
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--hermes-ink);
}

.hermes-hero {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 28px;
  overflow: hidden;
  min-height: 210px;
  padding: 32px 36px;
  color: #fff;
  border-radius: 24px;
  background:
    radial-gradient(circle at 87% 20%, rgba(56, 184, 160, .32), transparent 27%),
    radial-gradient(circle at 61% 112%, rgba(115, 88, 216, .38), transparent 35%),
    linear-gradient(130deg, #241c35 0%, #36264b 54%, #223a45 100%);
  box-shadow: 0 20px 50px rgba(48, 33, 67, .16);
}

.hermes-hero::after {
  position: absolute;
  right: 34%;
  bottom: -70px;
  width: 180px;
  height: 180px;
  content: '';
  border: 1px solid rgba(255, 255, 255, .16);
  border-radius: 50%;
  box-shadow: 0 0 0 24px rgba(255, 255, 255, .04), 0 0 0 48px rgba(255, 255, 255, .025);
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
  font-weight: 800;
  letter-spacing: .16em;
  text-transform: uppercase;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #9fe7d6;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: clamp(28px, 4vw, 46px);
  font-weight: 760;
  letter-spacing: -.045em;
}

.hero-chip {
  padding: 6px 9px;
  color: #c7f5ea;
  font-size: 10px;
  letter-spacing: .12em;
  border: 1px solid rgba(199, 245, 234, .25);
  border-radius: 999px;
}

.hero-subtitle {
  max-width: 630px;
  margin: 14px 0 22px;
  color: rgba(255, 255, 255, .76);
  line-height: 1.7;
}

.hero-status {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #e9fff9;
  font-size: 13px;
}

.status-dot,
.tag-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--hermes-mint);
  box-shadow: 0 0 0 4px rgba(56, 184, 160, .16);
}

.status-divider {
  width: 1px;
  height: 14px;
  margin: 0 4px;
  background: rgba(255, 255, 255, .3);
}

.status-note {
  color: rgba(255, 255, 255, .56);
}

.hero-controls {
  display: flex;
  flex: 0 0 220px;
  flex-direction: column;
  gap: 9px;
  align-items: stretch;
  justify-content: center;
}

.hero-controls label {
  color: rgba(255, 255, 255, .62);
  font-size: 12px;
}

.hero-controls :deep(.ant-select-selector) {
  color: #fff !important;
  background: rgba(255, 255, 255, .1) !important;
  border-color: rgba(255, 255, 255, .24) !important;
}

.hero-controls :deep(.ant-select-selection-placeholder),
.hero-controls :deep(.ant-select-selection-item),
.hero-controls :deep(.ant-select-arrow) {
  color: rgba(255, 255, 255, .85) !important;
}

.hero-controls :deep(.ant-btn) {
  color: #fff;
  border-color: rgba(255, 255, 255, .24);
  background: rgba(255, 255, 255, .1);
}

.load-alert,
.project-empty {
  border-radius: 16px;
}

.context-strip,
.conversation-card,
.evidence-card,
.diagnosis-result,
.plan-draft-card {
  border: 1px solid #ece9f0;
  background: var(--hermes-paper);
  box-shadow: 0 9px 28px rgba(43, 31, 61, .05);
}

.context-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 17px 22px;
  border-radius: 15px;
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
  color: var(--hermes-violet);
}

.context-intro strong {
  font-size: 16px;
}

.context-intro > span:last-child {
  color: #817c89;
  font-size: 12px;
}

.context-metrics {
  flex-wrap: wrap;
  gap: 15px;
  color: #817c89;
  font-size: 12px;
}

.context-metrics b {
  margin-right: 4px;
  color: var(--hermes-ink);
  font-size: 17px;
}

.assistant-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(310px, .85fr);
  gap: 18px;
  align-items: start;
}

.conversation-card,
.evidence-card,
.diagnosis-result,
.plan-draft-card {
  border-radius: 18px;
}

.conversation-card {
  min-width: 0;
  overflow: hidden;
}

.conversation-header,
.prompt-stations,
.composer {
  padding: 20px 24px;
}

.conversation-header,
.card-heading,
.diagnosis-heading,
.plan-draft-heading {
  justify-content: space-between;
  gap: 16px;
}

.conversation-header {
  border-bottom: 1px solid #eeeaf2;
}

h2 {
  margin-bottom: 0;
  color: var(--hermes-ink);
  font-size: 20px;
  letter-spacing: -.025em;
}

.conversation-header h2,
.card-heading h2,
.diagnosis-heading h2,
.plan-draft-heading h2 {
  margin-top: 6px;
}

.conversation-header :deep(.ant-tag) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  border-radius: 999px;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 21px;
  min-height: 330px;
  max-height: 570px;
  padding: 24px;
  overflow: auto;
  background: linear-gradient(180deg, #fcfbfd, #f7f5fa);
}

.message {
  display: flex;
  gap: 12px;
  max-width: 92%;
}

.message-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  display: grid;
  flex: 0 0 30px;
  place-items: center;
  width: 30px;
  height: 30px;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  border-radius: 10px;
  background: var(--hermes-violet);
}

.message-user .message-avatar {
  color: #244c45;
  background: #b8e8dc;
}

.message-body {
  min-width: 0;
}

.message-meta {
  display: flex;
  gap: 9px;
  align-items: baseline;
  margin-bottom: 5px;
  color: #918a9a;
  font-size: 11px;
}

.message-meta strong {
  color: var(--hermes-ink);
  font-size: 12px;
}

.message-text {
  margin-bottom: 0;
  padding: 12px 14px;
  color: #453e50;
  line-height: 1.7;
  border: 1px solid #ebe6f0;
  border-radius: 3px 14px 14px 14px;
  background: #fff;
}

.message-user .message-text {
  border-color: #c8eee5;
  border-radius: 14px 3px 14px 14px;
  background: #ecfbf7;
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
  padding: 8px 10px;
  color: #4d445b;
  text-align: left;
  border: 1px solid #e8e1ee;
  border-radius: 9px;
  background: #fff;
}

.message-task:hover,
.source-link:hover,
.text-action:hover {
  color: var(--hermes-violet);
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
  background: var(--hermes-coral);
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  margin-top: 10px;
}

.source-label {
  color: #9d95a7;
  font-size: 11px;
}

.source-link,
.text-action {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 0;
  color: var(--hermes-violet);
  font-size: 12px;
}

.thinking-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-left: 42px;
  color: #8a8194;
  font-size: 12px;
}

.thinking-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--hermes-mint);
  animation: pulse 1.1s ease-in-out infinite;
}

.prompt-stations {
  border-top: 1px solid #eeeaf2;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 13px;
}

.prompt-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 13px;
  color: var(--hermes-ink);
  text-align: left;
  border: 1px solid #e9e4ed;
  border-radius: 12px;
  cursor: pointer;
  background: #fff;
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}

.prompt-card:hover:not(:disabled) {
  border-color: #b5a6e8;
  box-shadow: 0 8px 20px rgba(115, 88, 216, .1);
  transform: translateY(-2px);
}

.prompt-card:disabled {
  cursor: wait;
  opacity: .55;
}

.prompt-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  border-radius: 9px;
  background: var(--hermes-violet);
}

.prompt-icon-explain_failure { background: #df8c6d; }
.prompt-icon-test_plan { background: #4fa89d; }
.prompt-icon-quality { background: #6178c7; }

.prompt-card strong,
.prompt-card small {
  display: block;
}

.prompt-card strong {
  font-size: 13px;
}

.prompt-card small {
  margin-top: 3px;
  overflow: hidden;
  color: #908797;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-card > .anticon {
  color: #aaa1b5;
}

.composer {
  display: flex;
  gap: 9px;
  border-top: 1px solid #eeeaf2;
}

.composer input,
.plan-form-grid input,
.plan-form-grid textarea,
.point-row input {
  min-width: 0;
  width: 100%;
  padding: 10px 12px;
  color: var(--hermes-ink);
  font: inherit;
  border: 1px solid #e5e0e9;
  border-radius: 9px;
  outline: none;
  background: #fff;
  transition: border-color .18s ease, box-shadow .18s ease;
}

.composer input:focus,
.plan-form-grid input:focus,
.plan-form-grid textarea:focus,
.point-row input:focus {
  border-color: var(--hermes-violet);
  box-shadow: 0 0 0 3px rgba(115, 88, 216, .13);
}

.composer .ant-btn {
  flex-shrink: 0;
  border-radius: 9px;
}

.composer-note,
.draft-note {
  margin: -10px 24px 19px;
  color: #9991a4;
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
  color: var(--hermes-violet);
  font-size: 20px;
}

.failure-card .card-heading :deep(.anticon) {
  color: var(--hermes-coral);
}

.quality-score {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 20px;
}

.quality-score strong {
  font-size: 42px;
  letter-spacing: -.06em;
}

.quality-score span {
  color: #928999;
  font-size: 13px;
}

.quality-bar {
  height: 7px;
  margin: 9px 0 17px;
  overflow: hidden;
  border-radius: 99px;
  background: #e9e4ee;
}

.quality-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--hermes-violet), var(--hermes-mint));
  transition: width .35s ease;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding-top: 13px;
  border-top: 1px solid #eeeaf2;
}

.quality-grid div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.quality-grid span {
  color: #928999;
  font-size: 11px;
}

.quality-grid b {
  font-size: 17px;
}

.quality-card .text-action {
  margin-top: 20px;
}

.card-description {
  margin: 12px 0 15px;
  color: #8d8597;
  font-size: 12px;
  line-height: 1.6;
}

.failure-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.failure-row {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 9px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #f7f4f8;
}

.failure-row.selected {
  border-color: #c9bde9;
  background: #f2effb;
}

.failure-main {
  display: flex;
  flex: 1;
  gap: 9px;
  align-items: center;
  min-width: 0;
  padding: 0;
  color: var(--hermes-ink);
  text-align: left;
}

.failure-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 3px;
}

.failure-info strong,
.failure-info small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.failure-info strong {
  font-size: 12px;
}

.failure-info small {
  color: #98909f;
  font-size: 10px;
}

.diagnose-action {
  flex-shrink: 0;
  padding: 3px 5px;
  color: var(--hermes-violet);
  font-size: 11px;
}

.diagnose-action:hover:not(:disabled) {
  color: var(--hermes-ink);
}

.failure-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 11px;
  border-top: 1px solid #eeeaf2;
}

.failure-footer :deep(.ant-btn) {
  padding-right: 0;
  padding-left: 0;
  font-size: 12px;
}

.diagnosis-result,
.plan-draft-card {
  padding: 23px 26px;
}

.diagnosis-result {
  border-left: 4px solid var(--hermes-coral);
}

.diagnosis-summary,
.plan-draft-heading p {
  margin: 14px 0 0;
  color: #5d5366;
  line-height: 1.7;
}

.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.suggestion-card {
  padding: 13px;
  border: 1px solid #ebe4ee;
  border-radius: 11px;
  background: #fff;
}

.suggestion-card > span,
.suggestion-card small {
  color: #94899d;
  font-size: 11px;
}

.suggestion-card strong {
  display: block;
  margin-top: 5px;
  font-size: 13px;
}

.suggestion-card p {
  margin: 8px 0;
  color: #5d5366;
  font-size: 12px;
  line-height: 1.6;
}

.diagnosis-source {
  margin-top: 17px;
}

.plan-draft-card {
  border-top: 4px solid var(--hermes-mint);
}

.plan-draft-heading {
  align-items: flex-start;
}

.plan-draft-heading p {
  margin-bottom: 0;
  color: #8d8495;
  font-size: 12px;
}

.plan-form-grid {
  display: grid;
  grid-template-columns: .8fr 1.2fr;
  gap: 14px;
  margin-top: 21px;
}

.plan-form-grid label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #786e81;
  font-size: 12px;
  font-weight: 700;
}

.plan-form-grid textarea {
  resize: vertical;
}

.plan-points {
  margin-top: 18px;
}

.points-heading {
  justify-content: space-between;
  margin-bottom: 9px;
  color: #786e81;
  font-size: 12px;
  font-weight: 700;
}

.point-row {
  display: flex;
  gap: 9px;
  align-items: center;
  margin-top: 7px;
}

.point-row > span {
  width: 25px;
  color: var(--hermes-violet);
  font-size: 11px;
  font-weight: 800;
}

.icon-action {
  flex: 0 0 26px;
  width: 26px;
  height: 26px;
  color: #9b91a4;
  border-radius: 7px;
}

.icon-action:hover {
  color: #bd6958;
  background: #fff0ed;
}

.plan-draft-card .draft-note {
  margin: 15px 0 0;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
:deep(.ant-select-selector:focus-visible) {
  outline: 3px solid rgba(115, 88, 216, .28);
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
    padding: 25px 20px;
  }

  .hero-title-row,
  .context-strip,
  .plan-draft-heading {
    display: block;
  }

  .hero-chip {
    display: inline-block;
    margin-top: 11px;
  }

  .hero-controls {
    margin-top: 24px;
  }

  .context-metrics {
    margin-top: 14px;
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
    padding-right: 17px;
    padding-left: 17px;
  }

  .message-list {
    padding: 17px;
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
