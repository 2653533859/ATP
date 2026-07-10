<template>
  <div class="case-detail-page">
    <a-card class="header-card" :bordered="false">
      <div class="page-header">
        <div class="page-header-main">
          <div class="page-header-eyebrow">{{ t('case.detail.title') }}</div>
          <div class="page-header-title-row">
            <h2>{{ detailTitle }}</h2>
            <a-space v-if="caseDetail" wrap size="small">
              <a-tag :color="caseTypeColor(caseDetail.case_type)">{{ caseTypeLabel(caseDetail.case_type) }}</a-tag>
              <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
              <a-tag :color="automationStatusColor(caseDetail.automation_status)">{{ automationStatusLabel(caseDetail.automation_status) }}</a-tag>
              <a-tag :color="statusColor(caseDetail.status)">{{ statusLabel(caseDetail.status) }}</a-tag>
            </a-space>
          </div>
          <p class="page-header-code">{{ detailCode }}</p>
          <p class="page-header-description">{{ detailDescription }}</p>
        </div>

        <div class="page-header-actions">
          <a-space wrap>
            <a-button @click="goBack">{{ t('case.detail.back') }}</a-button>
            <a-button @click="loadCase">{{ t('common.refresh') }}</a-button>
            <a-button :loading="copying" @click="handleCopy">{{ t('case.actions.copy') }}</a-button>
            <a-button :disabled="!caseDetail" @click="openHistory">{{ t('case.actions.history') }}</a-button>
            <a-button v-if="canSubmitReview" @click="handleWorkflow('submitReview')">{{ t('case.actions.submit_review') }}</a-button>
            <a-button v-if="canApprove" @click="handleWorkflow('approve')">{{ t('case.actions.approve') }}</a-button>
            <a-button v-if="canReject" @click="handleWorkflow('reject')">{{ t('case.actions.reject') }}</a-button>
            <a-button v-if="canDeprecate" @click="handleWorkflow('deprecate')">{{ t('case.actions.deprecate') }}</a-button>
            <a-button v-if="canReactivate" @click="handleWorkflow('reactivate')">{{ t('case.actions.reactivate') }}</a-button>
            <a-tooltip :title="caseDetail?.is_ready_for_execution ? t('case.detail.run_tooltip') : t('case.detail.run_disabled_tooltip')">
              <a-button type="primary" :disabled="!caseDetail?.is_ready_for_execution" @click="openRunModal">
                {{ t('case.actions.run') }}
              </a-button>
            </a-tooltip>
          </a-space>
        </div>
      </div>
    </a-card>

    <a-spin :spinning="loading">
      <template v-if="caseDetail">
        <div class="summary-grid">
          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">{{ t('common.project') }}</div>
            <div class="summary-value">{{ projectName }}</div>
            <div class="summary-hint">{{ t('case.detail.current_project') }}</div>
          </a-card>

          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">{{ t('common.module') }}</div>
            <div class="summary-value">{{ moduleName }}</div>
            <div class="summary-hint">{{ t('case.detail.current_module') }}</div>
          </a-card>

          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">{{ t('case.filters.review_status') }}</div>
            <div class="summary-value">
              <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
            </div>
            <div class="summary-hint">{{ t('case.detail.reviewed_at', { time: formatDateTime(caseDetail.reviewed_at) }) }}</div>
          </a-card>

          <a-card class="summary-card" :bordered="false">
            <div class="summary-label">{{ t('case.detail.execution_status') }}</div>
            <div class="summary-value">
              <a-tag :color="executionStatusColor">{{ executionStatusLabel }}</a-tag>
            </div>
            <div class="summary-hint">{{ executionStatusHint }}</div>
          </a-card>
        </div>

        <a-row :gutter="[16, 16]" class="detail-grid">
          <a-col :xs="24" :xl="16">
            <a-card class="detail-card" :title="t('case.detail.basic_info')" :bordered="false">
              <a-descriptions bordered size="small" :column="2">
                <a-descriptions-item :label="t('case.detail.code')">{{ caseDetail.case_code }}</a-descriptions-item>
                <a-descriptions-item :label="t('common.type')">
                  <a-tag :color="caseTypeColor(caseDetail.case_type)">{{ caseTypeLabel(caseDetail.case_type) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('common.project')">{{ projectName }}</a-descriptions-item>
                <a-descriptions-item :label="t('common.module')">{{ moduleName }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.filters.priority')">
                  <a-tag :color="priorityColor(caseDetail.priority)">{{ caseDetail.priority }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('case.filters.level')">{{ caseLevelLabel(caseDetail.case_level) }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.columns.lifecycle')">
                  <a-tag :color="statusColor(caseDetail.status)">{{ statusLabel(caseDetail.status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('case.filters.review_status')">
                  <a-tag :color="reviewStatusColor(caseDetail.review_status)">{{ reviewStatusLabel(caseDetail.review_status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('case.filters.automation_status')">
                  <a-tag :color="automationStatusColor(caseDetail.automation_status)">{{ automationStatusLabel(caseDetail.automation_status) }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.executable')">
                  <a-tag :color="caseDetail.is_ready_for_execution ? 'success' : 'default'">
                    {{ caseDetail.is_ready_for_execution ? t('common.yes') : t('common.no') }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.summary')" :span="2">{{ caseDetail.summary || '-' }}</a-descriptions-item>
                <a-descriptions-item :label="t('common.description')" :span="2">{{ caseDetail.description || '-' }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.tags')" :span="2">
                  <a-space wrap>
                    <a-tag v-for="tag in caseDetail.tags" :key="tag" color="blue">{{ tag }}</a-tag>
                    <span v-if="!caseDetail.tags.length">-</span>
                  </a-space>
                </a-descriptions-item>
                <a-descriptions-item :label="t('common.created_at')">{{ formatDateTime(caseDetail.created_at) }}</a-descriptions-item>
                <a-descriptions-item :label="t('common.updated_at')">{{ formatDateTime(caseDetail.updated_at) }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.creator_id')">{{ caseDetail.creator_id }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.owner_id')">{{ caseDetail.owner_id ?? '-' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="8">
            <a-card class="detail-card" :title="t('case.detail.review_info')" :bordered="false">
              <a-descriptions bordered size="small" :column="1">
                <a-descriptions-item :label="t('case.detail.submitted_at')">{{ formatDateTime(caseDetail.submitted_at) }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.review_time')">{{ formatDateTime(caseDetail.reviewed_at) }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.reviewer')">{{ caseDetail.reviewed_by ?? '-' }}</a-descriptions-item>
                <a-descriptions-item :label="t('case.detail.remarks')">{{ caseDetail.review_comment || '-' }}</a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="12">
            <a-card class="detail-card detail-card--compact" :title="t('case.detail.preconditions')" :bordered="false">
              <template v-if="caseDetail.preconditions.length">
                <div class="condition-tags">
                  <a-tag v-for="item in caseDetail.preconditions" :key="item">{{ item }}</a-tag>
                </div>
              </template>
              <a-empty v-else :description="t('case.detail.no_preconditions')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
            </a-card>
          </a-col>

          <a-col :xs="24" :xl="12">
            <a-card class="detail-card detail-card--compact" :title="t('case.detail.postconditions')" :bordered="false">
              <template v-if="caseDetail.postconditions.length">
                <div class="condition-tags">
                  <a-tag v-for="item in caseDetail.postconditions" :key="item">{{ item }}</a-tag>
                </div>
              </template>
              <a-empty v-else :description="t('case.detail.no_postconditions')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
            </a-card>
          </a-col>

          <a-col :span="24">
            <a-card class="detail-card table-card" :title="t('case.detail.standard_steps')" :bordered="false">
              <a-table
                v-if="caseDetail.steps.length"
                :columns="stepColumns"
                :data-source="caseDetail.steps"
                row-key="id"
                size="small"
                :pagination="false"
                :scroll="{ x: 1000 }"
                :locale="{ emptyText: t('common.no_data') }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'is_key_step'">
                    <a-tag :color="record.is_key_step ? 'red' : 'default'">
                      {{ record.is_key_step ? t('case.detail.key_step') : t('case.detail.normal_step') }}
                    </a-tag>
                  </template>
                </template>
              </a-table>
              <a-empty
                v-else
                :description="t('case.detail.no_standard_steps')"
                :image="Empty.PRESENTED_IMAGE_SIMPLE"
              />
            </a-card>
          </a-col>

          <a-col :span="24">
            <a-card class="detail-card" :title="t('case.detail.execution_config')" :bordered="false">
              <pre class="config-block">{{ prettyConfig }}</pre>
            </a-card>
          </a-col>
        </a-row>
      </template>

      <a-card v-else class="detail-card empty-card" :bordered="false">
        <a-empty :description="t('case.detail.not_found')" />
      </a-card>
    </a-spin>

    <a-modal
      v-model:open="runModalOpen"
      :title="t('case.run_modal_title')"
      :ok-text="t('case.actions.run')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">{{ t('case.run_modal_tip') }}</p>
      <a-select
        v-model:value="(runEnvId as number | undefined)"
        :placeholder="t('case.no_environment')"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="caseId"
      @close="historyOpen = false"
      @rolled="handleRolled"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { caseApi, environmentApi, projectApi } from '@/api'
import type {
  AutomationStatus,
  CaseDetailItem,
  CaseLevel,
  CasePriority,
  CaseStatus,
  CaseType,
  ModuleTreeItem,
  ProjectItem,
  ReviewStatus,
} from '@/api'
import CaseHistoryDrawer from '@/views/case/CaseHistoryDrawer.vue'
import { buildEnvironmentOptions, buildRunDetailLocation, buildRunPayload } from '@/utils/caseExecution'

type WorkflowAction = 'submitReview' | 'approve' | 'reject' | 'deprecate' | 'reactivate'
type ErrorLike = {
  message?: unknown
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const copying = ref(false)
const caseDetail = ref<CaseDetailItem | null>(null)
const projects = ref<ProjectItem[]>([])
const moduleNameMap = ref<Record<number, string>>({})
const historyOpen = ref(false)
const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)

const stepColumns = computed(() => [
  { title: '#', dataIndex: 'step_no', key: 'step_no', width: 70 },
  { title: t('case.detail.step_action'), dataIndex: 'action', key: 'action', width: 220 },
  { title: t('case.detail.test_data'), dataIndex: 'test_data', key: 'test_data', width: 220 },
  { title: t('case.detail.expected_result'), dataIndex: 'expected_result', key: 'expected_result', width: 260 },
  { title: t('common.type'), key: 'is_key_step', width: 100 },
  { title: t('case.detail.remarks'), dataIndex: 'remarks', key: 'remarks', width: 180 },
])

const caseId = computed(() => parsePositiveInt(route.params.caseId))
const projectQueryId = computed(() => parsePositiveInt(route.query.project_id))
const moduleQueryId = computed(() => parsePositiveInt(route.query.module_id))
const backQuery = computed<Record<string, string>>(() => {
  const query: Record<string, string> = {}
  if (projectQueryId.value) {
    query.project_id = String(projectQueryId.value)
  }
  if (moduleQueryId.value) {
    query.module_id = String(moduleQueryId.value)
  }
  return query
})

const projectName = computed(() => {
  if (!projectQueryId.value) {
    return '-'
  }
  return projects.value.find((item) => item.id === projectQueryId.value)?.name ?? t('case.project_fallback', { id: projectQueryId.value })
})

const moduleName = computed(() => {
  if (!caseDetail.value) {
    return '-'
  }
  return moduleNameMap.value[caseDetail.value.module_id] ?? t('case.module_fallback', { id: caseDetail.value.module_id })
})

const detailTitle = computed(() => caseDetail.value?.name || t('case.detail.title'))
const detailCode = computed(() => caseDetail.value?.case_code || t('case.detail.case_fallback', { id: caseId.value ?? '-' }))
const detailDescription = computed(() => {
  const parts: string[] = []
  if (projectName.value !== '-') {
    parts.push(t('case.detail.project_part', { name: projectName.value }))
  }
  if (moduleName.value !== '-') {
    parts.push(t('case.detail.module_part', { name: moduleName.value }))
  }
  if (caseDetail.value?.summary) {
    parts.push(caseDetail.value.summary)
  }
  return parts.length ? parts.join(' | ' ) : t('case.detail.default_description')
})
const executionStatusLabel = computed(() => caseDetail.value?.is_ready_for_execution ? t('case.detail.executable_yes') : t('case.detail.executable_no'))
const executionStatusColor = computed(() => caseDetail.value?.is_ready_for_execution ? 'success' : 'warning')
const executionStatusHint = computed(() => caseDetail.value?.is_ready_for_execution
  ? t('case.detail.execution_ready_hint')
  : t('case.detail.run_disabled_tooltip')
)
const prettyConfig = computed(() => JSON.stringify(caseDetail.value?.config ?? {}, null, 2))
const canSubmitReview = computed(() => !!caseDetail.value && caseDetail.value.status !== 'deprecated' && caseDetail.value.review_status !== 'pending')
const canApprove = computed(() => !!caseDetail.value && caseDetail.value.status !== 'deprecated' && caseDetail.value.review_status === 'pending')
const canReject = computed(() => !!caseDetail.value && caseDetail.value.review_status === 'pending')
const canDeprecate = computed(() => !!caseDetail.value && caseDetail.value.status !== 'deprecated')
const canReactivate = computed(() => !!caseDetail.value && caseDetail.value.status === 'deprecated' && caseDetail.value.review_status === 'approved')

function parsePositiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (Array.isArray(node.children) && node.children.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return fallback
}

function formatDateTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function caseTypeLabel(type: CaseType) {
  return t(`case.types.${type}`)
}

function caseTypeColor(type: CaseType) {
  return {
    api: 'geekblue',
    graphql: 'orange',
    websocket: 'cyan',
    grpc: 'red',
    web: 'purple',
    android: 'green',
  }[type] ?? 'default'
}

function caseLevelLabel(level: CaseLevel) {
  return {
    smoke: t('case.levels.smoke'),
    core: t('case.levels.core'),
    regression: t('case.levels.regression'),
    extended: t('case.levels.extended'),
  }[level]
}

function priorityColor(priority: CasePriority) {
  return {
    P0: 'red',
    P1: 'orange',
    P2: 'gold',
    P3: 'default',
  }[priority]
}

function reviewStatusLabel(status: ReviewStatus) {
  return {
    pending: t('case.review_statuses.pending'),
    approved: t('case.review_statuses.approved'),
    rejected: t('case.review_statuses.rejected'),
  }[status]
}

function reviewStatusColor(status: ReviewStatus) {
  return {
    pending: 'processing',
    approved: 'success',
    rejected: 'error',
  }[status]
}

function statusLabel(status: CaseStatus) {
  return {
    draft: t('case.statuses.draft'),
    active: t('case.statuses.active'),
    deprecated: t('case.statuses.deprecated'),
  }[status]
}

function statusColor(status: CaseStatus) {
  return {
    draft: 'default',
    active: 'success',
    deprecated: 'warning',
  }[status]
}

function automationStatusLabel(status: AutomationStatus) {
  return {
    manual: t('case.automation_statuses.manual'),
    semi_auto: t('case.automation_statuses.semi_auto'),
    auto: t('case.automation_statuses.auto'),
  }[status]
}

function automationStatusColor(status: AutomationStatus) {
  return {
    manual: 'default',
    semi_auto: 'processing',
    auto: 'success',
  }[status]
}

async function loadMeta() {
  if (!projectQueryId.value) {
    projects.value = []
    moduleNameMap.value = {}
    return
  }

  try {
    const [projectList, modules] = await Promise.all([
      projectApi.list(),
      projectApi.getModules(projectQueryId.value),
    ])
    projects.value = projectList
    moduleNameMap.value = flattenModules(modules)
  } catch {
    projects.value = []
    moduleNameMap.value = {}
  }
}

async function loadCase() {
  if (!caseId.value) {
    caseDetail.value = null
    return
  }

  loading.value = true
  try {
    caseDetail.value = await caseApi.get(caseId.value)
  } catch (error: unknown) {
    caseDetail.value = null
    message.error(errorMessage(error, t('case.detail.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

function goBack() {
  void router.push({ name: 'cases', query: backQuery.value })
}

async function handleCopy() {
  if (!caseId.value) {
    return
  }

  copying.value = true
  try {
    const copied = await caseApi.copy(caseId.value)
    message.success(t('case.msg.copied', { code: copied.case_code }))
    void router.replace({ name: 'case-detail', params: { caseId: String(copied.id) }, query: backQuery.value })
    caseDetail.value = copied
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.copy_failed')))
  } finally {
    copying.value = false
  }
}

async function handleWorkflow(action: WorkflowAction) {
  if (!caseId.value) {
    return
  }

  try {
    switch (action) {
      case 'submitReview':
        caseDetail.value = await caseApi.submitReview(caseId.value)
        message.success(t('case.msg.submit_review_done'))
        break
      case 'approve':
        caseDetail.value = await caseApi.approve(caseId.value)
        message.success(t('case.msg.approve_done'))
        break
      case 'reject':
        caseDetail.value = await caseApi.reject(caseId.value)
        message.success(t('case.msg.reject_done'))
        break
      case 'deprecate':
        caseDetail.value = await caseApi.deprecate(caseId.value)
        message.success(t('case.msg.deprecate_done'))
        break
      case 'reactivate':
        caseDetail.value = await caseApi.reactivate(caseId.value)
        message.success(t('case.msg.reactivate_done'))
        break
    }
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.workflow_failed')))
  }
}

function openHistory() {
  historyOpen.value = true
}

async function openRunModal() {
  runEnvId.value = null
  runEnvOptions.value = []
  runModalOpen.value = true

  if (!projectQueryId.value) {
    return
  }

  runEnvLoading.value = true
  try {
    const environments = await environmentApi.list(projectQueryId.value)
    runEnvOptions.value = buildEnvironmentOptions(environments)
  } catch {
    runEnvOptions.value = []
    message.warning(t('case.msg.load_env_failed'))
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  if (!caseId.value) {
    return
  }

  runConfirming.value = true
  try {
    const run = await caseApi.run(caseId.value, buildRunPayload(runEnvId.value))
    runModalOpen.value = false
    message.success(t('case.msg.run_started'))
    void router.push(buildRunDetailLocation(run.id))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.run_failed')))
  } finally {
    runConfirming.value = false
  }
}

async function handleRolled() {
  await loadCase()
}

onMounted(async () => {
  await Promise.all([loadMeta(), loadCase()])
})
</script>

<style scoped>
.case-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-card,
.summary-card,
.detail-card {
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.header-card :deep(.ant-card-body) {
  padding: 20px 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-header-main {
  min-width: 0;
  flex: 1 1 auto;
}

.page-header-eyebrow {
  margin-bottom: 8px;
  color: #1677ff;
  font-size: 13px;
  font-weight: 600;
}

.page-header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.page-header-title-row h2 {
  margin: 0;
  color: #1f1f1f;
}

.page-header-code {
  margin: 8px 0 0;
  color: #1f1f1f;
  font-size: 14px;
  font-weight: 600;
}

.page-header-description {
  margin: 8px 0 0;
  color: #666;
  line-height: 1.6;
}

.page-header-actions {
  flex: 0 0 auto;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card :deep(.ant-card-body) {
  padding: 18px 20px;
}

.summary-label {
  color: #667085;
  font-size: 13px;
}

.summary-value {
  margin-top: 10px;
  color: #1f1f1f;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
}

.summary-hint {
  margin-top: 8px;
  color: #8c8c8c;
  font-size: 12px;
  line-height: 1.5;
}

.detail-card :deep(.ant-card-head) {
  min-height: 54px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-card :deep(.ant-card-head-title) {
  font-weight: 600;
}

.detail-card :deep(.ant-card-body) {
  padding: 18px 20px;
}

.detail-card--compact :deep(.ant-card-body) {
  min-height: 112px;
}

.table-card :deep(.ant-card-body) {
  padding: 0;
}

.table-card :deep(.ant-empty) {
  margin: 40px 0;
}

.condition-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-block {
  margin: 0;
  padding: 16px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  overflow-x: auto;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #1f2937;
}

.empty-card :deep(.ant-card-body) {
  padding: 40px 24px;
}

.run-tip {
  margin-bottom: 12px;
  color: #666;
}

@media (max-width: 1280px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header-actions {
    width: 100%;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
