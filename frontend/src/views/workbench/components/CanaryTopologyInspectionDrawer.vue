<template>
  <a-drawer
    :open="open"
    title="全链路金丝雀染色拓扑与双轨流量分流透视抽屉"
    width="86%"
    placement="right"
    :destroy-on-close="true"
    class="canary-topology-inspection-drawer"
    @close="handleClose"
  >
    <div class="drawer-container">
      <!-- 1. 顶部金丝雀服务横幅 -->
      <div class="canary-hero-bar">
        <div class="hero-left">
          <div class="title-row">
            <CloudServerOutlined class="hero-icon text-primary" />
            <span class="service-title font-bold">{{ targetService || 'payment-service' }}</span>
            <a-tag color="processing" class="font-mono">
              灰度版本: {{ canaryVersion || 'v1.2.0-canary' }}
            </a-tag>
            <a-tag color="default" class="font-mono">
              基线版本: {{ baselineVersion || 'v1.0.0' }}
            </a-tag>
            <a-tag :color="isPollutionDetected ? 'error' : 'success'" class="font-mono">
              影子隔离: {{ isPollutionDetected ? 'CRITICAL_LEAK 污染泄漏' : '100% CLEAN 合规' }}
            </a-tag>
          </div>

          <div class="hero-summary-pills font-mono">
            <span class="metric-pill">
              当前灰度权重: <strong class="text-primary">{{ currentWeightPct }}%</strong>
            </span>
            <span class="metric-pill">
              基线流量权重: <strong class="text-secondary">{{ 100 - currentWeightPct }}%</strong>
            </span>
            <span class="metric-pill">
              五维健康得分: <strong class="text-success">{{ healthScore }} 分 (EXCELLENT)</strong>
            </span>
            <span class="metric-pill">
              双轨偏离裁决: <strong class="text-success">{{ overallVerdict }}</strong>
            </span>
          </div>
        </div>

        <div class="hero-actions">
          <a-space>
            <a-button :loading="refreshing" @click="handleRefresh">
              <template #icon><ReloadOutlined /></template>
              刷新指标
            </a-button>
            <a-popconfirm
              title="确定立即执行紧急切流回滚吗？将瞬间清空灰度权重(0%)并切断染色流量！"
              ok-text="确认熔断回滚"
              cancel-text="取消"
              ok-type="danger"
              @confirm="handleTriggerRollback"
            >
              <a-button type="primary" danger :loading="rollingBack">
                <template #icon><ThunderboltOutlined /></template>
                一键紧急切流回滚
              </a-button>
            </a-popconfirm>
          </a-space>
        </div>
      </div>

      <!-- 2. 全链路微服务分流与染色流向拓扑看板 -->
      <div class="topology-panel">
        <div class="panel-header">
          <span class="panel-title font-bold">
            <BranchesOutlined class="mr-1 text-primary" />
            微服务全链路分流拓扑与双轨调用链路
          </span>
          <span class="panel-tip text-xs text-secondary">
            染色规则: HTTP Header [X-Canary-Traffic: true] / W3C Baggage [canary_beta=1]
          </span>
        </div>

        <div class="topology-grid">
          <!-- 节点 1: 流量入口网关 -->
          <div class="topology-node ingress-node">
            <div class="node-badge">Ingress Gateway</div>
            <div class="node-title font-bold">API 网关分流器</div>
            <div class="node-desc text-xs text-secondary">染色判定 & 权重比例切分</div>
            <div class="traffic-meter mt-2">
              <div class="meter-bar-base" :style="{ width: `${100 - currentWeightPct}%` }">
                基线 {{ 100 - currentWeightPct }}%
              </div>
              <div class="meter-bar-canary" :style="{ width: `${currentWeightPct}%` }">
                灰度 {{ currentWeightPct }}%
              </div>
            </div>
          </div>

          <div class="topology-arrow">
            <ArrowRightOutlined class="arrow-icon" />
          </div>

          <!-- 节点 2: 双轨微服务执行集群 -->
          <div class="topology-node cluster-node">
            <div class="node-badge">Dual-Track Pods</div>
            <div class="node-title font-bold">{{ targetService || 'payment-service' }} 集群</div>
            <div class="dual-instances mt-2 font-mono text-xs">
              <div class="instance-row baseline-row">
                <span class="status-dot dot-base"></span>
                <span>基线集群 ({{ baselineVersion || 'v1.0.0' }}): 8 个 Pods</span>
              </div>
              <div class="instance-row canary-row">
                <span class="status-dot dot-canary"></span>
                <span>金丝雀集群 ({{ canaryVersion || 'v1.2.0-canary' }}): 2 个 Pods</span>
              </div>
            </div>
          </div>

          <div class="topology-arrow">
            <ArrowRightOutlined class="arrow-icon" />
          </div>

          <!-- 节点 3: 影子存储与数据隔离层 -->
          <div class="topology-node storage-node">
            <div class="node-badge">Storage Layer</div>
            <div class="node-title font-bold">数据库与消息队列</div>
            <div class="dual-storage mt-2 font-mono text-xs">
              <div class="storage-item base-storage">
                <DatabaseOutlined class="mr-1 text-secondary" />
                <span>生产真实主库 (t_order)</span>
              </div>
              <div class="storage-item canary-storage">
                <DatabaseOutlined class="mr-1 text-success" />
                <span class="text-success font-bold">影子测试库 (t_order_shadow)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. 双轨实时指标与偏离度看板 (Bento 风格卡片网格) -->
      <div class="metrics-panel mt-4">
        <div class="panel-header">
          <span class="panel-title font-bold">
            <ApartmentOutlined class="mr-1 text-primary" />
            金丝雀 vs 基线 双轨实时核心指标对比 (Dual-Track Metric Comparator)
          </span>
        </div>

        <div class="metrics-grid">
          <!-- 卡片 1: 错误率对比 -->
          <div class="metric-card">
            <div class="card-label text-secondary font-mono">请求错误率 (Error Rate)</div>
            <div class="card-diff font-bold" :class="errorDiffClass">
              差值: {{ formatSigned(errorRateDiff) }}%
            </div>
            <div class="dual-val-row font-mono text-xs mt-2">
              <span>基线: {{ baselineErrorRate }}%</span>
              <span class="text-primary">金丝雀: {{ canaryErrorRate }}%</span>
            </div>
          </div>

          <!-- 卡片 2: P99 响应时延 -->
          <div class="metric-card">
            <div class="card-label text-secondary font-mono">P99 响应延迟 (P99 Latency)</div>
            <div class="card-diff font-bold" :class="latencyRatioClass">
              倍率: {{ latencyRatio.toFixed(2) }}x
            </div>
            <div class="dual-val-row font-mono text-xs mt-2">
              <span>基线: {{ baselineP99 }} ms</span>
              <span class="text-primary">金丝雀: {{ canaryP99 }} ms</span>
            </div>
          </div>

          <!-- 卡片 3: 业务成功率 -->
          <div class="metric-card">
            <div class="card-label text-secondary font-mono">业务交易成功率 (Success Rate)</div>
            <div class="card-diff font-bold text-success">
              {{ canarySuccessRate }}%
            </div>
            <div class="dual-val-row font-mono text-xs mt-2">
              <span>基线: {{ baselineSuccessRate }}%</span>
              <span class="text-secondary">保底底线: 95.0%</span>
            </div>
          </div>

          <!-- 卡片 4: 影子隔离合规率 -->
          <div class="metric-card">
            <div class="card-label text-secondary font-mono">影子存储隔离防污染率</div>
            <div class="card-diff font-bold" :class="isPollutionDetected ? 'text-danger' : 'text-success'">
              {{ isolationCompliancePct }}%
            </div>
            <div class="dual-val-row font-mono text-xs mt-2">
              <span>已路由影子: {{ shadowRoutedCount }} 次</span>
              <span :class="isPollutionDetected ? 'text-danger font-bold' : 'text-secondary'">
                穿透主表: {{ leakedWritesCount }} 次
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  CloudServerOutlined,
  BranchesOutlined,
  ApartmentOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  ArrowRightOutlined,
  DatabaseOutlined,
} from '@ant-design/icons-vue'

