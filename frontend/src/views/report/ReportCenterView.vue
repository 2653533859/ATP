<template>
  <div class="report-page">
    <header class="report-hero">
      <div class="hero-copy">
        <div class="hero-kicker">QUALITY SIGNAL / N2.3</div>
        <h1>{{ t('report_center.title') }}</h1>
        <p>{{ t('report_center.subtitle') }}</p>
      </div>
      <div class="hero-controls">
        <a-select
          v-model:value="projectId"
          allow-clear
          show-search
          :filter-option="filterProject"
          :placeholder="t('report_center.all_projects')"
          :options="projectOptions"
          class="project-select"
        />
        <a-select v-model:value="days" :options="dayOptions" class="days-select" />
        <a-button :loading="loading" @click="loadReport">{{ t('report_center.refresh') }}</a-button>
        <a-button :loading="exporting" @click="exportTrend">{{ t('report_center.export_trend') }}</a-button>
        <a-button size="small" @click="openAsset('/cases')">{{ t('menu.cases') }}</a-button>
        <a-button size="small" @click="openAsset('/suites')">{{ t('menu.suites') }}</a-button>
        <a-button size="small" @click="openAsset('/plans')">{{ t('menu.plans') }}</a-button>
      </div>
    </header>

    <a-alert
      v-if="loadError"
      class="report-alert"
      type="warning"
      show-icon
      :message="t('report_center.load_failed')"
      :description="t('report_center.load_failed_hint')"
    />

    <a-spin :spinning="loading">
      <section class="signal-grid" aria-label="quality signal summary">
        <article class="score-card">
          <div class="score-card-top">
            <div>
              <span class="eyebrow">{{ t('report_center.score.eyebrow') }}</span>
              <h2>{{ t('report_center.score.title') }}</h2>
            </div>
            <span class="score-period">{{ t('report_center.period', { days: overview.days }) }}</span>
          </div>
          <div class="score-main">
            <div class="score-ring" :style="scoreRingStyle">
              <div class="score-ring-inner">
                <strong>{{ overview.quality_score.toFixed(1) }}</strong>
                <span>/ 100</span>
              </div>
            </div>
            <div class="score-copy">
              <strong>{{ qualityLabel }}</strong>
              <p>{{ t('report_center.score.formula') }}</p>
              <a-tag :color="overview.open_defects > 0 ? 'orange' : 'green'">
                {{ t('report_center.score.open_defects', { count: overview.open_defects }) }}
              </a-tag>
            </div>
          </div>
          <div class="score-breakdown">
            <div v-for="item in scoreBreakdown" :key="item.key" class="score-breakdown-item">
              <div class="breakdown-label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value.toFixed(1) }}%</strong>
              </div>
              <div class="breakdown-track"><span :style="{ width: `${Math.min(item.value, 100)}%` }" /></div>
            </div>
          </div>
        </article>

        <article class="metric-card metric-card-indigo">
          <span class="metric-kicker">{{ t('report_center.metrics.execution') }}</span>
          <strong>{{ overview.total_runs }}</strong>
          <span>{{ t('report_center.metrics.runs_in_period') }}</span>
          <div class="metric-foot"><span>{{ t('report_center.metrics.passed') }}</span><b>{{ overview.passed_runs }}</b></div>
        </article>
        <article class="metric-card metric-card-teal">
          <span class="metric-kicker">{{ t('report_center.metrics.coverage') }}</span>
          <strong>{{ overview.coverage_rate.toFixed(1) }}%</strong>
          <span>{{ t('report_center.metrics.case_coverage') }}</span>
          <div class="metric-foot"><span>{{ t('report_center.metrics.executed_cases') }}</span><b>{{ overview.executed_cases }} / {{ overview.total_cases }}</b></div>
        </article>
        <article class="metric-card metric-card-amber">
          <span class="metric-kicker">{{ t('report_center.metrics.stability') }}</span>
          <strong>{{ overview.pass_rate.toFixed(1) }}%</strong>
          <span>{{ t('report_center.metrics.pass_rate') }}</span>
          <div class="metric-foot"><span>{{ t('report_center.metrics.failed_error') }}</span><b>{{ overview.failed_runs + overview.error_runs }}</b></div>
        </article>
      </section>

      <section class="report-two-column">
        <a-card class="report-card trend-card" :bordered="false">
          <div class="card-heading">
            <div>
              <span class="eyebrow">{{ t('report_center.trend.eyebrow') }}</span>
              <h2>{{ t('report_center.trend.title') }}</h2>
            </div>
            <span class="card-note">{{ t('report_center.trend.note') }}</span>
          </div>
          <v-chart class="trend-chart" :option="trendOption" :theme="chartTheme" autoresize />
        </a-card>

        <a-card class="report-card health-card" :bordered="false">
          <div class="card-heading">
            <div>
              <span class="eyebrow">{{ t('report_center.health.eyebrow') }}</span>
              <h2>{{ t('report_center.health.title') }}</h2>
            </div>
          </div>
          <div class="health-list">
            <div class="health-row">
              <span>{{ t('report_center.health.total_cases') }}</span>
              <strong>{{ overview.total_cases }}</strong>
            </div>
            <div class="health-row">
              <span>{{ t('report_center.health.avg_duration') }}</span>
              <strong>{{ formatDuration(overview.avg_duration_ms) }}</strong>
            </div>
            <div class="health-row">
              <span>{{ t('report_center.health.defect_health') }}</span>
              <strong :class="overview.defect_health_rate < 80 ? 'value-warning' : 'value-good'">{{ overview.defect_health_rate.toFixed(1) }}%</strong>
            </div>
          </div>
          <div class="health-note">
            <span class="health-note-mark">i</span>
            <p>{{ t('report_center.health.definition') }}</p>
          </div>
        </a-card>
      </section>

      <section class="report-card protocol-card">
        <div class="card-heading runs-heading">
          <div>
            <span class="eyebrow">{{ t('report_center.protocol.eyebrow') }}</span>
            <h2>{{ t('report_center.protocol.title') }}</h2>
          </div>
          <span class="card-note">{{ t('report_center.protocol.note') }}</span>
        </div>
        <div v-if="overview.case_type_stats.length" class="protocol-list">
          <div v-for="item in overview.case_type_stats" :key="item.case_type" class="protocol-row">
            <div class="protocol-row-top">
              <strong>{{ caseTypeLabel(item.case_type) }}</strong>
              <span>{{ item.pass_rate.toFixed(1) }}%</span>
            </div>
            <div class="protocol-track"><span :style="{ width: `${Math.max(0, Math.min(item.pass_rate, 100))}%` }" /></div>
            <div class="protocol-meta">
              <span>{{ t('report_center.protocol.runs', { count: item.total_runs }) }}</span>
              <span>{{ t('report_center.protocol.result', { passed: item.passed_runs, failed: item.failed_runs + item.error_runs }) }}</span>
            </div>
          </div>
        </div>
        <a-empty v-else :description="t('report_center.protocol.empty')" />
      </section>

      <section class="report-card runs-card">
        <div class="card-heading runs-heading">
          <div>
            <span class="eyebrow">{{ t('report_center.runs.eyebrow') }}</span>
            <h2>{{ t('report_center.runs.title') }}</h2>
          </div>
          <span class="card-note">{{ t('report_center.runs.note') }}</span>
        </div>
        <a-table :data-source="overview.recent_runs" :columns="runColumns" :pagination="false" row-key="id" size="small">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'run'">
              <button class="run-link" type="button" @click="openRun(record.id)">
                <span>#{{ record.id }}</span>
                <strong>{{ record.case_name }}</strong>
              </button>
            </template>
            <template v-else-if="column.key === 'case_type'">
              <a-tag>{{ caseTypeLabel(record.case_type) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'duration'">
              {{ formatDuration(record.duration_ms) }}
            </template>
            <template v-else-if="column.key === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
          </template>
        </a-table>
        <a-empty v-if="!loading && !overview.recent_runs.length" :description="t('report_center.runs.empty')" />
      </section>

      <section class="report-card compare-card">
        <div class="card-heading runs-heading">
          <div>
            <span class="eyebrow">{{ t('report_center.compare.eyebrow') }}</span>
            <h2>{{ t('report_center.compare.title') }}</h2>
          </div>
          <span class="card-note">{{ t('report_center.compare.note') }}</span>
        </div>
        <div class="compare-controls">
          <div class="compare-select">
            <label>{{ t('report_center.compare.baseline') }}</label>
            <a-select v-model:value="baselineRunId" :options="runOptions" :placeholder="t('report_center.compare.select_run')" />
          </div>
          <span class="compare-arrow">→</span>
          <div class="compare-select">
            <label>{{ t('report_center.compare.current') }}</label>
            <a-select v-model:value="currentRunId" :options="runOptions" :placeholder="t('report_center.compare.select_run')" />
          </div>
          <a-button type="primary" :disabled="!canCompare" :loading="compareLoading" @click="compareRuns">
            {{ t('report_center.compare.action') }}
          </a-button>
        </div>
        <a-alert v-if="compareError" type="warning" show-icon :message="compareError" />
        <div v-if="comparison" class="comparison-result">
          <div class="comparison-banner" :class="comparison.has_regression ? 'is-regression' : 'is-improved'">
            <strong>{{ comparison.has_regression ? t('report_center.compare.regression') : t('report_center.compare.no_regression') }}</strong>
            <span>{{ comparison.current.case_name }} · #{{ comparison.baseline.id }} → #{{ comparison.current.id }}</span>
          </div>
          <a-table :data-source="comparison.metrics" :columns="compareColumns" :pagination="false" row-key="key" size="small">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'delta'">
                <span :class="metricDeltaClass(record)">{{ formatDelta(record.delta, record.unit) }}</span>
              </template>
            </template>
          </a-table>
        </div>
      </section>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { statisticsApi, projectApi, reportApi, type ProjectItem, type ReportCompareItem, type ReportOverviewItem } from '@/api'
import { useChartTheme } from '@/utils/chartTheme'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { chartTheme } = useChartTheme()

const projects = ref<ProjectItem[]>([])
const projectId = ref<number | undefined>(positiveInt(route.query.project_id))
const days = ref(reportDays(route.query.days))
const loading = ref(false)
const exporting = ref(false)
const loadError = ref(false)
const compareLoading = ref(false)
const compareError = ref('')
const baselineRunId = ref<number | undefined>()
const currentRunId = ref<number | undefined>()
const comparison = ref<ReportCompareItem | null>(null)
let requestSerial = 0

const emptyOverview = (selectedProjectId = projectId.value, selectedDays = days.value): ReportOverviewItem => ({
  project_id: selectedProjectId ?? null,
  days: selectedDays,
  total_cases: 0,
  executed_cases: 0,
  coverage_rate: 0,
  total_runs: 0,
  passed_runs: 0,
  failed_runs: 0,
  error_runs: 0,
  pass_rate: 0,
  avg_duration_ms: null,
  open_defects: 0,
  defect_health_rate: 100,
  quality_score: 0,
  trend: [],
  case_type_stats: [],
  recent_runs: [],
})
const overview = reactive<ReportOverviewItem>(emptyOverview())

const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: item.id })))
const dayOptions = computed(() => [
  { label: t('report_center.days.7'), value: 7 },
  { label: t('report_center.days.30'), value: 30 },
  { label: t('report_center.days.90'), value: 90 },
  { label: t('report_center.days.365'), value: 365 },
])
const runOptions = computed(() => overview.recent_runs.map((run) => ({
  label: `#${run.id} · ${run.case_name} · ${statusLabel(run.status)}`,
  value: run.id,
})))
const qualityLabel = computed(() => {
  if (overview.quality_score >= 90) return t('report_center.score.excellent')
  if (overview.quality_score >= 75) return t('report_center.score.good')
  if (overview.quality_score >= 60) return t('report_center.score.watch')
  return t('report_center.score.risk')
})
const scoreRingStyle = computed(() => ({ '--score': `${Math.max(0, Math.min(overview.quality_score, 100))}%` }))
const scoreBreakdown = computed(() => [
  { key: 'pass', label: t('report_center.score.pass_rate'), value: overview.pass_rate },
  { key: 'coverage', label: t('report_center.score.coverage'), value: overview.coverage_rate },
  { key: 'defect', label: t('report_center.score.defect_health'), value: overview.defect_health_rate },
])
const canCompare = computed(() => Boolean(baselineRunId.value && currentRunId.value && baselineRunId.value !== currentRunId.value))

