<template>
  <div class="page-shell quality-metrics-dashboard">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <h2 class="page-title">全生命周期软件测试质量度量大盘</h2>
        <p class="page-subtitle">
          基于用例覆盖率 (30%)、缺陷逃逸率 (20%)、执行稳定性 (25%) 与 MTTR (25%) 四维加权度量模型，量化项目质量健康度与发版准入评级。
        </p>
      </div>

      <div class="hero-actions">
        <a-space size="small">
          <span class="proj-label">项目:</span>
          <a-input-number
            v-model:value="projectId"
            :min="1"
            size="small"
            style="width: 70px"
          />
          <a-button :loading="loading" size="small" @click="loadMetrics">
            刷新大盘
          </a-button>
          <a-button type="primary" size="small" @click="simulatorModalOpen = true">
            指标推演模拟器
          </a-button>
          <a-button type="primary" danger size="small" @click="gateDrawerOpen = true">
            CI/CD 质量门禁配置
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 发版准入与综合评分 Hero 卡片 -->
    <a-card v-if="report" size="small" class="verdict-hero-card">
      <div class="verdict-box">
        <div class="score-display">
          <span class="score-label">综合质量健康评分</span>
          <div class="score-num-box">
            <strong class="score-num">{{ report.composite_health_score }}</strong>
            <span class="score-max">/ 100</span>
          </div>
        </div>

        <div class="verdict-divider" />

        <div class="grade-display">
          <span class="meta-label">质量等级 (Grade)</span>
          <div class="grade-badge" :class="`grade-${report.grade.toLowerCase()}`">
            {{ report.grade }}
          </div>
        </div>

        <div class="verdict-divider" />

        <div class="readiness-display">
          <span class="meta-label">发版准入终审结论 (Release Verdict)</span>
          <div class="verdict-badge">
            <a-tag :color="getVerdictColor(report.release_readiness)" class="verdict-tag">
              {{ getVerdictLabel(report.release_readiness) }}
            </a-tag>
          </div>
          <span class="verdict-desc">{{ getVerdictDesc(report.release_readiness) }}</span>
        </div>
      </div>
    </a-card>

    <!-- 四维加权维度指标卡片行 -->
    <div v-if="report" class="dimensions-row">
      <!-- 维度 1: 自动化用例覆盖率 -->
      <div class="dimension-card">
        <div class="dim-header">
          <span class="dim-title">自动化覆盖率 (Coverage)</span>
          <a-tag color="blue">权重 30%</a-tag>
        </div>
        <div class="dim-score">
          <strong class="text-blue">{{ report.dimensions.coverage.score }}</strong>
          <small class="dim-unit">分</small>
        </div>
        <div class="dim-metrics">
          <span>自动化用例: <strong>{{ report.dimensions.coverage.metrics.automated_cases }}</strong></span>
          <span>总用例: <strong>{{ report.dimensions.coverage.metrics.total_cases }}</strong></span>
          <span>覆盖率: <strong class="text-blue">{{ report.dimensions.coverage.metrics.coverage_pct }}%</strong></span>
        </div>
      </div>

      <!-- 维度 2: 缺陷逃逸率 -->
      <div class="dimension-card">
        <div class="dim-header">
          <span class="dim-title">缺陷逃逸 (Defect Escape)</span>
          <a-tag color="purple">权重 20%</a-tag>
        </div>
        <div class="dim-score">
          <strong class="text-purple">{{ report.dimensions.defect_escape.score }}</strong>
          <small class="dim-unit">分</small>
        </div>
        <div class="dim-metrics">
          <span>生产漏测: <strong :class="report.dimensions.defect_escape.metrics.prod_escapes > 0 ? 'text-red' : 'text-green'">{{ report.dimensions.defect_escape.metrics.prod_escapes }}</strong></span>
          <span>内部发现: <strong>{{ report.dimensions.defect_escape.metrics.internal_defects }}</strong></span>
          <span>逃逸率: <strong>{{ report.dimensions.defect_escape.metrics.escape_rate_pct }}%</strong></span>
        </div>
      </div>

      <!-- 维度 3: 执行稳定性 -->
      <div class="dimension-card">
        <div class="dim-header">
          <span class="dim-title">执行稳定性 (Stability)</span>
          <a-tag color="cyan">权重 25%</a-tag>
        </div>
        <div class="dim-score">
          <strong class="text-cyan">{{ report.dimensions.execution_stability.score }}</strong>
          <small class="dim-unit">分</small>
        </div>
        <div class="dim-metrics">
          <span>总执行次数: <strong>{{ report.dimensions.execution_stability.metrics.total_runs }}</strong></span>
          <span>Flaky 波动: <strong :class="report.dimensions.execution_stability.metrics.flaky_runs > 0 ? 'text-orange' : 'text-green'">{{ report.dimensions.execution_stability.metrics.flaky_runs }}</strong></span>
          <span>波动率: <strong>{{ report.dimensions.execution_stability.metrics.flaky_ratio_pct }}%</strong></span>
        </div>
      </div>

      <!-- 维度 4: MTTR 修复时长 -->
      <div class="dimension-card">
        <div class="dim-header">
          <span class="dim-title">修复时效 (MTTR)</span>
          <a-tag color="green">权重 25%</a-tag>
        </div>
        <div class="dim-score">
          <strong class="text-green">{{ report.dimensions.mttr.score }}</strong>
          <small class="dim-unit">分</small>
        </div>
        <div class="dim-metrics">
          <span>平均修复时长: <strong>{{ report.dimensions.mttr.metrics.mttr_hours }}</strong> 小时</span>
          <span>时效达标: <strong class="text-green">PASS</strong></span>
        </div>
      </div>
    </div>

    <!-- 主体区域：ECharts 四维加权雷达图 + 改进建议面板 -->
    <a-row v-if="report" :gutter="14" class="chart-section-row">
      <a-col :span="13">
        <a-card size="small" title="四维加权质量全景雷达图 (Multi-Dimensional Quality Radar)" class="radar-card">
          <div class="radar-container">
            <VChart :option="radarChartOption" autoresize class="echarts-view" />
          </div>
        </a-card>
      </a-col>

      <a-col :span="11">
        <a-card size="small" title="全生命周期质量改进建议 (Actionable Insights)" class="insights-card">
          <div class="recommendations-box">
            <div
              v-for="(rec, idx) in report.actionable_recommendations"
              :key="idx"
              class="rec-item"
            >
              <div class="rec-index">{{ idx + 1 }}</div>
              <span class="rec-text">{{ rec }}</span>
            </div>

            <div v-if="report.actionable_recommendations.length === 0" class="empty-rec">
              <span>项目质量指标表现优异，暂无阻断性风险项。</span>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 指标推演模拟器弹窗 -->
    <a-modal
      v-model:open="simulatorModalOpen"
      title="全生命周期质量指标在线推演模拟器"
      width="640px"
      :footer="null"
      destroy-on-close
    >
      <div class="simulator-box">
        <p class="sim-desc">
          调节以下四维核心输入参数，实时推演预测发版准入终审结论与综合质量评分：
        </p>

        <a-form layout="vertical" class="sim-form">
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="总用例数">
                <a-input-number v-model:value="simTotalCases" :min="1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="自动化用例数">
                <a-input-number v-model:value="simAutomatedCases" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="内部发现缺陷数">
                <a-input-number v-model:value="simInternalDefects" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="生产逃逸缺陷数">
                <a-input-number v-model:value="simProdEscapes" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="总执行次数">
                <a-input-number v-model:value="simTotalRuns" :min="1" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="Flaky 波动失败次数">
                <a-input-number v-model:value="simFlakyRuns" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item label="平均故障修复时长 MTTR (小时)">
            <a-input-number v-model:value="simMttrHours" :min="0.1" :step="0.5" style="width: 100%" />
          </a-form-item>

          <div class="sim-actions">
            <a-button type="primary" :loading="evaluating" @click="handleEvaluateSimulation">
              即刻执行推演计算
            </a-button>
          </div>
        </a-form>
      </div>
    </a-modal>
    <QualityGateRuleConfigDrawer v-model:open="gateDrawerOpen" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  qualityGovernanceApi,
  type QualityMetricsReport,
  type ReleaseVerdict,
} from '@/api/qualityGovernance'
import QualityGateRuleConfigDrawer from './components/QualityGateRuleConfigDrawer.vue'

