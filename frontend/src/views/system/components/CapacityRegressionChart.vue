<template>
  <div class="capacity-regression-chart">
    <!-- 顶部控制与 SLA 条件栏 -->
    <div class="control-header-box">
      <div class="header-info">
        <h3 class="title">多维性能对比、回归容量预测与拐点识别</h3>
        <p class="subtitle">
          基于多轮压测横向横截面数据，应用一阶线性与二阶多项式高斯消元回归，反解 SLA 约束下的集群安全容量上限与饱和拐点。
        </p>
      </div>
      <div class="header-actions">
        <a-button type="primary" size="small" :loading="calculating" @click="runForecast">
          计算容量预测
        </a-button>
        <a-button size="small" @click="loadSampleCapacity">
          载入示例多轮数据
        </a-button>
      </div>
    </div>

    <!-- SLA 约束与运行过滤表单 -->
    <div class="sla-form-card">
      <a-row :gutter="12">
        <a-col :span="10">
          <div class="field-item">
            <span class="field-lbl">比对压测运行 ID (逗号分隔):</span>
            <a-input v-model:value="runIdsInput" size="small" placeholder="例如: 101, 102, 103, 104" />
          </div>
        </a-col>
        <a-col :span="7">
          <div class="field-item">
            <span class="field-lbl">SLA 最大 P95 延迟 (ms):</span>
            <a-input-number v-model:value="slaForm.maxP95" :min="10" :step="50" size="small" style="width: 100%" />
          </div>
        </a-col>
        <a-col :span="7">
          <div class="field-item">
            <span class="field-lbl">SLA 容忍最大错误率 (%):</span>
            <a-input-number v-model:value="slaForm.maxErrorRate" :min="0.1" :max="10.0" :step="0.5" size="small" style="width: 100%" />
          </div>
        </a-col>
      </a-row>
    </div>

    <!-- 核心容量指标 KPI 卡片 -->
    <div v-if="forecastData && forecastData.capacity_limit" class="kpi-summary-grid">
      <a-card size="small" class="kpi-card highlight-card">
        <div class="kpi-title">最大安全承载并发上限 (Capacity Limit)</div>
        <div class="kpi-val-row">
          <span class="kpi-num">{{ Math.round(forecastData.capacity_limit.max_safe_concurrency) }}</span>
          <span class="kpi-unit">VU 并发</span>
          <a-tag :color="getConfidenceColor(forecastData.regression_models?.confidence)" class="confidence-tag">
            置信度 {{ forecastData.regression_models?.confidence }} (R² = {{ forecastData.regression_models?.avg_r_squared }})
          </a-tag>
        </div>
      </a-card>

      <a-card size="small" class="kpi-card">
        <div class="kpi-title">预估集群峰值吞吐量 (Peak RPS)</div>
        <div class="kpi-val-row">
          <span class="kpi-num">{{ Math.round(forecastData.capacity_limit.predicted_max_rps) }}</span>
          <span class="kpi-unit">RPS</span>
        </div>
      </a-card>

      <a-card size="small" class="kpi-card">
        <div class="kpi-title">性能饱和拐点 (Knee Point)</div>
        <div class="kpi-val-row">
          <span class="kpi-num">{{ forecastData.capacity_limit.knee_point?.concurrency ?? 'N/A' }}</span>
          <span class="kpi-unit">VU @ {{ forecastData.capacity_limit.knee_point?.rps ?? 'N/A' }} RPS</span>
        </div>
      </a-card>
    </div>

    <!-- 架构建议横幅 -->
    <div v-if="forecastData && forecastData.recommendation" class="advice-banner">
      <div class="advice-icon">💡</div>
      <div class="advice-text">{{ forecastData.recommendation }}</div>
    </div>

    <!-- 核心回归拟合曲线图 -->
    <a-card title="并发-吞吐量线性扩展与并发-延迟多项式回归预测曲线" size="small" class="chart-card">
      <div class="chart-box">
        <VChart :option="chartOption" autoresize class="echarts-view" />
      </div>
    </a-card>

    <!-- 横向多轮压测横截面比对矩阵表格 -->
    <div v-if="comparisonRows.length" class="matrix-card">
      <div class="matrix-header">
        <span class="matrix-title">多轮压测横截面比对矩阵 (Comparison Matrix)</span>
      </div>
      <a-table
        :columns="columns"
        :data-source="comparisonRows"
        :pagination="false"
        size="small"
        row-key="run_id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'efficiency'">
            <a-tag color="blue">
              {{ record.scaling_efficiency ? `${record.scaling_efficiency} RPS/VU` : 'N/A' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'error_rate'">
            <span :class="{ 'text-danger': record.error_rate > 0.01 }">
              {{ (record.error_rate * 100).toFixed(2) }}%
            </span>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { message } from 'ant-design-vue'
import {
  performanceApi,
  type PerformanceCapacityForecastResponse,
  type ComparisonMatrixItem,
} from '@/api'

const calculating = ref(false)
const runIdsInput = ref('101, 102, 103, 104')

const slaForm = ref({
  maxP95: 500,
  maxErrorRate: 1.0,
})

const forecastData = ref<PerformanceCapacityForecastResponse | null>(null)

const columns = [
  { title: '运行 ID', dataIndex: 'run_id', width: 90 },
  { title: '并发 (VU)', dataIndex: 'concurrency', width: 110 },
  { title: '吞吐量 (RPS)', dataIndex: 'rps', width: 130 },
  { title: 'P95 延迟 (ms)', dataIndex: 'p95_ms', width: 130 },
  { title: '错误率 (%)', key: 'error_rate', width: 120 },
  { title: '单机扩展效能比', key: 'efficiency', width: 160 },
]

const comparisonRows = computed<ComparisonMatrixItem[]>(() => {
  return forecastData.value?.comparison?.comparison_matrix || []
})

const getConfidenceColor = (conf?: string): string => {
  switch (conf) {
    case 'High':
      return 'green'
    case 'Medium':
      return 'blue'
    case 'Low':
      return 'orange'
    default:
      return 'default'
  }
}

const chartOption = computed<EChartsOption>(() => {
  const matrix = comparisonRows.value
  const xTested = matrix.map((m) => m.concurrency)
  const rpsTested = matrix.map((m) => [m.concurrency, m.rps])
  const p95Tested = matrix.map((m) => [m.concurrency, m.p95_ms])

  const maxTestedVu = xTested.length ? Math.max(...xTested) : 600
  const maxSafeVu = forecastData.value?.capacity_limit?.max_safe_concurrency || maxTestedVu * 1.5
  const maxX = Math.max(maxTestedVu * 1.5, maxSafeVu * 1.1)

  // Generate fitted regression line/curve points
  const rpsModel = forecastData.value?.regression_models?.rps_linear
  const p95Model = forecastData.value?.regression_models?.p95_polynomial

  const fittedRps: number[][] = []
  const fittedP95: number[][] = []

  const stepCount = 20
  for (let i = 0; i <= stepCount; i++) {
    const x = Math.round((maxX / stepCount) * i)
    if (rpsModel && rpsModel.valid) {
      const yRps = (rpsModel.slope || 0) * x + (rpsModel.intercept || 0)
      fittedRps.push([x, Math.max(0, Math.round(yRps))])
    }
    if (p95Model && p95Model.valid) {
      const yP95 = (p95Model.a || 0) * (x ** 2) + (p95Model.b || 0) * x + (p95Model.c || 0)
      fittedP95.push([x, Math.max(0, Math.round(yP95))])
    }
  }

  const knee = forecastData.value?.capacity_limit?.knee_point

  return {
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['实测吞吐量 (RPS)', 'RPS 线性拟合', '实测 P95 延迟 (ms)', 'P95 二次多项式拟合'],
      right: 20,
    },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'value',
      name: '并发负载 (VU)',
      min: 0,
      max: Math.round(maxX),
    },
    yAxis: [
      { type: 'value', name: '吞吐量 (RPS)', position: 'left' },
      { type: 'value', name: 'P95 响应延迟 (ms)', position: 'right' },
    ],
    series: [
      {
        name: '实测吞吐量 (RPS)',
        type: 'scatter',
        symbolSize: 10,
        itemStyle: { color: '#1890ff' },
        data: rpsTested,
      },
      {
        name: 'RPS 线性拟合',
        type: 'line',
        data: fittedRps,
        smooth: false,
        lineStyle: { type: 'dashed', color: '#1890ff', width: 2 },
      },
      {
        name: '实测 P95 延迟 (ms)',
        type: 'scatter',
        yAxisIndex: 1,
        symbolSize: 10,
        itemStyle: { color: '#fa8c16' },
        data: p95Tested,
      },
      {
        name: 'P95 二次多项式拟合',
        type: 'line',
        yAxisIndex: 1,
        data: fittedP95,
        smooth: true,
        lineStyle: { type: 'dashed', color: '#fa8c16', width: 2 },
        markLine: {
          symbol: ['none', 'none'],
          data: [
            {
              yAxis: slaForm.value.maxP95,
              lineStyle: { color: '#f5222d', type: 'dotted', width: 2 },
              label: { formatter: `SLA 阈值: ${slaForm.value.maxP95}ms` },
            },
          ],
        },
        markPoint: knee && knee.concurrency
          ? {
              data: [
                {
                  name: '饱和拐点',
                  coord: [knee.concurrency, knee.p95_ms || 100],
                  value: '饱和拐点',
                  itemStyle: { color: '#722ed1' },
                },
              ],
            }
          : undefined,
      },
    ],
  }
})

