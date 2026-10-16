<template>
  <a-card size="small" class="worker-failover-recovery-card">
    <template #title>
      <div class="card-title-box">
        <span class="card-title-text">跨节点 Worker 失联检测与孤儿任务故障转移</span>
        <a-tag color="red" class="ha-tag">高可用容灾与熔断</a-tag>
      </div>
    </template>

    <template #extra>
      <a-space size="small">
        <span class="threshold-label">超时阈值:</span>
        <a-input-number
          v-model:value="heartbeatThreshold"
          :min="5"
          :max="300"
          size="small"
          style="width: 70px"
        />
        <span class="unit-label">秒</span>
        <a-button
          type="primary"
          danger
          size="small"
          :loading="scanning"
          @click="handleTriggerScan"
        >
          全网失联巡检 (Sweep Scan)
        </a-button>
        <a-button size="small" :loading="loading" @click="loadHistory">
          刷新
        </a-button>
      </a-space>
    </template>

    <div class="failover-card-body">
      <!-- 容灾说明与指标概览 -->
      <div class="overview-box">
        <p class="description">
          节点心跳超时（默认 ≥30 秒）即刻判定为失联下线；其承载的未完成孤儿任务由调度引擎原子性抢救重入队，指派至活跃存活节点重试；针对超过最大重试阈值（3次）的异常任务执行安全熔断终止，杜绝任务雪崩。
        </p>

        <!-- KPI 概览 -->
        <div class="kpi-row">
          <div class="kpi-item">
            <span class="kpi-label">累计巡检批次</span>
            <strong class="kpi-val">{{ historyList.length }}</strong>
          </div>
          <div class="kpi-item">
            <span class="kpi-label">最近巡检失联节点</span>
            <strong class="kpi-val text-red">{{ latestDeadWorkersCount }}</strong>
          </div>
          <div class="kpi-item">
            <span class="kpi-label">最近抢救重调度任务</span>
            <strong class="kpi-val text-green">{{ latestRecoveredTasksCount }}</strong>
          </div>
          <div class="kpi-item">
            <span class="kpi-label">最近熔断终止保护</span>
            <strong class="kpi-val text-orange">{{ latestAbortedTasksCount }}</strong>
          </div>
        </div>
      </div>

      <!-- 最新一轮巡检成果报告 -->
      <div v-if="latestReport" class="latest-report-section">
        <a-alert
          type="warning"
          show-icon
          class="report-alert"
          :message="`[巡检报告 #${latestReport.report_id}] 时间戳: ${latestReport.timestamp}`"
          :description="`扫描孤儿任务 ${latestReport.orphan_tasks_scanned} 个，标记失联节点 ${latestReport.dead_worker_ids.length} 个，成功抢救重新调度 ${latestReport.recovered_tasks.length} 个，熔断终止 ${latestReport.aborted_tasks.length} 个。`"
        />

        <!-- 失联节点标签池 -->
        <div v-if="latestReport.dead_worker_ids.length > 0" class="dead-nodes-pool">
          <span class="pool-title">已下线失联 Worker 节点：</span>
          <a-space wrap>
            <a-tag v-for="w in latestReport.dead_worker_ids" :key="w" color="red">
              {{ w }}
            </a-tag>
          </a-space>
        </div>

        <!-- 孤儿任务抢救明细 -->
        <div v-if="latestReport.recovered_tasks.length > 0" class="sub-table-block">
          <h5 class="sub-table-title">抢救重调度孤儿任务流水：</h5>
          <a-table
            :data-source="latestReport.recovered_tasks"
            :columns="recoveredColumns"
            row-key="task_id"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'action'">
                <a-tag color="green">重新分发中 (rescheduled)</a-tag>
              </template>
              <template v-if="column.key === 'retry'">
                <span>第 {{ record.retry_count }} / {{ record.max_retries }} 次重试</span>
              </template>
            </template>
          </a-table>
        </div>

        <!-- 熔断终止保护明细 -->
        <div v-if="latestReport.aborted_tasks.length > 0" class="sub-table-block">
          <h5 class="sub-table-title text-orange">超限安全熔断任务流水：</h5>
          <a-table
            :data-source="latestReport.aborted_tasks"
            :columns="abortedColumns"
            row-key="task_id"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'action'">
                <a-tag color="red">安全熔断终止 (aborted)</a-tag>
              </template>
              <template v-if="column.key === 'reason'">
                <span class="text-danger">{{ record.reason }}</span>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  clusterWorkersApi,
  type FailoverSummaryReport,
} from '@/api/clusterWorkers'

