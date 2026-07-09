<template>
  <div class="page-shell suite-page">
    <div>
      <h2 class="page-title">{{ t('suite.title') }}</h2>
      <div class="page-subtitle">{{ t('suite.subtitle') }}</div>
    </div>
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectFilter"
          :placeholder="t('suite.select_project')"
          allow-clear
          style="width: 200px"
          @change="loadSuites"
        >
          <a-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" @click="openCreate" :disabled="!projectFilter">
        <PlusOutlined /> {{ t('suite.new') }}
      </a-button>
    </div>

    <BatchOperationBar :selected-count="selectedRowKeys.length" @cancel="selectedRowKeys = []">
      <a-button size="small" @click="handleBatchCopy">{{ t('suite.batch_copy') }}</a-button>
      <a-popconfirm
        :title="t('suite.confirm_delete_batch', { count: selectedRowKeys.length })"
        :ok-text="t('common.delete')"
        :cancel-text="t('common.cancel')"
        @confirm="handleBatchDelete"
      >
        <a-button size="small" danger>{{ t('suite.batch_delete') }}</a-button>
      </a-popconfirm>
    </BatchOperationBar>

    <a-table
      :columns="columns"
      :data-source="suites"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="{ pageSize: 20 }"
      :row-selection="{ selectedRowKeys, onChange: (keys: (string | number)[]) => (selectedRowKeys = keys as number[]) }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'case_count'">
          <a-tag color="blue">{{ t('suite.case_count_tag', { count: (record.case_ids || []).length }) }}</a-tag>
        </template>

        <template v-if="column.key === 'project'">
          {{ getProjectName(record.project_id) }}
        </template>

        <template v-if="column.key === 'strategy'">
          <a-space wrap :size="[4, 4]">
            <a-tag :color="suiteExecutionModeColor(record.config?.execution_mode)">
              {{ suiteExecutionModeLabel(record.config?.execution_mode) }}
            </a-tag>
            <a-tag :color="suiteFailStrategyColor(record.config?.fail_strategy)">
              {{ suiteFailStrategyLabel(record.config?.fail_strategy) }}
            </a-tag>
            <a-tag v-if="normalizeSuiteConfig(record.config).execution_mode === 'parallel'" color="blue">
              {{ t('suite.parallel_workers_tag', { n: normalizeSuiteConfig(record.config).max_workers }) }}
            </a-tag>
          </a-space>
        </template>

        <template v-if="column.key === 'created'">
          {{ formatTime(record.created_at) }}
        </template>

        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(record)">{{ t('suite.actions.edit') }}</a-button>
            <a-button
              type="link"
              size="small"
              :loading="runningId === record.id"
              @click="handleRun(record)"
            >
              {{ t('suite.actions.run') }}
            </a-button>
            <a-button type="link" size="small" @click="viewRuns(record)">{{ t('suite.actions.records') }}</a-button>
            <a-popconfirm :title="t('suite.confirm_delete_one')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('suite.actions.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 创建/编辑 Modal -->
    <a-modal
      v-model:open="formOpen"
      :title="editingId ? t('suite.edit') : t('suite.new')"
      width="1080"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('suite.form.name_label')" required>
          <a-input v-model:value="form.name" :placeholder="t('suite.form.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('suite.form.description_label')">
          <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('suite.form.description_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('suite.form.project_label')">
          <a-input :value="formProjectName" disabled />
        </a-form-item>
        <a-form-item :label="t('suite.form.strategy_label')">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item :label="t('suite.form.mode_label')">
                <a-select v-model:value="form.config.execution_mode" :options="executionModeOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('suite.form.fail_strategy_label')">
                <a-select v-model:value="form.config.fail_strategy" :options="failStrategyOptions" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-row v-if="form.config.execution_mode === 'parallel'" :gutter="16">
            <a-col :span="12">
              <a-form-item :label="t('suite.form.max_workers_label')">
                <a-input-number
                  v-model:value="form.config.max_workers"
                  :min="1"
                  :max="20"
                  :precision="0"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item v-if="form.config.fail_strategy === 'require-minimum-pass-rate'" :label="t('suite.form.min_pass_rate_label')">
                <a-input-number
                  v-model:value="form.config.min_pass_rate"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
          </a-row>
          <div class="suite-config-tip">{{ suiteConfigTip }}</div>
        </a-form-item>
        <a-form-item :label="t('suite.form.case_list_label')">
          <a-row :gutter="16">
            <a-col :span="16">
              <a-space direction="vertical" style="width: 100%" :size="12">
                <a-space wrap style="width: 100%">
                  <a-input-search
                    v-model:value="caseKeyword"
                    :placeholder="t('suite.case_table.search_placeholder')"
                    allow-clear
                    style="width: 280px"
                  />
                  <a-tree-select
                    v-model:value="caseModuleFilter"
                    :placeholder="t('suite.case_table.module_placeholder')"
                    allow-clear
                    show-search
                    tree-default-expand-all
                    tree-node-filter-prop="title"
                    style="width: 220px"
                    :tree-data="caseModuleTreeData"
                  />
                  <a-select
                    v-model:value="caseTypeFilter"
                    :placeholder="t('suite.case_table.type_placeholder')"
                    allow-clear
                    style="width: 150px"
                    :options="caseTypeOptions"
                  />
                  <a-select
                    v-model:value="caseSelectionScope"
                    style="width: 140px"
                    :options="caseSelectionScopeOptions"
                  />
                  <a-select
                    v-model:value="caseReadyFilter"
                    style="width: 150px"
                    :options="caseReadyFilterOptions"
                  />
                </a-space>
                <div class="case-filter-tip">
                  {{ t('suite.case_table.filter_tip') }}
                </div>
                <a-table
                  row-key="id"
                  size="small"
                  :columns="caseSelectColumns"
                  :data-source="filteredAvailableCases"
                  :loading="casesLoading"
                  :pagination="{ pageSize: 6, size: 'small' }"
                  :row-selection="caseRowSelection"
                  :scroll="{ x: 960 }"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'name'">
                      <div class="case-name-cell">
                        <div class="case-name-title">{{ record.name }}</div>
                        <div class="case-name-meta">{{ record.summary || record.description || '-' }}</div>
                      </div>
                    </template>
                    <template v-else-if="column.key === 'module'">
                      {{ getModuleName(record.module_id) }}
                    </template>
                    <template v-else-if="column.key === 'case_type'">
                      <a-tag :color="typeColor(record.case_type)">{{ typeLabel(record.case_type) }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'priority'">
                      <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'status'">
                      <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'ready'">
                      <a-tooltip :title="getExecutionHint(record)">
                        <a-tag :color="readyColor(record.is_ready_for_execution)">
                          {{ readyLabel(record.is_ready_for_execution) }}
                        </a-tag>
                      </a-tooltip>
                    </template>
                    <template v-else-if="column.key === 'ready_reason'">
                      <span
                        v-if="!record.is_ready_for_execution"
                        class="case-ready-reason"
                      >
                        {{ getExecutionReason(record) }}
                      </span>
                      <span v-else style="color: var(--c-text-tertiary)">-</span>
                    </template>
                    <template v-else-if="column.key === 'tags'">
                      <a-space wrap :size="[4, 4]">
                        <a-tag v-for="tag in record.tags" :key="tag" color="blue">{{ tag }}</a-tag>
                        <span v-if="!record.tags?.length" style="color: var(--c-text-tertiary)">-</span>
                      </a-space>
                    </template>
                  </template>
                </a-table>
              </a-space>
            </a-col>
            <a-col :span="8">
              <div class="selected-case-panel">
                <div class="selected-case-title">
                  <span>
                    {{ t('suite.selected.title') }}
                    <span class="selected-case-count">{{ selectedCaseItems.length }}</span>
                  </span>
                  <span class="selected-case-tip">{{ t('suite.selected.drag_tip') }}</span>
                </div>
                <div v-if="selectedUnreadyCaseItems.length" class="selected-case-warning">
                  {{ t('suite.selected.unready_warning', { count: selectedUnreadyCaseItems.length }) }}
                </div>
                <a-empty
                  v-if="selectedCaseItems.length === 0"
                  :description="t('suite.selected.empty')"
                  :image="false"
                />
                <draggable
                  v-else
                  v-model="selectedCaseListModel"
                  item-key="id"
                  handle=".selected-case-drag-handle"
                  class="selected-case-list"
                  ghost-class="selected-case-ghost"
                  :animation="180"
                >
                  <template #item="{ element: c, index }">
                    <div class="selected-case-item">
                      <div class="selected-case-order-group">
                        <HolderOutlined class="selected-case-drag-handle" />
                        <div class="selected-case-order">#{{ index + 1 }}</div>
                      </div>
                      <div class="selected-case-body">
                        <div class="selected-case-name">{{ c.case_code }} · {{ c.name }}</div>
                        <div class="selected-case-meta">
                          <a-tag :color="typeColor(c.case_type)">{{ typeLabel(c.case_type) }}</a-tag>
                          <a-tag :color="priorityColor(c.priority)">{{ c.priority }}</a-tag>
                          <a-tooltip :title="getExecutionHint(c)">
                            <a-tag :color="readyColor(c.is_ready_for_execution)">
                              {{ readyLabel(c.is_ready_for_execution) }}
                            </a-tag>
                          </a-tooltip>
                          <span>{{ getModuleName(c.module_id) }}</span>
                        </div>
                      </div>
                      <div class="selected-case-actions">
                        <a-button type="text" size="small" :disabled="index === 0" @click="moveSelectedCase(index, -1)">{{ t('suite.selected.move_up') }}</a-button>
                        <a-button type="text" size="small" :disabled="index === selectedCaseListModel.length - 1" @click="moveSelectedCase(index, 1)">{{ t('suite.selected.move_down') }}</a-button>
                        <a-button type="text" size="small" danger @click="removeSelectedCase(c.id)">{{ t('suite.selected.remove') }}</a-button>
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
              <div class="case-select-tip">
                {{ t('suite.selected.order_tip') }}
              </div>
            </a-col>
          </a-row>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 执行环境选择 -->
    <a-modal
      v-model:open="runModalOpen"
      :title="t('suite.run_modal.title')"
      :ok-text="t('suite.run_modal.ok')"
      :cancel-text="t('suite.run_modal.cancel')"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p style="margin-bottom: 12px; color: var(--c-text-secondary)">{{ t('suite.run_modal.tip') }}</p>
      <a-select
        v-model:value="runEnvId"
        :placeholder="t('suite.run_modal.placeholder')"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <!-- 执行记录 Drawer -->
    <a-drawer
      :open="runsDrawerOpen"
      :title="t('suite.runs.drawer_title', { name: runsDrawerTitle })"
      width="700"
      @close="() => {
        runsDrawerOpen = false
        activeRunsSuiteId = null
        stopSuiteRunsRefresh()
      }"
    >
      <a-table
        :columns="runColumns"
        :data-source="suiteRuns"
        :loading="runsLoading"
        row-key="id"
        size="small"
        :pagination="false"
        :expandedRowKeys="expandedSuiteRunKeys"
        @expand="onSuiteRunExpand"
      >
        <template #expandedRowRender="{ record }">
          <div class="aggregate-report-panel suite-run-cases-panel">
            <div class="aggregate-report-title">{{ t('suite.report.title') }}</div>
            <div class="aggregate-report-grid">
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('suite.report.pass_rate') }}</div>
                <div class="aggregate-report-value">{{ formatPercent(getSuiteRunPassRate(record)) }}</div>
              </div>
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('suite.report.failures') }}</div>
                <div class="aggregate-report-value danger">{{ getSuiteRunFailureCount(record) }}</div>
              </div>
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('suite.report.duration') }}</div>
                <div class="aggregate-report-value">{{ formatDuration(record.duration_ms) }}</div>
              </div>
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('suite.report.related_cases') }}</div>
                <div class="aggregate-report-value">{{ record.case_run_ids?.length ?? 0 }}</div>
              </div>
            </div>
            <div class="aggregate-report-section">
              <div class="aggregate-report-subtitle">{{ t('suite.report.failure_top') }}</div>
              <a-empty v-if="!getSuiteRunFailureItems(record).length" :description="t('suite.report.no_failures')" :image="false" />
              <a-list v-else size="small" :data-source="getSuiteRunFailureItems(record).slice(0, 5)">
                <template #renderItem="{ item }">
                  <a-list-item>
                    <a-space direction="vertical" :size="2" style="width: 100%">
                      <span>
                        <a-tag :color="item.status === 'failed' ? 'red' : 'orange'">{{ item.status }}</a-tag>
                        {{ item.case_name || t('suite.report.case_fallback', { id: item.case_id }) }}
                      </span>
                      <span class="aggregate-report-reason">{{ item.error || t('suite.report.no_reason') }}</span>
                    </a-space>
                  </a-list-item>
                </template>
              </a-list>
            </div>
            <template v-if="record.case_run_ids?.length">
              <div class="aggregate-report-subtitle">{{ t('suite.report.case_details') }}</div>
              <a-table
                :columns="suiteRunCaseColumns"
                :data-source="record.case_run_ids"
                row-key="run_id"
                size="small"
                :pagination="false"
              >
                <template #bodyCell="{ column, record: caseRun }">
                  <template v-if="column.key === 'status'">
                    <a-tag :color="caseRun.status === 'passed' ? 'green' : caseRun.status === 'failed' ? 'red' : caseRun.status === 'error' ? 'orange' : 'default'">{{ caseRun.status }}</a-tag>
                  </template>
                  <template v-if="column.key === 'stability'">
                    <a-tag v-if="caseRun.flaky" color="volcano">
                      {{ t('suite.report.flaky_case') }}
                    </a-tag>
                    <span v-else style="color: var(--c-text-tertiary)">-</span>
                  </template>
                  <template v-if="column.key === 'run_id'">
                    <a v-if="caseRun.run_id" @click="goToRunDetail(caseRun.run_id)">{{ caseRun.run_id }}</a>
                    <span v-else style="color: var(--c-text-tertiary)">-</span>
                  </template>
                </template>
              </a-table>
            </template>
            <template v-else>
              <a-empty :description="t('suite.runs.empty_cases')" :image="false" />
            </template>
          </div>
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-badge :status="runStatusBadge(record.status)" :text="record.status" />
          </template>
          <template v-if="column.key === 'summary'">
            <div v-if="record.result_summary">
              <a-space direction="vertical" style="width: 100%" :size="6">
                <a-progress
                  v-if="record.status === 'pending' || record.status === 'running'"
                  :percent="getSuiteRunProgressPercent(record)"
                  :status="getSuiteRunProgressStatus(record)"
                  size="small"
                />
                <a-space v-if="record.status === 'pending' || record.status === 'running'" wrap :size="[4, 4]">
                  <a-tag color="processing">
                    {{ t('suite.runs.progress_tag', { done: getSuiteRunCompletedCount(record), total: getSuiteRunTotalCount(record) }) }}
                  </a-tag>
                </a-space>
                <a-space wrap :size="[4, 4]">
                  <a-tag color="green">{{ t('suite.runs.passed_tag', { count: record.result_summary.passed ?? 0 }) }}</a-tag>
                  <a-tag v-if="record.result_summary.failed" color="red">{{ t('suite.runs.failed_tag', { count: record.result_summary.failed }) }}</a-tag>
                  <a-tag v-if="record.result_summary.error" color="orange">{{ t('suite.runs.error_tag', { count: record.result_summary.error }) }}</a-tag>
                  <a-tag v-if="record.result_summary.skipped" color="default">{{ t('suite.runs.skipped_tag', { count: record.result_summary.skipped }) }}</a-tag>
                  <a-tag :color="suiteExecutionModeColor(record.result_summary.execution_mode as SuiteConfig['execution_mode'])">
                    {{ suiteExecutionModeLabel(record.result_summary.execution_mode as SuiteConfig['execution_mode']) }}
                  </a-tag>
                  <a-tag :color="suiteFailStrategyColor(record.result_summary.fail_strategy as SuiteConfig['fail_strategy'])">
                    {{ suiteFailStrategyLabel(record.result_summary.fail_strategy as SuiteConfig['fail_strategy']) }}
                  </a-tag>
                  <a-tag v-if="record.result_summary.execution_mode === 'parallel'" color="blue">
                    {{ t('suite.runs.parallel_tag', { n: record.result_summary.max_workers ?? '-' }) }}
                  </a-tag>
                  <a-tag v-if="record.result_summary.fail_strategy === 'require-minimum-pass-rate'" color="purple">
                    {{ t('suite.runs.target_tag', { percent: Number(record.result_summary.min_pass_rate ?? 0).toLocaleString(locale, { style: 'percent', maximumFractionDigits: 0 }) }) }}
                  </a-tag>
                </a-space>
              </a-space>
            </div>
          </template>
          <template v-if="column.key === 'case_runs'">
            <a-tag v-if="record.case_run_ids?.length" color="blue">{{ t('suite.runs.case_count_tag', { count: record.case_run_ids.length }) }}</a-tag>
            <span v-else style="color: var(--c-text-tertiary)">-</span>
          </template>
          <template v-if="column.key === 'duration'">
            {{ formatDuration(record.duration_ms) }}
          </template>
          <template v-if="column.key === 'created'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-if="column.key === 'export'">
            <a-space>
              <a-button type="link" size="small" :loading="exportingSuiteRunHtmlId === record.id" @click="handleExportSuiteRunHtml(record.id)">HTML</a-button>
              <a-button type="link" size="small" :loading="exportingSuiteRunPdfId === record.id" @click="handleExportSuiteRunPdf(record.id)">PDF</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { HolderOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import type {
  CasePriority,
  CaseStatus,
  CaseSummaryItem,
  CaseType,
  EnvironmentItem,
  ModuleTreeItem,
  ProjectItem,
  SuiteConfig,
  SuiteExecutionMode,
  SuiteFailStrategy,
  SuiteItem,
  SuiteRunItem,
} from '@/api'
import { suiteApi, projectApi, caseApi, environmentApi } from '@/api'
import BatchOperationBar from '@/components/common/BatchOperationBar.vue'
import {
  createDefaultSuiteConfig,
  formatDuration,
  formatPercent,
  getSuiteRunCompletedCount,
  getSuiteRunFailureCount,
  getSuiteRunFailureItems,
  getSuiteRunPassRate,
  getSuiteRunProgressPercent,
  getSuiteRunProgressStatus,
  getSuiteRunTotalCount,
  hasActiveSuiteRuns,
  normalizeSuiteConfig,
  runStatusBadge,
  suiteExecutionModeColor,
  suiteFailStrategyColor,
} from '@/utils/suiteList'

const { t, locale } = useI18n()

type CaseSelectionScope = 'all' | 'selected' | 'unselected'
type CaseReadyFilter = 'all' | 'ready' | 'not_ready'
type SelectOption = { label: string; value: number }

interface SuiteFormState {
  name: string
  description: string
  config: Required<Pick<SuiteConfig, 'execution_mode' | 'max_workers' | 'fail_strategy' | 'min_pass_rate'>>
}

interface ModuleTreeOption {
  title: string
  value: number
  key: number
  children?: ModuleTreeOption[]
}

function getErrorMessage(error: unknown, fallback: string) {
  return typeof error === 'string' ? error : fallback
}

function createDefaultForm(): SuiteFormState {
  return {
    name: '',
    description: '',
    config: createDefaultSuiteConfig(),
  }
}

const suites = ref<SuiteItem[]>([])
const projects = ref<ProjectItem[]>([])
const loading = ref(false)
const selectedRowKeys = ref<number[]>([])
const projectFilter = ref<number | undefined>(undefined)

// Form
const formOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = ref<SuiteFormState>(createDefaultForm())
const selectedCaseIds = ref<number[]>([])
const availableCases = ref<CaseSummaryItem[]>([])
const casesLoading = ref(false)
const formProjectId = ref<number | null>(null)
const caseKeyword = ref('')
const caseModuleFilter = ref<number | undefined>(undefined)
const caseTypeFilter = ref<CaseType | undefined>(undefined)
const caseSelectionScope = ref<CaseSelectionScope>('all')
const caseReadyFilter = ref<CaseReadyFilter>('ready')
const moduleTree = ref<ModuleTreeItem[]>([])
const moduleNameMap = ref<Record<number, string>>({})

// Run
const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<SelectOption[]>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const runningId = ref<number | null>(null)
const pendingRunSuite = ref<SuiteItem | null>(null)

// Run records
const runsDrawerOpen = ref(false)
const runsDrawerTitle = ref('')
const suiteRuns = ref<SuiteRunItem[]>([])
const runsLoading = ref(false)
const expandedSuiteRunKeys = ref<number[]>([])
const exportingSuiteRunHtmlId = ref<number | null>(null)
const exportingSuiteRunPdfId = ref<number | null>(null)
const activeRunsSuiteId = ref<number | null>(null)
let suiteRunsRefreshTimer: ReturnType<typeof setInterval> | null = null

const columns = computed(() => [
  { title: t('suite.columns.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('suite.columns.project'), key: 'project', width: 150 },
  { title: t('suite.columns.strategy'), key: 'strategy', width: 260 },
  { title: t('suite.columns.case_count'), key: 'case_count', width: 100 },
  { title: t('suite.columns.created'), key: 'created', width: 170 },
  { title: t('suite.columns.action'), key: 'action', width: 220, fixed: 'right' as const },
])

const runColumns = computed(() => [
  { title: t('suite.run_columns.status'), key: 'status', width: 100 },
  { title: t('suite.run_columns.summary'), key: 'summary', width: 340 },
  { title: t('suite.run_columns.case_runs'), key: 'case_runs', width: 120 },
  { title: t('suite.run_columns.duration'), key: 'duration', width: 80 },
  { title: t('suite.run_columns.created'), key: 'created', width: 170 },
  { title: t('suite.run_columns.export'), key: 'export', width: 160 },
])

const suiteRunCaseColumns = computed(() => [
  { title: t('suite.case_columns.case_id'), dataIndex: 'case_id', key: 'case_id', width: 90 },
  { title: t('suite.case_columns.case_name'), dataIndex: 'case_name', key: 'case_name', ellipsis: true },
  { title: t('suite.case_columns.status'), key: 'status', width: 100 },
  { title: t('suite.case_columns.stability'), key: 'stability', width: 100 },
  { title: t('suite.case_columns.run_id'), key: 'run_id', width: 100 },
])

const caseSelectColumns = computed(() => [
  { title: t('suite.case_table_columns.code'), dataIndex: 'case_code', key: 'case_code', width: 150 },
  { title: t('suite.case_table_columns.name'), key: 'name', width: 260 },
  { title: t('suite.case_table_columns.module'), key: 'module', width: 140 },
  { title: t('suite.case_table_columns.type'), key: 'case_type', width: 90 },
  { title: t('suite.case_table_columns.priority'), key: 'priority', width: 90 },
  { title: t('suite.case_table_columns.status'), key: 'status', width: 90 },
  { title: t('suite.case_table_columns.ready'), key: 'ready', width: 100 },
  { title: t('suite.case_table_columns.ready_reason'), key: 'ready_reason', width: 220 },
  { title: t('suite.case_table_columns.tags'), key: 'tags', width: 180 },
])

const caseTypeOptions = computed<Array<{ label: string; value: CaseType }>>(() => [
  { label: t('suite.case_types.api'), value: 'api' },
  { label: t('suite.case_types.graphql'), value: 'graphql' },
  { label: t('suite.case_types.websocket'), value: 'websocket' },
  { label: t('suite.case_types.grpc'), value: 'grpc' },
  { label: t('suite.case_types.web'), value: 'web' },
  { label: t('suite.case_types.android'), value: 'android' },
])

const caseSelectionScopeOptions = computed<Array<{ label: string; value: CaseSelectionScope }>>(() => [
  { label: t('suite.case_selection_scope.all'), value: 'all' },
  { label: t('suite.case_selection_scope.selected'), value: 'selected' },
  { label: t('suite.case_selection_scope.unselected'), value: 'unselected' },
])

const caseReadyFilterOptions = computed<Array<{ label: string; value: CaseReadyFilter }>>(() => [
  { label: t('suite.case_ready_filter.all'), value: 'all' },
  { label: t('suite.case_ready_filter.ready'), value: 'ready' },
  { label: t('suite.case_ready_filter.not_ready'), value: 'not_ready' },
])

const executionModeOptions = computed<Array<{ label: string; value: SuiteExecutionMode }>>(() => [
  { label: t('suite.execution_modes.sequential'), value: 'sequential' },
  { label: t('suite.execution_modes.parallel'), value: 'parallel' },
])

const failStrategyOptions = computed<Array<{ label: string; value: SuiteFailStrategy }>>(() => [
  { label: t('suite.fail_strategies.continue'), value: 'continue' },
  { label: t('suite.fail_strategies.fast-fail'), value: 'fast-fail' },
  { label: t('suite.fail_strategies.require-minimum-pass-rate'), value: 'require-minimum-pass-rate' },
])

const moduleDescendantMap = computed(() => buildModuleDescendantMap(moduleTree.value))

const caseModuleTreeData = computed(() =>
  buildModuleTreeOptions(
    moduleTree.value,
    new Set(availableCases.value.map((item) => item.module_id)),
  ),
)

const formProjectName = computed(() => {
  if (!formProjectId.value) return '-'
  return getProjectName(formProjectId.value)
})

const suiteConfigTip = computed(() => {
  const cfg = form.value.config
  if (cfg.execution_mode === 'sequential') {
    return t('suite.config_tips.sequential')
  }
  if (cfg.fail_strategy === 'fast-fail') {
    return t('suite.config_tips.fast_fail', { n: cfg.max_workers })
  }
  if (cfg.fail_strategy === 'require-minimum-pass-rate') {
    return t('suite.config_tips.min_pass_rate', {
      n: cfg.max_workers,
      percent: (cfg.min_pass_rate * 100).toFixed(0),
    })
  }
  return t('suite.config_tips.continue', { n: cfg.max_workers })
})

const filteredAvailableCases = computed(() => {
  const keyword = caseKeyword.value.trim().toLowerCase()
  const selectedIds = new Set(selectedCaseIds.value)
  const allowedModuleIds =
    caseModuleFilter.value !== undefined
      ? moduleDescendantMap.value.get(caseModuleFilter.value) ?? new Set<number>()
      : null

  return availableCases.value.filter((item) => {
    if (allowedModuleIds && !allowedModuleIds.has(item.module_id)) {
      return false
    }
    if (caseTypeFilter.value !== undefined && item.case_type !== caseTypeFilter.value) {
      return false
    }
    if (caseReadyFilter.value === 'ready' && !item.is_ready_for_execution) {
      return false
    }
    if (caseReadyFilter.value === 'not_ready' && item.is_ready_for_execution) {
      return false
    }
    const isSelected = selectedIds.has(item.id)
    if (caseSelectionScope.value === 'selected' && !isSelected) {
      return false
    }
    if (caseSelectionScope.value === 'unselected' && isSelected) {
      return false
    }
    if (!keyword) {
      return true
    }

    const fields = [
      item.case_code,
      item.name,
      item.summary,
      item.description,
      ...(item.tags ?? []),
      getModuleName(item.module_id),
      typeLabel(item.case_type),
      item.priority,
      statusLabel(item.status),
      readyLabel(item.is_ready_for_execution),
      getExecutionReason(item),
    ]
    return fields.some((field) => String(field ?? '').toLowerCase().includes(keyword))
  })
})

const selectedCaseItems = computed(() => {
  const caseMap = new Map(availableCases.value.map((item) => [item.id, item]))
  return selectedCaseIds.value
    .map((id) => caseMap.get(id))
    .filter((item): item is CaseSummaryItem => Boolean(item))
})

const selectedCaseListModel = computed<CaseSummaryItem[]>({
  get: () => selectedCaseItems.value,
  set: (items) => {
    selectedCaseIds.value = items.map((item) => item.id)
  },
})

const selectedUnreadyCaseItems = computed(() =>
  selectedCaseItems.value.filter((item) => !item.is_ready_for_execution),
)

const caseRowSelection = computed(() => ({
  selectedRowKeys: selectedCaseIds.value,
  preserveSelectedRowKeys: true,
  getCheckboxProps: (record: CaseSummaryItem) => ({
    disabled: !record.is_ready_for_execution && !selectedCaseIds.value.includes(record.id),
  }),
  onSelect: (record: CaseSummaryItem, selected: boolean) => {
    if (selected) {
      if (!selectedCaseIds.value.includes(record.id)) {
        selectedCaseIds.value = [...selectedCaseIds.value, record.id]
      }
      return
    }
    selectedCaseIds.value = selectedCaseIds.value.filter((id) => id !== record.id)
  },
  onSelectAll: (selected: boolean, _rows: CaseSummaryItem[], changeRows: CaseSummaryItem[]) => {
    const changedIds = changeRows.map((item) => item.id)
    if (selected) {
      selectedCaseIds.value = [
        ...selectedCaseIds.value,
        ...changedIds.filter((id) => !selectedCaseIds.value.includes(id)),
      ]
      return
    }
    const removedIds = new Set(changedIds)
    selectedCaseIds.value = selectedCaseIds.value.filter((id) => !removedIds.has(id))
  },
}))

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ')
}

function getProjectName(id: number) {
  return projects.value.find(p => p.id === id)?.name ?? '-'
}

function typeLabel(typ: CaseType | string) {
  const map: Record<string, string> = {
    api: t('suite.case_types.api'),
    graphql: t('suite.case_types.graphql'),
    websocket: t('suite.case_types.websocket'),
    grpc: t('suite.case_types.grpc'),
    web: t('suite.case_types.web'),
    android: t('suite.case_types.android'),
  }
  return map[typ] ?? typ
}

function typeColor(typ: CaseType | string) {
  return {
    api: 'geekblue',
    graphql: 'cyan',
    websocket: 'gold',
    grpc: 'volcano',
    web: 'purple',
    android: 'green',
  }[typ] ?? 'default'
}

function priorityColor(priority: CasePriority | string) {
  return { P0: 'red', P1: 'volcano', P2: 'gold', P3: 'default' }[priority] ?? 'default'
}

function statusLabel(status: CaseStatus | string) {
  const map: Record<string, string> = {
    draft: t('suite.case_status.draft'),
    active: t('suite.case_status.active'),
    deprecated: t('suite.case_status.deprecated'),
  }
  return map[status] ?? status
}

function statusColor(status: CaseStatus | string) {
  return { draft: 'default', active: 'success', deprecated: 'error' }[status] ?? 'default'
}

function readyLabel(isReady: boolean) {
  return isReady ? t('suite.case_ready.ready') : t('suite.case_ready.not_ready')
}

function readyColor(isReady: boolean) {
  return isReady ? 'success' : 'orange'
}

function suiteExecutionModeLabel(mode?: SuiteConfig['execution_mode']) {
  return mode === 'parallel' ? t('suite.execution_modes.parallel') : t('suite.execution_modes.sequential')
}

function suiteFailStrategyLabel(strategy?: SuiteConfig['fail_strategy']) {
  const key = strategy ?? 'continue'
  return t(`suite.fail_strategies.${key}`)
}

function getExecutionReason(item: Pick<CaseSummaryItem, 'status' | 'review_status' | 'automation_status'>) {
  if (item.status !== 'active') {
    return t('suite.case_reason.status_not_active')
  }
  if (item.review_status !== 'approved') {
    return t('suite.case_reason.review_not_approved')
  }
  if (!['auto', 'semi_auto'].includes(item.automation_status)) {
    return t('suite.case_reason.not_automation')
  }
  return '-'
}

function getExecutionHint(item: Pick<CaseSummaryItem, 'is_ready_for_execution' | 'status' | 'review_status' | 'automation_status'>) {
  if (item.is_ready_for_execution) {
    return t('suite.case_reason.hint_ready')
  }
  return t('suite.case_reason.hint_not_ready', { reason: getExecutionReason(item) })
}

function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}) {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (node.children?.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}

function buildModuleDescendantMap(
  nodes: ModuleTreeItem[],
  acc: Map<number, Set<number>> = new Map(),
) {
  for (const node of nodes) {
    buildModuleDescendantMap(node.children ?? [], acc)
    const descendantIds = new Set<number>([node.id])
    for (const child of node.children ?? []) {
      const childIds = acc.get(child.id)
      if (!childIds) {
        continue
      }
      for (const childId of childIds) {
        descendantIds.add(childId)
      }
    }
    acc.set(node.id, descendantIds)
  }
  return acc
}

function buildModuleTreeOptions(
  nodes: ModuleTreeItem[],
  availableModuleIds: Set<number>,
): ModuleTreeOption[] {
  const options: ModuleTreeOption[] = []

  for (const node of nodes) {
    const children = buildModuleTreeOptions(node.children ?? [], availableModuleIds)
    if (!availableModuleIds.has(node.id) && children.length === 0) {
      continue
    }
    options.push({
      title: node.name,
      value: node.id,
      key: node.id,
      children: children.length ? children : undefined,
    })
  }

  return options
}

function getModuleName(moduleId: number) {
  return moduleNameMap.value[moduleId] ?? t('suite.module_fallback', { id: moduleId })
}

function stopSuiteRunsRefresh() {
  if (suiteRunsRefreshTimer) {
    clearInterval(suiteRunsRefreshTimer)
    suiteRunsRefreshTimer = null
  }
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (error: unknown) {
    projects.value = []
    message.error(getErrorMessage(error, t('suite.msg.load_projects_failed')))
  }
}

async function loadSuites() {
  loading.value = true
  try {
    suites.value = await suiteApi.list(
      projectFilter.value ? { project_id: projectFilter.value } : undefined,
    )
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.load_suites_failed')))
  } finally {
    loading.value = false
  }
}

async function handleBatchDelete() {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await suiteApi.batchDelete(selectedRowKeys.value)
    message.success(t('suite.msg.batch_delete_success', { processed: result.processed, requested: result.requested }))
    selectedRowKeys.value = []
    await loadSuites()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.batch_delete_failed')))
  }
}