const runForecast = async () => {
  const ids = runIdsInput.value
    .split(',')
    .map((s) => Number(s.trim()))
    .filter((n) => !isNaN(n) && n > 0)

  if (ids.length < 2) {
    message.warning('请输入至少 2 个有效的压测运行记录 ID')
    return
  }

  calculating.value = true
  try {
    const res = await performanceApi.forecastCapacity({
      run_ids: ids,
      sla_max_p95_ms: slaForm.value.maxP95,
      sla_max_error_rate: slaForm.value.maxErrorRate / 100.0,
      min_samples: 2,
    })
    forecastData.value = res
    if (res.status === 'ready') {
      message.success(`容量预测计算完成！最大安全承载: ${Math.round(res.capacity_limit?.max_safe_concurrency || 0)} VU`)
    } else {
      message.warning(res.message || '达标样本轮次不足，无法拟合')
    }
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '计算容量预测失败'
    message.error(msg)
  } finally {
    calculating.value = false
  }
}

const loadSampleCapacity = () => {
  const matrix: ComparisonMatrixItem[] = [
    { run_id: 101, status: 'success', created_at: '2026-10-16 10:00', concurrency: 100, rps: 1000, p95_ms: 50, error_rate: 0.0, scaling_efficiency: 10.0 },
    { run_id: 102, status: 'success', created_at: '2026-10-16 10:30', concurrency: 200, rps: 1950, p95_ms: 70, error_rate: 0.001, scaling_efficiency: 9.75 },
    { run_id: 103, status: 'success', created_at: '2026-10-16 11:00', concurrency: 400, rps: 3600, p95_ms: 140, error_rate: 0.002, scaling_efficiency: 9.0 },
    { run_id: 104, status: 'success', created_at: '2026-10-16 11:30', concurrency: 600, rps: 4800, p95_ms: 280, error_rate: 0.003, scaling_efficiency: 8.0 },
  ]

  forecastData.value = {
    status: 'ready',
    sample_count: 4,
    sla_criteria: { max_p95_ms: 500.0, max_error_rate: 0.01 },
    regression_models: {
      rps_linear: { slope: 7.7, intercept: 350.0, r_squared: 0.995, valid: true },
      p95_polynomial: { a: 0.00065, b: 0.07, c: 38.0, r_squared: 0.998, valid: true, model_type: 'polynomial_deg2' },
      confidence: 'High',
      avg_r_squared: 0.9965,
    },
    capacity_limit: {
      max_safe_concurrency: 792.0,
      predicted_max_rps: 6450.0,
      knee_point: matrix[3],
    },
    recommendation: '在 P95 响应延迟不超过 500ms 且错误率低于 1.0% 的 SLA 约束下，预测当前集群最大安全承载并发上限为 792 VU，预估峰值吞吐量为 6450 RPS。性能饱和拐点位于 600 VU 附近，超过此区间后边际收益递减并伴随延迟剧增。',
    comparison: {
      total_runs: 4,
      valid_points_count: 4,
      comparison_matrix: matrix,
      best_throughput: { run_id: 104, max_rps: 4800, at_concurrency: 600 },
      peak_efficiency: { run_id: 101, scaling_efficiency: 10.0, at_concurrency: 100 },
    },
  }
}

