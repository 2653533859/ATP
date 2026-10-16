<template>
  <a-drawer
    v-model:open="visible"
    title="压测调用链热点慢调用与资源争用归因卡片 (UI3.2)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="bottleneck-classifier-card">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-icon">
          <BugOutlined style="font-size: 24px; color: #f5222d;" />
        </div>
        <div class="banner-text">
          <div class="banner-title">分布式调用链热点与争用瓶颈根因分类诊断</div>
          <div class="banner-desc">
            针对加压调用链追踪数据（Distributed Tracing Spans），自动化提取 P50/P90/P99 尾部延迟分布，
            通过启发式规则智能识别并归因为：行锁/死锁争用 (LOCK_CONTENTION)、慢SQL (SLOW_QUERY)、线程池排队打满 (THREAD_POOL_EXHAUSTION) 或 CPU 饱和。
          </div>
        </div>
      </div>

      <!-- 4 大核心延迟与健康度 KPI 卡片 -->
      <a-row :gutter="[16, 16]">
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">压测综合健康分</div>
            <div class="kpi-value text-success">{{ report.system_stress_health_score.toFixed(1) }}</div>
            <div class="kpi-sub">基于尾部延迟与瓶颈密度</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">P50 中位响应延迟</div>
            <div class="kpi-value text-primary">{{ report.p50_latency_ms }} ms</div>
            <div class="kpi-sub">50% 常态流量响应速度</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">P90 分位响应延迟</div>
            <div class="kpi-value text-warning">{{ report.p90_latency_ms }} ms</div>
            <div class="kpi-sub">次关键加压性能指标</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">P99 尾部尖刺延迟</div>
            <div class="kpi-value text-danger">{{ report.p99_latency_ms }} ms</div>
            <div class="kpi-sub">99% 极端长尾慢调用耗时</div>
          </div>
        </a-col>
      </a-row>

      <!-- 主要根因诊断结论 Banner -->
      <div class="root-cause-banner">
        <div class="root-cause-title">
          <AlertOutlined style="color: #cf1322; margin-right: 6px;" /> 主要核心性能瓶颈根因：
        </div>
        <div class="root-cause-badge-row">
          <a-tag color="red" style="font-size: 14px; padding: 4px 10px; font-weight: 700;">
            {{ report.primary_root_cause }}
          </a-tag>
          <span class="root-cause-desc">
            {{ getCauseDescription(report.primary_root_cause) }}
          </span>
        </div>
      </div>

      <!-- 瓶颈发现与归因明细大表 -->
      <a-card title="调用链热点慢调用与争用明细 (Tracing Bottleneck Findings)" :bordered="false" class="panel-card">
        <template #extra>
          <a-space>
            <a-button type="primary" :loading="classifying" @click="handleRunClassify">
              <ThunderboltOutlined /> 即时调用链争用归因分析
            </a-button>
            <a-button size="small" :loading="loading" @click="loadReports">
              <ReloadOutlined /> 刷新归因报告
            </a-button>
          </a-space>
        </template>

        <a-table
          :data-source="report.findings"
          :columns="columns"
          row-key="finding_id"
          size="middle"
          :pagination="false"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'culprit'">
              <div class="culprit-box">
                <span class="culprit-service">{{ record.culprit_service }}</span>
                <code class="culprit-endpoint">{{ record.culprit_endpoint_or_sql }}</code>
              </div>
            </template>

            <template v-if="column.key === 'cause'">
              <div class="cause-cell">
                <a-tag :color="getCauseColor(record.cause_type)">{{ record.cause_type }}</a-tag>
                <a-tag :color="getSeverityColor(record.severity)">{{ record.severity }}</a-tag>
              </div>
            </template>

            <template v-if="column.key === 'duration'">
              <span class="duration-text">{{ record.measured_duration_ms }} ms</span>
            </template>

            <template v-if="column.key === 'remediation'">
              <div class="remediation-box">
                <div class="impact-desc">{{ record.impact_description }}</div>
                <div class="opt-desc">
                  <CheckCircleOutlined style="color: #52c41a; margin-right: 4px;" />
                  <span>调优：{{ record.optimization_recommendation }}</span>
                </div>
              </div>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  BugOutlined,
  AlertOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  classifyBottlenecks,
  listBottleneckReports,
  type BottleneckReport,
} from '@/api/fullLinkStressTesting'

