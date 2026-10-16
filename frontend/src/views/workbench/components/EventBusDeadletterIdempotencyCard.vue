<template>
  <div class="event-bus-guard-card">
    <!-- 头部机制与说明 Banner -->
    <div class="intro-banner">
      <div class="banner-top">
        <MailOutlined class="banner-icon" />
        <div class="banner-texts">
          <div class="banner-title">消息事件总线死信积压、消费延迟与幂等防线引擎 (T2.3)</div>
          <div class="banner-desc">
            面向异步事件驱动架构（Kafka / RabbitMQ / RocketMQ），实时监控消费者组消息延迟积压（Consumer Lag）；自动隔离超过重试上限的有毒消息至死信队列（DLQ）并支持一键重放；提供多轮并发重复投递压测，严格校验业务消费端幂等性（Idempotency Guard）。
          </div>
        </div>
      </div>
    </div>

    <!-- 三维功能选项卡 -->
    <a-tabs v-model:activeKey="activeTab" size="small" class="bus-tabs">
      <!-- Tab 1: 幂等消费重复投递压测 -->
      <a-tab-pane key="idempotency" tab="⚡ 幂等消费重复投递压测">
        <div class="tab-box">
          <div class="test-form">
            <a-space :size="12" align="center" wrap>
              <span class="field-lbl">目标 Topic:</span>
              <a-input v-model:value="idempotencyForm.topic" style="width: 180px" size="small" />

              <span class="field-lbl">业务唯一幂等凭证:</span>
              <a-input v-model:value="idempotencyForm.idempotency_key" placeholder="如 order_sku_9982" style="width: 200px" size="small" />

              <span class="field-lbl">重复投递轮次:</span>
              <a-input-number v-model:value="idempotencyForm.delivery_times" :min="2" :max="10" style="width: 70px" size="small" />
              <span class="unit-text">次</span>

              <a-button type="primary" size="small" :loading="testingIdempotency" @click="handleRunIdempotencyTest">
                <ThunderboltOutlined /> 发起多轮重复投递压测
              </a-button>
            </a-space>
          </div>

          <!-- 幂等压测裁决横幅 -->
          <div v-if="idempotencyReport" class="verdict-banner" :class="idempotencyReport.is_idempotent ? 'banner-ok' : 'banner-err'">
            <div class="verdict-head">
              <span class="status-tag" :class="idempotencyReport.is_idempotent ? 'tag-ok' : 'tag-err'">
                {{ idempotencyReport.is_idempotent ? '✅ 幂等防线达标 (IDEMPOTENT)' : '🚨 幂等性破坏 (MUTATION_LEAK)' }}
              </span>
              <span class="verdict-desc">{{ idempotencyReport.verdict_summary }}</span>
            </div>

            <div class="kpi-grid">
              <div class="kpi-card">
                <div class="kpi-val text-blue">{{ idempotencyReport.total_deliveries }} 次</div>
                <div class="kpi-lbl">重复投递总轮次</div>
              </div>
              <div class="kpi-card">
                <div class="kpi-val" :class="idempotencyReport.state_mutations_count === 1 ? 'text-green' : 'text-red'">
                  {{ idempotencyReport.state_mutations_count }} 次
                </div>
                <div class="kpi-lbl">底层实际状态写入次数 (标称严格为 1)</div>
              </div>
              <div class="kpi-card">
                <div class="kpi-val text-purple">{{ idempotencyReport.duplicate_suppressed_count }} 次</div>
                <div class="kpi-lbl">幂等拦截安全抑制次数</div>
              </div>
            </div>
          </div>
        </div>
      </a-tab-pane>

      <!-- Tab 2: Topic 消费延迟与消息积压监控 -->
      <a-tab-pane key="lag" tab="📊 Topic 消费延迟与积压监控">
        <div class="tab-box">
          <div class="tab-actions">
            <a-button size="small" :loading="loadingLag" @click="fetchLagMetrics">
              <ReloadOutlined /> 刷新消费积压指标
            </a-button>
          </div>

          <a-table
            :data-source="lagMetrics"
            :columns="lagColumns"
            row-key="topic"
            size="small"
            :pagination="false"
            bordered
            class="lag-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'topic'">
                <strong class="text-blue">{{ record.topic }}</strong>
              </template>

              <template v-if="column.key === 'consumer_group'">
                <a-tag>{{ record.consumer_group }}</a-tag>
              </template>

              <template v-if="column.key === 'current_lag'">
                <span :class="record.current_lag > 0 ? 'text-red font-bold' : 'text-green'">
                  {{ record.current_lag }} 消息
                </span>
              </template>

              <template v-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.lag_severity)">
                  {{ record.lag_severity }}
                </a-tag>
              </template>

              <template v-if="column.key === 'processing_time'">
                <span>{{ record.avg_processing_time_ms }} ms</span>
              </template>

              <template v-if="column.key === 'oldest_age'">
                <span>{{ record.oldest_unconsumed_age_sec }} 秒</span>
              </template>
            </template>
          </a-table>
        </div>
      </a-tab-pane>

      <!-- Tab 3: 死信队列管理与重放 -->
      <a-tab-pane key="dlq" tab="☠️ 死信队列 (DLQ) 隔离与重放">
        <div class="tab-box">
          <div class="tab-actions">
            <a-space>
              <a-button size="small" :loading="loadingDlq" @click="fetchDeadLetters">
                <ReloadOutlined /> 刷新死信队列
              </a-button>
              <span v-if="deadLetters.length > 0" class="dlq-alert">
                当前死信队列积压 <strong>{{ deadLetters.length }}</strong> 笔有毒消息！
              </span>
            </a-space>
          </div>

          <div v-if="deadLetters.length === 0" class="empty-dlq">
            <a-empty description="当前死信队列无积压有毒消息，所有事件消费平稳！" />
          </div>

          <a-table
            v-else
            :data-source="deadLetters"
            :columns="dlqColumns"
            row-key="message_id"
            size="small"
            :pagination="false"
            bordered
            class="dlq-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'message_id'">
                <code>{{ record.message_id }}</code>
              </template>

              <template v-if="column.key === 'topic'">
                <a-tag color="blue">{{ record.topic }}</a-tag>
              </template>

              <template v-if="column.key === 'retries'">
                <a-tag color="red">{{ record.retry_count }} / {{ record.max_retries }} 次</a-tag>
              </template>

              <template v-if="column.key === 'error'">
                <span class="text-red">{{ record.error_message }}</span>
              </template>

              <template v-if="column.key === 'action'">
                <a-button size="small" type="link" @click="handleRequeue(record.message_id)">
                  重放重新排队
                </a-button>
              </template>
            </template>
          </a-table>
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  MailOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  eventBusGuardApi,
  type IdempotencyVerificationReport,
  type TopicLagMetricItem,
  type EventMessageItem,
} from '@/api/distributedConsistency'

