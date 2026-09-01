<template>
  <div class="page-shell plan-page">
    <div>
      <h2 class="page-title">{{ t('plan.title') }}</h2>
      <div class="page-subtitle">{{ t('plan.subtitle') }}</div>
    </div>
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('plan.select_project')"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadPlans"
        />
      </a-space>
      <a-button type="primary" @click="openCreate" :disabled="!projectId">
        <PlusOutlined /> {{ t('plan.new') }}
      </a-button>
    </div>

    <BatchOperationBar :selected-count="selectedRowKeys.length" @cancel="selectedRowKeys = []">
      <a-button size="small" @click="handleBatchToggle(true)">{{ t('plan.batch_enable') }}</a-button>
      <a-button size="small" @click="handleBatchToggle(false)">{{ t('plan.batch_disable') }}</a-button>
      <a-popconfirm
        :title="t('plan.confirm_delete_batch', { count: selectedRowKeys.length })"
        :ok-text="t('common.delete')"
        :cancel-text="t('common.cancel')"
        @confirm="handleBatchDelete"
      >
        <a-button size="small" danger>{{ t('plan.batch_delete') }}</a-button>
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
          <span v-if="record.schedule_type === 'cron'" style="font-size: 12px; color: var(--c-text-tertiary); margin-left: 4px">
            {{ record.cron_expression }}
          </span>
        </template>

        <template v-if="column.key === 'is_enabled'">
          <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? t('common.enabled') : t('common.disabled') }}</a-tag>
        </template>

        <template v-if="column.key === 'suites'">
          <span>{{ t('plan.suite_count', { count: (record.suite_ids || []).length }) }}</span>
        </template>

        <template v-if="column.key === 'next_run_at'">
          <span v-if="record.next_run_at">{{ formatTime(record.next_run_at) }}</span>
          <span v-else style="color: var(--c-text-tertiary)">-</span>
        </template>

        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(asPlan(record))">{{ t('plan.actions.edit') }}</a-button>
            <a-button type="link" size="small" :loading="runningId === record.id" @click="handleRun(asPlan(record))">{{ t('plan.actions.run') }}</a-button>
            <a-button type="link" size="small" @click="viewRuns(asPlan(record))">{{ t('plan.actions.records') }}</a-button>
            <a-popconfirm :title="t('plan.confirm_delete_one')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('plan.actions.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? t('plan.edit_full') : t('plan.new_full')"
      :confirm-loading="saving"
      width="640px"
      @ok="handleSave"
    >
      <a-alert
        v-if="hermesDraftLoaded"
        type="info"
        show-icon
        :message="t('plan.hermes_draft_imported')"
        :description="t('plan.hermes_draft_imported_hint', hermesDraftScope)"
        style="margin-bottom: 16px"
      />
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('plan.form.name')" :rules="[{ required: true }]">
          <a-input v-model:value="form.name" :placeholder="t('plan.form.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('case.drawer.optional')" />
        </a-form-item>

        <a-form-item :label="t('plan.form.suites')">
          <a-select
            v-model:value="selectedSuiteIds"
            mode="multiple"
            :placeholder="t('plan.form.select_suites')"
            :options="suiteOptions"
            :loading="suitesLoading"
            style="width: 100%"
          />
        </a-form-item>

        <a-divider orientation="left" style="font-size: 13px">{{ t('plan.form.schedule_config') }}</a-divider>
        <a-form-item :label="t('plan.form.schedule_type')">
          <a-radio-group v-model:value="form.schedule_type">
            <a-radio-button value="manual">{{ t('plan.schedule_types.manual_trigger') }}</a-radio-button>
            <a-radio-button value="cron">{{ t('plan.schedule_types.cron_full') }}</a-radio-button>
            <a-radio-button value="webhook">Webhook</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <template v-if="form.schedule_type === 'cron'">
          <a-form-item :label="t('plan.form.config_mode')">
            <a-radio-group v-model:value="cronMode">
              <a-radio-button value="daily">{{ t('plan.cron_modes.daily') }}</a-radio-button>
              <a-radio-button value="weekly">{{ t('plan.cron_modes.weekly') }}</a-radio-button>
              <a-radio-button value="custom">{{ t('plan.cron_modes.custom') }}</a-radio-button>
            </a-radio-group>
          </a-form-item>

          <a-row v-if="cronMode === 'daily'" :gutter="12">
            <a-col :span="12">
              <a-form-item :label="t('plan.form.execution_hour')">
                <a-select v-model:value="cronHour" :options="hourOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('plan.form.execution_minute')">
                <a-select v-model:value="cronMinute" :options="minuteOptions" />
              </a-form-item>
            </a-col>
          </a-row>

          <template v-else-if="cronMode === 'weekly'">
            <a-form-item :label="t('plan.form.execution_weekday')">
              <a-select v-model:value="cronWeekday" :options="weekdayOptions" />
            </a-form-item>
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item :label="t('plan.form.execution_hour')">
                  <a-select v-model:value="cronHour" :options="hourOptions" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item :label="t('plan.form.execution_minute')">
                  <a-select v-model:value="cronMinute" :options="minuteOptions" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <a-form-item v-else :label="t('plan.form.cron_expression')">
            <a-input v-model:value="customCronExpression" placeholder="*/30 * * * *" />
            <div class="cron-help-text">
              {{ t('plan.form.cron_help') }}
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
            :message="t('plan.form.cron_preview', { expression: cronPreviewExpression })"
            :description="cronDescription"
          />
        </template>

        <a-form-item v-if="form.schedule_type === 'webhook' && editingPlan?.webhook_secret" label="Webhook Secret">
          <a-input-group compact>
            <a-input :value="editingPlan.webhook_secret" readonly style="width: calc(100% - 80px); font-family: monospace; font-size: 12px" />
            <a-button @click="copySecret">{{ t('plan.form.copy_secret') }}</a-button>
          </a-input-group>
          <div class="cron-help-text">
            {{ t('plan.form.webhook_secret_hint', { secret: editingPlan.webhook_secret?.slice(0, 8) }) }}
          </div>
        </a-form-item>

        <a-form-item :label="t('plan.form.default_environment')">
          <a-select
            v-model:value="(form.env_id as number | undefined)"
            :placeholder="t('plan.form.no_environment')"
            allow-clear
            style="width: 100%"
            :options="envOptions"
            :loading="envLoading"
          />
        </a-form-item>

        <a-form-item :label="t('plan.form.enable_schedule')">
          <a-switch v-model:checked="form.is_enabled" />
        </a-form-item>

        <a-form-item :label="t('plan.form.auto_create_bugs')">
          <a-switch v-model:checked="form.auto_create_bugs" />
        </a-form-item>

        <a-form-item :label="t('plan.form.execution_strategy')">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item :label="t('plan.form.execution_mode')">
                <a-select v-model:value="form.config.execution_mode" :options="planExecutionModeOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('plan.form.fail_strategy')">
                <a-select v-model:value="form.config.fail_strategy" :options="planFailStrategyOptions" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-row v-if="form.config.execution_mode === 'parallel' || form.config.fail_strategy === 'require-minimum-pass-rate'" :gutter="16">
            <a-col v-if="form.config.execution_mode === 'parallel'" :span="12">
              <a-form-item :label="t('plan.form.max_workers')">
                <a-input-number
                  v-model:value="form.config.max_workers"
                  :min="1"
                  :max="10"
                  :precision="0"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
            <a-col v-if="form.config.fail_strategy === 'require-minimum-pass-rate'" :span="12">
              <a-form-item :label="t('plan.form.min_pass_rate')">
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
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="runsOpen" :title="t('plan.runs_modal_title')" width="800px" :footer="null">
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
          <div class="aggregate-report-panel auto-bugs-panel">
            <div class="aggregate-report-title">{{ t('plan.report.title') }}</div>
            <div class="aggregate-report-grid">
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('plan.report.pass_rate') }}</div>
                <div class="aggregate-report-value">{{ formatPercent(getPlanRunPassRate(record)) }}</div>
              </div>
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('plan.report.failures') }}</div>
                <div class="aggregate-report-value danger">{{ getPlanRunFailureCount(record) }}</div>
              </div>
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('plan.report.duration') }}</div>
                <div class="aggregate-report-value">{{ formatDuration(record.duration_ms) }}</div>
              </div>
              <div class="aggregate-report-card">
                <div class="aggregate-report-label">{{ t('plan.report.related_suites') }}</div>
                <div class="aggregate-report-value">{{ record.suite_run_ids?.length ?? 0 }}</div>
              </div>
            </div>
            <div class="aggregate-report-section">
              <div class="aggregate-report-subtitle">{{ t('plan.report.failure_top') }}</div>
              <a-empty v-if="!getPlanRunFailureItems(record).length" :description="t('plan.report.no_failures')" :image="false" />
              <a-list v-else size="small" :data-source="getPlanRunFailureItems(record).slice(0, 5)">
                <template #renderItem="{ item }">
                  <a-list-item>
                    <a-space direction="vertical" :size="2" style="width: 100%">
                      <span>
                        <a-tag :color="String(item.status) === 'failed' ? 'red' : 'orange'">{{ item.status }}</a-tag>
                        {{ getSuiteRunReportName(item) }}
                      </span>
                      <span class="aggregate-report-reason">{{ getSuiteRunReportReason(item) }}</span>
                    </a-space>
                  </a-list-item>
                </template>
              </a-list>
            </div>
            <div class="aggregate-report-section">
              <div class="aggregate-report-subtitle">{{ t('plan.report.suite_details') }}</div>
              <a-table
                :columns="planRunSuiteColumns"
                :data-source="record.suite_run_ids"
                row-key="suite_run_id"
                size="small"
                :pagination="false"
                :scroll="{ x: 520 }"
              >
                <template #bodyCell="{ column, record: suiteRun }">
                  <template v-if="column.key === 'status'">
                    <a-tag :color="String(suiteRun.status) === 'passed' ? 'green' : String(suiteRun.status) === 'failed' ? 'red' : String(suiteRun.status) === 'error' ? 'orange' : 'default'">{{ suiteRun.status }}</a-tag>
                  </template>
                  <template v-if="column.key === 'suite_run_id'">
                    <span>{{ suiteRun.suite_run_id ?? '-' }}</span>
                  </template>
                  <template v-if="column.key === 'reason'">
                    <span class="aggregate-report-reason">{{ getSuiteRunReportReason(suiteRun) }}</span>
                  </template>
                  <template v-if="column.key === 'action'">
                    <a-button
                      type="link"
                      size="small"
                      :disabled="!positiveInt(suiteRun.suite_run_id)"
                      @click="openSuiteRun(suiteRun)"
                    >
                      {{ t('common.view_detail') }}
                    </a-button>
                  </template>
                </template>
              </a-table>
            </div>
            <div class="aggregate-report-section">
            <template v-if="record.result_summary?.auto_bugs_error">
              <a-alert type="error" show-icon :message="record.result_summary.auto_bugs_error" />
            </template>
            <template v-else-if="record.result_summary?.auto_bugs?.length">
              <div class="auto-bugs-title">{{ t('plan.auto_bugs.title') }}</div>
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
                    <a-tag :color="autoBug.duplicate ? 'orange' : 'green'">{{ autoBug.duplicate ? t('plan.auto_bugs.duplicate_yes') : t('plan.auto_bugs.duplicate_no') }}</a-tag>
                  </template>
                  <template v-if="column.key === 'attachment_uploaded'">
                    <a-tag :color="autoBug.attachment_uploaded ? 'blue' : 'default'">{{ autoBug.attachment_uploaded ? t('plan.auto_bugs.attachment_yes') : t('plan.auto_bugs.attachment_no') }}</a-tag>
                  </template>
                </template>
              </a-table>
            </template>
            <template v-else>
              <a-empty :description="t('plan.auto_bugs.empty')" :image="false" />
            </template>
            </div>
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
              {{ t('plan.runs_summary', { passed: record.result_summary.passed || 0, total: record.result_summary.total || 0 }) }}
            </span>
          </template>
          <template v-if="column.key === 'auto_bugs'">
            <a-tag v-if="record.result_summary?.auto_bugs_error" color="red">{{ t('plan.auto_bugs.error_tag') }}</a-tag>
            <a-tag v-else-if="record.result_summary?.auto_bugs?.length" color="blue">{{ t('plan.auto_bugs.count_tag', { count: record.result_summary.auto_bugs.length }) }}</a-tag>
            <span v-else style="color: var(--c-text-tertiary)">-</span>
          </template>
          <template v-if="column.key === 'duration_ms'">
            {{ formatDuration(record.duration_ms) }}
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
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import type {
  EnvironmentItem,
  PlanItem,
  PlanRunItem,
  ProjectItem,
  ScheduleType,
  SuiteExecutionMode,
  SuiteFailStrategy,
  SuiteItem,
} from '@/api'
import { environmentApi, planApi, projectApi, suiteApi } from '@/api'
import BatchOperationBar from '@/components/common/BatchOperationBar.vue'
import { projectIdFromQuery, selectAvailableProjectId } from '@/utils/projectContext'
import {
  buildPlanMutationPayload,
  createDefaultPlanConfig,
  formatDuration,
  formatPercent,
  getCronValidationErrorKey,
  getPlanRunFailureCount,
  getPlanRunFailureItems,
  getPlanRunPassRate,
  getPlanSaveValidationError,
  normalizePlanConfig,
  buildCronExpression,
  formatCronTime,
  parseCronPreset,
  runStatusColor,
  scheduleColor,
  type CronMode,
} from '@/utils/planList'

// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asPlan = (record: unknown) => record as PlanItem

const { t } = useI18n()
const router = useRouter()

type SelectOption = { label: string; value: number }
type HermesPlanDraftHandoff = {
  projectId: number
  name: string
  objective: string
  testPoints: string[]
  moduleIds: number[]
  caseIds: number[]
  regressionTaskIds: string[]
}
type HermesDraftScopeSummary = {
  modules: number
  cases: number
  regressions: number
}

const planExecutionModeOptions = computed<Array<{ label: string; value: SuiteExecutionMode }>>(() => [
  { label: t('suite.execution_modes.sequential'), value: 'sequential' },
  { label: t('suite.execution_modes.parallel'), value: 'parallel' },
])

const planFailStrategyOptions = computed<Array<{ label: string; value: SuiteFailStrategy }>>(() => [
  { label: t('suite.fail_strategies.continue'), value: 'continue' },
  { label: t('suite.fail_strategies.fast-fail'), value: 'fast-fail' },
  { label: t('suite.fail_strategies.require-minimum-pass-rate'), value: 'require-minimum-pass-rate' },
])

function weekdayLabel(day: number) {
  return t(`plan.weekdays.${day}`)
}

const weekdayOptions = computed(() => Array.from({ length: 7 }, (_, value) => ({
  label: weekdayLabel(value),
  value,
})))
const hourOptions = computed(() => Array.from({ length: 24 }, (_, value) => ({
  label: t('plan.form.hour_option', { value: String(value).padStart(2, '0') }),
  value,
})))
const minuteOptions = computed(() => Array.from({ length: 60 }, (_, value) => ({
  label: t('plan.form.minute_option', { value: String(value).padStart(2, '0') }),
  value,
})))

