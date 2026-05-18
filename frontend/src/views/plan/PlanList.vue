<template>
  <div class="plan-page">
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

    <BatchOperationBar :selected-count="selectedRowKeys.length" @cancel="selectedRowKeys = []">
      <a-button size="small" @click="handleBatchToggle(true)">批量启用</a-button>
      <a-button size="small" @click="handleBatchToggle(false)">批量停用</a-button>
      <a-popconfirm
        :title="`确认删除选中的 ${selectedRowKeys.length} 个计划？`"
        ok-text="删除"
        cancel-text="取消"
        @confirm="handleBatchDelete"
      >
        <a-button size="small" danger>批量删除</a-button>
      </a-popconfirm>
    </BatchOperationBar>

    <a-table
      :columns="columns"
      :data-source="plans"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20, showSizeChanger: true }"
      :row-selection="{ selectedRowKeys, onChange: (keys: (string | number)[]) => (selectedRowKeys = keys as number[]) }"
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

        <a-divider orientation="left" style="font-size: 13px">调度配置</a-divider>
        <a-form-item label="调度方式">
          <a-radio-group v-model:value="form.schedule_type">
            <a-radio-button value="manual">手动触发</a-radio-button>
            <a-radio-button value="cron">定时 Cron</a-radio-button>
            <a-radio-button value="webhook">Webhook</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <template v-if="form.schedule_type === 'cron'">
          <a-form-item label="配置方式">
            <a-radio-group v-model:value="cronMode">
              <a-radio-button value="daily">每天</a-radio-button>
              <a-radio-button value="weekly">每周</a-radio-button>
              <a-radio-button value="custom">自定义 Cron</a-radio-button>
            </a-radio-group>
          </a-form-item>

          <a-row v-if="cronMode === 'daily'" :gutter="12">
            <a-col :span="12">
              <a-form-item label="执行小时">
                <a-select v-model:value="cronHour" :options="hourOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="执行分钟">
                <a-select v-model:value="cronMinute" :options="minuteOptions" />
              </a-form-item>
            </a-col>
          </a-row>

          <template v-else-if="cronMode === 'weekly'">
            <a-form-item label="执行星期">
              <a-select v-model:value="cronWeekday" :options="weekdayOptions" />
            </a-form-item>
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="执行小时">
                  <a-select v-model:value="cronHour" :options="hourOptions" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="执行分钟">
                  <a-select v-model:value="cronMinute" :options="minuteOptions" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <a-form-item v-else label="Cron 表达式">
            <a-input v-model:value="customCronExpression" placeholder="*/30 * * * *" />
            <div class="cron-help-text">
              格式：分 时 日 月 周，例如 `0 8 * * 1-5` 表示工作日每天 8:00。
            </div>
          </a-form-item>

          <a-alert
            v-if="cronValidationError"
            type="error"
            show-icon
            :message="cronValidationError"
            style="margin-bottom: 16px"
          />
          <a-alert
            v-else
            type="info"
            show-icon
            style="margin-bottom: 16px"
            :message="`Cron：${cronPreviewExpression}`"
            :description="cronDescription"
          />
        </template>

        <a-form-item v-if="form.schedule_type === 'webhook' && editingPlan?.webhook_secret" label="Webhook Secret">
          <a-input-group compact>
            <a-input :value="editingPlan.webhook_secret" readonly style="width: calc(100% - 80px); font-family: monospace; font-size: 12px" />
            <a-button @click="copySecret">复制</a-button>
          </a-input-group>
          <div class="cron-help-text">
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

        <a-form-item label="自动创建缺陷">
          <a-switch v-model:checked="form.auto_create_bugs" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="runsOpen" title="执行记录" width="800px" :footer="null">
      <a-table
        :columns="runColumns"
        :data-source="planRuns"
        :loading="runsLoading"
        row-key="id"
        size="small"
        :pagination="{ pageSize: 10 }"
        :expandedRowKeys="expandedRunKeys"
        @expand="onRunExpand"
      >
        <template #expandedRowRender="{ record }">
          <div class="auto-bugs-panel">
            <template v-if="record.result_summary?.auto_bugs_error">
              <a-alert type="error" show-icon :message="record.result_summary.auto_bugs_error" />
            </template>
            <template v-else-if="record.result_summary?.auto_bugs?.length">
              <div class="auto-bugs-title">自动创建缺陷结果</div>
              <a-table
                :columns="autoBugColumns"
                :data-source="record.result_summary.auto_bugs"
                row-key="bug_id"
                size="small"
                :pagination="false"
              >
                <template #bodyCell="{ column, record: autoBug }">
                  <template v-if="column.key === 'bug_id'">
                    <a v-if="autoBug.bug_url" :href="autoBug.bug_url" target="_blank">{{ autoBug.bug_id }}</a>
                    <span v-else>{{ autoBug.bug_id }}</span>
                  </template>
                  <template v-if="column.key === 'duplicate'">
                    <a-tag :color="autoBug.duplicate ? 'orange' : 'green'">{{ autoBug.duplicate ? '重复命中' : '新建成功' }}</a-tag>
                  </template>
                  <template v-if="column.key === 'attachment_uploaded'">
                    <a-tag :color="autoBug.attachment_uploaded ? 'blue' : 'default'">{{ autoBug.attachment_uploaded ? '已上传' : '未上传' }}</a-tag>
                  </template>
                </template>
              </a-table>
            </template>
            <template v-else>
              <a-empty description="没有自动创建缺陷记录" :image="false" />
            </template>
          </div>
        </template>
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
          <template v-if="column.key === 'auto_bugs'">
            <a-tag v-if="record.result_summary?.auto_bugs_error" color="red">异常</a-tag>
            <a-tag v-else-if="record.result_summary?.auto_bugs?.length" color="blue">{{ record.result_summary.auto_bugs.length }} 条</a-tag>
            <span v-else style="color: #999">-</span>
          </template>
          <template v-if="column.key === 'duration_ms'">
            {{ record.duration_ms ? (record.duration_ms / 1000).toFixed(1) + 's' : '-' }}
          </template>
          <template v-if="column.key === 'export'">
            <a-space>
              <a-button type="link" size="small" :loading="exportingPlanRunHtmlId === record.id" @click="handleExportPlanRunHtml(record.id)">HTML</a-button>
              <a-button type="link" size="small" :loading="exportingPlanRunPdfId === record.id" @click="handleExportPlanRunPdf(record.id)">PDF</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import type {
  EnvironmentItem,
  PlanItem,
  PlanRunItem,
  ProjectItem,
  ScheduleType,
  SuiteItem,
} from '@/api'
import { environmentApi, planApi, projectApi, suiteApi } from '@/api'
import BatchOperationBar from '@/components/common/BatchOperationBar.vue'

