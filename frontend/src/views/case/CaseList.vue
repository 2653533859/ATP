<template>
  <div class="case-page">
    <div class="page-header">
      <div>
        <h2>Case Management</h2>
        <p>Manage standardized cases by project and module, then review or run them from one place.</p>
      </div>
      <a-space wrap>
        <a-select
          v-model:value="selectedProjectId"
          placeholder="Select project"
          style="width: 240px"
          :options="projectOptions"
          allow-clear
          @change="handleProjectChange"
        />
        <a-button @click="router.push({ name: 'projects' })">Projects</a-button>
        <a-button :disabled="!selectedProjectId" @click="refreshCurrentProject">Refresh</a-button>
      </a-space>
    </div>

    <template v-if="selectedProjectId">
      <a-row :gutter="[16, 16]" class="summary-row">
        <a-col :xs="24" :sm="8">
          <a-card>
            <a-statistic title="Project" :value="currentProjectName" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8">
          <a-card>
            <a-statistic title="Modules" :value="moduleCount" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8">
          <a-card>
            <a-statistic title="Visible cases" :value="filteredCases.length" />
          </a-card>
        </a-col>
      </a-row>

      <div class="workspace">
        <div class="side-panel">
          <div class="side-title">
            <span>Modules</span>
            <a-button type="link" size="small" :disabled="!selectedModuleId" @click="clearModuleFilter">
              View all
            </a-button>
          </div>
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            @select="onModuleSelect"
          />
        </div>

        <div class="main-panel">
          <a-card class="toolbar-card" :bordered="false">
            <div class="toolbar">
              <a-space wrap>
                <a-input-search
                  v-model:value="keyword"
                  placeholder="Search name, code, or summary"
                  style="width: 260px"
                  allow-clear
                  @search="handleSearch"
                />
                <a-select
                  v-model:value="filterType"
                  placeholder="Type"
                  allow-clear
                  style="width: 130px"
                  :options="caseTypeOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterPriority"
                  placeholder="Priority"
                  allow-clear
                  style="width: 120px"
                  :options="priorityOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterLevel"
                  placeholder="Level"
                  allow-clear
                  style="width: 140px"
                >
                  <a-select-option value="smoke">smoke</a-select-option>
                  <a-select-option value="core">core</a-select-option>
                  <a-select-option value="regression">regression</a-select-option>
                  <a-select-option value="extended">extended</a-select-option>
                </a-select>
                <a-select
                  v-model:value="filterStatus"
                  placeholder="Status"
                  allow-clear
                  style="width: 120px"
                  :options="statusOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterReviewStatus"
                  placeholder="Review"
                  allow-clear
                  style="width: 140px"
                  :options="reviewStatusOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterAutomationStatus"
                  placeholder="Automation"
                  allow-clear
                  style="width: 140px"
                  :options="automationStatusOptions"
                  @change="loadCases"
                />
                <a-button @click="handleSearch">Search</a-button>
                <a-button @click="handleResetFilters">Reset</a-button>
              </a-space>

              <a-space wrap>
                <a-tag color="blue">
                  {{ selectedModuleId ? `Module: ${activeModuleName}` : 'Module: All' }}
                </a-tag>
                <a-dropdown :disabled="!selectedModuleId">
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="api" @click="openCreate('api')">API</a-menu-item>
                      <a-menu-item key="graphql" @click="openCreate('graphql')">GraphQL</a-menu-item>
                      <a-menu-item key="websocket" @click="openCreate('websocket')">WebSocket</a-menu-item>
                      <a-menu-item key="grpc" @click="openCreate('grpc')">gRPC</a-menu-item>
                      <a-menu-item key="web" @click="openCreate('web')">Web UI</a-menu-item>
                      <a-menu-item key="android" @click="openCreate('android')">Android UI</a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="primary" :disabled="!selectedModuleId">
                    <PlusOutlined /> New case <DownOutlined />
                  </a-button>
                </a-dropdown>
              </a-space>
            </div>
          </a-card>

          <a-table
            :columns="columns"
            :data-source="filteredCases"
            :loading="loading"
            row-key="id"
            size="middle"
            :pagination="{ pageSize: 20, showSizeChanger: true }"
            :scroll="{ x: 1500 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <div class="case-name-cell">
                  <a-button type="link" class="case-link" @click="openDetail(record.id)">
                    {{ record.name }}
                  </a-button>
                  <div class="case-summary">
                    {{ record.case_code }} ? {{ record.summary || 'No summary' }}
                  </div>
                  <div v-if="record.tags.length" class="case-tags">
                    <a-tag v-for="tag in record.tags.slice(0, 3)" :key="tag" color="blue">
                      {{ tag }}
                    </a-tag>
                    <a-tag v-if="record.tags.length > 3">+{{ record.tags.length - 3 }}</a-tag>
                  </div>
                </div>
              </template>

              <template v-else-if="column.key === 'module'">
                <span>{{ moduleNameMap[record.module_id] ?? `Module #${record.module_id}` }}</span>
              </template>

              <template v-else-if="column.key === 'case_type'">
                <a-tag :color="caseTypeColor(record.case_type)">{{ caseTypeLabel(record.case_type) }}</a-tag>
              </template>

              <template v-else-if="column.key === 'priority'">
                <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
              </template>

              <template v-else-if="column.key === 'case_level'">
                <a-tag>{{ record.case_level }}</a-tag>
              </template>

              <template v-else-if="column.key === 'review_status'">
                <a-tag :color="reviewStatusColor(record.review_status)">
                  {{ reviewStatusLabel(record.review_status) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'status'">
                <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
              </template>

              <template v-else-if="column.key === 'automation_status'">
                <a-tag :color="automationStatusColor(record.automation_status)">
                  {{ record.automation_status }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'updated_at'">
                {{ formatDateTime(record.updated_at) }}
              </template>

              <template v-else-if="column.key === 'action'">
                <a-space wrap size="small">
                  <a-button type="link" size="small" @click="openDetail(record.id)">Detail</a-button>
                  <a-button type="link" size="small" @click="openEdit(record)">Edit</a-button>
                  <a-tooltip :title="record.is_ready_for_execution ? 'Run this case' : 'Only approved auto or semi-auto cases can run'">
                    <a-button
                      type="link"
                      size="small"
                      :loading="runningId === record.id"
                      :disabled="!record.is_ready_for_execution"
                      @click="handleRun(record)"
                    >
                      Run
                    </a-button>
                  </a-tooltip>
                  <a-dropdown>
                    <a-button type="link" size="small">
                      More <DownOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item key="copy" @click="handleCopy(record.id)">Copy</a-menu-item>
                        <a-menu-item key="history" @click="openHistory(record.id)">
                          <HistoryOutlined /> History
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item
                          v-if="canSubmitReview(record)"
                          key="submit-review"
                          @click="handleWorkflow(record, 'submitReview')"
                        >
                          Submit review
                        </a-menu-item>
                        <a-menu-item
                          v-if="canApprove(record)"
                          key="approve"
                          @click="handleWorkflow(record, 'approve')"
                        >
                          Approve
                        </a-menu-item>
                        <a-menu-item
                          v-if="canReject(record)"
                          key="reject"
                          @click="handleWorkflow(record, 'reject')"
                        >
                          Reject
                        </a-menu-item>
                        <a-menu-item
                          v-if="canDeprecate(record)"
                          key="deprecate"
                          @click="handleWorkflow(record, 'deprecate')"
                        >
                          Deprecate
                        </a-menu-item>
                        <a-menu-item
                          v-if="canReactivate(record)"
                          key="reactivate"
                          @click="handleWorkflow(record, 'reactivate')"
                        >
                          Reactivate
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item key="delete" @click="confirmDelete(record)">Delete</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-space>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </template>

    <a-result
      v-else
      status="info"
      title="Select a project"
      sub-title="Choose a project to manage its modules and standardized cases."
    />

    <CaseFormDrawer
      :open="drawerOpen"
      :module-id="selectedModuleId"
      :edit-case="editingCase"
      :default-case-type="createCaseType"
      @close="drawerOpen = false"
      @saved="onSaved"
    />

    <WebCaseDrawer
      :open="webDrawerOpen"
      :module-id="selectedModuleId"
      :edit-case="webEditingCase"
      @close="webDrawerOpen = false"
      @saved="onSaved"
    />

    <AndroidCaseDrawer
      :open="androidDrawerOpen"
      :module-id="selectedModuleId"
      :project-id="selectedProjectId"
      :edit-case="androidEditingCase"
      @close="androidDrawerOpen = false"
      @saved="onSaved"
    />

    <a-modal
      v-model:open="runModalOpen"
      title="Select environment"
      ok-text="Run"
      cancel-text="Cancel"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">Pick an environment for this run, or leave it empty to run without one.</p>
      <a-select
        v-model:value="runEnvId"
        placeholder="No environment"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="historyCaseId"
      @close="historyOpen = false"
      @rolled="handleHistoryRolled"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { DownOutlined, HistoryOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { caseApi, environmentApi, projectApi } from '@/api'
import type {
  AutomationStatus,
  CaseLevel,
  CasePriority,
  CaseQueryParams,
  CaseStatus,
  CaseSummaryItem,
  CaseType,
  ModuleTreeItem,
  ProjectItem,
  ReviewStatus,
} from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import WebCaseDrawer from '@/views/case/WebCaseDrawer.vue'
import AndroidCaseDrawer from '@/views/case/AndroidCaseDrawer.vue'
import CaseHistoryDrawer from '@/views/case/CaseHistoryDrawer.vue'

type WorkflowAction = 'submitReview' | 'approve' | 'reject' | 'deprecate' | 'reactivate'

const route = useRoute()
const router = useRouter()

const caseTypeOptions: Array<{ label: string; value: CaseType }> = [
  { label: 'API', value: 'api' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
  { label: 'gRPC', value: 'grpc' },
  { label: 'Web UI', value: 'web' },
  { label: 'Android UI', value: 'android' },
]

const priorityOptions: Array<{ label: string; value: CasePriority }> = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

const statusOptions: Array<{ label: string; value: CaseStatus }> = [
  { label: 'Draft', value: 'draft' },
  { label: 'Active', value: 'active' },
  { label: 'Deprecated', value: 'deprecated' },
]

const reviewStatusOptions: Array<{ label: string; value: ReviewStatus }> = [
  { label: 'Pending', value: 'pending' },
  { label: 'Approved', value: 'approved' },
  { label: 'Rejected', value: 'rejected' },
]

const automationStatusOptions: Array<{ label: string; value: AutomationStatus }> = [
  { label: 'manual', value: 'manual' },
  { label: 'semi_auto', value: 'semi_auto' },
  { label: 'auto', value: 'auto' },
]

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(null)
const moduleNameMap = ref<Record<number, string>>({})
const cases = ref<CaseSummaryItem[]>([])
const loading = ref(false)
const selectedModuleId = ref<number | null>(null)
const keyword = ref('')
const filterType = ref<CaseType | undefined>(undefined)
const filterPriority = ref<CasePriority | undefined>(undefined)
const filterLevel = ref<CaseLevel | undefined>(undefined)
const filterStatus = ref<CaseStatus | undefined>(undefined)
const filterReviewStatus = ref<ReviewStatus | undefined>(undefined)
const filterAutomationStatus = ref<AutomationStatus | undefined>(undefined)
const drawerOpen = ref(false)
const editingCase = ref<CaseSummaryItem | null>(null)
const createCaseType = ref<CaseType>('api')
const webDrawerOpen = ref(false)
const webEditingCase = ref<CaseSummaryItem | null>(null)
const androidDrawerOpen = ref(false)
const androidEditingCase = ref<CaseSummaryItem | null>(null)
const runningId = ref<number | null>(null)
const historyOpen = ref(false)
const historyCaseId = ref<number | null>(null)

const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const pendingRunCase = ref<CaseSummaryItem | null>(null)

const columns = [
  { title: 'Case', key: 'name', width: 320 },
  { title: 'Module', key: 'module', width: 160 },
  { title: 'Type', key: 'case_type', width: 110 },
  { title: 'Priority', key: 'priority', width: 100 },
  { title: 'Level', key: 'case_level', width: 120 },
  { title: 'Review', key: 'review_status', width: 120 },
  { title: 'Status', key: 'status', width: 120 },
  { title: 'Automation', key: 'automation_status', width: 130 },
  { title: 'Updated at', key: 'updated_at', width: 180 },
  { title: 'Actions', key: 'action', width: 280, fixed: 'right' },
]

const projectOptions = computed(() =>
  projects.value.map((project) => ({ label: project.name, value: project.id })),
)

const currentProjectName = computed(() =>
  projects.value.find((project) => project.id === selectedProjectId.value)?.name ?? '-',
)

const moduleCount = computed(() => Object.keys(moduleNameMap.value).length)

const activeModuleName = computed(() =>
  selectedModuleId.value ? (moduleNameMap.value[selectedModuleId.value] ?? `Module #${selectedModuleId.value}`) : 'All',
)

const filteredCases = computed(() =>
  cases.value.filter((testCase) => !filterLevel.value || testCase.case_level === filterLevel.value),
)

function parsePositiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (Array.isArray(node.children) && node.children.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function formatDateTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function caseTypeLabel(type: CaseType) {
  return caseTypeOptions.find((item) => item.value === type)?.label ?? type
}

function caseTypeColor(type: CaseType) {
  return {
    api: 'geekblue',
    graphql: 'orange',
    websocket: 'cyan',
    grpc: 'red',
    web: 'purple',
    android: 'green',
  }[type] ?? 'default'
}

function priorityColor(priority: CasePriority) {
  return {
    P0: 'red',
    P1: 'orange',
    P2: 'gold',
    P3: 'default',
  }[priority]
}

function reviewStatusLabel(status: ReviewStatus) {
  return {
    pending: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
  }[status]
}

function reviewStatusColor(status: ReviewStatus) {
  return {
    pending: 'processing',
    approved: 'success',
    rejected: 'error',
  }[status]
}

function statusLabel(status: CaseStatus) {
  return {
    draft: 'Draft',
    active: 'Active',
    deprecated: 'Deprecated',
  }[status]
}

function statusColor(status: CaseStatus) {
  return {
    draft: 'default',
    active: 'success',
    deprecated: 'warning',
  }[status]
}

function automationStatusColor(status: AutomationStatus) {
  return {
    manual: 'default',
    semi_auto: 'processing',
    auto: 'success',
  }[status]
}

function canSubmitReview(testCase: CaseSummaryItem) {
  return testCase.status !== 'deprecated' && testCase.review_status !== 'pending'
}

function canApprove(testCase: CaseSummaryItem) {
  return testCase.status !== 'deprecated' && testCase.review_status === 'pending'
}

function canReject(testCase: CaseSummaryItem) {
  return testCase.review_status === 'pending'
}

function canDeprecate(testCase: CaseSummaryItem) {
  return testCase.status !== 'deprecated'
}

function canReactivate(testCase: CaseSummaryItem) {
  return testCase.status === 'deprecated' && testCase.review_status === 'approved'
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (error: any) {
    message.error(error ?? 'Failed to load projects')
    projects.value = []
  }
}

async function loadModules() {
  if (!selectedProjectId.value) {
    moduleNameMap.value = {}
    return
  }

  try {
    const tree = await projectApi.getModules(selectedProjectId.value)
    moduleNameMap.value = flattenModules(tree)
    if (selectedModuleId.value && !moduleNameMap.value[selectedModuleId.value]) {
      selectedModuleId.value = null
    }
  } catch (error: any) {
    moduleNameMap.value = {}
    message.error(error ?? 'Failed to load modules')
  }
}

async function loadCases() {
  if (!selectedProjectId.value) {
    cases.value = []
    return
  }

  loading.value = true
  try {
    const params: CaseQueryParams = {
      project_id: selectedProjectId.value,
      module_id: selectedModuleId.value ?? undefined,
      case_type: filterType.value,
      priority: filterPriority.value,
      status: filterStatus.value,
      review_status: filterReviewStatus.value,
      automation_status: filterAutomationStatus.value,
      keyword: keyword.value.trim() || undefined,
    }
    cases.value = await caseApi.list(params)
  } catch (error: any) {
    message.error(error ?? 'Failed to load cases')
    cases.value = []
  } finally {
    loading.value = false
  }
}

function syncRoute() {
  const query: Record<string, string> = {}
  if (selectedProjectId.value) {
    query.project_id = String(selectedProjectId.value)
  }
  if (selectedModuleId.value) {
    query.module_id = String(selectedModuleId.value)
  }

  const currentProjectId = parsePositiveInt(route.query.project_id) ?? parsePositiveInt(route.params.projectId)
  const currentModuleId = parsePositiveInt(route.query.module_id)
  if (currentProjectId === selectedProjectId.value && currentModuleId === selectedModuleId.value) {
    return
  }

  void router.replace({ name: 'cases', query })
}

async function applyRouteSelection(useDefaultProject = false) {
  const routeProjectId = parsePositiveInt(route.query.project_id) ?? parsePositiveInt(route.params.projectId)
  const routeModuleId = parsePositiveInt(route.query.module_id)
  const fallbackProjectId = useDefaultProject ? (projects.value[0]?.id ?? null) : selectedProjectId.value
  const nextProjectId = routeProjectId ?? fallbackProjectId
  const projectChanged = nextProjectId !== selectedProjectId.value

  selectedProjectId.value = nextProjectId

  if (projectChanged) {
    selectedModuleId.value = null
    await loadModules()
  }

  if (!selectedProjectId.value) {
    cases.value = []
    return
  }

  if (!projectChanged && Object.keys(moduleNameMap.value).length === 0) {
    await loadModules()
  }

  selectedModuleId.value = routeModuleId && moduleNameMap.value[routeModuleId] ? routeModuleId : null
  await loadCases()

  if (!routeProjectId && selectedProjectId.value) {
    syncRoute()
  }
}

function handleProjectChange(projectId: number | null) {
  selectedProjectId.value = projectId
  selectedModuleId.value = null
  syncRoute()
}

function onModuleSelect(moduleId: number | null) {
  selectedModuleId.value = moduleId
  syncRoute()
}

function clearModuleFilter() {
  selectedModuleId.value = null
  syncRoute()
}

async function refreshCurrentProject() {
  await loadProjects()
  await loadModules()
  await loadCases()
}

function handleSearch() {
  void loadCases()
}

function handleResetFilters() {
  keyword.value = ''
  filterType.value = undefined
  filterPriority.value = undefined
  filterLevel.value = undefined
  filterStatus.value = undefined
  filterReviewStatus.value = undefined
  filterAutomationStatus.value = undefined
  void loadCases()
}

function openCreate(type: CaseType) {
  if (!selectedModuleId.value) {
    message.warning('Select a module before creating a case')
    return
  }

  if (type === 'web') {
    webEditingCase.value = null
    webDrawerOpen.value = true
  } else if (type === 'android') {
    androidEditingCase.value = null
    androidDrawerOpen.value = true
  } else {
    editingCase.value = null
    createCaseType.value = type
    drawerOpen.value = true
  }
}

function openEdit(testCase: CaseSummaryItem) {
  if (testCase.case_type === 'web') {
    webEditingCase.value = testCase
    webDrawerOpen.value = true
  } else if (testCase.case_type === 'android') {
    androidEditingCase.value = testCase
    androidDrawerOpen.value = true
  } else {
    editingCase.value = testCase
    drawerOpen.value = true
  }
}

function openDetail(caseId: number) {
  const query: Record<string, string> = {}
  if (selectedProjectId.value) {
    query.project_id = String(selectedProjectId.value)
  }
  if (selectedModuleId.value) {
    query.module_id = String(selectedModuleId.value)
  }
  void router.push({ name: 'case-detail', params: { caseId: String(caseId) }, query })
}

function onSaved() {
  void loadCases()
}

async function handleRun(testCase: CaseSummaryItem) {
  if (!selectedProjectId.value) {
    return
  }

  pendingRunCase.value = testCase
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const environments = await environmentApi.list(selectedProjectId.value)
    runEnvOptions.value = environments.map((item: any) => ({ label: item.name, value: item.id }))
  } catch {
    runEnvOptions.value = []
    message.warning('Failed to load environments, run will continue without one')
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  const testCase = pendingRunCase.value
  if (!testCase) {
    return
  }

  runConfirming.value = true
  runningId.value = testCase.id
  try {
    const payload: { env_id?: number } = {}
    if (runEnvId.value) {
      payload.env_id = runEnvId.value
    }
    const run = await caseApi.run(testCase.id, payload) as any
    runModalOpen.value = false
    message.success('Run started, opening the report')
    void router.push(`/runs/${run.id}`)
  } catch (error: any) {
    message.error(error ?? 'Failed to start run')
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function handleCopy(caseId: number) {
  try {
    const copied = await caseApi.copy(caseId)
    message.success(`Copied case ${copied.case_code}`)
    await loadCases()
    openDetail(copied.id)
  } catch (error: any) {
    message.error(error ?? 'Failed to copy case')
  }
}

async function handleWorkflow(testCase: CaseSummaryItem, action: WorkflowAction) {
  try {
    switch (action) {
      case 'submitReview':
        await caseApi.submitReview(testCase.id)
        message.success('Review submitted')
        break
      case 'approve':
        await caseApi.approve(testCase.id)
        message.success('Case approved')
        break
      case 'reject':
        await caseApi.reject(testCase.id)
        message.success('Case rejected')
        break
      case 'deprecate':
        await caseApi.deprecate(testCase.id)
        message.success('Case deprecated')
        break
      case 'reactivate':
        await caseApi.reactivate(testCase.id)
        message.success('Case reactivated')
        break
    }
    await loadCases()
  } catch (error: any) {
    message.error(error ?? 'Workflow action failed')
  }
}

function confirmDelete(testCase: CaseSummaryItem) {
  Modal.confirm({
    title: `Delete case "${testCase.name}"?`,
    content: 'This action cannot be undone.',
    okText: 'Delete',
    cancelText: 'Cancel',
    okType: 'danger',
    async onOk() {
      await caseApi.delete(testCase.id)
      message.success('Case deleted')
      await loadCases()
    },
  })
}

function openHistory(caseId: number) {
  historyCaseId.value = caseId
  historyOpen.value = true
}

function handleHistoryRolled() {
  void loadCases()
}

watch(
  () => [route.params.projectId, route.query.project_id, route.query.module_id].join('|'),
  () => {
    void applyRouteSelection(false)
  },
)

onMounted(async () => {
  await loadProjects()
  await applyRouteSelection(true)
})
</script>

<style scoped>
.case-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-header h2 {
  margin: 0;
}

.page-header p {
  margin: 6px 0 0;
  color: #666;
}

.summary-row :deep(.ant-statistic-content) {
  font-size: 24px;
}

.workspace {
  display: flex;
  gap: 16px;
  min-height: 560px;
}

.side-panel {
  width: 260px;
  flex-shrink: 0;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  padding: 16px;
  overflow-y: auto;
  background: #fff;
}

.side-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-weight: 600;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-card :deep(.ant-card-body) {
  padding: 14px 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.case-link {
  padding-inline: 0;
  font-weight: 600;
}

.case-summary {
  color: #666;
  font-size: 12px;
}

.case-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.run-tip {
  margin-bottom: 12px;
  color: #666;
}

@media (max-width: 960px) {
  .page-header,
  .workspace,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .side-panel {
    width: 100%;
  }
}
</style>
