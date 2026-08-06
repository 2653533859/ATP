<template>
  <div class="performance-center">
    <div class="header">
      <div>
        <h2>{{ t('performance.title') }}</h2>
        <div class="subtitle">{{ t('performance.subtitle') }}</div>
      </div>
      <a-space>
        <a-select
          v-model:value="(projectId as number | undefined)"
          :options="projectOptions"
          :placeholder="t('performance.select_project')"
          style="width: 240px"
          @change="handleProjectChange"
        />
        <a-button :loading="loading" @click="refreshAll">
          <template #icon><ReloadOutlined /></template>
          {{ t('common.refresh') }}
        </a-button>
        <a-button type="primary" :disabled="!projectId" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          {{ t('performance.create') }}
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="testColumns"
      :data-source="tests"
      :loading="loading"
      :pagination="false"
      row-key="id"
      :locale="{ emptyText: t('performance.empty_tests') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div class="primary-text">{{ record.name }}</div>
          <div class="muted mono">{{ record.script_object_name }}</div>
        </template>
        <template v-else-if="column.key === 'executor'">
          <a-tag color="blue">{{ record.executor }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space>
            <a-tooltip :title="t('performance.run')">
              <a-button size="small" type="primary" @click="openRun(asPerfTest(record))">
                <template #icon><PlayCircleOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-tooltip :title="t('common.edit')">
              <a-button size="small" @click="openEdit(asPerfTest(record))">
                <template #icon><EditOutlined /></template>
              </a-button>
            </a-tooltip>
          </a-space>
        </template>
      </template>
    </a-table>

    <div class="insight-grid">
      <div class="insight-panel">
        <div class="section-title">{{ t('performance.trend_title') }}</div>
        <v-chart class="trend-chart" :option="trendOption" :theme="chartTheme" autoresize />
      </div>
      <div class="insight-panel">
        <div class="section-title">{{ t('performance.compare_title') }}</div>
        <a-alert
          v-if="compareRows.length < 2"
          type="info"
          show-icon
          :message="t('performance.compare_hint')"
        />
        <a-table
          v-else
          size="small"
          :columns="compareColumns"
          :data-source="compareRows"
          :pagination="false"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'delta'">
              <span :class="record.deltaClass">{{ record.delta }}</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>

    <div class="section-title">{{ t('performance.runs_title') }}</div>
    <a-table
      :columns="runColumns"
      :data-source="runs"
      :loading="runsLoading"
      :pagination="{ pageSize: 10 }"
      :row-selection="runRowSelection"
      row-key="id"
      :locale="{ emptyText: t('performance.empty_runs') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'metrics'">
          <a-space wrap>
            <a-statistic :title="t('performance.rps')" :value="metricValue(record.summary.rps)" :precision="2" />
            <a-statistic :title="t('performance.p95')" :value="metricValue(record.summary.p95_ms)" :precision="0" suffix="ms" />
            <a-statistic :title="t('performance.error_rate')" :value="percentValue(record.summary.error_rate)" :precision="2" suffix="%" />
          </a-space>
        </template>
        <template v-else-if="column.key === 'duration'">
          {{ formatDuration(record.duration_ms) }}
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-tooltip :title="t('common.view_detail')">
            <a-button size="small" @click="openRunDetail(asPerfRun(record))">
              <template #icon><FileSearchOutlined /></template>
            </a-button>
          </a-tooltip>
        </template>
      </template>
    </a-table>

    <a-drawer
      v-model:open="editorOpen"
      :title="editing ? t('performance.edit_title') : t('performance.create_title')"
      :width="680"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      @ok="saveTest"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('performance.name')" required>
          <a-input v-model:value="testForm.name" :placeholder="t('performance.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('performance.description')">
          <a-textarea v-model:value="testForm.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('performance.creation_mode')">
          <a-radio-group v-model:value="testForm.mode" button-style="solid">
            <a-radio-button value="visual">{{ t('performance.visual_mode') }}</a-radio-button>
            <a-radio-button value="script">{{ t('performance.script_mode') }}</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <template v-if="testForm.mode === 'visual'">
          <a-alert
            type="info"
            show-icon
            :message="t('performance.visual_hint')"
            class="form-alert"
          />
          <a-form-item :label="t('performance.load_template')">
            <a-select
              v-model:value="testForm.scenario.loadTemplate"
              :options="loadTemplateOptions"
              @change="applyLoadTemplate"
            />
          </a-form-item>
          <a-row :gutter="12">
            <a-col :span="7">
              <a-form-item :label="t('performance.request_method')">
                <a-select v-model:value="testForm.scenario.method" :options="methodOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="17">
              <a-form-item :label="t('performance.request_url')" required>
                <a-input v-model:value="testForm.scenario.url" placeholder="https://example.test/api/health" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item :label="t('performance.request_headers')">
            <KvEditor v-model:value="testForm.scenario.headers" />
          </a-form-item>
          <a-form-item :label="t('performance.request_params')">
            <KvEditor v-model:value="testForm.scenario.params" />
          </a-form-item>
          <a-row :gutter="12">
            <a-col :span="8">
              <a-form-item :label="t('performance.body_type')">
                <a-select v-model:value="testForm.scenario.bodyType" :options="bodyTypeOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="16">
              <a-form-item :label="t('performance.expected_status')">
                <a-input-number v-model:value="testForm.scenario.expectedStatus" :min="100" :max="599" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item v-if="testForm.scenario.bodyType !== 'none'" :label="t('performance.request_body')">
            <a-textarea v-model:value="testForm.scenario.body" :rows="5" class="mono" />
          </a-form-item>
          <a-form-item :label="t('performance.auth_type')">
            <a-select v-model:value="testForm.scenario.authType" :options="authTypeOptions" />
          </a-form-item>
          <a-row v-if="testForm.scenario.authType === 'bearer'" :gutter="12">
            <a-col :span="24">
              <a-form-item :label="t('performance.token_variable')">
                <a-input v-model:value="testForm.scenario.bearerTokenKey" placeholder="API_TOKEN" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-row v-if="testForm.scenario.authType === 'basic'" :gutter="12">
            <a-col :span="12">
              <a-form-item :label="t('performance.username_variable')">
                <a-input v-model:value="testForm.scenario.basicUsernameKey" placeholder="API_USERNAME" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('performance.password_variable')">
                <a-input v-model:value="testForm.scenario.basicPasswordKey" placeholder="API_PASSWORD" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item :label="t('performance.body_contains')">
            <a-input v-model:value="testForm.scenario.bodyContains" :placeholder="t('performance.body_contains_placeholder')" />
          </a-form-item>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item :label="t('performance.p95_threshold')">
                <a-input-number v-model:value="testForm.scenario.p95ThresholdMs" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item :label="t('performance.error_threshold')">
                <a-input-number v-model:value="testForm.scenario.errorRateThresholdPercent" :min="0" :max="100" :step="0.1" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
          <div v-if="testForm.scenario.stages.length" class="stages-editor">
            <div class="section-label">{{ t('performance.stages') }}</div>
            <div v-for="(stage, index) in testForm.scenario.stages" :key="index" class="stage-row">
              <a-input v-model:value="stage.duration" :placeholder="t('performance.stage_duration')" />
              <a-input-number v-model:value="stage.target" :min="0" :placeholder="t('performance.stage_target')" />
              <a-button type="text" danger @click="removeStage(index)">{{ t('common.delete') }}</a-button>
            </div>
            <a-button type="dashed" block @click="addStage">{{ t('performance.add_stage') }}</a-button>
          </div>
        </template>
        <template v-else>
          <a-form-item :label="t('performance.script_object_name')" required>
            <a-space-compact class="script-input">
              <a-input v-model:value="testForm.script_object_name" class="mono" :placeholder="t('performance.script_placeholder')" />
              <a-upload
                accept=".js,.mjs"
                :before-upload="uploadScript"
                :show-upload-list="false"
              >
                <a-button :loading="scriptUploading">
                  <template #icon><UploadOutlined /></template>
                  {{ t('performance.upload_script') }}
                </a-button>
              </a-upload>
            </a-space-compact>
          </a-form-item>
          <a-form-item :label="t('performance.default_options')">
            <a-textarea v-model:value="testForm.defaultOptionsText" class="mono" :rows="10" />
          </a-form-item>
        </template>
      </a-form>
    </a-drawer>

    <a-modal
      v-model:open="runOpen"
      :title="t('performance.run_title')"
      :ok-text="t('performance.run')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="triggering"
      @ok="triggerRun"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('performance.environment')">
          <a-select
            v-model:value="runForm.environment_id"
            :options="environmentOptions"
            allow-clear
            :placeholder="t('performance.no_environment')"
          />
          <div class="field-hint">{{ t('performance.environment_hint') }}</div>
        </a-form-item>
        <a-form-item :label="t('performance.run_options')">
          <a-textarea v-model:value="runForm.optionsText" class="mono" :rows="8" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer v-model:open="detailOpen" :title="t('performance.run_detail')" :width="720">
      <template v-if="selectedRun">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="ID">{{ selectedRun.id }}</a-descriptions-item>
          <a-descriptions-item :label="t('common.status')">
            <a-tag :color="statusColor(selectedRun.status)">{{ statusLabel(selectedRun.status) }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="t('performance.rps')">{{ displayMetric(selectedRun.summary.rps) }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.p95')">{{ displayMetric(selectedRun.summary.p95_ms, 'ms') }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.p99')">{{ displayMetric(selectedRun.summary.p99_ms, 'ms') }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.error_rate')">
            {{ displayPercent(selectedRun.summary.error_rate) }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('performance.duration')">{{ formatDuration(selectedRun.duration_ms) }}</a-descriptions-item>
          <a-descriptions-item :label="t('performance.raw_result')">
            <a-space v-if="selectedRun.raw_result_object_name">
              <span class="mono">{{ selectedRun.raw_result_object_name }}</span>
              <a-button type="link" size="small" @click="openRawResult(selectedRun)">
                <template #icon><DownloadOutlined /></template>
                {{ t('performance.open_raw_result') }}
              </a-button>
            </a-space>
            <span v-else>-</span>
          </a-descriptions-item>
        </a-descriptions>
        <div v-if="selectedRun.error_message" class="detail-block">
          <a-alert type="error" :message="selectedRun.error_message" show-icon />
        </div>
        <div class="detail-block">
          <div class="section-label">{{ t('performance.thresholds') }}</div>
          <a-empty v-if="thresholdRows.length === 0" :description="t('performance.no_thresholds')" />
          <a-table
            v-else
            :columns="thresholdColumns"
            :data-source="thresholdRows"
            :pagination="false"
            size="small"
            row-key="key"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'ok'">
                <a-tag :color="record.ok ? 'success' : 'error'">
                  {{ record.ok ? t('performance.threshold_passed') : t('performance.threshold_failed') }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </div>
        <div class="detail-block">
          <div class="section-label">{{ t('performance.summary_json') }}</div>
          <pre class="json-preview">{{ JSON.stringify(selectedRun.summary, null, 2) }}</pre>
        </div>
        <div class="detail-block">
          <div class="section-label">{{ t('performance.options_snapshot') }}</div>
          <pre class="json-preview">{{ JSON.stringify(selectedRun.options_snapshot, null, 2) }}</pre>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { DownloadOutlined, EditOutlined, FileSearchOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  environmentApi,
  performanceApi,
  projectApi,
  type EnvironmentItem,
  type PerformanceRunItem,
  type PerformanceTestItem,
  type ProjectItem,
} from '@/api'
import KvEditor from '@/components/common/KvEditor.vue'
import { useChartTheme } from '@/utils/chartTheme'
import {
  applyPerformanceLoadTemplate,
  buildPerformanceOptions,
  createDefaultPerformanceScenario,
  generatePerformanceK6Script,
  type PerformanceLoadTemplate,
  type PerformanceScenario,
} from '@/utils/performanceScriptGenerator'
// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asPerfTest = (record: unknown) => record as PerformanceTestItem
const asPerfRun = (record: unknown) => record as PerformanceRunItem

const { t } = useI18n()
const { chartTheme } = useChartTheme()

const projectId = ref<number | null>(null)
const projectOptions = ref<{ label: string; value: number }[]>([])
const environmentOptions = ref<{ label: string; value: number }[]>([])
const tests = ref<PerformanceTestItem[]>([])
const runs = ref<PerformanceRunItem[]>([])
const loading = ref(false)
const runsLoading = ref(false)
const editorOpen = ref(false)
const runOpen = ref(false)
const detailOpen = ref(false)
const triggering = ref(false)
const scriptUploading = ref(false)
const editing = ref<PerformanceTestItem | null>(null)
const runTarget = ref<PerformanceTestItem | null>(null)
const selectedRun = ref<PerformanceRunItem | null>(null)
const selectedRunIds = ref<number[]>([])

type PerformanceCreationMode = 'visual' | 'script'

const loadTemplateOptions = computed(() => [
  { label: t('performance.template_smoke'), value: 'smoke' },
  { label: t('performance.template_load'), value: 'load' },
  { label: t('performance.template_stress'), value: 'stress' },
  { label: t('performance.template_spike'), value: 'spike' },
  { label: t('performance.template_soak'), value: 'soak' },
])

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({ label: value, value }))
const bodyTypeOptions = computed(() => [
  { label: t('performance.body_none'), value: 'none' },
  { label: t('performance.body_json'), value: 'json' },
  { label: t('performance.body_text'), value: 'text' },
])
const authTypeOptions = computed(() => [
  { label: t('performance.auth_none'), value: 'none' },
  { label: t('performance.auth_bearer'), value: 'bearer' },
  { label: t('performance.auth_basic'), value: 'basic' },
])

const testForm = ref<{
  mode: PerformanceCreationMode
  name: string
  description: string
  script_object_name: string
  defaultOptionsText: string
  scenario: PerformanceScenario
}>({
  mode: 'visual',
  name: '',
  description: '',
  script_object_name: '',
  defaultOptionsText: '{\n  "env": {\n    "TARGET_URL": "https://example.test"\n  }\n}',
  scenario: createDefaultPerformanceScenario(),
})

const runForm = ref<{ environment_id?: number; optionsText: string }>({
  environment_id: undefined,
  optionsText: '{}',
})

const testColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: t('performance.name'), key: 'name' },
  { title: t('performance.executor'), key: 'executor', width: 100 },
  { title: t('common.updated_at'), dataIndex: 'updated_at', key: 'updated_at', width: 180 },
  { title: t('common.actions'), key: 'actions', width: 120 },
])

const runColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: t('performance.test_id'), dataIndex: 'performance_test_id', key: 'performance_test_id', width: 110 },
  { title: t('common.status'), key: 'status', width: 110 },
  { title: t('performance.metrics'), key: 'metrics', width: 360 },
  { title: t('performance.duration'), key: 'duration', width: 120 },
  { title: t('common.created_at'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('common.actions'), key: 'actions', width: 90 },
])

const compareColumns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 72 },
  { title: t('common.status'), key: 'status', width: 100 },
  { title: t('performance.rps'), dataIndex: 'rps', key: 'rps', width: 90 },
  { title: t('performance.p95'), dataIndex: 'p95', key: 'p95', width: 90 },
  { title: t('performance.p99'), dataIndex: 'p99', key: 'p99', width: 90 },
  { title: t('performance.error_rate'), dataIndex: 'errorRate', key: 'errorRate', width: 100 },
  { title: t('performance.duration'), dataIndex: 'duration', key: 'duration', width: 100 },
  { title: t('performance.delta_vs_base'), key: 'delta' },
])

const runRowSelection = computed(() => ({
  selectedRowKeys: selectedRunIds.value,
  onChange: (keys: Array<string | number>) => {
    selectedRunIds.value = keys.map(Number).filter(Number.isFinite).slice(-4)
  },
}))