type SelectOption = { label: string; value: number }
type CronMode = 'daily' | 'weekly' | 'custom'

const weekdayLabels: Record<number, string> = {
  0: '周日',
  1: '周一',
  2: '周二',
  3: '周三',
  4: '周四',
  5: '周五',
  6: '周六',
}

const weekdayOptions = Object.entries(weekdayLabels).map(([value, label]) => ({
  label,
  value: Number(value),
}))
const hourOptions = Array.from({ length: 24 }, (_, value) => ({
  label: `${String(value).padStart(2, '0')} 时`,
  value,
}))
const minuteOptions = Array.from({ length: 60 }, (_, value) => ({
  label: `${String(value).padStart(2, '0')} 分`,
  value,
}))

function getErrorMessage(error: unknown, fallback: string) {
  return typeof error === 'string' ? error : fallback
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ') ?? '-'
}

function isIntegerInRange(value: string, min: number, max: number) {
  if (!/^\d+$/.test(value)) return false
  const num = Number(value)
  return num >= min && num <= max
}

function validateCronField(field: string, min: number, max: number): boolean {
  if (field === '*') return true
  if (field.includes('/')) {
    const [base, step] = field.split('/')
    return (base === '*' || isIntegerInRange(base, min, max)) && isIntegerInRange(step, 1, max - min + 1)
  }
  if (field.includes('-')) {
    const [start, end] = field.split('-')
    return isIntegerInRange(start, min, max) && isIntegerInRange(end, min, max) && Number(start) <= Number(end)
  }
  if (field.includes(',')) {
    return field.split(',').every(part => validateCronField(part, min, max))
  }
  return isIntegerInRange(field, min, max)
}

