<template>
  <a-drawer
    :open="open"
    :width="940"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>跨节点 Worker 集群协同负载与容量分级监控台</span>
    </template>

    <div class="cluster-worker-monitor-drawer">
      <!-- 头部控制栏：刷新与队列过滤 -->
      <a-card size="small" class="control-card">
        <div class="control-header">
          <div class="desc-box">
            <h4 class="title">多节点动态负载感知与算力加权择优调度</h4>
            <p class="subtitle">
              实时追踪全网分布在不同主机/容器的 Worker 节点并发水位、CPU 与内存利用率，通过多维加权复合评分算法实现毫秒级最优任务定向路由。
            </p>
          </div>
          <div class="action-box">
            <a-space>
              <a-select v-model:value="selectedQueue" style="width: 140px" @change="loadWorkers">
                <a-select-option value="">全部队列</a-select-option>
                <a-select-option value="default">default 队列</a-select-option>
                <a-select-option value="performance">performance 队列</a-select-option>
                <a-select-option value="api">api 队列</a-select-option>
                <a-select-option value="mobile_special">mobile 队列</a-select-option>
              </a-select>
              <a-button :loading="loading" @click="loadAll">
                刷新集群状态
              </a-button>
            </a-space>
          </div>
        </div>
      </a-card>

      <!-- 集群全域容量总览 KPI 卡片 -->
      <div v-if="overview" class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">存活活跃节点 / 注册总数</span>
          <div class="metric-value">
            <strong class="text-success">{{ overview.total_alive_nodes }}</strong>
            <span class="slash">/</span>
            <span>{{ overview.total_nodes_registered }}</span>
            <small class="unit">个节点</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">并发槽位总容量与水位</span>
          <div class="metric-value">
            <strong>{{ overview.total_active_tasks }} / {{ overview.total_concurrency_slots }}</strong>
            <a-tag color="blue" class="util-tag">
              {{ overview.cluster_utilization_pct }}%
            </a-tag>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">集群平均资源负载</span>
          <div class="metric-value">
            <span class="res-text">CPU: {{ overview.average_cpu_pct }}%</span>
            <span class="slash">|</span>
            <span class="res-text">内存: {{ overview.average_memory_pct }}%</span>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">五级容量梯队健康分布</span>
          <div class="health-dist-tags">
            <a-tag color="green">空闲: {{ overview.health_distribution?.HEALTHY_IDLE ?? 0 }}</a-tag>
            <a-tag color="blue">适中: {{ overview.health_distribution?.MODERATE_LOAD ?? 0 }}</a-tag>
            <a-tag color="orange">重载: {{ overview.health_distribution?.HEAVY_LOAD ?? 0 }}</a-tag>
            <a-tag color="red">超载: {{ overview.health_distribution?.OVERLOADED ?? 0 }}</a-tag>
          </div>
        </div>
      </div>

      <!-- 最优节点调度择优模拟卡片 -->
      <a-card size="small" title="自适应最优 Worker 节点择优选举模拟 (Optimal Dispatch Simulation)" class="sim-card">
        <div class="sim-content">
          <div class="sim-left">
            <a-form layout="inline">
              <a-form-item label="待派发任务队列">
                <a-input v-model:value="simQueue" placeholder="default" style="width: 140px" />
              </a-form-item>
              <a-button type="primary" :loading="selecting" @click="handleSimulateSelect">
                运行最优节点选举算法
              </a-button>
            </a-form>
          </div>

          <div v-if="optimalWorker" class="sim-result-badge">
            <span class="opt-lbl">当前选举胜出节点:</span>
            <strong class="opt-id">{{ optimalWorker.worker_id }}</strong>
            <a-tag color="cyan">{{ optimalWorker.hostname }} ({{ optimalWorker.ip_address }})</a-tag>
            <span class="opt-cap">可用容量分: <strong>{{ optimalWorker.capacity_score }}</strong></span>
          </div>
        </div>
      </a-card>

      <!-- 实时 Worker 节点列表明细 -->
      <a-card size="small" title="跨节点 Worker 实时监控明细流水" class="workers-table-card">
        <a-table
          :data-source="workers"
          :columns="columns"
          row-key="worker_id"
          size="small"
          :pagination="{ pageSize: 6 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'worker_id'">
              <div class="worker-id-cell">
                <span :class="record.is_alive ? 'live-dot' : 'dead-dot'" />
                <strong>{{ record.worker_id }}</strong>
              </div>
              <small class="host-info">{{ record.hostname }} ({{ record.ip_address }})</small>
            </template>

            <template v-if="column.key === 'queues'">
              <a-space size="small" class="tag-wrap">
                <a-tag v-for="q in record.queues" :key="q" color="blue" class="mini-tag">
                  {{ q }}
                </a-tag>
              </a-space>
            </template>

            <template v-if="column.key === 'concurrency'">
              <div class="conc-cell">
                <span>{{ record.current_concurrency }} / {{ record.max_concurrency }}</span>
                <a-progress
                  :percent="Math.round((record.current_concurrency / record.max_concurrency) * 100)"
                  :status="record.current_concurrency >= record.max_concurrency ? 'exception' : 'normal'"
                  size="small"
                  style="width: 80px"
                />
              </div>
            </template>

            <template v-if="column.key === 'resources'">
              <div class="res-cell">
                <span>CPU: <strong>{{ record.cpu_usage_pct }}%</strong></span>
                <span>内存: <strong>{{ record.memory_usage_pct }}%</strong></span>
              </div>
            </template>

            <template v-if="column.key === 'scores'">
              <div class="scores-cell">
                <span class="score-line">负载: <strong class="text-orange">{{ record.load_score }}</strong></span>
                <span class="score-line">可用容量: <strong class="text-success">{{ record.capacity_score }}</strong></span>
              </div>
            </template>

            <template v-if="column.key === 'level'">
              <a-tag :color="getLevelColor(record.capacity_level)">
                {{ getLevelLabel(record.capacity_level) }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </a-card>
      <!-- 容灾故障转移控制卡片 -->
      <WorkerFailoverRecoveryCard />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  clusterWorkersApi,
  type ClusterWorkerNodeItem,
  type ClusterCapacityOverview,
  type CapacityLevel,
} from '@/api/clusterWorkers'
import WorkerFailoverRecoveryCard from './WorkerFailoverRecoveryCard.vue'

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
const selecting = ref(false)
const selectedQueue = ref('')
const simQueue = ref('default')

