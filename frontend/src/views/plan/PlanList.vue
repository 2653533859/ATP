<template>
  <div class="plan-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          placeholder="选择项目"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadPlans"
        />
      </a-space>
      <a-button type="primary" @click="openCreate" :disabled="!projectId">
        <PlusOutlined /> 新建计划
      </a-button>
    </div>

    <!-- 计划表格 -->
    <a-table
      :columns="columns"
      :data-source="plans"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20, showSizeChanger: true }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'schedule_type'">
          <a-tag :color="scheduleColor(record.schedule_type)">{{ scheduleLabel(record.schedule_type) }}</a-tag>
          <span v-if="record.schedule_type === 'cron'" style="font-size: 12px; color: #999; margin-left: 4px">
            {{ record.cron_expression }}
          </span>
        </template>

        <template v-if="column.key === 'is_enabled'">
          <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? '启用' : '禁用' }}</a-tag>
        </template>

        <template v-if="column.key === 'suites'">
          <span>{{ (record.suite_ids || []).length }} 个套件</span>
        </template>

        <template v-if="column.key === 'next_run_at'">
          <span v-if="record.next_run_at">{{ formatTime(record.next_run_at) }}</span>
          <span v-else style="color: #999">-</span>
        </template>

        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-button type="link" size="small" :loading="runningId === record.id" @click="handleRun(record)">执行</a-button>
            <a-button type="link" size="small" @click="viewRuns(record)">记录</a-button>
            <a-popconfirm title="确认删除该计划？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新建/编辑 Modal -->
    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? '编辑测试计划' : '新建测试计划'"
      :confirm-loading="saving"
      width="640px"
      @ok="handleSave"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="计划名称" :rules="[{ required: true }]">
          <a-input v-model:value="form.name" placeholder="计划名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
        </a-form-item>

        <!-- 套件选择 -->
        <a-form-item label="测试套件">
          <a-select
            v-model:value="selectedSuiteIds"
            mode="multiple"
            placeholder="选择要包含的测试套件"
            :options="suiteOptions"
            :loading="suitesLoading"
            style="width: 100%"
          />
        </a-form-item>

        <!-- 调度配置 -->
        <a-divider orientation="left" style="font-size: 13px">调度配置</a-divider>
        <a-form-item label="调度方式">
          <a-radio-group v-model:value="form.schedule_type">
            <a-radio-button value="manual">手动触发</a-radio-button>
            <a-radio-button value="cron">定时 Cron</a-radio-button>
            <a-radio-button value="webhook">Webhook</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-form-item v-if="form.schedule_type === 'cron'" label="Cron 表达式">
          <a-input v-model:value="form.cron_expression" placeholder="*/30 * * * *（每30分钟）" />
          <div style="margin-top: 4px; font-size: 12px; color: #999">
            格式：分 时 日 月 周 &nbsp; 例：0 8 * * 1-5 = 工作日每天 8:00
          </div>
        </a-form-item>

        <a-form-item v-if="form.schedule_type === 'webhook' && editingPlan?.webhook_secret" label="Webhook Secret">
          <a-input-group compact>
            <a-input :value="editingPlan.webhook_secret" readonly style="width: calc(100% - 80px); font-family: monospace; font-size: 12px" />
            <a-button @click="copySecret">复制</a-button>
          </a-input-group>
          <div style="margin-top: 4px; font-size: 12px; color: #999">
            请求时带上 Header: X-Webhook-Secret: {{ editingPlan.webhook_secret?.slice(0, 8) }}...
          </div>
        </a-form-item>

        <a-form-item label="默认环境">
          <a-select
            v-model:value="form.env_id"
            placeholder="不使用环境"
            allow-clear
            style="width: 100%"
            :options="envOptions"
            :loading="envLoading"
          />
        </a-form-item>

        <a-form-item label="启用调度">
          <a-switch v-model:checked="form.is_enabled" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 执行记录 Modal -->
    <a-modal v-model:open="runsOpen" title="执行记录" width="800px" :footer="null">
      <a-table
        :columns="runColumns"
        :data-source="planRuns"
        :loading="runsLoading"
        row-key="id"
        size="small"
        :pagination="{ pageSize: 10 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="runStatusColor(record.status)">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'trigger_type'">
            <a-tag>{{ scheduleLabel(record.trigger_type) }}</a-tag>
          </template>
          <template v-if="column.key === 'summary'">
            <span v-if="record.result_summary">
              {{ record.result_summary.passed || 0 }}/{{ record.result_summary.total || 0 }} 通过
            </span>
          </template>
          <template v-if="column.key === 'duration_ms'">
            {{ record.duration_ms ? (record.duration_ms / 1000).toFixed(1) + 's' : '-' }}
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { planApi, projectApi, suiteApi, environmentApi } from '@/api'

const plans = ref<any[]>([])
const loading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingPlan = ref<any>(null)
const runningId = ref<number | null>(null)

const selectedSuiteIds = ref<number[]>([])
const suiteOptions = ref<Array<{ label: string; value: number }>>([])
const suitesLoading = ref(false)

const envOptions = ref<Array<{ label: string; value: number }>>([])
const envLoading = ref(false)

