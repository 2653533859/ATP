<template>
  <div class="page-shell ui-workbench">
    <section class="ui-hero">
      <div class="hero-copy">
        <div class="eyebrow"><DesktopOutlined /> {{ t('ui_workbench.eyebrow') }}</div>
        <div class="hero-title-row">
          <h1>{{ t('ui_workbench.title') }}</h1>
          <span class="hero-chip">PLAYWRIGHT / TRACE</span>
        </div>
        <p>{{ t('ui_workbench.subtitle') }}</p>
        <div class="hero-rail">
          <span class="live-dot" :class="{ muted: !workerReady }" />
          <span>{{ workerLabel }}</span>
          <span class="rail-separator" />
          <span class="rail-muted">{{ selectedProjectName || t('ui_workbench.no_project') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label>{{ t('ui_workbench.project_label') }}</label>
        <a-select
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :placeholder="t('ui_workbench.project_placeholder')"
          @change="handleProjectChange"
        />
        <div class="hero-control-row">
          <a-button :loading="loading" @click="refreshWorkbench"><ReloadOutlined /> {{ t('common.refresh') }}</a-button>
          <a-button type="link" @click="() => openAssets()"><SettingOutlined /> {{ t('ui_workbench.asset_management') }}</a-button>
        </div>
      </div>
    </section>

    <a-alert
      v-if="workerStatusError"
      class="worker-alert"
      type="warning"
      show-icon
      :message="t('ui_workbench.worker_status_error')"
      :description="workerStatusError"
    />
    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('ui_workbench.readonly_title')"
      :description="t('ui_workbench.readonly_description')"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('ui_workbench.select_project_hint')" />

    <template v-else>
      <section class="signal-grid" aria-label="UI workspace summary">
        <div class="signal-card signal-card-primary">
          <span class="signal-label">{{ t('ui_workbench.signals.web_cases') }}</span>
          <strong>{{ webCases.length }}</strong>
          <span class="signal-note">{{ t('ui_workbench.signals.project_scope') }}</span>
        </div>
        <div class="signal-card">
          <span class="signal-label">{{ t('ui_workbench.signals.ready_cases') }}</span>
          <strong>{{ readyCaseCount }}</strong>
          <span class="signal-note">{{ t('ui_workbench.signals.script_ready') }}</span>
        </div>
        <div class="signal-card">
          <span class="signal-label">{{ t('ui_workbench.signals.web_assets') }}</span>
          <strong>{{ assetCount }}</strong>
          <span class="signal-note">{{ t('ui_workbench.signals.asset_breakdown', { elements: elements.length, objects: pageObjects.length, baselines: baselines.length }) }}</span>
        </div>
        <div class="signal-card signal-card-run">
          <span class="signal-label">{{ t('ui_workbench.signals.recent_pass_rate') }}</span>
          <strong>{{ recentPassRate }}%</strong>
          <span class="signal-note">{{ recentRuns.length ? t('ui_workbench.signals.recent_runs', { count: recentRuns.length }) : t('ui_workbench.signals.no_runs') }}</span>
        </div>
      </section>

      <section class="studio-grid">
        <aside class="module-rail panel">
          <div class="panel-kicker">{{ t('ui_workbench.module_kicker') }}</div>
          <h2>{{ t('ui_workbench.module_title') }}</h2>
          <p class="panel-description">{{ t('ui_workbench.module_description') }}</p>
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            show-reset
            :reset-disabled="!selectedModuleId"
            :editable="canModify"
            @select="handleModuleSelect"
            @reset="handleModuleReset"
          />

          <div class="rail-divider" />
          <div class="panel-kicker">{{ t('ui_workbench.worker_kicker') }}</div>
          <div class="worker-card" :class="{ ready: workerReady }">
            <div class="worker-card-head">
              <span class="status-pulse" :class="{ ready: workerReady }" />
              <strong>{{ workerLabel }}</strong>
            </div>
            <p>{{ workerHint }}</p>
            <a-button size="small" :loading="workerLoading" @click="loadWorkerStatus">
              <ReloadOutlined /> {{ t('ui_workbench.refresh_worker') }}
            </a-button>
          </div>

          <div class="rail-divider" />
          <div class="asset-links">
            <button type="button" @click="openAssets('elements')"><span class="asset-link-mark mint" />{{ t('ui_workbench.element_assets') }}<strong>{{ elements.length }}</strong></button>
            <button type="button" @click="openAssets('page_objects')"><span class="asset-link-mark coral" />{{ t('ui_workbench.page_objects') }}<strong>{{ pageObjects.length }}</strong></button>
            <button type="button" @click="openAssets('visual_baselines')"><span class="asset-link-mark violet" />{{ t('ui_workbench.visual_baselines') }}<strong>{{ baselines.length }}</strong></button>
          </div>
        </aside>

        <main class="browser-console panel">
          <div class="console-head">
            <div>
              <div class="panel-kicker">{{ t('ui_workbench.case_kicker') }}</div>
              <h2>{{ selectedModuleId ? t('ui_workbench.selected_module', { name: selectedModuleName }) : t('ui_workbench.all_cases') }}</h2>
              <p>{{ t('ui_workbench.case_description') }}</p>
            </div>
            <div class="console-actions">
              <a-button :disabled="!canModify || !selectedModuleId" @click="openCreateCase">
                <PlusOutlined /> {{ t('ui_workbench.new_case') }}
              </a-button>
              <a-button type="primary" :disabled="!canRecord" @click="openRecorder('case')">
                <VideoCameraOutlined /> {{ t('ui_workbench.record_case') }}
              </a-button>
            </div>
          </div>

          <div class="browser-launch-bar">
            <div class="browser-launch-copy">
              <span class="browser-window-dot" />
              <div>
                <strong>{{ t('ui_workbench.recording_lane') }}</strong>
                <small>{{ t('ui_workbench.recording_lane_hint') }}</small>
              </div>
            </div>
            <a-input v-model:value="recordingUrl" :placeholder="t('ui_workbench.url_placeholder')" />
            <a-button :disabled="!canRecord" @click="openRecorder('case')"><VideoCameraOutlined /> {{ t('ui_workbench.record_steps') }}</a-button>
            <a-button :disabled="!canRecord" @click="openRecorder('baseline')"><EyeOutlined /> {{ t('ui_workbench.capture_baseline') }}</a-button>
          </div>

          <div v-if="recordedAssetCount" class="recorded-note">
            <CheckCircleOutlined /> {{ t('ui_workbench.recorded_assets', { count: recordedAssetCount }) }}
          </div>

          <div class="case-list-head">
            <span>{{ t('ui_workbench.case_catalog') }}</span>
            <span>{{ t('ui_workbench.case_count', { count: webCases.length }) }}</span>
          </div>
          <div v-if="webCases.length" class="case-list">
            <button
              v-for="item in webCases"
              :key="item.id"
              type="button"
              class="case-row"
              :class="{ selected: item.id === selectedCaseId }"
              @click="selectCase(item)"
            >
              <span class="case-row-mark" :class="item.id === selectedCaseId ? 'active' : ''" />
              <span class="case-row-main">
                <strong>{{ item.name }}</strong>
                <small>{{ item.case_code }} · {{ moduleNameMap[item.module_id] || t('ui_workbench.module_fallback', { id: item.module_id }) }}</small>
              </span>
              <span class="case-row-meta">
                <a-tag :color="item.script_status === 'generated' ? 'green' : 'orange'">{{ item.script_status === 'generated' ? t('ui_workbench.script_ready') : t('ui_workbench.script_missing') }}</a-tag>
                <span class="case-level">{{ t(`case.levels.${item.case_level}`) }}</span>
              </span>
            </button>
          </div>
          <a-empty v-else :description="t('ui_workbench.empty_cases')" />

          <section v-if="selectedCase" class="case-detail">
            <div class="detail-head">
              <div>
                <span class="case-code">{{ selectedCase.case_code }}</span>
                <h3>{{ selectedCase.name }}</h3>
              </div>
              <a-space>
                <a-button size="small" :disabled="!canModify" @click="openEditCase"><SettingOutlined /> {{ t('ui_workbench.edit_case') }}</a-button>
                <a-button type="primary" size="small" :disabled="!canRunSelected" :loading="runLoading" @click="runSelectedCase"><PlayCircleOutlined /> {{ t('ui_workbench.run_case') }}</a-button>
              </a-space>
            </div>
            <div class="detail-meta">
              <span>{{ selectedModuleName || t('ui_workbench.module_fallback', { id: selectedCase.module_id }) }}</span>
              <span>{{ t(`case.levels.${selectedCase.case_level}`) }}</span>
              <span>{{ selectedConfig.browser || 'chromium' }}</span>
              <span>{{ selectedConfig.headless === false ? t('ui_workbench.headed') : t('ui_workbench.headless') }}</span>
            </div>
            <div class="trace-strip detail-trace">
              <span class="trace-step trace-active"><b>01</b>{{ t('ui_workbench.trace.record') }}</span>
              <span class="trace-line" />
              <span class="trace-step trace-active"><b>02</b>{{ t('ui_workbench.trace.configure') }}</span>
              <span class="trace-line" />
              <span class="trace-step" :class="{ 'trace-active': selectedRuns.length }"><b>03</b>{{ t('ui_workbench.trace.observe') }}</span>
            </div>
            <div class="step-preview">
              <div class="step-preview-head"><strong>{{ t('ui_workbench.step_preview') }}</strong><span>{{ t('ui_workbench.step_count', { count: selectedSteps.length }) }}</span></div>
              <div v-if="selectedSteps.length" class="step-chips">
                <span v-for="(step, index) in selectedSteps.slice(0, 8)" :key="`${step.action}-${index}`" class="step-chip"><b>{{ index + 1 }}</b>{{ step.action }}</span>
                <span v-if="selectedSteps.length > 8" class="step-chip more">+{{ selectedSteps.length - 8 }}</span>
              </div>
              <a-empty v-else :description="t('ui_workbench.no_steps')" />
            </div>
            <div class="config-grid">
              <div><span>{{ t('ui_workbench.browser') }}</span><strong>{{ selectedConfig.browser || 'chromium' }}</strong></div>
              <div><span>{{ t('ui_workbench.viewport') }}</span><strong>{{ selectedViewport }}</strong></div>
              <div><span>{{ t('ui_workbench.trace_status') }}</span><strong>{{ selectedRuns.some((run) => Boolean(run.trace_id)) ? t('ui_workbench.connected') : t('ui_workbench.created_on_run') }}</strong></div>
              <div><span>{{ t('ui_workbench.script_status') }}</span><strong>{{ selectedCase.script_status === 'generated' ? t('ui_workbench.script_ready') : t('ui_workbench.script_missing') }}</strong></div>
            </div>
          </section>
          <a-spin v-if="detailLoading" class="detail-loading" />
        </main>

        <aside class="observe-rail panel">
          <div class="panel-kicker">{{ t('ui_workbench.observe_kicker') }}</div>
          <h2>{{ t('ui_workbench.observe_title') }}</h2>
          <p class="panel-description">{{ t('ui_workbench.observe_description') }}</p>
          <div class="observe-metric-row">
            <div><strong>{{ failedRunCount }}</strong><span>{{ t('ui_workbench.failed_runs') }}</span></div>
            <div><strong>{{ traceRunCount }}</strong><span>{{ t('ui_workbench.trace_runs') }}</span></div>
          </div>
          <div class="rail-divider" />
          <div class="panel-kicker">{{ t('ui_workbench.recent_runs') }}</div>
          <div v-if="recentRuns.length" class="run-list">
            <button v-for="run in recentRuns.slice(0, 7)" :key="run.id" type="button" class="run-row" @click="openRunDetail(run.id)">
              <span class="run-status-dot" :class="`status-${run.status}`" />
              <span class="run-row-main"><strong>{{ run.case_name || t('ui_workbench.run_case_fallback', { id: run.id }) }}</strong><small>#{{ run.id }} · {{ formatTime(run.created_at) }} · {{ runStatusLabel(run.status) }}</small></span>
              <span class="run-arrow">↗</span>
            </button>
          </div>
          <a-empty v-else :description="t('ui_workbench.no_runs')" />
          <a-button block class="observe-all" @click="openRunList"><HistoryOutlined /> {{ t('ui_workbench.view_all_runs') }}</a-button>
        </aside>
      </section>

      <section class="asset-band panel">
        <div class="asset-band-head">
          <div><div class="panel-kicker">{{ t('ui_workbench.asset_kicker') }}</div><h2>{{ t('ui_workbench.asset_title') }}</h2></div>
          <a-button type="link" @click="() => openAssets()">{{ t('ui_workbench.open_assets') }} ↗</a-button>
        </div>
        <div class="asset-band-grid">
          <button type="button" class="asset-card asset-card-mint" @click="openAssets('elements')"><span class="asset-card-index">01</span><strong>{{ t('ui_workbench.element_assets') }}</strong><small>{{ t('ui_workbench.element_assets_hint') }}</small><b>{{ elements.length }}</b></button>
          <button type="button" class="asset-card asset-card-coral" @click="openAssets('page_objects')"><span class="asset-card-index">02</span><strong>{{ t('ui_workbench.page_objects') }}</strong><small>{{ t('ui_workbench.page_objects_hint') }}</small><b>{{ pageObjects.length }}</b></button>
          <button type="button" class="asset-card asset-card-violet" @click="openAssets('visual_baselines')"><span class="asset-card-index">03</span><strong>{{ t('ui_workbench.visual_baselines') }}</strong><small>{{ t('ui_workbench.visual_baselines_hint') }}</small><b>{{ baselines.length }}</b></button>
          <div class="asset-card asset-card-note"><span class="asset-card-index">04</span><strong>{{ t('ui_workbench.diagnostics') }}</strong><small>{{ t('ui_workbench.diagnostics_hint') }}</small><span class="diagnostic-tags"><a-tag v-if="failedAssetCount" color="orange">{{ t('ui_workbench.asset_failures', { count: failedAssetCount }) }}</a-tag><a-tag v-else color="green">{{ t('ui_workbench.assets_healthy') }}</a-tag><a-tag>{{ t('ui_workbench.trace_network') }}</a-tag></span></div>
        </div>
      </section>
    </template>

    <WebRecorderModal
      :open="recorderOpen"
      :project-id="selectedProjectId"
      :initial-url="recordingUrl"
      :show-capture="recorderMode === 'baseline'"
      :auto-apply="false"
      @close="handleRecorderClose"
      @recorded="handleRecorded"
      @captured="handleScreenshotCaptured"
    />
    <WebCaseDrawer
      :open="caseDrawerOpen"
      :module-id="selectedModuleId"
      :project-id="selectedProjectId"
      :edit-case="editingCase"
      :initial-name="initialCaseName"
      :initial-description="initialCaseDescription"
      :initial-steps="initialCaseSteps"
      @close="caseDrawerOpen = false"
      @saved="handleCaseSaved"
    />
    <a-modal v-model:open="baselineModalOpen" :title="t('ui_workbench.baseline_modal_title')" :confirm-loading="baselineSaving" @ok="saveBaseline">
      <a-form layout="vertical">
        <a-form-item :label="t('ui_workbench.baseline_name')" required><a-input v-model:value="baselineName" /></a-form-item>
        <a-form-item :label="t('ui_workbench.baseline_url')"><a-input v-model:value="baselinePageUrl" /></a-form-item>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item :label="t('ui_workbench.threshold')"><a-input-number v-model:value="baselineThreshold" :min="0" :max="1" :step="0.001" style="width: 100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item :label="t('ui_workbench.pixel_threshold')"><a-input-number v-model:value="baselinePixelThreshold" :min="0" :max="255" style="width: 100%" /></a-form-item></a-col>
        </a-row>
        <a-alert v-if="baselineFile" type="success" show-icon :message="baselineFile.name" />
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  DesktopOutlined,
  EyeOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SettingOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  caseApi,
  projectApi,
  runApi,
  webAssetsApi,
  webRecordingApi,
  webVisualApi,
  type CaseDetailItem,
  type CaseSummaryItem,
  type CaseType,
  type ModuleTreeItem,
  type ProjectItem,
  type RunDetailItem,
  type WebElementAssetItem,
  type WebPageObjectItem,
  type WebRecordingStep,
  type WebRecordingWorkersResponse,
  type WebVisualBaselineItem,
} from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import WebRecorderModal from '@/components/common/WebRecorderModal.vue'
import WebCaseDrawer from '@/views/case/WebCaseDrawer.vue'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type ErrorLike = { response?: { data?: { detail?: unknown } }; message?: unknown }
type SelectOption<T extends string | number> = { label: string; value: T }
type RecorderMode = 'case' | 'baseline'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const selectedModuleId = ref<number | null>(positiveInt(route.query.module_id))
const moduleNameMap = ref<Record<number, string>>({})
const webCases = ref<CaseSummaryItem[]>([])
const recentRuns = ref<RunDetailItem[]>([])
const elements = ref<WebElementAssetItem[]>([])
const pageObjects = ref<WebPageObjectItem[]>([])
const baselines = ref<WebVisualBaselineItem[]>([])
const workerStatus = ref<WebRecordingWorkersResponse | null>(null)
const workerStatusError = ref('')
const selectedCaseId = ref<number | null>(null)
const selectedCaseDetail = ref<CaseDetailItem | null>(null)
const keyword = ref('')
const recordingUrl = ref('')
const loading = ref(false)
const detailLoading = ref(false)
const workerLoading = ref(false)
const runLoading = ref(false)
const recorderOpen = ref(false)
const recorderMode = ref<RecorderMode>('case')
const recordedDraftSteps = ref<WebRecordingStep[]>([])
const recordedAssetCount = ref(0)
const caseDrawerOpen = ref(false)
const editingCase = ref<CaseSummaryItem | null>(null)
const initialCaseName = ref('')
const initialCaseDescription = ref('')
const initialCaseSteps = ref<WebRecordingStep[]>([])
const baselineModalOpen = ref(false)
const baselineSaving = ref(false)
const baselineFile = ref<File | null>(null)
const baselineName = ref('')
const baselinePageUrl = ref('')
const baselineThreshold = ref(0.01)
const baselinePixelThreshold = ref(10)
let loadSequence = 0
let detailSequence = 0

const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const projectOptions = computed<SelectOption<number>[]>(() => projects.value.map((item) => ({ label: item.name, value: item.id })))
const selectedProject = computed(() => projects.value.find((item) => item.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const selectedModuleName = computed(() => selectedModuleId.value ? (moduleNameMap.value[selectedModuleId.value] || t('ui_workbench.module_fallback', { id: selectedModuleId.value })) : '')
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const workerReady = computed(() => Boolean(workerStatus.value && (workerStatus.value.mode !== 'worker' || workerStatus.value.ready)))
const workerLabel = computed(() => {
  if (!workerStatus.value) return t('ui_workbench.worker_checking')
  if (workerStatus.value.mode !== 'worker') return t('ui_workbench.worker_local')
  return workerStatus.value.ready ? t('ui_workbench.worker_ready', { count: workerStatus.value.available_count }) : t('ui_workbench.worker_unavailable')
})
const workerHint = computed(() => workerStatus.value?.mode === 'worker' ? t('ui_workbench.worker_remote_hint') : t('ui_workbench.worker_local_hint'))
const canRecord = computed(() => Boolean(canModify.value && workerReady.value))
const selectedCase = computed(() => webCases.value.find((item) => item.id === selectedCaseId.value) || null)
const selectedConfig = computed<Record<string, unknown>>(() => selectedCaseDetail.value?.config || {})
const selectedSteps = computed<WebRecordingStep[]>(() => Array.isArray(selectedConfig.value.steps) ? selectedConfig.value.steps as WebRecordingStep[] : [])
const selectedViewport = computed(() => {
  const viewport = selectedConfig.value.viewport
  if (!viewport || typeof viewport !== 'object') return '1280 × 720'
  const value = viewport as { width?: unknown; height?: unknown }
  return `${Number(value.width || 1280)} × ${Number(value.height || 720)}`
})
const selectedRuns = computed(() => selectedCaseId.value ? recentRuns.value.filter((run) => run.case_id === selectedCaseId.value) : [])
const readyCaseCount = computed(() => webCases.value.filter((item) => item.is_ready_for_execution).length)
const assetCount = computed(() => elements.value.length + pageObjects.value.length + baselines.value.length)
const failedAssetCount = computed(() => elements.value.filter((item) => Boolean(item.last_failed_at)).length)
const failedRunCount = computed(() => recentRuns.value.filter((run) => ['failed', 'error'].includes(run.status)).length)
const traceRunCount = computed(() => recentRuns.value.filter((run) => Boolean(run.trace_id)).length)
const recentPassRate = computed(() => {
  if (!recentRuns.value.length) return 0
  return Math.round((recentRuns.value.filter((run) => run.status === 'passed').length / recentRuns.value.length) * 100)
})

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(items: ModuleTreeItem[], result: Record<number, string> = {}) {
  for (const item of items) {
    result[item.id] = item.name
    flattenModules(item.children || [], result)
  }
  return result
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

function runStatusLabel(status: string) {
  const key = ['pending', 'running', 'passed', 'failed', 'error', 'cancelled', 'stopped'].includes(status) ? status : 'unknown'
  return t(`ui_workbench.run_status.${key}`)
}

function syncRoute() {
  void router.replace({ query: {
    ...(selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {}),
    ...(selectedModuleId.value ? { module_id: String(selectedModuleId.value) } : {}),
  } })
}

async function loadWorkerStatus() {
  workerLoading.value = true
  workerStatusError.value = ''
  try {
    workerStatus.value = await webRecordingApi.workers()
  } catch (error: unknown) {
    workerStatus.value = null
    workerStatusError.value = errorMessage(error, t('ui_workbench.worker_status_error'))
  } finally {
    workerLoading.value = false
  }
}

async function loadModules(projectId: number) {
  try {
    const tree = await projectApi.getModules(projectId)
    if (selectedProjectId.value !== projectId) return
    moduleNameMap.value = flattenModules(tree)
    if (selectedModuleId.value && !moduleNameMap.value[selectedModuleId.value]) selectedModuleId.value = null
  } catch {
    if (selectedProjectId.value !== projectId) return
    moduleNameMap.value = {}
  }
}

async function loadRuns(caseIds: number[], sequence?: number) {
  if (sequence !== undefined && sequence !== loadSequence) return
  if (!caseIds.length) {
    recentRuns.value = []
    return
  }
  try {
    const result = await runApi.list({ page: 1, page_size: 100 })
    if (sequence !== undefined && sequence !== loadSequence) return
    recentRuns.value = result.items
      .filter((run) => caseIds.includes(run.case_id))
      .sort((left, right) => right.created_at.localeCompare(left.created_at))
  } catch {
    if (sequence === undefined || sequence === loadSequence) recentRuns.value = []
  }
}

async function loadCases(projectId: number) {
  const sequence = ++loadSequence
  try {
    const result = await caseApi.list({ project_id: projectId, module_id: selectedModuleId.value ?? undefined, case_type: 'web' as CaseType, keyword: keyword.value.trim() || undefined })
    if (sequence !== loadSequence) return
    webCases.value = result.filter((item) => item.case_type === 'web')
    await loadRuns(webCases.value.map((item) => item.id), sequence)
    if (sequence !== loadSequence) return
    const nextId = selectedCaseId.value && webCases.value.some((item) => item.id === selectedCaseId.value) ? selectedCaseId.value : webCases.value[0]?.id ?? null
    selectedCaseId.value = nextId
    if (nextId) await loadCaseDetail(nextId, sequence)
    else selectedCaseDetail.value = null
  } catch (error: unknown) {
    if (sequence === loadSequence) message.error(errorMessage(error, t('ui_workbench.load_failed')))
  }
}

async function loadAssets(projectId: number) {
  try {
    const [elementItems, objectItems, baselineItems] = await Promise.all([
      webAssetsApi.listElements(projectId),
      webAssetsApi.listPageObjects(projectId),
      webVisualApi.listBaselines(projectId),
    ])
    if (selectedProjectId.value !== projectId) return
    elements.value = elementItems
    pageObjects.value = objectItems
    baselines.value = baselineItems
  } catch {
    if (selectedProjectId.value !== projectId) return
    elements.value = []
    pageObjects.value = []
    baselines.value = []
  }
}

function clearProjectData() {
  loadSequence += 1
  detailSequence += 1
  moduleNameMap.value = {}
  webCases.value = []
  recentRuns.value = []
  elements.value = []
  pageObjects.value = []
  baselines.value = []
  workerStatus.value = null
  workerStatusError.value = ''
  selectedCaseId.value = null
  selectedCaseDetail.value = null
}

async function loadProjectData() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    clearProjectData()
    return
  }
  loading.value = true
  try {
    await Promise.all([loadModules(projectId), loadCases(projectId), loadAssets(projectId), loadWorkerStatus()])
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (!selectedProjectId.value || !projects.value.some((item) => item.id === selectedProjectId.value)) selectedProjectId.value = projects.value[0]?.id ?? null
    await loadProjectData()
    syncRoute()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('ui_workbench.load_failed')))
  }
}

