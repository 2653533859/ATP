<template>
  <div class="page-shell change-risk-radar-dashboard">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <RadarChartOutlined class="hero-icon" />
          <h2 class="page-title">代码变更三维风险雷达大盘与准入指导</h2>
        </div>
        <p class="page-subtitle">
          综合量化代码变更规模体量 (30%)、AST 圈复杂度分支增量 (35%) 与核心涉敏资产命中度 (35%)，精准评定代码变更风险指数 (0-100) 并输出准入决策。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button :loading="loading" size="small" @click="loadData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('low')">示例: 低风险微型修改</a-button>
          <a-button size="small" @click="applyPreset('critical')">示例: 核心高危重构</a-button>
          <a-button type="primary" size="small" @click="showCustomModal = true">
            <SlidersOutlined /> 自定义 Diff 评估
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <template v-if="currentReport">
        <!-- 综合风险与准入指示大横幅 -->
        <div class="verdict-banner" :class="`banner-level-${currentReport.risk_level.toLowerCase()}`">
          <div class="score-circle-box">
            <div class="score-circle">
              <span class="score-num">{{ currentReport.overall_risk_score.toFixed(1) }}</span>
              <span class="score-lbl">综合风险分</span>
            </div>
          </div>

          <div class="verdict-content">
            <div class="verdict-level-row">
              <a-tag :color="getLevelColor(currentReport.risk_level)" class="level-tag font-bold">
                {{ currentReport.risk_level }} 风险等级
              </a-tag>
              <span class="risk-id-text mono">ID: {{ currentReport.risk_id }}</span>
            </div>
            <div class="action-recommendation">
              <strong>准入动作指示:</strong> {{ currentReport.recommended_action }}
            </div>
            <div class="verdict-meta">
              <span>评估时间: {{ formatTime(currentReport.evaluated_at) }}</span>
              <span>高危文件: <strong>{{ currentReport.high_risk_files?.length || 0 }}</strong> 处</span>
            </div>
          </div>
        </div>

        <!-- 三维风险拆解指标卡片网格 -->
        <div class="dimensions-grid">
          <!-- 1. 规模分 -->
          <div class="dim-card">
            <div class="dim-head">
              <span class="dim-title font-bold">变更代码规模 (Volume)</span>
              <span class="dim-weight">权重 30%</span>
            </div>
            <div class="dim-score-row">
              <span class="dim-score" :class="getScoreClass(currentReport.dimensions?.volume?.score)">
                {{ currentReport.dimensions?.volume?.score ?? 0 }}
              </span>
              <span class="dim-unit">/ 100</span>
            </div>
            <div class="dim-meta">
              新增: +{{ currentReport.dimensions?.volume?.raw_metrics?.total_added_lines || 0 }} |
              删除: -{{ currentReport.dimensions?.volume?.raw_metrics?.total_deleted_lines || 0 }} |
              文件: {{ currentReport.dimensions?.volume?.raw_metrics?.changed_files_count || 0 }}
            </div>
            <div class="dim-desc">{{ currentReport.dimensions?.volume?.description }}</div>
          </div>

          <!-- 2. 复杂度分 -->
          <div class="dim-card">
            <div class="dim-head">
              <span class="dim-title font-bold">圈复杂度增量 (Complexity)</span>
              <span class="dim-weight">权重 35%</span>
            </div>
            <div class="dim-score-row">
              <span class="dim-score" :class="getScoreClass(currentReport.dimensions?.complexity?.score)">
                {{ currentReport.dimensions?.complexity?.score ?? 0 }}
              </span>
              <span class="dim-unit">/ 100</span>
            </div>
            <div class="dim-meta">
              控制流分支/异常节点增量: +{{ currentReport.dimensions?.complexity?.raw_metrics?.complexity_delta_count || 0 }}
            </div>
            <div class="dim-desc">{{ currentReport.dimensions?.complexity?.description }}</div>
          </div>

          <!-- 3. 核心涉敏度分 -->
          <div class="dim-card">
            <div class="dim-head">
              <span class="dim-title font-bold">核心资产涉敏度 (Criticality)</span>
              <span class="dim-weight">权重 35%</span>
            </div>
            <div class="dim-score-row">
              <span class="dim-score" :class="getScoreClass(currentReport.dimensions?.criticality?.score)">
                {{ currentReport.dimensions?.criticality?.score ?? 0 }}
              </span>
              <span class="dim-unit">/ 100</span>
            </div>
            <div class="dim-meta">
              涉密核心模块命中数: {{ currentReport.dimensions?.criticality?.raw_metrics?.high_risk_files_count || 0 }} 处
            </div>
            <div class="dim-desc">{{ currentReport.dimensions?.criticality?.description }}</div>
          </div>
        </div>

        <!-- 雷达图与归因双栏 -->
        <div class="radar-insights-grid">
          <!-- 左侧：三维雷达图 -->
          <a-card title="代码变更三维风险雷达 (Risk Radar)" size="small" class="radar-card" :bordered="false">
            <v-chart class="risk-radar-chart" :option="radarChartOption" :theme="chartTheme" autoresize />
            <div class="radar-legend">
              <span class="leg-item"><span class="dot actual-dot" /> 本次变更实测风险分</span>
              <span class="leg-item"><span class="dot baseline-dot" /> 安全基准线 (≤25分)</span>
            </div>
          </a-card>

          <!-- 右侧：风险因子与高危文件清单 -->
          <div class="insights-col">
            <a-card title="风险驱动因子摘要 (Risk Factors)" size="small" class="sub-card">
              <div class="factors-list">
                <div v-for="(factor, idx) in currentReport.risk_factors_summary || []" :key="idx" class="factor-item">
                  <span class="factor-dot" />
                  <span>{{ factor }}</span>
                </div>
              </div>
            </a-card>

            <a-card title="涉及的高危敏感文件 (High Risk Files)" size="small" class="sub-card" style="margin-top: 12px">
              <div v-if="currentReport.high_risk_files?.length" class="files-list">
                <div v-for="f in currentReport.high_risk_files" :key="f" class="file-item">
                  <AlertOutlined class="file-warn-icon" />
                  <span class="file-path mono font-bold">{{ f }}</span>
                </div>
              </div>
              <div v-else class="empty-files-box">
                <CheckCircleOutlined class="text-success" />
                <span>本次变更未触及任何高危涉敏业务模块</span>
              </div>
            </a-card>
          </div>
        </div>
      </template>

      <a-empty v-else description="暂无代码风险评估数据，请点击「刷新」或「自定义 Diff 评估」" />
    </a-spin>

    <!-- 自定义 Diff 评估 Modal -->
    <a-modal
      v-model:open="showCustomModal"
      title="输入 Git Diff 文本评估代码变更风险"
      :width="720"
      @ok="handleEvaluateCustom"
    >
      <a-form layout="vertical">
        <a-form-item label="Git Unified Diff 补丁文本" required>
          <a-textarea
            v-model:value="customDiffText"
            :rows="8"
            placeholder="diff --git a/... b/..."
            style="font-family: monospace; font-size: 11px"
          />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item label="代码体量权重">
              <a-input-number v-model:value="weightVolume" :min="0" :max="1" :step="0.05" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="圈复杂度权重">
              <a-input-number v-model:value="weightComplexity" :min="0" :max="1" :step="0.05" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="核心敏感度权重">
              <a-input-number v-model:value="weightCriticality" :min="0" :max="1" :step="0.05" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { message } from 'ant-design-vue'
