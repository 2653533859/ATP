<template>
  <div class="page-shell case-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ t('case.title') }}</h2>
        <div class="page-subtitle">{{ t('case.subtitle') }}</div>
      </div>
      <a-space wrap>
        <a-select
          v-model:value="selectedProjectId"
          :placeholder="t('case.select_project')"
          style="width: 240px"
          :options="projectOptions"
          allow-clear
          @change="handleProjectChange"
        />
        <a-button @click="router.push({ name: 'projects' })">{{ t('case.project_management') }}</a-button>
        <a-button :disabled="!selectedProjectId" @click="refreshCurrentProject">{{ t('common.refresh') }}</a-button>
      </a-space>
    </div>

    <template v-if="selectedProjectId">
      <a-row :gutter="[16, 16]" class="summary-row">
        <a-col :xs="24" :sm="6">
          <a-card>
            <a-statistic :title="t('case.stats.project')" :value="currentProjectName" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="6">
          <a-card>
            <a-statistic :title="t('case.stats.module_count')" :value="moduleCount" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="6">
          <a-card>
            <a-statistic :title="t('case.stats.visible_cases')" :value="filteredCases.length" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="6">
          <a-card>
            <a-statistic :title="t('case.stats.pending_reviews')" :value="pendingReviewCount" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="6">
          <a-card>
            <a-statistic :title="t('case.stats.flaky_cases')" :value="flakyCaseCount" />
          </a-card>
        </a-col>
      </a-row>

      <div class="workspace">
        <div class="side-panel">
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            show-reset
            :reset-disabled="!selectedModuleId"
            @select="onModuleSelect"
            @reset="clearModuleFilter"
          />
        </div>

        <div class="main-panel">
          <a-card class="toolbar-card" :bordered="false">
            <div class="toolbar">
              <div class="toolbar-main">
                <a-space wrap>
                <a-input-search
                  v-model:value="keyword"
                  :placeholder="t('case.search_placeholder')"
                  style="width: 260px"
                  allow-clear
                  @search="handleSearch"
                />
                <a-select
                  v-model:value="filterType"
                  :placeholder="t('case.filters.type')"
                  allow-clear
                  style="width: 130px"
                  :options="caseTypeOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterPriority"
                  :placeholder="t('case.filters.priority')"
                  allow-clear
                  style="width: 120px"
                  :options="priorityOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterLevel"
                  :placeholder="t('case.filters.level')"
                  allow-clear
                  style="width: 140px"
                >
                  <a-select-option value="smoke">{{ t('case.levels.smoke') }}</a-select-option>
                  <a-select-option value="core">{{ t('case.levels.core') }}</a-select-option>
                  <a-select-option value="regression">{{ t('case.levels.regression') }}</a-select-option>
                  <a-select-option value="extended">{{ t('case.levels.extended') }}</a-select-option>
                </a-select>
                <a-select
                  v-model:value="filterStatus"
                  :placeholder="t('case.filters.status')"
                  allow-clear
                  style="width: 120px"
                  :options="statusOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterReviewStatus"
                  :placeholder="t('case.filters.review_status')"
                  allow-clear
                  style="width: 140px"
                  :options="reviewStatusOptions"
                  @change="loadCases"
                />
                <a-select
                  v-model:value="filterAutomationStatus"
                  :placeholder="t('case.filters.automation_status')"
                  allow-clear
                  style="width: 140px"
                  :options="automationStatusOptions"
                  @change="loadCases"
                />
                <a-button @click="handleSearch">{{ t('common.search') }}</a-button>
                <a-button @click="handleResetFilters">{{ t('common.reset') }}</a-button>
              </a-space>
              <div v-if="activeFilterTags.length" class="active-filter-row">
                <span class="active-filter-label">{{ t('case.active_filters') }}</span>
                <a-tag
                  v-for="tag in activeFilterTags"
                  :key="tag.key"
                  closable
                  @close.prevent="clearFilter(tag.key)"
                >
                  {{ tag.label }}
                </a-tag>
                <a-button size="small" type="link" @click="handleResetFilters">{{ t('case.clear_filters') }}</a-button>
              </div>
              </div>

              <div class="toolbar-actions">
                <a-space wrap>
                <a-tag color="blue">
                  {{ t('case.current_module', { name: selectedModuleId ? activeModuleName : t('common.all') }) }}
                </a-tag>
                <a-dropdown :disabled="!selectedModuleId || !canModifyCases">
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="api" @click="openCreate('api')">{{ t('case.types.api') }}</a-menu-item>
                      <a-menu-item key="graphql" @click="openCreate('graphql')">{{ t('case.types.graphql') }}</a-menu-item>
                      <a-menu-item key="websocket" @click="openCreate('websocket')">{{ t('case.types.websocket') }}</a-menu-item>
                      <a-menu-item key="grpc" @click="openCreate('grpc')">{{ t('case.types.grpc') }}</a-menu-item>
                      <a-menu-item key="web" @click="openCreate('web')">{{ t('case.types.web') }}</a-menu-item>
                      <a-menu-item key="android" @click="openCreate('android')">{{ t('case.types.android') }}</a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="primary" :disabled="!selectedModuleId || !canModifyCases">
                    <PlusOutlined /> {{ t('case.new_case') }} <DownOutlined />
                  </a-button>
                </a-dropdown>
                <a-tooltip :title="caseCreateDisabledTip">
                  <a-button :disabled="!selectedModuleId || !canModifyCases" @click="aiDrawerOpen = true">
                    <ThunderboltOutlined /> {{ t('case.ai_generate') }}
                  </a-button>
                </a-tooltip>
              </a-space>
              </div>
            </div>
          </a-card>

          <a-card class="table-card" :bordered="false">
            <BatchOperationBar :selected-count="selectedRowKeys.length" @cancel="selectedRowKeys = []">
              <a-button size="small" @click="handleBatchExport">{{ t('case.export_csv') }}</a-button>
              <a-button size="small" @click="handleBatchExportZip">{{ t('case.export_zip') }}</a-button>
              <a-button size="small" :disabled="!canModifyCases" @click="openBatchMove">
                {{ t('case.batch_move') }}
              </a-button>
              <a-popconfirm
                :title="t('case.confirm_batch_delete', { count: selectedRowKeys.length })"
                :ok-text="t('common.delete')"
                :cancel-text="t('common.cancel')"
                @confirm="handleBatchDelete"
              >
                <a-button size="small" danger :disabled="!canModifyCases">{{ t('case.batch_delete') }}</a-button>
              </a-popconfirm>
            </BatchOperationBar>
            <div class="batch-bar" style="margin-bottom: 12px">
              <span style="color: var(--c-text-tertiary)">{{ t('case.import_zip_label', { module: activeModuleName }) }}</span>
              <a-button size="small" :disabled="!canModifyCases" @click="handleDownloadImportTemplate">
                {{ t('case.import_template') }}
              </a-button>
              <a-upload
                :show-upload-list="false"
                :before-upload="handleBatchImportBeforeUpload"
                accept=".zip"
                :disabled="!selectedModuleId || !canModifyCases"
              >
                <a-button size="small" :loading="importPreviewLoading" :disabled="!selectedModuleId || !canModifyCases">
                  {{ t('case.import_zip') }}
                </a-button>
              </a-upload>
            </div>
            <a-table
              :columns="columns"
              :data-source="filteredCases"
              :loading="loading"
              row-key="id"
              size="middle"
              :pagination="{ pageSize: 20, showSizeChanger: true }"
              :scroll="cases.length ? { x: 1500 } : undefined"
              :row-selection="{ selectedRowKeys, onChange: (keys: (string | number)[]) => (selectedRowKeys = keys as number[]) }"
            >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <div class="case-name-cell">
                  <a-button type="link" class="case-link" @click="openDetail(record.id)">
                    {{ record.name }}
                  </a-button>
                  <div class="case-summary">
                    {{ record.case_code }} ｜ {{ record.summary || t('case.no_summary') }}
                  </div>
                  <div v-if="record.tags.length" class="case-tags">
                    <a-tag v-for="tag in record.tags.slice(0, 3)" :key="tag" color="blue">
                      {{ tag }}
                    </a-tag>
                    <a-tag v-if="record.tags.length > 3">+{{ record.tags.length - 3 }}</a-tag>
                  </div>
                </div>
              </template>

              <template v-else-if="column.key === 'module'">
                <span>{{ moduleNameMap[record.module_id] ?? t('case.module_fallback', { id: record.module_id }) }}</span>
              </template>

              <template v-else-if="column.key === 'case_type'">
                <a-tag :color="caseTypeColor(record.case_type)">{{ caseTypeLabel(record.case_type) }}</a-tag>
              </template>

              <template v-else-if="column.key === 'priority'">
                <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
              </template>

              <template v-else-if="column.key === 'case_level'">
                <a-tag>{{ caseLevelLabel(record.case_level) }}</a-tag>
              </template>

              <template v-else-if="column.key === 'review_status'">
                <div class="review-cell">
                  <a-tag :color="reviewStatusColor(record.review_status)">
                    {{ reviewStatusLabel(record.review_status) }}
                  </a-tag>
                  <a-space v-if="record.review_status === 'pending'" size="small">
                    <a-button type="link" size="small" :disabled="!canApproveCases" @click="handleWorkflow(record, 'approve')">
                      {{ t('case.actions.approve') }}
                    </a-button>
                    <a-button type="link" size="small" danger :disabled="!canApproveCases" @click="handleWorkflow(record, 'reject')">
                      {{ t('case.actions.reject') }}
                    </a-button>
                  </a-space>
                </div>
              </template>

              <template v-else-if="column.key === 'status'">
                <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
              </template>

              <template v-else-if="column.key === 'automation_status'">
                <a-tag :color="automationStatusColor(record.automation_status)">
                  {{ automationStatusLabel(record.automation_status) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'stability'">
                <a-tooltip :title="flakyTooltip(record)">
                  <a-tag :color="record.flaky_stats?.is_flaky ? 'volcano' : 'green'">
                    {{ record.flaky_stats?.is_flaky ? t('case.flaky.flaky') : t('case.flaky.stable') }}
                  </a-tag>
                </a-tooltip>
              </template>

              <template v-else-if="column.key === 'updated_at'">
                {{ formatDateTime(record.updated_at) }}
              </template>

              <template v-else-if="column.key === 'action'">
                <a-space wrap size="small">
                  <a-button type="link" size="small" @click="openDetail(record.id)">{{ t('case.actions.detail') }}</a-button>
                  <a-tooltip :title="canModifyCases ? t('case.actions.edit') : t('case.msg.read_only_role')">
                    <a-button type="link" size="small" :disabled="!canModifyCases" @click="openEdit(record)">{{ t('case.actions.edit') }}</a-button>
                  </a-tooltip>
                  <a-tooltip :title="runDisabledTip(record)">
                    <a-button
                      type="link"
                      size="small"
                      :loading="runningId === record.id"
                      :disabled="!record.is_ready_for_execution || !canRunCases"
                      @click="handleRun(record)"
                    >
                      {{ t('case.actions.run') }}
                    </a-button>
                  </a-tooltip>
                  <a-dropdown>
                    <a-button type="link" size="small">
                      {{ t('common.more') }} <DownOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item key="copy" :disabled="!canModifyCases" @click="handleCopy(record.id)">{{ t('case.actions.copy') }}</a-menu-item>
                        <a-menu-item key="history" @click="openHistory(record.id)">
                          <HistoryOutlined /> {{ t('case.actions.history') }}
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item
                          v-if="canSubmitReview(record)"
                          key="submit-review"
                          @click="handleWorkflow(record, 'submitReview')"
                        >
                          {{ t('case.actions.submit_review') }}
                        </a-menu-item>
                        <a-menu-item
                          v-if="canApprove(record)"
                          key="approve"
                          @click="handleWorkflow(record, 'approve')"
                        >
                          {{ t('case.actions.approve') }}
                        </a-menu-item>
                        <a-menu-item
                          v-if="canReject(record)"
                          key="reject"
                          @click="handleWorkflow(record, 'reject')"
                        >
                          {{ t('case.actions.reject') }}
                        </a-menu-item>
                        <a-menu-item
                          v-if="canDeprecate(record)"
                          key="deprecate"
                          @click="handleWorkflow(record, 'deprecate')"
                        >
                          {{ t('case.actions.deprecate') }}
                        </a-menu-item>
                        <a-menu-item
                          v-if="canReactivate(record)"
                          key="reactivate"
                          @click="handleWorkflow(record, 'reactivate')"
                        >
                          {{ t('case.actions.reactivate') }}
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item key="delete" :disabled="!canModifyCases" @click="confirmDelete(record)">{{ t('case.actions.delete') }}</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-space>
              </template>
            </template>
          </a-table>
          </a-card>
        </div>
      </div>
    </template>

    <a-result
      v-else
      status="info"
      :title="t('case.select_project_result')"
      :sub-title="t('case.select_project_subtitle')"
    />

    <CaseFormDrawer
      :open="drawerOpen"
      :module-id="selectedModuleId"
      :project-id="selectedProjectId"
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
      :title="t('case.run_modal_title')"
      :ok-text="t('case.actions.run')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">{{ t('case.run_modal_tip') }}</p>
      <a-select
        v-model:value="runEnvId"
        :placeholder="t('case.no_environment')"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <a-modal
      v-model:open="batchMoveOpen"
      :title="t('case.batch_move_title')"
      :ok-text="t('case.confirm_move')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="batchMoveLoading"
      @ok="submitBatchMove"
    >
      <p class="run-tip">{{ t('case.batch_move_tip', { count: selectedRowKeys.length }) }}</p>
      <a-select
        v-model:value="batchMoveTargetId"
        :placeholder="t('case.select_target_module')"
        style="width: 100%"
        :options="moduleSelectOptions"
        show-search
        :filter-option="filterModuleOption"
      />
    </a-modal>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="historyCaseId"
      @close="historyOpen = false"
      @rolled="handleHistoryRolled"
    />

    <AIGenerateDrawer
      :open="aiDrawerOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      @close="aiDrawerOpen = false"
      @saved="onSaved"
    />

    <a-modal
      v-model:open="importPreviewOpen"
      :title="t('case.import_preview.title')"
      :ok-text="t('case.import_preview.confirm')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="importConfirming"
      :ok-button-props="{ disabled: !importPreview?.valid_count }"
      width="720px"
      @ok="confirmBatchImport"
    >
      <template v-if="importPreview">
        <a-alert
          class="import-preview-alert"
          :type="importPreview.invalid_count ? 'warning' : 'success'"
          show-icon
          :message="t('case.import_preview.summary', {
            total: importPreview.total,
            valid: importPreview.valid_count,
            invalid: importPreview.invalid_count,
          })"
        />
        <a-table
          size="small"
          :pagination="false"
          :columns="importPreviewColumns"
          :data-source="importPreview.preview_cases"
          row-key="row"
          :scroll="{ x: 620 }"
        />
        <div v-if="importPreview.errors.length" class="import-error-list">
          <div class="import-error-title">{{ t('case.import_preview.errors') }}</div>
          <a-alert
            v-for="error in importPreview.errors.slice(0, 8)"
            :key="error"
            type="error"
            show-icon
            :message="error"
          />
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { DownOutlined, HistoryOutlined, PlusOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { caseApi, environmentApi, projectApi } from '@/api'
import type {
  AutomationStatus,
  CaseLevel,
  CasePriority,
  CaseQueryParams,
  CaseStatus,
  CaseSummaryItem,
  CaseType,
  ModuleTreeItem,
  ProjectItem,
  ReviewStatus,
} from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import WebCaseDrawer from '@/views/case/WebCaseDrawer.vue'
import AndroidCaseDrawer from '@/views/case/AndroidCaseDrawer.vue'
import CaseHistoryDrawer from '@/views/case/CaseHistoryDrawer.vue'
import AIGenerateDrawer from '@/views/case/AIGenerateDrawer.vue'
import BatchOperationBar from '@/components/common/BatchOperationBar.vue'
import { canEditProjectAssets, hasAnyRole } from '@/utils/permissions'
import {
  buildCaseDetailLocation,
  buildCasesQuery,
  readCaseRouteSelection,
} from '@/utils/caseNavigation'
import { buildEnvironmentOptions, buildRunDetailLocation, buildRunPayload } from '@/utils/caseExecution'
import { useAuthStore } from '@/stores/auth'

type WorkflowAction = 'submitReview' | 'approve' | 'reject' | 'deprecate' | 'reactivate'
type SelectOption = { label?: string; value?: number }
type FilterKey = 'keyword' | 'type' | 'priority' | 'level' | 'status' | 'review_status' | 'automation_status'
type FilterTag = { key: FilterKey; label: string }
type ImportPreview = {
  total: number
  valid_count: number
  invalid_count: number
  preview_cases: Array<{ row: number; name: string; case_type: string; priority: string; step_count: number }>
  errors: string[]
}
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
const auth = useAuthStore()
const { t } = useI18n()

const caseTypeOptions = computed<Array<{ label: string; value: CaseType }>>(() => [
  { label: t('case.types.api'), value: 'api' },
  { label: t('case.types.graphql'), value: 'graphql' },
  { label: t('case.types.websocket'), value: 'websocket' },
  { label: t('case.types.grpc'), value: 'grpc' },
  { label: t('case.types.web'), value: 'web' },
  { label: t('case.types.android'), value: 'android' },
])

const priorityOptions: Array<{ label: string; value: CasePriority }> = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

const statusOptions = computed<Array<{ label: string; value: CaseStatus }>>(() => [
  { label: t('case.statuses.draft'), value: 'draft' },
  { label: t('case.statuses.active'), value: 'active' },
  { label: t('case.statuses.deprecated'), value: 'deprecated' },
])

const reviewStatusOptions = computed<Array<{ label: string; value: ReviewStatus }>>(() => [
  { label: t('case.review_statuses.pending'), value: 'pending' },
  { label: t('case.review_statuses.approved'), value: 'approved' },
  { label: t('case.review_statuses.rejected'), value: 'rejected' },
])

const automationStatusOptions = computed<Array<{ label: string; value: AutomationStatus }>>(() => [
  { label: t('case.automation_statuses.manual'), value: 'manual' },
  { label: t('case.automation_statuses.semi_auto'), value: 'semi_auto' },
  { label: t('case.automation_statuses.auto'), value: 'auto' },
])

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(null)
const moduleNameMap = ref<Record<number, string>>({})
const cases = ref<CaseSummaryItem[]>([])
const loading = ref(false)
const selectedModuleId = ref<number | null>(null)
const keyword = ref('')
const filterType = ref<CaseType | undefined>(undefined)
const filterPriority = ref<CasePriority | undefined>(undefined)
const filterLevel = ref<CaseLevel | undefined>(undefined)
const filterStatus = ref<CaseStatus | undefined>(undefined)
const filterReviewStatus = ref<ReviewStatus | undefined>(undefined)
const filterAutomationStatus = ref<AutomationStatus | undefined>(undefined)
const drawerOpen = ref(false)
const editingCase = ref<CaseSummaryItem | null>(null)
const createCaseType = ref<CaseType>('api')
const webDrawerOpen = ref(false)
const webEditingCase = ref<CaseSummaryItem | null>(null)
const androidDrawerOpen = ref(false)
const androidEditingCase = ref<CaseSummaryItem | null>(null)
const runningId = ref<number | null>(null)
const selectedRowKeys = ref<number[]>([])
const batchMoveOpen = ref(false)
const batchMoveTargetId = ref<number | null>(null)
const batchMoveLoading = ref(false)
const historyOpen = ref(false)
const historyCaseId = ref<number | null>(null)
const aiDrawerOpen = ref(false)
const importPreviewOpen = ref(false)
const importPreviewLoading = ref(false)
const importConfirming = ref(false)
const pendingImportFile = ref<File | null>(null)
const importPreview = ref<ImportPreview | null>(null)

const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const pendingRunCase = ref<CaseSummaryItem | null>(null)

const columns = computed(() => [
  { title: t('case.columns.case'), key: 'name', width: 320 },
  { title: t('case.columns.module'), key: 'module', width: 160 },
  { title: t('case.columns.type'), key: 'case_type', width: 110 },
  { title: t('case.columns.priority'), key: 'priority', width: 100 },
  { title: t('case.columns.level'), key: 'case_level', width: 120 },
  { title: t('case.columns.review_status'), key: 'review_status', width: 120 },
  { title: t('case.columns.lifecycle'), key: 'status', width: 120 },
  { title: t('case.columns.automation'), key: 'automation_status', width: 130 },
  { title: t('case.columns.stability'), key: 'stability', width: 120 },
  { title: t('case.columns.updated_at'), key: 'updated_at', width: 180 },
  { title: t('case.columns.action'), key: 'action', width: 280, fixed: 'right' as const },
])

const importPreviewColumns = computed(() => [
  { title: t('case.import_preview.columns.row'), dataIndex: 'row', key: 'row', width: 80 },
  { title: t('case.import_preview.columns.name'), dataIndex: 'name', key: 'name', width: 260 },
  { title: t('case.import_preview.columns.type'), dataIndex: 'case_type', key: 'case_type', width: 120 },
  { title: t('case.import_preview.columns.priority'), dataIndex: 'priority', key: 'priority', width: 100 },
  { title: t('case.import_preview.columns.steps'), dataIndex: 'step_count', key: 'step_count', width: 100 },
])

const projectOptions = computed(() =>
  projects.value.map((project) => ({ label: project.name, value: project.id })),
)

const currentProjectName = computed(() =>
  projects.value.find((project) => project.id === selectedProjectId.value)?.name ?? '-',
)

const moduleCount = computed(() => Object.keys(moduleNameMap.value).length)

const activeModuleName = computed(() =>
  selectedModuleId.value ? (moduleNameMap.value[selectedModuleId.value] ?? t('case.module_fallback', { id: selectedModuleId.value })) : t('common.all'),
)

const filteredCases = computed(() =>
  cases.value.filter((testCase) => !filterLevel.value || testCase.case_level === filterLevel.value),
)

const pendingReviewCount = computed(() =>
  filteredCases.value.filter((testCase) => testCase.review_status === 'pending').length,
)

const flakyCaseCount = computed(() =>
  filteredCases.value.filter((testCase) => testCase.flaky_stats?.is_flaky).length,
)

const canModifyCases = computed(() => canEditProjectAssets(auth.user?.role))
const canApproveCases = computed(() => canEditProjectAssets(auth.user?.role))
const canRunCases = computed(() => hasAnyRole(auth.user?.role, ['admin', 'engineer', 'tester']))
const caseCreateDisabledTip = computed(() => {
  if (!canModifyCases.value) return t('case.msg.read_only_role')
  if (!selectedModuleId.value) return t('case.msg.select_module_first')
  return t('case.new_case')
})

const activeFilterTags = computed<FilterTag[]>(() => {
  const tags: FilterTag[] = []
  const keywordText = keyword.value.trim()
  if (keywordText) tags.push({ key: 'keyword', label: t('case.filter_tags.keyword', { value: keywordText }) })
  if (filterType.value) tags.push({ key: 'type', label: t('case.filter_tags.type', { value: caseTypeLabel(filterType.value) }) })
  if (filterPriority.value) tags.push({ key: 'priority', label: t('case.filter_tags.priority', { value: filterPriority.value }) })
  if (filterLevel.value) tags.push({ key: 'level', label: t('case.filter_tags.level', { value: caseLevelLabel(filterLevel.value) }) })
  if (filterStatus.value) tags.push({ key: 'status', label: t('case.filter_tags.status', { value: statusLabel(filterStatus.value) }) })
  if (filterReviewStatus.value) {
    tags.push({ key: 'review_status', label: t('case.filter_tags.review_status', { value: reviewStatusLabel(filterReviewStatus.value) }) })
  }
  if (filterAutomationStatus.value) {
    tags.push({ key: 'automation_status', label: t('case.filter_tags.automation_status', { value: automationStatusLabel(filterAutomationStatus.value) }) })
  }
  return tags
})

function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (Array.isArray(node.children) && node.children.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function filterModuleOption(input: string, option?: SelectOption) {
  return (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
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

const moduleSelectOptions = computed(() =>
  Object.entries(moduleNameMap.value).map(([id, name]) => ({
    value: Number(id),
    label: name,
  })),
)

function formatDateTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function caseTypeLabel(type: CaseType) {
  return caseTypeOptions.value.find((item) => item.value === type)?.label ?? type
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

function flakyTooltip(testCase: CaseSummaryItem) {
  const stats = testCase.flaky_stats
  if (!stats || stats.total_runs === 0) return t('case.flaky.no_runs')
  return t('case.flaky.tooltip', {
    total: stats.total_runs,
    passed: stats.passed_runs,
    failed: stats.failed_runs + stats.error_runs,
    rate: stats.failure_rate,
  })
}

function canSubmitReview(testCase: CaseSummaryItem) {
  return canModifyCases.value && testCase.status !== 'deprecated' && testCase.review_status !== 'pending'
}

function canApprove(testCase: CaseSummaryItem) {
  return canApproveCases.value && testCase.status !== 'deprecated' && testCase.review_status === 'pending'
}

function canReject(testCase: CaseSummaryItem) {
  return canApproveCases.value && testCase.review_status === 'pending'
}

function canDeprecate(testCase: CaseSummaryItem) {
  return canModifyCases.value && testCase.status !== 'deprecated'
}

function canReactivate(testCase: CaseSummaryItem) {
  return canModifyCases.value && testCase.status === 'deprecated' && testCase.review_status === 'approved'
}

function runDisabledTip(testCase: CaseSummaryItem) {
  if (!canRunCases.value) return t('case.msg.read_only_role')
  return testCase.is_ready_for_execution ? t('case.actions.run') : t('case.detail.run_disabled_tooltip')
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.load_projects_failed')))
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
  } catch (error: unknown) {
    moduleNameMap.value = {}
    message.error(errorMessage(error, t('case.msg.load_modules_failed')))
  }
}

async function loadCases() {
  if (!selectedProjectId.value) {
    cases.value = []
    return
  }

  loading.value = true
  try {
    const params: CaseQueryParams = {
      project_id: selectedProjectId.value,
      module_id: selectedModuleId.value ?? undefined,
      case_type: filterType.value,
      priority: filterPriority.value,
      status: filterStatus.value,
      review_status: filterReviewStatus.value,
      automation_status: filterAutomationStatus.value,
      keyword: keyword.value.trim() || undefined,
    }
    cases.value = await caseApi.list(params)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.load_cases_failed')))
    cases.value = []
  } finally {
    loading.value = false
  }
}

function syncRoute() {
  const query = buildCasesQuery({
    projectId: selectedProjectId.value,
    moduleId: selectedModuleId.value,
    reviewStatus: filterReviewStatus.value,
  })
  const {
    projectId: currentProjectId,
    moduleId: currentModuleId,
    reviewStatus: currentReviewStatus,
  } = readCaseRouteSelection(route)
  if (
    currentProjectId === selectedProjectId.value
    && currentModuleId === selectedModuleId.value
    && currentReviewStatus === filterReviewStatus.value
  ) {
    return
  }

  void router.replace({ name: 'cases', query })
}

async function applyRouteSelection(useDefaultProject = false) {
  const {
    projectId: routeProjectId,
    moduleId: routeModuleId,
    reviewStatus: routeReviewStatus,
  } = readCaseRouteSelection(route)
  const fallbackProjectId = useDefaultProject ? (projects.value[0]?.id ?? null) : selectedProjectId.value
  const nextProjectId = routeProjectId ?? fallbackProjectId
  const projectChanged = nextProjectId !== selectedProjectId.value

  selectedProjectId.value = nextProjectId
  filterReviewStatus.value = routeReviewStatus

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

async function refreshCurrentProject() {
  await loadProjects()
  await loadModules()
  await loadCases()
}

function handleSearch() {
  void loadCases()
}

function clearFilter(key: FilterKey) {
  if (key === 'keyword') keyword.value = ''
  if (key === 'type') filterType.value = undefined
  if (key === 'priority') filterPriority.value = undefined
  if (key === 'level') filterLevel.value = undefined
  if (key === 'status') filterStatus.value = undefined
  if (key === 'review_status') filterReviewStatus.value = undefined
  if (key === 'automation_status') filterAutomationStatus.value = undefined
  void loadCases()
  syncRoute()
}

function handleResetFilters() {
  keyword.value = ''
  filterType.value = undefined
  filterPriority.value = undefined
  filterLevel.value = undefined
  filterStatus.value = undefined
  filterReviewStatus.value = undefined
  filterAutomationStatus.value = undefined
  void loadCases()
  syncRoute()
}

function openCreate(type: CaseType) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedModuleId.value) {
    message.warning(t('case.msg.select_module_first'))
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

function openEdit(testCase: CaseSummaryItem) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
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

function openDetail(caseId: number) {
  void router.push(buildCaseDetailLocation(caseId, {
    projectId: selectedProjectId.value,
    moduleId: selectedModuleId.value,
  }))
}

function onSaved() {
  void loadCases()
}

async function handleRun(testCase: CaseSummaryItem) {
  if (!canRunCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedProjectId.value) {
    return
  }

  pendingRunCase.value = testCase
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const environments = await environmentApi.list(selectedProjectId.value)
    runEnvOptions.value = buildEnvironmentOptions(environments)
  } catch {
    runEnvOptions.value = []
    message.warning(t('case.msg.load_env_failed'))
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  const testCase = pendingRunCase.value
  if (!testCase) {
    return
  }

  runConfirming.value = true
  runningId.value = testCase.id
  try {
    const run = await caseApi.run(testCase.id, buildRunPayload(runEnvId.value))
    runModalOpen.value = false
    message.success(t('case.msg.run_started'))
    void router.push(buildRunDetailLocation(run.id))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.run_failed')))
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function handleCopy(caseId: number) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    const copied = await caseApi.copy(caseId)
    message.success(t('case.msg.copied', { code: copied.case_code }))
    await loadCases()
    openDetail(copied.id)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.copy_failed')))
  }
}

async function handleWorkflow(testCase: CaseSummaryItem, action: WorkflowAction) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    switch (action) {
      case 'submitReview':
        await caseApi.submitReview(testCase.id)
        message.success(t('case.msg.submit_review_done'))
        break
      case 'approve':
        await caseApi.approve(testCase.id)
        message.success(t('case.msg.approve_done'))
        break
      case 'reject':
        await caseApi.reject(testCase.id)
        message.success(t('case.msg.reject_done'))
        break
      case 'deprecate':
        await caseApi.deprecate(testCase.id)
        message.success(t('case.msg.deprecate_done'))
        break
      case 'reactivate':
        await caseApi.reactivate(testCase.id)
        message.success(t('case.msg.reactivate_done'))
        break
    }
    await loadCases()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.workflow_failed')))
  }
}

function confirmDelete(testCase: CaseSummaryItem) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  Modal.confirm({
    title: t('case.msg.delete_title', { name: testCase.name }),
    content: t('case.msg.delete_content'),
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      await caseApi.delete(testCase.id)
      message.success(t('case.msg.deleted'))
      await loadCases()
    },
  })
}

async function handleBatchDelete() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedRowKeys.value.length) return
  try {
    const result = await caseApi.batchDelete(selectedRowKeys.value)
    message.success(t('case.msg.batch_delete_success', { processed: result.processed, requested: result.requested }))
    selectedRowKeys.value = []
    await loadCases()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.batch_delete_failed')))
  }
}