function getErrorMessage(error: unknown, fallback: string) {
  return typeof error === 'string' ? error : fallback
}

function positiveInt(value: unknown) {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ') ?? '-'
}

function validateCronExpression(expression: string) {
  const errorKey = getCronValidationErrorKey(expression)
  return errorKey ? t(`plan.cron_errors.${errorKey}`) : ''
}

const plans = ref<PlanItem[]>([])
const loading = ref(false)
const selectedRowKeys = ref<number[]>([])
const projectId = ref<number | undefined>(undefined)
const route = useRoute()
const projectOptions = ref<SelectOption[]>([])

const formOpen = ref(false)
const hermesDraftLoaded = ref(false)
const hermesDraftScope = ref<HermesDraftScopeSummary>({ modules: 0, cases: 0, regressions: 0 })
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
  config: createDefaultPlanConfig(),
})

const cronMode = ref<CronMode>('daily')
const cronHour = ref(9)
const cronMinute = ref(0)
const cronWeekday = ref(1)
const customCronExpression = ref('')

const cronPreviewExpression = computed(() => {
  if (form.value.schedule_type !== 'cron') return ''
  return buildCronExpression({
    mode: cronMode.value,
    hour: cronHour.value,
    minute: cronMinute.value,
    weekday: cronWeekday.value,
    customExpression: customCronExpression.value,
  })
})

