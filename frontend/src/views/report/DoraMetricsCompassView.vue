<template>
  <div class="page-shell dora-metrics-compass-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <CompassOutlined class="hero-icon" />
          <h2 class="page-title">团队研发效能 DORA 罗盘看板与成熟度评估</h2>
        </div>
        <p class="page-subtitle">
          严格对齐 Google DORA (DevOps Research and Assessment) 标准模型，量化部署频率、变更前置时长、变更失败率与恢复时限 (MTTR) 四维核心效能，评定团队工程成熟度。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button :loading="loading" size="small" @click="loadData">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-button size="small" @click="applyPreset('elite')">
            示例: 卓越团队 (Elite)
          </a-button>
          <a-button size="small" @click="applyPreset('medium')">
            示例: 待优化团队 (Medium)
          </a-button>
          <a-button type="primary" size="small" @click="showSimulator = true">
            <SlidersOutlined /> 效能推演模拟器
          </a-button>
        </a-space>
      </div>
    </header>

    <a-spin :spinning="loading">
      <template v-if="currentReport">
        <!-- 成熟度与准时率 Hero 大卡片 -->
        <div class="maturity-banner" :class="`banner-level-${currentReport.overall_maturity_level}`">
          <div class="maturity-badge-box">
            <div class="maturity-level-title">{{ currentReport.overall_maturity_level.toUpperCase() }}</div>
            <div class="maturity-level-desc">团队综合工程效能成熟度</div>
          </div>

          <div class="maturity-divider" />

          <div class="on-time-kpi-box">
            <div class="kpi-num-row">
              <span class="kpi-num">{{ currentReport.test_on_time_completion_rate_pct }}%</span>
            </div>
            <div class="kpi-lbl">测试执行准时交付率 (On-Time Completion)</div>
          </div>

          <div class="maturity-divider" />

          <div class="meta-box">
            <div class="meta-item">
              <span class="meta-k">评估周期:</span>
              <span class="meta-v">近 {{ currentReport.evaluation_period_days }} 天</span>
            </div>
            <div class="meta-item">
              <span class="meta-k">报告 ID:</span>
              <span class="meta-v font-mono">{{ currentReport.report_id }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-k">更新时间:</span>
              <span class="meta-v">{{ formatTime(currentReport.evaluated_at) }}</span>
            </div>
          </div>
        </div>

        <!-- DORA 四维效能核心 KPI 卡片网格 -->
        <div class="dora-kpi-grid">
          <!-- 1. 部署频率 -->
          <div
            v-if="currentReport.dimensions?.deployment_frequency"
            class="dora-card"
            :class="`dora-card-${currentReport.dimensions.deployment_frequency.level}`"
          >
            <div class="dora-card-head">
              <span class="dimension-name">部署频率 (Deployment Frequency)</span>
              <a-tag :color="getLevelColor(currentReport.dimensions.deployment_frequency.level)">
                {{ currentReport.dimensions.deployment_frequency.level.toUpperCase() }}
              </a-tag>
            </div>
            <div class="dora-val-row">
              <span class="dora-val">{{ currentReport.dimensions.deployment_frequency.value }}</span>
              <span class="dora-unit">{{ currentReport.dimensions.deployment_frequency.unit }}</span>
            </div>
            <div class="dora-guideline">{{ currentReport.dimensions.deployment_frequency.benchmark_guideline }}</div>
            <div class="dora-desc">{{ currentReport.dimensions.deployment_frequency.description }}</div>
          </div>

          <!-- 2. 变更前置时长 -->
          <div
            v-if="currentReport.dimensions?.lead_time_for_changes"
            class="dora-card"
            :class="`dora-card-${currentReport.dimensions.lead_time_for_changes.level}`"
          >
            <div class="dora-card-head">
              <span class="dimension-name">变更前置时间 (Lead Time for Changes)</span>
              <a-tag :color="getLevelColor(currentReport.dimensions.lead_time_for_changes.level)">
                {{ currentReport.dimensions.lead_time_for_changes.level.toUpperCase() }}
              </a-tag>
            </div>
            <div class="dora-val-row">
              <span class="dora-val">{{ currentReport.dimensions.lead_time_for_changes.value }}</span>
              <span class="dora-unit">{{ currentReport.dimensions.lead_time_for_changes.unit }}</span>
            </div>
            <div class="dora-guideline">{{ currentReport.dimensions.lead_time_for_changes.benchmark_guideline }}</div>
            <div class="dora-desc">{{ currentReport.dimensions.lead_time_for_changes.description }}</div>
          </div>

          <!-- 3. 变更失败率 -->
          <div
            v-if="currentReport.dimensions?.change_failure_rate"
            class="dora-card"
            :class="`dora-card-${currentReport.dimensions.change_failure_rate.level}`"
          >
            <div class="dora-card-head">
              <span class="dimension-name">变更失败率 (Change Failure Rate)</span>
              <a-tag :color="getLevelColor(currentReport.dimensions.change_failure_rate.level)">
                {{ currentReport.dimensions.change_failure_rate.level.toUpperCase() }}
              </a-tag>
            </div>
            <div class="dora-val-row">
              <span class="dora-val">{{ currentReport.dimensions.change_failure_rate.value }}</span>
              <span class="dora-unit">{{ currentReport.dimensions.change_failure_rate.unit }}</span>
            </div>
            <div class="dora-guideline">{{ currentReport.dimensions.change_failure_rate.benchmark_guideline }}</div>
            <div class="dora-desc">{{ currentReport.dimensions.change_failure_rate.description }}</div>
          </div>

          <!-- 4. 故障恢复时长 -->
          <div
            v-if="currentReport.dimensions?.time_to_restore_service"
            class="dora-card"
            :class="`dora-card-${currentReport.dimensions.time_to_restore_service.level}`"
          >
            <div class="dora-card-head">
              <span class="dimension-name">服务恢复时限 (Time to Restore / MTTR)</span>
              <a-tag :color="getLevelColor(currentReport.dimensions.time_to_restore_service.level)">
                {{ currentReport.dimensions.time_to_restore_service.level.toUpperCase() }}
              </a-tag>
            </div>
            <div class="dora-val-row">
              <span class="dora-val">{{ currentReport.dimensions.time_to_restore_service.value }}</span>
              <span class="dora-unit">{{ currentReport.dimensions.time_to_restore_service.unit }}</span>
            </div>
            <div class="dora-guideline">{{ currentReport.dimensions.time_to_restore_service.benchmark_guideline }}</div>
            <div class="dora-desc">{{ currentReport.dimensions.time_to_restore_service.description }}</div>
          </div>
        </div>

        <!-- 罗盘雷达图与瓶颈建议双栏 -->
        <div class="radar-bottleneck-grid">
          <!-- 左侧：四维 DORA 罗盘雷达图 -->
          <a-card title="团队研发与交付效能 DORA 罗盘图 (Radar Compass)" size="small" class="radar-card" :bordered="false">
            <v-chart class="dora-radar-chart" :option="doraRadarOption" :theme="chartTheme" autoresize />
            <div class="radar-legend-row">
              <span class="legend-item"><span class="dot actual-dot" /> 团队当前效能折算分</span>
              <span class="legend-item"><span class="dot benchmark-dot" /> 卓越研发组织 Benchmark (100分)</span>
            </div>
          </a-card>

          <!-- 右侧：瓶颈识别与效能提升建议 -->
          <div class="insights-col">
            <!-- 检出的效能瓶颈 -->
            <a-card title="识别到的交付与测试瓶颈 (Bottlenecks)" size="small" class="sub-insight-card">
              <div v-if="currentReport.bottlenecks_identified?.length" class="bottlenecks-list">
                <div v-for="(b, idx) in currentReport.bottlenecks_identified" :key="idx" class="bottleneck-item">
                  <AlertFilled class="bottleneck-icon" />
                  <span>{{ b }}</span>
                </div>
              </div>
              <div v-else class="text-success-box">
                <CheckCircleFilled class="success-icon" />
                <span>各项工程效能指标均衡达标，未检出显著发布或恢复瓶颈。</span>
              </div>
            </a-card>

            <!-- 效能提升治理建议 -->
            <a-card title="工程效能提升与治理推进建议 (Recommendations)" size="small" class="sub-insight-card" style="margin-top: 12px">
              <div class="recs-list">
                <div
                  v-for="(rec, idx) in currentReport.engineering_efficiency_recommendations || []"
                  :key="idx"
                  class="rec-item"
                >
                  <span class="rec-idx">{{ idx + 1 }}</span>
                  <span class="rec-text">{{ rec }}</span>
                </div>
              </div>
            </a-card>
          </div>
        </div>
      </template>

      <a-empty v-else description="暂无 DORA 研发效能度量报告，请点击「刷新」或「效能推演模拟器」进行评估" />
    </a-spin>

    <!-- 效能推演模拟器 Modal -->
    <a-modal
      v-model:open="showSimulator"
      title="DORA 团队研发与测试效能指标推演模拟器"
      @ok="handleRunEvaluate"
    >
      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="评估周期天数 (天)" required>
              <a-input-number v-model:value="simForm.evaluation_period_days" :min="1" :max="365" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="周期内发布部署总次数" required>
              <a-input-number v-model:value="simForm.total_deployments_count" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="代码变更前置耗时 (小时)" required>
              <a-input-number v-model:value="simForm.lead_time_for_changes_hours" :min="0" :step="0.5" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="变更失败与回滚率 (%)" required>
              <a-input-number v-model:value="simForm.change_failure_rate_pct" :min="0" :max="100" :step="0.5" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="故障恢复平均用时 MTTR (分钟)" required>
              <a-input-number v-model:value="simForm.time_to_restore_service_minutes" :min="0" :step="5" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="测试执行准时完成轮次 / 总轮次">
              <a-space>
                <a-input-number v-model:value="simForm.test_runs_on_time_count" :min="0" style="width: 80px" />
                <span>/</span>
                <a-input-number v-model:value="simForm.test_runs_total_count" :min="1" style="width: 80px" />
              </a-space>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import VChart from 'vue-echarts'
import { message } from 'ant-design-vue'
import {
  CompassOutlined,
  ReloadOutlined,
  SlidersOutlined,
  AlertFilled,
  CheckCircleFilled,
} from '@ant-design/icons-vue'
import {
  doraMetricsApi,
  type DoraPerformanceReportItem,
  type DoraLevel,
} from '@/api/doraMetrics'
import { useChartTheme } from '@/utils/chartTheme'

const { chartTheme } = useChartTheme()

const loading = ref(false)
const currentReport = ref<DoraPerformanceReportItem | null>(null)
const showSimulator = ref(false)

const simForm = reactive({
  evaluation_period_days: 30,
  total_deployments_count: 45,
  lead_time_for_changes_hours: 0.8,
  change_failure_rate_pct: 4.2,
  time_to_restore_service_minutes: 35.0,
  test_runs_on_time_count: 95,
  test_runs_total_count: 100,
})

function getLevelColor(level: DoraLevel): string {
  switch (level) {
    case 'elite':
      return 'success'
    case 'high':
      return 'processing'
    case 'medium':
      return 'warning'
    case 'low':
      return 'error'
    default:
      return 'default'
  }
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

function applyPreset(type: 'elite' | 'medium') {
  if (type === 'elite') {
    simForm.evaluation_period_days = 30
    simForm.total_deployments_count = 60 // 每天 2 次
    simForm.lead_time_for_changes_hours = 0.5 // 30 分钟
    simForm.change_failure_rate_pct = 2.5
    simForm.time_to_restore_service_minutes = 20.0
    simForm.test_runs_on_time_count = 98
    simForm.test_runs_total_count = 100
  } else {
    simForm.evaluation_period_days = 30
    simForm.total_deployments_count = 2 // 每月 2 次
    simForm.lead_time_for_changes_hours = 48.0 // 2 天
    simForm.change_failure_rate_pct = 18.0
    simForm.time_to_restore_service_minutes = 180.0
    simForm.test_runs_on_time_count = 75
    simForm.test_runs_total_count = 100
  }
  handleRunEvaluate()
}

// 四维雷达图配置
const doraRadarOption = computed(() => {
  if (!currentReport.value) return {}
  const dims = currentReport.value.dimensions

  // 将四维水平折算为 0 - 100 分
  const scoreFromLevel = (lvl?: DoraLevel) => {
    switch (lvl) {
      case 'elite':
        return 100
      case 'high':
        return 80
      case 'medium':
        return 55
      case 'low':
        return 30
      default:
        return 50
    }
  }

  const depScore = scoreFromLevel(dims?.deployment_frequency?.level)
  const leadScore = scoreFromLevel(dims?.lead_time_for_changes?.level)
  const failScore = scoreFromLevel(dims?.change_failure_rate?.level)
  const mttrScore = scoreFromLevel(dims?.time_to_restore_service?.level)

  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: '部署频率 (DF)', max: 100 },
        { name: '变更前置时效 (LT)', max: 100 },
        { name: '发布变更质量 (1-CFR)', max: 100 },
        { name: '故障恢复韧性 (MTTR)', max: 100 },
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
        name: 'DORA 研发效能四维评分',
        type: 'radar',
        data: [
          {
            value: [depScore, leadScore, failScore, mttrScore],
            name: '团队当前效能折算分',
            itemStyle: { color: '#8b5cf6' },
            areaStyle: { color: 'rgba(139, 92, 246, 0.35)' },
          },
          {
            value: [100, 100, 100, 100],
            name: '卓越研发组织 Benchmark',
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
    const res = await doraMetricsApi.listReports()
    if (res.reports && res.reports.length > 0) {
      currentReport.value = res.reports[0]
    } else {
      await handleRunEvaluate()
    }
  } catch (err: any) {
    message.error(`加载 DORA 效能数据失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

async function handleRunEvaluate() {
  loading.value = true
  try {
    const res = await doraMetricsApi.evaluate(simForm)
    message.success(res.message || 'DORA 效能评估计算完成')
    currentReport.value = res.report
    showSimulator.value = false
  } catch (err: any) {
    message.error(`DORA 评估失败: ${err.message || err}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dora-metrics-compass-view {
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
  color: #8b5cf6;
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

/* 成熟度大 Banner */
.maturity-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-radius: 8px;
  margin-bottom: 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.banner-level-elite {
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border-color: #a7f3d0;
}

.banner-level-high {
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
  border-color: #bfdbfe;
}

.banner-level-medium {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-color: #fde68a;
}

.banner-level-low {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-color: #fecaca;
}

.maturity-badge-box {
  display: flex;
  flex-direction: column;
}

.maturity-level-title {
  font-size: 32px;
  font-weight: 900;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1;
}

.maturity-level-desc {
  font-size: 12px;
  color: #64748b;
  margin-top: 6px;
}

.maturity-divider {
  width: 1px;
  height: 48px;
  background: rgba(0, 0, 0, 0.08);
}

.on-time-kpi-box {
  display: flex;
  flex-direction: column;
}

.kpi-num-row {
  display: flex;
  align-items: baseline;
}

.kpi-num {
  font-size: 28px;
  font-weight: 800;
  color: #059669;
  line-height: 1;
}

.kpi-lbl {
  font-size: 12px;
  color: #64748b;
  margin-top: 6px;
}

.meta-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.meta-item {
  display: flex;
  gap: 8px;
}

.meta-k {
  color: #64748b;
}

.meta-v {
  color: #0f172a;
}

.font-mono {
  font-family: monospace;
}

/* DORA 四维 KPI 卡片网格 */
.dora-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.dora-card {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  transition: all 0.2s ease;
}

.dora-card-elite {
  border-left: 4px solid #10b981;
}

.dora-card-high {
  border-left: 4px solid #3b82f6;
}

.dora-card-medium {
  border-left: 4px solid #f59e0b;
}

.dora-card-low {
  border-left: 4px solid #ef4444;
}

.dora-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.dimension-name {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.dora-val-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 6px;
}

.dora-val {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}

.dora-unit {
  font-size: 12px;
  color: #64748b;
}

.dora-guideline {
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  background: #f8fafc;
  padding: 4px 6px;
  border-radius: 4px;
  margin-bottom: 6px;
}

.dora-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

/* 罗盘与建议双栏 */
.radar-bottleneck-grid {
  display: grid;
  grid-template-columns: 460px 1fr;
  gap: 16px;
}

.radar-card {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.dora-radar-chart {
  height: 320px;
  width: 100%;
}

.radar-legend-row {
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
  background: #8b5cf6;
}

.benchmark-dot {
  background: #10b981;
}

.insights-col {
  display: flex;
  flex-direction: column;
}

.sub-insight-card {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
}

.bottlenecks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bottleneck-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fef2f2;
  border-radius: 6px;
  font-size: 12px;
  color: #991b1b;
}

.bottleneck-icon {
  color: #ef4444;
}

.text-success-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #ecfdf5;
  border-radius: 6px;
  font-size: 12px;
  color: #065f46;
}

.success-icon {
  color: #10b981;
}

.recs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rec-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  border-left: 3px solid #8b5cf6;
}

.rec-idx {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #8b5cf6;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.rec-text {
  font-size: 12px;
  color: #334155;
  line-height: 1.5;
}
</style>
