<template>
  <div class="page-shell performance-workbench">
    <section class="perf-hero">
      <div class="hero-copy">
        <div class="eyebrow"><LineChartOutlined /> {{ t('performance_workbench.eyebrow') }}</div>
        <div class="hero-title-row">
          <h1>{{ t('performance_workbench.title') }}</h1>
          <span class="hero-chip">LOAD CONTROL / {{ readyExecutorCount }} EXECUTORS</span>
        </div>
        <p>{{ t('performance_workbench.subtitle') }}</p>
        <div class="hero-rail">
          <span class="live-dot" :class="{ muted: !onlineNodeCount }" />
          <span>{{ onlineNodeCount ? t('performance_workbench.worker_ready', { count: onlineNodeCount }) : t('performance_workbench.worker_waiting') }}</span>
          <span class="rail-separator" />
          <span class="rail-muted">{{ selectedProjectName || t('performance_workbench.no_project') }}</span>
        </div>
      </div>
      <div class="hero-controls">
        <label>{{ t('performance_workbench.project_label') }}</label>
        <a-select
          v-model:value="projectSelectId"
          :options="projectOptions"
          allow-clear
          :placeholder="t('performance_workbench.project_placeholder')"
          @change="handleProjectChange"
        />
        <div class="hero-control-row">
          <a-button :loading="loading" @click="refreshWorkbench"><ReloadOutlined /> {{ t('common.refresh') }}</a-button>
          <a-button type="link" @click="openFullConsole"><SettingOutlined /> {{ t('performance_workbench.full_console') }}</a-button>
        </div>
      </div>
    </section>

    <a-alert
      v-if="selectedProjectId && !canModify"
      class="readonly-alert"
      type="info"
      show-icon
      :message="t('performance_workbench.readonly_title')"
      :description="t('performance_workbench.readonly_description')"
    />
    <a-alert
      v-if="loadError"
      class="load-alert"
      type="warning"
      show-icon
      :message="t('performance_workbench.load_warning')"
      :description="loadError"
    />
    <a-empty v-if="!selectedProjectId" class="project-empty" :description="t('performance_workbench.select_project_hint')" />

    <template v-else>
      <section class="signal-grid" aria-label="Performance workspace summary">
        <div class="signal-card signal-card-primary">
          <span class="signal-label">{{ t('performance_workbench.signals.scenarios') }}</span>
          <strong>{{ tests.length }}</strong>
          <span class="signal-note">{{ t('performance_workbench.signals.scenarios_note') }}</span>
        </div>
        <div class="signal-card signal-card-blue">
          <span class="signal-label">{{ t('performance_workbench.signals.active_runs') }}</span>
          <strong>{{ activeRunCount }}</strong>
          <span class="signal-note">{{ t('performance_workbench.signals.active_note') }}</span>
        </div>
        <div class="signal-card signal-card-amber">
          <span class="signal-label">{{ t('performance_workbench.signals.online_nodes') }}</span>
          <strong>{{ onlineNodeCount }}<small>/{{ nodes.length }}</small></strong>
          <span class="signal-note">{{ t('performance_workbench.signals.nodes_note') }}</span>
        </div>
        <div class="signal-card signal-card-run">
          <span class="signal-label">{{ t('performance_workbench.signals.pass_rate') }}</span>
          <strong>{{ passRate }}%</strong>
          <span class="signal-note">{{ t('performance_workbench.signals.pass_note', { count: completedRunCount }) }}</span>
        </div>
      </section>

      <section class="runway" aria-label="Performance execution flow">
        <div class="runway-step active"><b>01</b><span>{{ t('performance_workbench.flow.define') }}</span><small>{{ t('performance_workbench.flow.define_hint') }}</small></div>
        <span class="runway-line" />
        <div class="runway-step active"><b>02</b><span>{{ t('performance_workbench.flow.launch') }}</span><small>{{ t('performance_workbench.flow.launch_hint') }}</small></div>
        <span class="runway-line" />
        <div class="runway-step" :class="{ active: activeRunCount > 0 || selectedRun }"><b>03</b><span>{{ t('performance_workbench.flow.observe') }}</span><small>{{ t('performance_workbench.flow.observe_hint') }}</small></div>
        <span class="runway-line" />
        <div class="runway-step" :class="{ active: selectedTest?.baseline_run_id || baselineComparison }"><b>04</b><span>{{ t('performance_workbench.flow.baseline') }}</span><small>{{ t('performance_workbench.flow.baseline_hint') }}</small></div>
      </section>

      <section class="control-grid">
        <aside class="scenario-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('performance_workbench.library_kicker') }}</div>
              <h2>{{ t('performance_workbench.library_title') }}</h2>
            </div>
            <a-button size="small" type="primary" :disabled="!canModify" @click="openQuickCreate"><PlusOutlined /> {{ t('performance_workbench.quick_create') }}</a-button>
          </div>
          <p class="panel-description">{{ t('performance_workbench.library_description') }}</p>
          <div v-if="tests.length" class="scenario-list">
            <button
              v-for="test in tests"
              :key="test.id"
              type="button"
              class="scenario-row"
              :class="{ selected: test.id === selectedTestId }"
              @click="selectTest(test.id)"
            >
              <span class="scenario-mark" :class="`executor-${test.executor}`" />
              <span class="scenario-row-main">
                <strong>{{ test.name }}</strong>
                <small>{{ test.executor }} · {{ test.script_object_name }}</small>
              </span>
              <span class="scenario-row-meta">
                <a-tag v-if="test.baseline_run_id" color="purple">{{ t('performance.baseline_set') }}</a-tag>
                <span>{{ formatDate(test.updated_at) }}</span>
              </span>
            </button>
          </div>
          <a-empty v-else :description="t('performance.empty_tests')" />
          <div class="panel-footer-actions">
            <a-button type="link" size="small" @click="openFullConsole">{{ t('performance_workbench.open_full_library') }} ↗</a-button>
          </div>
        </aside>

        <main class="launch-panel panel">
          <div class="panel-head launch-head">
            <div>
              <div class="panel-kicker">{{ t('performance_workbench.launch_kicker') }}</div>
              <h2>{{ selectedTest?.name || t('performance_workbench.launch_title') }}</h2>
              <p>{{ selectedTest ? selectedTest.description || t('performance_workbench.no_description') : t('performance_workbench.launch_description') }}</p>
            </div>
            <div class="launch-badge"><span class="signal-line" />{{ selectedTest?.executor || '—' }}</div>
          </div>

          <div v-if="selectedTest" class="selection-card">
            <div class="selection-title">
              <div>
                <span class="selection-kicker">{{ t('performance_workbench.selected_scenario') }}</span>
                <strong>{{ selectedTest.name }}</strong>
              </div>
              <a-tag :color="selectedTest.baseline_run_id ? 'purple' : 'default'">
                {{ selectedTest.baseline_run_id ? t('performance.baseline_set') : t('performance_workbench.no_baseline') }}
              </a-tag>
            </div>
            <div class="selection-meta">
              <span>{{ t('performance.executor') }}: {{ selectedTest.executor }}</span>
              <span v-if="selectedTest.dataset_id">{{ t('performance.dataset') }} #{{ selectedTest.dataset_id }}</span>
              <span v-if="selectedTest.schedule_enabled">{{ t('performance.schedule_enabled') }}</span>
              <span>{{ selectedTest.script_object_name }}</span>
            </div>
          </div>
          <a-empty v-else :description="t('performance_workbench.select_scenario')" />

          <div class="launch-form" :class="{ disabled: !selectedTest }">
            <div class="launch-form-grid">
              <div>
                <label>{{ t('performance_workbench.environment_label') }}</label>
                <a-select
                  v-model:value="launchEnvironmentId"
                  allow-clear
                  :options="environmentOptions"
                  :disabled="!selectedTest"
                  :placeholder="t('performance.no_environment')"
                />
                <small>{{ t('performance.environment_hint') }}</small>
              </div>
              <div>
                <label>{{ t('performance_workbench.node_label') }}</label>
                <a-select
                  v-model:value="launchNodeIds"
                  mode="multiple"
                  allow-clear
                  :options="launchNodeOptions"
                  :disabled="!selectedTest"
                  :placeholder="t('performance.no_node')"
                />
                <small>{{ t('performance.node_selector_hint') }}</small>
              </div>
            </div>
            <label>{{ t('performance.run_options') }}</label>
            <a-textarea v-model:value="launchOptionsText" class="mono" :rows="4" :disabled="!selectedTest" />
            <div class="launch-actions">
              <a-button type="primary" :disabled="!canLaunch" :loading="launching" @click="launchRun">
                <PlayCircleOutlined /> {{ t('performance_workbench.launch_run') }}
              </a-button>
              <a-button :disabled="!selectedTest || !canModify" @click="openFullConsole">{{ t('performance_workbench.advanced_config') }}</a-button>
              <a-button type="link" @click="openFullConsole">{{ t('performance_workbench.capacity_link') }}</a-button>
            </div>
            <p class="launch-note"><SafetyCertificateOutlined /> {{ canLaunch ? t('performance_workbench.launch_note') : t('performance_workbench.launch_unavailable') }}</p>
          </div>
        </main>

        <aside class="observe-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('performance_workbench.observe_kicker') }}</div>
              <h2>{{ t('performance_workbench.observe_title') }}</h2>
            </div>
            <span class="observe-live" :class="{ on: activeRunCount > 0 }"><i />{{ activeRunCount ? t('performance_workbench.live') : t('performance_workbench.idle') }}</span>
          </div>
          <p class="panel-description">{{ t('performance_workbench.observe_description') }}</p>
          <div v-if="recentRuns.length" class="run-list">
            <button v-for="run in recentRuns.slice(0, 7)" :key="run.id" type="button" class="run-row" :class="{ selected: run.id === selectedRunId }" @click="selectRun(run.id)">
              <span class="run-status-dot" :class="`status-${run.status}`" />
              <span class="run-row-main">
                <strong>#{{ run.id }} · {{ testName(run.performance_test_id) }}</strong>
                <small>{{ runStatusLabel(run.status) }} · {{ formatDate(run.created_at) }}</small>
              </span>
              <span class="run-progress-label">{{ progressPercent(run) }}%</span>
            </button>
          </div>
          <a-empty v-else :description="t('performance.empty_runs')" />
          <div class="panel-footer-actions">
            <a-button type="link" size="small" @click="openRuns">{{ t('performance_workbench.open_reports') }} ↗</a-button>
          </div>
        </aside>
      </section>

      <section class="evidence-grid">
        <main class="evidence-panel panel">
          <div class="panel-head">
            <div>
              <div class="panel-kicker">{{ t('performance_workbench.evidence_kicker') }}</div>
              <h2>{{ selectedRun ? `#${selectedRun.id} · ${testName(selectedRun.performance_test_id)}` : t('performance_workbench.evidence_title') }}</h2>
            </div>
            <a-space>
              <a-button v-if="selectedRun && isActive(selectedRun.status)" size="small" danger :loading="stoppingRunId === selectedRun.id" @click="stopSelectedRun"><StopOutlined /> {{ t('performance.stop') }}</a-button>
              <a-button v-if="selectedRun" size="small" :loading="evidenceLoading" @click="refreshEvidence"><ReloadOutlined /></a-button>
            </a-space>
          </div>
          <a-empty v-if="!selectedRun" :description="t('performance_workbench.select_run_hint')" />
          <template v-else>
            <div class="evidence-status-row">
              <div class="run-state-card" :class="`state-${selectedRun.status}`">
                <span class="run-status-dot" :class="`status-${selectedRun.status}`" />
                <strong>{{ runStatusLabel(selectedRun.status) }}</strong>
                <small>{{ t('performance.progress') }} {{ progressPercent(selectedRun) }}%</small>
              </div>
              <div class="gate-card" :class="`gate-${gateStatus}`">
                <span>{{ t('performance.threshold_gate') }}</span>
                <strong>{{ gateLabel }}</strong>
                <small>{{ gateSummary }}</small>
              </div>
              <div class="evidence-actions">
                <a-button size="small" :loading="exporting === 'json'" @click="exportReport('json')">{{ t('performance.export_json') }}</a-button>
                <a-button size="small" :loading="exporting === 'csv'" @click="exportReport('csv')">{{ t('performance.export_csv') }}</a-button>
              </div>
            </div>
            <div class="metric-grid">
              <div><span>{{ t('performance.rps') }}</span><strong>{{ displayMetric(selectedRun.summary.rps) }}</strong><small>{{ t('performance_workbench.metric_throughput') }}</small></div>
              <div><span>{{ t('performance.p95') }}</span><strong>{{ displayMetric(selectedRun.summary.p95_ms, 'ms') }}</strong><small>{{ t('performance_workbench.metric_latency') }}</small></div>
              <div><span>{{ t('performance.p99') }}</span><strong>{{ displayMetric(selectedRun.summary.p99_ms, 'ms') }}</strong><small>{{ t('performance_workbench.metric_tail') }}</small></div>
              <div><span>{{ t('performance.error_rate') }}</span><strong>{{ displayPercent(selectedRun.summary.error_rate) }}</strong><small>{{ formatDuration(selectedRun.duration_ms) }}</small></div>
            </div>
            <div v-if="selectedRun.error_message" class="run-error"><a-alert type="error" show-icon :message="selectedRun.error_message" /></div>
            <div class="resource-head">
              <div>
                <div class="section-label">{{ t('performance.resource_timeline') }}</div>
                <span class="field-hint">{{ t('performance_workbench.resource_hint') }}</span>
              </div>
              <a-space size="small">
                <a-select v-model:value="metricSource" size="small" :options="metricSourceOptions" :placeholder="t('performance.select_metric_source')" @change="handleMetricSourceChange" />
                <a-select v-model:value="resourceMetric" size="small" :options="resourceMetricOptions" :placeholder="t('performance.select_resource_metric')" />
              </a-space>
            </div>
            <a-empty v-if="!metricSamplesForSource.length" :description="t('performance.no_resource_metrics')" />
            <v-chart v-else class="resource-chart" :option="resourceTimelineOption" :theme="chartTheme" autoresize />
            <div class="evidence-foot">
              <span>{{ t('performance_workbench.samples_count', { count: metricSamples.length }) }}</span>
              <a-button type="link" size="small" @click="openFullConsole">{{ t('performance_workbench.open_full_detail') }} ↗</a-button>
            </div>
          </template>
        </main>

        <aside class="context-panel panel">
          <div class="panel-kicker">{{ t('performance_workbench.context_kicker') }}</div>
          <h2>{{ t('performance_workbench.context_title') }}</h2>
          <div class="context-block">
            <div class="context-block-head"><span>{{ t('performance_workbench.baseline_context') }}</span><a-tag v-if="selectedTest?.baseline_run_id" color="purple">{{ t('performance.baseline_set') }}</a-tag></div>
            <strong>{{ selectedTest?.baseline_run_id ? `#${selectedTest.baseline_run_id}` : t('performance_workbench.no_baseline') }}</strong>
            <small>{{ baselineComparison ? t('performance_workbench.baseline_loaded') : t('performance_workbench.baseline_hint') }}</small>
            <a-button v-if="selectedRun?.status === 'success'" size="small" type="primary" ghost :disabled="!canModify" @click="setSelectedBaseline">{{ t('performance.set_baseline') }}</a-button>
          </div>
          <div v-if="baselineComparison" class="baseline-list">
            <div v-for="metric in baselineComparison.metrics.slice(0, 4)" :key="metric.metric" class="baseline-row">
              <span>{{ metric.metric }}</span>
              <strong :class="`direction-${metric.direction}`">{{ formatBaselineDelta(metric.delta_percent) }}</strong>
            </div>
          </div>
          <div class="context-divider" />
          <div class="context-block">
            <div class="context-block-head"><span>{{ t('performance.nodes') }}</span><span class="count-pill">{{ onlineNodeCount }} {{ t('performance_workbench.online') }}</span></div>
            <div v-if="nodes.length" class="mini-node-list">
              <div v-for="node in nodes.slice(0, 4)" :key="node.id" class="mini-node-row">
                <span class="node-dot" :class="`node-${node.status}`" />
                <span><strong>{{ node.name }}</strong><small>{{ nodeExecutorLabel(node) }} · {{ node.queue_name }}</small></span>
              </div>
            </div>
            <a-empty v-else :description="t('performance.no_nodes')" />
            <a-button type="link" size="small" @click="openFullConsole">{{ t('performance_workbench.manage_nodes') }} ↗</a-button>
          </div>
          <div class="context-divider" />
          <div class="context-block compact-context">
            <span>{{ t('performance_workbench.next_action') }}</span>
            <strong>{{ t('performance_workbench.next_action_value') }}</strong>
            <small>{{ t('performance_workbench.next_action_hint') }}</small>
          </div>
        </aside>
      </section>
    </template>

    <a-drawer v-model:open="quickCreateOpen" :title="t('performance_workbench.quick_create_title')" width="520px" @close="quickCreateOpen = false">
      <a-form layout="vertical">
        <a-form-item :label="t('performance.name')" required><a-input v-model:value="quickForm.name" :placeholder="t('performance.name_placeholder')" /></a-form-item>
        <a-form-item :label="t('performance.executor')" required><a-select v-model:value="quickForm.executor" :options="executorOptions" /></a-form-item>
        <a-form-item :label="t('performance.script_object_name')" required><a-input v-model:value="quickForm.script_object_name" class="mono" :placeholder="t('performance.script_placeholder')" /></a-form-item>
        <a-form-item :label="t('performance.default_options')"><a-textarea v-model:value="quickForm.optionsText" class="mono" :rows="9" /></a-form-item>
        <a-alert type="info" show-icon :message="t('performance_workbench.quick_create_hint')" />
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="openFullConsole">{{ t('performance_workbench.advanced_config') }}</a-button>
          <a-button type="primary" :loading="quickCreating" @click="saveQuickCreate">{{ t('common.save') }}</a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  LineChartOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  StopOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  environmentApi,
  performanceApi,
  projectApi,
  type EnvironmentItem,
  type PerformanceBaselineComparisonItem,
  type PerformanceExecutorItem,
  type PerformanceMetricSampleItem,
  type PerformanceNodeItem,
  type PerformanceRunItem,
  type PerformanceTestItem,
  type ProjectItem,
} from '@/api'
import { useChartTheme } from '@/utils/chartTheme'
import { canEditProjectByRole } from '@/utils/permissions'
import { useAuthStore } from '@/stores/auth'

