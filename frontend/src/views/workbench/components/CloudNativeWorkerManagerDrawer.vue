<template>
  <a-drawer
    :open="open"
    :width="960"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <div class="drawer-title-box">
        <span>云原生弹性 Worker 容器 Pod 调度与配额管理中心</span>
        <a-tag color="blue">K8s Job & Docker 容器化引擎</a-tag>
      </div>
    </template>

    <div class="cloud-native-worker-drawer">
      <!-- 头部控制栏：快速拉起与配置 -->
      <a-card size="small" class="provision-card">
        <div class="provision-header">
          <h4 class="title">瞬时弹性 Worker 容器 Pod 按需拉起</h4>
          <p class="subtitle">
            支持基于 Kubernetes Pod 与 Docker 容器运行时动态开辟隔离执行环境，强制限制 CPU ≤ 16C、内存 ≤ 32GB 资源配额红线，支持生命周期秒级优雅下线与超时自动收割。
          </p>
        </div>

        <a-form layout="inline" class="provision-form">
          <a-form-item label="Worker 名称" required>
            <a-input
              v-model:value="newWorkerName"
              placeholder="如 k8s-worker-prod-01"
              size="small"
              style="width: 170px"
            />
          </a-form-item>

          <a-form-item label="容器运行时">
            <a-select v-model:value="newRuntime" size="small" style="width: 120px">
              <a-select-option value="kubernetes">Kubernetes</a-select-option>
              <a-select-option value="docker">Docker</a-select-option>
              <a-select-option value="containerd">Containerd</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="派发队列">
            <a-select v-model:value="newQueue" size="small" style="width: 110px">
              <a-select-option value="default">default</a-select-option>
              <a-select-option value="performance">performance</a-select-option>
              <a-select-option value="api">api</a-select-option>
              <a-select-option value="mobile_special">mobile</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="CPU Limit">
            <a-input-number
              v-model:value="newCpuLimit"
              :min="0.5"
              :max="16.0"
              :step="0.5"
              size="small"
              style="width: 70px"
            />
            <span class="unit-text">核</span>
          </a-form-item>

          <a-form-item label="内存 Limit">
            <a-input-number
              v-model:value="newMemoryLimit"
              :min="256"
              :max="32768"
              :step="512"
              size="small"
              style="width: 80px"
            />
            <span class="unit-text">MB</span>
          </a-form-item>

          <a-form-item>
            <a-space size="small">
              <a-button
                type="primary"
                size="small"
                :loading="provisioning"
                @click="handleProvision"
              >
                拉起 Worker Pod
              </a-button>
              <a-button
                danger
                size="small"
                :loading="reaping"
                @click="handleReapStale"
              >
                收割超时僵尸 Pod
              </a-button>
              <a-button size="small" :loading="loading" @click="loadPods">
                刷新列表
              </a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 资源水位 KPI 概览 -->
      <div class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">运行中 Pod 实例 (Running)</span>
          <div class="metric-value">
            <span class="live-dot" />
            <strong class="text-green">{{ runningPodsCount }}</strong>
            <small class="unit">个 Pod</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">已分配 CPU 核心总量</span>
          <div class="metric-value">
            <strong class="text-blue">{{ totalAllocatedCpu }}</strong>
            <small class="unit">Cores (上限 16C/Pod)</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">已分配内存总量</span>
          <div class="metric-value">
            <strong class="text-purple">{{ totalAllocatedMemory }}</strong>
            <small class="unit">MB</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">已下线销毁数 (Terminated)</span>
          <div class="metric-value">
            <strong class="text-slate">{{ terminatedPodsCount }}</strong>
            <small class="unit">个已回收</small>
          </div>
        </div>
      </div>

      <!-- 容器 Pod 实例明细流水表格 -->
      <a-card size="small" title="云原生 Worker 容器 Pod 生命周期流水" class="pods-table-card">
        <a-table
          :data-source="pods"
          :columns="columns"
          row-key="pod_id"
          size="small"
          :pagination="{ pageSize: 6 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'worker_name'">
              <div class="pod-title-cell">
                <strong>{{ record.worker_name }}</strong>
                <code class="pod-id-text">{{ record.pod_id }}</code>
              </div>
            </template>

            <template v-if="column.key === 'runtime'">
              <a-tag :color="getRuntimeColor(record.runtime)">
                {{ record.runtime.toUpperCase() }}
              </a-tag>
            </template>

            <template v-if="column.key === 'queue'">
              <a-tag color="blue">{{ record.assigned_queue }}</a-tag>
            </template>

            <template v-if="column.key === 'quota'">
              <div class="quota-cell">
                <span>CPU: <strong>{{ record.resource_quota.cpu_limit_cores }}C</strong></span>
                <span>内存: <strong>{{ record.resource_quota.memory_limit_mb }}MB</strong></span>
              </div>
            </template>

            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ record.status.toUpperCase() }}
              </a-tag>
            </template>

            <template v-if="column.key === 'actions'">
              <a-space size="small">
                <a-button size="small" type="link" @click="openLogsModal(record)">
                  查看日志
                </a-button>
                <a-button
                  v-if="record.status === 'running' || record.status === 'pending'"
                  size="small"
                  type="link"
                  danger
                  @click="handleTerminate(record.pod_id)"
                >
                  优雅下线
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 队列背压自适应 HPA 自动扩缩容看板 -->
      <HpaAutoscalingDashboardCard />

      <!-- 容器日志弹窗 -->
      <a-modal
        v-model:open="logsModalOpen"
        :title="`Pod 运行日志 - ${selectedPod?.worker_name || ''} (${selectedPod?.pod_id || ''})`"
        :footer="null"
        width="700px"
        destroy-on-close
      >
        <div class="logs-container">
          <pre class="logs-code">{{ podLogsText || '暂无容器控制台输出日志' }}</pre>
        </div>
      </a-modal>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  cloudNativeWorkersApi,
  type ContainerRuntime,
  type EphemeralWorkerPodItem,
  type PodStatus,
} from '@/api/cloudNativeWorkers'
import HpaAutoscalingDashboardCard from './HpaAutoscalingDashboardCard.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const provisioning = ref(false)
const reaping = ref(false)