const thresholdColumns = computed(() => [
  { title: t('performance.threshold_metric'), dataIndex: 'metric', key: 'metric' },
  { title: t('performance.threshold_rule'), dataIndex: 'rule', key: 'rule' },
  { title: t('performance.threshold_status'), key: 'ok', width: 120 },
])

const thresholdRows = computed(() => {
  const thresholds = selectedRun.value?.summary?.thresholds
  if (!thresholds || typeof thresholds !== 'object' || Array.isArray(thresholds)) {
    return []
  }
  const rows: Array<{ key: string; metric: string; rule: string; ok: boolean }> = []
  Object.entries(thresholds as Record<string, unknown>).forEach(([metric, rules]) => {
    if (!rules || typeof rules !== 'object' || Array.isArray(rules)) return
    Object.entries(rules as Record<string, unknown>).forEach(([rule, result]) => {
      const ok = typeof result === 'boolean'
        ? !result
        : !!(
          result
          && typeof result === 'object'
          && !Array.isArray(result)
          && (result as { ok?: unknown }).ok === true
        )
      rows.push({ key: `${metric}:${rule}`, metric, rule, ok })
    })
  })
  return rows
})

const trendRuns = computed(() => [...runs.value].reverse().filter((run) => run.status === 'success'))

const trendOption = computed<EChartsOption>(() => {
  const labels = trendRuns.value.map((run) => formatDateLabel(run.created_at))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: [t('performance.rps'), t('performance.p95'), t('performance.p99'), t('performance.error_rate')] },
    grid: { top: 42, right: 18, bottom: 32, left: 42 },
    xAxis: { type: 'category', data: labels },
    yAxis: [
      { type: 'value', name: t('performance.latency_axis') },
      { type: 'value', name: t('performance.error_axis'), min: 0, max: 100 },
    ],
    series: [
      { name: t('performance.rps'), type: 'line', smooth: true, data: trendRuns.value.map((run) => numericMetric(run.summary.rps)) },
      { name: t('performance.p95'), type: 'line', smooth: true, data: trendRuns.value.map((run) => numericMetric(run.summary.p95_ms)) },
      { name: t('performance.p99'), type: 'line', smooth: true, data: trendRuns.value.map((run) => numericMetric(run.summary.p99_ms)) },
      {
        name: t('performance.error_rate'),
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: trendRuns.value.map((run) => percentValue(run.summary.error_rate)),
      },
    ],
  }
})