async function refreshWorkbench() { await loadProjects() }

async function handleProjectChange(value: unknown) {
  selectedProjectId.value = positiveInt(value)
  selectedModuleId.value = null
  clearProjectData()
  await loadProjectData()
  syncRoute()
}

async function handleModuleSelect(moduleId: number | null) {
  selectedModuleId.value = moduleId
  const projectId = selectedProjectId.value
  if (!projectId) return
  await loadCases(projectId)
  syncRoute()
}

async function handleModuleReset() {
  selectedModuleId.value = null
  const projectId = selectedProjectId.value
  if (!projectId) return
  await loadCases(projectId)
  syncRoute()
}

async function selectCase(item: CaseSummaryItem) {
  selectedCaseId.value = item.id
  await loadCaseDetail(item.id)
}

async function loadCaseDetail(caseId: number, caseSequence?: number) {
  if (caseSequence !== undefined && caseSequence !== loadSequence) return
  const sequence = ++detailSequence
  detailLoading.value = true
  try {
    const detail = await caseApi.get(caseId)
    if (sequence === detailSequence && (caseSequence === undefined || caseSequence === loadSequence)) selectedCaseDetail.value = detail
  } catch (error: unknown) {
    if (sequence === detailSequence && (caseSequence === undefined || caseSequence === loadSequence)) message.error(errorMessage(error, t('ui_workbench.detail_failed')))
  } finally {
    if (sequence === detailSequence && (caseSequence === undefined || caseSequence === loadSequence)) detailLoading.value = false
  }
}

