<template>
  <a-modal
    :open="open"
    :width="1080"
    title="动态多目标加权调度拓扑与队列模拟中枢"
    :footer="null"
    destroy-on-close
    class="scheduler-topology-modal"
    @cancel="handleClose"
  >
    <div class="scheduler-modal-body">
      <!-- 头部说明横幅 -->
      <div class="modal-banner">
        <div class="banner-title">
          <ApartmentOutlined class="banner-icon" />
          <span>Dynamic Concurrency Router & Topology Simulator</span>
          <a-tag color="processing">v5.4.0 Engine</a-tag>
        </div>
        <p class="banner-desc">
          基于多目标加权自适应打分模型（健康度 40% + 负载余量 30% + 隧道 RTT 20% + 亲和度 10%），根据任务需求与物理集群实时健康度演算全局最优目标真机，防范过热与过载。
        </p>
      </div>

      <!-- 任务模拟参数配置表单 -->
      <div class="simulation-form-panel">
        <div class="form-grid">
          <div class="form-col">
            <span class="field-label">目标终端平台:</span>
            <a-radio-group v-model:value="form.target_platform" button-style="solid" size="small">
              <a-radio-button value="ios">iOS 物理真机</a-radio-button>
              <a-radio-button value="android">Android 物理真机</a-radio-button>
            </a-radio-group>
          </div>

          <div class="form-col">
            <span class="field-label">任务优先级:</span>
            <a-select v-model:value="form.priority" size="small" style="width: 140px">
              <a-select-option value="CRITICAL">P0 紧急 (CRITICAL)</a-select-option>
              <a-select-option value="HIGH">P1 重要 (HIGH)</a-select-option>
              <a-select-option value="NORMAL">P2 普通 (NORMAL)</a-select-option>
              <a-select-option value="LOW">P3 巡检 (LOW)</a-select-option>
            </a-select>
          </div>

          <div class="form-col">
            <span class="field-label">偏好指定设备 (可选):</span>
            <a-input
              v-model:value="form.preferred_device_id"
              size="small"
              placeholder="如指定将赋予亲和度加分"
              style="width: 220px"
              allow-clear
            />
          </div>
        </div>

        <div class="thresholds-row">
          <span class="threshold-item">
            最低允许电量:
            <a-input-number v-model:value="form.min_battery_percent" :min="10" :max="100" size="small" style="width: 70px" />%
          </span>
          <span class="threshold-item">
            最高耐受温度:
            <a-input-number v-model:value="form.max_temperature_c" :min="30" :max="50" size="small" style="width: 70px" />°C
          </span>
          <a-button
            type="primary"
            size="small"
            :loading="routing"
            @click="handleSimulateRouting"
          >
            <ThunderboltOutlined /> 执行自适应路由演算
          </a-button>
        </div>
      </div>

      <!-- 路由决策结果大盘 -->
      <div v-if="routingResult" class="decision-result-panel">
        <div class="decision-verdict-banner" :class="'status-' + routingResult.status.toLowerCase()">
          <div class="verdict-left">
            <span class="verdict-status-badge">
              <a-tag :color="getStatusTagColor(routingResult.status)">
                {{ routingResult.status }}
              </a-tag>
            </span>
            <span class="verdict-device font-mono">
              命中设备: <strong>{{ routingResult.selected_device_id || '无可用设备 (进入等待队列)' }}</strong>
            </span>
            <span v-if="routingResult.fitness_score" class="verdict-score font-mono">
              综合适应度: <strong class="text-primary">{{ routingResult.fitness_score.toFixed(1) }} 分</strong>
            </span>
          </div>
          <div class="verdict-time font-mono">
            {{ routingResult.allocated_at }}
          </div>
        </div>

        <p class="decision-reason-text">
          <strong>决策依据:</strong> {{ routingResult.routing_reason }}
        </p>

        <!-- 候选设备打分排名矩阵表格 -->
        <div class="candidate-matrix-section">
          <div class="matrix-title">
            <span>候选物理真机加权打分与淘汰裁决明细 ({{ routingResult.candidate_evaluations?.length || 0 }} 台)</span>
          </div>
          <a-table
            :data-source="routingResult.candidate_evaluations || []"
            :columns="candidateColumns"
            row-key="device_id"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'device_id'">
                <code class="font-mono">{{ record.device_id }}</code>
              </template>
              <template v-else-if="column.key === 'eligible'">
                <a-tag :color="record.eligible ? 'green' : 'red'">
                  {{ record.eligible ? '准入通过' : '门禁淘汰' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'composite_fitness'">
                <strong :class="record.eligible ? 'text-primary' : 'text-secondary'">
                  {{ record.composite_fitness.toFixed(1) }} 分
                </strong>
              </template>
              <template v-else-if="column.key === 'disqualify_reason'">
                <span class="reason-text text-danger">{{ record.disqualify_reason || '--' }}</span>
              </template>
            </template>
          </a-table>
        </div>
      </div>

      <!-- 底部控制按钮条 -->
      <div class="modal-footer-bar">
        <a-button @click="handleClose">关闭</a-button>
        <a-button
          v-if="routingResult && routingResult.selected_device_id"
          type="primary"
          @click="handleConfirmDispatch"
        >
          <CheckOutlined /> 确认派发并锁定真机租约
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  ThunderboltOutlined,
  CheckOutlined,
} from '@ant-design/icons-vue'
import {
  fleetSchedulerApi,
  type RoutingDecisionDTO,
} from '@/api/fleetScheduler'

interface Props {
  open: boolean
  defaultPlatform?: string
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  defaultPlatform: 'ios',
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'dispatched', decision: RoutingDecisionDTO): void
}>()