const selectedCompareRuns = computed(() => {
  const byId = new Map(runs.value.map((run) => [run.id, run]))
  return selectedRunIds.value.map((id) => byId.get(id)).filter((run): run is PerformanceRunItem => !!run)
})

const compareRows = computed(() => {
  const base = selectedCompareRuns.value[0]
  const baseP95 = base ? numericMetric(base.summary.p95_ms) : null
  return selectedCompareRuns.value.map((run, index) => {
    const p95 = numericMetric(run.summary.p95_ms)
    const delta = index === 0 || baseP95 === null || p95 === null ? t('performance.baseline') : formatDelta(p95 - baseP95, 'ms')
    return {
      id: run.id,
      status: run.status,
      rps: displayMetric(run.summary.rps),
      p95: displayMetric(run.summary.p95_ms, 'ms'),
      p99: displayMetric(run.summary.p99_ms, 'ms'),
      errorRate: displayPercent(run.summary.error_rate),
      duration: formatDuration(run.duration_ms),
      delta,
      deltaClass: delta.startsWith('+') ? 'delta-bad' : delta.startsWith('-') ? 'delta-good' : 'muted',
    }
  })
})

async function loadProjects() {
  const items = await projectApi.list()
  projectOptions.value = items.map((project: ProjectItem) => ({ label: project.name, value: project.id }))
  if (!projectId.value && projectOptions.value.length) {
    projectId.value = projectOptions.value[0].value
    await refreshAll()
  }
}