async function handleBatchCopy() {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await suiteApi.batchCopy(selectedRowKeys.value)
    message.success(t('suite.msg.batch_copy_success', { processed: result.processed, requested: result.requested }))
    selectedRowKeys.value = []
    await loadSuites()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.batch_copy_failed')))
  }
}

async function loadCases(projectId = formProjectId.value) {
  if (!projectId) {
    availableCases.value = []
    moduleTree.value = []
    moduleNameMap.value = {}
    return
  }
  casesLoading.value = true
  try {
    const [cases, moduleTreeData] = await Promise.all([
      caseApi.list({ project_id: projectId }),
      projectApi.getModules(projectId),
    ])
    availableCases.value = cases
    moduleTree.value = moduleTreeData
    moduleNameMap.value = flattenModules(moduleTreeData)
  } catch (error: unknown) {
    availableCases.value = []
    moduleTree.value = []
    moduleNameMap.value = {}
    message.error(getErrorMessage(error, t('suite.msg.load_cases_failed')))
  } finally {
    casesLoading.value = false
  }
}

function openCreate() {
  formProjectId.value = projectFilter.value ?? null
  editingId.value = null
  form.value = createDefaultForm()
  selectedCaseIds.value = []
  caseKeyword.value = ''
  caseModuleFilter.value = undefined
  caseTypeFilter.value = undefined
  caseSelectionScope.value = 'all'
  caseReadyFilter.value = 'ready'
  loadCases(formProjectId.value)
  formOpen.value = true
}