export interface DualTrackMetricsData {
  error_rate_diff_pct?: number
  latency_p99_ratio?: number
  baseline_error_rate?: number
  canary_error_rate?: number
  baseline_p99_ms?: number
  canary_p99_ms?: number
  baseline_success_rate?: number
  canary_success_rate?: number
  overall_verdict?: string
}

export interface IsolationStatusData {
  isolation_compliance_pct?: number
  is_pollution_detected?: boolean
  shadow_routed_count?: number
  leaked_master_writes_count?: number
}

const props = withDefaults(
  defineProps<{
    open: boolean
    targetService?: string
    canaryVersion?: string
    baselineVersion?: string
    currentWeightPct?: number
    healthScore?: number
    metrics?: DualTrackMetricsData | null
    isolation?: IsolationStatusData | null
  }>(),
  {
    open: false,
    targetService: 'payment-service',
    canaryVersion: 'v1.2.0-canary',
    baselineVersion: 'v1.0.0',
    currentWeightPct: 15.0,
    healthScore: 92.5,
    metrics: null,
    isolation: null,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'rollback', service: string): void
  (e: 'refresh', service: string): void
}>()

const refreshing = ref(false)
const rollingBack = ref(false)

const overallVerdict = computed(() => props.metrics?.overall_verdict || 'CONFORMANT')
const errorRateDiff = computed(() => props.metrics?.error_rate_diff_pct ?? 0.1)
const baselineErrorRate = computed(() => props.metrics?.baseline_error_rate ?? 0.1)
const canaryErrorRate = computed(() => props.metrics?.canary_error_rate ?? 0.2)
const latencyRatio = computed(() => props.metrics?.latency_p99_ratio ?? 1.05)
const baselineP99 = computed(() => props.metrics?.baseline_p99_ms ?? 105)
const canaryP99 = computed(() => props.metrics?.canary_p99_ms ?? 110)
const baselineSuccessRate = computed(() => props.metrics?.baseline_success_rate ?? 99.9)
const canarySuccessRate = computed(() => props.metrics?.canary_success_rate ?? 99.8)