const cronValidationError = computed(() => {
  if (form.value.schedule_type !== 'cron') return ''
  return validateCronExpression(cronPreviewExpression.value)
})

const cronDescription = computed(() => {
  if (form.value.schedule_type !== 'cron') return ''
  if (cronValidationError.value) return t('plan.cron_descriptions.fix_first')
  const time = formatCronTime(cronHour.value, cronMinute.value)
  if (cronMode.value === 'daily') return t('plan.cron_descriptions.daily', { time })
  if (cronMode.value === 'weekly') return t('plan.cron_descriptions.weekly', { weekday: weekdayLabel(cronWeekday.value), time })
  return t('plan.cron_descriptions.custom')
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

const columns = computed(() => [
  { title: t('plan.columns.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('plan.columns.schedule_type'), key: 'schedule_type', width: 160 },
  { title: t('plan.columns.suites'), key: 'suites', width: 90 },
  { title: t('plan.columns.enabled'), key: 'is_enabled', width: 80 },
  { title: t('plan.columns.next_run_at'), key: 'next_run_at', width: 170 },
  { title: t('plan.columns.action'), key: 'action', width: 220, fixed: 'right' as const },
])

const runColumns = computed(() => [
  { title: t('plan.runs_columns.id'), dataIndex: 'id', width: 60 },
  { title: t('plan.runs_columns.trigger_type'), key: 'trigger_type', width: 100 },
  { title: t('plan.runs_columns.status'), key: 'status', width: 90 },
  { title: t('plan.runs_columns.summary'), key: 'summary', width: 120 },
  { title: t('plan.runs_columns.auto_bugs'), key: 'auto_bugs', width: 120 },
  { title: t('plan.runs_columns.duration_ms'), key: 'duration_ms', width: 90 },
  {
    title: t('plan.runs_columns.time'),
    dataIndex: 'created_at',
    width: 170,
    customRender: ({ text }: { text?: string }) => formatTime(text ?? ''),
  },
  { title: t('plan.runs_columns.export'), key: 'export', width: 160 },
])

const autoBugColumns = computed(() => [
  { title: t('plan.auto_bugs.col_case_id'), dataIndex: 'case_id', key: 'case_id', width: 90 },
  { title: t('plan.auto_bugs.col_bug_id'), key: 'bug_id', width: 180 },
  { title: t('plan.auto_bugs.col_duplicate'), key: 'duplicate', width: 100 },
  { title: t('plan.auto_bugs.col_attachment'), key: 'attachment_uploaded', width: 100 },
])

const planRunSuiteColumns = computed(() => [
  { title: t('plan.report.columns.suite_id'), dataIndex: 'suite_id', key: 'suite_id', width: 100 },
  { title: t('plan.report.columns.suite_run_id'), key: 'suite_run_id', width: 120 },
  { title: t('plan.report.columns.status'), key: 'status', width: 100 },
  { title: t('plan.report.columns.reason'), key: 'reason', width: 220 },
  { title: t('common.action'), key: 'action', width: 100 },
])

function scheduleLabel(type: string) {
  const key = `plan.schedule_types.${type}`
  const translated = t(key)
  return translated === key ? type : translated
}
function getSuiteRunReportName(item: Record<string, unknown>) {
  return String(item.suite_name || t('plan.report.suite_fallback', { id: item.suite_id ?? '-' }))
}

function getSuiteRunReportReason(item: Record<string, unknown>) {
  return String(item.error_message || item.error || item.reason || t('plan.report.no_reason'))
}

function openSuiteRun(item: Record<string, unknown>) {
  const runId = positiveInt(item.suite_run_id)
  if (!runId) return
  const query: Record<string, string> = { run_id: String(runId) }
  if (projectId.value) query.project_id = String(projectId.value)
  void router.push({ path: '/suites', query })
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
    projectId.value = selectAvailableProjectId(projectIdFromQuery(route.query.project_id), projects)
    await loadPlans()
    await openRequestedRun()
    applyHermesDraft()
  } catch (error: unknown) {
    projectOptions.value = []
    message.error(getErrorMessage(error, t('plan.msg.load_projects_failed')))
  }
})

function boundedStringArray(value: unknown, max: number) {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => item.trim().slice(0, 512))
    .slice(0, max)
}

function boundedNumberArray(value: unknown, max: number) {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is number => Number.isInteger(item) && item > 0)
    .slice(0, max)
}