import {
  RadarChartOutlined,
  ReloadOutlined,
  SlidersOutlined,
  AlertOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  ciImpactApi,
  type ChangeRiskReportItem,
  type RiskLevel,
} from '@/api/ciImpact'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme } = useChartTheme()

const loading = ref(false)
const showCustomModal = ref(false)
const currentReport = ref<ChangeRiskReportItem | null>(null)

const weightVolume = ref(0.30)
const weightComplexity = ref(0.35)
const weightCriticality = ref(0.35)

const SAMPLE_LOW_DIFF = `diff --git a/app/utils/format.py b/app/utils/format.py
--- a/app/utils/format.py
+++ b/app/utils/format.py
@@ -5,2 +5,2 @@ def format_name(first: str, last: str) -> str:
-    return first + " " + last
+    return f"{first} {last}".strip()
`

const SAMPLE_CRITICAL_DIFF = `diff --git a/backend/app/core/auth_security.py b/backend/app/core/auth_security.py
--- a/backend/app/core/auth_security.py
+++ b/backend/app/core/auth_security.py
@@ -5,4 +5,12 @@ def verify_payment_token(token: str, secret: str) -> bool:
+    if not token or not secret:
+        raise ValueError("Missing credentials")
+    for attempt in range(3):
+        try:
+            if len(token) > 10 and secret.startswith("sec_"):
+                return True
+        except Exception:
+            pass
     return False
`

const customDiffText = ref(SAMPLE_LOW_DIFF)

function getLevelColor(level: RiskLevel): string {
  switch (level) {
    case 'CRITICAL':
      return 'error'
    case 'HIGH':
      return 'warning'
    case 'MEDIUM':
      return 'processing'
    case 'LOW':
      return 'success'
    default:
      return 'default'
  }
}

function getScoreClass(score?: number): string {
  if (score === undefined) return ''
  if (score >= 75) return 'text-danger'
  if (score >= 50) return 'text-warning'
  return 'text-success'
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return isoStr
  }
}

