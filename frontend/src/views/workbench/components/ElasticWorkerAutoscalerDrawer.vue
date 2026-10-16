<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="云原生 Worker 容器 Pod 弹性扩缩容拓扑与集群配额监控控制台"
    destroy-on-close
    class="autoscaler-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部机制介绍 Banner -->
      <div class="mechanism-banner">
        <div class="banner-icon-col">
          <CloudServerOutlined class="banner-icon" />
        </div>
        <div class="banner-texts">
          <div class="banner-title">Kubernetes / Docker 动态 Worker 容器弹性伸缩与配额仲裁引擎 (T1.1)</div>
          <div class="banner-desc">
            基于用例任务排队深度与单 Worker 推荐并发度，通过云原生 HPA 弹性算法动态计算期望副本数；具备物理资源硬配额仲裁与超额平滑降级机制，杜绝集群 OOM 与资源排队饥饿。
          </div>
        </div>
      </div>

      <!-- 集群资源配额水位 KPI -->
      <div class="quota-section">
        <div class="section-title">集群物理资源水位与 Worker 运行态势</div>
        <a-row :gutter="[16, 16]">
          <a-col :xs="24" :sm="12" :md="6">
            <div class="kpi-card">
              <div class="kpi-label">活跃 Worker 副本数</div>
              <div class="kpi-value text-primary">
                {{ clusterStatus?.current_active_replicas ?? 2 }}
                <span class="kpi-sub">/ {{ clusterStatus?.max_replicas ?? 20 }} Max</span>
              </div>
              <div class="kpi-footer">最小保障副本: {{ clusterStatus?.min_replicas ?? 1 }}</div>
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="kpi-card">
              <div class="kpi-label">CPU 资源分配水位</div>
              <div class="kpi-value text-success">
                {{ clusterStatus?.used_cpu_cores ?? 1.0 }}
                <span class="kpi-sub">/ {{ clusterStatus?.allocatable_cpu_cores ?? 32.0 }} Cores</span>
              </div>
              <a-progress
                :percent="clusterStatus?.cpu_usage_pct ?? 3.1"
                size="small"
                status="active"
                stroke-color="#10b981"
              />
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="kpi-card">
              <div class="kpi-label">内存资源分配水位</div>
              <div class="kpi-value text-warning">
                {{ clusterStatus?.used_memory_gib ?? 2.0 }}
                <span class="kpi-sub">/ {{ clusterStatus?.allocatable_memory_gib ?? 64.0 }} GiB</span>
              </div>
              <a-progress
                :percent="clusterStatus?.memory_usage_pct ?? 3.1"
                size="small"
                status="active"
                stroke-color="#f59e0b"
              />
            </div>
          </a-col>
          <a-col :xs="24" :sm="12" :md="6">
            <div class="kpi-card">
              <div class="kpi-label">历史扩缩容审计事件</div>
              <div class="kpi-value text-purple">{{ events.length }} <span class="kpi-sub">次</span></div>
              <div class="kpi-footer">不可篡改事件流追踪</div>
            </div>
          </a-col>
        </a-row>
      </div>

      <!-- 交互式模拟排队与扩缩容决策评估 -->
      <div class="simulation-section">
        <div class="section-title">任务负载感知与扩缩容决策模拟</div>
        <div class="simulation-box">
          <div class="slider-row">
            <span class="slider-label">当前任务队列排队深度 (Queue Depth):</span>
            <div class="slider-control">
              <a-slider v-model:value="simQueueDepth" :min="0" :max="80" class="flex-1" />
              <a-input-number v-model:value="simQueueDepth" :min="0" :max="80" class="w-20" />
            </div>
            <a-button type="primary" :loading="evaluating" @click="handleEvaluate">
              <ThunderboltOutlined /> 评估扩缩容决策
            </a-button>
          </div>

          <!-- 决策结果卡片 -->
          <div v-if="latestDecision" class="decision-card">
            <div class="decision-header">
              <div class="action-badge-row">
                <span class="decision-title">扩缩容决策结果:</span>
                <a-tag :color="getActionColor(latestDecision.action)" class="action-tag">
                  {{ latestDecision.action }}
                </a-tag>
                <a-tag :color="getArbitrationColor(latestDecision.arbitration_status)">
                  {{ latestDecision.arbitration_status }}
                </a-tag>
              </div>
              <a-button
                v-if="latestDecision.action !== 'NOOP' && latestDecision.action !== 'QUOTA_BLOCKED'"
                type="primary"
                size="small"
                :loading="applying"
                @click="handleApply"
              >
                落地调度执行该决策
              </a-button>
            </div>

            <div class="replica-change-flow">
              <div class="replica-box">
                <div class="box-label">当前活跃副本</div>
                <div class="box-val">{{ latestDecision.current_replicas }}</div>
              </div>
              <div class="flow-arrow">➔</div>
              <div class="replica-box">
                <div class="box-label">算法期望副本</div>
                <div class="box-val">{{ latestDecision.desired_replicas }}</div>
              </div>
              <div class="flow-arrow">➔</div>
              <div class="replica-box highlight">
                <div class="box-label">实际分配副本 (经仲裁)</div>
                <div class="box-val text-primary">{{ latestDecision.allocated_replicas }}</div>
              </div>
            </div>

            <div class="decision-reason">
              <span class="reason-label">决策裁决原因:</span>
              <span class="reason-text">{{ latestDecision.reason }}</span>
            </div>

            <div class="estimate-stats">
              <span>预计 CPU 水位: <strong>{{ latestDecision.cpu_utilization_estimate_pct }}%</strong></span>
              <span>预计 内存 水位: <strong>{{ latestDecision.memory_utilization_estimate_pct }}%</strong></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史扩缩容审计事件列表 -->
      <div class="history-section">
        <div class="history-header">
          <div class="section-title">扩缩容审计事件流日志</div>
          <a-space>
            <a-button size="small" :loading="loading" @click="fetchData">
              <ReloadOutlined /> 刷新事件
            </a-button>
            <a-button size="small" danger :disabled="events.length === 0" @click="handleClearEvents">
              <DeleteOutlined /> 清空事件
            </a-button>
          </a-space>
        </div>

        <a-table
          :data-source="events"
          :columns="columns"
          :row-key="(r: any) => r.decision_id"
          :loading="loading"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'action'">
              <a-tag :color="getActionColor(record.action)">{{ record.action }}</a-tag>
            </template>
            <template v-else-if="column.key === 'replicas'">
              <span>{{ record.current_replicas }} ➔ <strong>{{ record.allocated_replicas }}</strong></span>
            </template>
            <template v-else-if="column.key === 'arbitration_status'">
              <a-tag :color="getArbitrationColor(record.arbitration_status)">{{ record.arbitration_status }}</a-tag>
            </template>
            <template v-else-if="column.key === 'created_at'">
              <span class="text-xs">{{ record.created_at.substring(11, 19) }}</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CloudServerOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import {
  elasticWorkerAutoscalerApi,
  type ClusterStatus,
  type ScalingDecision,
} from '@/api/cloudNativeCluster'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const evaluating = ref(false)
const applying = ref(false)
const simQueueDepth = ref(20)
const clusterStatus = ref<ClusterStatus | null>(null)
const latestDecision = ref<ScalingDecision | null>(null)
const events = ref<ScalingDecision[]>([])