function validateCronExpression(expression: string) {
  const trimmed = expression.trim()
  if (!trimmed) return '请输入 Cron 表达式'

  const parts = trimmed.split(/\s+/)
  if (parts.length !== 5) return 'Cron 表达式必须包含 5 段：分 时 日 月 周'

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts
  if (!validateCronField(minute, 0, 59)) return 'Cron 分钟段不合法'
  if (!validateCronField(hour, 0, 23)) return 'Cron 小时段不合法'
  if (!validateCronField(dayOfMonth, 1, 31)) return 'Cron 日期段不合法'
  if (!validateCronField(month, 1, 12)) return 'Cron 月份段不合法'
  if (!validateCronField(dayOfWeek, 0, 6)) return 'Cron 星期段不合法（0=周日，6=周六）'
  return ''
}

function parseCronPreset(expression: string | null | undefined): {
  mode: CronMode
  hour: number
  minute: number
  weekday: number
  customExpression: string
} {
  const cron = (expression ?? '').trim()
  const dailyMatch = cron.match(/^(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*$/)
  if (dailyMatch) {
    return {
      mode: 'daily',
      minute: Number(dailyMatch[1]),
      hour: Number(dailyMatch[2]),
      weekday: 1,
      customExpression: cron,
    }
  }

  const weeklyMatch = cron.match(/^(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+([0-6])$/)
  if (weeklyMatch) {
    return {
      mode: 'weekly',
      minute: Number(weeklyMatch[1]),
      hour: Number(weeklyMatch[2]),
      weekday: Number(weeklyMatch[3]),
      customExpression: cron,
    }
  }

  return {
    mode: 'custom',
    minute: 0,
    hour: 9,
    weekday: 1,
    customExpression: cron,
  }
}

const plans = ref<PlanItem[]>([])
const loading = ref(false)
const selectedRowKeys = ref<number[]>([])
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<SelectOption[]>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingPlan = ref<PlanItem | null>(null)
const runningId = ref<number | null>(null)

const selectedSuiteIds = ref<number[]>([])
const suiteOptions = ref<SelectOption[]>([])
const suitesLoading = ref(false)

const envOptions = ref<SelectOption[]>([])
const envLoading = ref(false)

const form = ref({
  name: '',
  description: '',
  schedule_type: 'manual' as ScheduleType,
  cron_expression: '',
  is_enabled: true,
  auto_create_bugs: false,
  env_id: null as number | null,
})

const cronMode = ref<CronMode>('daily')
const cronHour = ref(9)
const cronMinute = ref(0)
const cronWeekday = ref(1)
const customCronExpression = ref('')

const cronPreviewExpression = computed(() => {
  if (form.value.schedule_type !== 'cron') return ''
  if (cronMode.value === 'daily') return `${cronMinute.value} ${cronHour.value} * * *`
  if (cronMode.value === 'weekly') return `${cronMinute.value} ${cronHour.value} * * ${cronWeekday.value}`
  return customCronExpression.value.trim()
})

const cronValidationError = computed(() => {
  if (form.value.schedule_type !== 'cron') return ''
  return validateCronExpression(cronPreviewExpression.value)
})

const cronDescription = computed(() => {
  if (form.value.schedule_type !== 'cron') return ''
  if (cronValidationError.value) return '请先修正 Cron 配置'
  const hh = String(cronHour.value).padStart(2, '0')
  const mm = String(cronMinute.value).padStart(2, '0')
  if (cronMode.value === 'daily') return `每天 ${hh}:${mm} 执行`
  if (cronMode.value === 'weekly') return `${weekdayLabels[cronWeekday.value]} ${hh}:${mm} 执行`
  return '使用自定义 Cron 表达式执行'
})

watch(
  [cronMode, cronHour, cronMinute, cronWeekday, customCronExpression, () => form.value.schedule_type],
  () => {
    form.value.cron_expression = form.value.schedule_type === 'cron' ? cronPreviewExpression.value : ''
  },
  { immediate: true },
)

watch(
  () => form.value.schedule_type,
  (value) => {
    if (value !== 'cron') {
      form.value.cron_expression = ''
    }
  },
)

const runsOpen = ref(false)
const planRuns = ref<PlanRunItem[]>([])
const runsLoading = ref(false)
const expandedRunKeys = ref<number[]>([])
const exportingPlanRunHtmlId = ref<number | null>(null)
const exportingPlanRunPdfId = ref<number | null>(null)

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
  { title: '自动缺陷', key: 'auto_bugs', width: 120 },
  { title: '耗时', key: 'duration_ms', width: 90 },
  {
    title: '时间',
    dataIndex: 'created_at',
    width: 170,
    customRender: ({ text }: { text?: string }) => formatTime(text ?? ''),
  },
  { title: '导出', key: 'export', width: 160 },
]

const autoBugColumns = [
  { title: '用例 ID', dataIndex: 'case_id', key: 'case_id', width: 90 },
  { title: '缺陷单号', key: 'bug_id', width: 180 },
  { title: '结果', key: 'duplicate', width: 100 },
  { title: '截图上传', key: 'attachment_uploaded', width: 100 },
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

function resetCronEditor(expression?: string | null) {
  const parsed = parseCronPreset(expression)
  cronMode.value = parsed.mode
  cronHour.value = parsed.hour
  cronMinute.value = parsed.minute
  cronWeekday.value = parsed.weekday
  customCronExpression.value = parsed.customExpression
}

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: ProjectItem) => ({ label: p.name, value: p.id }))
  } catch (error: unknown) {
    projectOptions.value = []
    message.error(getErrorMessage(error, '加载项目列表失败'))
  }
})

