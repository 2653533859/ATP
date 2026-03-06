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
      width="720"
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
        <a-form-item label="用例列表">
          <a-select
            v-model:value="selectedCaseIds"
            mode="multiple"
            placeholder="搜索并添加用例"
            style="width: 100%"
            :loading="casesLoading"
            option-label-prop="label"
          >
            <a-select-option
              v-for="c in availableCases"
              :key="c.id"
              :value="c.id"
              :label="c.name"
            >
              <a-tag :color="typeColor(c.case_type)" style="margin-right: 4px">
                {{ typeLabel(c.case_type) }}
              </a-tag>
              {{ c.name }}
            </a-select-option>
          </a-select>
          <div style="margin-top: 4px; color: #999; font-size: 12px">
            用例将按选择顺序依次执行
          </div>
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
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { suiteApi, projectApi, caseApi, environmentApi } from '@/api'

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
const availableCases = ref<any[]>([])
const casesLoading = ref(false)

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

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ')
}

function getProjectName(id: number) {
  return projects.value.find(p => p.id === id)?.name ?? '-'
}

function typeLabel(t: string) {
  return { api: '接口', web: 'Web', android: 'Android' }[t] ?? t
}

function typeColor(t: string) {
  return { api: 'geekblue', web: 'purple', android: 'green' }[t] ?? 'default'
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

async function loadCases() {
  if (!projectFilter.value) return
  casesLoading.value = true
  try {
    availableCases.value = await caseApi.list()
  } catch {
    availableCases.value = []
  } finally {
    casesLoading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', description: '' }
  selectedCaseIds.value = []
  loadCases()
  formOpen.value = true
}

async function openEdit(record: any) {
  editingId.value = record.id
  form.value = { name: record.name, description: record.description ?? '' }
  selectedCaseIds.value = (record.case_ids || []).map((c: any) => c.case_id)
  loadCases()
  formOpen.value = true
}

async function handleSave() {
  if (!form.value.name.trim()) {
    message.warning('请输入套件名称')
    return
  }
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
        project_id: projectFilter.value,
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
</style>
