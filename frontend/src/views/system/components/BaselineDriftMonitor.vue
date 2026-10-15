<template>
  <div class="baseline-drift-monitor">
    <!-- 顶部状态栏与操作 -->
    <div class="monitor-header-bar">
      <div class="header-info">
        <h3 class="title">性能基准 Baseline 漂移监控与智能晋升</h3>
        <p class="subtitle">实时比对压测指标与历史基线的偏离度，精准拦截 RPS 下跌与 P95 恶化，并支持更优结果一键晋升。</p>
      </div>

      <div class="header-actions">
        <div class="id-inputs">
          <a-input-number
            v-model:value="currentTestId"
            :min="1"
            size="small"
            placeholder="压测测试 ID"
            style="width: 120px"
          />
          <a-input-number
            v-model:value="currentRunId"
            :min="1"
            size="small"
            placeholder="压测执行 ID"
            style="width: 120px"
          />
        </div>
        <a-button type="primary" size="small" :loading="loading" @click="fetchDriftAlert">
          检查基线漂移
        </a-button>
        <a-button size="small" :loading="aligning" @click="runAutoPromote">
          智能对齐并晋升
        </a-button>
        <a-button size="small" @click="loadSampleDrift">
          载入漂移示例
        </a-button>
      </div>
    </div>

    <!-- 告警与漂移状态横幅 -->
    <div
      v-if="driftData"
      class="status-banner"
      :class="`severity-${driftData.severity}`"
    >
      <div class="banner-icon">
        <CheckCircleOutlined v-if="driftData.severity === 'none'" />
        <WarningOutlined v-else-if="driftData.severity === 'warning'" />
        <AlertOutlined v-else />
      </div>
      <div class="banner-body">
        <div class="banner-top">
          <span class="status-title">
            {{
              driftData.severity === 'none'
                ? '各项性能指标稳定，完全在基线容差范围内 (STABLE)'
                : driftData.severity === 'warning'
                ? '性能指标出现轻度漂移，建议关注趋势 (WARNING)'
                : '性能指标发生严重劣化，已触发基线漂移告警 (CRITICAL)'
            }}
          </span>
          <a-tag :color="getSeverityTagColor(driftData.severity)">
            {{ driftData.severity.toUpperCase() }}
          </a-tag>
        </div>
        <div v-if="driftData.alert_reasons && driftData.alert_reasons.length" class="alert-reasons-list">
          <div v-for="(reason, rIdx) in driftData.alert_reasons" :key="rIdx" class="reason-item">
            • {{ reason }}
          </div>
        </div>
        <div v-else class="normal-tip">
          RPS、P95 延迟与接口错误率波动均在安全阈值（RPS 下跌 &lt; 15%，P95 恶化 &lt; 20%）内。
        </div>
      </div>
    </div>

    <!-- 核心指标对比横向卡片 -->
    <div v-if="driftData" class="metrics-comparison-grid">
      <!-- 1. 吞吐量 RPS -->
      <a-card size="small" class="metric-delta-card" :class="{ 'has-regression': driftData.deltas.rps_delta_pct < -15 }">
        <div class="card-title">吞吐量 (Throughput RPS)</div>
        <div class="card-values">
          <div class="val-box">
            <span class="lbl">基线目标</span>
            <span class="num">{{ driftData.baseline_summary?.rps?.toFixed(1) ?? 'N/A' }}</span>
          </div>
          <div class="val-arrow">→</div>
          <div class="val-box">
            <span class="lbl">当前实测</span>
            <span class="num">{{ driftData.current_summary?.rps?.toFixed(1) ?? 'N/A' }}</span>
          </div>
        </div>
        <div class="delta-badge" :class="driftData.deltas.rps_delta_pct >= 0 ? 'good' : 'bad'">
          偏离: {{ driftData.deltas.rps_delta_pct > 0 ? '+' : '' }}{{ driftData.deltas.rps_delta_pct.toFixed(2) }}%
        </div>
      </a-card>

      <!-- 2. P95 响应延迟 -->
      <a-card size="small" class="metric-delta-card" :class="{ 'has-regression': driftData.deltas.p95_delta_pct > 20 }">
        <div class="card-title">P95 响应延迟 (Latency)</div>
        <div class="card-values">
          <div class="val-box">
            <span class="lbl">基线目标</span>
            <span class="num">{{ driftData.baseline_summary?.p95_ms?.toFixed(1) ?? 'N/A' }} ms</span>
          </div>
          <div class="val-arrow">→</div>
          <div class="val-box">
            <span class="lbl">当前实测</span>
            <span class="num">{{ driftData.current_summary?.p95_ms?.toFixed(1) ?? 'N/A' }} ms</span>
          </div>
        </div>
        <div class="delta-badge" :class="driftData.deltas.p95_delta_pct <= 0 ? 'good' : 'bad'">
          偏离: {{ driftData.deltas.p95_delta_pct > 0 ? '+' : '' }}{{ driftData.deltas.p95_delta_pct.toFixed(2) }}%
        </div>
      </a-card>

      <!-- 3. 错误率 -->
      <a-card size="small" class="metric-delta-card" :class="{ 'has-regression': driftData.deltas.error_rate_delta_pct > 2.0 }">
        <div class="card-title">接口错误率 (Error Rate)</div>
        <div class="card-values">
          <div class="val-box">
            <span class="lbl">基线目标</span>
            <span class="num">{{ ((driftData.baseline_summary?.error_rate ?? 0) * 100).toFixed(2) }}%</span>
          </div>
          <div class="val-arrow">→</div>
          <div class="val-box">
            <span class="lbl">当前实测</span>
            <span class="num">{{ ((driftData.current_summary?.error_rate ?? 0) * 100).toFixed(2) }}%</span>
          </div>
        </div>
        <div class="delta-badge" :class="driftData.deltas.error_rate_delta_pct <= 0 ? 'good' : 'bad'">
          增量: {{ driftData.deltas.error_rate_delta_pct > 0 ? '+' : '' }}{{ driftData.deltas.error_rate_delta_pct.toFixed(2) }}%
        </div>
      </a-card>
    </div>

    <!-- 基准晋升与对齐候选建议面板 -->
    <div v-if="promotionResult" class="promotion-panel">
      <div class="promotion-header">
        <span class="prom-title">基准晋升评估建议 (Baseline Promotion Candidate)</span>
        <a-tag :color="promotionResult.eligible ? 'green' : 'orange'">
          {{ promotionResult.eligible ? '具备基准晋升资格' : '暂未达标，维持原基线' }}
        </a-tag>
      </div>
      <div class="promotion-body">
        <div v-if="promotionResult.reasons && promotionResult.reasons.length" class="prom-reasons">
          <div v-for="(reason, idx) in promotionResult.reasons" :key="idx" class="prom-reason-item">
            ✔ {{ reason }}
          </div>
        </div>
        <div v-if="promotionResult.promoted" class="prom-success-box">
          🎉 成功原子打标！新基准已锁定至运行记录 ID: {{ promotionResult.new_baseline_run_id }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { AlertOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import {
  performanceApi,
  type PerformanceDriftAlertResponse,
  type PerformanceAlignBaselineResponse,
} from '@/api'

const props = withDefaults(
  defineProps<{
    testId?: number
    runId?: number
  }>(),
  {
    testId: 1,
    runId: 101,
  },
)

const loading = ref(false)
const aligning = ref(false)
const currentTestId = ref<number>(props.testId)
const currentRunId = ref<number>(props.runId)
const driftData = ref<PerformanceDriftAlertResponse | null>(null)
const promotionResult = ref<PerformanceAlignBaselineResponse | null>(null)

const getSeverityTagColor = (sev: string): string => {
  switch (sev) {
    case 'critical':
      return 'red'
    case 'warning':
      return 'orange'
    case 'none':
      return 'green'
    default:
      return 'default'
  }
}

const fetchDriftAlert = async () => {
  if (!currentRunId.value) {
    message.warning('请输入压测执行 ID')
    return
  }
  loading.value = true
  try {
    const res = await performanceApi.getDriftAlert(currentRunId.value)
    driftData.value = res
    message.success('已完成基线偏离度与告警检测！')
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '检查基线漂移失败'
    message.error(msg)
  } finally {
    loading.value = false
  }
}

const runAutoPromote = async () => {
  if (!currentTestId.value) {
    message.warning('请输入压测测试 ID')
    return
  }
  aligning.value = true
  try {
    const res = await performanceApi.alignBaseline(currentTestId.value, true)
    promotionResult.value = res
    if (res.promoted) {
      message.success(`成功晋升新基准！基线 ID: ${res.new_baseline_run_id}`)
    } else {
      message.info(res.reasons?.[0] || '评估完成，维持既有基准')
    }
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '智能对齐基准失败'
    message.error(msg)
  } finally {
    aligning.value = false
  }
}

const loadSampleDrift = () => {
  driftData.value = {
    is_drifted: true,
    should_alert: true,
    severity: 'critical',
    alert_reasons: [
      '吞吐量 (RPS) 较基线严重下跌 -24.50% (阈值: 15.0%)',
      'P95 响应延迟较基线恶化 +32.40% (阈值: 20.0%)',
    ],
    deltas: {
      rps_delta_pct: -24.5,
      p95_delta_pct: 32.4,
      error_rate_delta_pct: 0.8,
    },
    baseline_summary: {
      rps: 1200.0,
      p95_ms: 65.0,
      error_rate: 0.002,
    },
    current_summary: {
      rps: 906.0,
      p95_ms: 86.1,
      error_rate: 0.010,
    },
  }

  promotionResult.value = {
    eligible: true,
    is_first_baseline: false,
    reasons: ['候选运行吞吐量提升并在容差阈值内，具备晋升资格'],
    promoted: true,
    new_baseline_run_id: currentRunId.value,
    candidate_run_id: currentRunId.value,
  }
}

onMounted(() => {
  loadSampleDrift()
})
</script>

<style scoped>
.baseline-drift-monitor {
  padding: 4px 0;
}
.monitor-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 18px;
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
  align-items: center;
  gap: 8px;
}
.id-inputs {
  display: flex;
  gap: 6px;
}
.status-banner {
  display: flex;
  align-items: flex-start;
  padding: 14px 18px;
  border-radius: 8px;
  margin-bottom: 18px;
  border: 1px solid transparent;
}
.status-banner.severity-none {
  background: rgba(82, 196, 26, 0.08);
  border-color: rgba(82, 196, 26, 0.25);
}
.status-banner.severity-warning {
  background: rgba(250, 140, 22, 0.08);
  border-color: rgba(250, 140, 22, 0.25);
}
.status-banner.severity-critical {
  background: rgba(245, 34, 45, 0.08);
  border-color: rgba(245, 34, 45, 0.3);
}
.banner-icon {
  font-size: 22px;
  margin-right: 14px;
  margin-top: 2px;
}
.severity-none .banner-icon {
  color: #52c41a;
}
.severity-warning .banner-icon {
  color: #fa8c16;
}
.severity-critical .banner-icon {
  color: #f5222d;
}
.banner-body {
  flex: 1;
}
.banner-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.status-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.alert-reasons-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #cf1322;
  font-weight: 600;
}
.normal-tip {
  font-size: 12px;
  color: var(--c-text-secondary, #4b5563);
}
.metrics-comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.metric-delta-card {
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e5e7eb);
}
.metric-delta-card.has-regression {
  border-color: #ff4d4f;
  background: rgba(255, 77, 79, 0.02);
}
.card-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #4b5563);
  margin-bottom: 10px;
}
.card-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.val-box {
  display: flex;
  flex-direction: column;
}
.val-box .lbl {
  font-size: 10px;
  color: var(--c-text-tertiary, #9ca3af);
}
.val-box .num {
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.val-arrow {
  color: #9ca3af;
  font-weight: 700;
}
.delta-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  display: inline-block;
}
.delta-badge.good {
  background: rgba(82, 196, 26, 0.1);
  color: #52c41a;
}
.delta-badge.bad {
  background: rgba(245, 34, 45, 0.1);
  color: #cf1322;
}
.promotion-panel {
  padding: 14px 18px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
}
.promotion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.prom-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #111827);
}
.prom-reasons {
  font-size: 12px;
  color: var(--c-text-secondary, #4b5563);
  margin-bottom: 8px;
}
.prom-success-box {
  padding: 6px 10px;
  background: rgba(82, 196, 26, 0.1);
  border-radius: 4px;
  color: #52c41a;
  font-size: 12px;
  font-weight: 600;
}
</style>
