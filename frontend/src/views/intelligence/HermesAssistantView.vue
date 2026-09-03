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

      <section v-if="governanceSummary" class="governance-card" :aria-label="t('hermes.governance_aria')">
        <div class="governance-heading">
          <div>
            <span class="section-kicker">{{ t('hermes.governance_kicker') }}</span>
            <h2>{{ t('hermes.governance_title') }}</h2>
          </div>
          <div class="governance-meta">
            <span class="governance-version">{{ governanceSummary.prompt_version }}</span>
            <span>{{ t('hermes.governance_eval_set', { size: governanceSummary.evaluation_set.size, version: governanceSummary.evaluation_set.version }) }}</span>
          </div>
        </div>
        <div class="governance-metrics">
          <div class="governance-metric governance-metric-citation">
            <strong>{{ governanceRate(governanceSummary.citation_coverage) }}</strong>
            <span>{{ t('hermes.governance_citation') }}</span>
          </div>
          <div class="governance-metric governance-metric-refusal">
            <strong>{{ governanceRate(governanceSummary.refusal_rate) }}</strong>
            <span>{{ t('hermes.governance_refusal') }}</span>
          </div>
          <div class="governance-metric">
            <strong>{{ governanceSummary.average_latency_ms }}<small>ms</small></strong>
            <span>{{ t('hermes.governance_latency') }}</span>
          </div>
          <div class="governance-metric">
            <strong>{{ governanceRate(governanceSummary.helpful_rate) }}</strong>
            <span>{{ t('hermes.governance_helpful') }}</span>
          </div>
        </div>
        <div class="governance-footer">
          <span>{{ t('hermes.governance_activity', { sessions: governanceSummary.sessions, messages: governanceSummary.assistant_messages }) }}</span>
          <span>{{ t('hermes.governance_feedback', { count: governanceSummary.feedback_total }) }}</span>
          <span v-if="!governanceSummary.cost_tracking.available" class="governance-cost-note">{{ t('hermes.governance_cost_unavailable') }}</span>
        </div>
      </section>

      <section class="conversation-context-card" :aria-label="t('hermes.conversation_context_aria')">
        <div class="conversation-context-heading">
          <div>
            <span class="section-kicker">{{ t('hermes.session_kicker') }}</span>
            <strong>{{ t('hermes.session_id', { id: shortConversationId }) }}</strong>
            <p>{{ t('hermes.session_description') }}</p>
          </div>
          <a-button size="small" @click="startNewConversation">
            <PlusOutlined /> {{ t('hermes.new_conversation') }}
          </a-button>
        </div>
        <div class="conversation-filter-grid">
          <div class="conversation-filter">
            <label for="hermes-source-filter">{{ t('hermes.source_filter') }}</label>
            <a-select
              id="hermes-source-filter"
              v-model:value="sourceTypes"
              mode="multiple"
              :options="sourceTypeOptions"
              :max-tag-count="1"
              allow-clear
              :placeholder="t('hermes.source_filter_placeholder')"
            />
          </div>
          <div class="conversation-filter">
            <label for="hermes-date-filter">{{ t('hermes.date_filter') }}</label>
            <a-range-picker
              id="hermes-date-filter"
              v-model:value="(dateRange as [Dayjs, Dayjs] | undefined)"
              :placeholder="[t('hermes.date_from'), t('hermes.date_to')]"
              allow-clear
            />
          </div>
          <div class="conversation-filter">
            <label for="hermes-context-budget">{{ t('hermes.context_budget') }}</label>
            <a-select id="hermes-context-budget" v-model:value="contextBudget" :options="contextBudgetOptions" />
          </div>
        </div>
        <div class="conversation-context-status">
          <span class="status-dot" />
          <span>{{ t('hermes.context_status', { used: historyUsed, omitted: historyOmitted, chars: contextChars, budget: contextBudget }) }}</span>
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
                <span v-if="message.mode" class="message-mode">{{ modeLabel(message.mode) }}</span>
                <div v-if="message.toolSteps?.length" class="message-tool-chain">
                  <span class="tool-chain-label">{{ t('hermes.tool_chain') }}</span>
                  <span v-for="step in message.toolSteps" :key="`${message.id}-${step.tool}`" class="tool-chain-step">
                    {{ toolLabel(step.tool) }} · {{ toolStatusLabel(step.status) }}
                  </span>
                </div>
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
                <a-space v-if="message.role === 'assistant' && message.backendIndex != null" size="small">
                  <a-button type="text" size="small" @click="rateMessage(message, 'helpful')">{{ t('hermes.helpful') }}</a-button>
                  <a-button type="text" size="small" @click="rateMessage(message, 'not_helpful')">{{ t('hermes.not_helpful') }}</a-button>
                </a-space>
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
            <div class="draft-status-line">
              <span class="draft-status-dot" :class="{ confirmed: draftConfirmed }" />
              <strong>{{ draftConfirmed ? t('hermes.plan_status_confirmed') : t('hermes.plan_status_review') }}</strong>
              <span>·</span>
              <span>{{ t('hermes.plan_change_count', { count: draftChangedCount }) }}</span>
            </div>
          </div>
          <a-space>
            <a-button :loading="savingDraft" @click="savePlanDraft">{{ t('hermes.confirm_save_draft') }}</a-button>
            <a-button type="primary" @click="confirmPlanDraft">
              <ArrowRightOutlined /> {{ draftConfirmed ? t('hermes.open_plans') : t('hermes.confirm_plan_draft') }}
            </a-button>
          </a-space>
        </div>
        <div class="plan-form-grid">
          <label>
            <span>{{ t('hermes.plan_name') }}</span>
            <input v-model="planDraft.name" maxlength="256" />
          </label>
          <label>
            <span>{{ t('hermes.plan_objective') }}</span>
            <textarea v-model="planDraft.objective" maxlength="2000" rows="3" />
          </label>
        </div>
        <div class="plan-points">
          <div class="points-heading">
            <span>{{ t('hermes.plan_points') }}</span>
            <button type="button" class="text-action" @click="addPlanPoint"><PlusOutlined /> {{ t('hermes.add_point') }}</button>
          </div>
          <div v-for="(_, index) in planDraft.testPoints" :key="`point-${index}`" class="point-row">
            <span>{{ String(index + 1).padStart(2, '0') }}</span>
            <input v-model="planDraft.testPoints[index]" maxlength="512" />
            <button type="button" class="icon-action" :aria-label="t('hermes.remove_point')" @click="removePlanPoint(index)"><CloseOutlined /></button>
          </div>
        </div>
        <div class="draft-impact-grid">
          <div><span>{{ t('hermes.plan_impact_modules') }}</span><strong>{{ selectedDraftModuleCount }}</strong></div>
          <div><span>{{ t('hermes.plan_impact_cases') }}</span><strong>{{ selectedDraftCaseCount }}</strong></div>
          <div><span>{{ t('hermes.plan_impact_regression') }}</span><strong>{{ selectedDraftRegressionCount }}</strong></div>
          <div><span>{{ t('hermes.plan_impact_failures') }}</span><strong>{{ failedTasks.length }}</strong></div>
        </div>
        <div class="draft-structure-grid">
          <section class="draft-block">
            <div class="draft-block-heading">
              <span>{{ t('hermes.plan_scope_modules') }}</span>
              <small>{{ t('hermes.plan_scope_hint') }}</small>
            </div>
            <div v-for="module in planDraft.scopeModules" :key="module.id" class="draft-check-row">
              <input v-model="module.selected" type="checkbox" />
              <button type="button" class="draft-item-link" @click="openPath(module.path)">{{ module.name }} <ArrowRightOutlined /></button>
            </div>
            <p v-if="!planDraft.scopeModules.length" class="draft-empty">{{ t('hermes.plan_no_modules') }}</p>
          </section>
          <section class="draft-block">
            <div class="draft-block-heading">
              <span>{{ t('hermes.plan_case_drafts') }}</span>
              <small>{{ t('hermes.plan_case_hint') }}</small>
            </div>
            <div v-for="item in planDraft.caseDrafts" :key="item.id" class="draft-case-row">
              <label class="draft-check-row">
                <input v-model="item.selected" type="checkbox" />
              </label>
              <button type="button" class="draft-item-link" @click="openPath(item.path)">{{ item.id }} <ArrowRightOutlined /></button>
              <input v-model="item.title" class="draft-case-title" maxlength="256" :aria-label="t('hermes.plan_case_title')" />
              <input v-model="item.expected" class="draft-case-expected" maxlength="512" :aria-label="t('hermes.plan_case_expected')" />
            </div>
            <p v-if="!planDraft.caseDrafts.length" class="draft-empty">{{ t('hermes.plan_no_cases') }}</p>
          </section>
        </div>
        <div class="draft-structure-grid">
          <section class="draft-block">
            <div class="draft-block-heading">
              <span>{{ t('hermes.plan_regression_scope') }}</span>
              <small>{{ t('hermes.plan_regression_hint') }}</small>
            </div>
            <label v-for="item in planDraft.regressionScope" :key="item.taskId" class="draft-regression-row">
              <input v-model="item.selected" type="checkbox" />
              <span class="draft-regression-copy"><strong>{{ item.name }}</strong><small>{{ item.reason }}</small></span>
              <button type="button" class="text-action" @click="openPath(item.path)">{{ t('hermes.view_evidence') }}</button>
            </label>
            <p v-if="!planDraft.regressionScope.length" class="draft-empty">{{ t('hermes.plan_no_regressions') }}</p>
          </section>
          <section class="draft-block draft-diff-block">
            <div class="draft-block-heading">
              <span>{{ t('hermes.plan_diff_title') }}</span>
              <small>{{ t('hermes.plan_diff_hint') }}</small>
            </div>
            <div v-for="row in planDraftDiffRows" :key="row.key" class="draft-diff-row" :class="{ changed: row.changed }">
              <strong>{{ row.label }}</strong>
              <div><small>{{ t('hermes.plan_diff_before') }}</small><span>{{ row.before }}</span></div>
              <div><small>{{ t('hermes.plan_diff_after') }}</small><span>{{ row.after }}</span></div>
            </div>
          </section>
        </div>
        <div class="draft-sources">
          <span class="source-label">{{ t('hermes.plan_sources') }}</span>
          <button v-for="item in planDraft.sources" :key="item.path" type="button" class="source-link" @click="openSource(item)">
            {{ item.label }} <ArrowRightOutlined />
          </button>
        </div>
        <p class="draft-note"><BulbOutlined /> {{ t('hermes.plan_draft_note') }}</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
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

