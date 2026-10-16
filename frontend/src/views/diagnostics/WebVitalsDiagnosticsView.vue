<template>
  <div class="page-shell web-vitals-diagnostics-view">
    <!-- 头部工具栏与 URL 输入区 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <GlobalOutlined class="hero-icon" />
          <h2 class="page-title">Web 性能 Core Web Vitals 自动化深度诊断中心</h2>
        </div>
        <p class="page-subtitle">
          严格对齐 Google 官方三维核心指标（LCP、INP、CLS）与辅助体验指标（FCP、TTFB、TBT），基于 Lighthouse 权重模型自动计算性能综合分并排查渲染阻断资源。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button :loading="loading" size="small" @click="loadReports">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="fillPreset('login')">
            示例: 登录页
          </a-button>
          <a-button size="small" @click="fillPreset('dashboard')">
            示例: 数据看板
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 诊断表单输入卡片 -->
    <a-card size="small" class="diagnosis-form-card" :bordered="false">
      <a-form layout="inline" class="form-row">
        <a-form-item label="诊断目标 URL" class="url-input-item">
          <a-input
            v-model:value="diagForm.target_url"
            placeholder="https://example.com/app"
            style="width: 320px"
          />
        </a-form-item>
        <a-form-item label="浏览器内核">
          <a-select v-model:value="diagForm.browser_type" style="width: 120px">
            <a-select-option value="chromium">Chromium</a-select-option>
            <a-select-option value="firefox">Firefox</a-select-option>
            <a-select-option value="webkit">WebKit (Safari)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="设备模式">
          <a-select v-model:value="diagForm.device_emulation" style="width: 110px">
            <a-select-option value="desktop">桌面端 (PC)</a-select-option>
            <a-select-option value="mobile">移动端 (H5)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="diagnosing" @click="handleRunDiagnose">
            <ThunderboltOutlined /> 执行深度诊断
          </a-button>
        </a-form-item>
        <a-form-item v-if="historyReports.length > 0">
          <a-select
            v-model:value="selectedReportId"
            placeholder="查看历史诊断报告"
            style="width: 220px"
            :options="historyOptions"
            @change="handleSelectHistory"
          />
        </a-form-item>
      </a-form>
    </a-card>

    <a-spin :spinning="loading || diagnosing">
      <template v-if="currentReport">
        <!-- 综合评分与评级 Hero 卡片 -->
        <div class="verdict-banner" :class="`rating-${currentReport.overall_rating}`">
          <div class="score-box">
            <div class="score-circle">
              <span class="score-num">{{ currentReport.overall_performance_score }}</span>
              <span class="score-label">综合得分</span>
            </div>
          </div>
          <div class="verdict-info">
            <div class="verdict-top">
              <a-tag :color="getRatingColor(currentReport.overall_rating)" class="rating-tag">
                {{ getRatingLabel(currentReport.overall_rating) }} ({{ currentReport.overall_rating.toUpperCase() }})
              </a-tag>
              <span class="url-chip">{{ currentReport.target_url }}</span>
            </div>
            <p class="verdict-desc">
              {{ getVerdictDescription(currentReport.overall_performance_score, currentReport.overall_rating) }}
            </p>
            <div class="meta-row">
              <span>内核: <code>{{ currentReport.browser_type }}</code></span>
              <span>设备: <code>{{ currentReport.device_emulation }}</code></span>
              <span>报告 ID: <code>{{ currentReport.audit_id }}</code></span>
              <span>诊断时间: {{ formatTime(currentReport.evaluated_at) }}</span>
            </div>
          </div>
        </div>

        <!-- 核心指标卡片矩阵与雷达图双栏区 -->
        <div class="metrics-radar-grid">
          <!-- 左侧：指标卡片网格 -->
          <div class="metrics-cards-container">
            <div class="section-title-row">
              <span class="section-title">Core Web Vitals 官方核心体验指标</span>
              <a-tag color="blue">三大核心</a-tag>
            </div>
            <div class="vitals-grid">
              <div
                v-for="(metric, key) in currentReport.core_vitals"
                :key="key"
                class="vital-card"
                :class="`card-${metric.rating}`"
              >
                <div class="vital-header">
                  <span class="vital-key">{{ key }}</span>
                  <a-tag :color="getRatingColor(metric.rating)">
                    {{ getRatingLabel(metric.rating) }}
                  </a-tag>
                </div>
                <div class="vital-name">{{ metric.name }}</div>
                <div class="vital-value-row">
                  <span class="vital-value">{{ metric.value }}</span>
                  <span class="vital-unit">{{ metric.unit }}</span>
                </div>
                <div class="threshold-bar">
                  <span class="th-tip">良好阈值: &le; {{ metric.good_threshold }} {{ metric.unit }}</span>
                </div>
                <div class="vital-desc">{{ metric.description }}</div>
              </div>
            </div>

            <div class="section-title-row" style="margin-top: 16px">
              <span class="section-title">Supplementary Vitals 辅助关键性能指标</span>
              <a-tag color="purple">加载与阻塞度量</a-tag>
            </div>
            <div class="vitals-grid">
              <div
                v-for="(metric, key) in currentReport.supplementary_vitals"
                :key="key"
                class="vital-card"
                :class="`card-${metric.rating}`"
              >
                <div class="vital-header">
                  <span class="vital-key">{{ key }}</span>
                  <a-tag :color="getRatingColor(metric.rating)">
                    {{ getRatingLabel(metric.rating) }}
                  </a-tag>
                </div>
                <div class="vital-name">{{ metric.name }}</div>
                <div class="vital-value-row">
                  <span class="vital-value">{{ metric.value }}</span>
                  <span class="vital-unit">{{ metric.unit }}</span>
                </div>
                <div class="threshold-bar">
                  <span class="th-tip">良好阈值: &le; {{ metric.good_threshold }} {{ metric.unit }}</span>
                </div>
                <div class="vital-desc">{{ metric.description }}</div>
              </div>
            </div>
          </div>

          <!-- 右侧：六维 Web Vitals 全景雷达图 -->
          <div class="radar-container">
            <a-card title="六维 Web Vitals 体验综合雷达图" size="small" class="radar-card" :bordered="false">
              <v-chart class="vitals-radar-chart" :option="radarChartOption" :theme="chartTheme" autoresize />
              <div class="radar-legend-note">
                <span class="legend-item"><span class="dot actual-dot" /> 当前页面实测折算分</span>
                <span class="legend-item"><span class="dot benchmark-dot" /> 卓越基准线 (100分)</span>
              </div>
            </a-card>
          </div>
        </div>

        <!-- 关键渲染阻断资源与优化建议区 -->
        <div class="bottom-analysis-grid">
          <!-- 关键渲染阻断资源表格 -->
          <a-card title="关键渲染阻塞资源清单 (Render-Blocking Resources)" size="small" class="analysis-card">
            <template #extra>
              <a-tag color="warning">{{ currentReport.blocking_resources?.length || 0 }} 个阻断资源</a-tag>
            </template>
            <a-table
              :data-source="currentReport.blocking_resources || []"
              :columns="resourceColumns"
              row-key="url"
              size="small"
              :pagination="{ pageSize: 5, showTotal: (t: number) => `共 ${t} 个资源` }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'url'">
                  <div class="resource-url-box">
                    <span class="resource-url" :title="record.url">{{ record.url }}</span>
                  </div>
                </template>
                <template v-else-if="column.key === 'resource_type'">
                  <a-tag :color="getResourceTypeColor(record.resource_type)">
                    {{ record.resource_type }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'duration_ms'">
                  <span class="mono-text">{{ record.duration_ms }} ms</span>
                </template>
                <template v-else-if="column.key === 'transfer_size_kb'">
                  <span class="mono-text">{{ record.transfer_size_kb }} KB</span>
                </template>
                <template v-else-if="column.key === 'impact'">
                  <a-tag :color="record.impact === 'high' ? 'error' : (record.impact === 'medium' ? 'warning' : 'default')">
                    {{ record.impact.toUpperCase() }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'suggestion'">
                  <span class="suggestion-text">{{ record.suggestion }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- AI 智能优化建议清单 -->
          <a-card title="Google Lighthouse 智能性能优化推进建议" size="small" class="analysis-card">
            <div class="recommendations-list">
              <div
                v-for="(rec, idx) in currentReport.optimization_recommendations || []"
                :key="idx"
                class="rec-item"
              >
                <span class="rec-badge">{{ idx + 1 }}</span>
                <span class="rec-text">{{ rec }}</span>
              </div>
            </div>
          </a-card>
        </div>
      </template>

      <a-empty v-else description="暂无诊断报告，请在上方输入 Web 页面 URL 并点击「执行深度诊断」" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import VChart from 'vue-echarts'
import { message } from 'ant-design-vue'
import {
  GlobalOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  webVitalsApi,
  type WebVitalsAuditReport,
  type VitalRating,
} from '@/api/webVitals'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme } = useChartTheme()

const loading = ref(false)
const diagnosing = ref(false)
const historyReports = ref<WebVitalsAuditReport[]>([])
const selectedReportId = ref<string | undefined>(undefined)
const currentReport = ref<WebVitalsAuditReport | null>(null)

const diagForm = reactive({
  target_url: 'https://app.atp.io/dashboard',
  browser_type: 'chromium',
  device_emulation: 'desktop',
  lcp_ms: 2200.0,
  inp_ms: 120.0,
  cls_score: 0.05,
  fcp_ms: 1400.0,
  ttfb_ms: 350.0,
  tbt_ms: 150.0,
})

const historyOptions = computed(() =>
  historyReports.value.map((r) => ({
    label: `${r.target_url} (${r.overall_performance_score}分 · ${r.overall_rating})`,
    value: r.audit_id,
  }))
)

const resourceColumns = [
  { title: '资源 URL', key: 'url', width: 260 },
  { title: '类型', key: 'resource_type', width: 90 },
  { title: '耗时', key: 'duration_ms', width: 90 },
  { title: '传输大小', key: 'transfer_size_kb', width: 100 },
  { title: '阻断影响', key: 'impact', width: 90 },
  { title: '优化策略建议', key: 'suggestion' },
]

function getRatingLabel(rating: VitalRating): string {
  switch (rating) {
    case 'good':
      return '优秀良好'
    case 'needs_improvement':
      return '需优化改进'
    case 'poor':
      return '体验较差'
    default:
      return rating
  }
}

function getRatingColor(rating: VitalRating): string {
  switch (rating) {
    case 'good':
      return 'success'
    case 'needs_improvement':
      return 'warning'
    case 'poor':
      return 'error'
    default:
      return 'default'
  }
}

function getResourceTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case 'script':
      return 'purple'
    case 'stylesheet':
      return 'blue'
    case 'image':
      return 'green'
    case 'font':
      return 'cyan'
    default:
      return 'default'
  }
}

