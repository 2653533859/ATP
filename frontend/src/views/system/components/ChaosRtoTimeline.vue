<template>
  <div class="chaos-rto-timeline">
    <!-- 顶部状态栏与自愈 RTO 评级摘要 -->
    <div v-if="rtoData" class="rto-summary-bar">
      <div class="summary-left">
        <div class="grade-badge" :class="`grade-${rtoData.resilience_grade.toLowerCase()}`">
          <div class="grade-val">Grade {{ rtoData.resilience_grade }}</div>
          <div class="grade-score">{{ rtoData.resilience_score.toFixed(1) }} 分</div>
        </div>

        <div class="rto-core-info">
          <div class="rto-title-line">
            <span class="rto-label">自愈恢复时长 (RTO):</span>
            <strong v-if="rtoData.recovered" class="rto-seconds">
              {{ rtoData.rto_seconds?.toFixed(2) }} 秒
            </strong>
            <strong v-else class="rto-unrecovered">未在窗口内自愈 (FAIL)</strong>
            <a-tag :color="rtoData.recovered ? 'green' : 'red'">
              {{ rtoData.recovered ? '自愈成功' : '自愈超时' }}
            </a-tag>
          </div>
          <p class="rto-recommendation">{{ rtoData.recommendation }}</p>
        </div>
      </div>

      <div class="summary-stats">
        <div class="stat-item">
          <span class="stat-lbl">故障前基线 RPS</span>
          <span class="stat-val">{{ rtoData.baseline_metrics.rps.toFixed(1) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-lbl">故障中最低 RPS</span>
          <span class="stat-val text-danger">{{ rtoData.in_fault_metrics.min_rps.toFixed(1) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-lbl">吞吐量最大跌幅</span>
          <span class="stat-val text-danger">-{{ rtoData.in_fault_metrics.rps_drop_pct.toFixed(1) }}%</span>
        </div>
        <div class="stat-item">
          <span class="stat-lbl">防抖持续健康门槛</span>
          <span class="stat-val">{{ rtoData.recovery_targets.sustain_seconds.toFixed(1) }}s</span>
        </div>
      </div>
    </div>

    <!-- 交互式配置与演练操作栏 -->
    <div class="controls-card">
      <div class="controls-header">
        <span class="controls-title">混沌故障注入与自愈测定控制</span>
        <div class="controls-actions">
          <a-input-number
            v-model:value="currentRunId"
            :min="1"
            size="small"
            placeholder="压测运行 ID"
            style="width: 120px"
          />
          <a-button type="primary" size="small" :loading="evaluating" @click="evaluateRto">
            测定自愈 RTO
          </a-button>
          <a-button size="small" :loading="planning" @click="createPlan">
            编排故障注入
          </a-button>
          <a-button size="small" @click="loadSampleChaos">
            载入示例混沌演练
          </a-button>
        </div>
      </div>

      <a-row :gutter="12" class="form-row">
        <a-col :span="6">
          <div class="field-box">
            <span class="field-lbl">故障类型:</span>
            <a-select v-model:value="chaosConfig.faultType" size="small" style="width: 100%">
              <a-select-option value="service_unavailable">下游 503 宕机</a-select-option>
              <a-select-option value="latency_spike">下游延迟突增</a-select-option>
              <a-select-option value="packet_loss">网络传输丢包</a-select-option>
              <a-select-option value="connection_reset">TCP 连接中断</a-select-option>
            </a-select>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="field-box">
            <span class="field-lbl">注入起始秒数:</span>
            <a-input-number v-model:value="chaosConfig.startOffset" :min="0" size="small" style="width: 100%" />
          </div>
        </a-col>
        <a-col :span="6">
          <div class="field-box">
            <span class="field-lbl">故障持续秒数:</span>
            <a-input-number v-model:value="chaosConfig.duration" :min="1" size="small" style="width: 100%" />
          </div>
        </a-col>
        <a-col :span="6">
          <div class="field-box">
            <span class="field-lbl">恢复门槛比例:</span>
            <a-input-number v-model:value="chaosConfig.recoveryRpsRatio" :min="0.5" :max="1.0" :step="0.05" size="small" style="width: 100%" />
          </div>
        </a-col>
      </a-row>
    </div>

    <!-- 核心时序曲线图 -->
    <a-card title="三段式混沌故障注入与自愈恢复轨迹图 (Timeline & RTO Trajectory)" size="small" class="chart-card">
      <div class="chart-box">
        <VChart :option="chartOption" autoresize class="echarts-view" />
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import { message } from 'ant-design-vue'
import {
  performanceApi,
  type ChaosRtoEvaluateResponse,
  type ChaosRtoTimeSeriesItem,
} from '@/api'

const props = withDefaults(
  defineProps<{
    runId?: number
  }>(),
  {
    runId: 101,
  },
)

const currentRunId = ref<number>(props.runId)
const planning = ref(false)
const evaluating = ref(false)

const chaosConfig = ref({
  faultType: 'service_unavailable',
  targetService: 'order-downstream-api',
  startOffset: 10,
  duration: 20,
  recoveryRpsRatio: 0.85,
})

const timeSeriesData = ref<ChaosRtoTimeSeriesItem[]>([])
const rtoData = ref<ChaosRtoEvaluateResponse | null>(null)

const chartOption = computed<EChartsOption>(() => {
  const series = timeSeriesData.value || []
  const xLabels = series.map((s) => `${s.offset_seconds}s`)
  const rpsValues = series.map((s) => s.rps)
  const p95Values = series.map((s) => s.p95_ms)

  const faultStart = chaosConfig.value.startOffset
  const faultEnd = chaosConfig.value.startOffset + chaosConfig.value.duration
  const recoveredAt = rtoData.value?.recovered_at_offset

  return {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: ['吞吐量 RPS', 'P95 延迟 (ms)'],
      right: 20,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xLabels,
      name: '压测时间 (秒)',
    },
    yAxis: [
      {
        type: 'value',
        name: '吞吐量 (RPS)',
        position: 'left',
      },
      {
        type: 'value',
        name: 'P95 延迟 (ms)',
        position: 'right',
      },
    ],
    series: [
      {
        name: '吞吐量 RPS',
        type: 'line',
        data: rpsValues,
        smooth: true,
        itemStyle: { color: '#1890ff' },
        markArea: {
          itemStyle: {
            color: 'rgba(255, 77, 79, 0.12)',
          },
          data: [
            [
              { name: '故障注入区间 (Fault Window)', xAxis: `${faultStart}s` },
              { xAxis: `${faultEnd}s` },
            ],
          ],
        },
        markLine: recoveredAt != null
          ? {
              symbol: ['none', 'none'],
              label: {
                formatter: `自愈恢复点 (${recoveredAt}s)\nRTO = ${rtoData.value?.rto_seconds}s`,
                position: 'insideEndTop',
              },
              lineStyle: {
                color: '#52c41a',
                width: 2,
                type: 'dashed',
              },
              data: [{ xAxis: `${recoveredAt}s` }],
            }
          : undefined,
      },
      {
        name: 'P95 延迟 (ms)',
        type: 'line',
        yAxisIndex: 1,
        data: p95Values,
        smooth: true,
        itemStyle: { color: '#fa8c16' },
      },
    ],
  }
})

const createPlan = async () => {
  if (!currentRunId.value) {
    message.warning('请输入压测运行 ID')
    return
  }
  planning.value = true
  try {
    const res = await performanceApi.createChaosPlan(currentRunId.value, {
      fault_type: chaosConfig.value.faultType,
      target_service: chaosConfig.value.targetService,
      start_delay_seconds: chaosConfig.value.startOffset,
      duration_seconds: chaosConfig.value.duration,
    })
    message.success(`成功编排混沌注入任务！计划 ID: ${res.plan_id}`)
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '编排混沌计划失败'
    message.error(msg)
  } finally {
    planning.value = false
  }
}

const evaluateRto = async () => {
  if (!currentRunId.value) {
    message.warning('请输入压测运行 ID')
    return
  }
  evaluating.value = true
  try {
    const res = await performanceApi.evaluateChaosRto(currentRunId.value, {
      time_series: timeSeriesData.value,
      fault_start_offset: chaosConfig.value.startOffset,
      fault_duration: chaosConfig.value.duration,
      recovery_rps_ratio: chaosConfig.value.recoveryRpsRatio,
      sustain_seconds: 3.0,
    })
    rtoData.value = res
    message.success(`自愈 RTO 测定完成: ${res.recovered ? `${res.rto_seconds}s (Grade ${res.resilience_grade})` : '未恢复'}`)
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '测定自愈 RTO 失败'
    message.error(msg)
  } finally {
    evaluating.value = false
  }
}

const loadSampleChaos = () => {
  const series: ChaosRtoTimeSeriesItem[] = []
  // 0 - 9s: Baseline (1000 RPS, 50ms)
  for (let t = 0; t < 10; t++) {
    series.push({ offset_seconds: t, rps: 1000, p95_ms: 50, error_rate: 0.0 })
  }
  // 10 - 29s: In-Fault (120 RPS, 450ms, 35% error)
  for (let t = 10; t < 30; t++) {
    series.push({ offset_seconds: t, rps: 120, p95_ms: 450, error_rate: 0.35 })
  }
  // 30 - 31s: Immediate post-fault transition
  series.push({ offset_seconds: 30, rps: 350, p95_ms: 220, error_rate: 0.12 })
  series.push({ offset_seconds: 31, rps: 680, p95_ms: 110, error_rate: 0.04 })
  // 32 - 45s: Sustained recovered healthy window (960 RPS, 52ms) -> RTO = 32.5s - 30s = 2.5s
  for (let t = 32; t <= 45; t++) {
    series.push({ offset_seconds: t, rps: 960, p95_ms: 52, error_rate: 0.005 })
  }

  timeSeriesData.value = series
  chaosConfig.value.startOffset = 10
  chaosConfig.value.duration = 20

  rtoData.value = {
    recovered: true,
    rto_seconds: 2.5,
    recovered_at_offset: 32.5,
    fault_start_offset: 10.0,
    fault_end_offset: 30.0,
    baseline_metrics: { rps: 1000.0, p95_ms: 50.0, error_rate: 0.0 },
    in_fault_metrics: { min_rps: 120.0, max_p95_ms: 450.0, max_error_rate: 0.35, rps_drop_pct: 88.0 },
    recovery_targets: { target_rps: 850.0, target_p95_ms: 65.0, target_error_rate: 0.03, sustain_seconds: 3.0 },
    resilience_score: 94.0,
    resilience_grade: 'A',
    recommendation: '服务具备秒级极速自愈能力（RTO < 3s），断路器与快速恢复机制运行优良。',
  }
}

onMounted(() => {
  loadSampleChaos()
})
</script>

<style scoped>
.chaos-rto-timeline {
  padding: 4px 0;
}
.rto-summary-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 18px;
}
.summary-left {
  display: flex;
  align-items: center;
  gap: 18px;
}
.grade-badge {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #ffffff;
  background: #1890ff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}
.grade-badge.grade-a {
  background: #52c41a;
  box-shadow: 0 4px 12px rgba(82, 196, 26, 0.3);
}
.grade-badge.grade-b {
  background: #1890ff;
}
.grade-badge.grade-c {
  background: #fa8c16;
  box-shadow: 0 4px 12px rgba(250, 140, 22, 0.3);
}
.grade-badge.grade-d,
.grade-badge.grade-f {
  background: #f5222d;
  box-shadow: 0 4px 12px rgba(245, 34, 45, 0.3);
}
.grade-val {
  font-size: 16px;
  font-weight: 800;
  line-height: 1;
}
.grade-score {
  font-size: 11px;
  opacity: 0.9;
  margin-top: 3px;
}
.rto-core-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rto-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rto-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #111827);
}
.rto-seconds {
  font-size: 18px;
  font-weight: 800;
  color: #52c41a;
}
.rto-unrecovered {
  font-size: 16px;
  font-weight: 800;
  color: #cf1322;
}
.rto-recommendation {
  font-size: 12px;
  color: var(--c-text-secondary, #6b7280);
  margin: 0;
}
.summary-stats {
  display: flex;
  gap: 20px;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.stat-lbl {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
}
.stat-val {
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.stat-val.text-danger {
  color: #cf1322;
}
.controls-card {
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 18px;
}
.controls-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.controls-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #111827);
}
.controls-actions {
  display: flex;
  gap: 8px;
}
.form-row {
  margin-top: 4px;
}
.field-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-lbl {
  font-size: 11px;
  color: var(--c-text-secondary, #4b5563);
}
.chart-card {
  border-radius: 8px;
}
.chart-box {
  height: 380px;
}
.echarts-view {
  width: 100%;
  height: 100%;
}
</style>
