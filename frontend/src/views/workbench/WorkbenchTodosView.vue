<template>
  <section class="workbench-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">{{ t('workbench.eyebrow') }}</p>
        <h1>{{ t('workbench.todos_title') }}</h1>
        <p class="subtitle">{{ t('workbench.todos_subtitle') }}</p>
      </div>
      <div class="heading-actions">
        <a-select
          v-model:value="projectId"
          allow-clear
          class="project-select"
          :placeholder="t('workbench.all_projects')"
          @change="handleProjectChange"
        >
          <a-select-option v-for="project in projects" :key="project.id" :value="project.id">
            {{ project.name }}
          </a-select-option>
        </a-select>
        <a-button :loading="loading" @click="loadOverview">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </div>
    </div>

    <div class="metric-grid">
      <a-card v-for="metric in metrics" :key="metric.key" size="small" class="metric-card">
        <a-statistic :title="t(metric.labelKey)" :value="count(metric.key)" />
        <span class="metric-caption">{{ t(metric.captionKey) }}</span>
      </a-card>
    </div>

    <a-alert
      class="scope-alert"
      type="info"
      show-icon
      :message="t('workbench.todos_scope_title')"
      :description="t('workbench.todos_scope_description')"
    />

    <a-card :bordered="false" class="todo-card">
      <template #title>
        <div class="card-title-row">
          <span>{{ t('workbench.todo_list_title') }}</span>
          <a-tag v-if="overview" color="blue">{{ t('workbench.todo_count', { count: count('total_todos') }) }}</a-tag>
          <span v-if="overview?.has_more_todos" class="list-hint">{{ t('workbench.todo_has_more') }}</span>
        </div>
      </template>
      <a-table
        :data-source="overview?.todos ?? []"
        :columns="columns"
        :loading="loading"
        row-key="id"
        :pagination="false"
        :locale="{ emptyText: t('workbench.todos_empty') }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'priority'">
            <a-tag :color="priorityColor(record.priority)">{{ t(`workbench.priority.${record.priority}`) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'item'">
            <div class="todo-title">{{ record.title }}</div>
            <div class="todo-description">{{ record.description || '-' }}</div>
          </template>
          <template v-else-if="column.key === 'project'">
            {{ record.project_name || t('workbench.global_scope') }}
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" @click="router.push(record.path)">{{ t('workbench.open_item') }}</a-button>
          </template>
        </template>
      </a-table>
      <div v-if="count('total_todos') > todoPageSize" class="pagination-row">
        <a-pagination
          :current="todoPage"
          :page-size="todoPageSize"
          :total="todoPaginationTotal"
          show-less-items
          @change="handleTodoPageChange"
        />
      </div>
    </a-card>

    <div class="sync-note">
      <span v-if="count('total_todos')">
        {{ t('workbench.todo_page_summary', { page: todoPage, total: count('total_todos') }) }} ·
      </span>
      {{ t('workbench.last_sync', { time: formatTime(overview?.generated_at) }) }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { projectApi, workbenchApi, type ProjectItem, type WorkbenchOverviewItem } from '@/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const projects = ref<ProjectItem[]>([])
const projectId = ref<number | undefined>(toProjectId(route.query.project_id))
const todoPageSize = 50
const maxTodoOffset = 1000
const maxTodoPage = Math.floor(maxTodoOffset / todoPageSize) + 1
const todoPage = ref(toPage(route.query.todo_page, maxTodoPage))
const overview = ref<WorkbenchOverviewItem | null>(null)
const todoPaginationTotal = computed(() => Math.min(count('total_todos'), maxTodoOffset + todoPageSize))
const loading = ref(false)
let refreshTimer: number | undefined
let loadSequence = 0

const metrics = [
  { key: 'pending_reviews', labelKey: 'workbench.metrics.pending_reviews', captionKey: 'workbench.metrics.pending_reviews_caption' },
  { key: 'failed_runs', labelKey: 'workbench.metrics.failed_runs', captionKey: 'workbench.metrics.failed_runs_caption' },
  { key: 'overdue_plans', labelKey: 'workbench.metrics.overdue_plans', captionKey: 'workbench.metrics.overdue_plans_caption' },
  { key: 'device_anomalies', labelKey: 'workbench.metrics.device_anomalies', captionKey: 'workbench.metrics.device_anomalies_caption' },
]

const columns = computed(() => [
  { title: t('workbench.columns.priority'), key: 'priority', width: 100 },
  { title: t('workbench.columns.item'), key: 'item', width: 420 },
  { title: t('workbench.columns.project'), key: 'project', width: 180 },
  { title: t('workbench.columns.created_at'), key: 'created_at', width: 180 },
  { title: t('workbench.columns.action'), key: 'action', width: 110 },
])

function toProjectId(value: unknown) {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

function toPage(value: unknown, maximum: number) {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? Math.min(parsed, maximum) : 1
}

function count(key: string) {
  return overview.value?.counts[key] ?? 0
}

function priorityColor(priority: string) {
  return { high: 'red', medium: 'orange', low: 'blue' }[priority] ?? 'default'
}

function formatTime(value?: string | null) {
  if (!value) return t('workbench.not_available')
  return value.slice(0, 19).replace('T', ' ')
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    message.error(t('workbench.projects_load_failed'))
  }
}

async function loadOverview() {
  const requestSequence = ++loadSequence
  loading.value = true
  try {
    const nextQuery: Record<string, string> = {}
    if (projectId.value) nextQuery.project_id = String(projectId.value)
    if (todoPage.value > 1) nextQuery.todo_page = String(todoPage.value)
    const knownQueryKeys = new Set(['project_id', 'todo_page'])
    const currentQuery: Record<string, string> = {}
    for (const key of knownQueryKeys) {
      const value = route.query[key]
      const normalized = Array.isArray(value) ? value[0] : value
      if (typeof normalized === 'string' && normalized.trim()) currentQuery[key] = normalized
    }
    const queryChanged = Object.keys(route.query).some((key) => !knownQueryKeys.has(key))
      || JSON.stringify(currentQuery) !== JSON.stringify(nextQuery)
    if (queryChanged) {
      await router.replace({ query: nextQuery })
    }
    const result = await workbenchApi.overview({
      project_id: projectId.value,
      todo_limit: todoPageSize,
      todo_offset: Math.min((todoPage.value - 1) * todoPageSize, maxTodoOffset),
      task_limit: 100,
    })
    if (requestSequence === loadSequence) overview.value = result
  } catch {
    if (requestSequence === loadSequence) message.error(t('workbench.load_failed'))
  } finally {
    if (requestSequence === loadSequence) loading.value = false
  }
}

function handleProjectChange() {
  todoPage.value = 1
  loadOverview()
}

function handleTodoPageChange(nextPage: number) {
  todoPage.value = Math.min(Math.max(nextPage, 1), maxTodoPage)
  loadOverview()
}

onMounted(async () => {
  await loadProjects()
  await loadOverview()
  refreshTimer = window.setInterval(loadOverview, 30_000)
})

onBeforeUnmount(() => {
  if (refreshTimer !== undefined) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.workbench-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-heading,
.card-title-row,
.heading-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
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
.todo-description,
.metric-caption,
.sync-note {
  color: var(--c-text-secondary);
}

.subtitle {
  margin: 8px 0 0;
}

.project-select {
  min-width: 180px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
}

.metric-caption {
  display: block;
  margin-top: 5px;
  font-size: 12px;
}

.scope-alert,
.todo-card {
  border-radius: var(--radius-md);
}

.todo-card {
  border: 1px solid var(--c-border);
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}

.list-hint {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.todo-title {
  color: var(--c-text);
  font-weight: 600;
}

.todo-description {
  max-width: 650px;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-note {
  font-size: 12px;
  text-align: right;
}

@media (max-width: 760px) {
  .page-heading,
  .heading-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .project-select {
    width: 100%;
  }
}
</style>