async function handleBatchExport() {
  if (!selectedRowKeys.value.length) return
  try {
    const blob = await caseApi.batchExportCsv(selectedRowKeys.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cases-export-${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(t('case.msg.export_success', { count: selectedRowKeys.value.length }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.export_failed')))
  }
}

async function handleBatchExportZip() {
  if (!selectedRowKeys.value.length) return
  try {
    const blob = await caseApi.batchExportZip(selectedRowKeys.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cases-export-${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(t('case.msg.export_zip_success', { count: selectedRowKeys.value.length }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.export_failed')))
  }
}

async function handleDownloadImportTemplate() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    const blob = await caseApi.downloadImportTemplate()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'case-import-template.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(t('case.msg.template_downloaded'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.template_download_failed')))
  }
}

function handleBatchImportBeforeUpload(file: File) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return false
  }
  if (!selectedModuleId.value) {
    message.warning(t('case.msg.select_target_module_first'))
    return false
  }
  ;(async () => {
    importPreviewLoading.value = true
    try {
      importPreview.value = await caseApi.previewImportZip(file)
      pendingImportFile.value = file
      importPreviewOpen.value = true
    } catch (e: unknown) {
      message.error(errorMessage(e, t('case.msg.import_preview_failed')))
    } finally {
      importPreviewLoading.value = false
    }
  })()
  return false
}

async function confirmBatchImport() {
  if (!pendingImportFile.value || !selectedModuleId.value) {
    return
  }
  importConfirming.value = true
  try {
    const result = await caseApi.batchImportZip(pendingImportFile.value, selectedModuleId.value)
    if (result.errors.length) {
      message.warning(t('case.msg.import_done_with_skips', { imported: result.imported, skipped: result.skipped_count }))
    } else {
      message.success(t('case.msg.import_success', { imported: result.imported }))
    }
    importPreviewOpen.value = false
    pendingImportFile.value = null
    importPreview.value = null
    await loadCases()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.import_failed')))
  } finally {
    importConfirming.value = false
  }
}

function openBatchMove() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedRowKeys.value.length) return
  batchMoveTargetId.value = null
  batchMoveOpen.value = true
}