type HermesSource = { label: string; path: string }
type HermesMessage = {
  id: number
  role: 'assistant' | 'user'
  text: string
  createdAt: string
  sources?: HermesSource[]
  taskIds?: string[]
  mode?: HermesQueryResult['mode']
  toolSteps?: Array<{ tool: string; status: string }>
  isWelcome?: boolean
  backendIndex?: number
}
type PromptKey = 'failed_tasks' | 'explain_failure' | 'test_plan' | 'quality'
type DraftModule = { id: number; name: string; selected: boolean; path: string }
type DraftCase = { id: number; title: string; expected: string; selected: boolean; path: string }
type DraftRegressionItem = { taskId: string; name: string; reason: string; selected: boolean; path: string }
type HermesPlanDraftHandoff = {
  projectId: number
  name: string
  objective: string
  testPoints: string[]
  moduleIds: number[]
  caseIds: number[]
  regressionTaskIds: string[]
}
type PlanDraftSnapshot = {
  name: string
  objective: string
  testPoints: string[]
  moduleNames: string[]
  caseTitles: string[]
  regressionTaskIds: string[]
  regressionTaskNames: string[]
}
type PlanDraft = {
  name: string
  objective: string
  testPoints: string[]
  scopeModules: DraftModule[]
  caseDrafts: DraftCase[]
  regressionScope: DraftRegressionItem[]
  sources: HermesSource[]
  baseline: PlanDraftSnapshot
}

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
const diagnosis = ref<{ taskId: string; result: FailureDiagnosisResult } | null>(null)
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
const selectedDraftModuleCount = computed(() => planDraft.value?.scopeModules.filter((item) => item.selected).length ?? 0)
const selectedDraftCaseCount = computed(() => planDraft.value?.caseDrafts.filter((item) => item.selected).length ?? 0)
const selectedDraftRegressionCount = computed(() => planDraft.value?.regressionScope.filter((item) => item.selected).length ?? 0)
const planDraftDiffRows = computed(() => {
  const draft = planDraft.value
  if (!draft) return []
  const current = {
    name: draft.name,
    objective: draft.objective,
    testPoints: draft.testPoints,
    moduleNames: draft.scopeModules.filter((item) => item.selected).map((item) => item.name),
    caseTitles: draft.caseDrafts.filter((item) => item.selected).map((item) => item.title.trim()).filter(Boolean),
    regressionTaskIds: draft.regressionScope.filter((item) => item.selected).map((item) => item.taskId),
    regressionTaskNames: draft.regressionScope.filter((item) => item.selected).map((item) => item.name),
  }
  const display = (value: string | string[]) => Array.isArray(value)
    ? value.join('、') || t('hermes.plan_none_selected')
    : value.trim() || t('hermes.plan_not_filled')
  return [
    { key: 'name', label: t('hermes.plan_diff_name'), before: display(draft.baseline.name), after: display(current.name), changed: draft.baseline.name !== current.name },
    { key: 'objective', label: t('hermes.plan_diff_objective'), before: display(draft.baseline.objective), after: display(current.objective), changed: draft.baseline.objective !== current.objective },
    { key: 'testPoints', label: t('hermes.plan_diff_points'), before: display(draft.baseline.testPoints), after: display(current.testPoints), changed: JSON.stringify(draft.baseline.testPoints) !== JSON.stringify(current.testPoints) },
    { key: 'modules', label: t('hermes.plan_diff_modules'), before: display(draft.baseline.moduleNames), after: display(current.moduleNames), changed: JSON.stringify(draft.baseline.moduleNames) !== JSON.stringify(current.moduleNames) },
    { key: 'cases', label: t('hermes.plan_diff_cases'), before: display(draft.baseline.caseTitles), after: display(current.caseTitles), changed: JSON.stringify(draft.baseline.caseTitles) !== JSON.stringify(current.caseTitles) },
    { key: 'regression', label: t('hermes.plan_diff_regression'), before: display(draft.baseline.regressionTaskNames), after: display(current.regressionTaskNames), changed: JSON.stringify(draft.baseline.regressionTaskIds) !== JSON.stringify(current.regressionTaskIds) },
  ]
})
const draftChangedCount = computed(() => planDraftDiffRows.value.filter((row) => row.changed).length)
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

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : t('hermes.not_available')
}

