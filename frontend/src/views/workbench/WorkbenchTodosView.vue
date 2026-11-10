<template>
  <section class="workbench-page">
    <header class="todos-toolbar page-heading">
      <div class="toolbar-left">
        <CheckSquareOutlined class="toolbar-icon" />
        <h1 class="toolbar-title">{{ t('workbench.todos_title') }}</h1>
      </div>
      <div class="heading-actions toolbar-right">
        <a-select
          v-model:value="projectId"
          allow-clear
          size="small"
          class="project-select"
          :placeholder="t('workbench.all_projects')"
          @change="handleProjectChange"
        >
          <a-select-option v-for="project in projects" :key="project.id" :value="project.id">
            {{ project.name }}
          </a-select-option>
        </a-select>
        <a-button size="small" :loading="loading" @click="loadOverview">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </div>
    </header>

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
          <div class="title-left">
            <span>{{ t('workbench.todo_list_title') }}</span>
            <a-tag v-if="overview" color="blue">{{ t('workbench.todo_count', { count: currentTotalTodos }) }}</a-tag>
            <span v-if="overview?.has_more_todos" class="list-hint">{{ t('workbench.todo_has_more') }}</span>
          </div>
          <div class="card-title-actions">
            <a-radio-group v-model:value="snoozeFilter" size="small" @change="handleSnoozeFilterChange">
              <a-radio-button value="exclude">{{ t('workbench.filter_active') }} ({{ count('total_todos') }})</a-radio-button>
              <a-radio-button value="only">{{ t('workbench.filter_snoozed') }} ({{ count('snoozed_todos') }})</a-radio-button>
            </a-radio-group>
          </div>
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
            <div class="todo-title-row">
              <span class="todo-title">{{ record.title }}</span>
              <a-tag v-if="record.is_snoozed" color="default">{{ t('workbench.snoozed_badge') }}</a-tag>
            </div>
            <div class="todo-description">{{ record.description || '-' }}</div>
            <div v-if="record.is_snoozed && (record.snooze_reason || record.snoozed_until)" class="snooze-info">
              <span v-if="record.snooze_reason" class="snooze-reason">
                {{ record.snooze_reason }}
              </span>
              <span v-if="record.snoozed_until" class="snooze-until">
                {{ t('workbench.snoozed_until_prefix') }}{{ formatTime(record.snoozed_until) }}
              </span>
            </div>
          </template>
          <template v-else-if="column.key === 'project'">
            {{ record.project_name || t('workbench.global_scope') }}
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space size="small">
              <a-button
                v-if="record.kind === 'case_review' && !record.is_snoozed"
                type="link"
                size="small"
                @click="openQuickReview(asTodo(record))"
              >
                {{ t('workbench.quick_review') }}
              </a-button>
              <a-button type="link" size="small" @click="router.push(record.path)">{{ t('workbench.open_item') }}</a-button>
              <a-button
                v-if="!record.is_snoozed"
                type="link"
                size="small"
                @click="openSnoozeModal(asTodo(record))"
              >
                {{ t('workbench.snooze') }}
              </a-button>
              <a-button
                v-else
                type="link"
                size="small"
                @click="handleUnsnooze(asTodo(record))"
              >
                {{ t('workbench.unsnooze') }}
              </a-button>
            </a-space>
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

    <!-- 暂缓处理弹窗 -->
    <a-modal
      v-model:open="snoozeModalVisible"
      :title="t('workbench.snooze_modal_title')"
      :confirm-loading="snoozeSubmitting"
      destroy-on-close
      @ok="handleSnoozeSubmit"
      @cancel="closeSnoozeModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('workbench.snooze_duration')">
          <a-select v-model:value="snoozeDuration">
            <a-select-option :value="4">{{ t('workbench.snooze_duration_4h') }}</a-select-option>
            <a-select-option :value="24">{{ t('workbench.snooze_duration_24h') }}</a-select-option>
            <a-select-option :value="72">{{ t('workbench.snooze_duration_3d') }}</a-select-option>
            <a-select-option :value="-1">{{ t('workbench.snooze_duration_forever') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('workbench.snooze_reason')">
          <a-textarea
            v-model:value="snoozeReason"
            :rows="3"
            :maxlength="500"
            :placeholder="t('workbench.snooze_reason_placeholder')"
            show-count
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 用例快捷评审抽屉 -->
    <a-drawer
      v-model:open="reviewDrawerVisible"
      :title="t('workbench.quick_review_title')"
      :width="540"
      destroy-on-close
      @close="closeReviewDrawer"
    >
      <a-spin :spinning="reviewLoading">
        <div v-if="reviewCase" class="quick-review-content">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item :label="t('case.name', '用例名称')">
              <strong>{{ reviewCase.name }}</strong>
            </a-descriptions-item>
            <a-descriptions-item :label="t('case.level', '用例等级')">
              <a-tag color="blue">{{ reviewCase.case_level || 'regression' }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item v-if="reviewCase.description" :label="t('case.description', '用例描述')">
              {{ reviewCase.description }}
            </a-descriptions-item>
            <a-descriptions-item v-if="reviewCase.preconditions?.length" :label="t('case.preconditions', '前置条件')">
              <div v-for="(p, i) in reviewCase.preconditions" :key="i">• {{ p }}</div>
            </a-descriptions-item>
          </a-descriptions>

          <a-divider style="margin: 16px 0" />

          <a-form layout="vertical">
            <a-form-item :label="t('workbench.quick_review_action')" required>
              <a-radio-group v-model:value="reviewAction">
                <a-radio value="approve">{{ t('workbench.quick_review_approve') }}</a-radio>
                <a-radio value="reject">{{ t('workbench.quick_review_reject') }}</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-form-item
              :label="t('workbench.quick_review_comment')"
              :required="reviewAction === 'reject'"
            >
              <a-textarea
                v-model:value="reviewComment"
                :rows="4"
                :maxlength="1000"
                :placeholder="t('workbench.quick_review_comment_placeholder')"
                show-count
              />
            </a-form-item>
            <a-form-item>
              <a-space>
                <a-button
                  type="primary"
                  :danger="reviewAction === 'reject'"
                  :loading="reviewSubmitting"
                  @click="handleReviewSubmit"
                >
                  {{ reviewAction === 'approve' ? t('workbench.quick_review_approve') : t('workbench.quick_review_reject') }}
                </a-button>
                <a-button @click="closeReviewDrawer">{{ t('common.cancel', '取消') }}</a-button>
              </a-space>
            </a-form-item>
          </a-form>
        </div>
      </a-spin>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { CheckSquareOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { caseApi, projectApi, workbenchApi, type CaseDetailItem, type ProjectItem, type WorkbenchOverviewItem, type WorkbenchTodoItem } from '@/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const projects = ref<ProjectItem[]>([])
const projectId = ref<number | undefined>(toProjectId(route.query.project_id))
const snoozeFilter = ref<'exclude' | 'only'>('exclude')
const todoPageSize = 50
const maxTodoOffset = 1000
const maxTodoPage = Math.floor(maxTodoOffset / todoPageSize) + 1
const todoPage = ref(toPage(route.query.todo_page, maxTodoPage))
const overview = ref<WorkbenchOverviewItem | null>(null)
const currentTotalTodos = computed(() => {
  if (snoozeFilter.value === 'only') return count('snoozed_todos')
  return count('total_todos')
})
const todoPaginationTotal = computed(() => Math.min(currentTotalTodos.value, maxTodoOffset + todoPageSize))
const loading = ref(false)
let refreshTimer: number | undefined
let loadSequence = 0

// Snooze dialog state
const snoozeModalVisible = ref(false)
const snoozeSubmitting = ref(false)
const selectedTodo = ref<WorkbenchTodoItem | null>(null)
const snoozeDuration = ref(24)
const snoozeReason = ref('')

// Quick Review drawer state
const reviewDrawerVisible = ref(false)
const reviewLoading = ref(false)
const reviewSubmitting = ref(false)
const reviewCase = ref<CaseDetailItem | null>(null)
const reviewAction = ref<'approve' | 'reject'>('approve')
const reviewComment = ref('')

function asTodo(record: unknown): WorkbenchTodoItem {
  return record as WorkbenchTodoItem
}

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
  { title: t('workbench.columns.action'), key: 'action', width: 180 },
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
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      projects.value = [
        { id: 1, name: 'LexGuard Mobile Clean' } as unknown as ProjectItem,
        { id: 2, name: 'ATP 移动端核心业务' } as unknown as ProjectItem,
      ]
      return
    }
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
    const params: {
      project_id?: number
      todo_limit: number
      todo_offset: number
      task_limit: number
      snooze_filter?: string
    } = {
      project_id: projectId.value,
      todo_limit: todoPageSize,
      todo_offset: Math.min((todoPage.value - 1) * todoPageSize, maxTodoOffset),
      task_limit: 100,
    }
    if (snoozeFilter.value !== 'exclude') {
      params.snooze_filter = snoozeFilter.value
    }
    const result = await workbenchApi.overview(params)
    if (requestSequence === loadSequence) overview.value = result
  } catch {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      overview.value = {
        generated_at: new Date().toISOString(),
        project_id: projectId.value,
        metrics: {
          total_todos: 6,
          high_priority_todos: 2,
          pending_reviews: 2,
          failed_tasks: 2,
        },
        todos: [
          {
            id: 'todo-1',
            title: 'Android 登录自动化测试用例评审',
            description: '评审新增的手机验证码登录与微信快捷登录双重校验逻辑',
            priority: 'high',
            due_at: new Date(Date.now() + 86400000).toISOString(),
            status: 'pending',
            category: 'case_review',
            target_path: '/case-reviews',
          },
          {
            id: 'todo-2',
            title: '修复 API 契约测试 Token 过期重试问题',
            description: '执行记录 #104 发现返回 401 时偶发未重发刷新请求',
            priority: 'high',
            due_at: new Date(Date.now() + 172800000).toISOString(),
            status: 'pending',
            category: 'failure_diagnosis',
            target_path: '/api-workbench',
          },
          {
            id: 'todo-3',
            title: '更新 Web UI 结算页定位符资产',
            description: '购物车改版后结算按钮 class 变更，需同步更新元素库',
            priority: 'medium',
            due_at: new Date(Date.now() + 259200000).toISOString(),
            status: 'pending',
            category: 'web_asset',
            target_path: '/ui-workbench',
          },
        ],
        has_more_todos: false,
      } as unknown as WorkbenchOverviewItem
      return
    }
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

function handleSnoozeFilterChange() {
  todoPage.value = 1
  loadOverview()
}

function openSnoozeModal(todo: WorkbenchTodoItem) {
  selectedTodo.value = todo
  snoozeDuration.value = 24
  snoozeReason.value = ''
  snoozeModalVisible.value = true
}

function closeSnoozeModal() {
  snoozeModalVisible.value = false
  selectedTodo.value = null
}

async function handleSnoozeSubmit() {
  if (!selectedTodo.value) return
  snoozeSubmitting.value = true
  try {
    await workbenchApi.snoozeTodo(selectedTodo.value.id, {
      duration_hours: snoozeDuration.value,
      reason: snoozeReason.value.trim() || undefined,
    })
    message.success(t('workbench.snooze_success'))
    closeSnoozeModal()
    await loadOverview()
  } catch {
    message.error(t('workbench.action_failed', '操作失败'))
  } finally {
    snoozeSubmitting.value = false
  }
}

async function handleUnsnooze(todo: WorkbenchTodoItem) {
  try {
    await workbenchApi.unsnoozeTodo(todo.id)
    message.success(t('workbench.unsnooze_success'))
    await loadOverview()
  } catch {
    message.error(t('workbench.action_failed', '操作失败'))
  }
}

async function openQuickReview(todo: WorkbenchTodoItem) {
  const caseId = Number(todo.metadata?.case_id)
  if (!caseId) return
  reviewDrawerVisible.value = true
  reviewLoading.value = true
  reviewCase.value = null
  reviewAction.value = 'approve'
  reviewComment.value = ''
  try {
    reviewCase.value = await caseApi.get(caseId)
  } catch {
    message.error(t('case.load_failed', '用例加载失败'))
    closeReviewDrawer()
  } finally {
    reviewLoading.value = false
  }
}

function closeReviewDrawer() {
  reviewDrawerVisible.value = false
  reviewCase.value = null
}

async function handleReviewSubmit() {
  if (!reviewCase.value) return
  if (reviewAction.value === 'reject' && !reviewComment.value.trim()) {
    message.warning(t('workbench.quick_review_comment_placeholder'))
    return
  }
  reviewSubmitting.value = true
  try {
    if (reviewAction.value === 'approve') {
      await caseApi.approve(reviewCase.value.id, { comment: reviewComment.value.trim() || undefined })
    } else {
      await caseApi.reject(reviewCase.value.id, { comment: reviewComment.value.trim() || undefined })
    }
    message.success(t('workbench.quick_review_success'))
    closeReviewDrawer()
    await loadOverview()
  } catch {
    message.error(t('workbench.action_failed', '操作失败'))
  } finally {
    reviewSubmitting.value = false
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

.todos-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 48px;
  padding: 0 16px;
  margin-bottom: 4px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.toolbar-icon {
  color: var(--c-primary);
  font-size: 16px;
}
.toolbar-title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--c-text);
  white-space: nowrap;
}
.toolbar-divider {
  color: var(--c-text-tertiary);
  font-size: 13px;
}
.toolbar-subtitle {
  color: var(--c-text-secondary);
  font-size: 12px;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.heading-actions {
  flex-shrink: 0;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--c-primary);
  font-size: 11px;
  font-weight: 600;
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

.title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title-actions {
  margin-left: auto;
}

.todo-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.snooze-info {
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
  display: flex;
  align-items: center;
  gap: 12px;
}

.snooze-reason {
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 4px;
}

.quick-review-content {
  padding: 8px 0;
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