const radarChartOption = computed(() => {
  if (!currentReport.value) return {}
  const dims = currentReport.value.dimensions

  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: '代码变更规模 (Volume)', max: 100 },
        { name: '圈复杂度增量 (Complexity)', max: 100 },
        { name: '核心资产涉敏度 (Criticality)', max: 100 },
      ],
      shape: 'polygon',
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(241, 245, 249, 0.6)', 'rgba(248, 250, 252, 0.3)'],
        },
      },
    },
    series: [
      {
        name: '代码变更三维风险得分',
        type: 'radar',
        data: [
          {
            value: [
              dims?.volume?.score || 0,
              dims?.complexity?.score || 0,
              dims?.criticality?.score || 0,
            ],
            name: '本次变更实测风险分',
            itemStyle: { color: currentReport.value.overall_risk_score >= 50 ? '#ef4444' : '#6366f1' },
            areaStyle: { opacity: 0.3 },
          },
          {
            value: [25, 25, 25],
            name: '安全基准线 (≤25分)',
            itemStyle: { color: '#10b981' },
            lineStyle: { type: 'dashed' },
          },
        ],
      },
    ],
  }
})

async function loadData() {
  loading.value = true
  try {
    const res = await ciImpactApi.listRiskReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    } else {
      await runEvaluate(SAMPLE_LOW_DIFF)
    }
  } catch (err: any) {
    message.error(`加载风险大盘失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function runEvaluate(diff: string) {
  loading.value = true
  try {
    const res = await ciImpactApi.evaluateRisk({
      diff_text: diff,
      weight_volume: weightVolume.value,
      weight_complexity: weightComplexity.value,
      weight_criticality: weightCriticality.value,
    })
    currentReport.value = res.report
    message.success(res.message || '代码变更风险评估完成')
  } catch (err: any) {
    message.error(`风险评估失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

function applyPreset(type: 'low' | 'critical') {
  if (type === 'low') {
    customDiffText.value = SAMPLE_LOW_DIFF
  } else {
    customDiffText.value = SAMPLE_CRITICAL_DIFF
  }
  runEvaluate(customDiffText.value)
}

function handleEvaluateCustom() {
  showCustomModal.value = false
  runEvaluate(customDiffText.value)
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.change-risk-radar-dashboard {
  min-width: 0;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 16px 20px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 22px;
  color: #ef4444;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.5;
  max-width: 820px;
}

/* 准入指示横幅 */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 18px 24px;
  border-radius: 8px;
  margin-bottom: 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.banner-level-low {
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border-color: #a7f3d0;
}

.banner-level-medium {
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
  border-color: #bfdbfe;
}

.banner-level-high {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fde68a;
}

.banner-level-critical {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fecaca;
}

.score-circle-box {
  flex-shrink: 0;
}

.score-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.score-num {
  font-size: 28px;
  font-weight: 900;
  color: #0f172a;
  line-height: 1;
}

.score-lbl {
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
}

.verdict-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.verdict-level-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.level-tag {
  font-size: 12px;
}

.risk-id-text {
  font-size: 11px;
  color: #64748b;
}

.action-recommendation {
  font-size: 13px;
  color: #1e293b;
  line-height: 1.5;
}

.verdict-meta {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: #64748b;
}

/* 三维卡片 */
.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.dim-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
}

.dim-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.dim-title {
  font-size: 13px;
  color: #0f172a;
}

.dim-weight {
  font-size: 11px;
  color: #94a3b8;
}

.dim-score-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 4px;
}

.dim-score {
  font-size: 26px;
  font-weight: 800;
  line-height: 1.1;
}

.dim-unit {
  font-size: 12px;
  color: #94a3b8;
}

.dim-meta {
  font-size: 11px;
  color: #475569;
  background: #f8fafc;
  padding: 3px 6px;
  border-radius: 4px;
  margin-bottom: 6px;
}

.dim-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

/* 雷达与因子双栏 */
.radar-insights-grid {
  display: grid;
  grid-template-columns: 460px 1fr;
  gap: 16px;
}

.radar-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.risk-radar-chart {
  height: 320px;
  width: 100%;
}

.radar-legend {
  display: flex;
  justify-content: center;
  gap: 16px;
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
}

.leg-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.actual-dot {
  background: #ef4444;
}

.baseline-dot {
  background: #10b981;
}

.insights-col {
  display: flex;
  flex-direction: column;
}

.sub-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.factors-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.factor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #334155;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 4px;
}

.factor-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ef4444;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  padding: 6px 10px;
  background: #fff5f5;
  border: 1px solid #fed7d7;
  border-radius: 4px;
}

.file-warn-icon {
  color: #ef4444;
}

.empty-files-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  font-size: 12px;
  color: #065f46;
  background: #ecfdf5;
  border-radius: 4px;
}

.font-bold {
  font-weight: 700;
}

.mono {
  font-family: monospace;
}

.text-success {
  color: #10b981 !important;
}

.text-warning {
  color: #f59e0b !important;
}

.text-danger {
  color: #ef4444 !important;
}
</style>