function readHermesPlanDraft(): HermesPlanDraftHandoff | null {
  if (route.query.hermes_draft !== '1' || typeof window === 'undefined') return null
  const raw = window.history.state?.hermesPlanDraft
  if (!raw || typeof raw !== 'object') return null
  const value = raw as Record<string, unknown>
  const draftProjectId = positiveInt(value.projectId)
  const name = typeof value.name === 'string' ? value.name.trim().slice(0, 256) : ''
  if (!draftProjectId || !name) return null
  return {
    projectId: draftProjectId,
    name,
    objective: typeof value.objective === 'string' ? value.objective.trim().slice(0, 2000) : '',
    testPoints: boundedStringArray(value.testPoints, 16),
    moduleIds: boundedNumberArray(value.moduleIds, 16),
    caseIds: boundedNumberArray(value.caseIds, 16),
    regressionTaskIds: boundedStringArray(value.regressionTaskIds, 16),
  }
}

function clearHermesDraftMarker() {
  const query = { ...route.query }
  delete query.hermes_draft
  void router.replace({ query })
}

function applyHermesDraft() {
  if (route.query.hermes_draft !== '1') return
  const draft = readHermesPlanDraft()
  if (!draft || draft.projectId !== projectId.value) {
    clearHermesDraftMarker()
    return
  }
  openCreate()
  form.value.name = draft.name
  form.value.description = [draft.objective, ...draft.testPoints.map((point) => `• ${point}`)].filter(Boolean).join('\n')
  hermesDraftScope.value = {
    modules: draft.moduleIds.length,
    cases: draft.caseIds.length,
    regressions: draft.regressionTaskIds.length,
  }
  hermesDraftLoaded.value = true
  clearHermesDraftMarker()
}

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
    message.error(getErrorMessage(error, t('plan.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

async function handleBatchDelete() {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await planApi.batchDelete(selectedRowKeys.value)
    message.success(t('plan.msg.batch_delete_success', { processed: result.processed, requested: result.requested }))
    selectedRowKeys.value = []
    await loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('plan.msg.batch_delete_failed')))
  }
}

