<template>
  <a-drawer
    :open="open"
    title="分布式混沌故障注入拓扑与稳态指标透视抽屉"
    width="86%"
    placement="right"
    :destroy-on-close="true"
    class="chaos-experiment-inspection-drawer"
    @close="handleClose"
  >
    <div class="chaos-drawer-content">
      <!-- 1. 顶部演练状态与 KPI 横幅 -->
      <div class="chaos-hero-bar">
        <div class="hero-left">
          <div class="experiment-badge">
            <span class="exp-id font-mono text-primary font-bold">
              {{ displayExperiment.experiment_id }}
            </span>
            <a-tag :color="getStatusTagColor(displayExperiment.state)">
              {{ getStatusLabel(displayExperiment.state) }}
            </a-tag>
            <a-tag color="purple" class="font-mono">
              目标: {{ displayExperiment.target_service }}
            </a-tag>
          </div>
          <div class="hero-summary-metrics font-mono">
            <span class="metric-pill">
              P99 延迟:
              <strong :class="p99Exceeded ? 'text-danger' : 'text-success'">
                {{ currentP99Ms }}ms
              </strong>
              <small class="muted-text"> (基线: {{ displayExperiment.baseline_hypothesis.max_p99_latency_ms }}ms)</small>
            </span>
            <span class="metric-pill">
              业务成功率:
              <strong :class="successRateBreached ? 'text-danger' : 'text-success'">
                {{ currentSuccessRate }}%
              </strong>
              <small class="muted-text"> (基线: ≥{{ displayExperiment.baseline_hypothesis.min_success_rate_pct }}%)</small>
            </span>
            <span class="metric-pill">
              熔断器状态:
              <strong :class="circuitOpen ? 'text-warning' : 'text-primary'">
                {{ circuitOpen ? 'OPEN (已跳闸)' : 'CLOSED (正常)' }}
              </strong>
            </span>
            <span class="metric-pill">
              降级接管率:
              <strong class="text-primary font-bold">{{ fallbackTakeoverRate }}%</strong>
            </span>
          </div>
        </div>

        <div class="hero-actions">
          <a-space>
            <a-button
              type="primary"
              danger
              :loading="aborting"
              class="abort-btn"
              @click="handleEmergencyAbort"
            >
              <template #icon><StopOutlined /></template>
              一键紧急熔断恢复 (Abort)
            </a-button>

            <a-button
              type="primary"
              :loading="injecting"
              @click="handleToggleInjection"
            >
              <template #icon>
                <PlayCircleOutlined v-if="displayExperiment.state !== 'FAULT_INJECTING'" />
                <PauseCircleOutlined v-else />
              </template>
              {{ displayExperiment.state === 'FAULT_INJECTING' ? '暂停故障注入' : '开始故障注入' }}
            </a-button>

            <a-button @click="handleClose">关闭</a-button>
          </a-space>
        </div>
      </div>

      <!-- 2. 服务调用拓扑流向与爆炸半径图谱 -->
      <a-card class="topology-card" title="实时服务拓扑流向与故障爆炸波及全景图">
        <template #extra>
          <a-tag color="blue">实时监控拓扑: 4 节点 3 链路</a-tag>
        </template>
        <div class="topology-canvas">
          <div class="topology-node node-client">
            <div class="node-icon"><ApartmentOutlined /></div>
            <div class="node-name">用户客户端 / Web App</div>
            <div class="node-sub">流量入口</div>
            <div class="node-stat font-mono">QPS: 1,420</div>
          </div>

          <div class="topology-arrow">
            <span class="arrow-line"></span>
            <span class="arrow-text font-mono">REST / gRPC</span>
            <span class="arrow-triangle">▶</span>
          </div>

          <div class="topology-node node-gateway">
            <div class="node-icon"><ApartmentOutlined /></div>
            <div class="node-name">api-gateway</div>
            <div class="node-sub">微服务路由网关</div>
            <div class="node-stat font-mono">限流阈值: 3000</div>
          </div>

          <div class="topology-arrow">
            <span class="arrow-line" :class="{ 'arrow-fault': displayExperiment.state === 'FAULT_INJECTING' }"></span>
            <span class="arrow-text font-mono text-danger">注入攻击面</span>
            <span class="arrow-triangle">▶</span>
          </div>

          <div class="topology-node node-target" :class="{ 'node-injected': displayExperiment.state === 'FAULT_INJECTING' }">
            <div class="target-indicator">
              <span class="live-dot live-dot-danger" v-if="displayExperiment.state === 'FAULT_INJECTING'"></span>
              <span>故障目标</span>
            </div>
            <div class="node-icon text-danger"><FireOutlined /></div>
            <div class="node-name font-bold">{{ displayExperiment.target_service }}</div>
            <div class="node-sub font-mono">状态: {{ displayExperiment.state }}</div>
            <div class="node-stat font-mono text-danger">
              {{ activeFaultsCount }} 个算子生效中
            </div>
          </div>

          <div class="topology-arrow">
            <span class="arrow-line"></span>
            <span class="arrow-text font-mono">降级保底链路</span>
            <span class="arrow-triangle">▶</span>
          </div>

          <div class="topology-node node-fallback">
            <div class="node-icon text-success"><SafetyCertificateOutlined /></div>
            <div class="node-name">redis-cache / 旁路</div>
            <div class="node-sub">只读快照降级</div>
            <div class="node-stat font-mono text-success">接管: {{ fallbackTakeoverRate }}%</div>
          </div>
        </div>
      </a-card>

      <!-- 3. 双栏栅格: 故障算子配置列表 + 稳态偏离实时监测 -->
      <a-row :gutter="[16, 16]" class="mt-4">
        <a-col :xs="24" :lg="13">
          <a-card class="fault-rules-card" title="生效故障算子配置 (Active Fault Rules)">
            <template #extra>
              <a-tag color="red">{{ rulesList.length }} 个规则已装配</a-tag>
            </template>
            <a-table
              :data-source="rulesList"
              :columns="ruleColumns"
              :pagination="false"
              row-key="rule_id"
              size="small"
              class="fault-rules-table font-mono"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'fault_type'">
                  <a-tag :color="getFaultTypeColor(record.fault_type)">
                    {{ record.fault_type }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'target_pattern'">
                  <span class="font-mono text-primary">{{ record.target_pattern }}</span>
                </template>
                <template v-else-if="column.key === 'params'">
                  <span>{{ formatFaultParams(record.config) }}</span>
                </template>
                <template v-else-if="column.key === 'is_enabled'">
                  <a-switch
                    :checked="record.is_enabled"
                    size="small"
                    @change="(val: any) => handleToggleRule(record.rule_id, Boolean(val))"
                  />
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>

        <a-col :xs="24" :lg="11">
          <a-card class="steady-eval-card" title="稳态指标偏离判定 (Steady-State Verification)">
            <template #extra>
              <a-tag :color="steadyCompliant ? 'green' : 'red'">
                {{ steadyCompliant ? '稳态假说成立' : '稳态指标偏离击穿' }}
              </a-tag>
            </template>
            <div class="steady-items-container">
              <div class="steady-row">
                <span class="steady-label">P99 延迟偏离:</span>
                <span class="steady-val font-mono" :class="p99Exceeded ? 'text-danger' : 'text-success'">
                  {{ currentP99Ms }}ms
                  <small>({{ p99Exceeded ? '↑ 超标' : '正常' }} / 阈值 {{ displayExperiment.baseline_hypothesis.max_p99_latency_ms }}ms)</small>
                </span>
              </div>
              <div class="steady-row">
                <span class="steady-label">业务错误率偏离:</span>
                <span class="steady-val font-mono" :class="currentErrorRate > 5.0 ? 'text-danger' : 'text-success'">
                  {{ currentErrorRate }}%
                  <small>({{ currentErrorRate > 5.0 ? '↑ 击穿' : '正常' }} / 红线 5.0%)</small>
                </span>
              </div>
              <div class="steady-row">
                <span class="steady-label">探针健康检查:</span>
                <span class="steady-val font-mono text-success">
                  {{ displayExperiment.baseline_hypothesis.health_probe_endpoint }} · 200 OK
                </span>
              </div>
              <div class="steady-row">
                <span class="steady-label">断路器自愈时间 (RTO):</span>
                <span class="steady-val font-mono text-primary font-bold">
                  {{ (displayExperiment.rto_seconds || 4.2).toFixed(1) }}s (SLO: &lt; 15.0s)
                </span>
              </div>
            </div>

            <a-divider style="margin: 12px 0;" />
            <div class="radar-summary-box">
              <span class="font-bold">架构韧性建议: </span>
              <span class="text-secondary">
                {{ p99Exceeded ? '断路器超时判定阈值设置偏高，建议缩减滑动窗口；已就绪降级快照接管。' : '系统弹性表现稳健，故障波及被有效隔离在目标微服务内部。' }}
              </span>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  StopOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  ApartmentOutlined,
  FireOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons-vue'

interface BaselineHypothesis {
  max_p99_latency_ms: number
  min_success_rate_pct: number
  health_probe_endpoint: string
}

interface FaultConfig {
  latency_ms?: number
  jitter_ms?: number
  packet_loss_rate?: number
  status_code?: number
}

interface FaultRule {
  rule_id: string
  fault_type: string
  target_service: string
  target_pattern: string
  config: FaultConfig
  is_enabled: boolean
}

interface ChaosExperiment {
  experiment_id: string
  name: string
  target_service: string
  state: string
  baseline_hypothesis: BaselineHypothesis
  rto_seconds?: number
}

const props = withDefaults(
  defineProps<{
    open: boolean
    experiment?: ChaosExperiment | null
    rules?: FaultRule[]
  }>(),
  {
    open: false,
    experiment: null,
    rules: () => [],
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
  (e: 'emergencyAbort', experimentId: string): void
  (e: 'toggleInjection', experimentId: string, willInject: boolean): void
  (e: 'toggleRule', ruleId: string, enabled: boolean): void
}>()

const aborting = ref(false)
const injecting = ref(false)

const defaultExperiment: ChaosExperiment = {
  experiment_id: 'exp_payment_circuit_breaker',
  name: '核心支付网关高延迟与网络丢包弹性韧性演练',
  target_service: 'payment-service',
  state: 'FAULT_INJECTING',
  baseline_hypothesis: {
    max_p99_latency_ms: 250.0,
    min_success_rate_pct: 99.0,
    health_probe_endpoint: '/health/ready',
  },
  rto_seconds: 4.2,
}

const defaultRules: FaultRule[] = [
  {
    rule_id: 'rule_net_delay_01',
    fault_type: 'NETWORK_LATENCY',
    target_service: 'payment-service',
    target_pattern: '/api/v1/payment/*',
    config: { latency_ms: 500, jitter_ms: 100 },
    is_enabled: true,
  },
  {
    rule_id: 'rule_packet_loss_02',
    fault_type: 'PACKET_LOSS',
    target_service: 'payment-service',
    target_pattern: '/api/v1/payment/checkout',
    config: { packet_loss_rate: 0.15 },
    is_enabled: true,
  },
  {
    rule_id: 'rule_status_500',
    fault_type: 'HTTP_STATUS_MUTATION',
    target_service: 'payment-service',
    target_pattern: '/api/v1/payment/refund',
    config: { status_code: 500 },
    is_enabled: false,
  },
]

const displayExperiment = computed(() => props.experiment || defaultExperiment)
const rulesList = ref<FaultRule[]>(props.rules && props.rules.length ? props.rules : defaultRules)

const ruleColumns = [
  { title: '算子类型', dataIndex: 'fault_type', key: 'fault_type', width: 140 },
  { title: '拦截路径', dataIndex: 'target_pattern', key: 'target_pattern', width: 180 },
  { title: '注入参数', key: 'params' },
  { title: '启停', key: 'is_enabled', width: 70 },
]

const activeFaultsCount = computed(() => rulesList.value.filter(r => r.is_enabled).length)
const currentP99Ms = computed(() => (displayExperiment.value.state === 'FAULT_INJECTING' ? 620 : 180))
const currentSuccessRate = computed(() => (displayExperiment.value.state === 'FAULT_INJECTING' ? 92.5 : 99.8))
const currentErrorRate = computed(() => (displayExperiment.value.state === 'FAULT_INJECTING' ? 7.5 : 0.2))
const p99Exceeded = computed(() => currentP99Ms.value > displayExperiment.value.baseline_hypothesis.max_p99_latency_ms)
const successRateBreached = computed(() => currentSuccessRate.value < displayExperiment.value.baseline_hypothesis.min_success_rate_pct)
const circuitOpen = computed(() => displayExperiment.value.state === 'FAULT_INJECTING')
const fallbackTakeoverRate = computed(() => (displayExperiment.value.state === 'FAULT_INJECTING' ? 94.5 : 100.0))
const steadyCompliant = computed(() => !p99Exceeded.value && !successRateBreached.value)

function getStatusLabel(state: string): string {
  const map: Record<string, string> = {
    CREATED: '已创建',
    BASELINE_STABILIZING: '基线稳定中',
    FAULT_INJECTING: '故障注入中',
    STEADY_STATE_VERIFIED: '稳态验证通过',
    STEADY_STATE_VIOLATED: '稳态击穿告警',
    STOPPED: '已终止',
  }
  return map[state] || state
}

function getStatusTagColor(state: string): string {
  const map: Record<string, string> = {
    CREATED: 'default',
    BASELINE_STABILIZING: 'blue',
    FAULT_INJECTING: 'orange',
    STEADY_STATE_VERIFIED: 'green',
    STEADY_STATE_VIOLATED: 'red',
    STOPPED: 'gray',
  }
  return map[state] || 'blue'
}

function getFaultTypeColor(ft: string): string {
  const map: Record<string, string> = {
    NETWORK_LATENCY: 'orange',
    PACKET_LOSS: 'red',
    HTTP_STATUS_MUTATION: 'volcano',
    TIMEOUT_ABORT: 'purple',
    PAYLOAD_CORRUPTION: 'magenta',
  }
  return map[ft] || 'blue'
}

function formatFaultParams(cfg: FaultConfig): string {
  const parts: string[] = []
  if (cfg.latency_ms !== undefined) parts.push(`延迟: ${cfg.latency_ms}ms (±${cfg.jitter_ms || 0}ms)`)
  if (cfg.packet_loss_rate !== undefined) parts.push(`丢包率: ${(cfg.packet_loss_rate * 100).toFixed(0)}%`)
  if (cfg.status_code !== undefined) parts.push(`状态码: ${cfg.status_code}`)
  return parts.join(' | ') || '默认故障参数'
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

function handleEmergencyAbort() {
  aborting.value = true
  emit('emergencyAbort', displayExperiment.value.experiment_id)
  setTimeout(() => {
    aborting.value = false
    displayExperiment.value.state = 'STOPPED'
  }, 400)
}

function handleToggleInjection() {
  injecting.value = true
  const willInject = displayExperiment.value.state !== 'FAULT_INJECTING'
  emit('toggleInjection', displayExperiment.value.experiment_id, willInject)
  setTimeout(() => {
    injecting.value = false
    displayExperiment.value.state = willInject ? 'FAULT_INJECTING' : 'STOPPED'
  }, 300)
}

function handleToggleRule(ruleId: string, val: boolean) {
  const target = rulesList.value.find(r => r.rule_id === ruleId)
  if (target) {
    target.is_enabled = val
  }
  emit('toggleRule', ruleId, val)
}
</script>

<style scoped>
.chaos-drawer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chaos-hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px;
  background: var(--c-bg-subtle, #fafafa);
  border: 1px solid var(--c-border, #f0f0f0);
  border-radius: 8px;
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.experiment-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
}

.hero-summary-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
}

.metric-pill {
  padding: 4px 8px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e8e8e8);
  border-radius: 4px;
}

.topology-canvas {
  display: flex;
  align-items: center;
  justify-content: space-around;
  flex-wrap: wrap;
  gap: 12px;
  padding: 24px 12px;
  background: var(--c-bg-surface, #ffffff);
  min-height: 140px;
}

.topology-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 170px;
  padding: 12px 8px;
  border: 1px solid var(--c-border, #e8e8e8);
  border-radius: 8px;
  background: var(--c-bg-subtle, #fcfcfc);
  transition: all 0.2s ease;
}

.topology-node:hover {
  border-color: var(--c-primary, #1677ff);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.node-injected {
  border-color: #ff4d4f !important;
  background: #fff1f0 !important;
}

.target-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #ff4d4f;
  margin-bottom: 2px;
}

.node-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.node-name {
  font-size: 13px;
  text-align: center;
}

.node-sub {
  font-size: 11px;
  color: var(--c-text-secondary, #666);
}

.node-stat {
  font-size: 11px;
  margin-top: 4px;
}

.topology-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
}

.arrow-line {
  display: block;
  width: 48px;
  height: 2px;
  background: var(--c-border-strong, #ccc);
}

.arrow-fault {
  background: #ff4d4f !important;
  height: 3px !important;
}

.arrow-text {
  font-size: 10px;
}

.arrow-triangle {
  font-size: 10px;
  color: var(--c-text-secondary, #888);
}

.steady-items-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.steady-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.radar-summary-box {
  font-size: 12px;
  line-height: 1.6;
}

.mt-4 {
  margin-top: 16px;
}

.text-danger {
  color: #ff4d4f;
}

.text-success {
  color: #52c41a;
}

.text-warning {
  color: #faad14;
}

.text-primary {
  color: #1677ff;
}

.text-secondary {
  color: var(--c-text-secondary, #666);
}
</style>