type ErrorLike = { response?: { data?: { detail?: unknown } }; message?: unknown }

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { chartTheme } = useChartTheme()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(positiveInt(route.query.project_id))
const projectSelectId = computed<number | undefined>({
  get: () => selectedProjectId.value ?? undefined,
  set: (value) => { selectedProjectId.value = positiveInt(value) },
})
const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: item.id })))
const selectedProject = computed(() => projects.value.find((item) => item.id === selectedProjectId.value))
const selectedProjectName = computed(() => selectedProject.value?.name || '')
const tests = ref<PerformanceTestItem[]>([])
const runs = ref<PerformanceRunItem[]>([])
const nodes = ref<PerformanceNodeItem[]>([])
const executors = ref<PerformanceExecutorItem[]>([])
const environments = ref<EnvironmentItem[]>([])
const loading = ref(false)
const loadError = ref('')
const launching = ref(false)
const quickCreating = ref(false)
const quickCreateOpen = ref(false)
const evidenceLoading = ref(false)
const stoppingRunId = ref<number | null>(null)
const exporting = ref<'json' | 'csv' | null>(null)
const selectedTestId = ref<number | null>(null)
const selectedRunId = ref<number | null>(null)
const launchEnvironmentId = ref<number | undefined>()
const launchNodeIds = ref<number[]>([])
const launchOptionsText = ref('{}')
const metricSamples = ref<PerformanceMetricSampleItem[]>([])
const metricSource = ref('performance-worker')
const resourceMetric = ref('cpu_percent')
const gate = ref<{ status: string; passed: number; total: number } | null>(null)
const baselineComparison = ref<PerformanceBaselineComparisonItem | null>(null)
const quickForm = ref({
  name: '',
  executor: 'k6',
  script_object_name: '',
  optionsText: '{\n  "env": {\n    "TARGET_URL": "https://example.test"\n  }\n}',
})
let loadSequence = 0
let evidenceSequence = 0
let pollTimer: ReturnType<typeof window.setInterval> | null = null