const projectId = ref<number>(1)
const loading = ref<boolean>(false)
const evaluating = ref<boolean>(false)
const simulatorModalOpen = ref<boolean>(false)
const gateDrawerOpen = ref<boolean>(false)

const report = ref<QualityMetricsReport | null>(null)

// 模拟器参数
const simTotalCases = ref(100)
const simAutomatedCases = ref(85)
const simInternalDefects = ref(40)
const simProdEscapes = ref(0)
const simTotalRuns = ref(50)
const simFlakyRuns = ref(2)
const simMttrHours = ref(3.5)

function getVerdictColor(v: ReleaseVerdict): string {
  switch (v) {
    case 'APPROVED':
      return 'green'
    case 'WARNING':
      return 'orange'
    case 'BLOCKED':
      return 'red'
    default:
      return 'default'
  }
}

function getVerdictLabel(v: ReleaseVerdict): string {
  switch (v) {
    case 'APPROVED':
      return '准予发版 (APPROVED)'
    case 'WARNING':
      return '风险发版 (WARNING)'
    case 'BLOCKED':
      return '阻断发版 (BLOCKED)'
    default:
      return v
  }
}

function getVerdictDesc(v: ReleaseVerdict): string {
  switch (v) {
    case 'APPROVED':
      return '各项质量维稳指标严格合规，全维度无破坏性阻断项，具备生产发版条件。'
    case 'WARNING':
      return '存在中度质量风险指标，建议关注生产漏测与用例稳定性后审慎放行。'
    case 'BLOCKED':
      return '核心指标未达发版安全红线，流水线已强制卡点阻断，禁止上线。'
    default:
      return ''
  }
}

