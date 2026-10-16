<template>
  <a-drawer
    :open="open"
    :width="940"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <span>自适应任务排队水位与 P0 弹性抢占调度控制台</span>
    </template>

    <div class="adaptive-task-queue-drawer">
      <!-- 头部控制栏：快捷测试与提交 -->
      <a-card size="small" class="control-card">
        <div class="control-header">
          <div class="desc-box">
            <h4 class="title">四级优先级梯队与动态弹性抢占调度 (P0 ~ P3)</h4>
            <p class="subtitle">
              当集群执行槽位满载时，紧急高优先级任务（P0）自动对运行中的低优先级长任务（P3/P2）执行安全挂起抢占；任务完成后优先自动唤醒挂起任务，防止任务饥饿。
            </p>
          </div>
          <div class="action-box">
            <a-space>
              <a-button type="primary" danger size="small" :loading="submitting" @click="handleQuickEnqueueP0">
                模拟提交 P0 紧急抢占
              </a-button>
              <a-button size="small" :loading="submitting" @click="handleQuickEnqueueP2">
                提交 P2 常规任务
              </a-button>
              <a-button size="small" :loading="loading" @click="loadTasks">
                刷新队列
              </a-button>
            </a-space>
          </div>
        </div>
      </a-card>

      <!-- 队列水位与排队统计指标卡 -->
      <div class="metrics-row">
        <div class="metric-card">
          <span class="metric-label">正在执行中 (Running)</span>
          <div class="metric-value">
            <span class="live-dot" />
            <strong class="text-success">{{ runningTasksCount }}</strong>
            <small class="unit">个任务</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">排队等待中 (Queued)</span>
          <div class="metric-value">
            <strong class="text-blue">{{ queuedTasksCount }}</strong>
            <small class="unit">个任务</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">被弹性抢占挂起 (Suspended)</span>
          <div class="metric-value">
            <strong class="text-orange">{{ suspendedTasksCount }}</strong>
            <small class="unit">个挂起等待唤醒</small>
          </div>
        </div>

        <div class="metric-card">
          <span class="metric-label">队列过滤</span>
          <div class="filter-box">
            <a-select v-model:value="selectedQueue" style="width: 140px" @change="loadTasks">
              <a-select-option value="">全部队列</a-select-option>
              <a-select-option value="default">default 队列</a-select-option>
              <a-select-option value="performance">performance</a-select-option>
              <a-select-option value="api">api 队列</a-select-option>
            </a-select>
          </div>
        </div>
      </div>

      <!-- ETA 预测信息展示条 -->
      <a-alert
        v-if="activeEtaInfo"
        type="info"
        show-icon
        closable
        class="eta-alert"
        :message="`[实时排队 ETA] ${activeEtaInfo.message}`"
        :description="`任务 ID: ${activeEtaInfo.task_id}，当前排在队列第 ${activeEtaInfo.queue_position} 位，预计等待 ${activeEtaInfo.estimated_wait_seconds} 秒`"
        @close="activeEtaInfo = null"
      />

      <!-- 实时调度队列流水表格 -->
      <a-card size="small" title="自适应任务调度流水明细" class="tasks-table-card">
        <a-table
          :data-source="tasks"
          :columns="columns"
          row-key="task_id"
          size="small"
          :pagination="{ pageSize: 7 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'task_name'">
              <div class="task-title-cell">
                <strong>{{ record.task_name }}</strong>
                <code class="task-id">{{ record.task_id }}</code>
              </div>
            </template>

            <template v-if="column.key === 'priority'">
              <a-tag :color="getPriorityColor(record.priority)" class="priority-tag">
                {{ record.priority }}
              </a-tag>
            </template>

            <template v-if="column.key === 'status'">
              <div class="status-cell">
                <a-tag :color="getStatusColor(record.status)">
                  {{ getStatusLabel(record.status) }}
                </a-tag>
                <a-tag v-if="record.preempted_count > 0" color="orange" class="preempted-tag">
                  被抢占 {{ record.preempted_count }} 次
                </a-tag>
              </div>
            </template>

            <template v-if="column.key === 'worker'">
              <span v-if="record.assigned_worker_id" class="worker-text">
                {{ record.assigned_worker_id }}
              </span>
              <span v-else class="text-muted">待分发</span>
            </template>

            <template v-if="column.key === 'actions'">
              <a-space size="small">
                <a-button
                  v-if="record.status === 'queued' || record.status === 'suspended'"
                  size="small"
                  type="link"
                  @click="handleCheckEta(record.task_id)"
                >
                  测算 ETA
                </a-button>

                <a-button
                  v-if="record.status === 'running'"
                  size="small"
                  type="link"
                  class="complete-btn"
                  @click="handleCompleteTask(record.task_id)"
                >
                  完成释放
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  clusterWorkersApi,
  type QueuedTaskItem,
  type TaskPriority,
  type TaskStatus,
  type TaskEtaResult,
} from '@/api/clusterWorkers'

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
const submitting = ref(false)
const selectedQueue = ref('')
const tasks = ref<QueuedTaskItem[]>([])
const activeEtaInfo = ref<TaskEtaResult | null>(null)