function governanceRate(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function newConversationId() {
  const randomPart = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `hermes-${selectedProjectId.value || 'none'}-${randomPart}`
}

function modeLabel(mode: HermesQueryResult['mode']) {
  return t(`hermes.modes.${mode}`)
}

function toolLabel(tool: string) {
  return t(`hermes.tool_labels.${tool}`)
}

function toolStatusLabel(status: string) {
  return t(`hermes.tool_status.${status}`)
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
  loadError.value = failures.join('；')
  resetConversation()
  try {
    const sessions = await hermesApi.sessions(projectId)
    const latest = sessions[0]
    if (latest) {
      sessionId.value = latest.id
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
            backendIndex: role === 'assistant' ? index : undefined,
          }
        })
        .filter((item): item is HermesMessage => item !== null)
      if (restored.length) messages.value = restored
    }
  } catch {
    failures.push(t('hermes.load_sessions_failed'))
  }
  loadError.value = failures.join('；')
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
    const draft = planDraft.value
    const handoff: HermesPlanDraftHandoff = {
      projectId: selectedProjectId.value,
      name: draft.name.trim().slice(0, 256),
      objective: draft.objective.trim().slice(0, 2000),
      testPoints: draft.testPoints.map((point) => point.trim().slice(0, 512)).filter(Boolean).slice(0, 16),
      moduleIds: draft.scopeModules.filter((item) => item.selected).map((item) => item.id).slice(0, 16),
      caseIds: draft.caseDrafts.filter((item) => item.selected).map((item) => item.id).slice(0, 16),
      regressionTaskIds: draft.regressionScope.filter((item) => item.selected).map((item) => item.taskId).slice(0, 16),
    }
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
      appendMessage('assistant', result.clarification || result.answer)
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
.governance-card,
.conversation-context-card,
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