async function openEdit(record: SuiteItem) {
  formProjectId.value = record.project_id
  editingId.value = record.id
  form.value = {
    name: record.name,
    description: record.description ?? '',
    config: normalizeSuiteConfig(record.config),
  }
  selectedCaseIds.value = (record.case_ids || []).map((c) => c.case_id)
  caseKeyword.value = ''
  caseModuleFilter.value = undefined
  caseTypeFilter.value = undefined
  caseSelectionScope.value = 'all'
  caseReadyFilter.value = 'ready'
  await loadCases(formProjectId.value)
  formOpen.value = true
}

async function handleSave() {
  if (saving.value) {
    return
  }
  if (!form.value.name.trim()) {
    message.warning(t('suite.msg.name_required'))
    return
  }
  if (!formProjectId.value) {
    message.warning(t('suite.msg.project_required'))
    return
  }
  if (selectedCaseIds.value.length === 0) {
    message.warning(t('suite.msg.case_required'))
    return
  }
  if (selectedUnreadyCaseItems.value.length > 0) {
    const names = selectedUnreadyCaseItems.value
      .slice(0, 3)
      .map((item) => `${item.case_code}(${getExecutionReason(item)})`)
      .join('、')
    const restCount = selectedUnreadyCaseItems.value.length - 3

    Modal.confirm({
      title: t('suite.confirm.unready_title', { count: selectedUnreadyCaseItems.value.length }),
      content: restCount > 0
        ? t('suite.confirm.unready_content_more', { names, total: restCount + 3 })
        : t('suite.confirm.unready_content', { names }),
      okText: t('suite.confirm.ok_text'),
      cancelText: t('suite.confirm.cancel_text'),
      async onOk() {
        await persistSuite()
      },
    })
    return
  }
  await persistSuite()
}

