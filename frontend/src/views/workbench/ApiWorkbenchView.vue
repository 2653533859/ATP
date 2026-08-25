<template>
  <div class="page-shell api-workbench">
    <section class="api-hero">
      <div class="hero-copy">
        <div class="eyebrow"><ApiOutlined /> {{ t('api_workbench.eyebrow') }}</div>
        <h1>{{ t('api_workbench.title') }}</h1>
        <p>{{ t('api_workbench.subtitle') }}</p>
        <div class="hero-rail">
          <span class="live-dot" />
          <span>{{ t('api_workbench.execution_rail') }}</span>
          <span class="rail-separator" />
          <span class="rail-muted">{{ selectedProjectName || t('api_workbench.no_project') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label>{{ t('api_workbench.project_label') }}</label>
        <a-select
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :placeholder="t('api_workbench.project_placeholder')"
          @change="handleProjectChange"
        />
        <a-button :loading="loading || environmentsLoading" @click="refreshWorkbench">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </div>
    </section>

    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('api_workbench.readonly_title')"
      :description="t('api_workbench.readonly_description')"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('api_workbench.select_project_hint')" />

    <template v-else>
      <section class="signal-grid" aria-label="API workspace summary">
        <div class="signal-card signal-card-primary">
          <span class="signal-label">{{ t('api_workbench.signals.api_cases') }}</span>
          <strong>{{ filteredCases.length }}</strong>
          <span class="signal-note">{{ selectedModuleId ? t('api_workbench.signals.module_scope') : t('api_workbench.signals.project_scope') }}</span>
        </div>
        <div class="signal-card">
          <span class="signal-label">{{ t('api_workbench.signals.ready') }}</span>
          <strong>{{ readyCount }}</strong>
          <span class="signal-note">{{ t('api_workbench.signals.ready_note') }}</span>
        </div>
        <div class="signal-card">
          <span class="signal-label">{{ t('api_workbench.signals.recent_pass_rate') }}</span>
          <strong>{{ recentPassRate }}%</strong>
          <span class="signal-note">{{ t('api_workbench.signals.recent_note') }}</span>
        </div>
        <div class="signal-card signal-card-run">
          <span class="signal-label">{{ t('api_workbench.signals.last_activity') }}</span>
          <strong>{{ lastActivityLabel }}</strong>
          <span class="signal-note">{{ lastActivityTime }}</span>
        </div>
      </section>

      <section class="workbench-frame">
        <aside class="module-column">
          <div class="column-kicker">{{ t('api_workbench.module_kicker') }}</div>
          <h2>{{ t('api_workbench.module_title') }}</h2>
          <p class="column-description">{{ t('api_workbench.module_description') }}</p>
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            show-reset
            :reset-disabled="!selectedModuleId"
            :editable="canModify"
            @select="handleModuleSelect"
            @reset="handleModuleReset"
          />
          <div class="protocol-key">
            <div class="column-kicker">{{ t('api_workbench.protocol_kicker') }}</div>
            <div v-for="protocol in API_CASE_TYPES" :key="protocol" class="protocol-key-row">
              <span class="protocol-mark" :class="`protocol-${protocol}`" />
              <span>{{ protocolLabel(protocol) }}</span>
            </div>
          </div>
        </aside>

        <main class="case-column">
          <div class="case-toolbar">
            <div>
              <div class="column-kicker">{{ t('api_workbench.case_kicker') }}</div>
              <h2>{{ selectedModuleName || t('api_workbench.all_modules') }}</h2>
              <p>{{ t('api_workbench.case_description') }}</p>
            </div>
            <div class="toolbar-actions">
              <a-button :disabled="!selectedModuleId || !canModify" @click="openImport">
                <ThunderboltOutlined /> {{ t('api_workbench.import_generate') }}
              </a-button>
              <a-button type="primary" :disabled="!selectedModuleId || !canModify" @click="openCreate">
                <PlusOutlined /> {{ t('api_workbench.new_case') }}
              </a-button>
            </div>
          </div>

          <div class="filter-strip">
            <a-input-search
              v-model:value="keyword"
              allow-clear
              :placeholder="t('api_workbench.search_placeholder')"
              @search="loadCases"
            />
            <a-select v-model:value="protocolFilter" :options="protocolOptions" @change="loadCases" />
            <a-button type="text" @click="resetFilters"><FilterOutlined /> {{ t('common.reset') }}</a-button>
          </div>

          <a-table
            :data-source="filteredCases"
            :columns="columns"
            :loading="loading"
            row-key="id"
            :pagination="{ pageSize: 10, hideOnSinglePage: true }"
            :locale="{ emptyText: t('api_workbench.empty_cases') }"
            class="api-case-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <button class="case-name-button" type="button" @click="openDetail(asCase(record))">
                  {{ asCase(record).name }}
                </button>
                <div class="case-code">{{ asCase(record).case_code }}</div>
              </template>
              <template v-else-if="column.key === 'protocol'">
                <a-tag :color="protocolColor(asCase(record).case_type)">{{ protocolLabel(asCase(record).case_type as ApiCaseType) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'level'">
                <span class="level-chip">{{ t(`case.levels.${asCase(record).case_level}`) }}</span>
              </template>
              <template v-else-if="column.key === 'last_run'">
                <span class="run-state" :class="`run-${lastRunStatus(asCase(record))}`">
                  <span class="state-dot" /> {{ runStatusLabel(lastRunStatus(asCase(record))) }}
                </span>
              </template>
              <template v-else-if="column.key === 'updated_at'">
                <span class="muted-cell">{{ formatTime(asCase(record).updated_at) }}</span>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space size="small">
                  <a-button type="link" size="small" @click="openDetail(asCase(record))">{{ t('common.view_detail') }}</a-button>
                  <a-button type="link" size="small" :disabled="!canModify" @click="openEdit(asCase(record))">{{ t('common.edit') }}</a-button>
                  <a-button type="link" size="small" :disabled="!canModify || !asCase(record).is_ready_for_execution" @click="openRun(asCase(record))">
                    <PlayCircleOutlined /> {{ t('api_workbench.run') }}
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </main>
      </section>
    </template>

    <a-drawer v-model:open="detailOpen" :title="selectedCase?.name || t('api_workbench.detail_title')" width="620px">
      <a-spin :spinning="detailLoading">
        <template v-if="selectedCase">
          <div class="detail-headline">
            <div>
              <span class="case-code">{{ selectedCase.case_code }}</span>
              <h2>{{ selectedCase.name }}</h2>
            </div>
            <a-tag :color="protocolColor(selectedCase.case_type)">{{ protocolLabel(selectedCase.case_type as ApiCaseType) }}</a-tag>
          </div>
          <div class="detail-actions">
            <a-button type="primary" :disabled="!canModify || !selectedCase.is_ready_for_execution" @click="openRun(selectedCase)">
              <PlayCircleOutlined /> {{ t('api_workbench.run_now') }}
            </a-button>
            <a-button :disabled="!canModify" @click="openEdit(selectedCase)">{{ t('common.edit') }}</a-button>
          </div>

          <section class="detail-block">
            <div class="detail-block-title">{{ t('api_workbench.request_snapshot') }}</div>
            <div class="request-snapshot">
              <div class="request-method">{{ selectedRequest.method }}</div>
              <code>{{ selectedRequest.target || t('api_workbench.target_missing') }}</code>
            </div>
            <div class="request-meta">
              <span>{{ t('api_workbench.request_steps', { count: selectedSteps.length }) }}</span>
              <span>{{ t('api_workbench.request_assertions', { count: selectedAssertionCount }) }}</span>
              <span>{{ selectedCase.dataset_id ? t('api_workbench.dataset_bound') : t('api_workbench.dataset_unbound') }}</span>
            </div>
          </section>

          <section class="detail-block">
            <div class="detail-block-title">{{ t('api_workbench.recent_runs') }}</div>
            <a-empty v-if="!selectedRunHistory.length" :description="t('api_workbench.no_runs')" />
            <div v-for="run in selectedRunHistory" :key="run.id" class="run-history-row">
              <div>
                <span class="run-state" :class="`run-${run.status}`"><span class="state-dot" />{{ runStatusLabel(run.status) }}</span>
                <span class="run-time">{{ formatTime(run.created_at) }}</span>
              </div>
              <div class="run-history-right">
                <span>{{ formatDuration(run.duration_ms) }}</span>
                <a-button type="link" size="small" @click="openRunDetail(run.id)">{{ t('api_workbench.open_result') }}</a-button>
              </div>
            </div>
          </section>
        </template>
      </a-spin>
    </a-drawer>

    <a-modal v-model:open="runModalOpen" :title="t('api_workbench.run_title')" :confirm-loading="runLoading" @ok="confirmRun">
      <a-form layout="vertical">
        <a-form-item :label="t('api_workbench.run_case_label')">
          <strong>{{ pendingRunCase?.name || '—' }}</strong>
        </a-form-item>
        <a-form-item :label="t('api_workbench.environment_label')">
          <a-select
            v-model:value="runEnvironmentId"
            allow-clear
            :options="environmentOptions"
            :placeholder="t('api_workbench.environment_placeholder')"
            style="width: 100%"
          />
          <div class="form-hint">{{ t('api_workbench.environment_hint') }}</div>
        </a-form-item>
      </a-form>
    </a-modal>

    <CaseFormDrawer
      :open="caseFormOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      :edit-case="editingCase"
      :default-case-type="defaultCaseType"
      @close="closeCaseForm"
      @saved="handleSaved"
    />

    <AIGenerateDrawer
      :open="importDrawerOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      :allowed-case-types="API_CASE_TYPES"
      @close="importDrawerOpen = false"
      @saved="handleSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  FilterOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  caseApi,
  environmentApi,
  projectApi,
  runApi,
  type CaseDetailItem,
  type CaseSummaryItem,
  type CaseType,
  type EnvironmentItem,
  type ProjectItem,
  type RunDetailItem,
} from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import AIGenerateDrawer from '@/views/case/AIGenerateDrawer.vue'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type ApiCaseType = 'api' | 'graphql' | 'websocket' | 'grpc'
type ProtocolFilter = 'all' | ApiCaseType
type ErrorLike = { response?: { data?: { detail?: unknown } }; message?: unknown }

const API_CASE_TYPES: CaseType[] = ['api', 'graphql', 'websocket', 'grpc']

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
const selectedModuleId = ref<number | null>(positiveInt(route.query.module_id))
const cases = ref<CaseSummaryItem[]>([])
const recentRuns = ref<RunDetailItem[]>([])
const environments = ref<EnvironmentItem[]>([])
const keyword = ref('')
const protocolFilter = ref<ProtocolFilter>('all')
const loading = ref(false)
const environmentsLoading = ref(false)
const detailOpen = ref(false)
const detailLoading = ref(false)
const selectedCase = ref<CaseSummaryItem | null>(null)
const selectedCaseDetail = ref<CaseDetailItem | null>(null)
const caseFormOpen = ref(false)
const editingCase = ref<CaseDetailItem | null>(null)
const importDrawerOpen = ref(false)
const runModalOpen = ref(false)
const runLoading = ref(false)
const pendingRunCase = ref<CaseSummaryItem | null>(null)
const runEnvironmentId = ref<number | undefined>(undefined)
let loadSequence = 0
let detailSequence = 0
let environmentSequence = 0

const projectOptions = computed(() => projects.value.map((project) => ({
  label: project.name,
  value: project.id,
})) )
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const selectedModuleName = computed(() => selectedModuleId.value ? t('api_workbench.selected_module', { id: selectedModuleId.value }) : '')
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const defaultCaseType = computed<CaseType>(() => protocolFilter.value === 'all' ? 'api' : protocolFilter.value)
const protocolOptions = computed(() => [
  { label: t('api_workbench.protocol_all'), value: 'all' },
  ...API_CASE_TYPES.map((protocol) => ({ label: protocolLabel(protocol), value: protocol })),
])
const environmentOptions = computed(() => environments.value.map((environment) => ({
  label: environment.name,
  value: environment.id,
})) )
const filteredCases = computed(() => cases.value.filter((item) => protocolFilter.value === 'all' || item.case_type === protocolFilter.value))
const readyCount = computed(() => filteredCases.value.filter((item) => item.is_ready_for_execution).length)
const recentApiRuns = computed(() => recentRuns.value.filter((run) => cases.value.some((item) => item.id === run.case_id)))
const recentPassRate = computed(() => {
  if (!recentApiRuns.value.length) return 0
  const passed = recentApiRuns.value.filter((run) => run.status === 'passed').length
  return Math.round((passed / recentApiRuns.value.length) * 100)
})
const lastActivity = computed(() => recentApiRuns.value[0])
const lastActivityLabel = computed(() => lastActivity.value ? runStatusLabel(lastActivity.value.status) : t('api_workbench.no_activity'))
const lastActivityTime = computed(() => lastActivity.value ? formatTime(lastActivity.value.created_at) : t('api_workbench.no_activity_hint'))
const selectedSteps = computed(() => {
  const raw = selectedCaseDetail.value?.config?.steps
  return Array.isArray(raw) ? raw as Array<Record<string, unknown>> : []
})
const selectedRequest = computed(() => {
  const step = selectedSteps.value[0] || {}
  const type = selectedCaseDetail.value?.case_type
  if (type === 'graphql') return { method: 'POST', target: String(step.endpoint || '') }
  if (type === 'grpc') return { method: 'RPC', target: `${String(step.target || '')}/${String(step.service || '')}/${String(step.method || '')}` }
  return { method: String(step.method || (type === 'websocket' ? 'WS' : 'GET')), target: String(step.url || '') }
})
const selectedAssertionCount = computed(() => selectedSteps.value.reduce((sum, step) => sum + (Array.isArray(step.assertions) ? step.assertions.length : 0), 0))
const selectedRunHistory = computed(() => selectedCase.value ? recentRuns.value.filter((run) => run.case_id === selectedCase.value?.id).slice(0, 8) : [])
const columns = computed(() => [
  { title: t('api_workbench.columns.name'), key: 'name', width: 250 },
  { title: t('api_workbench.columns.protocol'), key: 'protocol', width: 120 },
  { title: t('api_workbench.columns.priority'), dataIndex: 'priority', key: 'priority', width: 90 },
  { title: t('api_workbench.columns.level'), key: 'level', width: 100 },
  { title: t('api_workbench.columns.last_run'), key: 'last_run', width: 130 },
  { title: t('api_workbench.columns.updated_at'), key: 'updated_at', width: 150 },
  { title: t('api_workbench.columns.action'), key: 'action', width: 250 },
])

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function asCase(record: unknown) {
  return record as CaseSummaryItem
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return error instanceof Error ? error.message : fallback
}

function protocolLabel(protocol: ApiCaseType | CaseType) {
  return t(`api_workbench.protocols.${protocol}`)
}

function protocolColor(protocol: CaseType) {
  return ({ api: 'blue', graphql: 'orange', websocket: 'cyan', grpc: 'purple' } as Record<string, string>)[protocol] || 'default'
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '—'
}

function formatDuration(value?: number | null) {
  if (value == null) return '—'
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)} s`
}

function runStatusLabel(status?: string | null) {
  if (!status) return t('api_workbench.run_status.none')
  const key = ['pending', 'running', 'passed', 'failed', 'error', 'cancelled', 'stopped'].includes(status) ? status : 'unknown'
  return t(`api_workbench.run_status.${key}`)
}

function lastRunStatus(item: CaseSummaryItem) {
  return recentRuns.value.find((run) => run.case_id === item.id)?.status || 'none'
}

function syncRoute() {
  void router.replace({
    query: {
      ...(selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {}),
      ...(selectedModuleId.value ? { module_id: String(selectedModuleId.value) } : {}),
    },
  })
}

async function loadEnvironments() {
  const projectId = selectedProjectId.value
  const sequence = ++environmentSequence
  if (!projectId) {
    environments.value = []
    environmentsLoading.value = false
    return
  }
  environmentsLoading.value = true
  try {
    const result = await environmentApi.list(projectId)
    if (sequence !== environmentSequence) return
    environments.value = result
  } catch {
    if (sequence === environmentSequence) environments.value = []
  } finally {
    if (sequence === environmentSequence) environmentsLoading.value = false
  }
}

async function loadRecentRuns(caseIds: number[], sequence?: number) {
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

async function loadCases() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    cases.value = []
    recentRuns.value = []
    return
  }
  const sequence = ++loadSequence
  loading.value = true
  try {
    const result = await caseApi.list({
      project_id: projectId,
      module_id: selectedModuleId.value ?? undefined,
      keyword: keyword.value.trim() || undefined,
    })
    if (sequence !== loadSequence) return
    cases.value = result.filter((item) => API_CASE_TYPES.includes(item.case_type))
    await loadRecentRuns(cases.value.map((item) => item.id), sequence)
  } catch (error: unknown) {
    if (sequence === loadSequence) message.error(errorMessage(error, t('api_workbench.load_failed')))
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (!selectedProjectId.value || !projects.value.some((item) => item.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
    }
    await Promise.all([loadEnvironments(), loadCases()])
    syncRoute()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.load_failed')))
  }
}

async function handleProjectChange(value: unknown) {
  selectedProjectId.value = positiveInt(value)
  selectedModuleId.value = null
  await Promise.all([loadEnvironments(), loadCases()])
  syncRoute()
}

async function handleModuleSelect(moduleId: number | null) {
  selectedModuleId.value = moduleId
  await loadCases()
  syncRoute()
}

async function handleModuleReset() {
  selectedModuleId.value = null
  await loadCases()
  syncRoute()
}

async function refreshWorkbench() {
  // loadProjects 会在确认当前项目后统一刷新环境、用例和 URL，避免刷新按钮触发重复请求。
  await loadProjects()
}

function resetFilters() {
  keyword.value = ''
  protocolFilter.value = 'all'
  void loadCases()
}

function openCreate() {
  if (!selectedModuleId.value) {
    message.warning(t('api_workbench.select_module_first'))
    return
  }
  if (!canModify.value) {
    message.warning(t('api_workbench.readonly_title'))
    return
  }
  invalidateDetailRequest()
  editingCase.value = null
  caseFormOpen.value = true
}

function invalidateDetailRequest() {
  detailSequence += 1
  detailLoading.value = false
}

function closeCaseForm() {
  invalidateDetailRequest()
  caseFormOpen.value = false
  editingCase.value = null
}

async function openEdit(item: CaseSummaryItem) {
  if (!canModify.value) return
  const sequence = ++detailSequence
  detailLoading.value = true
  try {
    const detail = await caseApi.get(item.id)
    if (sequence !== detailSequence) return
    editingCase.value = detail
    caseFormOpen.value = true
  } catch (error: unknown) {
    if (sequence === detailSequence) message.error(errorMessage(error, t('api_workbench.detail_failed')))
  } finally {
    if (sequence === detailSequence) detailLoading.value = false
  }
}

async function openDetail(item: CaseSummaryItem) {
  const sequence = ++detailSequence
  selectedCase.value = item
  selectedCaseDetail.value = null
  detailOpen.value = true
  detailLoading.value = true
  try {
    const detail = await caseApi.get(item.id)
    if (sequence !== detailSequence) return
    selectedCaseDetail.value = detail
  } catch (error: unknown) {
    if (sequence === detailSequence) message.error(errorMessage(error, t('api_workbench.detail_failed')))
  } finally {
    if (sequence === detailSequence) detailLoading.value = false
  }
}

function openImport() {
  if (!selectedModuleId.value) {
    message.warning(t('api_workbench.select_module_first'))
    return
  }
  importDrawerOpen.value = true
}

function handleSaved() {
  invalidateDetailRequest()
  caseFormOpen.value = false
  importDrawerOpen.value = false
  void loadCases()
}

function openRun(item: CaseSummaryItem) {
  if (!canModify.value || !item.is_ready_for_execution) return
  pendingRunCase.value = item
  runEnvironmentId.value = undefined
  runModalOpen.value = true
}

async function confirmRun() {
  if (!pendingRunCase.value) return
  runLoading.value = true
  try {
    const result = await caseApi.run(pendingRunCase.value.id, {
      env_id: runEnvironmentId.value,
    })
    runModalOpen.value = false
    message.success(t('api_workbench.run_started'))
    await loadCases()
    await router.push({ name: 'run-detail', params: { runId: String(result.id) } })
  } catch (error: unknown) {
    message.error(errorMessage(error, t('api_workbench.run_failed')))
  } finally {
    runLoading.value = false
  }
}

function openRunDetail(runId: number) {
  void router.push({ name: 'run-detail', params: { runId: String(runId) } })
}

onMounted(() => {
  void loadProjects()
})
</script>

<style scoped>
.api-workbench {
  --api-ink: #122033;
  --api-muted: #6b7a90;
  --api-line: #dfe6ef;
  --api-cyan: #16a6b6;
  --api-amber: #f3a33a;
  color: var(--api-ink);
}

.api-hero {
  display: flex;
  justify-content: space-between;
  gap: 28px;
  padding: 28px 30px 24px;
  border: 1px solid #dce6ef;
  border-radius: 18px;
  background: linear-gradient(112deg, #f8fbfc 0%, #edf7f7 62%, #fff8ea 100%);
  box-shadow: 0 14px 34px rgba(33, 55, 77, 0.07);
}

.hero-copy { min-width: 0; }
.eyebrow, .column-kicker { color: var(--api-cyan); font-size: 11px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
.eyebrow { display: flex; align-items: center; gap: 7px; }
.api-hero h1 { margin: 8px 0 8px; color: #0c2635; font-size: 30px; letter-spacing: -.04em; }
.api-hero p { max-width: 680px; margin: 0; color: var(--api-muted); line-height: 1.7; }
.hero-rail { display: flex; align-items: center; gap: 9px; margin-top: 20px; color: #285362; font-size: 12px; font-weight: 650; }
.live-dot, .state-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--api-cyan); box-shadow: 0 0 0 4px rgba(22, 166, 182, .13); }
.rail-separator { width: 1px; height: 14px; margin: 0 2px; background: #bbd5d6; }
.rail-muted { color: #8a9aaa; font-weight: 500; }
.hero-controls { display: flex; flex: 0 0 250px; flex-direction: column; align-items: stretch; gap: 8px; }
.hero-controls label { color: var(--api-muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.hero-controls .ant-select { width: 100%; }
.hero-controls .ant-btn { margin-top: 4px; align-self: flex-start; }
.readonly-alert { margin-top: 16px; }
.project-empty { min-height: 320px; padding: 100px 0; }

.signal-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.signal-card { position: relative; min-height: 112px; overflow: hidden; padding: 17px 18px; border: 1px solid var(--api-line); border-radius: 12px; background: #fff; }
.signal-card::after { position: absolute; right: 0; bottom: 0; width: 44px; height: 3px; background: #d9e2ea; content: ''; }
.signal-card-primary { border-color: #b8e0e2; background: #f3fcfc; }
.signal-card-primary::after { background: var(--api-cyan); }
.signal-card-run::after { background: var(--api-amber); }
.signal-label { display: block; color: var(--api-muted); font-size: 11px; font-weight: 750; letter-spacing: .05em; text-transform: uppercase; }
.signal-card strong { display: block; margin-top: 10px; color: #102d3d; font-size: 28px; letter-spacing: -.05em; }
.signal-note { display: block; margin-top: 4px; color: #93a0ad; font-size: 11px; }

.workbench-frame { display: grid; grid-template-columns: 230px minmax(0, 1fr); min-height: 520px; overflow: hidden; border: 1px solid var(--api-line); border-radius: 16px; background: #fff; box-shadow: 0 10px 25px rgba(31, 49, 65, .05); }
.module-column { padding: 22px 17px; border-right: 1px solid #e7edf2; background: #f8fafb; }
.module-column h2, .case-column h2 { margin: 5px 0 4px; color: #163042; font-size: 18px; letter-spacing: -.025em; }
.column-description { margin: 0 0 18px; color: var(--api-muted); font-size: 12px; line-height: 1.6; }
.protocol-key { margin-top: 28px; padding-top: 18px; border-top: 1px solid #e2e9ee; }
.protocol-key-row { display: flex; align-items: center; gap: 9px; margin-top: 9px; color: #68798a; font-size: 12px; }
.protocol-mark { width: 8px; height: 8px; border-radius: 2px; background: #8093a7; }
.protocol-api { background: #4f86e8; }.protocol-graphql { background: #ee9d32; }.protocol-websocket { background: #1db1bf; }.protocol-grpc { background: #8d6bd1; }
.case-column { min-width: 0; padding: 23px 24px 26px; }
.case-toolbar { display: flex; justify-content: space-between; gap: 18px; padding-bottom: 18px; border-bottom: 1px solid #e9eef2; }
.case-toolbar p { margin: 0; color: var(--api-muted); font-size: 12px; }
.toolbar-actions { display: flex; flex-shrink: 0; align-items: flex-start; gap: 8px; }
.filter-strip { display: flex; align-items: center; gap: 9px; padding: 16px 0; }
.filter-strip .ant-input-search { width: 260px; }
.filter-strip .ant-select { width: 150px; }
.api-case-table :deep(.ant-table-thead > tr > th) { color: #718398; background: #f7f9fb; font-size: 11px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
.api-case-table :deep(.ant-table-tbody > tr > td) { padding-top: 14px; padding-bottom: 14px; }
.case-name-button { display: block; max-width: 250px; overflow: hidden; padding: 0; border: 0; background: transparent; color: #165a70; cursor: pointer; font-size: 13px; font-weight: 700; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.case-name-button:hover, .case-name-button:focus-visible { color: var(--api-cyan); text-decoration: underline; outline: none; }
.case-code { margin-top: 4px; color: #9aa8b5; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; }
.level-chip, .muted-cell { color: #718398; font-size: 12px; }
.run-state { display: inline-flex; align-items: center; gap: 7px; color: #7c8b9a; font-size: 12px; white-space: nowrap; }
.run-state .state-dot { width: 6px; height: 6px; background: #a9b5bf; box-shadow: none; }
.run-passed { color: #278a71; }.run-passed .state-dot { background: #39aa8c; }.run-failed, .run-error { color: #c75b58; }.run-failed .state-dot, .run-error .state-dot { background: #d96b66; }.run-running, .run-pending { color: #be7c20; }.run-running .state-dot, .run-pending .state-dot { background: var(--api-amber); }

.detail-headline { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.detail-headline h2 { margin: 4px 0 0; color: #173244; font-size: 21px; }
.detail-actions { display: flex; gap: 8px; margin: 18px 0 24px; }
.detail-block { margin-top: 24px; padding-top: 18px; border-top: 1px solid #e8edf1; }
.detail-block-title { margin-bottom: 11px; color: #51687c; font-size: 12px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.request-snapshot { display: flex; align-items: center; gap: 11px; padding: 13px; border: 1px solid #d9e5e9; border-radius: 9px; background: #f4fbfb; }
.request-method { color: #168997; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; font-weight: 800; }
.request-snapshot code { overflow: hidden; color: #294456; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.request-meta { display: flex; flex-wrap: wrap; gap: 8px 15px; margin-top: 9px; color: #8695a3; font-size: 11px; }
.run-history-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 1px solid #edf1f3; }
.run-time { margin-left: 10px; color: #9aa8b4; font-size: 11px; }
.run-history-right { display: flex; align-items: center; gap: 7px; color: #8795a1; font-size: 11px; }
.form-hint { margin-top: 6px; color: #8997a5; font-size: 12px; line-height: 1.5; }

@media (max-width: 960px) {
  .api-hero, .case-toolbar { flex-direction: column; }
  .hero-controls { flex-basis: auto; width: min(100%, 360px); }
  .signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .toolbar-actions { align-self: flex-start; }
}

@media (max-width: 700px) {
  .api-hero { padding: 21px; }
  .workbench-frame { display: block; }
  .module-column { border-right: 0; border-bottom: 1px solid #e7edf2; }
  .signal-grid { grid-template-columns: 1fr 1fr; }
  .case-column { padding: 18px 14px; }
  .filter-strip { flex-wrap: wrap; }
  .filter-strip .ant-input-search { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .case-name-button { transition: none; }
}
</style>
