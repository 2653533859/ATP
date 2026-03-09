<template>
  <div class="case-page">
    <div class="page-header">
      <div>
        <h2>统一用例管理</h2>
        <p>在一个页面内切换项目、管理模块、维护用例并直接执行。</p>
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
        <a-button @click="refreshCurrentProject" :disabled="!selectedProjectId">刷新</a-button>
      </a-space>
    </div>

    <template v-if="selectedProjectId">
      <a-row :gutter="[16, 16]" class="summary-row">
        <a-col :xs="24" :sm="8">
          <a-card>
            <a-statistic title="当前项目" :value="currentProjectName" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8">
          <a-card>
            <a-statistic title="模块数" :value="moduleCount" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8">
          <a-card>
            <a-statistic title="当前结果集用例数" :value="cases.length" />
          </a-card>
        </a-col>
      </a-row>

      <div class="workspace">
        <div class="side-panel">
          <div class="side-title">
            <span>模块目录</span>
            <a-button type="link" size="small" :disabled="!selectedModuleId" @click="clearModuleFilter">
              查看全部
            </a-button>
          </div>
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            @select="onModuleSelect"
          />
        </div>

        <div class="main-panel">
          <div class="toolbar">
            <a-space wrap>
              <a-input-search
                v-model:value="searchText"
                placeholder="搜索用例名称"
                style="width: 240px"
              />
              <a-select
                v-model:value="filterType"
                placeholder="用例类型"
                allow-clear
                style="width: 130px"
                @change="loadCases"
              >
                <a-select-option value="api">接口测试</a-select-option>
                <a-select-option value="graphql">GraphQL</a-select-option>
                <a-select-option value="websocket">WebSocket</a-select-option>
                <a-select-option value="grpc">gRPC</a-select-option>
                <a-select-option value="web">Web UI</a-select-option>
                <a-select-option value="android">Android UI</a-select-option>
              </a-select>
              <a-tag color="blue">{{ selectedModuleId ? `当前模块：${activeModuleName}` : '当前模块：全部' }}</a-tag>
            </a-space>
            <a-dropdown :disabled="!selectedModuleId">
              <template #overlay>
                <a-menu>
                  <a-menu-item key="api" @click="openCreate('api')">接口测试</a-menu-item>
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
          </div>

          <a-table
            :columns="columns"
            :data-source="filteredCases"
            :loading="loading"
            row-key="id"
            size="middle"
            :pagination="{ pageSize: 20, showSizeChanger: true }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'module'">
                <span>{{ moduleNameMap[record.module_id] ?? `模块 #${record.module_id}` }}</span>
              </template>

              <template v-if="column.key === 'case_type'">
                <a-tag :color="typeColor(record.case_type)">{{ typeLabel(record.case_type) }}</a-tag>
              </template>

              <template v-if="column.key === 'tags'">
                <a-tag v-for="t in record.tags" :key="t" color="blue">{{ t }}</a-tag>
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
                  <a-button type="link" size="small" @click="openHistory(record.id)">
                    <HistoryOutlined /> 历史
                  </a-button>
                  <a-popconfirm title="确认删除该用例？" @confirm="handleDelete(record.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
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
      title="请选择一个项目"
      sub-title="选择项目后即可统一管理该项目下的模块与用例，并直接触发执行。"
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
      <p style="margin-bottom: 12px; color: #666">可选择一个环境，变量将自动注入到用例执行中。</p>
      <a-select
        v-model:value="runEnvId"
        placeholder="不使用环境"
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
      @rolled="loadCases"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, DownOutlined, HistoryOutlined } from '@ant-design/icons-vue'
import { caseApi, environmentApi, projectApi } from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import WebCaseDrawer from '@/views/case/WebCaseDrawer.vue'
import AndroidCaseDrawer from '@/views/case/AndroidCaseDrawer.vue'
import CaseHistoryDrawer from '@/views/case/CaseHistoryDrawer.vue'

const route = useRoute()
const router = useRouter()

