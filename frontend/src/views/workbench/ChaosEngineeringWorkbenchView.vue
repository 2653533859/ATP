<template>
  <div class="page-shell chaos-engineering-workbench-view">
    <!-- 1. 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <FireOutlined class="hero-icon text-danger" />
          <h2 class="page-title">分布式混沌工程与微服务弹性韧性演练工作台中枢</h2>
          <span class="live-dot" />
          <a-tag color="volcano">v5.8.0 混沌攻防引擎在线</a-tag>
        </div>
        <p class="page-subtitle">
          全链路分布式微服务故障注入、动态稳态基线偏离探测、爆炸半径看门狗毫秒级熔断回滚与架构韧性雷达中枢
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" danger @click="openInspectionDrawer(selectedExperiment)">
            <template #icon><ThunderboltOutlined /></template>
            故障注入拓扑透视
          </a-button>

          <a-button @click="openConfigModal">
            <template #icon><SafetyCertificateOutlined /></template>
            安全围栏与看门狗配置
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新演练大盘
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 2. 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">演练稳态守住率</span>
          <CheckCircleOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success">95.8%</span>
          <span class="kpi-trend text-success">零雪崩外溢</span>
        </div>
        <div class="kpi-footer font-mono">
          稳态假说达成: 23 / 24 场次通过
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">平均自愈恢复时间 (RTO)</span>
          <FieldTimeOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary">3.4s</span>
          <span class="kpi-sub text-success">极速自愈收敛</span>
        </div>
        <div class="kpi-footer font-mono">
          SLO 标准门槛: &lt; 15.0s (提升 77.3%)
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-warning">
        <div class="kpi-header">
          <span class="kpi-title">看门狗紧急熔断拦截</span>
          <StopOutlined class="kpi-icon text-warning" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-warning">14 次</span>
          <span class="kpi-trend text-warning">毫秒级强行回滚</span>
        </div>
        <div class="kpi-footer font-mono">
          成功阻断 14 起故障扩散与生产击穿风险
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-purple">
        <div class="kpi-header">
          <span class="kpi-title">架构韧性雷达综合得分</span>
          <RadarChartOutlined class="kpi-icon text-purple" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-purple">91.2 分</span>
          <span class="kpi-badge">卓越级韧性</span>
        </div>
        <div class="kpi-footer font-mono">
          断路器 / 舱壁 / 降级三维全防御联动
        </div>
      </div>
    </div>

    <!-- 3. 混沌演练实验大盘流水表 -->
    <a-card class="experiments-table-card mt-4" title="分布式混沌攻防演练实验大盘 (Active Experiments)">
      <template #extra>
        <a-space>
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="按实验名称 / 微服务过滤..."
            style="width: 240px;"
            size="small"
            @search="handleSearch"
          />
          <a-tag color="blue">当前演练数: {{ filteredExperiments.length }}</a-tag>
        </a-space>
      </template>

      <a-table
        :data-source="filteredExperiments"
        :columns="tableColumns"
        :pagination="false"
        row-key="experiment_id"
        size="middle"
        class="experiments-table font-mono"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'experiment_id'">
            <a class="exp-link font-bold text-primary" @click="openInspectionDrawer(record as any)">
              {{ record.experiment_id }}
            </a>
          </template>

          <template v-else-if="column.key === 'state'">
            <a-tag :color="getStateColor(record.state)">
              {{ getStateText(record.state) }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'fault_types'">
            <a-space size="small">
              <a-tag v-for="ft in record.fault_types" :key="ft" color="orange">
                {{ ft }}
              </a-tag>
            </a-space>
          </template>

          <template v-else-if="column.key === 'p99_latency'">
            <span :class="record.current_p99_ms > record.baseline_hypothesis.max_p99_latency_ms ? 'text-danger font-bold' : 'text-success'">
              {{ record.current_p99_ms }}ms
            </span>
          </template>

          <template v-else-if="column.key === 'rto_seconds'">
            <span class="text-primary font-bold">
              {{ record.rto_seconds ? `${record.rto_seconds}s` : '--' }}
            </span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space size="small">
              <a-button size="small" type="link" @click="openInspectionDrawer(record as any)">
                拓扑透视
              </a-button>
              <a-button size="small" type="link" @click="openConfigModal">
                围栏配置
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 4. 联动组件: 故障注入拓扑抽屉 (UI3.1) -->
    <ChaosExperimentInspectionDrawer
      v-model:open="inspectionDrawerOpen"
      :experiment="selectedExperiment"
      @emergencyAbort="handleEmergencyAbort"
    />

    <!-- 5. 联动组件: 爆炸半径配置弹窗 (UI3.2) -->
    <BlastRadiusConfigModal
      v-model:open="configModalOpen"
      :experiment-id="selectedExperiment?.experiment_id"
      @save="handleSavePolicy"
      @testTriggerAbort="handleTestAbort"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  FireOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  FieldTimeOutlined,
  StopOutlined,
  RadarChartOutlined,
} from '@ant-design/icons-vue'
import ChaosExperimentInspectionDrawer from './components/ChaosExperimentInspectionDrawer.vue'
import BlastRadiusConfigModal, { type BlastRadiusPolicy } from './components/BlastRadiusConfigModal.vue'