async function handleProjectChange() {
  await refreshAll()
}

async function refreshAll() {
  await Promise.all([loadTests(), loadRuns(), loadEnvironments()])
}

async function loadTests() {
  if (!projectId.value) {
    tests.value = []
    return
  }
  loading.value = true
  try {
    tests.value = await performanceApi.listTests(projectId.value)
  } catch {
    message.error(t('performance.msg.load_tests_failed'))
  } finally {
    loading.value = false
  }
}

async function loadRuns() {
  if (!projectId.value) {
    runs.value = []
    return
  }
  runsLoading.value = true
  try {
    runs.value = await performanceApi.listRuns(projectId.value)
    selectedRunIds.value = selectedRunIds.value.filter((id) => runs.value.some((run) => run.id === id))
  } catch {
    message.error(t('performance.msg.load_runs_failed'))
  } finally {
    runsLoading.value = false
  }
}

async function loadEnvironments() {
  if (!projectId.value) {
    environmentOptions.value = []
    return
  }
  try {
    const items = await environmentApi.list(projectId.value)
    environmentOptions.value = items.map((env: EnvironmentItem) => ({ label: env.name, value: env.id }))
  } catch {
    environmentOptions.value = []
  }
}

function openCreate() {
  editing.value = null
  testForm.value = {
    mode: 'visual',
    name: '',
    description: '',
    script_object_name: '',
    defaultOptionsText: '{\n  "env": {\n    "TARGET_URL": "https://example.test"\n  }\n}',
    scenario: createDefaultPerformanceScenario(),
  }
  editorOpen.value = true
}