async function handleBatchToggle(isEnabled: boolean) {
  if (!selectedRowKeys.value.length) return
  try {
    const result = await planApi.batchToggle(selectedRowKeys.value, isEnabled)
    message.success(
      t('plan.msg.batch_toggle_success', {
        action: isEnabled ? t('common.enabled') : t('common.disabled'),
        processed: result.processed,
        requested: result.requested,
      }),
    )
    selectedRowKeys.value = []
    await loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('plan.msg.batch_toggle_failed')))
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
    message.error(getErrorMessage(error, t('plan.msg.load_suites_failed')))
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
    message.error(getErrorMessage(error, t('plan.msg.load_envs_failed')))
  } finally {
    envLoading.value = false
  }
}

function openCreate() {
  isEdit.value = false
  editingPlan.value = null
  form.value = {
    name: '',
    description: '',
    schedule_type: 'manual',
    cron_expression: '',
    is_enabled: true,
    auto_create_bugs: false,
    env_id: null,
    config: createDefaultPlanConfig(),
  }
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
    config: normalizePlanConfig(record.config ?? null),
  }
  resetCronEditor(record.cron_expression)
  selectedSuiteIds.value = (record.suite_ids || []).map((s) => s.suite_id)
  formOpen.value = true
  loadSuites()
  loadEnvs()
}

