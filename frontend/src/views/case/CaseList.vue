<template>
  <div class="case-page">
    <!-- 左侧：模块树 -->
    <div class="side-panel">
      <ModuleTree
        :project-id="projectId"
        @select="onModuleSelect"
      />
    </div>

    <!-- 右侧：用例列表 -->
    <div class="main-panel">
      <!-- 工具栏 -->
      <div class="toolbar">
        <a-space>
          <a-input-search
            v-model:value="searchText"
            placeholder="搜索用例名称"
            style="width: 240px"
            @search="loadCases"
          />
          <a-select
            v-model:value="filterType"
            placeholder="用例类型"
            allow-clear
            style="width: 130px"
            @change="loadCases"
          >
            <a-select-option value="api">接口测试</a-select-option>
            <a-select-option value="web">Web UI</a-select-option>
            <a-select-option value="android">Android UI</a-select-option>
          </a-select>
        </a-space>
        <a-dropdown :disabled="!selectedModuleId">
          <template #overlay>
            <a-menu>
              <a-menu-item key="api" @click="openCreate('api')">接口测试</a-menu-item>
              <a-menu-item key="web" @click="openCreate('web')">Web UI</a-menu-item>
            </a-menu>
          </template>
          <a-button type="primary" :disabled="!selectedModuleId">
            <PlusOutlined /> 新建用例 <DownOutlined />
          </a-button>
        </a-dropdown>
      </div>

      <!-- 无模块选中提示 -->
      <a-result
        v-if="!selectedModuleId"
        status="info"
        title="请先在左侧选择模块"
        sub-title="选中模块后可查看和管理该模块下的用例"
        style="padding-top: 80px"
      />

      <!-- 用例表格 -->
      <a-table
        v-else
        :columns="columns"
        :data-source="filteredCases"
        :loading="loading"
        row-key="id"
        size="middle"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
      >
        <template #bodyCell="{ column, record }">
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
              <a-popconfirm title="确认删除该用例？" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 用例表单抽屉 (API) -->
    <CaseFormDrawer
      :open="drawerOpen"
      :module-id="selectedModuleId"
      :edit-case="editingCase"
      @close="drawerOpen = false"
      @saved="onSaved"
    />

    <!-- Web UI 用例抽屉 -->
    <WebCaseDrawer
      :open="webDrawerOpen"
      :module-id="selectedModuleId"
      :edit-case="webEditingCase"
      @close="webDrawerOpen = false"
      @saved="onSaved"
    />

    <!-- 执行环境选择 Modal -->
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, DownOutlined } from '@ant-design/icons-vue'
import { caseApi, environmentApi } from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import WebCaseDrawer from '@/views/case/WebCaseDrawer.vue'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)

const cases = ref<any[]>([])
const loading = ref(false)
const selectedModuleId = ref<number | null>(null)
const searchText = ref('')
const filterType = ref<string | undefined>(undefined)
const drawerOpen = ref(false)
const editingCase = ref<any>(null)
const webDrawerOpen = ref(false)
const webEditingCase = ref<any>(null)
const runningId = ref<number | null>(null)

// -- Run environment selection --
const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const pendingRunCase = ref<any>(null)

const columns = [
  { title: '用例名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '类型', key: 'case_type', width: 110 },
  { title: '标签', key: 'tags', width: 200 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170,
    customRender: ({ text }: any) => text?.slice(0, 19).replace('T', ' ') },
  { title: '操作', key: 'action', width: 160, fixed: 'right' },
]

const filteredCases = computed(() =>
  cases.value.filter(c => !searchText.value || c.name.includes(searchText.value)),
)

function typeLabel(t: string) {
  return { api: '接口测试', web: 'Web UI', android: 'Android' }[t] ?? t
}
function typeColor(t: string) {
  return { api: 'geekblue', web: 'purple', android: 'green' }[t] ?? 'default'
}

async function loadCases() {
  if (!selectedModuleId.value) return
  loading.value = true
  try {
    cases.value = await caseApi.list({
      module_id: selectedModuleId.value,
      case_type: filterType.value,
    })
  } catch (e: any) {
    message.error(e ?? '加载用例列表失败')
  } finally {
    loading.value = false
  }
}

function onModuleSelect(id: number | null) {
  selectedModuleId.value = id
  cases.value = []
  if (id) loadCases()
}

function openCreate(type: string) {
  if (type === 'web') {
    webEditingCase.value = null
    webDrawerOpen.value = true
  } else {
    editingCase.value = null
    drawerOpen.value = true
  }
}

function openEdit(c: any) {
  if (c.case_type === 'web') {
    webEditingCase.value = c
    webDrawerOpen.value = true
  } else {
    editingCase.value = c
    drawerOpen.value = true
  }
}

function onSaved() {
  loadCases()
}

async function handleRun(c: any) {
  pendingRunCase.value = c
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const envs = await environmentApi.list(projectId)
    runEnvOptions.value = envs.map((e: any) => ({ label: e.name, value: e.id }))
  } catch {
    runEnvOptions.value = []
    message.warning('加载环境列表失败，将不使用环境执行')
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  const c = pendingRunCase.value
  if (!c) return
  runConfirming.value = true
  runningId.value = c.id
  try {
    const payload: { env_id?: number } = {}
    if (runEnvId.value) {
      payload.env_id = runEnvId.value
    }
    const run = await caseApi.run(c.id, payload) as any
    runModalOpen.value = false
    message.success('已触发执行，正在跳转报告页')
    router.push(`/runs/${run.id}`)
  } catch (e: any) {
    message.error(e ?? '执行触发失败')
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function handleDelete(id: number) {
  try {
    await caseApi.delete(id)
    message.success('已删除')
    loadCases()
  } catch (e: any) {
    message.error(e ?? '删除用例失败')
  }
}
</script>

<style scoped>
.case-page {
  display: flex;
  gap: 16px;
  height: 100%;
}
.side-panel {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid #f0f0f0;
  padding-right: 16px;
  overflow-y: auto;
}
.main-panel {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