const activeTab = ref<'idempotency' | 'lag' | 'dlq'>('idempotency')
const testingIdempotency = ref(false)
const loadingLag = ref(false)
const loadingDlq = ref(false)

const idempotencyReport = ref<IdempotencyVerificationReport | null>(null)
const lagMetrics = ref<TopicLagMetricItem[]>([])
const deadLetters = ref<EventMessageItem[]>([])

const idempotencyForm = reactive({
  topic: 'order.events',
  idempotency_key: 'order_sku_9982',
  delivery_times: 3,
  consumer_group: 'order_consumer_group',
})

const lagColumns = [
  { title: 'Topic 名称', key: 'topic', width: 220 },
  { title: '消费者组 (Group)', key: 'consumer_group', width: 200 },
  { title: '当前未消费积压量', key: 'current_lag', width: 160 },
  { title: '积压健康度评级', key: 'severity', width: 140 },
  { title: '平均消费耗时', key: 'processing_time', width: 130 },
  { title: '最长未消费存活期', key: 'oldest_age' },
]

const dlqColumns = [
  { title: '死信消息 ID', key: 'message_id', width: 180 },
  { title: '所属 Topic', key: 'topic', width: 160 },
  { title: '重试超限次数', key: 'retries', width: 130 },
  { title: '有毒异常原因', key: 'error' },
  { title: '操作', key: 'action', width: 120 },
]

function getSeverityColor(s: string): string {
  switch (s) {
    case 'HEALTHY': return 'green'
    case 'WARNING': return 'orange'
    case 'CRITICAL_BACKLOG': return 'red'
    default: return 'blue'
  }
}

async function handleRunIdempotencyTest() {
  testingIdempotency.value = true
  try {
    const res = await eventBusGuardApi.verifyIdempotency({
      topic: idempotencyForm.topic,
      idempotency_key: idempotencyForm.idempotency_key,
      delivery_times: idempotencyForm.delivery_times,
      consumer_group: idempotencyForm.consumer_group,
    })
    idempotencyReport.value = res.report
    message.success(res.message || '幂等性压测完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '压测失败')
  } finally {
    testingIdempotency.value = false
  }
}

async function fetchLagMetrics() {
  loadingLag.value = true
  try {
    const res = await eventBusGuardApi.getLag()
    lagMetrics.value = res.metrics
  } catch {
    // ignore
  } finally {
    loadingLag.value = false
  }
}

async function fetchDeadLetters() {
  loadingDlq.value = true
  try {
    const res = await eventBusGuardApi.listDeadLetters()
    deadLetters.value = res.dead_letters
  } catch {
    // ignore
  } finally {
    loadingDlq.value = false
  }
}

async function handleRequeue(mid: string) {
  try {
    const res = await eventBusGuardApi.requeueDeadLetter(mid)
    message.success(res.message || '死信已重新入队排队')
    await fetchDeadLetters()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '重放失败')
  }
}

onMounted(() => {
  handleRunIdempotencyTest()
  fetchLagMetrics()
  fetchDeadLetters()
})
</script>

<style scoped>
.event-bus-guard-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intro-banner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
}

.banner-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 22px;
  color: #0284c7;
  margin-top: 2px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  margin-top: 4px;
}

.bus-tabs {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
}

.tab-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 6px;
}

.test-form {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
}

.field-lbl {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
  margin-left: -6px;
}

/* 裁决横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 14px 18px;
  border: 1px solid transparent;
}

.banner-ok {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.banner-err {
  background: #fef2f2;
  border-color: #fecaca;
}

.verdict-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.status-tag {
  font-size: 13px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
}

.tag-ok {
  background: #16a34a;
  color: #ffffff;
}

.tag-err {
  background: #dc2626;
  color: #ffffff;
}

.verdict-desc {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}

.kpi-val {
  font-size: 18px;
  font-weight: 800;
}

.kpi-lbl {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.text-blue {
  color: #0284c7;
}

.text-green {
  color: #16a34a;
}

.text-red {
  color: #dc2626;
}

.text-purple {
  color: #9333ea;
}

.font-bold {
  font-weight: 700;
}

.tab-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dlq-alert {
  font-size: 12px;
  color: #dc2626;
}

.empty-dlq {
  padding: 24px 0;
}

.lag-table,
.dlq-table {
  background: #ffffff;
}
</style>