const selectedTest = computed(() => tests.value.find((item) => item.id === selectedTestId.value) || null)
const selectedRun = computed(() => runs.value.find((item) => item.id === selectedRunId.value) || null)
const canModify = computed(() => canEditProjectByRole(auth.user?.role, selectedProject.value?.current_user_role))
const readyExecutorCount = computed(() => executors.value.filter((item) => item.ready).length)
const onlineNodeCount = computed(() => nodes.value.filter((item) => item.status === 'online' && item.enabled).length)
const activeRunCount = computed(() => runs.value.filter((item) => isActive(item.status)).length)
const completedRuns = computed(() => runs.value.filter((item) => ['success', 'failed', 'cancelled'].includes(item.status)))
const completedRunCount = computed(() => completedRuns.value.length)
const passRate = computed(() => completedRunCount.value ? Math.round((completedRuns.value.filter((item) => item.status === 'success').length / completedRunCount.value) * 100) : 0)
const environmentOptions = computed(() => environments.value.map((item) => ({ label: item.name, value: item.id })))
const executorOptions = computed(() => executors.value.map((item) => ({ label: item.label, value: item.name, disabled: !item.ready })))
const launchNodeOptions = computed(() => {
  const executor = selectedTest.value?.executor
  return nodes.value.map((node) => {
    const supportsExecutor = nodeExecutorNames(node).includes(executor || '')
    const disabled = node.status !== 'online' || !node.enabled || !supportsExecutor
    return {
      label: `${node.name} · ${node.queue_name} · ${nodeStatusLabel(node.status)}`,
      value: node.id,
      disabled,
    }
  })
})
const canLaunch = computed(() => Boolean(canModify.value && selectedTest.value && !launching.value && isExecutorReady(selectedTest.value.executor)))
const recentRuns = computed(() => [...runs.value].sort((a, b) => b.created_at.localeCompare(a.created_at)))
const metricSamplesForSource = computed(() => metricSamples.value.filter((item) => item.source === metricSource.value))
const metricSourceOptions = computed(() => [...new Set(metricSamples.value.map((item) => item.source).filter(Boolean))].map((source) => ({ label: metricSourceLabel(source), value: source })))
const resourceMetricOptions = computed(() => [...new Set(metricSamplesForSource.value.flatMap((item) => Object.keys(item.metrics)))].map((key) => ({ label: metricLabel(key), value: key })))
const gateStatus = computed(() => gate.value?.status || 'pending')
const gateLabel = computed(() => {
  if (!gate.value || gate.value.status === 'pending') return t('performance_workbench.gate_loading')
  return t(`performance.threshold_gate_${gate.value.status}`)
})
const gateSummary = computed(() => gate.value ? t('performance.threshold_gate_summary', { passed: gate.value.passed, total: gate.value.total }) : t('performance_workbench.gate_hint'))
const resourceTimelineOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { top: 22, right: 18, bottom: 38, left: 55 },
  xAxis: { type: 'category', data: metricSamplesForSource.value.map((item) => formatDate(item.captured_at)) },
  yAxis: { type: 'value', name: metricLabel(resourceMetric.value) },
  series: [{ name: metricLabel(resourceMetric.value), type: 'line', smooth: true, showSymbol: false, data: metricSamplesForSource.value.map((item) => item.metrics[resourceMetric.value] ?? null) }],
}))

function positiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return error instanceof Error ? error.message : fallback
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDuration(value?: number | null) {
  if (!value) return '—'
  return value < 1000 ? `${value}ms` : `${(value / 1000).toFixed(1)}s`
}

function progressPercent(run: PerformanceRunItem) { return Math.max(0, Math.min(100, Math.round(run.progress_percent || 0))) }
function isActive(status: string) { return ['pending', 'running', 'cancelling'].includes(status) }
function runStatusLabel(status: string) { return t(`performance.status.${status}`, status) }
function displayMetric(value: unknown, suffix = '') { return typeof value === 'number' ? `${value.toFixed(Math.abs(value) >= 100 ? 0 : 2)}${suffix}` : '—' }
function displayPercent(value: unknown) { return typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : '—' }
function formatBaselineDelta(value: unknown) { return typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%` : '—' }
function testName(id: number) { return tests.value.find((item) => item.id === id)?.name || `#${id}` }
function isExecutorReady(name: string) { return executors.value.find((item) => item.name === name)?.ready === true }
function nodeExecutorNames(node: PerformanceNodeItem): string[] {
  const declared = node.capabilities?.executors
  if (Array.isArray(declared)) return declared.map(String).filter(Boolean)
  if (typeof declared === 'string') return declared.split(',').map((item) => item.trim()).filter(Boolean)
  return ['k6']
}
function nodeExecutorLabel(node: PerformanceNodeItem) { return nodeExecutorNames(node).join(', ') }
function nodeStatusLabel(status: string) { return t(`performance.node_status.${status}`, status) }
function metricSourceLabel(source: string) {
  if (source === 'performance-worker') return t('performance.metric_source_worker')
  if (source === 'target-service-prometheus') return t('performance.metric_source_prometheus')
  if (source === 'atp-platform') return t('performance.metric_source_platform')
  return source
}
function metricLabel(key: string) { return t(`performance.resource_metric_${key}`, key) }

function clearProjectData() {
  loadSequence += 1
  evidenceSequence += 1
  tests.value = []
  runs.value = []
  nodes.value = []
  executors.value = []
  environments.value = []
  selectedTestId.value = null
  selectedRunId.value = null
  metricSamples.value = []
  gate.value = null
  baselineComparison.value = null
  evidenceLoading.value = false
  stopPolling()
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (!selectedProjectId.value || !projects.value.some((item) => item.id === selectedProjectId.value)) selectedProjectId.value = projects.value[0]?.id ?? null
    await loadProjectData()
    syncRoute()
  } catch (error: unknown) {
    loadError.value = errorMessage(error, t('performance_workbench.load_failed'))
  }
}