async function loadPlans() {
  if (!projectId.value) {
    plans.value = []
    return
  }
  loading.value = true
  try {
    plans.value = await planApi.list({ project_id: projectId.value })
  } catch (error: unknown) {
    plans.value = []
    message.error(getErrorMessage(error, '加载计划列表失败'))
  } finally {
    loading.value = false
  }
}

async function handleBatchDelete() {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await planApi.batchDelete(selectedRowKeys.value)
    message.success(`已删除 ${result.processed} / ${result.requested} 个计划`)
    selectedRowKeys.value = []
    await loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '批量删除失败'))
  }
}

async function handleBatchToggle(isEnabled: boolean) {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await planApi.batchToggle(selectedRowKeys.value, isEnabled)
    message.success(`已${isEnabled ? '启用' : '停用'} ${result.processed} / ${result.requested} 个计划`)
    selectedRowKeys.value = []
    await loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '批量操作失败'))
  }
}

async function loadSuites() {
  if (!projectId.value) return
  suitesLoading.value = true
  try {
    const list = await suiteApi.list({ project_id: projectId.value })
    suiteOptions.value = list.map((s: SuiteItem) => ({ label: s.name, value: s.id }))
  } catch (error: unknown) {
    suiteOptions.value = []
    message.error(getErrorMessage(error, '加载套件列表失败'))
  } finally {
    suitesLoading.value = false
  }
}

async function loadEnvs() {
  if (!projectId.value) return
  envLoading.value = true
  try {
    const list = await environmentApi.list(projectId.value)
    envOptions.value = list.map((e: EnvironmentItem) => ({ label: e.name, value: e.id }))
  } catch (error: unknown) {
    envOptions.value = []
    message.error(getErrorMessage(error, '加载环境列表失败'))
  } finally {
    envLoading.value = false
  }
}

