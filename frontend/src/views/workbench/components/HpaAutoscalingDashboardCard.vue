<template>
  <a-card size="small" class="hpa-autoscaling-card">
    <template #title>
      <div class="card-title-box">
        <span class="card-title-text">任务队列背压自适应 HPA 自动扩缩容看板</span>
        <a-tag v-if="lastDecision?.direction === 'scale_up'" color="green">建议扩容 (+{{ lastDecision.replicas_delta }})</a-tag>
        <a-tag v-else-if="lastDecision?.direction === 'scale_down'" color="orange">建议缩容 ({{ lastDecision.replicas_delta }})</a-tag>
        <a-tag v-else-if="lastDecision" color="blue">维持现状 (Maintain)</a-tag>
      </div>
    </template>

    <template #extra>
      <a-space size="small">
        <a-button
          type="primary"
          size="small"
          :loading="evaluating"
          @click="handleEvaluateHpa"
        >
          评估扩缩容决策
        </a-button>
        <a-button size="small" :loading="loading" @click="loadPolicies">
          刷新策略
        </a-button>
      </a-space>
    </template>

    <div class="hpa-card-body">
      <!-- 策略配置与说明 -->
      <div class="hpa-policy-box">
        <p class="description">
          实时采集任务队列积压深度（Queue Depth）与历史 P95 排队时延，基于单 Pod 承载力与时延 SLO 惩罚因子计算目标副本数；配备 60 秒缩容防震荡平滑冷却窗口。
        </p>

        <!-- 策略参数表单 -->
        <a-form layout="inline" class="hpa-inline-form">
          <a-form-item label="策略 ID">
            <a-input v-model:value="policyId" size="small" style="width: 130px" />
          </a-form-item>

          <a-form-item label="监控队列">
            <a-select v-model:value="targetQueue" size="small" style="width: 100px">
              <a-select-option value="default">default</a-select-option>
              <a-select-option value="performance">performance</a-select-option>
              <a-select-option value="api">api</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="保底~上限副本">
            <a-input-number v-model:value="minReplicas" :min="1" :max="20" size="small" style="width: 55px" />
            <span class="range-sep">~</span>
            <a-input-number v-model:value="maxReplicas" :min="minReplicas" :max="100" size="small" style="width: 60px" />
          </a-form-item>

          <a-form-item label="单Pod承载">
            <a-input-number v-model:value="concurrencyPerPod" :min="1" size="small" style="width: 55px" />
            <span class="unit-text">并发</span>
          </a-form-item>

          <a-form-item label="时延SLO">
            <a-input-number v-model:value="latencySloSec" :min="1" size="small" style="width: 55px" />
            <span class="unit-text">秒</span>
          </a-form-item>

          <a-form-item>
            <a-button type="primary" size="small" :loading="saving" @click="handleSavePolicy">
              保存策略
            </a-button>
          </a-form-item>
        </a-form>
      </div>

      <!-- 实时背压输入模拟栏 -->
      <div class="simulation-bar">
        <span class="bar-label">实时队列背压输入模拟：</span>
        <a-space size="small" wrap>
          <span>排队积压:</span>
          <a-input-number v-model:value="simQueueDepth" :min="0" size="small" style="width: 65px" />
          <span>运行中:</span>
          <a-input-number v-model:value="simRunningTasks" :min="0" size="small" style="width: 65px" />
          <span>P95时延:</span>
          <a-input-number v-model:value="simP95Latency" :min="0" :step="0.5" size="small" style="width: 70px" />
          <span>秒</span>
          <span>当前副本:</span>
          <a-input-number v-model:value="simCurrentReplicas" :min="1" size="small" style="width: 60px" />
        </a-space>
      </div>

      <!-- 扩缩容决策结果横幅 -->
      <div v-if="lastDecision" class="decision-result-section">
        <a-alert
          :type="getDecisionAlertType(lastDecision.direction)"
          show-icon
          class="decision-alert"
          :message="`[HPA 扩缩容决策 #${lastDecision.decision_id}] 推荐动作: ${getDirectionLabel(lastDecision.direction)}`"
          :description="lastDecision.reason"
        />

        <!-- 决策核心 KPI -->
        <div class="kpi-row">
          <div class="kpi-item">
            <span class="kpi-label">当前运行副本</span>
            <strong class="kpi-val">{{ lastDecision.current_replicas }}</strong>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">目标期望副本 (Desired)</span>
            <strong class="kpi-val text-blue">{{ lastDecision.desired_replicas }}</strong>
          </div>

          <div class="kpi-item">
            <span class="kpi-label">副本增减差值 (Delta)</span>
            <strong :class="lastDecision.replicas_delta > 0 ? 'text-green' : lastDecision.replicas_delta < 0 ? 'text-orange' : 'text-slate'" class="kpi-val">
              {{ lastDecision.replicas_delta > 0 ? `+${lastDecision.replicas_delta}` : lastDecision.replicas_delta }}
            </strong>
          </div>

          <div class="kpi-item apply-action-item">
            <a-button
              type="primary"
              :danger="lastDecision.direction === 'scale_down'"
              :disabled="lastDecision.direction === 'maintain'"
              :loading="applying"
              size="small"
              @click="handleApplyScaling"
            >
              一键应用扩缩容联动
            </a-button>
          </div>
        </div>
      </div>

      <!-- 历史决策台账表格 -->
      <div v-if="historyList.length > 0" class="history-table-box">
        <h5 class="sub-table-title">近期 HPA 自适应扩缩容决策台账流水：</h5>
        <a-table
          :data-source="historyList"
          :columns="historyColumns"
          row-key="decision_id"
          size="small"
          :pagination="{ pageSize: 4 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'direction'">
              <a-tag :color="getDirectionColor(record.direction)">
                {{ getDirectionLabel(record.direction) }}
              </a-tag>
            </template>
            <template v-if="column.key === 'delta'">
              <strong>{{ record.replicas_delta > 0 ? `+${record.replicas_delta}` : record.replicas_delta }}</strong>
            </template>
            <template v-if="column.key === 'evaluated_at'">
              <span class="time-text">{{ record.evaluated_at }}</span>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  hpaAutoscalingApi,
  type HpaEvaluationDecisionItem,
  type HpaScalingDirection,
} from '@/api/cloudNativeWorkers'