const loading = ref(false)
const scanning = ref(false)
const heartbeatThreshold = ref(30)
const historyList = ref<FailoverSummaryReport[]>([])
const latestReport = ref<FailoverSummaryReport | null>(null)

const recoveredColumns = [
  { title: '任务 ID', dataIndex: 'task_id', key: 'task_id', width: 220 },
  { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
  { title: '原失联 Worker', dataIndex: 'dead_worker_id', key: 'dead_worker_id', width: 180 },
  { title: '重试策略', key: 'retry', width: 140 },
  { title: '转移动作', key: 'action', width: 180 },
]

const abortedColumns = [
  { title: '任务 ID', dataIndex: 'task_id', key: 'task_id', width: 220 },
  { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
  { title: '原失联 Worker', dataIndex: 'dead_worker_id', key: 'dead_worker_id', width: 180 },
  { title: '熔断原因', key: 'reason', dataIndex: 'reason' },
  { title: '终止保护', key: 'action', width: 180 },
]

const latestDeadWorkersCount = computed(() => latestReport.value?.dead_worker_ids.length ?? 0)
const latestRecoveredTasksCount = computed(() => latestReport.value?.recovered_tasks.length ?? 0)
const latestAbortedTasksCount = computed(() => latestReport.value?.aborted_tasks.length ?? 0)

async function loadHistory() {
  loading.value = true
  try {
    const res = await clusterWorkersApi.listFailoverHistory()
    historyList.value = res.history
    if (res.history.length > 0 && !latestReport.value) {
      latestReport.value = res.history[res.history.length - 1]
    }
  } catch (err: any) {
    message.error(err.message || '获取故障转移历史失败')
  } finally {
    loading.value = false
  }
}

async function handleTriggerScan() {
  scanning.value = true
  try {
    const report = await clusterWorkersApi.triggerFailoverScan(heartbeatThreshold.value)
    latestReport.value = report
    if (report.dead_worker_ids.length > 0 || report.recovered_tasks.length > 0) {
      message.warning(`巡检完成：捕获 ${report.dead_worker_ids.length} 个失联节点，抢救 ${report.recovered_tasks.length} 个任务！`)
    } else {
      message.success('全网巡检完成：全集群 Worker 心跳健康，未检测到失联节点。')
    }
    await loadHistory()
  } catch (err: any) {
    message.error(err.message || '全网巡检执行失败')
  } finally {
    scanning.value = false
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.worker-failover-recovery-card {
  border-radius: 8px;
  margin-top: 14px;
}

.card-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title-text {
  font-size: 14px;
  font-weight: 600;
}

.ha-tag {
  font-size: 11px;
}

.threshold-label,
.unit-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.failover-card-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.description {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

.kpi-item {
  padding: 8px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-val {
  font-size: 16px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.text-red {
  color: #dc2626;
}

.text-green {
  color: #16a34a;
}

.text-orange {
  color: #ea580c;
}

.latest-report-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-alert {
  border-radius: 6px;
}

.dead-nodes-pool {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pool-title {
  color: #64748b;
}

.sub-table-block {
  margin-top: 4px;
}

.sub-table-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 6px;
}

.text-danger {
  color: #dc2626;
  font-size: 11px;
}
</style>