function openCreateCase() {
  if (!selectedModuleId.value) {
    message.warning(t('ui_workbench.select_module_first'))
    return
  }
  editingCase.value = null
  initialCaseName.value = ''
  initialCaseDescription.value = ''
  initialCaseSteps.value = []
  caseDrawerOpen.value = true
}

function openEditCase() {
  if (!selectedCase.value) return
  editingCase.value = selectedCase.value
  initialCaseName.value = ''
  initialCaseDescription.value = ''
  initialCaseSteps.value = []
  caseDrawerOpen.value = true
}

function openRecorder(mode: RecorderMode) {
  if (!canRecord.value) {
    message.warning(t('ui_workbench.worker_unavailable'))
    return
  }
  recorderMode.value = mode
  recorderOpen.value = true
}

function handleRecorded(steps: WebRecordingStep[], assetIds: number[]) {
  recordedDraftSteps.value = steps.map((step) => ({ ...step, params: { ...step.params } }))
  recordedAssetCount.value = assetIds.length
  message.success(t('ui_workbench.recorded_steps', { count: steps.length }))
}

function handleRecorderClose() {
  recorderOpen.value = false
  if (recorderMode.value !== 'case' || !recordedDraftSteps.value.length) return
  if (!selectedModuleId.value) {
    message.warning(t('ui_workbench.select_module_first'))
    recordedDraftSteps.value = []
    return
  }
  initialCaseName.value = t('ui_workbench.recorded_case_prefix')
  initialCaseDescription.value = t('ui_workbench.recorded_case_description', { count: recordedAssetCount.value })
  initialCaseSteps.value = recordedDraftSteps.value
  editingCase.value = null
  caseDrawerOpen.value = true
  recordedDraftSteps.value = []
}