interface BaselineHypothesis {
  max_p99_latency_ms: number
  min_success_rate_pct: number
  health_probe_endpoint: string
}

interface ChaosExperimentItem {
  experiment_id: string
  name: string
  target_service: string
  state: string
  fault_types: string[]
  current_p99_ms: number
  rto_seconds: number
  baseline_hypothesis: BaselineHypothesis
}

const loading = ref(false)
const searchKeyword = ref('')
const inspectionDrawerOpen = ref(false)
const configModalOpen = ref(false)

const experimentsList = ref<ChaosExperimentItem[]>([
  {
    experiment_id: 'exp_payment_circuit_breaker',
    name: '核心支付网关高延迟与网络丢包弹性韧性演练',
    target_service: 'payment-service',
    state: 'FAULT_INJECTING',
    fault_types: ['NETWORK_LATENCY', 'PACKET_LOSS'],
    current_p99_ms: 620,
    rto_seconds: 4.2,
    baseline_hypothesis: {
      max_p99_latency_ms: 250.0,
      min_success_rate_pct: 99.0,
      health_probe_endpoint: '/health/ready',
    },
  },
  {
    experiment_id: 'exp_order_db_timeout',
    name: '订单微服务数据库连接池慢调用堆积演练',
    target_service: 'order-service',
    state: 'STEADY_STATE_VERIFIED',
    fault_types: ['TIMEOUT_ABORT'],
    current_p99_ms: 190,
    rto_seconds: 2.8,
    baseline_hypothesis: {
      max_p99_latency_ms: 300.0,
      min_success_rate_pct: 99.5,
      health_probe_endpoint: '/health/db',
    },
  },
  {
    experiment_id: 'exp_inventory_http_mutation',
    name: '库存中心 500 状态码变异与降级缓存接管演练',
    target_service: 'inventory-service',
    state: 'STEADY_STATE_VIOLATED',
    fault_types: ['HTTP_STATUS_MUTATION'],
    current_p99_ms: 850,
    rto_seconds: 6.5,
    baseline_hypothesis: {
      max_p99_latency_ms: 200.0,
      min_success_rate_pct: 99.0,
      health_probe_endpoint: '/health/ready',
    },
  },
  {
    experiment_id: 'exp_user_auth_token_corruption',
    name: '用户认证中心请求载荷脏数据变异防守测试',
    target_service: 'auth-service',
    state: 'STOPPED',
    fault_types: ['PAYLOAD_CORRUPTION'],
    current_p99_ms: 140,
    rto_seconds: 1.5,
    baseline_hypothesis: {
      max_p99_latency_ms: 200.0,
      min_success_rate_pct: 99.9,
      health_probe_endpoint: '/health/auth',
    },
  },
])

