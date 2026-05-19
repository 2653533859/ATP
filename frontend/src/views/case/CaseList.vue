<template>
  <div class="case-page">
    <div class="page-header">
      <div>
        <h2>用例管理</h2>
        <p>按项目与模块统一管理标准化用例，并在同一页面完成评审与执行。</p>
      </div>
      <a-space wrap>
        <a-select
          v-model:value="selectedProjectId"
          placeholder="请选择项目"
          style="width: 240px"
          :options="projectOptions"
          allow-clear
          @change="handleProjectChange"
        />
        <a-button @click="router.push({ name: 'projects' })">项目管理</a-button>
        <a-button :disabled="!selectedProjectId" @click="refreshCurrentProject">刷新</a-button>
      </a-space>
    </div>

    <template v-if="selectedProjectId">
      <a-row :gutter="[16, 16]" class="summary-row">
        <a-col :xs="24" :sm="8">
          <a-card>
            <a-statistic title="项目" :value="currentProjectName" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8">
          <a-card>
            <a-statistic title="模块数" :value="moduleCount" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8">
          <a-card>
            <a-statistic title="可见用例数" :value="filteredCases.length" />
          </a-card>
        </a-col>
      </a-row>

      <div class="workspace">
        <div class="side-panel">
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            show-reset
            :reset-disabled="!selectedModuleId"
            @select="onModuleSelect"
            @reset="clearModuleFilter"
          />
        </div>

        <div class="main-panel">
          <a-card class="toolbar-card" :bordered="false">
            <div class="toolbar">
              <div class="toolbar-main">
                <a-space wrap>
                <a-input-search
                  v-model:value="keyword"
                  placeholder="搜索名称、编码或摘要"
                  style="width: 260px"
                  allow-clear
                  @search="handleSearch"
                />
                <a-select
                  v-model:value="filterType"
                  placeholder="类型"
                  allow-clear
                  style="width: 130px"
                  :options="caseTypeOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterPriority"
                  placeholder="优先级"
                  allow-clear
                  style="width: 120px"
                  :options="priorityOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterLevel"
                  placeholder="等级"
                  allow-clear
                  style="width: 140px"
                >
                  <a-select-option value="smoke">冒烟</a-select-option>
                  <a-select-option value="core">核心</a-select-option>
                  <a-select-option value="regression">回归</a-select-option>
                  <a-select-option value="extended">扩展</a-select-option>
                </a-select>
                <a-select
                  v-model:value="filterStatus"
                  placeholder="状态"
                  allow-clear
                  style="width: 120px"
                  :options="statusOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterReviewStatus"
                  placeholder="评审状态"
                  allow-clear
                  style="width: 140px"
                  :options="reviewStatusOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterAutomationStatus"
                  placeholder="自动化状态"
                  allow-clear
                  style="width: 140px"
                  :options="automationStatusOptions"
                  @change="loadCases"
                />
                <a-button @click="handleSearch">查询</a-button>
                <a-button @click="handleResetFilters">重置</a-button>
              </a-space>
              </div>

              <div class="toolbar-actions">
                <a-space wrap>
                <a-tag color="blue">
                  {{ selectedModuleId ? `当前模块：${activeModuleName}` : '当前模块：全部' }}
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
                    <PlusOutlined /> 新建用例 <DownOutlined />
                  </a-button>
                </a-dropdown>
                <a-button :disabled="!selectedModuleId" @click="aiDrawerOpen = true">
                  <ThunderboltOutlined /> AI 生成
                </a-button>
              </a-space>
              </div>
            </div>
          </a-card>

          <a-card class="table-card" :bordered="false">
            <BatchOperationBar :selected-count="selectedRowKeys.length" @cancel="selectedRowKeys = []">
              <a-button size="small" @click="handleBatchExport">导出 CSV</a-button>
              <a-button size="small" @click="handleBatchExportZip">导出 ZIP</a-button>
              <a-button size="small" @click="openBatchMove" :disabled="!selectedModuleId">
                批量移动
              </a-button>
              <a-popconfirm
                :title="`确认删除选中的 ${selectedRowKeys.length} 个用例？`"
                ok-text="删除"
                cancel-text="取消"
                @confirm="handleBatchDelete"
              >
                <a-button size="small" danger>批量删除</a-button>
              </a-popconfirm>
            </BatchOperationBar>
            <div class="batch-bar" style="margin-bottom: 12px">
              <span style="color: #888">导入用例 ZIP（目标模块：{{ activeModuleName }}）：</span>
              <a-upload
                :show-upload-list="false"
                :before-upload="handleBatchImportBeforeUpload"
                accept=".zip"
                :disabled="!selectedModuleId"
              >
                <a-button size="small" :disabled="!selectedModuleId">导入 ZIP</a-button>
              </a-upload>
            </div>
            <a-table
              :columns="columns"
              :data-source="filteredCases"
              :loading="loading"
              row-key="id"
              size="middle"
              :pagination="{ pageSize: 20, showSizeChanger: true }"
              :scroll="{ x: 1500 }"
              :row-selection="{ selectedRowKeys, onChange: (keys: (string | number)[]) => (selectedRowKeys = keys as number[]) }"
            >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <div class="case-name-cell">
                  <a-button type="link" class="case-link" @click="openDetail(record.id)">
                    {{ record.name }}
                  </a-button>
                  <div class="case-summary">
                    {{ record.case_code }} ｜ {{ record.summary || '暂无摘要' }}
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
                <span>{{ moduleNameMap[record.module_id] ?? `模块 #${record.module_id}` }}</span>
              </template>

              <template v-else-if="column.key === 'case_type'">
                <a-tag :color="caseTypeColor(record.case_type)">{{ caseTypeLabel(record.case_type) }}</a-tag>
              </template>

              <template v-else-if="column.key === 'priority'">
                <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
              </template>

              <template v-else-if="column.key === 'case_level'">
                <a-tag>{{ caseLevelLabel(record.case_level) }}</a-tag>
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
                  {{ automationStatusLabel(record.automation_status) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'updated_at'">
                {{ formatDateTime(record.updated_at) }}
              </template>

              <template v-else-if="column.key === 'action'">
                <a-space wrap size="small">
                  <a-button type="link" size="small" @click="openDetail(record.id)">详情</a-button>
                  <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
                  <a-tooltip :title="record.is_ready_for_execution ? '执行该用例' : '仅已评审通过的自动化或半自动化用例可执行'">
                    <a-button
                      type="link"
                      size="small"
                      :loading="runningId === record.id"
                      :disabled="!record.is_ready_for_execution"
                      @click="handleRun(record)"
                    >
                      执行
                    </a-button>
                  </a-tooltip>
                  <a-dropdown>
                    <a-button type="link" size="small">
                      更多 <DownOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item key="copy" @click="handleCopy(record.id)">复制</a-menu-item>
                        <a-menu-item key="history" @click="openHistory(record.id)">
                          <HistoryOutlined /> 历史
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item
                          v-if="canSubmitReview(record)"
                          key="submit-review"
                          @click="handleWorkflow(record, 'submitReview')"
                        >
                          提交评审
                        </a-menu-item>
                        <a-menu-item
                          v-if="canApprove(record)"
                          key="approve"
                          @click="handleWorkflow(record, 'approve')"
                        >
                          审核通过
                        </a-menu-item>
                        <a-menu-item
                          v-if="canReject(record)"
                          key="reject"
                          @click="handleWorkflow(record, 'reject')"
                        >
                          审核驳回
                        </a-menu-item>
                        <a-menu-item
                          v-if="canDeprecate(record)"
                          key="deprecate"
                          @click="handleWorkflow(record, 'deprecate')"
                        >
                          废弃
                        </a-menu-item>
                        <a-menu-item
                          v-if="canReactivate(record)"
                          key="reactivate"
                          @click="handleWorkflow(record, 'reactivate')"
                        >
                          重新激活
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item key="delete" @click="confirmDelete(record)">删除</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-space>
              </template>
            </template>
          </a-table>
          </a-card>
        </div>
      </div>
    </template>

    <a-result
      v-else
      status="info"
      title="请选择项目"
      sub-title="请选择一个项目后再管理其模块和标准化用例。"
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
      title="选择执行环境"
      ok-text="执行"
      cancel-text="取消"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">请选择本次执行使用的环境，不选择则按无环境方式执行。</p>
      <a-select
        v-model:value="runEnvId"
        placeholder="不选择环境"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <a-modal
      v-model:open="batchMoveOpen"
      title="批量移动用例"
      ok-text="确认移动"
      cancel-text="取消"
      :confirm-loading="batchMoveLoading"
      @ok="submitBatchMove"
    >
      <p class="run-tip">选择目标模块，将把已选 {{ selectedRowKeys.length }} 个用例移动到该模块。</p>
      <a-select
        v-model:value="batchMoveTargetId"
        placeholder="选择目标模块"
        style="width: 100%"
        :options="moduleSelectOptions"
        show-search
        :filter-option="(input: string, option: any) => option.label?.toLowerCase().includes(input.toLowerCase())"
      />
    </a-modal>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="historyCaseId"
      @close="historyOpen = false"
      @rolled="handleHistoryRolled"
    />

    <AIGenerateDrawer
      :open="aiDrawerOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      @close="aiDrawerOpen = false"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { DownOutlined, HistoryOutlined, PlusOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
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
import AIGenerateDrawer from '@/views/case/AIGenerateDrawer.vue'
import BatchOperationBar from '@/components/common/BatchOperationBar.vue'

type WorkflowAction = 'submitReview' | 'approve' | 'reject' | 'deprecate' | 'reactivate'

const route = useRoute()
const router = useRouter()

const caseTypeOptions: Array<{ label: string; value: CaseType }> = [
  { label: 'API', value: 'api' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
  { label: 'gRPC', value: 'grpc' },
  { label: 'Web 用例', value: 'web' },
  { label: 'Android 用例', value: 'android' },
]

const priorityOptions: Array<{ label: string; value: CasePriority }> = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

const statusOptions: Array<{ label: string; value: CaseStatus }> = [
  { label: '草稿', value: 'draft' },
  { label: '启用', value: 'active' },
  { label: '已废弃', value: 'deprecated' },
]

const reviewStatusOptions: Array<{ label: string; value: ReviewStatus }> = [
  { label: '待评审', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
]

const automationStatusOptions: Array<{ label: string; value: AutomationStatus }> = [
  { label: '手工', value: 'manual' },
  { label: '半自动', value: 'semi_auto' },
  { label: '自动', value: 'auto' },
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
const selectedRowKeys = ref<number[]>([])
const batchMoveOpen = ref(false)
const batchMoveTargetId = ref<number | null>(null)
const batchMoveLoading = ref(false)
const historyOpen = ref(false)
const historyCaseId = ref<number | null>(null)
const aiDrawerOpen = ref(false)

const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const pendingRunCase = ref<CaseSummaryItem | null>(null)

const columns = [
  { title: '用例', key: 'name', width: 320 },
  { title: '模块', key: 'module', width: 160 },
  { title: '类型', key: 'case_type', width: 110 },
  { title: '优先级', key: 'priority', width: 100 },
  { title: '等级', key: 'case_level', width: 120 },
  { title: '评审状态', key: 'review_status', width: 120 },
  { title: '生命周期', key: 'status', width: 120 },
  { title: '自动化', key: 'automation_status', width: 130 },
  { title: '更新时间', key: 'updated_at', width: 180 },
  { title: '操作', key: 'action', width: 280, fixed: 'right' },
]

const projectOptions = computed(() =>
  projects.value.map((project) => ({ label: project.name, value: project.id })),
)

const currentProjectName = computed(() =>
  projects.value.find((project) => project.id === selectedProjectId.value)?.name ?? '-',
)

const moduleCount = computed(() => Object.keys(moduleNameMap.value).length)

const activeModuleName = computed(() =>
  selectedModuleId.value ? (moduleNameMap.value[selectedModuleId.value] ?? `模块 #${selectedModuleId.value}`) : '全部',
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

const moduleSelectOptions = computed(() =>
  Object.entries(moduleNameMap.value).map(([id, name]) => ({
    value: Number(id),
    label: name,
  })),
)

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

function caseLevelLabel(level: CaseLevel) {
  return {
    smoke: '冒烟',
    core: '核心',
    regression: '回归',
    extended: '扩展',
  }[level]
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
    pending: '待评审',
    approved: '已通过',
    rejected: '已驳回',
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
    draft: '草稿',
    active: '启用',
    deprecated: '已废弃',
  }[status]
}

function statusColor(status: CaseStatus) {
  return {
    draft: 'default',
    active: 'success',
    deprecated: 'warning',
  }[status]
}

function automationStatusLabel(status: AutomationStatus) {
  return {
    manual: '手工',
    semi_auto: '半自动',
    auto: '自动',
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
    message.error(error ?? '????????')
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
    message.error(error ?? '??????')
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
    message.error(error ?? '????????')
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
    message.warning('加载环境失败，将按无环境方式继续执行')
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
    message.success('已开始执行，正在打开报告')
    void router.push(`/runs/${run.id}`)
  } catch (error: any) {
    message.error(error ?? '启动执行失败')
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function handleCopy(caseId: number) {
  try {
    const copied = await caseApi.copy(caseId)
    message.success(`已复制用例 ${copied.case_code}`)
    await loadCases()
    openDetail(copied.id)
  } catch (error: any) {
    message.error(error ?? '复制用例失败')
  }
}

async function handleWorkflow(testCase: CaseSummaryItem, action: WorkflowAction) {
  try {
    switch (action) {
      case 'submitReview':
        await caseApi.submitReview(testCase.id)
        message.success('已提交评审')
        break
      case 'approve':
        await caseApi.approve(testCase.id)
        message.success('用例已审核通过')
        break
      case 'reject':
        await caseApi.reject(testCase.id)
        message.success('用例已审核驳回')
        break
      case 'deprecate':
        await caseApi.deprecate(testCase.id)
        message.success('用例已废弃')
        break
      case 'reactivate':
        await caseApi.reactivate(testCase.id)
        message.success('用例已重新激活')
        break
    }
    await loadCases()
  } catch (error: any) {
    message.error(error ?? '流程操作失败')
  }
}

function confirmDelete(testCase: CaseSummaryItem) {
  Modal.confirm({
    title: `确认删除用例“${testCase.name}”吗？`,
    content: '删除后不可恢复，请谨慎操作。',
    okText: '删除',
    cancelText: '取消',
    okType: 'danger',
    async onOk() {
      await caseApi.delete(testCase.id)
      message.success('用例已删除')
      await loadCases()
    },
  })
}

async function handleBatchDelete() {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await caseApi.batchDelete(selectedRowKeys.value)
    message.success(`已删除 ${result.processed} / ${result.requested} 个用例`)
    selectedRowKeys.value = []
    await loadCases()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '批量删除失败')
  }
}

async function handleBatchExport() {
  if (!selectedRowKeys.value.length) return
  try {
    const blob = await caseApi.batchExportCsv(selectedRowKeys.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cases-export-${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(`已导出 ${selectedRowKeys.value.length} 个用例`)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '导出失败')
  }
}

async function handleBatchExportZip() {
  if (!selectedRowKeys.value.length) return
  try {
    const blob = await caseApi.batchExportZip(selectedRowKeys.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cases-export-${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(`已导出 ${selectedRowKeys.value.length} 个用例 (ZIP)`)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '导出失败')
  }
}

function handleBatchImportBeforeUpload(file: File) {
  if (!selectedModuleId.value) {
    message.warning('请先选择目标模块')
    return false
  }
  ;(async () => {
    try {
      const result = await caseApi.batchImportZip(file, selectedModuleId.value as number)
      if (result.errors.length) {
        message.warning(`导入完成：成功 ${result.imported} 个，跳过 ${result.skipped_count} 个`)
      } else {
        message.success(`已导入 ${result.imported} 个用例`)
      }
      await loadCases()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败')
    }
  })()
  return false
}

function openBatchMove() {
  if (!selectedRowKeys.value.length) return
  batchMoveTargetId.value = null
  batchMoveOpen.value = true
}

async function submitBatchMove() {
  if (!batchMoveTargetId.value) {
    message.warning('请选择目标模块')
    return
  }
  batchMoveLoading.value = true
  try {
    const result = await caseApi.batchMove(selectedRowKeys.value, batchMoveTargetId.value)
    message.success(`已移动 ${result.processed} / ${result.requested} 个用例`)
    batchMoveOpen.value = false
    selectedRowKeys.value = []
    await loadCases()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '批量移动失败')
  } finally {
    batchMoveLoading.value = false
  }
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
  display: grid;
  grid-template-columns: minmax(280px, 300px) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
  min-height: 560px;
}

.side-panel {
  min-width: 0;
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  padding: 14px;
  overflow-y: auto;
  background: linear-gradient(180deg, #fafcff 0%, #ffffff 100%);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.side-panel :deep(.tree-header) {
  margin-bottom: 12px;
  padding: 2px 2px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.side-panel :deep(.ant-tree) {
  background: transparent;
}

.main-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-card,
.table-card {
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.toolbar-card :deep(.ant-card-body) {
  padding: 14px 16px;
}

.table-card :deep(.ant-card-body) {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-main {
  flex: 1 1 960px;
  min-width: 0;
}

.toolbar-actions {
  flex: 0 0 auto;
  margin-left: auto;
}

.toolbar-actions :deep(.ant-space) {
  justify-content: flex-end;
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
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .toolbar-main,
  .toolbar-actions {
    flex: 1 1 auto;
    margin-left: 0;
  }
}
</style>