function handleScreenshotCaptured(file: File, pageUrl: string) {
  baselineFile.value = file
  baselineName.value = t('ui_workbench.recorded_baseline_prefix')
  baselinePageUrl.value = pageUrl
  baselineThreshold.value = 0.01
  baselinePixelThreshold.value = 10
  baselineModalOpen.value = true
}

async function saveBaseline() {
  if (!selectedProjectId.value || !baselineFile.value || !baselineName.value.trim()) {
    message.warning(t('ui_workbench.baseline_required'))
    return
  }
  baselineSaving.value = true
  try {
    await webVisualApi.uploadBaseline(selectedProjectId.value, {
      name: baselineName.value.trim(),
      page_url: baselinePageUrl.value.trim() || undefined,
      threshold: baselineThreshold.value,
      pixel_threshold: baselinePixelThreshold.value,
      file: baselineFile.value,
    })
    baselineModalOpen.value = false
    baselineFile.value = null
    message.success(t('ui_workbench.baseline_saved'))
    await loadAssets(selectedProjectId.value)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('ui_workbench.baseline_failed')))
  } finally {
    baselineSaving.value = false
  }
}

async function runSelectedCase() {
  if (!selectedCase.value || !canRunSelected.value) return
  runLoading.value = true
  try {
    const result = await caseApi.run(selectedCase.value.id)
    message.success(t('ui_workbench.run_started'))
    await router.push({ name: 'run-detail', params: { runId: String(result.id) } })
  } catch (error: unknown) {
    message.error(errorMessage(error, t('ui_workbench.run_failed')))
  } finally {
    runLoading.value = false
  }
}