function getVerdictDescription(score: number, rating: VitalRating): string {
  if (score >= 90 && rating === 'good') {
    return '页面加载迅速且视觉表现极其稳定，各项 Web Vitals 均处于 Google 官方推荐的绿色健康阈值内，无需紧急重构。'
  }
  if (rating === 'needs_improvement') {
    return '页面整体具备可用性，但存在轻微的主内容绘制延迟或长任务阻塞，建议重点优化阻塞脚本与大体积静态资源。'
  }
  return '页面存在严重的渲染阻塞或大幅度视口布局意外偏移，用户交互迟滞感明显，需研发立即按优化建议整改！'
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

function fillPreset(type: 'login' | 'dashboard') {
  if (type === 'login') {
    diagForm.target_url = 'https://app.atp.io/login'
    diagForm.lcp_ms = 1800.0
    diagForm.inp_ms = 80.0
    diagForm.cls_score = 0.02
    diagForm.fcp_ms = 1100.0
    diagForm.ttfb_ms = 220.0
    diagForm.tbt_ms = 90.0
  } else {
    diagForm.target_url = 'https://app.atp.io/dashboard'
    diagForm.lcp_ms = 3200.0
    diagForm.inp_ms = 280.0
    diagForm.cls_score = 0.18
    diagForm.fcp_ms = 2200.0
    diagForm.ttfb_ms = 600.0
    diagForm.tbt_ms = 350.0
  }
}

// 六维雷达图配置
const radarChartOption = computed(() => {
  if (!currentReport.value) return {}

  const c = currentReport.value.core_vitals
  const s = currentReport.value.supplementary_vitals

  // 将各项指标转换为 0-100 健康得分折算
  const calcScore = (val: number, good: number, poor: number) => {
    if (val <= good) return 100
    if (val >= poor) return Math.max(20, 50 - ((val - poor) / poor) * 50)
    return 90 - ((val - good) / (poor - good)) * 40
  }

  const lcpScore = Math.round(calcScore(c?.LCP?.value || 2500, 2500, 4000))
  const inpScore = Math.round(calcScore(c?.INP?.value || 200, 200, 500))
  const clsScore = Math.round(calcScore(c?.CLS?.value || 0.1, 0.1, 0.25))
  const fcpScore = Math.round(calcScore(s?.FCP?.value || 1800, 1800, 3000))
  const ttfbScore = Math.round(calcScore(s?.TTFB?.value || 800, 800, 1800))
  const tbtScore = Math.round(calcScore(s?.TBT?.value || 200, 200, 600))

  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: 'LCP (主内容渲染)', max: 100 },
        { name: 'INP (交互响应)', max: 100 },
        { name: 'CLS (布局稳定性)', max: 100 },
        { name: 'FCP (首次绘制)', max: 100 },
        { name: 'TTFB (网络时延)', max: 100 },
        { name: 'TBT (总阻塞耗时)', max: 100 },
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
        name: 'Web Vitals 六维体检得分',
        type: 'radar',
        data: [
          {
            value: [lcpScore, inpScore, clsScore, fcpScore, ttfbScore, tbtScore],
            name: '当前页面实测折算分',
            itemStyle: { color: '#6366f1' },
            areaStyle: { color: 'rgba(99, 102, 241, 0.35)' },
          },
          {
            value: [100, 100, 100, 100, 100, 100],
            name: '卓越基准线 (100分)',
            itemStyle: { color: '#10b981' },
            lineStyle: { type: 'dashed' },
          },
        ],
      },
    ],
  }
})

