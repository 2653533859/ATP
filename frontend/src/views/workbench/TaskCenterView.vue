<template>
  <section class="task-center-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">{{ t('task_center.eyebrow') }}</p>
        <h1>{{ t('task_center.title') }}</h1>
        <p class="subtitle">{{ t('task_center.subtitle') }}</p>
      </div>
      <div class="heading-actions">
        <a-select
          v-model:value="projectId"
          allow-clear
          class="project-select"
          :placeholder="t('task_center.all_projects')"
          @change="loadTasks"
        >
          <a-select-option v-for="project in projects" :key="project.id" :value="project.id">
            {{ project.name }}
          </a-select-option>
        </a-select>
        <a-button :loading="loading" @click="loadTasks">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </div>
    </div>

    <div class="filter-bar">
      <a-select v-model:value="statusFilter" allow-clear :placeholder="t('task_center.status_filter')" @change="loadTasks">
        <a-select-option v-for="option in statusOptions" :key="option.value" :value="option.value">
          {{ t(`task_center.statuses.${option.value}`) }}
        </a-select-option>
      </a-select>
      <a-select v-model:value="taskType" allow-clear :placeholder="t('task_center.type_filter')" @change="loadTasks">
        <a-select-option v-for="option in taskTypeOptions" :key="option" :value="option">
          {{ t(`task_center.types.${option}`) }}
        </a-select-option>
      </a-select>
      <span class="filter-hint">{{ t('task_center.refresh_hint') }}</span>
    </div>

    <div class="action-bar">
      <span>{{ t('task_center.selected', { count: selectedRowKeys.length }) }}</span>
      <div class="action-buttons">
        <a-button :disabled="!selectedRowKeys.length" @click="handleBatch('retry')">
          {{ t('task_center.retry_selected') }}
        </a-button>
        <a-button danger :disabled="!selectedRowKeys.length" @click="handleBatch('stop')">
          {{ t('task_center.stop_selected') }}
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data-source="tasks"
      :loading="loading"
      row-key="id"
      :row-selection="rowSelection"
      :pagination="{ pageSize: 20, hideOnSinglePage: true }"
      :locale="{ emptyText: t('task_center.empty') }"
      :scroll="{ x: 1180 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'type'">
          <a-tag color="blue">{{ t(`task_center.types.${record.task_type}`) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'name'">
          <div class="task-name">{{ record.name }}</div>
          <div class="task-id">{{ t('task_center.run_id', { id: record.run_id }) }}</div>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'project'">
          {{ record.project_name || t('task_center.global_scope') }}
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" @click="router.push(record.detail_path)">{{ t('task_center.view') }}</a-button>
            <a-button v-if="record.can_retry" type="link" :loading="actionKey === record.id" @click="handleAction(asTask(record), 'retry')">
              {{ t('task_center.retry') }}
            </a-button>
            <a-button v-if="record.can_stop" type="link" danger :loading="actionKey === record.id" @click="handleAction(asTask(record), 'stop')">
              {{ t('task_center.stop') }}
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <div class="sync-note">
      {{ t('task_center.last_sync', { time: formatTime(generatedAt) }) }}
      <span v-if="hasMore"> · {{ t('task_center.has_more') }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import {
  projectApi,
  workbenchApi,
  type ProjectItem,
  type WorkbenchAction,
  type WorkbenchTaskItem,
  type WorkbenchTaskType,
} from '@/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const projects = ref<ProjectItem[]>([])
const projectId = ref<number | undefined>(toProjectId(route.query.project_id))
const statusFilter = ref<string | undefined>()
const taskType = ref<WorkbenchTaskType | undefined>()
const tasks = ref<WorkbenchTaskItem[]>([])
const selectedRowKeys = ref<string[]>([])
const generatedAt = ref<string | null>(null)
const hasMore = ref(false)
const loading = ref(false)
const actionKey = ref<string | null>(null)
let refreshTimer: number | undefined
let loadSequence = 0

const taskTypeOptions: WorkbenchTaskType[] = ['case', 'suite', 'plan', 'android', 'performance']
const statusOptions = [
  { value: 'pending' },
  { value: 'running' },
  { value: 'failed' },
  { value: 'error' },
  { value: 'passed' },
  { value: 'success' },
  { value: 'completed' },
  { value: 'cancelled' },
  { value: 'stopped' },
]

const columns = computed(() => [
  { title: t('task_center.columns.type'), key: 'type', width: 120 },
  { title: t('task_center.columns.name'), key: 'name', width: 260 },
  { title: t('task_center.columns.project'), key: 'project', width: 160 },
  { title: t('task_center.columns.status'), key: 'status', width: 120 },
  { title: t('task_center.columns.created_at'), key: 'created_at', width: 180 },
  { title: t('task_center.columns.action'), key: 'action', width: 220, fixed: 'right' as const },
])

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: (string | number)[]) => {
    selectedRowKeys.value = keys.map(String)
  },
}))