const canRunSelected = computed(() => Boolean(canModify.value && selectedCase.value?.is_ready_for_execution && !runLoading.value))

function handleCaseSaved() {
  caseDrawerOpen.value = false
  recordedAssetCount.value = 0
  if (selectedProjectId.value) void loadProjectData()
}

function openAssets(tab?: string) {
  void router.push({ path: '/system/web-assets', query: {
    ...(selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {}),
    ...(tab ? { tab } : {}),
  } })
}

function openRunDetail(runId: number) { void router.push({ name: 'run-detail', params: { runId: String(runId) } }) }
function openRunList() { void router.push({ path: '/runs', query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} }) }

onMounted(() => { void loadProjects() })
</script>

<style scoped>
.ui-workbench { --ui-ink: #20272a; --ui-muted: #788384; --ui-line: #d9dfdc; --ui-paper: #f4f1eb; --ui-panel: #fffdf9; --ui-coral: #ed765e; --ui-mint: #6bb9ae; --ui-violet: #8b82b8; color: var(--ui-ink); }
.ui-hero { display: flex; justify-content: space-between; gap: 28px; padding: 30px 32px 26px; overflow: hidden; border: 1px solid #202b2d; border-radius: 16px; background: radial-gradient(circle at 88% 12%, rgba(107, 185, 174, .23), transparent 22%), linear-gradient(120deg, #172124, #253337 70%, #39494a); color: #fbfaf5; box-shadow: 0 18px 38px rgba(32, 39, 42, .15); }
.hero-copy { min-width: 0; }.eyebrow, .panel-kicker { color: var(--ui-mint); font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }.eyebrow { display: flex; align-items: center; gap: 7px; }.hero-title-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 8px 0 7px; }.ui-hero h1 { margin: 0; color: #fff; font-size: 31px; letter-spacing: -.045em; }.hero-chip { padding: 4px 8px; border: 1px solid rgba(237, 118, 94, .46); border-radius: 4px; color: #ffc1b2; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; letter-spacing: .04em; }.ui-hero p { max-width: 700px; margin: 0; color: #c8d4d1; line-height: 1.7; }.hero-rail { display: flex; align-items: center; gap: 9px; margin-top: 21px; color: #e6f1ed; font-size: 12px; font-weight: 650; }.live-dot, .status-pulse, .browser-window-dot, .case-row-mark, .run-status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--ui-coral); }.live-dot { box-shadow: 0 0 0 4px rgba(237, 118, 94, .14); }.live-dot.muted { background: #c5a15b; box-shadow: 0 0 0 4px rgba(197, 161, 91, .13); }.rail-separator { width: 28px; height: 1px; background: rgba(233, 245, 239, .3); }.rail-muted { color: #a9bbb8; font-weight: 500; }.hero-controls { width: 250px; flex: 0 0 250px; }.hero-controls label { display: block; margin-bottom: 7px; color: #b9cbc7; font-size: 11px; font-weight: 700; }.hero-controls :deep(.ant-select-selector) { border-color: #637474 !important; background: rgba(255, 255, 255, .08) !important; color: #fff !important; }.hero-controls :deep(.ant-select-selection-placeholder), .hero-controls :deep(.ant-select-selection-item) { color: #fff !important; }.hero-control-row { display: flex; align-items: center; justify-content: space-between; margin-top: 13px; }.hero-control-row .ant-btn { color: #c9d8d4; }.worker-alert, .readonly-alert { margin-top: 14px; }.signal-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }.signal-card { min-height: 106px; padding: 17px 18px; border: 1px solid var(--ui-line); border-radius: 10px; background: var(--ui-panel); box-shadow: 0 7px 18px rgba(34, 46, 43, .045); }.signal-card-primary { border-top: 3px solid var(--ui-mint); }.signal-card-run { border-top: 3px solid var(--ui-coral); }.signal-label { display: block; color: var(--ui-muted); font-size: 11px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em; }.signal-card strong { display: block; margin-top: 8px; font-size: 28px; letter-spacing: -.05em; }.signal-note { display: block; margin-top: 5px; color: #9a a3a0; font-size: 11px; }
.studio-grid { display: grid; grid-template-columns: 235px minmax(0, 1fr) 265px; gap: 14px; align-items: start; }.panel { border: 1px solid var(--ui-line); border-radius: 12px; background: var(--ui-panel); box-shadow: 0 8px 20px rgba(34, 46, 43, .045); }.module-rail, .observe-rail { min-width: 0; padding: 18px; }.panel h2 { margin: 5px 0 7px; font-size: 18px; letter-spacing: -.03em; }.panel-description { margin: 0 0 15px; color: var(--ui-muted); font-size: 11px; line-height: 1.6; }.rail-divider { height: 1px; margin: 17px 0; background: var(--ui-line); }.worker-card { padding: 11px; border: 1px solid #ecd5cd; border-radius: 9px; background: #fff8f5; }.worker-card.ready { border-color: #cce3dd; background: #f4fbf8; }.worker-card-head { display: flex; align-items: center; gap: 8px; font-size: 12px; }.status-pulse.ready { background: var(--ui-mint); box-shadow: 0 0 0 4px rgba(107, 185, 174, .15); }.worker-card p { margin: 7px 0 10px; color: var(--ui-muted); font-size: 10px; line-height: 1.5; }.asset-links { display: grid; gap: 4px; }.asset-links button { display: flex; align-items: center; gap: 8px; width: 100%; padding: 7px 0; border: 0; background: transparent; color: var(--ui-ink); cursor: pointer; font-size: 11px; text-align: left; }.asset-links button:hover, .asset-links button:focus-visible { color: var(--ui-coral); }.asset-links strong { margin-left: auto; font-family: ui-monospace, monospace; font-size: 12px; }.asset-link-mark { width: 7px; height: 7px; border-radius: 2px; background: var(--ui-mint); }.asset-link-mark.coral { background: var(--ui-coral); }.asset-link-mark.violet { background: var(--ui-violet); }
.browser-console { min-width: 0; padding: 20px; }.console-head, .asset-band-head, .detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }.console-head h2 { font-size: 21px; }.console-head p { margin: 0; color: var(--ui-muted); font-size: 11px; }.console-actions { display: flex; gap: 7px; flex-wrap: wrap; justify-content: flex-end; }.browser-launch-bar { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(180px, 1.5fr) auto auto; gap: 8px; align-items: center; margin: 17px 0 13px; padding: 9px; border: 1px solid #cbd8d5; border-radius: 8px; background: #edf5f2; }.browser-launch-copy { display: flex; align-items: center; gap: 9px; min-width: 0; }.browser-window-dot { flex: 0 0 auto; width: 12px; height: 12px; background: var(--ui-coral); box-shadow: 16px 0 0 #e9bf57, 32px 0 0 var(--ui-mint); margin-right: 26px; }.browser-launch-copy strong, .browser-launch-copy small { display: block; }.browser-launch-copy strong { font-size: 11px; }.browser-launch-copy small { margin-top: 2px; color: var(--ui-muted); font-size: 9px; white-space: nowrap; }.recorded-note { display: flex; align-items: center; gap: 7px; margin: 10px 0; padding: 8px 10px; border-radius: 6px; background: #f2fbf7; color: #3b786f; font-size: 11px; }.case-list-head { display: flex; justify-content: space-between; margin: 12px 0 7px; color: var(--ui-muted); font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }.case-list { display: grid; gap: 5px; max-height: 300px; overflow-y: auto; }.case-row { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 9px; border: 1px solid transparent; border-radius: 7px; background: #faf9f5; color: var(--ui-ink); cursor: pointer; text-align: left; transition: border-color .16s ease, background .16s ease, transform .16s ease; }.case-row:hover, .case-row:focus-visible { border-color: #eeb9ae; background: #fff8f5; transform: translateX(2px); }.case-row.selected { border-color: #e39a89; background: #fff4ef; }.case-row-mark { flex: 0 0 auto; width: 6px; height: 28px; border-radius: 2px; background: #dfe4e1; }.case-row-mark.active { background: var(--ui-coral); }.case-row-main { min-width: 0; flex: 1; }.case-row-main strong, .case-row-main small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.case-row-main strong { font-size: 12px; }.case-row-main small { margin-top: 3px; color: var(--ui-muted); font-size: 10px; }.case-row-meta { display: flex; align-items: flex-end; flex-direction: column; gap: 3px; }.case-level { color: var(--ui-muted); font-family: ui-monospace, monospace; font-size: 9px; }.case-detail { margin-top: 15px; padding-top: 16px; border-top: 1px solid var(--ui-line); }.case-code { color: var(--ui-coral); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; font-weight: 700; }.detail-head h3 { margin: 3px 0 0; font-size: 17px; }.detail-meta { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 10px 0 13px; color: var(--ui-muted); font-size: 10px; }.trace-strip { display: flex; align-items: center; gap: 7px; }.trace-step { display: inline-flex; align-items: center; gap: 5px; color: #a2aaa7; font-size: 10px; font-weight: 700; white-space: nowrap; }.trace-step b { color: #a2aaa7; font-family: ui-monospace, monospace; font-size: 9px; }.trace-step.trace-active { color: var(--ui-ink); }.trace-step.trace-active b { color: var(--ui-coral); }.trace-line { flex: 1; min-width: 12px; height: 1px; background: #cbd6d2; }.detail-trace { margin-bottom: 13px; }.step-preview { padding: 11px; border-radius: 8px; background: #202b2d; color: #f6f3eb; }.step-preview-head { display: flex; justify-content: space-between; color: #e8f1ed; font-size: 10px; }.step-preview-head span { color: #9fb5b0; font-family: ui-monospace, monospace; }.step-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }.step-chip { padding: 5px 7px; border: 1px solid rgba(125, 213, 198, .25); border-radius: 4px; color: #bde7de; font-family: ui-monospace, monospace; font-size: 10px; }.step-chip b { margin-right: 5px; color: var(--ui-coral); }.step-chip.more { color: #f2c3b7; }.config-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.config-grid div { padding: 9px; border-left: 2px solid #d9e5e1; background: #faf9f5; }.config-grid span, .config-grid strong { display: block; }.config-grid span { color: var(--ui-muted); font-size: 9px; }.config-grid strong { margin-top: 5px; font-size: 11px; }.detail-loading { display: block; margin: 16px auto 0; }
.observe-rail h2 { font-size: 19px; }.observe-metric-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }.observe-metric-row div { padding: 10px; border-radius: 7px; background: #faf9f5; }.observe-metric-row strong, .observe-metric-row span { display: block; }.observe-metric-row strong { font-size: 22px; }.observe-metric-row span { margin-top: 4px; color: var(--ui-muted); font-size: 9px; }.run-list { display: grid; gap: 3px; margin-top: 8px; }.run-row { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 0; border: 0; border-bottom: 1px solid #eef0ed; background: transparent; color: var(--ui-ink); cursor: pointer; text-align: left; }.run-row:hover, .run-row:focus-visible { color: var(--ui-coral); }.run-status-dot { flex: 0 0 auto; width: 7px; height: 7px; background: #c7cfcc; }.run-status-dot.status-passed { background: var(--ui-mint); }.run-status-dot.status-failed, .run-status-dot.status-error { background: var(--ui-coral); }.run-status-dot.status-running { background: #5e9bc3; }.run-row-main { min-width: 0; flex: 1; }.run-row-main strong, .run-row-main small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.run-row-main strong { font-size: 10px; }.run-row-main small { margin-top: 2px; color: var(--ui-muted); font-size: 9px; }.run-arrow { color: var(--ui-muted); font-size: 13px; }.observe-all { margin-top: 14px; }
.asset-band { margin-top: 14px; padding: 18px; }.asset-band-head h2 { margin-bottom: 0; }.asset-band-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; margin-top: 14px; }.asset-card { position: relative; min-height: 125px; padding: 14px; overflow: hidden; border: 1px solid var(--ui-line); border-radius: 8px; background: #fbfaf6; color: var(--ui-ink); cursor: pointer; text-align: left; transition: transform .16s ease, box-shadow .16s ease; }.asset-card:hover, .asset-card:focus-visible { transform: translateY(-2px); box-shadow: 0 8px 17px rgba(34, 46, 43, .09); }.asset-card-mint { border-top: 3px solid var(--ui-mint); }.asset-card-coral { border-top: 3px solid var(--ui-coral); }.asset-card-violet { border-top: 3px solid var(--ui-violet); }.asset-card-note { cursor: default; border-top: 3px solid #d3a95f; }.asset-card-index { display: block; color: var(--ui-muted); font-family: ui-monospace, monospace; font-size: 9px; }.asset-card strong, .asset-card small { display: block; }.asset-card strong { margin-top: 10px; font-size: 13px; }.asset-card small { max-width: 185px; margin-top: 4px; color: var(--ui-muted); font-size: 10px; line-height: 1.4; }.asset-card b { position: absolute; right: 13px; bottom: 11px; font-family: ui-monospace, monospace; font-size: 22px; }.diagnostic-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 13px; }.diagnostic-tags :deep(.ant-tag) { margin: 0; font-size: 10px; }
button:focus-visible, a:focus-visible, :deep(.ant-btn:focus-visible), :deep(.ant-select-selector:focus-visible), :deep(input:focus-visible) { outline: 2px solid var(--ui-coral); outline-offset: 2px; }
@media (max-width: 1180px) { .studio-grid { grid-template-columns: 210px minmax(0, 1fr); }.observe-rail { grid-column: 1 / -1; }.run-list { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }.asset-band-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 800px) { .ui-hero { flex-direction: column; padding: 24px 20px; }.hero-controls { width: 100%; flex-basis: auto; }.signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.studio-grid { grid-template-columns: 1fr; }.module-rail, .observe-rail { grid-column: auto; }.browser-launch-bar { grid-template-columns: 1fr; }.config-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.console-head, .detail-head { flex-direction: column; }.console-actions { justify-content: flex-start; }.run-list { grid-template-columns: 1fr; } }
@media (max-width: 480px) { .signal-grid, .asset-band-grid { grid-template-columns: 1fr; }.browser-console, .module-rail, .observe-rail, .asset-band { padding: 14px; }.ui-hero h1 { font-size: 25px; } }
@media (prefers-reduced-motion: reduce) { .case-row, .asset-card { transition: none; } }
.signal-note { color: #9aa3a0; }
</style>