const newWorkerName = ref('k8s-worker-prod-01')
const newRuntime = ref<ContainerRuntime>('kubernetes')
const newQueue = ref('default')
const newCpuLimit = ref(2.0)
const newMemoryLimit = ref(2048)

const pods = ref<EphemeralWorkerPodItem[]>([])
const selectedPod = ref<EphemeralWorkerPodItem | null>(null)
const logsModalOpen = ref(false)
const podLogsText = ref('')

const columns = [
  { title: 'Pod 名称 / 唯一标识', key: 'worker_name', width: 220 },
  { title: '容器运行时', key: 'runtime', width: 110 },
  { title: '任务队列', key: 'queue', width: 110 },
  { title: '配额规格 (Quota)', key: 'quota', width: 150 },
  { title: '调度状态', key: 'status', width: 110 },
  { title: '操作', key: 'actions', width: 140 },
]

const runningPodsCount = computed(() => pods.value.filter((p) => p.status === 'running').length)
const terminatedPodsCount = computed(() => pods.value.filter((p) => p.status === 'terminated').length)

const totalAllocatedCpu = computed(() => {
  const running = pods.value.filter((p) => p.status === 'running')
  const sumCpu = running.reduce((acc, p) => acc + (p.resource_quota?.cpu_limit_cores || 0), 0)
  return roundTo(sumCpu, 1)
})

const totalAllocatedMemory = computed(() => {
  const running = pods.value.filter((p) => p.status === 'running')
  return running.reduce((acc, p) => acc + (p.resource_quota?.memory_limit_mb || 0), 0)
})