const radarChartOption = computed<EChartsOption>(() => {
  if (!report.value) return {}
  const dims = report.value.dimensions

  return {
    tooltip: {
      trigger: 'item',
    },
    legend: {
      data: ['当前项目实际评分', '卓越基线目标 (Benchmark)'],
      textStyle: { color: '#64748b', fontSize: 11 },
      top: 0,
    },
    radar: {
      indicator: [
        { name: '自动化覆盖率 (30%)', max: 100 },
        { name: '缺陷零逃逸 (20%)', max: 100 },
        { name: '执行稳定性 (25%)', max: 100 },
        { name: 'MTTR 修复时效 (25%)', max: 100 },
      ],
      shape: 'polygon',
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(241, 245, 249, 0.6)', 'rgba(248, 250, 252, 0.4)'],
        },
      },
    },
    series: [
      {
        name: '四维质量指标分布',
        type: 'radar',
        data: [
          {
            value: [
              dims.coverage.score,
              dims.defect_escape.score,
              dims.execution_stability.score,
              dims.mttr.score,
            ],
            name: '当前项目实际评分',
            itemStyle: { color: '#2563eb' },
            areaStyle: { color: 'rgba(37, 99, 235, 0.25)' },
          },
          {
            value: [90, 95, 90, 85],
            name: '卓越基线目标 (Benchmark)',
            itemStyle: { color: '#10b981' },
            areaStyle: { color: 'rgba(16, 185, 129, 0.15)' },
          },
        ],
      },
    ],
  }
})

async function loadMetrics() {
  loading.value = true
  try {
    const res = await qualityGovernanceApi.getProjectMetrics(projectId.value)
    report.value = res
  } catch (err: any) {
    message.error(err.message || '获取质量度量大盘失败')
  } finally {
    loading.value = false
  }
}

async function handleEvaluateSimulation() {
  evaluating.value = true
  try {
    const res = await qualityGovernanceApi.evaluateCustomMetrics({
      project_id: projectId.value,
      total_cases: simTotalCases.value,
      automated_cases: simAutomatedCases.value,
      internal_defects: simInternalDefects.value,
      prod_escapes: simProdEscapes.value,
      total_runs: simTotalRuns.value,
      flaky_runs: simFlakyRuns.value,
      mttr_hours: simMttrHours.value,
    })
    report.value = res
    simulatorModalOpen.value = false
    message.success('指标推演完成，大盘已即时刷新！')
  } catch (err: any) {
    message.error(err.message || '指标推演计算失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  loadMetrics()
})
</script>

<style scoped>
.quality-metrics-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text, #0f172a);
}

.page-subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.proj-label {
  font-size: 12px;
  color: #64748b;
}

.verdict-hero-card,
.radar-card,
.insights-card {
  border-radius: 8px;
}

.verdict-box {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 8px 12px;
}

.score-display {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.score-label,
.meta-label {
  font-size: 11px;
  color: #64748b;
}

.score-num-box {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.score-num {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
}

.score-max {
  font-size: 14px;
  color: #94a3b8;
}

.verdict-divider {
  width: 1px;
  height: 48px;
  background: var(--c-border, #e2e8f0);
}

.grade-display {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.grade-badge {
  font-size: 26px;
  font-weight: 800;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.grade-a {
  background: #dcfce7;
  color: #16a34a;
}

.grade-b {
  background: #dbeafe;
  color: #2563eb;
}

.grade-c {
  background: #ffedd5;
  color: #ea580c;
}

.grade-d {
  background: #fee2e2;
  color: #dc2626;
}

.readiness-display {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.verdict-tag {
  font-size: 14px;
  font-weight: 600;
  padding: 2px 10px;
}

.verdict-desc {
  font-size: 12px;
  color: #64748b;
}

.dimensions-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.dimension-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dim-title {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.dim-score {
  font-size: 22px;
  font-weight: 700;
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.dim-unit {
  font-size: 11px;
  font-weight: normal;
  color: #94a3b8;
}

.dim-metrics {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: #64748b;
  border-top: 1px dashed var(--c-border, #e2e8f0);
  padding-top: 6px;
}

.text-blue {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

.text-cyan {
  color: #06b6d4;
}

.text-green {
  color: #16a34a;
}

.text-orange {
  color: #ea580c;
}

.text-red {
  color: #dc2626;
}

.radar-container {
  height: 340px;
  width: 100%;
}

.echarts-view {
  height: 100%;
  width: 100%;
}

.recommendations-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 340px;
  overflow-y: auto;
}

.rec-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 10px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 6px;
  border-left: 3px solid #2563eb;
}

.rec-index {
  width: 20px;
  height: 20px;
  background: #2563eb;
  color: #ffffff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.rec-text {
  font-size: 12px;
  color: #334155;
  line-height: 1.5;
}

.empty-rec {
  padding: 24px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
}

.sim-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.sim-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
