<template>
  <div class="network-resilience-radar">
    <!-- 头部指标与评分概览 -->
    <div class="resilience-summary-card">
      <div class="summary-left">
        <div class="score-badge" :class="`grade-${metricsSummary.resilience_rating.toLowerCase()}`">
          <div class="score-val">{{ metricsSummary.resilience_score.toFixed(1) }}</div>
          <div class="score-lbl">抗弱网韧性分</div>
        </div>
        <div class="summary-info">
          <div class="info-top">
            <span class="rating-tag" :class="`grade-${metricsSummary.resilience_rating.toLowerCase()}`">
              等级 {{ metricsSummary.resilience_rating }}
            </span>
            <span class="profile-chip">弱网模式: {{ profileName }}</span>
          </div>
          <p class="summary-desc">
            基于网络往返延迟、极端丢包率、超时频度与自动重试自愈能力综合评估。
          </p>
        </div>
      </div>

      <div class="summary-stats">
        <div class="stat-col">
          <span class="stat-lbl">平均延迟</span>
          <span class="stat-val">{{ metricsSummary.avg_latency_ms.toFixed(1) }} ms</span>
        </div>
        <div class="stat-col">
          <span class="stat-lbl">P95 延迟</span>
          <span class="stat-val">{{ metricsSummary.p95_latency_ms.toFixed(1) }} ms</span>
        </div>
        <div class="stat-col">
          <span class="stat-lbl">错误率</span>
          <span class="stat-val" :class="{ 'has-error': metricsSummary.error_rate > 0 }">
            {{ (metricsSummary.error_rate * 100).toFixed(1) }}%
          </span>
        </div>
        <div class="stat-col">
          <span class="stat-lbl">重试率</span>
          <span class="stat-val">{{ (metricsSummary.retry_rate * 100).toFixed(1) }}%</span>
        </div>
      </div>
    </div>

    <!-- 图表与故障注入布局 -->
    <a-row :gutter="20" class="content-row">
      <!-- 左侧：多维韧性五维雷达图 -->
      <a-col :span="12">
        <a-card title="抗弱网韧性五维评估雷达图" size="small" class="panel-card">
          <div class="chart-wrapper">
            <VChart :option="radarChartOption" autoresize class="echarts-box" />
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：在线故障注入与规则评估面板 -->
      <a-col :span="12">
        <a-card title="网络故障注入在线模拟与评估" size="small" class="panel-card">
          <a-form layout="vertical">
            <a-form-item label="目标请求 URL">
              <a-input
                v-model:value="faultForm.requestUrl"
                placeholder="例如: https://api.atp.io/v1/payments/checkout"
              />
            </a-form-item>

            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="故障类型 (Action)">
                  <a-select v-model:value="faultForm.action" style="width: 100%">
                    <a-select-option value="dns_spoofing">DNS 劫持与重定向</a-select-option>
                    <a-select-option value="connection_reset">TCP 连接中断 (RESET)</a-select-option>
                    <a-select-option value="timeout">请求网关超时 (TIMEOUT)</a-select-option>
                    <a-select-option value="http_status">下游服务不可用 (503/502)</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="触发概率 (0 ~ 1.0)">
                  <a-input-number
                    v-model:value="faultForm.probability"
                    :min="0"
                    :max="1.0"
                    :step="0.1"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="匹配 URL 正则表达式 (Pattern)">
              <a-input v-model:value="faultForm.urlPattern" placeholder=".*pay.*" />
            </a-form-item>

            <a-button type="primary" :loading="evaluatingFault" @click="runFaultEvaluation">
              执行故障注入试算
            </a-button>
          </a-form>

          <!-- 故障评估结果面板 -->
          <div v-if="faultResult" class="fault-result-box">
            <div class="fault-status-line">
              <span>注入判定:</span>
              <a-tag :color="faultResult.fault_injected ? 'red' : 'green'">
                {{ faultResult.fault_injected ? '已命中并注入故障' : '正常放行 (PASS)' }}
              </a-tag>
              <span class="action-tag">动作: {{ faultResult.action }}</span>
            </div>
            <div v-if="faultResult.fault_injected" class="fault-details">
              <div>目标地址: <code>{{ faultResult.target_url }}</code></div>
              <div v-if="faultResult.details" class="fault-json">
                <pre>{{ JSON.stringify(faultResult.details, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'
import {
  networkSimulationApi,
  type NetworkMetricsSummary,
  type FaultInjectionEvaluateOut,
} from '@/api/networkSimulation'

const props = withDefaults(
  defineProps<{
    profileName?: string
    metrics?: Partial<NetworkMetricsSummary>
  }>(),
  {
    profileName: '2G (EDGE 良好)',
    metrics: () => ({}),
  },
)

const evaluatingFault = ref(false)
const faultResult = ref<FaultInjectionEvaluateOut | null>(null)

const faultForm = ref({
  requestUrl: 'https://api.atp.io/v1/payments/verify',
  action: 'dns_spoofing',
  probability: 1.0,
  urlPattern: '.*pay.*',
})

const metricsSummary = computed<NetworkMetricsSummary>(() => {
  return {
    total_requests: props.metrics.total_requests ?? 50,
    total_errors: props.metrics.total_errors ?? 2,
    total_retries: props.metrics.total_retries ?? 5,
    total_timeouts: props.metrics.total_timeouts ?? 1,
    total_bytes_transferred: props.metrics.total_bytes_transferred ?? 1048576,
    error_rate: props.metrics.error_rate ?? 0.04,
    retry_rate: props.metrics.retry_rate ?? 0.10,
    timeout_rate: props.metrics.timeout_rate ?? 0.02,
    avg_latency_ms: props.metrics.avg_latency_ms ?? 320.0,
    p95_latency_ms: props.metrics.p95_latency_ms ?? 580.0,
    max_latency_ms: props.metrics.max_latency_ms ?? 1200.0,
    resilience_score: props.metrics.resilience_score ?? 86.5,
    resilience_rating: props.metrics.resilience_rating ?? 'B',
  }
})

// Calculate scores for 5 axes (0 - 100)
const radarScores = computed(() => {
  const m = metricsSummary.value
  const latencyScore = Math.max(10, Math.min(100, Math.round(100 - m.avg_latency_ms / 10)))
  const successScore = Math.max(0, Math.min(100, Math.round((1.0 - m.error_rate) * 100)))
  const retryScore = Math.max(10, Math.min(100, Math.round(100 - m.retry_rate * 200)))
  const timeoutScore = Math.max(10, Math.min(100, Math.round(100 - m.timeout_rate * 300)))
  const overallScore = Math.round(m.resilience_score)
  return [latencyScore, successScore, retryScore, timeoutScore, overallScore]
})

const radarChartOption = computed<EChartsOption>(() => {
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: '响应速度', max: 100 },
        { name: '成功率', max: 100 },
        { name: '重试适应力', max: 100 },
        { name: '超时防抖', max: 100 },
        { name: '综合韧性', max: 100 },
      ],
      shape: 'polygon',
      splitNumber: 4,
      axisName: {
        color: '#4b5563',
        fontSize: 12,
        fontWeight: 'bold',
      },
      splitLine: {
        lineStyle: { color: 'rgba(0, 0, 0, 0.1)' },
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(24, 144, 255, 0.02)', 'rgba(24, 144, 255, 0.06)'],
        },
      },
    },
    series: [
      {
        name: '弱网韧性评级',
        type: 'radar',
        data: [
          {
            value: radarScores.value,
            name: '当前模型指标',
            itemStyle: { color: '#1890ff' },
            areaStyle: { color: 'rgba(24, 144, 255, 0.35)' },
          },
        ],
      },
    ],
  }
})