.governance-card {
  position: relative;
  overflow: hidden;
  padding: 17px 20px 15px;
  border-radius: var(--radius-lg);
  background:
    linear-gradient(100deg, color-mix(in srgb, var(--c-ai) 7%, var(--c-bg-elevated)), var(--c-bg-elevated) 58%),
    var(--c-bg-elevated);
}

.governance-card::after {
  position: absolute;
  top: -44px;
  right: 7%;
  width: 140px;
  height: 140px;
  border: 1px solid color-mix(in srgb, var(--c-ai) 22%, transparent);
  border-radius: 50%;
  content: '';
  pointer-events: none;
}

.governance-heading,
.governance-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.governance-meta,
.governance-footer {
  color: var(--c-text-tertiary);
  font-size: 10px;
}

.governance-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
  text-align: right;
}

.governance-version {
  padding: 3px 7px;
  color: var(--c-ai);
  border: 1px solid color-mix(in srgb, var(--c-ai) 30%, transparent);
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--c-ai) 9%, transparent);
  font-family: 'JetBrains Mono', monospace;
}

.governance-metrics {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.governance-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
  border-left: 2px solid var(--c-border-strong);
  background: color-mix(in srgb, var(--c-bg-subtle) 68%, transparent);
}

.governance-metric strong {
  color: var(--c-text);
  font-size: 21px;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -.04em;
}