function openEdit(record: PerformanceTestItem) {
  editing.value = record
  const scenarioValue = record.default_options?.atp_scenario
  const visual = isPerformanceScenario(scenarioValue)
  testForm.value = {
    mode: visual ? 'visual' : 'script',
    name: record.name,
    description: record.description || '',
    script_object_name: record.script_object_name,
    defaultOptionsText: JSON.stringify(record.default_options || {}, null, 2),
    scenario: visual ? cloneScenario(scenarioValue) : createDefaultPerformanceScenario(),
  }
  editorOpen.value = true
}

function isPerformanceScenario(value: unknown): value is PerformanceScenario {
  return !!(
    value
    && typeof value === 'object'
    && !Array.isArray(value)
    && typeof (value as PerformanceScenario).url === 'string'
    && typeof (value as PerformanceScenario).method === 'string'
    && typeof (value as PerformanceScenario).loadTemplate === 'string'
  )
}

function cloneScenario(scenario: PerformanceScenario): PerformanceScenario {
  return {
    ...scenario,
    headers: { ...scenario.headers },
    params: { ...scenario.params },
    stages: (scenario.stages || []).map((stage) => ({ ...stage })),
  }
}

function applyLoadTemplate(value: unknown) {
  const template = String(value) as PerformanceLoadTemplate
  testForm.value.scenario = applyPerformanceLoadTemplate(testForm.value.scenario, template)
}

function addStage() {
  testForm.value.scenario.stages.push({ duration: '30s', target: 10 })
}

function removeStage(index: number) {
  testForm.value.scenario.stages.splice(index, 1)
}

function parseJsonObject(text: string, fallback: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(text || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      message.warning(fallback)
      return null
    }
    return value as Record<string, unknown>
  } catch {
    message.warning(fallback)
    return null
  }
}

async function saveTest() {
  if (!projectId.value) return
  const name = testForm.value.name.trim()
  if (!name) {
    message.warning(t('performance.msg.required'))
    return
  }

  let scriptObjectName = testForm.value.script_object_name.trim()
  let defaultOptions: Record<string, unknown> | null
  if (testForm.value.mode === 'visual') {
    if (!testForm.value.scenario.url.trim()) {
      message.warning(t('performance.msg.visual_required'))
      return
    }
    defaultOptions = buildPerformanceOptions(testForm.value.scenario)
    const filename = 'performance-' + slugify(name) + '.js'
    scriptUploading.value = true
    try {
      const script = generatePerformanceK6Script(testForm.value.scenario)
      const file = new File([script], filename, { type: 'application/javascript' })
      const result = await performanceApi.uploadScript(projectId.value, file)
      scriptObjectName = result.script_object_name
    } catch {
      message.error(t('performance.msg.upload_failed'))
      return
    } finally {
      scriptUploading.value = false
    }
  } else {
    if (!scriptObjectName) {
      message.warning(t('performance.msg.required'))
      return
    }
    defaultOptions = parseJsonObject(testForm.value.defaultOptionsText, t('performance.msg.options_invalid'))
    if (!defaultOptions) return
  }
  if (!defaultOptions) return

  try {
    if (editing.value) {
      await performanceApi.updateTest(editing.value.id, {
        name,
        description: testForm.value.description || null,
        script_object_name: scriptObjectName,
        default_options: defaultOptions,
      })
      message.success(t('performance.msg.update_success'))
    } else {
      await performanceApi.createTest({
        project_id: projectId.value,
        name,
        description: testForm.value.description || null,
        executor: 'k6',
        script_object_name: scriptObjectName,
        default_options: defaultOptions,
      })
      message.success(t('performance.msg.create_success'))
    }
    editorOpen.value = false
    await loadTests()
  } catch {
    message.error(t('performance.msg.save_failed'))
  }
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'scenario'
}