function openCreate() {
  isEdit.value = false
  editingPlan.value = null
  form.value = { name: '', description: '', schedule_type: 'manual', cron_expression: '', is_enabled: true, auto_create_bugs: false, env_id: null }
  selectedSuiteIds.value = []
  resetCronEditor('0 9 * * *')
  formOpen.value = true
  loadSuites()
  loadEnvs()
}

function openEdit(record: PlanItem) {
  isEdit.value = true
  editingPlan.value = record
  form.value = {
    name: record.name,
    description: record.description ?? '',
    schedule_type: record.schedule_type,
    cron_expression: record.cron_expression ?? '',
    is_enabled: record.is_enabled,
    auto_create_bugs: record.auto_create_bugs ?? false,
    env_id: record.env_id ?? null,
  }
  resetCronEditor(record.cron_expression)
  selectedSuiteIds.value = (record.suite_ids || []).map((s) => s.suite_id)
  formOpen.value = true
  loadSuites()
  loadEnvs()
}

async function handleSave() {
  if (!form.value.name) {
    message.warning('请输入计划名称')
    return
  }
  if (selectedSuiteIds.value.length === 0) {
    message.warning('请选择至少一个套件')
    return
  }
  if (form.value.schedule_type === 'cron') {
    if (cronValidationError.value) {
      message.warning(cronValidationError.value)
      return
    }
    form.value.cron_expression = cronPreviewExpression.value
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
      auto_create_bugs: form.value.auto_create_bugs,
      env_id: form.value.env_id,
    }
    if (isEdit.value && editingPlan.value) {
      await planApi.update(editingPlan.value.id, payload)
    } else {
      await planApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? '更新成功' : '创建成功')
    formOpen.value = false
    void loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function handleRun(record: PlanItem) {
  runningId.value = record.id
  try {
    await planApi.run(record.id)
    message.success('已触发执行')
    void loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '执行触发失败'))
  } finally {
    runningId.value = null
  }
}

async function handleDelete(id: number) {
  try {
    await planApi.delete(id)
    message.success('已删除')
    void loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '删除失败'))
  }
}

async function viewRuns(record: PlanItem) {
  runsOpen.value = true
  runsLoading.value = true
  expandedRunKeys.value = []
  try {
    planRuns.value = await planApi.listRuns({ plan_id: record.id })
  } catch (error: unknown) {
    planRuns.value = []
    message.error(getErrorMessage(error, '加载执行记录失败'))
  } finally {
    runsLoading.value = false
  }
}

function onRunExpand(expanded: boolean, record: PlanRunItem) {
  if (expanded) {
    expandedRunKeys.value = [record.id]
    return
  }
  expandedRunKeys.value = expandedRunKeys.value.filter(id => id !== record.id)
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

async function handleExportPlanRunHtml(runId: number) {
  exportingPlanRunHtmlId.value = runId
  try {
    const blob = await planApi.exportRunHtml(runId)
    downloadBlob(blob, `plan-run-${runId}-report.html`)
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '导出 HTML 失败'))
  } finally {
    exportingPlanRunHtmlId.value = null
  }
}

async function handleExportPlanRunPdf(runId: number) {
  exportingPlanRunPdfId.value = runId
  try {
    const blob = await planApi.exportRunPdf(runId)
    downloadBlob(blob, `plan-run-${runId}-report.pdf`)
  } catch (error: unknown) {
    message.error(getErrorMessage(error, '导出 PDF 失败'))
  } finally {
    exportingPlanRunPdfId.value = null
  }
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

.cron-help-text {
  margin-top: 4px;
  font-size: 12px;
  color: #999;
}

.auto-bugs-panel {
  padding: 8px 0;
}

.auto-bugs-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #595959;
}
</style>