const routing = ref(false)
const routingResult = ref<RoutingDecisionDTO | null>(null)

const form = reactive({
  task_id: 'task_sim_001',
  task_name: '混合工作流移动端端到端回放',
  target_platform: 'ios',
  priority: 'HIGH',
  preferred_device_id: '',
  min_battery_percent: 20,
  max_temperature_c: 42.0,
})

const candidateColumns = [
  { title: '候选真机 ID', dataIndex: 'device_id', key: 'device_id', width: 220 },
  { title: '准入状态', dataIndex: 'eligible', key: 'eligible', width: 100 },
  { title: '健康度 (40%)', dataIndex: 'health_score', key: 'health_score', width: 110 },
  { title: '负载余量 (30%)', dataIndex: 'load_margin_score', key: 'load_margin_score', width: 110 },
  { title: '时延优势 (20%)', dataIndex: 'latency_score', key: 'latency_score', width: 110 },
  { title: '亲和奖励 (10%)', dataIndex: 'affinity_score', key: 'affinity_score', width: 110 },
  { title: '综合适应分', dataIndex: 'composite_fitness', key: 'composite_fitness', width: 110 },
  { title: '淘汰或加分原因', dataIndex: 'disqualify_reason', key: 'disqualify_reason' },
]

function getStatusTagColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'ROUTED':
      return 'green'
    case 'QUEUED':
      return 'orange'
    case 'NO_AVAILABLE_DEVICE':
    default:
      return 'red'
  }
}

async function handleSimulateRouting() {
  routing.value = true
  try {
    const res = await fleetSchedulerApi.dispatchTask({
      task_id: form.task_id,
      task_name: form.task_name,
      target_platform: form.target_platform,
      priority: form.priority,
      preferred_device_id: form.preferred_device_id || undefined,
      min_battery_percent: form.min_battery_percent,
      max_temperature_c: form.max_temperature_c,
    })
    routingResult.value = res.decision
    message.success('多目标自适应路由演算完成！')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '路由演算失败')
  } finally {
    routing.value = false
  }
}

function handleConfirmDispatch() {
  if (!routingResult.value) return
  emit('dispatched', routingResult.value)
  message.success(`已锁定设备 [${routingResult.value.selected_device_id}] 执行配额租约！`)
  handleClose()
}

function handleClose() {
  emit('update:open', false)
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (props.defaultPlatform) {
        form.target_platform = props.defaultPlatform
      }
      form.task_id = `task_sim_${Date.now().toString().slice(-6)}`
      routingResult.value = null
    }
  }
)
</script>

<style scoped>
.scheduler-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-banner {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 4px;
}

.banner-icon {
  color: #1677ff;
  font-size: 16px;
}

.banner-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin: 0;
  line-height: 1.6;
}

.simulation-form-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.form-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18px;
}

.form-col {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  font-size: 12px;
  color: #475569;
  font-weight: 500;
}

.thresholds-row {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-top: 8px;
  border-top: 1px dashed #f1f5f9;
}

.threshold-item {
  font-size: 12px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.decision-result-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.decision-verdict-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
}

.decision-verdict-banner.status-routed {
  border-color: #86efac;
  background: #f0fdf4;
}

.decision-verdict-banner.status-queued {
  border-color: #fde68a;
  background: #fffbeb;
}

.decision-verdict-banner.status-no_available_device {
  border-color: #fca5a5;
  background: #fef2f2;
}

.verdict-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.verdict-device {
  font-size: 13px;
  color: #1e293b;
}

.verdict-score {
  font-size: 12px;
  background: #ffffff;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #cbd5e1;
}

.verdict-time {
  font-size: 11px;
  color: #94a3b8;
}

.decision-reason-text {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.5;
}

.candidate-matrix-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.matrix-title {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.reason-text {
  font-size: 11px;
}

.modal-footer-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--c-border-subtle, #e2e8f0);
}

.text-primary {
  color: #2563eb;
}
.text-danger {
  color: #dc2626;
}
.text-secondary {
  color: #94a3b8;
}
</style>