const projects = ref<any[]>([])
const selectedProjectId = ref<number | null>(null)
const moduleNameMap = ref<Record<number, string>>({})
const cases = ref<any[]>([])
const loading = ref(false)
const selectedModuleId = ref<number | null>(null)
const searchText = ref('')
const filterType = ref<string | undefined>(undefined)
const drawerOpen = ref(false)
const editingCase = ref<any>(null)
const createCaseType = ref('api')
const webDrawerOpen = ref(false)
const webEditingCase = ref<any>(null)
const androidDrawerOpen = ref(false)
const androidEditingCase = ref<any>(null)
const runningId = ref<number | null>(null)
const historyOpen = ref(false)
const historyCaseId = ref<number | null>(null)

const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const pendingRunCase = ref<any>(null)

const columns = [
  { title: '用例名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '模块', key: 'module', width: 180 },
  { title: '类型', key: 'case_type', width: 110 },
  { title: '标签', key: 'tags', width: 200 },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    key: 'updated_at',
    width: 170,
    customRender: ({ text }: any) => text?.slice(0, 19).replace('T', ' '),
  },
  { title: '操作', key: 'action', width: 220, fixed: 'right' },
]

const projectOptions = computed(() =>
  projects.value.map((project: any) => ({ label: project.name, value: project.id })),
)

const currentProjectName = computed(() =>
  projects.value.find((project: any) => project.id === selectedProjectId.value)?.name ?? '-',
)

const moduleCount = computed(() => Object.keys(moduleNameMap.value).length)

const activeModuleName = computed(() =>
  selectedModuleId.value ? (moduleNameMap.value[selectedModuleId.value] ?? `模块 #${selectedModuleId.value}`) : '全部模块',
)

const filteredCases = computed(() =>
  cases.value.filter((testCase) => !searchText.value || testCase.name.includes(searchText.value)),
)

function parsePositiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(nodes: any[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (Array.isArray(node.children) && node.children.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function typeLabel(type: string) {
  return {
    api: '接口测试',
    graphql: 'GraphQL',
    websocket: 'WebSocket',
    grpc: 'gRPC',
    web: 'Web UI',
    android: 'Android',
  }[type] ?? type
}

function typeColor(type: string) {
  return {
    api: 'geekblue',
    graphql: 'orange',
    websocket: 'cyan',
    grpc: 'red',
    web: 'purple',
    android: 'green',
  }[type] ?? 'default'
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (error: any) {
    message.error(error ?? '加载项目列表失败')
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
    message.error(error ?? '加载模块树失败')
  }
}

async function loadCases() {
  if (!selectedProjectId.value) {
    cases.value = []
    return
  }

  loading.value = true
  try {
    cases.value = await caseApi.list({
      project_id: selectedProjectId.value,
      module_id: selectedModuleId.value ?? undefined,
      case_type: filterType.value,
    })
  } catch (error: any) {
    message.error(error ?? '加载用例列表失败')
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

function refreshCurrentProject() {
  void loadProjects()
  void loadModules()
  void loadCases()
}

function openCreate(type: string) {
  if (!selectedModuleId.value) {
    message.warning('请先选择一个模块再创建用例')
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

function openEdit(testCase: any) {
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

function onSaved() {
  void loadCases()
}

async function handleRun(testCase: any) {
  if (!selectedProjectId.value) return

  pendingRunCase.value = testCase
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const environments = await environmentApi.list(selectedProjectId.value)
    runEnvOptions.value = environments.map((item: any) => ({ label: item.name, value: item.id }))
  } catch {
    runEnvOptions.value = []
    message.warning('加载环境列表失败，将不使用环境执行')
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  const testCase = pendingRunCase.value
  if (!testCase) return

  runConfirming.value = true
  runningId.value = testCase.id
  try {
    const payload: { env_id?: number } = {}
    if (runEnvId.value) {
      payload.env_id = runEnvId.value
    }
    const run = await caseApi.run(testCase.id, payload) as any
    runModalOpen.value = false
    message.success('已触发执行，正在跳转报告页')
    void router.push(`/runs/${run.id}`)
  } catch (error: any) {
    message.error(error ?? '执行触发失败')
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function handleDelete(caseId: number) {
  try {
    await caseApi.delete(caseId)
    message.success('已删除')
    await loadCases()
  } catch (error: any) {
    message.error(error ?? '删除用例失败')
  }
}

function openHistory(caseId: number) {
  historyCaseId.value = caseId
  historyOpen.value = true
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

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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