const selectedExperiment = ref<ChaosExperimentItem>(experimentsList.value[0])

const tableColumns = [
  { title: '演练实验编码', dataIndex: 'experiment_id', key: 'experiment_id', width: 220 },
  { title: '演练实验名称', dataIndex: 'name', key: 'name' },
  { title: '目标微服务', dataIndex: 'target_service', key: 'target_service', width: 160 },
  { title: '演练状态', dataIndex: 'state', key: 'state', width: 140 },
  { title: '生效算子', dataIndex: 'fault_types', key: 'fault_types', width: 220 },
  { title: '实时 P99 延迟', key: 'p99_latency', width: 130 },
  { title: '自愈耗时 (RTO)', key: 'rto_seconds', width: 130 },
  { title: '快捷操作', key: 'actions', width: 160 },
]

const filteredExperiments = computed(() => {
  if (!searchKeyword.value.trim()) return experimentsList.value
  const kw = searchKeyword.value.trim().toLowerCase()
  return experimentsList.value.filter(
    (exp) =>
      exp.experiment_id.toLowerCase().includes(kw) ||
      exp.name.toLowerCase().includes(kw) ||
      exp.target_service.toLowerCase().includes(kw)
  )
})

function getStateColor(state: string): string {
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

function getStateText(state: string): string {
  const map: Record<string, string> = {
    CREATED: '已就绪',
    BASELINE_STABILIZING: '基线稳定中',
    FAULT_INJECTING: '故障注入中',
    STEADY_STATE_VERIFIED: '稳态假说达成',
    STEADY_STATE_VIOLATED: '稳态击穿告警',
    STOPPED: '已终止',
  }
  return map[state] || state
}

function openInspectionDrawer(exp?: any) {
  if (exp) {
    selectedExperiment.value = exp
  }
  inspectionDrawerOpen.value = true
}

function openConfigModal() {
  configModalOpen.value = true
}

function fetchData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 400)
}

function handleSearch() {
  // filteredExperiments handles search dynamically
}

function handleEmergencyAbort(expId: string) {
  const target = experimentsList.value.find((e) => e.experiment_id === expId)
  if (target) {
    target.state = 'STOPPED'
  }
}

function handleSavePolicy(_policy: BlastRadiusPolicy) {
  // policy saved notification / state
}

function handleTestAbort(expId: string) {
  handleEmergencyAbort(expId)
}
</script>

<style scoped>
.chaos-engineering-workbench-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 18px 24px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 22px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text);
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--c-text-secondary);
}

.bento-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4, 16px);
}

.bento-card {
  padding: 16px 20px;
  border-radius: var(--radius-md, 8px);
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  box-shadow: var(--shadow-xs);
  min-height: 104px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.bento-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
  border-color: var(--c-primary);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text-secondary);
}

.kpi-icon {
  font-size: 18px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 10px 0 6px;
}

.kpi-number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
  color: var(--c-text);
}

.kpi-trend,
.kpi-sub {
  font-size: 11px;
  font-family: var(--font-mono, monospace);
}

.kpi-badge {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--c-ai-soft);
  border: 1px solid var(--c-ai);
  color: var(--c-ai);
  border-radius: var(--radius-xs, 4px);
  font-family: var(--font-mono, monospace);
  font-weight: 600;
}

.kpi-footer {
  font-size: 11px;
  color: var(--c-text-tertiary);
  border-top: 1px dashed var(--c-border-subtle, var(--c-border));
  padding-top: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mt-4 {
  margin-top: 16px;
}

.text-danger {
  color: var(--c-error);
}

.text-success {
  color: var(--c-success);
}

.text-warning {
  color: var(--c-warning);
}

.text-primary {
  color: var(--c-primary);
}

.text-purple {
  color: var(--c-ai);
}

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1024px) {
  .bento-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 640px) {
  .bento-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
