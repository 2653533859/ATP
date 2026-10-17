<template>
  <a-drawer
    :open="open"
    title="用例依赖 DAG 拓扑图谱与波次执行透视抽屉"
    width="88%"
    placement="right"
    :destroy-on-close="true"
    class="case-dag-topology-drawer"
    @close="handleClose"
  >
    <div class="dag-drawer-container">
      <!-- 顶部综合拓扑指标横幅 -->
      <div class="hero-kpi-bar">
        <div class="kpi-left">
          <div class="speedup-box">
            <span class="speedup-val text-success">
              {{ accelerationRatio.toFixed(1) }}x
            </span>
            <span class="speedup-label">拓扑并发加速比</span>
          </div>

          <div class="meta-details">
            <div class="title-row">
              <span class="dag-id-badge font-mono font-bold text-primary">{{ displayDag?.dag_id || 'dag_active_01' }}</span>
              <a-tag :color="isValidDag ? 'green' : 'red'">
                {{ isValidDag ? 'DAG 有向无环 · 无死锁' : 'CYCLE_DEADLOCK 存在环路' }}
              </a-tag>
              <a-tag color="blue">
                {{ displayWaves.length }} 个独立执行波次 (Waves)
              </a-tag>
            </div>

            <div class="status-pills-row font-mono">
              <span class="pill-item">
                节点总数: <strong class="text-primary">{{ displayDag?.nodes_count || 4 }} 个</strong>
              </span>
              <span class="pill-item">
                依赖边数: <strong class="text-secondary">{{ displayDag?.edges_count || 3 }} 条</strong>
              </span>
              <span class="pill-item">
                关键路径耗时: <strong class="text-success">{{ (displayPlan?.critical_path_duration_seconds || 37.0).toFixed(1) }}s</strong>
              </span>
              <span class="pill-item">
                全串行耗时: <strong class="text-secondary">{{ (displayPlan?.sequential_duration_seconds || 45.0).toFixed(1) }}s</strong>
              </span>
            </div>
          </div>
        </div>

        <div class="kpi-right">
          <a-space>
            <a-button
              type="primary"
              :loading="dispatchingAll"
              @click="handleDispatchAllWaves"
            >
              <template #icon><PlayCircleOutlined /></template>
              一键全波次流水线调度
            </a-button>

            <a-button @click="handleClose">关闭</a-button>
          </a-space>
        </div>
      </div>

      <!-- 死锁警告条 (如果存在环路) -->
      <div v-if="!isValidDag && detectedCycles.length > 0" class="deadlock-alert-card">
        <div class="alert-header text-danger font-bold">
          <WarningOutlined /> 检测到用例循环依赖死锁 (Circular Dependency Deadlock)
        </div>
        <div class="alert-desc text-xs">
          以下节点构成闭环回路，请断开弱数据流边以恢复无环调度:
        </div>
        <div v-for="(cycle, cidx) in detectedCycles" :key="cidx" class="cycle-path font-mono text-xs">
          {{ cycle.join(' ➔ ') }} ➔ {{ cycle[0] }}
        </div>
      </div>

      <!-- 多波次分级执行泳道面板 -->
      <div class="waves-swimlane-section">
        <div class="section-title-row">
          <h4 class="section-title">
            <ApartmentOutlined /> DAG 并发波次分层泳道 (Topological Waves)
          </h4>
          <span class="section-subtext">按照 Kahn 拓扑排序算法分级并发调度，同波次最大并行化，跨波次状态管道注入</span>
        </div>

        <div class="waves-grid">
          <div
            v-for="wave in displayWaves"
            :key="wave.wave_index"
            class="wave-card"
            :class="{ 'terminal-wave': wave.is_terminal }"
          >
            <div class="wave-header">
              <div class="wave-title-group">
                <span class="wave-index-badge font-bold">Wave {{ wave.wave_index }}</span>
                <a-tag color="cyan">并发度 {{ wave.concurrency_level }}</a-tag>
                <a-tag v-if="wave.is_terminal" color="purple">终止收官波次</a-tag>
              </div>

              <div class="wave-actions">
                <span class="wave-time text-xs font-mono">耗时 ~{{ wave.wave_estimated_duration_seconds }}s</span>
                <a-button
                  size="small"
                  type="link"
                  @click="handleDispatchSingleWave(wave.wave_index)"
                >
                  调度波次
                </a-button>
              </div>
            </div>

            <div class="wave-nodes-list">
              <div
                v-for="node in wave.nodes"
                :key="node.case_id"
                class="node-card"
                :class="getNodeStatusClass(getNodeStatus(node.case_id))"
                @click="handleNodeClick(node.case_id)"
              >
                <div class="node-header">
                  <span class="node-name font-bold">{{ node.case_name }}</span>
                  <a-tag :color="getNodeStatusColor(getNodeStatus(node.case_id))">
                    {{ getNodeStatus(node.case_id) }}
                  </a-tag>
                </div>

                <div class="node-id font-mono text-xs text-secondary">
                  {{ node.case_id }} · 耗时 {{ node.estimated_duration_seconds }}s
                </div>

                <!-- 数据变量管道标签 -->
                <div class="variables-strip text-xs font-mono">
                  <div v-if="node.required_variables?.length > 0" class="var-group in-var">
                    <span class="var-label text-warning">[入]</span>
                    <span class="var-names">{{ node.required_variables.join(', ') }}</span>
                  </div>

                  <div v-if="node.produced_variables?.length > 0" class="var-group out-var">
                    <span class="var-label text-success">[出]</span>
                    <span class="var-names">{{ node.produced_variables.join(', ') }}</span>
                  </div>
                </div>

                <!-- 级联跳过原因提示 -->
                <div v-if="getNodeCascadeReason(node.case_id)" class="cascade-reason-box text-xs font-mono">
                  <InfoCircleOutlined /> {{ getNodeCascadeReason(node.case_id) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 数据变量管道传递透视表 -->
      <div class="pipeline-state-section">
        <div class="section-title-row">
          <h4 class="section-title">
            <FieldTimeOutlined /> 跨波次数据流变量管道透视 (State Pipeline Flow)
          </h4>
          <span class="section-subtext">呈现上游用例产出输出变量被下游各波次用例消费注入的拓扑管道流转</span>
        </div>

        <a-table
          :data-source="pipelineVariableRows"
          :columns="pipelineColumns"
          :pagination="false"
          size="middle"
          row-key="variable_name"
          class="pipeline-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'variable_name'">
              <span class="font-mono font-bold text-primary">{{ record.variable_name }}</span>
            </template>
            <template v-else-if="column.key === 'producer_case'">
              <span class="font-mono text-success">{{ record.producer_case }}</span>
            </template>
            <template v-else-if="column.key === 'consumer_cases'">
              <div class="consumers-pill-wrap font-mono">
                <span
                  v-for="cid in record.consumer_cases"
                  :key="cid"
                  class="consumer-tag text-xs"
                >
                  {{ cid }}
                </span>
              </div>
            </template>
            <template v-else-if="column.key === 'sample_value'">
              <span class="font-mono text-secondary text-xs">{{ record.sample_value }}</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlayCircleOutlined,
  WarningOutlined,
  ApartmentOutlined,
  InfoCircleOutlined,
  FieldTimeOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  open: boolean
  dagData?: any
  wavePlan?: any
  faultReport?: any
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'executedWave', waveIndex: number): void
  (e: 'selectedNode', caseId: string): void
}>()

