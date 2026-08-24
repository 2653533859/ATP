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
          @change="loadOverview"
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
        :pagination="{ pageSize: 10, hideOnSinglePage: true }"
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
    </a-card>

    <div class="sync-note">
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
const overview = ref<WorkbenchOverviewItem | null>(null)
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
    const nextQuery = projectId.value ? { project_id: String(projectId.value) } : {}
    if (route.query.project_id !== nextQuery.project_id) {
      await router.replace({ query: nextQuery })
    }
    const result = await workbenchApi.overview({
      project_id: projectId.value,
      todo_limit: 100,
      task_limit: 100,
    })
    if (requestSequence === loadSequence) overview.value = result
  } catch {
    if (requestSequence === loadSequence) message.error(t('workbench.load_failed'))
  } finally {
    if (requestSequence === loadSequence) loading.value = false
  }
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