const loading = ref(false)
const saving = ref(false)
const evaluating = ref(false)
const applying = ref(false)

const policyId = ref('hpa_default_queue')
const targetQueue = ref('default')
const minReplicas = ref(1)
const maxReplicas = ref(20)
const concurrencyPerPod = ref(5)
const latencySloSec = ref(15.0)

// 模拟背压输入
const simQueueDepth = ref(25)
const simRunningTasks = ref(5)
const simP95Latency = ref(25.0)
const simCurrentReplicas = ref(2)

const lastDecision = ref<HpaEvaluationDecisionItem | null>(null)
const historyList = ref<HpaEvaluationDecisionItem[]>([])

const historyColumns = [
  { title: '决策 ID', dataIndex: 'decision_id', key: 'decision_id', width: 140 },
  { title: '扩缩方向', key: 'direction', width: 110 },
  { title: '当前/期望副本', dataIndex: 'desired_replicas', key: 'desired_replicas', width: 120 },
  { title: '副本差值', key: 'delta', width: 90 },
  { title: '决策原因', dataIndex: 'reason', key: 'reason' },
  { title: '评估时间', key: 'evaluated_at', width: 160 },
]

function getDirectionColor(dir: HpaScalingDirection): string {
  switch (dir) {
    case 'scale_up':
      return 'green'
    case 'scale_down':
      return 'orange'
    case 'maintain':
      return 'blue'
    default:
      return 'default'
  }
}

function getDirectionLabel(dir: HpaScalingDirection): string {
  switch (dir) {
    case 'scale_up':
      return '弹性扩容 (Scale Up)'
    case 'scale_down':
      return '弹性缩容 (Scale Down)'
    case 'maintain':
      return '维持现状 (Maintain)'
    default:
      return dir
  }
}