async function submitBatchMove() {
  if (!batchMoveTargetId.value) {
    message.warning(t('case.msg.select_target_module_first'))
    return
  }
  batchMoveLoading.value = true
  try {
    const result = await caseApi.batchMove(selectedRowKeys.value, batchMoveTargetId.value)
    message.success(t('case.msg.move_success', { processed: result.processed, requested: result.requested }))
    batchMoveOpen.value = false
    selectedRowKeys.value = []
    await loadCases()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.move_failed')))
  } finally {
    batchMoveLoading.value = false
  }
}

function openHistory(caseId: number) {
  historyCaseId.value = caseId
  historyOpen.value = true
}

function handleHistoryRolled() {
  void loadCases()
}

watch(
  () => [route.params.projectId, route.query.project_id, route.query.module_id, route.query.review_status].join('|'),
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
  color: var(--c-text-secondary);
}

.summary-row :deep(.ant-statistic-content) {
  font-size: 24px;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 300px) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
  min-height: 560px;
}

.side-panel {
  min-width: 0;
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 14px;
  overflow-y: auto;
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.side-panel :deep(.tree-header) {
  margin-bottom: 12px;
  padding: 2px 2px 12px;
  border-bottom: 1px solid var(--c-border);
}

.side-panel :deep(.ant-tree) {
  background: transparent;
}

.main-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-card,
.table-card {
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
}

.toolbar-card :deep(.ant-card-body) {
  padding: 14px 16px;
}

.table-card :deep(.ant-card-body) {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-main {
  flex: 1 1 960px;
  min-width: 0;
}

.toolbar-actions {
  flex: 0 0 auto;
  margin-left: auto;
}

.toolbar-actions :deep(.ant-space) {
  justify-content: flex-end;
}

.active-filter-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.active-filter-label {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.case-link {
  padding-inline: 0;
  font-weight: 600;
}

.case-summary {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.case-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.review-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.review-cell :deep(.ant-btn-link) {
  height: auto;
  padding: 0;
  font-size: 12px;
}

.run-tip {
  margin-bottom: 12px;
  color: var(--c-text-secondary);
}

.import-preview-alert {
  margin-bottom: 12px;
}

.import-error-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.import-error-title {
  color: var(--c-text-secondary);
  font-size: 12px;
}

@media (max-width: 960px) {
  .page-header,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .toolbar-main,
  .toolbar-actions {
    flex: 1 1 auto;
    margin-left: 0;
  }
}

@media (max-width: 640px) {
  .page-header :deep(.ant-space),
  .toolbar-main :deep(.ant-space),
  .toolbar-actions :deep(.ant-space) {
    width: 100%;
  }

  .page-header :deep(.ant-space-item),
  .toolbar-main :deep(.ant-space-item),
  .toolbar-actions :deep(.ant-space-item) {
    max-width: 100%;
  }

  .page-header :deep(.ant-select),
  .page-header :deep(.ant-btn),
  .toolbar-main :deep(.ant-input-search),
  .toolbar-main :deep(.ant-select),
  .toolbar-main :deep(.ant-btn),
  .toolbar-actions :deep(.ant-dropdown-trigger),
  .toolbar-actions :deep(.ant-btn) {
    width: 100% !important;
  }

  .side-panel {
    max-height: 320px;
  }

  .summary-row :deep(.ant-statistic-content) {
    font-size: 20px;
  }

  .table-card {
    overflow: hidden;
  }
}
</style>