function roundTo(num: number, decimals: number): number {
  const factor = Math.pow(10, decimals)
  return Math.round(num * factor) / factor
}

function getRuntimeColor(runtime: ContainerRuntime): string {
  switch (runtime) {
    case 'kubernetes':
      return 'blue'
    case 'docker':
      return 'green'
    case 'containerd':
      return 'orange'
    default:
      return 'default'
  }
}

function getStatusColor(status: PodStatus): string {
  switch (status) {
    case 'running':
      return 'green'
    case 'pending':
      return 'blue'
    case 'succeeded':
      return 'cyan'
    case 'failed':
      return 'red'
    case 'terminated':
      return 'default'
    default:
      return 'default'
  }
}

function handleClose() {
  emit('update:open', false)
}

async function loadPods() {
  loading.value = true
  try {
    const res = await cloudNativeWorkersApi.listPods()
    pods.value = res.pods
  } catch (err: any) {
    message.error(err.message || '获取 Worker Pods 失败')
  } finally {
    loading.value = false
  }
}

async function handleProvision() {
  if (!newWorkerName.value) {
    message.warning('请输入 Worker 名称')
    return
  }
  provisioning.value = true
  try {
    const res = await cloudNativeWorkersApi.provisionPod({
      worker_name: newWorkerName.value,
      image: 'atp/worker-python:3.12-v1',
      assigned_queue: newQueue.value,
      runtime: newRuntime.value,
      cpu_limit_cores: newCpuLimit.value,
      memory_limit_mb: newMemoryLimit.value,
    })
    message.success(`Worker Pod 拉起成功: ${res.pod.pod_id}`)
    await loadPods()
  } catch (err: any) {
    message.error(err.message || '拉起 Worker Pod 失败')
  } finally {
    provisioning.value = false
  }
}

async function handleTerminate(podId: string) {
  try {
    await cloudNativeWorkersApi.terminatePod(podId, 0)
    message.success('Worker Pod 已优雅下线并销毁！')
    await loadPods()
  } catch (err: any) {
    message.error(err.message || '下线 Pod 失败')
  }
}

async function handleReapStale() {
  reaping.value = true
  try {
    const res = await cloudNativeWorkersApi.reapStalePods(3600.0)
    message.success(`僵尸 Pod 收割完成！已回收 ${res.reaped_count} 个超限容器。`)
    await loadPods()
  } catch (err: any) {
    message.error(err.message || '收割僵尸 Pod 失败')
  } finally {
    reaping.value = false
  }
}

async function openLogsModal(pod: any) {
  selectedPod.value = pod
  logsModalOpen.value = true
  try {
    const detail = await cloudNativeWorkersApi.getPod(pod.pod_id)
    podLogsText.value = detail.logs?.join('\n') || ''
  } catch (err: any) {
    podLogsText.value = '拉取容器日志失败: ' + (err.message || '')
  }
}

onMounted(() => {
  loadPods()
})
</script>

<style scoped>
.cloud-native-worker-drawer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.provision-card,
.pods-table-card {
  border-radius: 8px;
}

.provision-header {
  margin-bottom: 8px;
}

.title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.provision-form {
  margin-top: 6px;
}

.unit-text {
  font-size: 11px;
  color: #64748b;
  margin-left: 4px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
}

.metric-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  display: block;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  color: var(--c-text, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.unit {
  font-size: 11px;
  font-weight: normal;
  color: var(--c-text-tertiary, #94a3b8);
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
}

.text-green {
  color: #16a34a;
}

.text-blue {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

.text-slate {
  color: #64748b;
}

.pod-title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pod-id-text {
  font-size: 10px;
  color: #94a3b8;
  font-family: monospace;
}

.quota-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: #475569;
}

.logs-container {
  background: #0f172a;
  border-radius: 6px;
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.logs-code {
  color: #38bdf8;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
}
</style>