async function handleSave() {
  const validationError = getPlanSaveValidationError(
    form.value,
    selectedSuiteIds.value,
    cronValidationError.value,
  )
  if (validationError === 'name') {
    message.warning(t('plan.msg.name_required'))
    return
  }
  if (validationError === 'suite') {
    message.warning(t('plan.msg.suite_required'))
    return
  }
  if (validationError === 'cron') {
    message.warning(cronValidationError.value)
    return
  }
  if (form.value.schedule_type === 'cron') {
    form.value.cron_expression = cronPreviewExpression.value
  }

  saving.value = true
  try {
    const payload = buildPlanMutationPayload(form.value, selectedSuiteIds.value)
    if (isEdit.value && editingPlan.value) {
      await planApi.update(editingPlan.value.id, payload)
    } else {
      await planApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? t('plan.msg.update_success') : t('plan.msg.create_success'))
    formOpen.value = false
    void loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('plan.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function handleRun(record: PlanItem) {
  runningId.value = record.id
  try {
    await planApi.run(record.id)
    message.success(t('plan.msg.run_started'))
    void loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('plan.msg.run_failed')))
  } finally {
    runningId.value = null
  }
}

async function handleDelete(id: number) {
  try {
    await planApi.delete(id)
    message.success(t('plan.msg.delete_success'))
    void loadPlans()
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('plan.msg.delete_failed')))
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
    message.error(getErrorMessage(error, t('plan.msg.load_runs_failed')))
  } finally {
    runsLoading.value = false
  }
}

async function openRequestedRun() {
  const runId = positiveInt(route.query.run_id)
  if (!runId) return
  try {
    const run = await planApi.getRun(runId)
    const plan = plans.value.find((item) => item.id === run.plan_id)
    if (!plan) return
    await viewRuns(plan)
    expandedRunKeys.value = [runId]
  } catch (error: unknown) {
    message.error(getErrorMessage(error, t('plan.msg.load_runs_failed')))
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
    message.error(getErrorMessage(error, t('plan.msg.export_html_failed')))
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
    message.error(getErrorMessage(error, t('plan.msg.export_pdf_failed')))
  } finally {
    exportingPlanRunPdfId.value = null
  }
}

function copySecret() {
  if (editingPlan.value?.webhook_secret) {
    navigator.clipboard.writeText(editingPlan.value.webhook_secret)
    message.success(t('plan.msg.secret_copied'))
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
  color: var(--c-text-tertiary);
}

.auto-bugs-panel {
  padding: 8px 0;
}

.auto-bugs-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--c-text-secondary);
}
</style>