async function persistSuite() {
  saving.value = true
  try {
    const caseIds = selectedCaseIds.value.map((id, idx) => ({ case_id: id, sort: idx }))
    const config = normalizeSuiteConfig(form.value.config)
    if (editingId.value) {
      await suiteApi.update(editingId.value, {
        name: form.value.name,
        description: form.value.description,
        case_ids: caseIds,
        config,
      })
      message.success(t('suite.msg.save_success'))
    } else {
      await suiteApi.create({
        name: form.value.name,
        description: form.value.description,
        project_id: formProjectId.value ?? undefined,
        case_ids: caseIds,
        config,
      })
      message.success(t('suite.msg.created'))
    }
    formOpen.value = false
    loadSuites()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

function moveSelectedCase(index: number, delta: -1 | 1) {
  const targetIndex = index + delta
  if (targetIndex < 0 || targetIndex >= selectedCaseIds.value.length) {
    return
  }

  const nextIds = [...selectedCaseIds.value]
  const [current] = nextIds.splice(index, 1)
  nextIds.splice(targetIndex, 0, current)
  selectedCaseIds.value = nextIds
}

function removeSelectedCase(caseId: number) {
  selectedCaseIds.value = selectedCaseIds.value.filter((id) => id !== caseId)
}

async function handleRun(record: SuiteItem) {
  pendingRunSuite.value = record
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const envs = await environmentApi.list(record.project_id)
    runEnvOptions.value = envs.map((e: EnvironmentItem) => ({ label: e.name, value: e.id }))
  } catch (error: unknown) {
    runEnvOptions.value = []
    message.error(getErrorMessage(error, t('suite.msg.load_environments_failed')))
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
    message.success(t('suite.msg.run_triggered'))
    // 打开执行记录
    viewRuns(s)
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.run_failed')))
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function viewRuns(record: SuiteItem) {
  runsDrawerTitle.value = record.name
  runsDrawerOpen.value = true
  activeRunsSuiteId.value = record.id
  expandedSuiteRunKeys.value = []
  await loadSuiteRuns(record.id, true)
}

async function loadSuiteRuns(suiteId = activeRunsSuiteId.value, showLoading = false) {
  if (!suiteId) {
    suiteRuns.value = []
    stopSuiteRunsRefresh()
    return
  }

  if (showLoading) {
    runsLoading.value = true
  }

  try {
    const runs = await suiteApi.listRuns({ suite_id: suiteId })
    suiteRuns.value = runs
    if (runsDrawerOpen.value && hasActiveSuiteRuns(runs)) {
      if (!suiteRunsRefreshTimer) {
        suiteRunsRefreshTimer = setInterval(() => {
          void loadSuiteRuns(suiteId, false)
        }, 3000)
      }
    } else {
      stopSuiteRunsRefresh()
    }
  } catch (error: unknown) {
    if (showLoading) {
      suiteRuns.value = []
      message.error(getErrorMessage(error, t('suite.msg.load_runs_failed')))
    }
    stopSuiteRunsRefresh()
  } finally {
    if (showLoading) {
      runsLoading.value = false
    }
  }
}

function onSuiteRunExpand(expanded: boolean, record: SuiteRunItem) {
  if (expanded) {
    expandedSuiteRunKeys.value = [record.id]
    return
  }
  expandedSuiteRunKeys.value = expandedSuiteRunKeys.value.filter(id => id !== record.id)
}

function goToRunDetail(runId: number) {
  window.open(`/runs/${runId}`, '_blank')
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

async function handleExportSuiteRunHtml(runId: number) {
  exportingSuiteRunHtmlId.value = runId
  try {
    const blob = await suiteApi.exportRunHtml(runId)
    downloadBlob(blob, `suite-run-${runId}-report.html`)
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.export_html_failed')))
  } finally {
    exportingSuiteRunHtmlId.value = null
  }
}

async function handleExportSuiteRunPdf(runId: number) {
  exportingSuiteRunPdfId.value = runId
  try {
    const blob = await suiteApi.exportRunPdf(runId)
    downloadBlob(blob, `suite-run-${runId}-report.pdf`)
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.export_pdf_failed')))
  } finally {
    exportingSuiteRunPdfId.value = null
  }
}

async function handleDelete(id: number) {
  try {
    await suiteApi.delete(id)
    message.success(t('suite.msg.deleted'))
    loadSuites()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('suite.msg.delete_failed')))
  }
}

onMounted(() => {
  loadProjects()
  loadSuites()
})

onUnmounted(() => {
  stopSuiteRunsRefresh()
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

.suite-run-cases-panel {
  padding: 8px 0;
}
.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.case-name-title {
  font-weight: 500;
  color: var(--c-text);
}
.case-name-meta {
  font-size: 12px;
  color: var(--c-text-tertiary);
}
.case-filter-tip {
  font-size: 12px;
  color: var(--c-text-tertiary);
}
.case-ready-reason {
  font-size: 12px;
  color: var(--c-warning);
}
.suite-config-tip {
  margin-top: -4px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}
.selected-case-panel {
  min-height: 330px;
  padding: 12px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
}
.selected-case-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
}
.selected-case-tip {
  font-size: 12px;
  font-weight: 400;
  color: var(--c-text-tertiary);
}
.selected-case-count {
  color: var(--c-primary);
}
.selected-case-warning {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--c-warning-soft);
  color: var(--c-warning);
  font-size: 12px;
}
.selected-case-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.selected-case-ghost {
  opacity: 0.6;
}
.selected-case-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-elevated);
}
.selected-case-order-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.selected-case-drag-handle {
  font-size: 16px;
  color: var(--c-text-tertiary);
  cursor: grab;
}
.selected-case-drag-handle:active {
  cursor: grabbing;
}
.selected-case-order {
  min-width: 28px;
  font-weight: 600;
  color: var(--c-primary);
}
.selected-case-body {
  flex: 1;
  min-width: 0;
}
.selected-case-name {
  margin-bottom: 6px;
  font-weight: 500;
  color: var(--c-text);
  word-break: break-word;
}
.selected-case-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: var(--c-text-tertiary);
}
.selected-case-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
}
.case-select-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}
</style>