async function loadReports() {
  loading.value = true
  try {
    const res = await webVitalsApi.listReports()
    historyReports.value = res.reports || []
    if (historyReports.value.length > 0) {
      if (!selectedReportId.value || !historyReports.value.some((r) => r.audit_id === selectedReportId.value)) {
        selectedReportId.value = historyReports.value[0].audit_id
      }
      currentReport.value = historyReports.value[0]
    } else {
      // 若历史为空，自动发起一次默认诊断
      await handleRunDiagnose()
    }
  } catch (err: any) {
    message.error(`加载 Web Vitals 诊断列表失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function handleRunDiagnose() {
  diagnosing.value = true
  try {
    const res = await webVitalsApi.diagnose(diagForm)
    message.success(res.message || 'Web Vitals 诊断已完成')
    currentReport.value = res.report
    selectedReportId.value = res.report.audit_id
    // 重新拉取历史列表
    const listRes = await webVitalsApi.listReports()
    historyReports.value = listRes.reports || []
  } catch (err: any) {
    message.error(`执行诊断失败: ${err.message || err}`)
  } finally {
    diagnosing.value = false
  }
}

async function handleSelectHistory(auditId: any) {
  if (!auditId) return
  loading.value = true
  try {
    const r = await webVitalsApi.getReport(String(auditId))
    currentReport.value = r
  } catch (err: any) {
    message.error(`拉取历史诊断报告失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.web-vitals-diagnostics-view {
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
  color: #6366f1;
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

.diagnosis-form-card {
  margin-bottom: 16px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.form-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

/* 评级横幅 */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 20px;
  border-radius: 8px;
  margin-bottom: 16px;
  transition: all 0.2s ease;
}

.rating-good {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.rating-needs_improvement {
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.rating-poor {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.score-box {
  flex-shrink: 0;
}

.score-circle {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
}

.score-num {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}

.score-label {
  font-size: 10px;
  color: #64748b;
  margin-top: 4px;
}

.verdict-info {
  flex: 1;
}

.verdict-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.rating-tag {
  font-weight: 700;
}

.url-chip {
  font-family: monospace;
  font-size: 12px;
  color: #475569;
}

.verdict-desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
}

.meta-row {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: #64748b;
}

.meta-row code {
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 4px;
  border-radius: 4px;
}

/* 指标卡片网格与雷达图 */
.metrics-radar-grid {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 16px;
  margin-bottom: 16px;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #1e293b);
}

.vitals-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.vital-card {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.card-good {
  border-left: 4px solid #10b981;
}

.card-needs_improvement {
  border-left: 4px solid #f59e0b;
}

.card-poor {
  border-left: 4px solid #ef4444;
}

.vital-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.vital-key {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.vital-name {
  font-size: 11px;
  color: #64748b;
  margin: 4px 0 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vital-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 6px;
}

.vital-value {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}

.vital-unit {
  font-size: 12px;
  color: #94a3b8;
}

.threshold-bar {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}

.vital-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

.radar-card {
  height: 100%;
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.vitals-radar-chart {
  height: 310px;
  width: 100%;
}

.radar-legend-note {
  display: flex;
  justify-content: center;
  gap: 16px;
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
}

.legend-item {
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
  background: #6366f1;
}

.benchmark-dot {
  background: #10b981;
}

/* 底部阻断资源与建议 */
.bottom-analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.analysis-card {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.resource-url-box {
  max-width: 240px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.resource-url {
  font-family: monospace;
  font-size: 11px;
  color: #3b82f6;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.suggestion-text {
  font-size: 11px;
  color: #334155;
}

.recommendations-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rec-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 6px;
  border-left: 3px solid #6366f1;
}

.rec-badge {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #6366f1;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.rec-text {
  font-size: 12px;
  color: #334155;
  line-height: 1.5;
}
</style>
