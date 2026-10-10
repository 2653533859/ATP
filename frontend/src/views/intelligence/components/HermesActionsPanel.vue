<template>
  <section class="assistant-actions">
    <span>{{ t('hermes.actions.title') }}</span>
    <button v-for="item in actions" :key="item" type="button" @click="openAction(item)">{{ t(`hermes.actions.${item}`) }}</button>
  </section>
  <details v-if="history.length" class="action-history">
    <summary>{{ t('hermes.actions.history') }} · {{ history.length }}</summary>
    <p>{{ t('hermes.actions.history_scope') }}</p>
    <a-alert v-if="historyError" type="warning" :message="historyError" />
    <a-button :loading="historyLoading" @click="refreshHistory">{{ t('hermes.actions.refresh_history') }}</a-button>
    <div v-for="item in history" :key="item.id">
      <span>{{ t(`hermes.actions.${item.action}`) }}{{ item.resourceId ? ` #${item.resourceId}` : '' }} · {{ new Date(item.createdAt).toLocaleString() }} · {{ t(`hermes.actions.status_${item.status}`) }}</span>
      <span v-if="item.runStatus">{{ t(`hermes.actions.run_${item.runStatus}`) }}</span>
      <a-tag v-if="item.dispatchStatus" :color="['uncertain', 'blocked'].includes(item.dispatchStatus) ? 'orange' : 'blue'">{{ t(`hermes.actions.dispatch_${item.dispatchStatus}`) }}</a-tag>
      <a-button type="link" @click="router.push(item.path)">{{ t('hermes.actions.open_result') }}</a-button>
    </div>
  </details>
  <a-drawer v-model:open="opened" :title="t(`hermes.actions.${kind}`)" :width="Math.min(720, windowWidth)" :closable="!busy" :mask-closable="!busy" :keyboard="!busy">
    <a-alert type="info" show-icon :message="t('hermes.actions.preview_hint')" class="action-alert" />
    <a-alert v-if="error" type="error" show-icon :message="error" class="action-alert" />
    <a-form layout="vertical" :disabled="busy || applied">
      <a-form-item v-if="['record', 'repair', 'android'].includes(kind)" :label="t('hermes.actions.case')">
        <a-select v-model:value="caseId" :options="caseOptions" show-search :filter-option="filterOption" />
      </a-form-item>
      <a-form-item v-if="kind === 'api'" :label="t('hermes.actions.module')"><a-select v-model:value="moduleId" :options="moduleOptions" /></a-form-item>
      <a-form-item v-if="kind === 'api'" :label="t('hermes.actions.schema_type')">
        <a-select v-model:value="schemaType" :options="schemaOptions" />
      </a-form-item>
      <a-form-item v-if="kind === 'api'" :label="t('hermes.actions.schema')"><a-textarea v-model:value="schemaText" :rows="5" /></a-form-item>
      <a-form-item v-if="['record', 'repair'].includes(kind)" :label="t('hermes.actions.expected_text')"><a-input v-model:value="expectedText" /></a-form-item>
      <template v-if="kind === 'repair'">
        <a-form-item :label="t('hermes.actions.failure_run')"><a-select v-model:value="runId" :options="repairFailureOptions" /></a-form-item>
        <a-button :disabled="!runId || !caseId" :loading="busy" @click="diagnoseRepair">{{ t('hermes.actions.diagnose') }}</a-button>
        <pre v-if="diagnosisText" class="diagnosis-text">{{ diagnosisText }}</pre>
        <a-form-item :label="t('hermes.actions.old_locator')"><a-input v-model:value="oldLocator" /></a-form-item>
        <a-form-item :label="t('hermes.actions.new_locator')"><a-input v-model:value="newLocator" /></a-form-item>
      </template>
      <a-form-item v-if="kind === 'regression'" :label="t('hermes.actions.cases')"><a-select v-model:value="selectedIds" mode="multiple" :options="regressionOptions" show-search :filter-option="filterOption" /></a-form-item>
      <a-form-item v-if="['regression', 'android'].includes(kind)" :label="t('hermes.actions.environment')"><a-select v-model:value="envId" allow-clear :options="environmentOptions" :placeholder="t('hermes.actions.no_environment')" /></a-form-item>
      <a-form-item v-if="kind === 'defect'" :label="t('hermes.actions.failure_run')"><a-select v-model:value="runId" :options="failureOptions" /></a-form-item>
      <a-form-item v-if="['regression', 'defect', 'knowledge'].includes(kind)" :label="t('hermes.actions.name')"><a-input v-model:value="name" /></a-form-item>
      <a-form-item v-if="['api', 'knowledge', 'regression', 'defect'].includes(kind)" :label="t('hermes.actions.requirement')"><a-textarea v-model:value="requirement" :auto-size="{ minRows: 3, maxRows: 8 }" /></a-form-item>
      <a-form-item v-if="kind === 'summary'" :label="t('hermes.actions.days')"><a-input-number v-model:value="days" :min="1" :max="30" /></a-form-item>
      <a-button :loading="busy" :disabled="applied" @click="prepare">{{ t('hermes.actions.prepare') }}</a-button>
    </a-form>
    <section v-if="proposal" class="proposal">
      <h3>{{ t('hermes.actions.preview') }}</h3>
      <a-alert v-for="note in proposal.notes" :key="note" type="info" :message="note" class="action-alert" />
      <pre>{{ proposal.preview }}</pre>
      <template v-if="webSteps.length">
        <h4>{{ t('hermes.actions.edit_steps') }}</h4>
        <a-form-item :label="t('hermes.actions.timeout_seconds')"><a-input-number v-if="proposal.config" :value="typeof proposal.config.timeout === 'number' ? proposal.config.timeout : undefined" :min="1" :max="600" :disabled="busy || applied" @update:value="value => { if (proposal?.config) proposal.config.timeout = value }" /></a-form-item>
        <div :inert="busy || applied"><LowcodeStepEditor :model-value="webSteps" :project-id="projectId" @update:model-value="updateWebSteps" /></div>
      </template>
      <template v-if="proposal.cases">
        <a-card v-for="(draft, index) in proposal.cases" :key="index" size="small" class="draft-card">
          <a-input v-model:value="draft.name" :disabled="busy || applied" :aria-label="t('hermes.actions.name')" />
          <p>{{ draft.summary }}</p>
          <HermesApiDraftEditor v-if="draft.config" :model-value="draft.config" :disabled="busy || applied" @update:model-value="value => draft.config = value" />
          <ol><li v-for="(step, number) in draft.steps" :key="number">{{ step.action }} → {{ step.expected_result }}</li></ol>
          <details><summary>{{ t('hermes.actions.request_details') }}</summary><pre>{{ JSON.stringify(draft.config, null, 2) }}</pre></details>
          <a-checkbox v-model:checked="draftSelections[index]" :disabled="busy || applied">{{ t('hermes.actions.save_this') }}</a-checkbox>
        </a-card>
      </template>
      <template v-if="!applied">
        <a-checkbox v-if="kind !== 'summary'" v-model:checked="confirmed">{{ t('hermes.actions.confirm') }}</a-checkbox>
        <div class="proposal-buttons">
          <a-button v-if="kind === 'summary'" @click="downloadSummary">{{ t('hermes.actions.download') }}</a-button>
          <a-button v-else type="primary" :disabled="!confirmed || submissionStarted" :loading="busy" @click="applyProposal">{{ t('hermes.actions.apply') }}</a-button>
        </div>
      </template>
      <a-alert v-if="applied" type="success" :message="t('hermes.actions.done')" />
      <a-button v-if="resultPath" type="link" @click="router.push(resultPath)">{{ t('hermes.actions.open_result') }}</a-button>
      <template v-if="createdSuiteId && !startedRun">
        <a-divider />
        <a-checkbox v-model:checked="executionConfirmed">{{ t('hermes.actions.confirm_run') }}</a-checkbox>
        <a-button :disabled="!executionConfirmed || runSubmissionStarted" :loading="busy" @click="runCreatedSuite">{{ t('hermes.actions.run_suite') }}</a-button>
      </template>
    </section>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  aiCaseGenerationApi, apkApi, caseApi, defectApi, deviceApi, environmentApi, knowledgeApi, projectApi,
  reportApi, runApi, suiteApi, workbenchApi,
  type CaseDetailItem, type CaseSavePayload, type CaseSummaryItem, type ModuleTreeItem,
  type SchemaSourceType, type WorkbenchTaskItem,
} from '@/api'
import { recordingErrorMessage } from '@/utils/webRecording'
import LowcodeStepEditor from '@/components/common/LowcodeStepEditor.vue'
import HermesApiDraftEditor from './HermesApiDraftEditor.vue'
import { useAuthStore } from '@/stores/auth'
import { normalizeDispatchStatus, readActionHistory, writeActionHistory, type HermesActionReceipt } from '@/utils/hermesActionHistory'
import http from '@/api/http'