async function loadProjectData() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    clearProjectData()
    return
  }
  const sequence = ++loadSequence
  loading.value = true
  loadError.value = ''
  try {
    const [testResult, runResult, environmentResult, nodeResult, executorResult] = await Promise.allSettled([
      performanceApi.listTests(projectId),
      performanceApi.listRuns(projectId),
      environmentApi.list(projectId),
      performanceApi.listNodes(),
      performanceApi.listExecutors(),
    ])
    if (sequence !== loadSequence || selectedProjectId.value !== projectId) return
    tests.value = testResult.status === 'fulfilled' ? testResult.value : []
    runs.value = runResult.status === 'fulfilled' ? runResult.value : []
    environments.value = environmentResult.status === 'fulfilled' ? environmentResult.value : []
    nodes.value = nodeResult.status === 'fulfilled' ? nodeResult.value : []
    executors.value = executorResult.status === 'fulfilled' ? executorResult.value : []
    if ([testResult, runResult, environmentResult, nodeResult, executorResult].some((result) => result.status === 'rejected')) {
      loadError.value = t('performance_workbench.load_warning')
    }
    if (!selectedTestId.value || !tests.value.some((item) => item.id === selectedTestId.value)) selectedTestId.value = tests.value[0]?.id ?? null
    if (!selectedRunId.value || !runs.value.some((item) => item.id === selectedRunId.value)) selectedRunId.value = recentRuns.value[0]?.id ?? null
    syncLaunchFromTest()
    syncPolling()
    if (selectedRunId.value) await loadEvidence(selectedRunId.value)
    else clearEvidence()
  } catch (error: unknown) {
    if (sequence === loadSequence) loadError.value = errorMessage(error, t('performance_workbench.load_failed'))
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function refreshWorkbench() { await loadProjectData() }

async function handleProjectChange(value: unknown) {
  selectedProjectId.value = positiveInt(value)
  clearProjectData()
  await loadProjectData()
  syncRoute()
}

function syncRoute() {
  void router.replace({ query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

async function loadRuns() {
  const projectId = selectedProjectId.value
  if (!projectId) return
  const sequence = loadSequence
  try {
    const items = await performanceApi.listRuns(projectId)
    if (sequence !== loadSequence || selectedProjectId.value !== projectId) return
    runs.value = items
    if (!selectedRunId.value || !runs.value.some((item) => item.id === selectedRunId.value)) selectedRunId.value = recentRuns.value[0]?.id ?? null
    syncPolling()
  } catch {
    // 后台轮询失败不覆盖当前证据，下一轮继续尝试。
  }
}

function syncPolling() {
  if (activeRunCount.value && pollTimer === null) pollTimer = window.setInterval(() => void loadRuns(), 2500)
  if (!activeRunCount.value) stopPolling()
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function selectTest(id: number) {
  selectedTestId.value = id
  syncLaunchFromTest()
}

function syncLaunchFromTest() {
  const test = selectedTest.value
  if (!test) {
    launchOptionsText.value = '{}'
    launchNodeIds.value = []
    return
  }
  launchOptionsText.value = JSON.stringify(test.default_options || {}, null, 2)
  launchNodeIds.value = launchNodeIds.value.filter((id) => launchNodeOptions.value.some((option) => option.value === id && !option.disabled))
}

watch(selectedTestId, () => syncLaunchFromTest())

function clearEvidence() {
  evidenceSequence += 1
  metricSamples.value = []
  gate.value = null
  baselineComparison.value = null
}

async function selectRun(id: number) {
  selectedRunId.value = id
  await loadEvidence(id)
}

async function loadEvidence(runId: number) {
  const sequence = ++evidenceSequence
  evidenceLoading.value = true
  try {
    const [gateResult, baselineResult, metricsResult] = await Promise.allSettled([
      performanceApi.getGate(runId),
      performanceApi.getBaselineComparison(runId),
      performanceApi.getMetrics(runId),
    ])
    if (sequence !== evidenceSequence || selectedRunId.value !== runId) return
    gate.value = gateResult.status === 'fulfilled' ? gateResult.value : null
    baselineComparison.value = baselineResult.status === 'fulfilled' ? baselineResult.value : null
    metricSamples.value = metricsResult.status === 'fulfilled' ? metricsResult.value : []
    if (!metricSourceOptions.value.some((item) => item.value === metricSource.value)) metricSource.value = metricSourceOptions.value[0]?.value || 'performance-worker'
    if (!resourceMetricOptions.value.some((item) => item.value === resourceMetric.value)) resourceMetric.value = resourceMetricOptions.value[0]?.value || 'cpu_percent'
  } finally {
    if (sequence === evidenceSequence) evidenceLoading.value = false
  }
}

function refreshEvidence() {
  if (selectedRunId.value) void loadEvidence(selectedRunId.value)
}

function handleMetricSourceChange() {
  if (!resourceMetricOptions.value.some((item) => item.value === resourceMetric.value)) resourceMetric.value = resourceMetricOptions.value[0]?.value || 'cpu_percent'
}

function openQuickCreate() {
  quickForm.value = {
    name: '',
    executor: executors.value.find((item) => item.ready)?.name || 'k6',
    script_object_name: '',
    optionsText: '{\n  "env": {\n    "TARGET_URL": "https://example.test"\n  }\n}',
  }
  quickCreateOpen.value = true
}

function parseOptions(text: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(text || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('object expected')
    return value as Record<string, unknown>
  } catch {
    message.warning(t('performance_workbench.options_invalid'))
    return null
  }
}

async function saveQuickCreate() {
  const projectId = selectedProjectId.value
  const name = quickForm.value.name.trim()
  const scriptObjectName = quickForm.value.script_object_name.trim()
  if (!projectId || !name || !scriptObjectName) {
    message.warning(t('performance_workbench.quick_required'))
    return
  }
  const options = parseOptions(quickForm.value.optionsText)
  if (!options) return
  quickCreating.value = true
  try {
    const created = await performanceApi.createTest({
      project_id: projectId,
      name,
      executor: quickForm.value.executor as 'k6' | 'locust' | 'grpc' | 'jmeter',
      script_object_name: scriptObjectName,
      default_options: options,
    })
    quickCreateOpen.value = false
    selectedTestId.value = created.id
    message.success(t('performance_workbench.quick_created'))
    await loadProjectData()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('performance_workbench.save_failed')))
  } finally {
    quickCreating.value = false
  }
}

function createIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `performance-workbench-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

async function launchRun() {
  const test = selectedTest.value
  if (!test || !canLaunch.value) return
  const options = parseOptions(launchOptionsText.value)
  if (!options) return
  launching.value = true
  try {
    const run = await performanceApi.triggerRun(test.id, {
      environment_id: launchEnvironmentId.value ?? null,
      performance_node_ids: launchNodeIds.value,
      idempotency_key: createIdempotencyKey(),
      options,
    })
    message.success(t('performance_workbench.run_started', { id: run.id }))
    await loadProjectData()
    selectedRunId.value = run.id
    if (!runs.value.some((item) => item.id === run.id)) runs.value = [run, ...runs.value]
    await loadEvidence(run.id)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('performance_workbench.run_failed')))
  } finally {
    launching.value = false
  }
}

async function stopSelectedRun() {
  const run = selectedRun.value
  if (!run || !isActive(run.status)) return
  stoppingRunId.value = run.id
  try {
    await performanceApi.stopRun(run.id)
    message.success(t('performance_workbench.stop_started'))
    await loadRuns()
    await loadEvidence(run.id)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('performance_workbench.stop_failed')))
  } finally {
    stoppingRunId.value = null
  }
}

async function setSelectedBaseline() {
  const run = selectedRun.value
  if (!run || run.status !== 'success' || !canModify.value) return
  try {
    await performanceApi.setBaseline(run.performance_test_id, run.id)
    message.success(t('performance_workbench.baseline_saved'))
    await loadProjectData()
    await loadEvidence(run.id)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('performance_workbench.baseline_failed')))
  }
}

async function exportReport(format: 'json' | 'csv') {
  if (!selectedRun.value) return
  exporting.value = format
  try {
    const blob = format === 'json' ? await performanceApi.exportRunJson(selectedRun.value.id) : await performanceApi.exportRunCsv(selectedRun.value.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `performance-run-${selectedRun.value.id}-report.${format}`
    link.click()
    URL.revokeObjectURL(url)
    message.success(t('performance_workbench.exported'))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('performance_workbench.export_failed')))
  } finally {
    exporting.value = null
  }
}

function openFullConsole() {
  void router.push({ path: '/system/performance', query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

function openRuns() {
  void router.push({ path: '/system/performance', query: selectedProjectId.value ? { project_id: String(selectedProjectId.value) } : {} })
}

onMounted(() => { void loadProjects() })
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.performance-workbench { --perf-ink: #20282f; --perf-muted: #74818a; --perf-line: #d9e0e3; --perf-paper: #f3f6f5; --perf-panel: #fff; --perf-blue: #4a91d9; --perf-amber: #d69a3a; --perf-teal: #43aa9c; --perf-red: #dc6b5d; color: var(--perf-ink); }
.perf-hero { display: flex; justify-content: space-between; gap: 28px; padding: 30px 32px 26px; overflow: hidden; border: 1px solid #202a31; border-radius: 15px; background: radial-gradient(circle at 86% 20%, rgba(74, 145, 217, .24), transparent 23%), linear-gradient(122deg, #182329, #253844 68%, #344c58); color: #f9fbfb; box-shadow: 0 18px 38px rgba(30, 43, 50, .15); }
.hero-copy { min-width: 0; }.eyebrow, .panel-kicker { color: #7fc4be; font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }.eyebrow { display: flex; align-items: center; gap: 7px; }.hero-title-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 8px 0 7px; }.perf-hero h1 { margin: 0; color: #fff; font-size: 31px; letter-spacing: -.05em; }.hero-chip { padding: 4px 8px; border: 1px solid rgba(124, 196, 190, .42); border-radius: 4px; color: #b8e2de; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; letter-spacing: .04em; }.perf-hero p { max-width: 720px; margin: 0; color: #c9d6dc; line-height: 1.7; }.hero-rail { display: flex; align-items: center; gap: 9px; margin-top: 21px; color: #e4eef1; font-size: 12px; font-weight: 650; }.live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--perf-teal); box-shadow: 0 0 0 4px rgba(67, 170, 156, .14); }.live-dot.muted { background: var(--perf-amber); box-shadow: 0 0 0 4px rgba(214, 154, 58, .14); }.rail-separator { width: 28px; height: 1px; background: rgba(231, 242, 245, .28); }.rail-muted { color: #aebdc4; font-weight: 500; }.hero-controls { width: 250px; flex: 0 0 250px; }.hero-controls label { display: block; margin-bottom: 7px; color: #bdcbd1; font-size: 11px; font-weight: 700; }.hero-controls :deep(.ant-select-selector) { border-color: #657781 !important; background: rgba(255, 255, 255, .08) !important; color: #fff !important; }.hero-controls :deep(.ant-select-selection-placeholder), .hero-controls :deep(.ant-select-selection-item) { color: #fff !important; }.hero-control-row { display: flex; align-items: center; justify-content: space-between; margin-top: 13px; }.hero-control-row .ant-btn { color: #cedce1; }.readonly-alert, .load-alert { margin-top: 14px; }.signal-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }.signal-card { min-height: 106px; padding: 17px 18px; border: 1px solid var(--perf-line); border-radius: 10px; background: var(--perf-panel); box-shadow: 0 7px 18px rgba(31, 48, 58, .045); }.signal-card-primary { border-top: 3px solid var(--perf-teal); }.signal-card-blue { border-top: 3px solid var(--perf-blue); }.signal-card-amber { border-top: 3px solid var(--perf-amber); }.signal-card-run { border-top: 3px solid var(--perf-red); }.signal-label { display: block; color: var(--perf-muted); font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }.signal-card strong { display: block; margin-top: 8px; font-size: 28px; letter-spacing: -.05em; }.signal-card strong small { margin-left: 4px; color: var(--perf-muted); font-size: 14px; letter-spacing: 0; }.signal-note { display: block; margin-top: 5px; color: #99a4aa; font-size: 11px; }.runway { display: flex; align-items: center; gap: 10px; margin: 14px 0; padding: 13px 17px; border: 1px solid #cbd8dc; border-radius: 9px; background: #edf4f5; }.runway-step { display: grid; grid-template-columns: 25px auto; grid-template-rows: auto auto; column-gap: 7px; min-width: 0; color: #9ba5a8; }.runway-step b { grid-row: 1 / span 2; color: #aab5b9; font-family: ui-monospace, monospace; font-size: 11px; }.runway-step span { font-size: 11px; font-weight: 800; }.runway-step small { margin-top: 2px; font-size: 9px; white-space: nowrap; }.runway-step.active { color: var(--perf-ink); }.runway-step.active b { color: var(--perf-blue); }.runway-line { flex: 1; min-width: 12px; height: 1px; background: #b8c8ce; }.control-grid { display: grid; grid-template-columns: 255px minmax(0, 1fr) 275px; gap: 14px; align-items: start; }.panel { min-width: 0; border: 1px solid var(--perf-line); border-radius: 12px; background: var(--perf-panel); box-shadow: 0 8px 20px rgba(31, 48, 58, .045); }.scenario-panel, .observe-panel, .context-panel { padding: 18px; }.launch-panel, .evidence-panel { padding: 20px; }.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.panel h2 { margin: 5px 0 7px; font-size: 18px; letter-spacing: -.035em; }.panel-description { margin: 0 0 14px; color: var(--perf-muted); font-size: 11px; line-height: 1.65; }.scenario-list { display: grid; gap: 5px; max-height: 350px; overflow-y: auto; }.scenario-row { display: flex; align-items: center; gap: 9px; width: 100%; padding: 10px 8px; border: 1px solid transparent; border-radius: 7px; background: #f7f9f8; color: var(--perf-ink); cursor: pointer; text-align: left; transition: border-color .16s ease, background .16s ease, transform .16s ease; }.scenario-row:hover, .scenario-row:focus-visible { border-color: #9dc9e8; background: #f3f8fd; transform: translateX(2px); }.scenario-row.selected { border-color: #6fa9db; background: #edf5fc; }.scenario-mark { flex: 0 0 auto; width: 6px; height: 30px; border-radius: 2px; background: var(--perf-blue); }.scenario-mark.executor-locust { background: var(--perf-teal); }.scenario-mark.executor-grpc { background: var(--perf-amber); }.scenario-mark.executor-jmeter { background: #9a7bc4; }.scenario-row-main { min-width: 0; flex: 1; }.scenario-row-main strong, .scenario-row-main small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.scenario-row-main strong { font-size: 12px; }.scenario-row-main small { margin-top: 3px; color: var(--perf-muted); font-family: ui-monospace, monospace; font-size: 9px; }.scenario-row-meta { display: flex; align-items: flex-end; flex-direction: column; gap: 3px; color: var(--perf-muted); font-size: 9px; white-space: nowrap; }.panel-footer-actions { margin-top: 13px; padding-top: 10px; border-top: 1px solid #edf0f1; }.launch-head h2 { font-size: 22px; }.launch-head p { max-width: 540px; margin: 0; color: var(--perf-muted); font-size: 11px; }.launch-badge { display: flex; align-items: center; gap: 7px; padding: 7px 9px; border: 1px solid #d9e5e9; border-radius: 5px; background: #f4f8f9; color: #53666f; font-family: ui-monospace, monospace; font-size: 10px; text-transform: uppercase; }.signal-line { display: inline-block; width: 18px; height: 2px; background: var(--perf-blue); box-shadow: 5px 4px 0 var(--perf-amber), 10px -4px 0 var(--perf-teal); }.selection-card { margin: 17px 0 15px; padding: 12px; border: 1px solid #c7dce8; border-radius: 8px; background: #f4f9fc; }.selection-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.selection-kicker { display: block; color: var(--perf-blue); font-size: 9px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }.selection-title strong { display: block; margin-top: 3px; font-size: 14px; }.selection-meta { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 10px; color: var(--perf-muted); font-size: 10px; }.launch-form { margin-top: 13px; }.launch-form.disabled { opacity: .7; }.launch-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.launch-form label { display: block; margin: 10px 0 6px; color: #51636c; font-size: 11px; font-weight: 750; }.launch-form small { display: block; margin-top: 5px; color: #99a4aa; font-size: 10px; line-height: 1.4; }.launch-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 14px; }.launch-note { display: flex; align-items: center; gap: 6px; margin: 12px 0 0; color: var(--perf-muted); font-size: 10px; }.observe-live { display: inline-flex; align-items: center; gap: 5px; color: #9aa6aa; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }.observe-live i { width: 7px; height: 7px; border-radius: 50%; background: #b7c0c3; }.observe-live.on { color: #3a8d81; }.observe-live.on i { background: var(--perf-teal); box-shadow: 0 0 0 4px rgba(67, 170, 156, .12); }.run-list { display: grid; gap: 3px; margin-top: 10px; }.run-row { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 0; border: 0; border-bottom: 1px solid #edf0f1; background: transparent; color: var(--perf-ink); cursor: pointer; text-align: left; }.run-row:hover, .run-row:focus-visible { color: var(--perf-blue); }.run-row.selected { color: var(--perf-blue); }.run-status-dot { flex: 0 0 auto; width: 7px; height: 7px; border-radius: 50%; background: #bcc6c9; }.run-status-dot.status-success { background: var(--perf-teal); }.run-status-dot.status-failed { background: var(--perf-red); }.run-status-dot.status-running, .run-status-dot.status-pending, .run-status-dot.status-cancelling { background: var(--perf-amber); }.run-row-main { min-width: 0; flex: 1; }.run-row-main strong, .run-row-main small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.run-row-main strong { font-size: 10px; }.run-row-main small { margin-top: 2px; color: var(--perf-muted); font-size: 9px; }.run-progress-label { color: var(--perf-muted); font-family: ui-monospace, monospace; font-size: 9px; }.evidence-grid { display: grid; grid-template-columns: minmax(0, 1fr) 275px; gap: 14px; margin-top: 14px; }.evidence-status-row { display: grid; grid-template-columns: 1fr 1.1fr auto; gap: 9px; align-items: stretch; margin: 15px 0 12px; }.run-state-card, .gate-card { display: flex; flex-direction: column; justify-content: center; min-height: 60px; padding: 9px 11px; border: 1px solid #dae2e5; border-radius: 7px; background: #f8faf9; }.run-state-card { flex-direction: row; align-items: center; gap: 7px; flex-wrap: wrap; }.run-state-card strong { font-size: 12px; }.run-state-card small, .gate-card small { width: 100%; color: var(--perf-muted); font-size: 9px; }.state-success { border-color: #b8dfd7; background: #f1fbf8; }.state-failed { border-color: #ebc0bb; background: #fff5f3; }.gate-passed { border-color: #b8dfd7; background: #f1fbf8; }.gate-failed { border-color: #ebc0bb; background: #fff5f3; }.gate-card span { color: var(--perf-muted); font-size: 9px; }.gate-card strong { display: block; margin-top: 3px; font-size: 12px; }.evidence-actions { display: flex; flex-direction: column; justify-content: center; gap: 5px; }.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }.metric-grid div { padding: 11px; border-left: 2px solid #bcd4e5; background: #f8faf9; }.metric-grid span, .metric-grid strong, .metric-grid small { display: block; }.metric-grid span { color: var(--perf-muted); font-size: 9px; }.metric-grid strong { margin: 5px 0 3px; font-family: ui-monospace, monospace; font-size: 18px; letter-spacing: -.04em; }.metric-grid small { color: #9aa6aa; font-size: 9px; }.run-error { margin-top: 10px; }.resource-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 10px; margin-top: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--perf-line); }.resource-chart { width: 100%; height: 230px; margin-top: 10px; }.evidence-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; color: var(--perf-muted); font-size: 10px; }.context-panel h2 { margin: 5px 0 15px; }.context-block { display: grid; gap: 7px; }.context-block-head { display: flex; align-items: center; justify-content: space-between; color: var(--perf-muted); font-size: 10px; }.context-block > strong { font-size: 15px; }.context-block > small { color: var(--perf-muted); font-size: 10px; line-height: 1.5; }.context-block .ant-btn { justify-self: start; padding-left: 0; }.context-divider { height: 1px; margin: 17px 0; background: var(--perf-line); }.count-pill { padding: 3px 6px; border-radius: 3px; background: #edf4f2; color: #438a80; font-size: 9px; font-weight: 800; }.baseline-list { display: grid; gap: 5px; margin-top: 10px; }.baseline-row { display: flex; justify-content: space-between; padding: 6px 8px; border-radius: 4px; background: #fafbfa; font-family: ui-monospace, monospace; font-size: 10px; }.direction-regression { color: var(--perf-red); }.direction-improvement { color: var(--perf-teal); }.mini-node-list { display: grid; gap: 8px; }.mini-node-row { display: flex; align-items: flex-start; gap: 7px; }.mini-node-row > span:last-child { min-width: 0; }.mini-node-row strong, .mini-node-row small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.mini-node-row strong { font-size: 10px; }.mini-node-row small { margin-top: 2px; color: var(--perf-muted); font-size: 9px; }.node-dot { flex: 0 0 auto; width: 7px; height: 7px; margin-top: 3px; border-radius: 50%; background: #bdc6c9; }.node-online { background: var(--perf-teal); box-shadow: 0 0 0 3px rgba(67, 170, 156, .12); }.node-offline { background: var(--perf-red); }.node-draining { background: var(--perf-amber); }.compact-context > strong { font-size: 12px; }.mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.quick-create-title { font-weight: 700; }
:deep(.ant-btn:focus-visible), .scenario-row:focus-visible, .run-row:focus-visible { outline: 2px solid #4a91d9; outline-offset: 2px; }
@media (max-width: 1180px) { .control-grid { grid-template-columns: 225px minmax(0, 1fr); }.observe-panel { grid-column: 1 / -1; }.run-list { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 15px; }.evidence-grid { grid-template-columns: minmax(0, 1fr) 225px; } }
@media (max-width: 800px) { .perf-hero { flex-direction: column; padding: 23px 20px; }.hero-controls { width: 100%; flex-basis: auto; }.signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.runway { overflow-x: auto; }.control-grid, .evidence-grid { grid-template-columns: 1fr; }.observe-panel { grid-column: auto; }.launch-form-grid, .metric-grid, .evidence-status-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }.evidence-actions { grid-column: 1 / -1; flex-direction: row; }.run-list { grid-template-columns: 1fr; } }
@media (max-width: 480px) { .perf-hero h1 { font-size: 25px; }.signal-grid { gap: 8px; }.signal-card { padding: 13px; }.runway { padding: 11px; }.runway-step small { display: none; }.launch-form-grid, .metric-grid, .evidence-status-row { grid-template-columns: 1fr; }.evidence-actions { grid-column: auto; flex-direction: row; }.resource-head { align-items: flex-start; flex-direction: column; } }
@media (prefers-reduced-motion: reduce) { .scenario-row { transition: none; } }
</style>