.governance-metric strong small {
  margin-left: 2px;
  color: var(--c-text-tertiary);
  font-size: 10px;
  letter-spacing: 0;
}

.governance-metric span {
  overflow: hidden;
  color: var(--c-text-tertiary);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.governance-metric-citation { border-left-color: var(--c-success); }
.governance-metric-refusal { border-left-color: var(--c-warning); }

.governance-footer {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--c-border);
}

.governance-cost-note {
  margin-left: auto;
  color: var(--c-warning);
}

.conversation-context-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  background:
    linear-gradient(110deg, color-mix(in srgb, var(--c-ai) 5%, var(--c-bg-elevated)), var(--c-bg-elevated));
}

.conversation-context-heading,
.conversation-context-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.conversation-context-heading strong {
  display: block;
  margin-top: 4px;
  color: var(--c-text);
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
}

.conversation-context-heading p {
  margin: 5px 0 0;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.conversation-context-heading :deep(.ant-btn) {
  flex: 0 0 auto;
  border-color: var(--c-border-strong);
  border-radius: var(--radius-md);
}

.conversation-filter-grid {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(240px, 1.2fr) minmax(150px, .7fr);
  gap: 12px;
}

.conversation-filter {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.conversation-filter label {
  color: var(--c-text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
}

.conversation-filter :deep(.ant-select),
.conversation-filter :deep(.ant-picker) {
  width: 100%;
}

.conversation-context-status {
  justify-content: flex-start;
  color: var(--c-text-secondary);
  font-size: 11px;
}

.conversation-context-status .status-dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
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

.message-mode {
  display: inline-flex;
  margin-top: 8px;
  padding: 3px 8px;
  border: 1px solid var(--c-primary-glow);
  border-radius: 999px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
}

.message-tool-chain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 9px;
  color: var(--c-text-tertiary);
  font-size: 10px;
}

.tool-chain-label {
  color: var(--c-ai);
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: .04em;
  text-transform: uppercase;
}

.tool-chain-step {
  padding: 3px 7px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-full);
  background: var(--c-bg-subtle);
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

.plan-draft-heading :deep(.ant-btn) {
  flex: 0 0 auto;
}

.draft-status-line {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 12px;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.draft-status-line strong {
  color: var(--c-ai);
  font-size: 11px;
}

.draft-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-warning);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-warning) 12%, transparent);
}