const form = ref({
  name: '',
  description: '',
  schedule_type: 'manual',
  cron_expression: '',
  is_enabled: true,
  env_id: null as number | null,
})

const runsOpen = ref(false)
const planRuns = ref<any[]>([])
const runsLoading = ref(false)

const columns = [
  { title: '计划名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '调度方式', key: 'schedule_type', width: 160 },
  { title: '套件', key: 'suites', width: 90 },
  { title: '状态', key: 'is_enabled', width: 80 },
  { title: '下次执行', key: 'next_run_at', width: 170 },
  { title: '操作', key: 'action', width: 220, fixed: 'right' },
]

const runColumns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '触发方式', key: 'trigger_type', width: 100 },
  { title: '状态', key: 'status', width: 90 },
  { title: '结果', key: 'summary', width: 120 },
  { title: '耗时', key: 'duration_ms', width: 90 },
  { title: '时间', dataIndex: 'created_at', width: 170,
    customRender: ({ text }: any) => text?.slice(0, 19).replace('T', ' ') },
]

function scheduleLabel(t: string) {
  return { manual: '手动', cron: '定时', webhook: 'Webhook' }[t] ?? t
}
function scheduleColor(t: string) {
  return { manual: 'default', cron: 'blue', webhook: 'orange' }[t] ?? 'default'
}
function runStatusColor(s: string) {
  return { pending: 'default', running: 'processing', passed: 'success', failed: 'error', error: 'warning' }[s] ?? 'default'
}
function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ') ?? '-'
}

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: any) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadPlans() {
  if (!projectId.value) { plans.value = []; return }
  loading.value = true
  try {
    plans.value = await planApi.list({ project_id: projectId.value })
  } catch { message.error('加载计划列表失败') }
  finally { loading.value = false }
}

async function loadSuites() {
  if (!projectId.value) return
  suitesLoading.value = true
  try {
    const list = await suiteApi.list({ project_id: projectId.value })
    suiteOptions.value = list.map((s: any) => ({ label: s.name, value: s.id }))
  } catch { /* ignore */ }
  finally { suitesLoading.value = false }
}

async function loadEnvs() {
  if (!projectId.value) return
  envLoading.value = true
  try {
    const list = await environmentApi.list(projectId.value)
    envOptions.value = list.map((e: any) => ({ label: e.name, value: e.id }))
  } catch { /* ignore */ }
  finally { envLoading.value = false }
}

function openCreate() {
  isEdit.value = false
  editingPlan.value = null
  form.value = { name: '', description: '', schedule_type: 'manual', cron_expression: '', is_enabled: true, env_id: null }
  selectedSuiteIds.value = []
  formOpen.value = true
  loadSuites()
  loadEnvs()
}

function openEdit(record: any) {
  isEdit.value = true
  editingPlan.value = record
  form.value = {
    name: record.name,
    description: record.description ?? '',
    schedule_type: record.schedule_type,
    cron_expression: record.cron_expression ?? '',
    is_enabled: record.is_enabled,
    env_id: record.env_id,
  }
  selectedSuiteIds.value = (record.suite_ids || []).map((s: any) => s.suite_id)
  formOpen.value = true
  loadSuites()
  loadEnvs()
}

async function handleSave() {
  if (!form.value.name) { message.warning('请输入计划名称'); return }
  if (selectedSuiteIds.value.length === 0) { message.warning('请选择至少一个套件'); return }
  if (form.value.schedule_type === 'cron' && !form.value.cron_expression) {
    message.warning('请输入 Cron 表达式'); return
  }

  saving.value = true
  try {
    const suiteList = selectedSuiteIds.value.map((id, idx) => ({ suite_id: id, sort: idx }))
    const payload = {
      name: form.value.name,
      description: form.value.description || null,
      suite_ids: suiteList,
      schedule_type: form.value.schedule_type,
      cron_expression: form.value.schedule_type === 'cron' ? form.value.cron_expression : null,
      is_enabled: form.value.is_enabled,
      env_id: form.value.env_id,
    }
    if (isEdit.value) {
      await planApi.update(editingPlan.value.id, payload)
    } else {
      await planApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    formOpen.value = false
    loadPlans()
  } catch { message.error('保存失败') }
  finally { saving.value = false }
}

async function handleRun(record: any) {
  runningId.value = record.id
  try {
    await planApi.run(record.id)
    message.success('已触发执行')
    loadPlans()
  } catch { message.error('执行触发失败') }
  finally { runningId.value = null }
}

async function handleDelete(id: number) {
  try {
    await planApi.delete(id)
    message.success('已删除')
    loadPlans()
  } catch { message.error('删除失败') }
}

async function viewRuns(record: any) {
  runsOpen.value = true
  runsLoading.value = true
  try {
    planRuns.value = await planApi.listRuns({ plan_id: record.id })
  } catch { message.error('加载执行记录失败') }
  finally { runsLoading.value = false }
}

function copySecret() {
  if (editingPlan.value?.webhook_secret) {
    navigator.clipboard.writeText(editingPlan.value.webhook_secret)
    message.success('已复制到剪贴板')
  }
}
</script>

<style scoped>
.plan-page {
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