function toProjectId(value: unknown) {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

function formatTime(value?: string | null) {
  if (!value) return t('task_center.not_available')
  return value.slice(0, 19).replace('T', ' ')
}

function asTask(value: unknown) {
  return value as WorkbenchTaskItem
}

function statusLabel(status: string) {
  return t(`task_center.statuses.${status}`)
}

function statusColor(status: string) {
  return {
    pending: 'default',
    running: 'blue',
    cancelling: 'orange',
    passed: 'green',
    success: 'green',
    completed: 'green',
    failed: 'red',
    error: 'red',
    cancelled: 'orange',
    stopped: 'orange',
  }[status] ?? 'default'
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    message.error(t('task_center.projects_load_failed'))
  }
}

async function loadTasks() {
  const requestSequence = ++loadSequence
  loading.value = true
  try {
    const nextQuery = projectId.value ? { project_id: String(projectId.value) } : {}
    if (route.query.project_id !== nextQuery.project_id) {
      await router.replace({ query: nextQuery })
    }
    const result = await workbenchApi.tasks({
      project_id: projectId.value,
      status: statusFilter.value,
      task_type: taskType.value,
      limit: 200,
    })
    if (requestSequence !== loadSequence) return
    tasks.value = result.items
    generatedAt.value = result.generated_at
    hasMore.value = result.has_more
    selectedRowKeys.value = selectedRowKeys.value.filter((key) => tasks.value.some((task) => task.id === key))
  } catch {
    if (requestSequence === loadSequence) message.error(t('task_center.load_failed'))
  } finally {
    if (requestSequence === loadSequence) loading.value = false
  }
}

async function handleAction(task: WorkbenchTaskItem, action: WorkbenchAction) {
  actionKey.value = task.id
  try {
    if (action === 'retry' && !task.can_retry) return
    if (action === 'stop' && !task.can_stop) return
    const result = action === 'retry'
      ? await workbenchApi.retry(task.task_type, task.run_id)
      : await workbenchApi.stop(task.task_type, task.run_id)
    message.success(result.message)
    await loadTasks()
  } catch {
    message.error(t('task_center.action_failed'))
  } finally {
    actionKey.value = null
  }
}

async function handleBatch(action: WorkbenchAction) {
  const selected = tasks.value.filter((task) => selectedRowKeys.value.includes(task.id))
  const eligible = selected.filter((task) => action === 'retry' ? task.can_retry : task.can_stop)
  if (!eligible.length) {
    message.warning(t('task_center.no_eligible_tasks'))
    return
  }
  try {
    const result = await workbenchApi.batchAction(action, eligible.map((task) => ({ task_type: task.task_type, run_id: task.run_id })))
    if (result.failures.length) {
      message.warning(t('task_center.batch_partial', { processed: result.processed, failed: result.failures.length }))
    } else {
      message.success(t('task_center.batch_success', { count: result.processed }))
    }
    selectedRowKeys.value = []
    await loadTasks()
  } catch {
    message.error(t('task_center.action_failed'))
  }
}

onMounted(async () => {
  await loadProjects()
  await loadTasks()
  refreshTimer = window.setInterval(loadTasks, 10_000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== undefined) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.task-center-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-heading,
.heading-actions,
.filter-bar,
.action-bar,
.action-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-heading,
.action-bar {
  justify-content: space-between;
}

.page-heading {
  align-items: flex-start;
}

.heading-actions {
  flex-shrink: 0;
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: var(--c-text);
  font-size: clamp(24px, 3vw, 34px);
  letter-spacing: -0.03em;
}

.subtitle,
.filter-hint,
.task-id,
.sync-note {
  color: var(--c-text-secondary);
}

.subtitle {
  margin: 8px 0 0;
}

.project-select {
  min-width: 180px;
}

.filter-bar {
  padding: 12px;
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
}

.filter-hint {
  margin-left: auto;
  font-size: 12px;
}

.action-bar {
  color: var(--c-text-secondary);
  font-size: 13px;
}

.task-name {
  color: var(--c-text);
  font-weight: 600;
}

.task-id {
  margin-top: 4px;
  font-size: 12px;
}

.sync-note {
  font-size: 12px;
  text-align: right;
}

@media (max-width: 760px) {
  .page-heading,
  .heading-actions,
  .filter-bar,
  .action-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .project-select,
  .filter-bar :deep(.ant-select) {
    width: 100%;
  }

  .filter-hint {
    margin-left: 0;
  }
}
</style>