const dispatchingAll = ref(false)

const displayDag = computed(() => {
  return props.dagData || {
    dag_id: 'dag_precision_001',
    is_valid_dag: true,
    nodes_count: 4,
    edges_count: 3,
    cycles: [],
    nodes: {
      case_login: { case_name: '用户登录主流程', produced_variables: ['auth_token'], consumed_variables: [] },
      case_init_config: { case_name: '系统基础配置拉取', produced_variables: ['app_config'], consumed_variables: [] },
      case_create_order: { case_name: '创建收银台订单', produced_variables: ['order_id'], consumed_variables: ['auth_token'] },
      case_pay_order: { case_name: '订单完成支付', produced_variables: ['pay_receipt'], consumed_variables: ['order_id', 'app_config'] },
    },
  }
})

const displayPlan = computed(() => {
  return props.wavePlan || {
    critical_path_duration_seconds: 37.0,
    sequential_duration_seconds: 45.0,
    concurrency_acceleration_ratio: 1.22,
  }
})

const isValidDag = computed(() => {
  return displayDag.value?.is_valid_dag !== false
})

const detectedCycles = computed(() => {
  return displayDag.value?.cycles || []
})

const accelerationRatio = computed(() => {
  return displayPlan.value?.concurrency_acceleration_ratio || 2.5
})

const displayWaves = computed(() => {
  if (props.wavePlan?.waves?.length > 0) {
    return props.wavePlan.waves
  }
  return [
    {
      wave_index: 0,
      concurrency_level: 2,
      wave_estimated_duration_seconds: 10.0,
      is_terminal: false,
      nodes: [
        {
          case_id: 'case_login',
          case_name: '用户登录主流程',
          required_variables: [],
          produced_variables: ['auth_token'],
          estimated_duration_seconds: 10.0,
        },
        {
          case_id: 'case_init_config',
          case_name: '系统基础配置拉取',
          required_variables: [],
          produced_variables: ['app_config'],
          estimated_duration_seconds: 8.0,
        },
      ],
    },
    {
      wave_index: 1,
      concurrency_level: 1,
      wave_estimated_duration_seconds: 12.0,
      is_terminal: false,
      nodes: [
        {
          case_id: 'case_create_order',
          case_name: '创建收银台订单',
          required_variables: ['auth_token'],
          produced_variables: ['order_id'],
          estimated_duration_seconds: 12.0,
        },
      ],
    },
    {
      wave_index: 2,
      concurrency_level: 1,
      wave_estimated_duration_seconds: 15.0,
      is_terminal: true,
      nodes: [
        {
          case_id: 'case_pay_order',
          case_name: '订单完成支付',
          required_variables: ['order_id', 'app_config'],
          produced_variables: ['pay_receipt'],
          estimated_duration_seconds: 15.0,
        },
      ],
    },
  ]
})