const props = defineProps<{ projectId: number; canModify: boolean; latestAnswer: string }>()
const emit = defineEmits<{ completed: [text: string, path?: string] }>()
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const historyUserId = auth.user?.id
const history = ref<HermesActionReceipt[]>(historyUserId ? readActionHistory(historyUserId, props.projectId) : [])
const historyLoading = ref(false)
const historyError = ref('')
async function refreshHistory() {
  if (historyLoading.value) return
  historyLoading.value = true
  historyError.value = ''
  try {
    const persisted = await http.get<unknown, Array<{ command_id: string; action: string; resource_id: number; created_at: string; run_status?: string; resource_missing?: boolean; resource_unverified?: boolean; dispatch_status?: string }>>('/hermes/action-records', { params: { project_id: props.projectId } })
    if (!live || auth.user?.id !== historyUserId) return
    const ids = new Set(persisted.map(item => item.command_id))
    history.value = [...persisted.map(item => ({ id: item.command_id, action: 'regression', status: 'completed' as const, resourceId: item.resource_id, createdAt: item.created_at, path: `/suites?project_id=${props.projectId}`, runStatus: item.resource_unverified ? 'unverified' : item.resource_missing ? 'missing' : item.run_status || undefined, dispatchStatus: normalizeDispatchStatus(item.dispatch_status) })), ...history.value.filter(item => !ids.has(item.id))].slice(0, 20)
    saveHistory()
  } catch (reason) { if (live) historyError.value = recordingErrorMessage(reason, t('hermes.actions.failed')) }
  finally { historyLoading.value = false }
}
watch(() => auth.user?.id, userId => { if (userId !== historyUserId) history.value = [] })
function saveHistory() {
  if (historyUserId && auth.user?.id === historyUserId && !writeActionHistory(historyUserId, props.projectId, history.value)) error.value = t('hermes.actions.history_unavailable')
}
function startReceipt(action: string): string {
  const id = crypto.randomUUID()
  const path = action === 'knowledge' ? '/knowledge' : action === 'defect' ? '/bugs' : action === 'regression' ? '/suites' : '/cases'
  const receipt: HermesActionReceipt = { id, action, status: 'pending', createdAt: new Date().toISOString(), path: `${path}?project_id=${props.projectId}` }
  history.value = [receipt, ...history.value].slice(0, 20)
  saveHistory(); return id
}
function finishReceipt(id: string, status: HermesActionReceipt['status'], path?: string, resourceId?: number) {
  const receipt = history.value.find(item => item.id === id)
  if (receipt) { receipt.status = status; if (path) receipt.path = path; if (resourceId) receipt.resourceId = resourceId; saveHistory() }
}
const actions = ['record', 'api', 'regression', 'repair', 'android', 'defect', 'knowledge', 'summary'] as const
type Action = typeof actions[number]
type Step = { action: string; name?: string; params: Record<string, unknown> }
interface Proposal {
  preview: string; notes: string[]; baseline?: CaseDetailItem; config?: Record<string, unknown>
  cases?: CaseSavePayload[]; caseIds?: number[]; runId?: number; title?: string; content?: string
}
const opened = ref(false)
const kind = ref<Action>('record')
const busy = ref(false)
const error = ref('')
const applied = ref(false)
const confirmed = ref(false)
const submissionStarted = ref(false)
const suiteCommandId = ref<string>()
const proposal = ref<Proposal | null>(null)
const webSteps = computed(() => {
  const steps = proposal.value?.config?.steps
  return Array.isArray(steps) ? (steps as Step[]).map(step => ({ ...step, name: step.name || step.action })) : []
})
function updateWebSteps(steps: Array<{ action: string; name: string; params: Record<string, unknown> }>) {
  if (!proposal.value?.config || busy.value || applied.value) return
  const previous = webSteps.value
  // 直接编辑定位器时清除旧资产引用；用户重新选择资产时保留新绑定。
  for (const [index, step] of steps.entries()) {
    const old = previous[index]
    if (old && old.params.selector !== step.params.selector && old.params.element_asset_id === step.params.element_asset_id) delete step.params.element_asset_id
  }
  proposal.value.config.steps = steps
  proposal.value.preview = steps.map((step, index) => `${index + 1}. ${step.name} · ${step.params.selector || step.params.text || ''}`).join('\n')
  confirmed.value = false
}
const resultPath = ref('')
const cases = ref<CaseSummaryItem[]>([])
const modules = ref<Array<{ label: string; value: number }>>([])
const failures = ref<WorkbenchTaskItem[]>([])
const caseId = ref<number>()
const moduleId = ref<number>()
const runId = ref<number>()
const selectedIds = ref<number[]>([])
const expectedText = ref('')
const oldLocator = ref('')
const newLocator = ref('')
const name = ref('')
const requirement = ref('')
const schemaType = ref<SchemaSourceType>('curl')
const schemaText = ref('')
const days = ref(1)
const envId = ref<number>()
const environmentOptions = ref<Array<{ label: string; value: number }>>([])
const diagnosisText = ref('')
const draftSelections = ref<boolean[]>([])
const createdSuiteId = ref<number>()
const executionConfirmed = ref(false)
const startedRun = ref(false)
const runSubmissionStarted = ref(false)
const windowWidth = ref(window.innerWidth)
let live = true
onMounted(() => { void refreshHistory() })
function resize() { windowWidth.value = window.innerWidth }
window.addEventListener('resize', resize)
onBeforeUnmount(() => { live = false; window.removeEventListener('resize', resize) })
const schemaOptions = computed(() => ['curl', 'openapi', 'postman'].map(value => ({ label: value, value })))
const moduleOptions = computed(() => modules.value)
const caseOptions = computed(() => cases.value.filter(item => kind.value === 'android' ? item.case_type === 'android' : item.case_type === 'web').map(item => ({ label: `${item.case_code} · ${item.name}`, value: item.id })))
const regressionOptions = computed(() => cases.value.filter(item => item.is_ready_for_execution).map(item => ({ label: `${item.case_type} · ${item.name}`, value: item.id })))
const failureOptions = computed(() => failures.value.filter(item => item.task_type === 'case').map(item => ({ label: `#${item.run_id} · ${item.name}`, value: item.run_id })))
const repairFailureOptions = computed(() => failures.value.filter(item => item.task_type === 'case' && item.source_id === caseId.value).map(item => ({ label: `#${item.run_id} · ${item.name}`, value: item.run_id })))
function filterOption(input: string, option?: { label?: string }) { return String(option?.label || '').toLowerCase().includes(input.toLowerCase()) }
function flatten(items: ModuleTreeItem[]): Array<{ label: string; value: number }> {
  return items.flatMap(item => [{ label: item.name, value: item.id }, ...flatten(item.children || [])])
}
watch([caseId, moduleId, runId, selectedIds, expectedText, oldLocator, newLocator, name, requirement, schemaText, schemaType, days, envId], () => {
  if (!applied.value) { proposal.value = null; confirmed.value = false }
}, { deep: true })
watch(caseId, () => { diagnosisText.value = '' })
watch(() => proposal.value?.cases, () => { confirmed.value = false }, { deep: true })
watch(() => proposal.value?.config, () => { confirmed.value = false }, { deep: true })
watch(draftSelections, () => { confirmed.value = false }, { deep: true })

