<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="全生命周期多维质量健康综合评分仪表盘与诊断控制台"
    destroy-on-close
    class="health-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制说明 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <DashboardOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">多维质量健康加权融合模型与 P0 缺陷一票否决引擎 (T4.1)</div>
          <div class="banner-desc">
            告别单一通过率盲区！融合测试执行 (25%)、代码覆盖率 (20%)、变异测试有效性 (15%)、未修复缺陷惩罚 (20%)、变更风险 (10%) 与基础设施合规 (10%) 6 大维度；具备未修复 P0 缺陷一票否决硬约束，输出严谨权威的系统质量健康度与 A+ 评级。
          </div>
        </div>
      </div>

      <!-- 场景预设与快速计算控制栏 -->
      <div class="config-section">
        <div class="section-title">质量评估场景预设与参数</div>
        <div class="config-row">
          <div class="preset-group">
            <span class="label">评估场景预设:</span>
            <a-radio-group v-model:value="selectedPreset" size="small" @change="handlePresetChange">
              <a-radio-button value="grade_a_plus">卓越发版候选 (A+ 极高可靠度)</a-radio-button>
              <a-radio-button value="p0_veto">P0 缺陷一票否决 (强制锁定 C 级)</a-radio-button>
              <a-radio-button value="coverage_penalty">覆盖率与变异不足 (B 级风险预警)</a-radio-button>
            </a-radio-group>
          </div>
          <a-button type="primary" size="small" :loading="calculating" @click="handleCalculate">
            <ThunderboltOutlined /> 计算综合质量评分
          </a-button>
        </div>
      </div>

      <!-- P0 一票否决警报大横幅 -->
      <a-alert
        v-if="currentReport?.grade === 'C' && hasP0Risk"
        type="error"
        show-icon
        message="严重质量风险：检测到未解决的 P0 核心阻塞级缺陷，已触发一票否决限制！"
        description="系统综合健康得分强制上限截断为 65.0 分，系统质量等级强制评定为 C (高危阻断)，必须修复 P0 缺陷方可进入发布流转！"
        class="mb-3"
      />

      <!-- 4 大核心 KPI 统计卡片 -->
      <a-row :gutter="[16, 16]" class="kpi-row">
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">多维质量健康综合得分</div>
            <div class="stat-value" :class="getScoreColorClass(currentReport?.composite_score ?? 90)">
              {{ currentReport?.composite_score ?? 90 }} <span class="unit">/ 100</span>
            </div>
            <div class="stat-trend">6 大核心维度加权总评</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">系统质量健康等级</div>
            <div class="stat-value" :class="getGradeColorClass(currentReport?.grade ?? 'A+')">
              {{ currentReport?.grade ?? 'A+' }}
            </div>
            <div class="stat-trend">{{ getGradeDesc(currentReport?.grade ?? 'A+') }}</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">P0 一票否决状态</div>
            <div class="stat-value" :class="hasP0Risk ? 'text-danger' : 'text-success'">
              {{ hasP0Risk ? '触发否决' : '未触发' }}
            </div>
            <div class="stat-trend">{{ hasP0Risk ? '核心阻塞缺陷阻断' : '主交易路径无阻塞' }}</div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <div class="stat-card">
            <div class="stat-label">识别核心风险因子数</div>
            <div class="stat-value text-warning">
              {{ currentReport?.primary_risk_factors.length ?? 0 }} <span class="unit">项</span>
            </div>
            <div class="stat-trend">针对性归因分析排查</div>
          </div>
        </a-col>
      </a-row>

      <!-- 双栏布局：左侧 6 维子分与权重 + 右侧风险归因与优化指引 -->
      <div class="workbench-layout">
        <!-- 左侧：6 维加权子分进度条 -->
        <div class="dimensions-panel">
          <div class="panel-header">
            <span class="panel-title"><BarChartOutlined /> 6 大质量维度健康子分与权重矩阵</span>
            <span class="text-xs text-muted">加权基准模型</span>
          </div>

          <div class="dimensions-list">
            <div class="dim-item">
              <div class="dim-header">
                <span class="dim-name">自动化测试执行通过率 (权重: 25%)</span>
                <span class="dim-score text-primary">{{ currentReport?.dimension_scores?.test_execution ?? 100 }} 分</span>
              </div>
              <a-progress
                :percent="currentReport?.dimension_scores?.test_execution ?? 100"
                size="small"
                stroke-color="#2563eb"
              />
            </div>

            <div class="dim-item">
              <div class="dim-header">
                <span class="dim-name">核心业务代码覆盖率 (权重: 20%)</span>
                <span class="dim-score text-success">{{ currentReport?.dimension_scores?.code_coverage ?? 90 }} 分</span>
              </div>
              <a-progress
                :percent="currentReport?.dimension_scores?.code_coverage ?? 90"
                size="small"
                stroke-color="#10b981"
              />
            </div>

            <div class="dim-item">
              <div class="dim-header">
                <span class="dim-name">变异测试断言有效性 (权重: 15%)</span>
                <span class="dim-score text-purple">{{ currentReport?.dimension_scores?.mutation_score ?? 85 }} 分</span>
              </div>
              <a-progress
                :percent="currentReport?.dimension_scores?.mutation_score ?? 85"
                size="small"
                stroke-color="#7c3aed"
              />
            </div>

            <div class="dim-item">
              <div class="dim-header">
                <span class="dim-name">未解决缺陷密度健康分 (权重: 20%)</span>
                <span class="dim-score text-danger">{{ currentReport?.dimension_scores?.defect_density ?? 100 }} 分</span>
              </div>
              <a-progress
                :percent="currentReport?.dimension_scores?.defect_density ?? 100"
                size="small"
                stroke-color="#dc2626"
              />
            </div>

            <div class="dim-item">
              <div class="dim-header">
                <span class="dim-name">代码变更安全低风险度 (权重: 10%)</span>
                <span class="dim-score text-warning">{{ currentReport?.dimension_scores?.change_risk ?? 95 }} 分</span>
              </div>
              <a-progress
                :percent="currentReport?.dimension_scores?.change_risk ?? 95"
                size="small"
                stroke-color="#d97706"
              />
            </div>

            <div class="dim-item">
              <div class="dim-header">
                <span class="dim-name">基础设施与 IaC 合规度 (权重: 10%)</span>
                <span class="dim-score text-success">{{ currentReport?.dimension_scores?.env_compliance ?? 100 }} 分</span>
              </div>
              <a-progress
                :percent="currentReport?.dimension_scores?.env_compliance ?? 100"
                size="small"
                stroke-color="#059669"
              />
            </div>
          </div>
        </div>

        <!-- 右侧：核心扣分归因与研发优化指引 -->
        <div class="analysis-panel">
          <div class="panel-header">
            <span class="panel-title"><FileTextOutlined /> 首要风险归因与研发质量优化指引</span>
          </div>

          <div class="analysis-content">
            <div class="risk-section mb-3">
              <div class="box-title text-danger">⚠️ 首要扣分风险因素:</div>
              <div class="risk-list">
                <div
                  v-for="(risk, idx) in currentReport?.primary_risk_factors ?? []"
                  :key="idx"
                  class="risk-bubble"
                >
                  <span class="bubble-num">{{ idx + 1 }}</span>
                  <span class="bubble-text">{{ risk }}</span>
                </div>
              </div>
            </div>

            <div class="recommendation-section">
              <div class="box-title text-primary">💡 针对性质量提升优化建议:</div>
              <div class="rec-list">
                <div
                  v-for="(rec, idx) in currentReport?.optimization_recommendations ?? []"
                  :key="idx"
                  class="rec-bubble"
                >
                  <span class="bubble-num green">{{ idx + 1 }}</span>
                  <span class="bubble-text">{{ rec }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  DashboardOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'
import {
  qualityHealthScoreApi,
  type QualityHealthScoreResult,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const calculating = ref(false)
const selectedPreset = ref<'grade_a_plus' | 'p0_veto' | 'coverage_penalty'>('grade_a_plus')
const currentReport = ref<QualityHealthScoreResult | null>(null)

const PRESET_METRICS = {
  grade_a_plus: {
    target_name: 'release-v4.3.0',
    test_pass_rate_pct: 100.0,
    code_coverage_pct: 92.0,
    mutation_score_pct: 88.0,
    p0_defects_count: 0,
    p1_defects_count: 0,
    p2_defects_count: 0,
    change_risk_score: 5.0,
    compliance_score_pct: 100.0,
  },
  p0_veto: {
    target_name: 'release-with-p0',
    test_pass_rate_pct: 100.0,
    code_coverage_pct: 95.0,
    mutation_score_pct: 90.0,
    p0_defects_count: 1, // 存在 P0 一票否决
    p1_defects_count: 0,
    p2_defects_count: 0,
    change_risk_score: 5.0,
    compliance_score_pct: 100.0,
  },
  coverage_penalty: {
    target_name: 'feature-sprint-low-coverage',
    test_pass_rate_pct: 96.0,
    code_coverage_pct: 70.0,
    mutation_score_pct: 60.0,
    p0_defects_count: 0,
    p1_defects_count: 2,
    p2_defects_count: 2,
    change_risk_score: 30.0,
    compliance_score_pct: 90.0,
  },
}

const hasP0Risk = computed(() => {
  if (!currentReport.value) return false
  return currentReport.value.primary_risk_factors.some((r) => r.includes('P0'))
})

function handleClose() {
  emit('update:open', false)
}

function handlePresetChange() {
  handleCalculate()
}

function getGradeColorClass(grade: string) {
  switch (grade) {
    case 'A+': return 'text-success'
    case 'A': return 'text-primary'
    case 'B': return 'text-warning'
    case 'C': return 'text-danger'
    default: return 'text-primary'
  }
}

function getGradeDesc(grade: string) {
  switch (grade) {
    case 'A+': return '卓越品质 · 极高可靠度准入放行'
    case 'A': return '良好达标 · 常规准入放行'
    case 'B': return '风险预警 · 需重点灰度观察'
    case 'C': return '高危阻断 · 禁止上线发版'
    default: return '质量达标'
  }
}

function getScoreColorClass(score: number) {
  if (score >= 90) return 'text-success'
  if (score >= 80) return 'text-primary'
  if (score >= 70) return 'text-warning'
  return 'text-danger'
}

async function handleCalculate() {
  calculating.value = true
  try {
    const p = PRESET_METRICS[selectedPreset.value]
    const res = await qualityHealthScoreApi.calculate(p)
    currentReport.value = res.report
    message.success(res.message || '质量健康综合评分计算完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '计算失败')
  } finally {
    calculating.value = false
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      handleCalculate()
    }
  }
)

onMounted(() => {
  if (props.open) {
    handleCalculate()
  }
})
</script>

<style scoped>
.health-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #2563eb;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #3b82f6;
  line-height: 1.5;
}

.config-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 10px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.preset-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.kpi-row {
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
}

.stat-value {
  font-size: 22px;
  font-weight: 800;
  margin: 4px 0;
}

.stat-value .unit {
  font-size: 12px;
  font-weight: normal;
  color: #94a3b8;
}

.stat-trend {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-danger { color: #dc2626; }
.text-purple { color: #7c3aed; }

.workbench-layout {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 16px;
}

.dimensions-panel,
.analysis-panel {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.dimensions-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dim-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
}

.dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.dim-name {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.dim-score {
  font-size: 12px;
  font-weight: 800;
}

.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.box-title {
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 6px;
}

.risk-list,
.rec-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.risk-bubble,
.rec-bubble {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 11px;
}

.risk-bubble {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  color: #991b1b;
}

.rec-bubble {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #14532d;
}

.bubble-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #dc2626;
  color: #ffffff;
  font-size: 10px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bubble-num.green {
  background: #16a34a;
}

.bubble-text {
  flex: 1;
  line-height: 1.4;
}

.mb-3 { margin-bottom: 12px; }
.text-xs { font-size: 11px; }
.text-muted { color: #94a3b8; }
</style>
