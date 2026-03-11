<template>
  <div class="suite-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectFilter"
          placeholder="选择项目"
          allow-clear
          style="width: 200px"
          @change="loadSuites"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" @click="openCreate" :disabled="!projectFilter">
        <PlusOutlined /> 新建套件
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="suites"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'case_count'">
          <a-tag color="blue">{{ (record.case_ids || []).length }} 个用例</a-tag>
        </template>

        <template v-if="column.key === 'project'">
          {{ getProjectName(record.project_id) }}
        </template>

        <template v-if="column.key === 'created'">
          {{ formatTime(record.created_at) }}
        </template>

        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-button
              type="link"
              size="small"
              :loading="runningId === record.id"
              @click="handleRun(record)"
            >
              执行
            </a-button>
            <a-button type="link" size="small" @click="viewRuns(record)">记录</a-button>
            <a-popconfirm title="确认删除该套件？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 创建/编辑 Modal -->
    <a-modal
      v-model:open="formOpen"
      :title="editingId ? '编辑套件' : '新建套件'"
      width="1080"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item label="套件名称" required>
          <a-input v-model:value="form.name" placeholder="输入套件名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
        </a-form-item>
        <a-form-item label="所属项目">
          <a-input :value="formProjectName" disabled />
        </a-form-item>
        <a-form-item label="用例列表">
          <a-row :gutter="16">
            <a-col :span="16">
              <a-space direction="vertical" style="width: 100%" :size="12">
                <a-space wrap style="width: 100%">
                  <a-input-search
                    v-model:value="caseKeyword"
                    placeholder="搜索编号、名称、摘要或标签"
                    allow-clear
                    style="width: 280px"
                  />
                  <a-tree-select
                    v-model:value="caseModuleFilter"
                    placeholder="按模块筛选"
                    allow-clear
                    show-search
                    tree-default-expand-all
                    tree-node-filter-prop="title"
                    style="width: 220px"
                    :tree-data="caseModuleTreeData"
                  />
                  <a-select
                    v-model:value="caseTypeFilter"
                    placeholder="按类型筛选"
                    allow-clear
                    style="width: 150px"
                    :options="caseTypeOptions"
                  />
                  <a-select
                    v-model:value="caseSelectionScope"
                    style="width: 140px"
                    :options="caseSelectionScopeOptions"
                  />
                  <a-select
                    v-model:value="caseReadyFilter"
                    style="width: 150px"
                    :options="caseReadyFilterOptions"
                  />
                </a-space>
                <div class="case-filter-tip">
                  默认仅展示可执行用例；切换到“全部用例”或“仅看未就绪”可查看禁选原因。
                </div>
                <a-table
                  row-key="id"
                  size="small"
                  :columns="caseSelectColumns"
                  :data-source="filteredAvailableCases"
                  :loading="casesLoading"
                  :pagination="{ pageSize: 6, size: 'small' }"
                  :row-selection="caseRowSelection"
                  :scroll="{ x: 960 }"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'name'">
                      <div class="case-name-cell">
                        <div class="case-name-title">{{ record.name }}</div>
                        <div class="case-name-meta">{{ record.summary || record.description || '-' }}</div>
                      </div>
                    </template>
                    <template v-else-if="column.key === 'module'">
                      {{ getModuleName(record.module_id) }}
                    </template>
                    <template v-else-if="column.key === 'case_type'">
                      <a-tag :color="typeColor(record.case_type)">{{ typeLabel(record.case_type) }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'priority'">
                      <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'status'">
                      <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'ready'">
                      <a-tooltip :title="getExecutionHint(record)">
                        <a-tag :color="readyColor(record.is_ready_for_execution)">
                          {{ readyLabel(record.is_ready_for_execution) }}
                        </a-tag>
                      </a-tooltip>
                    </template>
                    <template v-else-if="column.key === 'ready_reason'">
                      <span
                        v-if="!record.is_ready_for_execution"
                        class="case-ready-reason"
                      >
                        {{ getExecutionReason(record) }}
                      </span>
                      <span v-else style="color: #bfbfbf">-</span>
                    </template>
                    <template v-else-if="column.key === 'tags'">
                      <a-space wrap :size="[4, 4]">
                        <a-tag v-for="tag in record.tags" :key="tag" color="blue">{{ tag }}</a-tag>
                        <span v-if="!record.tags?.length" style="color: #999">-</span>
                      </a-space>
                    </template>
                  </template>
                </a-table>
              </a-space>
            </a-col>
            <a-col :span="8">
              <div class="selected-case-panel">
                <div class="selected-case-title">
                  <span>
                    已选用例
                    <span class="selected-case-count">{{ selectedCaseItems.length }}</span>
                  </span>
                  <span class="selected-case-tip">拖拽左侧图标排序</span>
                </div>
                <div v-if="selectedUnreadyCaseItems.length" class="selected-case-warning">
                  当前包含 {{ selectedUnreadyCaseItems.length }} 个未就绪用例，保存时会二次确认。
                </div>
                <a-empty
                  v-if="selectedCaseItems.length === 0"
                  description="请在左侧选择用例"
                  :image="false"
                />
                <draggable
                  v-else
                  v-model="selectedCaseListModel"
                  item-key="id"
                  handle=".selected-case-drag-handle"
                  class="selected-case-list"
                  ghost-class="selected-case-ghost"
                  :animation="180"
                >
                  <template #item="{ element: c, index }">
                    <div class="selected-case-item">
                      <div class="selected-case-order-group">
                        <HolderOutlined class="selected-case-drag-handle" />
                        <div class="selected-case-order">#{{ index + 1 }}</div>
                      </div>
                      <div class="selected-case-body">
                        <div class="selected-case-name">{{ c.case_code }} · {{ c.name }}</div>
                        <div class="selected-case-meta">
                          <a-tag :color="typeColor(c.case_type)">{{ typeLabel(c.case_type) }}</a-tag>
                          <a-tag :color="priorityColor(c.priority)">{{ c.priority }}</a-tag>
                          <a-tooltip :title="getExecutionHint(c)">
                            <a-tag :color="readyColor(c.is_ready_for_execution)">
                              {{ readyLabel(c.is_ready_for_execution) }}
                            </a-tag>
                          </a-tooltip>
                          <span>{{ getModuleName(c.module_id) }}</span>
                        </div>
                      </div>
                      <div class="selected-case-actions">
                        <a-button type="text" size="small" :disabled="index === 0" @click="moveSelectedCase(index, -1)">上移</a-button>
                        <a-button type="text" size="small" :disabled="index === selectedCaseListModel.length - 1" @click="moveSelectedCase(index, 1)">下移</a-button>
                        <a-button type="text" size="small" danger @click="removeSelectedCase(c.id)">移除</a-button>
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
              <div class="case-select-tip">
                套件会按右侧顺序执行。支持拖拽、上移、下移三种调整方式。
              </div>
            </a-col>
          </a-row>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 执行环境选择 -->
    <a-modal
      v-model:open="runModalOpen"
      title="选择执行环境"
      ok-text="执行"
      cancel-text="取消"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p style="margin-bottom: 12px; color: #666">可选择一个环境，变量将注入到套件内所有用例。</p>
      <a-select
        v-model:value="runEnvId"
        placeholder="不使用环境"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <!-- 执行记录 Drawer -->
    <a-drawer
      :open="runsDrawerOpen"
      :title="`执行记录 - ${runsDrawerTitle}`"
      width="700"
      @close="runsDrawerOpen = false"
    >
      <a-table
        :columns="runColumns"
        :data-source="suiteRuns"
        :loading="runsLoading"
        row-key="id"
        size="small"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-badge :status="runStatusBadge(record.status)" :text="record.status" />
          </template>
          <template v-if="column.key === 'summary'">
            <span v-if="record.result_summary">
              <a-tag color="green">{{ record.result_summary.passed ?? 0 }} 通过</a-tag>
              <a-tag v-if="record.result_summary.failed" color="red">{{ record.result_summary.failed }} 失败</a-tag>
              <a-tag v-if="record.result_summary.error" color="orange">{{ record.result_summary.error }} 错误</a-tag>
            </span>
          </template>
          <template v-if="column.key === 'duration'">
            {{ record.duration_ms ? (record.duration_ms / 1000).toFixed(1) + 's' : '-' }}
          </template>
          <template v-if="column.key === 'created'">
            {{ formatTime(record.created_at) }}
          </template>
        </template>
      </a-table>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { HolderOutlined, PlusOutlined } from '@ant-design/icons-vue'
import draggable from 'vuedraggable'
import type { CasePriority, CaseStatus, CaseSummaryItem, CaseType, ModuleTreeItem } from '@/api'
import { suiteApi, projectApi, caseApi, environmentApi } from '@/api'

type CaseSelectionScope = 'all' | 'selected' | 'unselected'
type CaseReadyFilter = 'all' | 'ready' | 'not_ready'

interface ModuleTreeOption {
  title: string
  value: number
  key: number
  children?: ModuleTreeOption[]
}

const suites = ref<any[]>([])
const projects = ref<any[]>([])
const loading = ref(false)
const projectFilter = ref<number | undefined>(undefined)

// Form
const formOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', description: '' })
const selectedCaseIds = ref<number[]>([])
const availableCases = ref<CaseSummaryItem[]>([])
const casesLoading = ref(false)
const formProjectId = ref<number | null>(null)
const caseKeyword = ref('')
const caseModuleFilter = ref<number | undefined>(undefined)
const caseTypeFilter = ref<CaseType | undefined>(undefined)
const caseSelectionScope = ref<CaseSelectionScope>('all')
const caseReadyFilter = ref<CaseReadyFilter>('ready')
const moduleTree = ref<ModuleTreeItem[]>([])
const moduleNameMap = ref<Record<number, string>>({})

// Run
const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const runningId = ref<number | null>(null)
const pendingRunSuite = ref<any>(null)

// Run records
const runsDrawerOpen = ref(false)
const runsDrawerTitle = ref('')
const suiteRuns = ref<any[]>([])
const runsLoading = ref(false)

const columns = [
  { title: '套件名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '项目', key: 'project', width: 150 },
  { title: '用例数', key: 'case_count', width: 100 },
  { title: '创建时间', key: 'created', width: 170 },
  { title: '操作', key: 'action', width: 220, fixed: 'right' as const },
]

const runColumns = [
  { title: '状态', key: 'status', width: 100 },
  { title: '结果', key: 'summary', width: 240 },
  { title: '耗时', key: 'duration', width: 80 },
  { title: '执行时间', key: 'created', width: 170 },
]

const caseSelectColumns = [
  { title: '编号', dataIndex: 'case_code', key: 'case_code', width: 150 },
  { title: '名称 / 摘要', key: 'name', width: 260 },
  { title: '模块', key: 'module', width: 140 },
  { title: '类型', key: 'case_type', width: 90 },
  { title: '优先级', key: 'priority', width: 90 },
  { title: '状态', key: 'status', width: 90 },
  { title: '执行', key: 'ready', width: 100 },
  { title: '未就绪原因', key: 'ready_reason', width: 220 },
  { title: '标签', key: 'tags', width: 180 },
]

const caseTypeOptions = [
  { label: '接口', value: 'api' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
  { label: 'gRPC', value: 'grpc' },
  { label: 'Web', value: 'web' },
  { label: 'Android', value: 'android' },
] satisfies Array<{ label: string; value: CaseType }>

const caseSelectionScopeOptions = [
  { label: '全部', value: 'all' },
  { label: '仅看已选', value: 'selected' },
  { label: '仅看未选', value: 'unselected' },
] satisfies Array<{ label: string; value: CaseSelectionScope }>

const caseReadyFilterOptions = [
  { label: '全部用例', value: 'all' },
  { label: '仅看可执行', value: 'ready' },
  { label: '仅看未就绪', value: 'not_ready' },
] satisfies Array<{ label: string; value: CaseReadyFilter }>

const moduleDescendantMap = computed(() => buildModuleDescendantMap(moduleTree.value))

const caseModuleTreeData = computed(() =>
  buildModuleTreeOptions(
    moduleTree.value,
    new Set(availableCases.value.map((item) => item.module_id)),
  ),
)

const formProjectName = computed(() => {
  if (!formProjectId.value) return '-'
  return getProjectName(formProjectId.value)
})

const filteredAvailableCases = computed(() => {
  const keyword = caseKeyword.value.trim().toLowerCase()
  const selectedIds = new Set(selectedCaseIds.value)
  const allowedModuleIds =
    caseModuleFilter.value !== undefined
      ? moduleDescendantMap.value.get(caseModuleFilter.value) ?? new Set<number>()
      : null

  return availableCases.value.filter((item) => {
    if (allowedModuleIds && !allowedModuleIds.has(item.module_id)) {
      return false
    }
    if (caseTypeFilter.value !== undefined && item.case_type !== caseTypeFilter.value) {
      return false
    }
    if (caseReadyFilter.value === 'ready' && !item.is_ready_for_execution) {
      return false
    }
    if (caseReadyFilter.value === 'not_ready' && item.is_ready_for_execution) {
      return false
    }
    const isSelected = selectedIds.has(item.id)
    if (caseSelectionScope.value === 'selected' && !isSelected) {
      return false
    }
    if (caseSelectionScope.value === 'unselected' && isSelected) {
      return false
    }
    if (!keyword) {
      return true
    }

    const fields = [
      item.case_code,
      item.name,
      item.summary,
      item.description,
      ...(item.tags ?? []),
      getModuleName(item.module_id),
      typeLabel(item.case_type),
      item.priority,
      statusLabel(item.status),
      readyLabel(item.is_ready_for_execution),
      getExecutionReason(item),
    ]
    return fields.some((field) => String(field ?? '').toLowerCase().includes(keyword))
  })
})

const selectedCaseItems = computed(() => {
  const caseMap = new Map(availableCases.value.map((item) => [item.id, item]))
  return selectedCaseIds.value
    .map((id) => caseMap.get(id))
    .filter((item): item is CaseSummaryItem => Boolean(item))
})

const selectedCaseListModel = computed<CaseSummaryItem[]>({
  get: () => selectedCaseItems.value,
  set: (items) => {
    selectedCaseIds.value = items.map((item) => item.id)
  },
})

const selectedUnreadyCaseItems = computed(() =>
  selectedCaseItems.value.filter((item) => !item.is_ready_for_execution),
)

const caseRowSelection = computed(() => ({
  selectedRowKeys: selectedCaseIds.value,
  preserveSelectedRowKeys: true,
  getCheckboxProps: (record: CaseSummaryItem) => ({
    disabled: !record.is_ready_for_execution && !selectedCaseIds.value.includes(record.id),
  }),
  onSelect: (record: CaseSummaryItem, selected: boolean) => {
    if (selected) {
      if (!selectedCaseIds.value.includes(record.id)) {
        selectedCaseIds.value = [...selectedCaseIds.value, record.id]
      }
      return
    }
    selectedCaseIds.value = selectedCaseIds.value.filter((id) => id !== record.id)
  },
  onSelectAll: (selected: boolean, _rows: CaseSummaryItem[], changeRows: CaseSummaryItem[]) => {
    const changedIds = changeRows.map((item) => item.id)
    if (selected) {
      selectedCaseIds.value = [
        ...selectedCaseIds.value,
        ...changedIds.filter((id) => !selectedCaseIds.value.includes(id)),
      ]
      return
    }
    const removedIds = new Set(changedIds)
    selectedCaseIds.value = selectedCaseIds.value.filter((id) => !removedIds.has(id))
  },
}))

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ')
}

function getProjectName(id: number) {
  return projects.value.find(p => p.id === id)?.name ?? '-'
}

function typeLabel(t: CaseType | string) {
  return {
    api: '接口',
    graphql: 'GraphQL',
    websocket: 'WebSocket',
    grpc: 'gRPC',
    web: 'Web',
    android: 'Android',
  }[t] ?? t
}

function typeColor(t: CaseType | string) {
  return {
    api: 'geekblue',
    graphql: 'cyan',
    websocket: 'gold',
    grpc: 'volcano',
    web: 'purple',
    android: 'green',
  }[t] ?? 'default'
}

function priorityColor(priority: CasePriority | string) {
  return { P0: 'red', P1: 'volcano', P2: 'gold', P3: 'default' }[priority] ?? 'default'
}

function statusLabel(status: CaseStatus | string) {
  return { draft: '草稿', active: '生效', deprecated: '废弃' }[status] ?? status
}

function statusColor(status: CaseStatus | string) {
  return { draft: 'default', active: 'success', deprecated: 'error' }[status] ?? 'default'
}

function readyLabel(isReady: boolean) {
  return isReady ? '可执行' : '未就绪'
}

function readyColor(isReady: boolean) {
  return isReady ? 'success' : 'orange'
}

function getExecutionReason(item: Pick<CaseSummaryItem, 'status' | 'review_status' | 'automation_status'>) {
  if (item.status !== 'active') {
    return '状态不是 active'
  }
  if (item.review_status !== 'approved') {
    return '审核未通过'
  }
  if (!['auto', 'semi_auto'].includes(item.automation_status)) {
    return '不是自动化或半自动化'
  }
  return '-'
}

function getExecutionHint(item: Pick<CaseSummaryItem, 'is_ready_for_execution' | 'status' | 'review_status' | 'automation_status'>) {
  if (item.is_ready_for_execution) {
    return '满足执行前置校验，可直接加入套件执行。'
  }
  return `${getExecutionReason(item)}，不能加入执行。`
}

function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (node.children?.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function buildModuleDescendantMap(
  nodes: ModuleTreeItem[],
  acc: Map<number, Set<number>> = new Map(),
) {
  for (const node of nodes) {
    buildModuleDescendantMap(node.children ?? [], acc)
    const descendantIds = new Set<number>([node.id])
    for (const child of node.children ?? []) {
      const childIds = acc.get(child.id)
      if (!childIds) {
        continue
      }
      for (const childId of childIds) {
        descendantIds.add(childId)
      }
    }
    acc.set(node.id, descendantIds)
  }
  return acc
}

function buildModuleTreeOptions(
  nodes: ModuleTreeItem[],
  availableModuleIds: Set<number>,
): ModuleTreeOption[] {
  const options: ModuleTreeOption[] = []

  for (const node of nodes) {
    const children = buildModuleTreeOptions(node.children ?? [], availableModuleIds)
    if (!availableModuleIds.has(node.id) && children.length === 0) {
      continue
    }
    options.push({
      title: node.name,
      value: node.id,
      key: node.id,
      children: children.length ? children : undefined,
    })
  }

  return options
}

function getModuleName(moduleId: number) {
  return moduleNameMap.value[moduleId] ?? `模块 #${moduleId}`
}

function runStatusBadge(s: string) {
  return { pending: 'default', running: 'processing', passed: 'success', failed: 'error', error: 'warning' }[s] ?? 'default'
}

async function loadProjects() {
  try { projects.value = await projectApi.list() } catch { /* ignore */ }
}

async function loadSuites() {
  loading.value = true
  try {
    suites.value = await suiteApi.list(
      projectFilter.value ? { project_id: projectFilter.value } : undefined,
    )
  } catch (e: any) {
    message.error(e ?? '加载套件列表失败')
  } finally {
    loading.value = false
  }
}

async function loadCases(projectId = formProjectId.value) {
  if (!projectId) {
    availableCases.value = []
    moduleTree.value = []
    moduleNameMap.value = {}
    return
  }
  casesLoading.value = true
  try {
    const [cases, moduleTreeData] = await Promise.all([
      caseApi.list({ project_id: projectId }),
      projectApi.getModules(projectId),
    ])
    availableCases.value = cases
    moduleTree.value = moduleTreeData
    moduleNameMap.value = flattenModules(moduleTreeData)
  } catch {
    availableCases.value = []
    moduleTree.value = []
    moduleNameMap.value = {}
  } finally {
    casesLoading.value = false
  }
}

function openCreate() {
  formProjectId.value = projectFilter.value ?? null
  editingId.value = null
  form.value = { name: '', description: '' }
  selectedCaseIds.value = []
  caseKeyword.value = ''
  caseModuleFilter.value = undefined
  caseTypeFilter.value = undefined
  caseSelectionScope.value = 'all'
  caseReadyFilter.value = 'ready'
  loadCases(formProjectId.value)
  formOpen.value = true
}

async function openEdit(record: any) {
  formProjectId.value = record.project_id
  editingId.value = record.id
  form.value = { name: record.name, description: record.description ?? '' }
  selectedCaseIds.value = (record.case_ids || []).map((c: any) => c.case_id)
  caseKeyword.value = ''
  caseModuleFilter.value = undefined
  caseTypeFilter.value = undefined
  caseSelectionScope.value = 'all'
  caseReadyFilter.value = 'ready'
  await loadCases(formProjectId.value)
  formOpen.value = true
}

async function handleSave() {
  if (saving.value) {
    return
  }
  if (!form.value.name.trim()) {
    message.warning('请输入套件名称')
    return
  }
  if (!formProjectId.value) {
    message.warning('请先选择项目')
    return
  }
  if (selectedCaseIds.value.length === 0) {
    message.warning('请至少选择一个用例')
    return
  }
  if (selectedUnreadyCaseItems.value.length > 0) {
    const names = selectedUnreadyCaseItems.value
      .slice(0, 3)
      .map((item) => `${item.case_code}(${getExecutionReason(item)})`)
      .join('、')
    const restCount = selectedUnreadyCaseItems.value.length - 3

    Modal.confirm({
      title: `当前包含 ${selectedUnreadyCaseItems.value.length} 个未就绪用例，是否继续保存？`,
      content: restCount > 0 ? `${names} 等 ${restCount + 3} 个用例仍未就绪。` : `${names} 仍未就绪。`,
      okText: '继续保存',
      cancelText: '返回处理',
      async onOk() {
        await persistSuite()
      },
    })
    return
  }
  await persistSuite()
}

async function persistSuite() {
  saving.value = true
  try {
    const caseIds = selectedCaseIds.value.map((id, idx) => ({ case_id: id, sort: idx }))
    if (editingId.value) {
      await suiteApi.update(editingId.value, {
        name: form.value.name,
        description: form.value.description,
        case_ids: caseIds,
      })
      message.success('保存成功')
    } else {
      await suiteApi.create({
        name: form.value.name,
        description: form.value.description,
        project_id: formProjectId.value,
        case_ids: caseIds,
      })
      message.success('套件已创建')
    }
    formOpen.value = false
    loadSuites()
  } catch (e: any) {
    message.error(e ?? '保存失败')
  } finally {
    saving.value = false
  }
}

function moveSelectedCase(index: number, delta: -1 | 1) {
  const targetIndex = index + delta
  if (targetIndex < 0 || targetIndex >= selectedCaseIds.value.length) {
    return
  }

  const nextIds = [...selectedCaseIds.value]
  const [current] = nextIds.splice(index, 1)
  nextIds.splice(targetIndex, 0, current)
  selectedCaseIds.value = nextIds
}

function removeSelectedCase(caseId: number) {
  selectedCaseIds.value = selectedCaseIds.value.filter((id) => id !== caseId)
}

async function handleRun(record: any) {
  pendingRunSuite.value = record
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const envs = await environmentApi.list(record.project_id)
    runEnvOptions.value = envs.map((e: any) => ({ label: e.name, value: e.id }))
  } catch {
    runEnvOptions.value = []
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  const s = pendingRunSuite.value
  if (!s) return
  runConfirming.value = true
  runningId.value = s.id
  try {
    const payload: { env_id?: number } = {}
    if (runEnvId.value) payload.env_id = runEnvId.value
    await suiteApi.run(s.id, payload)
    runModalOpen.value = false
    message.success('套件执行已触发')
    // 打开执行记录
    viewRuns(s)
  } catch (e: any) {
    message.error(e ?? '执行触发失败')
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function viewRuns(record: any) {
  runsDrawerTitle.value = record.name
  runsDrawerOpen.value = true
  runsLoading.value = true
  try {
    suiteRuns.value = await suiteApi.listRuns({ suite_id: record.id })
  } catch {
    suiteRuns.value = []
  } finally {
    runsLoading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await suiteApi.delete(id)
    message.success('已删除')
    loadSuites()
  } catch (e: any) {
    message.error(e ?? '删除失败')
  }
}

onMounted(() => {
  loadProjects()
  loadSuites()
})
</script>

<style scoped>
.suite-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.case-name-title {
  font-weight: 500;
  color: #262626;
}
.case-name-meta {
  font-size: 12px;
  color: #8c8c8c;
}
.case-filter-tip {
  font-size: 12px;
  color: #8c8c8c;
}
.case-ready-reason {
  font-size: 12px;
  color: #d46b08;
}
.selected-case-panel {
  min-height: 330px;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}
.selected-case-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
}
.selected-case-tip {
  font-size: 12px;
  font-weight: 400;
  color: #8c8c8c;
}
.selected-case-count {
  color: #1677ff;
}
.selected-case-warning {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fff7e6;
  color: #ad6800;
  font-size: 12px;
}
.selected-case-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.selected-case-ghost {
  opacity: 0.6;
}
.selected-case-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fff;
}
.selected-case-order-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.selected-case-drag-handle {
  font-size: 16px;
  color: #8c8c8c;
  cursor: grab;
}
.selected-case-drag-handle:active {
  cursor: grabbing;
}
.selected-case-order {
  min-width: 28px;
  font-weight: 600;
  color: #1677ff;
}
.selected-case-body {
  flex: 1;
  min-width: 0;
}
.selected-case-name {
  margin-bottom: 6px;
  font-weight: 500;
  color: #262626;
  word-break: break-word;
}
.selected-case-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: #8c8c8c;
}
.selected-case-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
}
.case-select-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