const isolationCompliancePct = computed(() => props.isolation?.isolation_compliance_pct ?? 100.0)
const isPollutionDetected = computed(() => props.isolation?.is_pollution_detected ?? false)
const shadowRoutedCount = computed(() => props.isolation?.shadow_routed_count ?? 42)
const leakedWritesCount = computed(() => props.isolation?.leaked_master_writes_count ?? 0)

const errorDiffClass = computed(() => {
  if (errorRateDiff.value > 2.0) return 'text-danger'
  if (errorRateDiff.value > 0.5) return 'text-warning'
  return 'text-success'
})

const latencyRatioClass = computed(() => {
  if (latencyRatio.value > 1.5) return 'text-danger'
  if (latencyRatio.value > 1.25) return 'text-warning'
  return 'text-success'
})

function formatSigned(val: number): string {
  return val >= 0 ? `+${val.toFixed(2)}` : val.toFixed(2)
}

function handleClose() {
  emit('update:open', false)
}

function handleRefresh() {
  refreshing.value = true
  emit('refresh', props.targetService)
  setTimeout(() => {
    refreshing.value = false
  }, 400)
}

function handleTriggerRollback() {
  rollingBack.value = true
  emit('rollback', props.targetService)
  setTimeout(() => {
    rollingBack.value = false
  }, 400)
}
</script>

<style scoped>
.drawer-container {
  padding: 8px 0;
}

.canary-hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  margin-bottom: var(--space-4, 16px);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.hero-icon {
  font-size: 20px;
}

.service-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text);
}

.hero-summary-pills {
  display: flex;
  gap: 16px;
  font-size: 13px;
}

.metric-pill {
  color: var(--c-text-secondary);
}

.topology-panel {
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  margin-bottom: var(--space-4, 16px);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
}

.topology-grid {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.topology-node {
  flex: 1;
  padding: 14px;
  background: var(--c-bg-elevated, var(--c-surface));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm, 6px);
  position: relative;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.topology-node:hover {
  border-color: var(--c-primary);
  box-shadow: var(--shadow-subtle);
}

.node-badge {
  font-size: 10px;
  font-family: var(--font-mono, monospace);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  padding: 2px 6px;
  border-radius: var(--radius-xs, 4px);
  display: inline-block;
  margin-bottom: 6px;
  font-weight: 600;
}

.node-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 2px;
}

.traffic-meter {
  display: flex;
  height: 22px;
  border-radius: var(--radius-xs, 4px);
  overflow: hidden;
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  text-align: center;
  line-height: 22px;
  color: #ffffff;
}

.meter-bar-base {
  background: var(--c-text-tertiary);
}

.meter-bar-canary {
  background: var(--c-primary);
}

.topology-arrow {
  display: flex;
  align-items: center;
  color: var(--c-text-tertiary);
  font-size: 18px;
}

.instance-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-base {
  background: var(--c-text-tertiary);
}

.dot-canary {
  background: var(--c-primary);
}

.storage-item {
  display: flex;
  align-items: center;
  margin-top: 4px;
}

.metrics-panel {
  padding: 16px 20px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.metric-card {
  padding: 14px;
  background: var(--c-bg-elevated, var(--c-surface));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm, 6px);
  transition: border-color 0.2s ease;
}

.metric-card:hover {
  border-color: var(--c-primary);
}

.card-label {
  font-size: 12px;
  color: var(--c-text-secondary);
  margin-bottom: 6px;
}

.card-diff {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}

.dual-val-row {
  display: flex;
  justify-content: space-between;
  border-top: 1px dashed var(--c-border-subtle, var(--c-border));
  padding-top: 6px;
}

.text-primary {
  color: var(--c-primary);
}

.text-secondary {
  color: var(--c-text-secondary);
}

.text-success {
  color: var(--c-success);
}

.text-warning {
  color: var(--c-warning);
}

.text-danger {
  color: var(--c-error);
}

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}
</style>