const columns = [
  { title: '任务名称 / 标识', key: 'task_name', width: 230 },
  { title: '队列', dataIndex: 'queue_name', key: 'queue_name', width: 100 },
  { title: '优先级', key: 'priority', width: 90 },
  { title: '调度状态', key: 'status', width: 170 },
  { title: '分配 Worker', key: 'worker', width: 150 },
  { title: '操作', key: 'actions', width: 120 },
]

const runningTasksCount = computed(() => tasks.value.filter((t) => t.status === 'running').length)
const queuedTasksCount = computed(() => tasks.value.filter((t) => t.status === 'queued').length)
const suspendedTasksCount = computed(() => tasks.value.filter((t) => t.status === 'suspended').length)

function getPriorityColor(p: TaskPriority): string {
  switch (p) {
    case 'P0':
      return 'red'
    case 'P1':
      return 'orange'
    case 'P2':
      return 'blue'
    case 'P3':
      return 'default'
    default:
      return 'default'
  }
}

function getStatusColor(s: TaskStatus): string {
  switch (s) {
    case 'running':
      return 'green'
    case 'suspended':
      return 'orange'
    case 'queued':
      return 'blue'
    case 'completed':
      return 'default'
    case 'aborted':
      return 'red'
    default:
      return 'default'
  }
}

function getStatusLabel(s: TaskStatus): string {
  switch (s) {
    case 'running':
      return '正在执行'
    case 'suspended':
      return '被挂起'
    case 'queued':
      return '排队等待'
    case 'completed':
      return '已完成'
    case 'aborted':
      return '已终止'
    default:
      return s
  }
}

function handleClose() {
  emit('update:open', false)
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await clusterWorkersApi.listTasks(selectedQueue.value || undefined)
    tasks.value = res.tasks
  } catch (err: any) {
    message.error(err.message || '获取任务队列失败')
  } finally {
    loading.value = false
  }
}

async function handleQuickEnqueueP0() {
  submitting.value = true
  try {
    const res = await clusterWorkersApi.enqueueTask({
      task_name: '线上阻断紧急冒烟测试 (P0)',
      queue_name: selectedQueue.value || 'default',
      priority: 'P0',
      allow_preemption: true,
    })
    if (res.preempted) {
      message.warning('P0 紧急任务已触发弹性抢占！低优先级任务已被挂起让出槽位。')
    } else {
      message.success('P0 任务已成功派发运行！')
    }
    await loadTasks()
  } catch (err: any) {
    message.error(err.message || '提交任务失败')
  } finally {
    submitting.value = false
  }
}

async function handleQuickEnqueueP2() {
  submitting.value = true
  try {
    await clusterWorkersApi.enqueueTask({
      task_name: '常规自动化回归用例测试 (P2)',
      queue_name: selectedQueue.value || 'default',
      priority: 'P2',
      allow_preemption: false,
    })
    message.success('P2 常规任务已提交至队列！')
    await loadTasks()
  } catch (err: any) {
    message.error(err.message || '提交任务失败')
  } finally {
    submitting.value = false
  }
}

async function handleCheckEta(taskId: string) {
  try {
    const res = await clusterWorkersApi.getTaskEta(taskId)
    activeEtaInfo.value = res
  } catch (err: any) {
    message.error(err.message || '获取 ETA 失败')
  }
}

async function handleCompleteTask(taskId: string) {
  try {
    await clusterWorkersApi.completeTask(taskId)
    message.success('任务完成并释放槽位，已自动尝试唤醒排队/挂起任务！')
    await loadTasks()
  } catch (err: any) {
    message.error(err.message || '标记完成失败')
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.adaptive-task-queue-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-card,
.tasks-table-card {
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

.text-success {
  color: #16a34a;
}

.text-blue {
  color: #2563eb;
}

.text-orange {
  color: #ea580c;
}

.text-muted {
  color: #94a3b8;
}

.eta-alert {
  border-radius: 6px;
}

.task-title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-id {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
  font-family: monospace;
}

.status-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.preempted-tag {
  font-size: 10px;
  padding: 0 4px;
}

.worker-text {
  font-size: 11px;
  font-family: monospace;
  color: #334155;
}

.complete-btn {
  color: #16a34a;
}
</style>