const trendOption = computed(() => ({
  grid: { left: 42, right: 44, top: 28, bottom: 28 },
  tooltip: { trigger: 'axis' },
  legend: { top: 0, right: 0, data: [t('report_center.trend.runs'), t('report_center.trend.pass_rate')] },
  xAxis: { type: 'category', data: overview.trend.map((item) => item.date), boundaryGap: false },
  yAxis: [
    { type: 'value', name: t('report_center.trend.runs'), minInterval: 1 },
    { type: 'value', name: '%', min: 0, max: 100 },
  ],
  series: [
    { name: t('report_center.trend.runs'), type: 'bar', yAxisIndex: 0, barMaxWidth: 18, data: overview.trend.map((item) => item.total) },
    { name: t('report_center.trend.pass_rate'), type: 'line', yAxisIndex: 1, smooth: true, symbolSize: 7, data: overview.trend.map((item) => item.pass_rate) },
  ],
}))

const runColumns = computed(() => [
  { title: t('report_center.runs.run'), key: 'run' },
  { title: t('report_center.runs.type'), key: 'case_type', width: 110 },
  { title: t('report_center.runs.status'), key: 'status', width: 110 },
  { title: t('report_center.runs.duration'), key: 'duration', width: 120 },
  { title: t('report_center.runs.created_at'), key: 'created_at', width: 170 },
])
const compareColumns = computed(() => [
  { title: t('report_center.compare.metric'), dataIndex: 'label', key: 'label' },
  { title: t('report_center.compare.baseline_value'), dataIndex: 'baseline', key: 'baseline' },
  { title: t('report_center.compare.current_value'), dataIndex: 'current', key: 'current' },
  { title: t('report_center.compare.delta'), key: 'delta' },
])