const columns = [
  { title: '决策 ID', dataIndex: 'decision_id', key: 'decision_id', width: 180 },
  { title: '动作', key: 'action', width: 110 },
  { title: '排队深度', dataIndex: 'queue_depth', key: 'queue_depth', width: 90 },
  { title: '副本流转', key: 'replicas', width: 120 },
  { title: '配额仲裁', key: 'arbitration_status', width: 130 },
  { title: '裁决原因', dataIndex: 'reason', key: 'reason' },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 90 },
]

function handleClose() {
  emit('update:open', false)
}

function getActionColor(action: string) {
  switch (action) {
    case 'SCALE_UP': return 'green'
    case 'SCALE_DOWN': return 'blue'
    case 'QUOTA_BLOCKED': return 'red'
    default: return 'default'
  }
}

function getArbitrationColor(status: string) {
  switch (status) {
    case 'SUFFICIENT': return 'success'
    case 'ARBITRATED_DEGRADED': return 'warning'
    case 'EXHAUSTED': return 'error'
    default: return 'default'
  }
}

async function fetchData() {
  loading.value = true
  try {
    const [statusRes, eventsRes] = await Promise.all([
      elasticWorkerAutoscalerApi.getStatus(),
      elasticWorkerAutoscalerApi.getEvents({ limit: 50 }),
    ])
    clusterStatus.value = statusRes
    events.value = eventsRes.events || []
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取集群状态失败')
  } finally {
    loading.value = false
  }
}
async function handleEvaluate() {
  evaluating.value = true
  try {
    const res = await elasticWorkerAutoscalerApi.evaluate({ queue_depth: simQueueDepth.value })
    latestDecision.value = res.decision
    message.success(res.message || '扩缩容决策评估完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '评估失败')
  } finally {
    evaluating.value = false
  }
}

async function handleApply() {
  if (!latestDecision.value) return
  applying.value = true
  try {
    const res = await elasticWorkerAutoscalerApi.apply({ queue_depth: simQueueDepth.value })
    message.success(res.message || '扩缩容调度成功执行')
    await fetchData()
    latestDecision.value = res.decision
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '执行失败')
  } finally {
    applying.value = false
  }
}