const runFaultEvaluation = async () => {
  evaluatingFault.value = true
  try {
    const res = await networkSimulationApi.evaluateFaultInjection({
      request_url: faultForm.value.requestUrl,
      fault_policy: {
        action: faultForm.value.action,
        probability: faultForm.value.probability,
        url_pattern: faultForm.value.urlPattern,
      },
    })
    faultResult.value = res
  } catch {
    // Local fallback simulation
    const pattern = new RegExp(faultForm.value.urlPattern, 'i')
    const matches = pattern.test(faultForm.value.requestUrl)
    const injected = matches && Math.random() <= faultForm.value.probability

    faultResult.value = {
      fault_injected: injected,
      action: injected ? faultForm.value.action : 'pass',
      target_url: injected && faultForm.value.action === 'dns_spoofing'
        ? 'http://127.0.0.1:9999/downstream-sink'
        : faultForm.value.requestUrl,
      details: injected
        ? {
            policy_action: faultForm.value.action,
            matched_pattern: faultForm.value.urlPattern,
            status_code: faultForm.value.action === 'http_status' ? 503 : undefined,
          }
        : undefined,
    }
  } finally {
    evaluatingFault.value = false
  }
}
</script>

<style scoped>
.network-resilience-radar {
  padding: 4px 0;
}
.resilience-summary-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 20px;
}
.summary-left {
  display: flex;
  align-items: center;
  gap: 18px;
}
.score-badge {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #ffffff;
  background: #1890ff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}
.score-badge.grade-a {
  background: #52c41a;
  box-shadow: 0 4px 12px rgba(82, 196, 26, 0.3);
}
.score-badge.grade-b {
  background: #1890ff;
}
.score-badge.grade-c {
  background: #fa8c16;
  box-shadow: 0 4px 12px rgba(250, 140, 22, 0.3);
}
.score-badge.grade-d {
  background: #f5222d;
  box-shadow: 0 4px 12px rgba(245, 34, 45, 0.3);
}
.score-val {
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
}
.score-lbl {
  font-size: 10px;
  opacity: 0.9;
  margin-top: 3px;
}
.summary-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rating-tag {
  font-size: 13px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 12px;
  color: #ffffff;
  background: #1890ff;
}
.rating-tag.grade-a {
  background: #52c41a;
}
.rating-tag.grade-b {
  background: #1890ff;
}
.rating-tag.grade-c {
  background: #fa8c16;
}
.rating-tag.grade-d {
  background: #f5222d;
}
.profile-chip {
  font-size: 12px;
  color: var(--c-text-secondary, #4b5563);
  font-weight: 500;
}
.summary-desc {
  font-size: 12px;
  color: var(--c-text-tertiary, #6b7280);
  margin: 0;
}
.summary-stats {
  display: flex;
  gap: 24px;
}
.stat-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.stat-lbl {
  font-size: 11px;
  color: var(--c-text-tertiary, #6b7280);
}
.stat-val {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-text-primary, #111827);
}
.stat-val.has-error {
  color: #cf1322;
}
.content-row {
  margin-top: 10px;
}
.panel-card {
  border-radius: 8px;
  height: 100%;
}
.chart-wrapper {
  height: 320px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.echarts-box {
  width: 100%;
  height: 100%;
}
.fault-result-box {
  margin-top: 16px;
  padding: 12px;
  background: var(--c-bg-page, #f9fafb);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 6px;
}
.fault-status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.action-tag {
  font-size: 12px;
  font-family: monospace;
  color: var(--c-text-secondary, #4b5563);
  margin-left: auto;
}
.fault-details {
  font-size: 12px;
}
.fault-json pre {
  margin: 6px 0 0 0;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  max-height: 120px;
  overflow: auto;
}
</style>