function positiveInt(value: unknown) {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

function reportDays(value: unknown) {
  const parsed = positiveInt(value)
  return parsed === 7 || parsed === 30 || parsed === 90 || parsed === 365 ? parsed : 30
}

function filterProject(input: string, option: any) {
  return String(option.label || '').toLowerCase().includes(input.toLowerCase())
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function formatDuration(value?: number | null) {
  if (value == null) return '-'
  if (value < 1000) return `${Math.round(value)} ms`
  return `${(value / 1000).toFixed(1)} s`
}

function formatDelta(value: number, unit?: string | null) {
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${Number.isInteger(value) ? value : value.toFixed(1)}${unit ? ` ${unit}` : ''}`
}

function metricDeltaClass(record: Record<string, any>) {
  const bad = record.key === 'failed_steps' || record.key === 'error_steps' || record.key === 'duration_ms'
  return bad ? (record.delta > 0 ? 'delta-bad' : 'delta-good') : 'delta-neutral'
}

function statusLabel(status: string) {
  return t(`report_center.status.${status}`, status)
}

function statusColor(status: string) {
  return ({ passed: 'green', failed: 'red', error: 'orange', pending: 'default', running: 'blue' } as Record<string, string>)[status] || 'default'
}

function caseTypeLabel(caseType: string) {
  return t(`report_center.case_type.${caseType}`, caseType)
}

function openRun(runId: number) {
  void router.push({ name: 'run-detail', params: { runId } })
}

function openAsset(path: '/cases' | '/suites' | '/plans') {
  void router.push({
    path,
    query: projectId.value ? { project_id: String(projectId.value) } : undefined,
  })
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    projects.value = []
  }
}

async function loadReport() {
  const serial = ++requestSerial
  loading.value = true
  loadError.value = false
  try {
    const result = await reportApi.overview({ project_id: projectId.value, days: days.value, recent_limit: 20 })
    if (serial !== requestSerial) return
    Object.assign(overview, result)
    const ids = new Set(result.recent_runs.map((run) => run.id))
    if (!baselineRunId.value || !ids.has(baselineRunId.value)) baselineRunId.value = result.recent_runs[1]?.id
    if (!currentRunId.value || !ids.has(currentRunId.value)) currentRunId.value = result.recent_runs[0]?.id
    comparison.value = null
    compareError.value = ''
  } catch {
    if (serial === requestSerial) {
      loadError.value = true
      Object.assign(overview, emptyOverview())
      baselineRunId.value = undefined
      currentRunId.value = undefined
      comparison.value = null
      compareError.value = ''
    }
  } finally {
    if (serial === requestSerial) loading.value = false
  }
}

async function compareRuns() {
  if (!baselineRunId.value || !currentRunId.value || baselineRunId.value === currentRunId.value) return
  compareLoading.value = true
  compareError.value = ''
  try {
    comparison.value = await reportApi.compare({ baseline_run_id: baselineRunId.value, current_run_id: currentRunId.value })
  } catch {
    comparison.value = null
    compareError.value = t('report_center.compare.failed')
  } finally {
    compareLoading.value = false
  }
}

async function exportTrend() {
  exporting.value = true
  try {
    const blob = await statisticsApi.exportCsv({ chart: 'pass_rate_trend', project_id: projectId.value, days: days.value, aggregate: 'daily' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `atp-report-trend-${days.value}d.csv`
    anchor.click()
    URL.revokeObjectURL(url)
    message.success(t('report_center.export_success'))
  } catch {
    message.error(t('report_center.export_failed'))
  } finally {
    exporting.value = false
  }
}

watch([projectId, days], ([nextProjectId, nextDays]) => {
  void router.replace({
    query: {
      ...route.query,
      project_id: nextProjectId ? String(nextProjectId) : undefined,
      days: String(nextDays),
    },
  })
  if (nextDays !== overview.days || nextProjectId !== overview.project_id) void loadReport()
})

onMounted(async () => {
  await loadProjects()
  await loadReport()
})
</script>

<style scoped>
.report-page {
  --report-ink: #172033;
  --report-muted: #7c879c;
  --report-line: #e6eaf2;
  min-height: calc(100vh - 132px);
  color: var(--report-ink);
}

.report-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 2px 24px;
  border-bottom: 1px solid var(--report-line);
}

.hero-kicker,
.eyebrow {
  color: #4f46e5;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .15em;
}

.hero-kicker { margin-bottom: 8px; }
.hero-copy h1 { margin: 0; font-size: clamp(28px, 3vw, 40px); letter-spacing: -.045em; }
.hero-copy p { max-width: 660px; margin: 9px 0 0; color: var(--report-muted); line-height: 1.7; }
.hero-controls { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.project-select { min-width: 190px; }
.days-select { width: 112px; }
.report-alert { margin: 18px 0; }

.signal-grid {
  display: grid;
  grid-template-columns: minmax(340px, 1.8fr) repeat(3, minmax(150px, 1fr));
  gap: 12px;
  margin: 20px 0;
}

.score-card,
.metric-card,
.report-card {
  border: 1px solid var(--report-line);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(32, 46, 86, .045);
}

.score-card { padding: 20px; background: linear-gradient(135deg, #f8f9ff 0%, #fff 58%, #f9fbff 100%); }
.score-card-top, .card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.score-card h2, .card-heading h2 { margin: 5px 0 0; font-size: 19px; letter-spacing: -.02em; }
.score-period, .card-note { color: var(--report-muted); font-size: 12px; white-space: nowrap; }
.score-main { display: flex; align-items: center; gap: 20px; margin: 18px 0 16px; }
.score-ring { display: grid; width: 126px; height: 126px; flex: 0 0 126px; place-items: center; border-radius: 50%; background: conic-gradient(#4f46e5 var(--score), #e8ebf6 0); }
.score-ring-inner { display: flex; width: 96px; height: 96px; flex-direction: column; align-items: center; justify-content: center; border-radius: 50%; background: #fff; }
.score-ring-inner strong { font-size: 30px; letter-spacing: -.06em; }
.score-ring-inner span { color: var(--report-muted); font-size: 11px; }
.score-copy strong { display: block; font-size: 20px; }
.score-copy p { max-width: 260px; margin: 7px 0 12px; color: var(--report-muted); font-size: 12px; line-height: 1.6; }
.score-breakdown { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.breakdown-label { display: flex; justify-content: space-between; gap: 8px; color: var(--report-muted); font-size: 11px; }
.breakdown-label strong { color: var(--report-ink); }
.breakdown-track { height: 5px; margin-top: 7px; overflow: hidden; border-radius: 4px; background: #e9ecf5; }
.breakdown-track span { display: block; height: 100%; border-radius: inherit; background: #4f46e5; transition: width .35s ease; }

.metric-card { display: flex; min-height: 178px; flex-direction: column; padding: 19px; overflow: hidden; }
.metric-card::after { width: 100px; height: 100px; margin: auto -40px -48px auto; content: ''; border: 1px solid rgba(255, 255, 255, .28); border-radius: 50%; }
.metric-card strong { margin-top: 20px; color: #fff; font-size: 34px; letter-spacing: -.06em; }
.metric-card > span:not(.metric-kicker) { color: rgba(255, 255, 255, .78); font-size: 12px; }
.metric-kicker { color: rgba(255, 255, 255, .72); font-size: 11px; font-weight: 800; letter-spacing: .12em; }
.metric-foot { display: flex; justify-content: space-between; gap: 8px; margin-top: auto; color: rgba(255, 255, 255, .72); font-size: 11px; }
.metric-foot b { color: #fff; }
.metric-card-indigo { background: linear-gradient(145deg, #4f46e5, #6d63ed); }
.metric-card-teal { background: linear-gradient(145deg, #087f8c, #13a6a0); }
.metric-card-amber { background: linear-gradient(145deg, #b76e13, #d99426); }

.report-two-column { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(280px, .8fr); gap: 16px; margin-bottom: 16px; }
.report-card { padding: 20px; }
.trend-chart { width: 100%; height: 310px; margin-top: 12px; }
.health-card { background: #fbfcfe; }
.health-list { margin-top: 20px; }
.health-row { display: flex; align-items: center; justify-content: space-between; padding: 15px 0; border-bottom: 1px solid var(--report-line); color: var(--report-muted); font-size: 13px; }
.health-row strong { color: var(--report-ink); font-size: 18px; }
.value-good { color: #159a6b !important; }
.value-warning { color: #c17a15 !important; }
.health-note { display: flex; gap: 9px; margin-top: 20px; color: var(--report-muted); font-size: 12px; line-height: 1.6; }
.health-note-mark { display: grid; width: 19px; height: 19px; flex: 0 0 19px; place-items: center; border-radius: 50%; color: #4f46e5; background: #e9eaff; font-weight: 800; }
.health-note p { margin: 0; }
.protocol-card { margin-bottom: 16px; }
.protocol-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 20px; }
.protocol-row { padding: 14px; border: 1px solid var(--report-line); border-radius: 10px; background: #fbfcfe; }
.protocol-row-top, .protocol-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.protocol-row-top { color: var(--report-ink); font-size: 14px; }
.protocol-row-top span { color: #4f46e5; font-weight: 800; }
.protocol-track { height: 7px; margin: 13px 0 10px; overflow: hidden; border-radius: 5px; background: #e9ecf5; }
.protocol-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #4f46e5, #16a085); transition: width .35s ease; }
.protocol-meta { color: var(--report-muted); font-size: 11px; }
.runs-card, .compare-card { margin-bottom: 16px; }
.runs-heading { margin-bottom: 16px; }
.run-link { display: inline-flex; flex-direction: column; align-items: flex-start; padding: 0; border: 0; color: var(--report-ink); background: transparent; text-align: left; cursor: pointer; }
.run-link span { color: #4f46e5; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; }
.run-link strong { margin-top: 3px; font-size: 13px; }
.run-link:hover strong { color: #4f46e5; }
.compare-controls { display: flex; align-items: flex-end; gap: 12px; }
.compare-select { display: flex; min-width: 260px; flex: 1; flex-direction: column; gap: 7px; }
.compare-select label { color: var(--report-muted); font-size: 12px; font-weight: 700; }
.compare-arrow { padding-bottom: 7px; color: #4f46e5; font-size: 22px; }
.comparison-result { margin-top: 20px; }
.comparison-banner { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 12px; padding: 12px 14px; border-radius: 10px; color: #19724f; background: #effaf4; font-size: 12px; }
.comparison-banner.is-regression { color: #ad541d; background: #fff6e9; }
.comparison-banner strong { font-size: 14px; }
.delta-bad { color: #c74e3a; font-weight: 700; }
.delta-good { color: #159a6b; font-weight: 700; }
.delta-neutral { color: var(--report-ink); font-weight: 700; }

.run-link:focus-visible, .score-card:focus-visible { outline: 3px solid rgba(79, 70, 229, .32); outline-offset: 3px; }
@media (max-width: 1100px) {
  .signal-grid { grid-template-columns: repeat(3, 1fr); }
  .score-card { grid-column: 1 / -1; }
}
@media (max-width: 820px) {
  .report-hero { align-items: flex-start; flex-direction: column; }
  .hero-controls { justify-content: flex-start; width: 100%; }
  .report-two-column { grid-template-columns: 1fr; }
  .compare-controls { align-items: stretch; flex-direction: column; }
  .compare-arrow { align-self: center; padding: 0; transform: rotate(90deg); }
  .compare-select { min-width: 0; }
}
@media (max-width: 560px) {
  .signal-grid { grid-template-columns: 1fr; }
  .score-main { align-items: flex-start; flex-direction: column; }
  .score-breakdown { grid-template-columns: 1fr; }
  .score-period, .card-note { white-space: normal; }
  .project-select { min-width: 0; width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
.breakdown-track span { transition: none; }
.protocol-track span { transition: none; }
}
</style>