async function handleClearEvents() {
  try {
    await elasticWorkerAutoscalerApi.clearEvents()
    message.success('已清空扩缩容历史事件')
    await fetchData()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '清空失败')
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      fetchData()
      handleEvaluate()
    }
  }
)

onMounted(() => {
  if (props.open) {
    fetchData()
    handleEvaluate()
  }
})
</script>

<style scoped>
.autoscaler-drawer :deep(.ant-drawer-body) {
  padding: 16px;
  background: var(--c-bg-layout, #f8fafc);
}

.mechanism-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.banner-icon {
  font-size: 28px;
  color: #2563eb;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
  margin-bottom: 2px;
}

.banner-desc {
  font-size: 12px;
  color: #3b82f6;
  line-height: 1.5;
}

.quota-section,
.simulation-section,
.history-section {
  background: #ffffff;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 12px;
}

.kpi-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px 14px;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
}

.kpi-value {
  font-size: 20px;
  font-weight: 800;
  margin: 4px 0;
}

.kpi-sub {
  font-size: 12px;
  font-weight: normal;
  color: #94a3b8;
}

.kpi-footer {
  font-size: 11px;
  color: #94a3b8;
}

.text-primary { color: #2563eb; }
.text-success { color: #10b981; }
.text-warning { color: #f59e0b; }
.text-purple { color: #8b5cf6; }

.simulation-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.slider-label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  width: 250px;
}

.slider-control {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.decision-card {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 14px;
}

.decision-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.action-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.decision-title {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.action-tag {
  font-weight: 700;
}

.replica-change-flow {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.replica-box {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 6px 14px;
  text-align: center;
}

.replica-box.highlight {
  border-color: #3b82f6;
  background: #eff6ff;
}

.box-label {
  font-size: 10px;
  color: #64748b;
}

.box-val {
  font-size: 16px;
  font-weight: 800;
}

.flow-arrow {
  color: #94a3b8;
  font-weight: bold;
}

.decision-reason {
  font-size: 12px;
  color: #334155;
  margin-bottom: 8px;
}

.reason-label {
  font-weight: 700;
  margin-right: 4px;
}

.estimate-stats {
  display: flex;
  gap: 20px;
  font-size: 11px;
  color: #64748b;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.text-xs {
  font-size: 11px;
}

.flex-1 {
  flex: 1;
}

.w-20 {
  width: 80px;
}
</style>