function isK6Script(file: File) {
  return /\.(mjs|js)$/i.test(file.name)
}

async function uploadScript(file: File) {
  if (!projectId.value) {
    message.warning(t('performance.msg.select_project_first'))
    return false
  }
  if (!isK6Script(file)) {
    message.warning(t('performance.msg.script_type_invalid'))
    return false
  }
  scriptUploading.value = true
  try {
    const result = await performanceApi.uploadScript(projectId.value, file)
    testForm.value.script_object_name = result.script_object_name
    message.success(t('performance.msg.upload_success'))
  } catch {
    message.error(t('performance.msg.upload_failed'))
  } finally {
    scriptUploading.value = false
  }
  return false
}

function openRun(record: PerformanceTestItem) {
  runTarget.value = record
  runForm.value = { environment_id: undefined, optionsText: '{}' }
  runOpen.value = true
}

async function triggerRun() {
  if (!runTarget.value) return
  const options = parseJsonObject(runForm.value.optionsText, t('performance.msg.options_invalid'))
  if (!options) return
  triggering.value = true
  try {
    const run = await performanceApi.triggerRun(runTarget.value.id, {
      environment_id: runForm.value.environment_id ?? null,
      options,
    })
    runOpen.value = false
    message.success(t('performance.msg.run_started', { id: run.id }))
    await loadRuns()
  } catch {
    message.error(t('performance.msg.run_failed'))
  } finally {
    triggering.value = false
  }
}

function openRunDetail(record: PerformanceRunItem) {
  selectedRun.value = record
  detailOpen.value = true
}

async function openRawResult(record: PerformanceRunItem) {
  try {
    const result = await performanceApi.getRawResult(record.id)
    window.open(result.url, '_blank', 'noopener,noreferrer')
  } catch {
    message.error(t('performance.msg.raw_result_failed'))
  }
}

function statusColor(status: string) {
  const colors: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    success: 'success',
    failed: 'error',
    cancelled: 'warning',
  }
  return colors[status] || 'default'
}

function statusLabel(status: string) {
  return t(`performance.status.${status}`, status)
}

function metricValue(value: unknown) {
  return typeof value === 'number' ? value : 0
}

function percentValue(value: unknown) {
  return typeof value === 'number' ? value * 100 : 0
}

function displayMetric(value: unknown, suffix = '') {
  if (typeof value !== 'number') return '-'
  return `${value.toFixed(value >= 100 ? 0 : 2)}${suffix}`
}

function numericMetric(value: unknown) {
  return typeof value === 'number' ? value : null
}

function displayPercent(value: unknown) {
  if (typeof value !== 'number') return '-'
  return `${(value * 100).toFixed(2)}%`
}

function formatDelta(value: number, suffix = '') {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(Math.abs(value) >= 100 ? 0 : 2)}${suffix}`
}

function formatDateLabel(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDuration(value?: number | null) {
  if (!value) return '-'
  if (value < 1000) return `${value}ms`
  return `${(value / 1000).toFixed(1)}s`
}

onMounted(loadProjects)
</script>

<style scoped>
.performance-center {
  padding: 16px;
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
}

.subtitle,
.muted {
  color: #8c8c8c;
}

.primary-text {
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.script-input {
  display: flex;
  width: 100%;
}

.script-input :deep(.ant-input) {
  flex: 1;
}

.form-alert {
  margin-bottom: 16px;
}

.field-hint {
  margin-top: 6px;
  color: #8c8c8c;
  font-size: 12px;
}

.stages-editor {
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}

.stage-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.section-title {
  margin: 24px 0 12px;
  font-size: 16px;
  font-weight: 600;
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
  gap: 16px;
  margin-top: 20px;
}

.insight-panel {
  min-width: 0;
}

.trend-chart {
  width: 100%;
  height: 280px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
}

.delta-good {
  color: #389e0d;
  font-weight: 600;
}

.delta-bad {
  color: #cf1322;
  font-weight: 600;
}

.detail-block {
  margin-top: 16px;
}

.section-label {
  margin-bottom: 6px;
  color: #595959;
  font-weight: 600;
}

.json-preview {
  max-height: 280px;
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  background: #fafafa;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1080px) {
  .insight-grid {
    grid-template-columns: 1fr;
  }
}
</style>