.draft-status-dot.confirmed {
  background: var(--c-success);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-success) 12%, transparent);
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

.draft-impact-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.draft-impact-grid > div {
  display: grid;
  gap: 4px;
  padding: 11px 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
}

.draft-impact-grid span,
.draft-block-heading small,
.draft-diff-row small {
  color: var(--c-text-tertiary);
  font-size: 10px;
}

.draft-impact-grid strong {
  color: var(--c-text);
  font-size: 18px;
  font-family: 'JetBrains Mono', monospace;
}

.draft-structure-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.draft-block {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--c-bg-subtle) 72%, var(--c-bg-elevated));
}

.draft-block-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.draft-block-heading small {
  font-weight: 400;
  text-align: right;
}

.draft-check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 7px 0;
  color: var(--c-text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.draft-check-row input,
.draft-regression-row > input {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
  accent-color: var(--c-ai);
}

.draft-item-link {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 4px;
  padding: 0;
  overflow: hidden;
  border: 0;
  background: transparent;
  color: var(--c-ai);
  font: inherit;
  font-size: 11px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.draft-item-link:hover {
  color: var(--c-text);
}

.draft-item-link:focus-visible {
  outline: 2px solid var(--c-ai);
  outline-offset: 2px;
}

.draft-case-row {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: 7px 9px;
  align-items: center;
  padding: 7px 0;
  border-top: 1px solid var(--c-border);
}

.draft-case-row:first-of-type {
  border-top: 0;
}

.draft-case-row .draft-check-row {
  grid-row: span 2;
  padding: 0;
}

.draft-case-title {
  grid-column: 3;
}

.draft-case-expected {
  grid-column: 2 / -1;
}

.draft-case-row > input {
  min-width: 0;
  padding: 6px 8px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
  color: var(--c-text);
  font-size: 11px;
}

.draft-regression-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--c-border);
}

.draft-regression-row:first-of-type {
  border-top: 0;
}

.draft-regression-copy {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: 3px;
}

.draft-regression-copy strong,
.draft-regression-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.draft-regression-copy strong {
  color: var(--c-text);
  font-size: 12px;
}

.draft-regression-copy small {
  color: var(--c-text-tertiary);
  font-size: 10px;
}

.draft-empty {
  margin: 10px 0 0;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.draft-diff-row {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  padding: 8px 0;
  border-top: 1px solid var(--c-border);
}

.draft-diff-row:first-of-type {
  border-top: 0;
}

.draft-diff-row > strong {
  color: var(--c-text-secondary);
  font-size: 11px;
}

.draft-diff-row > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.draft-diff-row > div span {
  overflow: hidden;
  color: var(--c-text-secondary);
  font-size: 11px;
  line-height: 1.45;
  text-overflow: ellipsis;
}

.draft-diff-row.changed > div:last-child span {
  color: var(--c-ai);
  font-weight: 600;
}

.draft-sources {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border);
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
  .governance-heading,
  .conversation-context-heading,
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

  .governance-meta {
    justify-content: flex-start;
    margin-top: 10px;
    text-align: left;
  }

  .governance-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .governance-cost-note {
    margin-left: 0;
  }

  .conversation-context-heading :deep(.ant-btn) {
    margin-top: 10px;
  }

  .conversation-filter-grid {
    grid-template-columns: 1fr;
  }

  .evidence-column,
  .prompt-grid,
  .plan-form-grid,
  .draft-impact-grid,
  .draft-structure-grid {
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

  .draft-diff-row {
    grid-template-columns: 1fr;
  }

  .draft-diff-row > strong {
    margin-bottom: -2px;
  }
}
</style>