async function openAction(action: Action, text = '') {
  if (busy.value) return
  kind.value = action; opened.value = true; error.value = ''; proposal.value = null
  confirmed.value = false; applied.value = false; submissionStarted.value = false; resultPath.value = ''
  createdSuiteId.value = undefined; startedRun.value = false; runSubmissionStarted.value = false; executionConfirmed.value = false
  suiteCommandId.value = undefined
  caseId.value = undefined; moduleId.value = undefined; runId.value = undefined; selectedIds.value = []
  envId.value = undefined; environmentOptions.value = []; diagnosisText.value = ''
  expectedText.value = ''; oldLocator.value = ''; newLocator.value = ''; schemaText.value = ''
  name.value = ''; requirement.value = action === 'knowledge' ? props.latestAnswer : text
  cases.value = []; modules.value = []; failures.value = []
  busy.value = true
  try {
    const results = await Promise.allSettled([
      caseApi.list({ project_id: props.projectId }), projectApi.getModules(props.projectId),
      workbenchApi.tasks({ project_id: props.projectId, status: 'failed', limit: 100 }),
      environmentApi.list(props.projectId),
    ])
    if (!live) return
    await refreshHistory()
    if (!live) return
    const [caseResult, moduleResult, failureResult, environmentResult] = results
    if (caseResult.status === 'fulfilled') cases.value = caseResult.value
    if (moduleResult.status === 'fulfilled') modules.value = flatten(moduleResult.value)
    if (failureResult.status === 'fulfilled') failures.value = failureResult.value.items
    if (environmentResult.status === 'fulfilled') environmentOptions.value = environmentResult.value.map(item => ({ label: item.name, value: item.id }))
    if (results.some(item => item.status === 'rejected')) error.value = t('hermes.actions.partial_load')
    moduleId.value = modules.value[0]?.value
    const suggested = failures.value.filter(item => item.task_type === 'case').map(item => item.source_id)
    selectedIds.value = cases.value.filter(item => item.is_ready_for_execution && suggested.includes(item.id)).map(item => item.id)
    runId.value = failures.value.find(item => item.task_type === 'case')?.run_id
    if (action === 'regression') name.value = t('hermes.actions.regression_name')
    if (action === 'knowledge') name.value = t('hermes.actions.knowledge_name')
  } catch (reason) { error.value = recordingErrorMessage(reason, t('hermes.actions.failed')) }
  finally { busy.value = false }
}