onMounted(() => {
  loadSampleCapacity()
})
</script>

<style scoped>
.capacity-regression-chart {
  padding: 4px 0;
}
.control-header-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 14px;
}
.header-info .title {
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: var(--c-text-primary, #111827);
}
.header-info .subtitle {
  font-size: 12px;
  color: var(--c-text-secondary, #6b7280);
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.sla-form-card {
  padding: 12px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 16px;
}
.field-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-lbl {
  font-size: 11px;
  color: var(--c-text-secondary, #4b5563);
}
.kpi-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.kpi-card {
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e5e7eb);
}
.kpi-card.highlight-card {
  border-color: #1890ff;
  background: rgba(24, 144, 255, 0.03);
}
.kpi-title {
  font-size: 12px;
  color: var(--c-text-secondary, #4b5563);
  margin-bottom: 8px;
}
.kpi-val-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.kpi-num {
  font-size: 22px;
  font-weight: 800;
  color: var(--c-text-primary, #111827);
}
.kpi-unit {
  font-size: 12px;
  color: var(--c-text-tertiary, #9ca3af);
}
.confidence-tag {
  margin-left: auto;
  font-weight: 600;
}
.advice-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(24, 144, 255, 0.06);
  border: 1px solid rgba(24, 144, 255, 0.2);
  border-radius: 8px;
  margin-bottom: 16px;
}
.advice-icon {
  font-size: 20px;
}
.advice-text {
  font-size: 12px;
  color: var(--c-text-primary, #1f2937);
  line-height: 1.5;
}
.chart-card {
  border-radius: 8px;
  margin-bottom: 16px;
}
.chart-box {
  height: 380px;
}
.echarts-view {
  width: 100%;
  height: 100%;
}
.matrix-card {
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
}
.matrix-header {
  margin-bottom: 10px;
}
.matrix-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #111827);
}
.text-danger {
  color: #cf1322;
  font-weight: 600;
}
</style>