function getDecisionAlertType(dir: HpaScalingDirection): 'success' | 'warning' | 'info' {
  switch (dir) {
    case 'scale_up':
      return 'success'
    case 'scale_down':
      return 'warning'
    default:
      return 'info'
  }
}

async function loadPolicies() {
  loading.value = true
  try {
    const res = await hpaAutoscalingApi.listPolicies()
    if (res.policies.length > 0) {
      const p = res.policies[0]
      policyId.value = p.policy_id
      targetQueue.value = p.target_queue
      minReplicas.value = p.min_replicas
      maxReplicas.value = p.max_replicas
      concurrencyPerPod.value = p.target_concurrency_per_pod
      latencySloSec.value = p.target_latency_slo_sec
    }
    await loadHistory()
  } catch (err: any) {
    message.error(err.message || '获取 HPA 策略失败')
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    const res = await hpaAutoscalingApi.listHistory(policyId.value)
    historyList.value = res.history
  } catch (err: any) {
    // 忽略初次历史加载非阻塞错误
  }
}

async function handleSavePolicy() {
  saving.value = true
  try {
    await hpaAutoscalingApi.createPolicy({
      policy_id: policyId.value,
      target_queue: targetQueue.value,
      min_replicas: minReplicas.value,
      max_replicas: maxReplicas.value,
      target_concurrency_per_pod: concurrencyPerPod.value,
      target_latency_slo_sec: latencySloSec.value,
    })
    message.success('HPA 自动扩缩容策略保存成功！')
  } catch (err: any) {
    message.error(err.message || '保存 HPA 策略失败')
  } finally {
    saving.value = false
  }
}

async function handleEvaluateHpa() {
  evaluating.value = true
  try {
    const res = await hpaAutoscalingApi.evaluateHpa({
      policy_id: policyId.value,
      current_queue_depth: simQueueDepth.value,
      running_tasks_count: simRunningTasks.value,
      p95_queue_latency_sec: simP95Latency.value,
      current_replicas: simCurrentReplicas.value,
    })
    lastDecision.value = res
    message.success(`HPA 决策完成：建议 ${getDirectionLabel(res.direction)}！`)
    await loadHistory()
  } catch (err: any) {
    message.error(err.message || 'HPA 决策评估失败')
  } finally {
    evaluating.value = false
  }
}

async function handleApplyScaling() {
  if (!lastDecision.value) return
  applying.value = true
  try {
    const res = await hpaAutoscalingApi.applyScaling({
      decision_id: lastDecision.value.decision_id,
      policy_id: lastDecision.value.policy_id,
      direction: lastDecision.value.direction,
      replicas_delta: lastDecision.value.replicas_delta,
      target_queue: targetQueue.value,
    })
    message.success(`扩缩容执行完成！${res.executed_actions.join('；') || '已同步至集群'}`)
    simCurrentReplicas.value = lastDecision.value.desired_replicas
  } catch (err: any) {
    message.error(err.message || '应用扩缩容失败')
  } finally {
    applying.value = false
  }
}

onMounted(() => {
  loadPolicies()
})
</script>

<style scoped>
.hpa-autoscaling-card {
  border-radius: 8px;
  margin-top: 14px;
}

.card-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-title-text {
  font-size: 14px;
  font-weight: 600;
}

.hpa-card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.description {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.hpa-inline-form {
  margin-bottom: 6px;
}

.range-sep {
  margin: 0 4px;
  color: #94a3b8;
}

.unit-text {
  font-size: 11px;
  color: #64748b;
  margin-left: 4px;
}

.simulation-bar {
  background: var(--c-bg-subtle, #f8fafc);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--c-border, #e2e8f0);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-weight: 600;
  color: #334155;
}

.decision-result-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.decision-alert {
  border-radius: 6px;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
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
  color: #64748b;
}

.kpi-val {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.text-blue {
  color: #2563eb;
}

.text-green {
  color: #16a34a;
}

.text-orange {
  color: #ea580c;
}

.text-slate {
  color: #64748b;
}

.apply-action-item {
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-table-box {
  margin-top: 6px;
}

.sub-table-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 6px;
}

.time-text {
  font-size: 11px;
  color: #64748b;
}
</style>