async function diagnoseRepair() {
  if (!caseId.value || !runId.value || busy.value || !repairFailureOptions.value.some(item => item.value === runId.value)) return
  busy.value = true; error.value = ''
  try {
    const result = await runApi.generateFailureDiagnosis(runId.value)
    if (live) diagnosisText.value = [result.summary, ...result.repair_suggestions.map(item => `${item.step_name}: ${item.suggested_change}\n${item.evidence}`)].join('\n\n')
  } catch (reason) { error.value = recordingErrorMessage(reason, t('hermes.actions.failed')) }
  finally { busy.value = false }
}

async function prepare() {
  if (busy.value || applied.value) return
  error.value = ''; proposal.value = null; confirmed.value = false; busy.value = true
  try {
    if (!props.canModify && kind.value !== 'summary') throw new Error(t('hermes.actions.editor_required'))
    let next: Proposal
    if (kind.value === 'record' || kind.value === 'repair') {
      if (!caseId.value || !caseOptions.value.some(item => item.value === caseId.value)) throw new Error(t('hermes.actions.choose_case'))
      const detail = await caseApi.get(caseId.value)
      const config = structuredClone(detail.config)
      if (!Array.isArray(config.steps) || !config.steps.length) throw new Error(t('hermes.actions.no_recording'))
      const steps = config.steps as Step[]
      if (steps.some(step => !step || typeof step.action !== 'string' || !step.params || typeof step.params !== 'object')) throw new Error(t('hermes.actions.invalid_steps'))
      const notes: string[] = []
      if (kind.value === 'repair') {
        if (!oldLocator.value.trim() || !newLocator.value.trim()) throw new Error(t('hermes.actions.locators_required'))
        let changed = 0
        for (const step of steps) if (step.params.selector === oldLocator.value.trim()) { step.params.selector = newLocator.value.trim(); delete step.params.element_asset_id; changed++ }
        if (!changed) throw new Error(t('hermes.actions.locator_not_found'))
        notes.push(t('hermes.actions.locators_changed', { count: changed }))
      }
      if (!expectedText.value.trim() && kind.value === 'record') throw new Error(t('hermes.actions.expected_required'))
      if (expectedText.value.trim()) steps.push({ action: 'assert_text', name: t('hermes.actions.assertion'), params: { text: expectedText.value.trim() } })
      if (typeof config.timeout !== 'number' || !Number.isFinite(config.timeout) || config.timeout < 1) config.timeout = 30
      next = { baseline: detail, config, notes: [...notes, t('hermes.actions.timeout_note'), t('hermes.actions.review_required')], preview: steps.map((step, index) => `${index + 1}. ${step.name || step.action} · ${step.params.selector || (step.action === 'assert_text' ? step.params.text : '')}`).join('\n') }
    } else if (kind.value === 'api') {
      if (!moduleId.value || !schemaText.value.trim()) throw new Error(t('hermes.actions.schema_required'))
      const parsed = await aiCaseGenerationApi.parseSchema({ source_type: schemaType.value, content: schemaText.value, external_ref_policy: 'reject' })
      if (!parsed.endpoints.length || parsed.endpoints.length > 20) throw new Error(t('hermes.actions.endpoint_limit'))
      const generated = await aiCaseGenerationApi.generate({ project_id: props.projectId, module_id: moduleId.value, endpoints: parsed.endpoints, user_requirement: requirement.value, case_type: 'api', max_cases: 5 })
      if (!generated.drafts.length) throw new Error(t('hermes.actions.no_drafts'))
      next = { notes: [...parsed.warnings, ...generated.warnings, t('hermes.actions.review_required')], preview: `${generated.source.model_name} · ${generated.drafts.length} ${t('hermes.actions.cases')}`, cases: generated.drafts.map(draft => ({ ...draft, config: { ...draft.config, _ai_generated: true, _ai_source: generated.source }, module_id: moduleId.value, description: draft.description || undefined, summary: draft.summary || undefined, automation_status: 'auto' })) }
      draftSelections.value = next.cases!.map(() => true)
    } else if (kind.value === 'regression') {
      if (!name.value.trim() || !selectedIds.value.length) throw new Error(t('hermes.actions.select_cases'))
      if (selectedIds.value.some(id => !regressionOptions.value.some(item => item.value === id))) throw new Error(t('hermes.actions.not_ready'))
      next = { title: name.value.trim(), content: requirement.value, caseIds: [...selectedIds.value], notes: [t('hermes.actions.run_separate')], preview: cases.value.filter(item => selectedIds.value.includes(item.id)).map(item => `${item.case_code} · ${item.name}`).join('\n') }
    } else if (kind.value === 'android') {
      if (!caseId.value || !caseOptions.value.some(item => item.value === caseId.value)) throw new Error(t('hermes.actions.choose_case'))
      const [detail, devices, apks] = await Promise.all([caseApi.get(caseId.value), deviceApi.list(), apkApi.list({ project_id: props.projectId })])
      const device = devices.find(item => item.id === detail.config.device_id)
      const apkId = detail.config.apk_id
      if (!detail.is_ready_for_execution || !device || device.status !== 'online') throw new Error(t('hermes.actions.device_not_ready'))
      if (apkId && !apks.some(item => item.id === apkId)) throw new Error(t('hermes.actions.apk_missing'))
      next = { baseline: detail, notes: [t('hermes.actions.device_cached')], preview: `${detail.name}\n${device.serial} · ${device.status}\n${apkId ? `APK #${apkId}` : t('hermes.actions.installed_app')}` }
    } else if (kind.value === 'defect') {
      if (!runId.value || !failureOptions.value.some(item => item.value === runId.value)) throw new Error(t('hermes.actions.choose_run'))
      const run = await runApi.get(runId.value)
      if (!['failed', 'error'].includes(run.status)) throw new Error(t('hermes.actions.not_failure'))
      const title = name.value.trim() || `${run.case_name || `#${run.case_id}`} · ${run.status}`
      const content = `${requirement.value}\n\n${run.error_message || ''}\n${run.steps.map(step => `${step.name}: ${step.status} ${step.error_message || ''}`).join('\n')}`.trim()
      next = { title, content, runId: run.id, notes: [t('hermes.actions.evidence_link')], preview: `${title}\n${content}` }
    } else if (kind.value === 'knowledge') {
      if (!name.value.trim() || !requirement.value.trim()) throw new Error(t('hermes.actions.content_required'))
      next = { title: name.value.trim(), content: requirement.value.trim(), notes: [t('hermes.actions.knowledge_draft')], preview: `${name.value}\n\n${requirement.value}` }
    } else {
      const overview = await reportApi.overview({ project_id: props.projectId, days: days.value, recent_limit: 50 })
      next = { notes: [t('hermes.actions.summary_limit')], preview: `# ${t('hermes.actions.summary')}\n\n${t('hermes.actions.period', { days: days.value })}\n\n${t('hermes.actions.summary_metrics', { runs: overview.total_runs, passed: overview.passed_runs, failed: overview.failed_runs, error: overview.error_runs, rate: overview.pass_rate, defects: overview.open_defects })}\n\n${overview.recent_runs.map(run => `- #${run.id} ${run.case_name}: ${run.status}${run.error_message ? ` — ${run.error_message}` : ''}`).join('\n')}` }
    }
    if (live) proposal.value = next
  } catch (reason) { error.value = recordingErrorMessage(reason, t('hermes.actions.failed')) }
  finally { busy.value = false }
}

async function applyProposal() {
  const current = proposal.value
  if (!current || !confirmed.value || busy.value || submissionStarted.value || !props.canModify) return
  busy.value = true; error.value = ''
  let receiptId: string | undefined
  let resourceId: number | undefined
  try {
    if (current.baseline) {
      const fresh = await caseApi.get(current.baseline.id)
      if (fresh.updated_at !== current.baseline.updated_at || JSON.stringify(fresh.config) !== JSON.stringify(current.baseline.config)) throw new Error(t('hermes.actions.stale'))
    }
    if (!live) return
    if (current.config && (!webSteps.value.length || webSteps.value.some(step => !validWebStep(step)) || typeof current.config.timeout !== 'number' || !Number.isFinite(current.config.timeout) || current.config.timeout < 1 || current.config.timeout > 600)) throw new Error(t('hermes.actions.invalid_steps'))
    if (kind.value === 'api') {
      const selected = current.cases!.filter((_, index) => draftSelections.value[index])
      if (!selected.length) throw new Error(t('hermes.actions.select_cases'))
      if (selected.some(draft => !draft.name.trim() || !validApiConfig(draft.config))) throw new Error(t('hermes.actions.invalid_api'))
    }
    receiptId = startReceipt(kind.value)
    if (kind.value === 'regression') suiteCommandId.value = receiptId
    submissionStarted.value = true
    if (kind.value === 'record' || kind.value === 'repair') {
      const detail = current.baseline!
      await caseApi.update(detail.id, { config: current.config, expected_updated_at: detail.updated_at, expected_config: detail.config })
      resourceId = detail.id
      resultPath.value = `/cases/${detail.id}`
    } else if (kind.value === 'api') {
      const selected = current.cases!.filter((_, index) => draftSelections.value[index])
      if (!selected.length) { submissionStarted.value = false; throw new Error(t('hermes.actions.select_cases')) }
      const result = await caseApi.importCases(props.projectId, selected, 'fail')
      if (result.imported !== selected.length || result.conflicts.length) throw new Error(t('hermes.actions.import_failed'))
      resultPath.value = `/cases?project_id=${props.projectId}`
    } else if (kind.value === 'regression') {
      const suite = await suiteApi.create({ command_id: suiteCommandId.value, project_id: props.projectId, name: current.title!, description: current.content, case_ids: current.caseIds!.map((id, sort) => ({ case_id: id, sort })), config: { execution_mode: 'sequential', fail_strategy: 'continue' } })
      createdSuiteId.value = suite.id; resultPath.value = `/suites?project_id=${props.projectId}`
      resourceId = suite.id
    } else if (kind.value === 'android') {
      const started = await caseApi.run(current.baseline!.id, { env_id: envId.value })
      resultPath.value = `/runs/${started.id}`
      resourceId = started.id
    } else if (kind.value === 'defect') {
      const result = await defectApi.createFromRun('case', current.runId!, { title: current.title, description: current.content })
      resultPath.value = `/bugs?project_id=${props.projectId}`
      resourceId = result.defect.id
      if (!result.created) current.notes.push(t('hermes.actions.duplicate_defect'))
    } else if (kind.value === 'knowledge') {
      const saved = await knowledgeApi.create({ project_id: props.projectId, source_type: 'experience', title: current.title!, content: current.content!, status: 'draft', tags: ['Hermes'] })
      resourceId = saved.document_id || undefined
      resultPath.value = `/knowledge?project_id=${props.projectId}`
    }
    applied.value = true
    finishReceipt(receiptId, 'completed', resultPath.value, resourceId)
    emit('completed', t('hermes.actions.completed_message', { action: t(`hermes.actions.${kind.value}`) }), resultPath.value)
  } catch (reason) {
    if (receiptId) finishReceipt(receiptId, 'uncertain')
    error.value = `${recordingErrorMessage(reason, t('hermes.actions.failed'))}${submissionStarted.value ? ` ${t('hermes.actions.check_before_retry')}` : ''}`
  }
  finally { busy.value = false }
}

async function runCreatedSuite() {
  if (!createdSuiteId.value || !executionConfirmed.value || busy.value || runSubmissionStarted.value || !props.canModify) return
  runSubmissionStarted.value = true; busy.value = true
  const receiptId = startReceipt('regression')
  try {
    const run = await suiteApi.run(createdSuiteId.value, { env_id: envId.value, command_id: receiptId })
    startedRun.value = true; resultPath.value = `/suites?project_id=${props.projectId}`
    finishReceipt(receiptId, 'completed', resultPath.value, run.id)
    await refreshHistory()
    emit('completed', t('hermes.actions.run_started', { id: run.id }), resultPath.value)
  } catch (reason) { finishReceipt(receiptId, 'uncertain'); error.value = `${recordingErrorMessage(reason, t('hermes.actions.failed'))} ${t('hermes.actions.check_before_retry')}` }
  finally { busy.value = false }
}
function downloadSummary() {
  if (!proposal.value) return
  const url = URL.createObjectURL(new Blob([proposal.value.preview], { type: 'text/markdown;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = `hermes-summary-${props.projectId}-${new Date().toISOString().slice(0, 10)}.md`; link.click(); URL.revokeObjectURL(url)
}
function validApiConfig(config?: Record<string, unknown>): boolean {
  if (!config) return false
  const requests = Array.isArray(config.steps) ? config.steps : [config]
  return requests.length > 0 && requests.every(request => {
    if (!request || typeof request !== 'object' || typeof request.url !== 'string' || !request.url.trim()) return false
    if (!['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].includes(String(request.method || 'GET').toUpperCase())) return false
    if (!Array.isArray(request.assertions)) return false
    return request.assertions.length > 0 && request.assertions.every((assertion: Record<string, unknown>) => {
      if (!assertion || typeof assertion !== 'object' || !['status_code', 'body', 'header', 'duration', 'json_schema'].includes(String(assertion.target)) || !['eq', 'contains', 'gt', 'lt', 'exists', 'valid', 'invalid'].includes(String(assertion.operator))) return false
      if (assertion.target === 'json_schema') {
        if (!['valid', 'invalid'].includes(String(assertion.operator))) return false
        if (assertion.schema_asset_id) return true
        try {
          const schema: unknown = typeof assertion.expected === 'string' ? JSON.parse(assertion.expected) : assertion.expected
          return typeof schema === 'boolean' || (!!schema && typeof schema === 'object' && !Array.isArray(schema))
        } catch { return false }
      }
      if (['valid', 'invalid'].includes(String(assertion.operator))) return false
      if (assertion.target === 'header' && (typeof assertion.expression !== 'string' || !assertion.expression.trim())) return false
      if (assertion.operator === 'exists') return true
      if (['status_code', 'duration'].includes(String(assertion.target)) && (assertion.expected == null || String(assertion.expected).trim() === '' || !Number.isFinite(Number(assertion.expected)))) return false
      return assertion.expected !== undefined && (typeof assertion.expected !== 'number' || Number.isFinite(assertion.expected))
    })
  })
}
function validWebStep(step: Step): boolean {
  const params = step.params
  if (!params || typeof params !== 'object') return false
  const has = (key: string) => params[key] != null && String(params[key]).trim().length > 0
  if (step.action === 'goto') return has('url')
  if (step.action === 'assert_text') return has('text')
  if (step.action === 'wait') return typeof params.ms === 'number' && Number.isFinite(params.ms) && params.ms >= 0
  if (step.action === 'screenshot') return true
  if (step.action === 'page_object') return has('page_object_id')
  if (step.action === 'visual_assert') return has('baseline_id')
  if (!['click', 'fill', 'assert_visible', 'select', 'press', 'hover', 'upload', 'download'].includes(step.action)) return false
  if (!has('selector') && !has('element_asset_id')) return false
  if (['fill', 'select'].includes(step.action)) return params.value !== undefined
  if (step.action === 'press') return has('key')
  if (step.action === 'upload') return has('object_name')
  return true
}
function openForText(text: string): boolean {
  const match = /录制.*(完善|整理|断言)|(完善|整理).*录制/.test(text) ? 'record'
    : /(生成|创建).*(API|接口).*用例/i.test(text) ? 'api'
    : /(组织|执行|运行|创建).*回归/.test(text) ? 'regression'
    : /修复.*(用例|定位器)/.test(text) ? 'repair'
    : /(检查|测试|运行).*(安卓|Android|手机)/i.test(text) ? 'android'
    : /(创建|生成|整理).*缺陷/.test(text) ? 'defect'
    : /(记住|保存.*知识|沉淀)/.test(text) ? 'knowledge'
    : /(总结|导出).*(测试|今天|报告)/.test(text) ? 'summary' : null
  if (!match) return false
  void openAction(match, text); return true
}
defineExpose({ openForText })
</script>

<style scoped>
.assistant-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.assistant-actions > span { font-size: 12px; color: var(--c-text-tertiary); margin-right: 4px; }
.assistant-actions button { padding: 6px 10px; border: 1px solid var(--c-border); border-radius: 6px; background: var(--c-bg-elevated); color: var(--c-text-secondary); font-size: 12px; cursor: pointer; }
.assistant-actions button:hover { border-color: var(--c-primary); color: var(--c-primary); }
.assistant-actions button:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }
.action-alert { margin-bottom: 12px; }
.action-history { font-size: 12px; color: var(--c-text-secondary); }
.action-history summary { cursor: pointer; }.action-history > div { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.proposal { margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--c-border); }
.proposal pre, .diagnosis-text { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; font-size: 13px; line-height: 1.7; padding: 16px; border-radius: 8px; background: var(--c-bg-subtle); }
.proposal-buttons { margin: 16px 0; }.draft-card { margin-bottom: 12px; }
</style>