const pipelineVariableRows = computed(() => {
  return [
    {
      variable_name: 'auth_token',
      producer_case: 'case_login',
      consumer_cases: ['case_create_order'],
      sample_value: 'val_auth_token_case_login',
    },
    {
      variable_name: 'app_config',
      producer_case: 'case_init_config',
      consumer_cases: ['case_pay_order'],
      sample_value: 'val_app_config_case_init_config',
    },
    {
      variable_name: 'order_id',
      producer_case: 'case_create_order',
      consumer_cases: ['case_pay_order'],
      sample_value: 'val_order_id_case_create_order',
    },
    {
      variable_name: 'pay_receipt',
      producer_case: 'case_pay_order',
      consumer_cases: ['--'],
      sample_value: 'val_pay_receipt_case_pay_order',
    },
  ]
})

const pipelineColumns = [
  { title: '数据流变量名称', key: 'variable_name', width: 200 },
  { title: '生产源用例 (Producer)', key: 'producer_case', width: 220 },
  { title: '消费下游用例集合 (Consumers)', key: 'consumer_cases', width: 260 },
  { title: '当前管道流转模拟取值', key: 'sample_value' },
]

function getNodeStatus(caseId: string): string {
  const records = props.faultReport?.node_records || []
  const match = records.find((r: any) => r.case_id === caseId)
  if (match) return match.status
  return 'SUCCESS'
}

function getNodeCascadeReason(caseId: string): string | null {
  const records = props.faultReport?.node_records || []
  const match = records.find((r: any) => r.case_id === caseId)
  return match?.cascade_skip_reason || null
}

function getNodeStatusColor(status: string) {
  switch (status) {
    case 'SUCCESS':
      return 'green'
    case 'FAILED':
      return 'red'
    case 'CASCADE_SKIPPED':
      return 'orange'
    case 'RUNNING':
      return 'blue'
    default:
      return 'cyan'
  }
}

function getNodeStatusClass(status: string) {
  switch (status) {
    case 'SUCCESS':
      return 'node-success'
    case 'FAILED':
      return 'node-failed'
    case 'CASCADE_SKIPPED':
      return 'node-skipped'
    default:
      return 'node-pending'
  }
}

function handleNodeClick(caseId: string) {
  emit('selectedNode', caseId)
}

function handleDispatchSingleWave(waveIndex: number) {
  emit('executedWave', waveIndex)
  message.success(`已派发波次 Wave ${waveIndex} 并发执行`)
}

async function handleDispatchAllWaves() {
  dispatchingAll.value = true
  try {
    message.success('已启动 DAG 全波次流水线自动并发调度')
    emit('executedWave', -1)
  } finally {
    dispatchingAll.value = false
  }
}

function handleClose() {
  emit('update:open', false)
}
</script>

<style scoped>
.dag-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-kpi-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.kpi-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.speedup-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.speedup-val {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}

.speedup-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  margin-top: 4px;
}

.meta-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dag-id-badge {
  font-size: 15px;
}

.status-pills-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.deadlock-alert-card {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cycle-path {
  color: #b91c1c;
  padding: 4px 8px;
  background: #fee2e2;
  border-radius: 4px;
}

.waves-swimlane-section {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.section-title-row {
  margin-bottom: 14px;
}

.section-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text-primary, #1e293b);
}

.section-subtext {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.waves-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.wave-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  padding: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.terminal-wave {
  border-left: 4px solid #8b5cf6;
}

.wave-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wave-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wave-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wave-nodes-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.node-card {
  padding: 10px 12px;
  border-radius: 6px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.node-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
}

.node-success {
  border-left: 4px solid #10b981;
}

.node-failed {
  border-left: 4px solid #ef4444;
  background: #fef2f2;
}

.node-skipped {
  border-left: 4px solid #f59e0b;
  background: #fffbeb;
}

.node-pending {
  border-left: 4px solid #94a3b8;
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.node-name {
  font-size: 13px;
  color: var(--c-text-primary, #1e293b);
}

.variables-strip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 4px;
  border-top: 1px dashed #e2e8f0;
}

.var-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cascade-reason-box {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  padding: 4px 6px;
  border-radius: 4px;
  border: 1px dashed #fcd34d;
}

.pipeline-state-section {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.consumers-pill-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.consumer-tag {
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  color: #334155;
}

.text-success {
  color: #10b981;
}

.text-warning {
  color: #f59e0b;
}

.text-danger {
  color: #ef4444;
}

.text-primary {
  color: #2563eb;
}

.text-secondary {
  color: var(--c-text-secondary, #64748b);
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: bold;
}

.text-xs {
  font-size: 12px;
}
</style>