const overview = ref<ClusterCapacityOverview | null>(null)
const workers = ref<ClusterWorkerNodeItem[]>([])
const optimalWorker = ref<ClusterWorkerNodeItem | null>(null)

const columns = [
  { title: '节点 ID / 主机名', key: 'worker_id', width: 220 },
  { title: '监听队列', key: 'queues', width: 140 },
  { title: '当前并发槽位', key: 'concurrency', width: 160 },
  { title: 'CPU / 内存负载', key: 'resources', width: 140 },
  { title: '负载 / 容量分', key: 'scores', width: 130 },
  { title: '容量分级', key: 'level', width: 100 },
]

function getLevelColor(level: CapacityLevel): string {
  switch (level) {
    case 'HEALTHY_IDLE':
      return 'green'
    case 'MODERATE_LOAD':
      return 'blue'
    case 'HEAVY_LOAD':
      return 'orange'
    case 'OVERLOADED':
      return 'red'
    default:
      return 'default'
  }
}

function getLevelLabel(level: CapacityLevel): string {
  switch (level) {
    case 'HEALTHY_IDLE':
      return '空闲健康'
    case 'MODERATE_LOAD':
      return '负载适中'
    case 'HEAVY_LOAD':
      return '重载运行'
    case 'OVERLOADED':
      return '超载饱和'
    case 'DRAINING':
      return '排空下线'
    case 'OFFLINE':
      return '离线失联'
    default:
      return level
  }
}

function handleClose() {
  emit('update:open', false)
}

async function loadOverview() {
  try {
    const res = await clusterWorkersApi.getOverview()
    overview.value = res
  } catch (err: any) {
    message.error(err.message || '获取集群容量总览失败')
  }
}

async function loadWorkers() {
  loading.value = true
  try {
    const res = await clusterWorkersApi.listWorkers({
      queue: selectedQueue.value || undefined,
      only_alive: false,
    })
    workers.value = res.workers
  } catch (err: any) {
    message.error(err.message || '获取 Worker 节点列表失败')
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  await Promise.all([loadOverview(), loadWorkers()])
  message.success('集群实时状态已更新！')
}

async function handleSimulateSelect() {
  selecting.value = true
  try {
    const res = await clusterWorkersApi.selectOptimal({
      required_queue: simQueue.value.trim() || 'default',
    })
    optimalWorker.value = res.worker
    message.success(`最优节点选举成功: 节点 ${res.worker.worker_id} 胜出！`)
  } catch (err: any) {
    message.error(err.message || '最优节点选举失败')
  } finally {
    selecting.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.cluster-worker-monitor-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-card,
.sim-card,
.workers-table-card {
  border-radius: 8px;
}

.control-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  padding: 12px 14px;
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
  font-size: 17px;
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

.slash {
  color: var(--c-text-tertiary, #94a3b8);
}

.text-success {
  color: #16a34a;
}

.text-orange {
  color: #ea580c;
}

.util-tag {
  font-size: 11px;
  padding: 0 6px;
}

.res-text {
  font-size: 13px;
  color: #334155;
}

.health-dist-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sim-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.sim-result-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  font-size: 12px;
}

.opt-lbl {
  color: var(--c-text-secondary, #64748b);
}

.opt-id {
  color: #16a34a;
}

.opt-cap {
  color: #0369a1;
}

.worker-id-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
}

.dead-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}

.host-info {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-family: monospace;
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mini-tag {
  font-size: 10px;
  padding: 0 4px;
}

.conc-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.res-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: #475569;
}

.scores-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}
</style>