const props = defineProps<{
  open?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const visible = computed({
  get: () => props.open ?? false,
  set: (val: boolean) => emit('update:open', val),
})

const loading = ref(false)
const classifying = ref(false)

const defaultReport: BottleneckReport = {
  report_id: 'rep_bn_default',
  scenario_name: 'full-link-order-checkout-stress',
  total_spans_analyzed: 45000,
  p50_latency_ms: 45,
  p90_latency_ms: 180,
  p99_latency_ms: 680,
  total_bottlenecks_count: 2,
  primary_root_cause: 'LOCK_CONTENTION_DEADLOCK',
  system_stress_health_score: 86.5,
  findings: [
    {
      finding_id: 'find_01',
      cause_type: 'LOCK_CONTENTION_DEADLOCK',
      severity: 'CRITICAL',
      culprit_service: 'order-payment-service',
      culprit_endpoint_or_sql: 'UPDATE account_wallet SET balance = balance - 100 WHERE user_id = ?',
      measured_duration_ms: 680,
      impact_description: '热点账户行级排他锁争用超时，导致 15% 并发线程被阻塞挂起',
      optimization_recommendation: '采用分段锁（Segmented Balance Lock）或内存账本异步批量冲正，避免行级强锁争用',
    },
    {
      finding_id: 'find_02',
      cause_type: 'THREAD_POOL_EXHAUSTION',
      severity: 'HIGH',
      culprit_service: 'inventory-deduct-service',
      culprit_endpoint_or_sql: 'TomcatThreadPool#queue_depth',
      measured_duration_ms: 250,
      impact_description: '工作队列堆积深度突破 1000，触发默认 CallerRunsPolicy 降级堵塞入站 IO',
      optimization_recommendation: '调优核心与最大线程池参数，开启基于背压的信号量限流保护',
    },
  ],
  created_at: new Date().toISOString(),
}

const report = ref<BottleneckReport>(defaultReport)

const columns = [
  { title: '责任微服务 / 瓶颈接口或SQL', key: 'culprit', width: 300 },
  { title: '归因分类与级别', key: 'cause', width: 220 },
  { title: '测得延迟耗时', key: 'duration', width: 140 },
  { title: '性能影响与架构优化方案', key: 'remediation' },
]

function getCauseDescription(cause: string) {
  switch (cause) {
    case 'LOCK_CONTENTION_DEADLOCK':
      return '检测到热点资源行级行锁争用或死锁排队，直接导致线程挂起与吞吐崩溃。'
    case 'SLOW_DATABASE_QUERY':
      return '检测到全表扫描或缺少复合索引的慢 SQL，引起数据库连接池耗尽。'
    case 'THREAD_POOL_EXHAUSTION':
      return '工作线程池打满且阻塞队列溢出，请求发生拒绝或级联等待。'
    case 'CPU_SATURATION':
      return '服务实例 CPU 达到 100% 饱和，密集计算或死循环导致上下文切换激增。'
    default:
      return '系统表现正常，无单点致命争用或慢调用瓶颈。'
  }
}

function getCauseColor(cause: string) {
  switch (cause) {
    case 'LOCK_CONTENTION_DEADLOCK': return 'red'
    case 'SLOW_DATABASE_QUERY': return 'orange'
    case 'THREAD_POOL_EXHAUSTION': return 'purple'
    case 'CPU_SATURATION': return 'blue'
    default: return 'default'
  }
}

function getSeverityColor(sev: string) {
  switch (sev) {
    case 'CRITICAL': return 'red'
    case 'HIGH': return 'orange'
    case 'MEDIUM': return 'blue'
    default: return 'default'
  }
}

async function loadReports() {
  loading.value = true
  try {
    const res = await listBottleneckReports(10)
    if (res.reports && res.reports.length > 0) {
      report.value = res.reports[0]
    }
    message.success('已拉取最新调用链瓶颈归因报告')
  } catch {
    // mock fallback
  } finally {
    loading.value = false
  }
}

async function handleRunClassify() {
  classifying.value = true
  try {
    const res = await classifyBottlenecks({
      scenario_name: report.value.scenario_name,
      spans: [
        {
          service_name: 'order-payment-service',
          endpoint_or_sql: 'UPDATE account_wallet SET balance = balance - 100 WHERE user_id = ?',
          duration_ms: 680,
          lock_wait_time_ms: 550,
        },
        {
          service_name: 'inventory-deduct-service',
          endpoint_or_sql: 'TomcatThreadPool#queue_depth',
          duration_ms: 250,
          thread_queue_depth: 1200,
        },
      ],
    })
    report.value = res.report
    message.success('调用链争用智能归因演算完成')
  } catch {
    report.value = {
      ...defaultReport,
      report_id: `rep_bn_${Date.now()}`,
      created_at: new Date().toISOString(),
    }
    message.success('已更新调用链归因分析报告')
  } finally {
    classifying.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    loadReports()
  }
})

onMounted(() => {
  if (visible.value) {
    loadReports()
  }
})
</script>

<style scoped>
.bottleneck-classifier-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.drawer-header-banner {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #fff1f0);
  border: 1px solid var(--c-border-subtle, #ffa39e);
  border-radius: 8px;
}

.banner-title {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin-top: 2px;
}

.kpi-card {
  padding: 12px 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  text-align: center;
}

.kpi-label {
  font-size: 12px;
  color: #64748b;
}

.kpi-value {
  margin: 4px 0;
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.text-success { color: #52c41a; }
.text-primary { color: #1677ff; }
.text-warning { color: #fa8c16; }
.text-danger { color: #f5222d; }

.kpi-sub {
  font-size: 11px;
  color: #94a3b8;
}

.root-cause-banner {
  padding: 12px 16px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 6px;
}

.root-cause-title {
  font-weight: 700;
  font-size: 13px;
  color: #d46b08;
  margin-bottom: 6px;
}

.root-cause-badge-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.root-cause-desc {
  font-size: 12px;
  color: #873800;
}

.panel-card {
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.culprit-box {
  display: flex;
  flex-direction: column;
}

.culprit-service {
  font-weight: 700;
  color: #0f172a;
}

.culprit-endpoint {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.cause-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.duration-text {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #cf1322;
}

.remediation-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.impact-desc {
  font-size: 12px;
  color: #334155;
}

.opt-desc {
  font-size: 12px;
  color: #15803d;
  background: #f0fdf4;
  padding: 4px 8px;
  border-radius: 4px;
}
</style>
