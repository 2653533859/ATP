<template>
  <div class="page-shell mesh-resilience-report-view">
    <!-- 页面头部 -->
    <header class="page-hero">
      <div class="hero-left">
        <h2 class="page-title">全链路微服务高可用 SLA 韧性评分报告</h2>
        <p class="page-subtitle">
          度量混沌故障演练期间各微服务的可用性 SLA 达成度、跌幅与自愈恢复耗时（RTO），输出四维加权微服务架构韧性得分与云原生加固指引。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-input
            v-model:value="experimentIdInput"
            placeholder="实验 ID (如: exp_mesh_01)"
            style="width: 200px"
          />
          <a-select v-model:value="slaBaselineInput" style="width: 130px">
            <a-select-option :value="99.9">基线 99.9%</a-select-option>
            <a-select-option :value="99.99">基线 99.99%</a-select-option>
            <a-select-option :value="99.0">基线 99.0%</a-select-option>
          </a-select>
          <a-button @click="loadSampleServices">
            载入典型网关演练样本
          </a-button>
          <a-button type="primary" :loading="compiling" @click="handleCompileReport">
            生成韧性报告
          </a-button>
        </a-space>
      </div>
    </header>

    <div v-if="report" class="report-content">
      <!-- 韧性评分与评级总览卡片 -->
      <a-card size="small" class="score-card">
        <div class="score-grid">
          <!-- 左侧：总分与等级 -->
          <div class="main-score-box">
            <span class="score-lbl">全链路微服务架构韧性总分</span>
            <div class="score-number-row">
              <span class="big-score" :class="getScoreColorClass(report.summary.resilience_score)">
                {{ report.summary.resilience_score }}
              </span>
              <span class="score-max">/ 100</span>
              <a-tag :color="getGradeColor(report.summary.resilience_grade)" class="grade-tag">
                Grade {{ report.summary.resilience_grade }}
              </a-tag>
            </div>
            <div class="status-tags">
              <a-tag v-if="!report.summary.blast_radius_breached" color="success">
                爆炸半径未违约
              </a-tag>
              <a-tag v-else color="error">
                爆炸半径已违约
              </a-tag>

              <a-tag v-if="report.summary.emergency_aborted" color="red">
                已触发紧急熔断
              </a-tag>
            </div>
          </div>

          <!-- 中间：短板服务与评估指标 -->
          <div class="weakest-box">
            <div class="kpi-mini">
              <span class="kpi-lbl">全链路最薄弱短板微服务 (Weakest Link)</span>
              <strong class="kpi-val text-danger">
                {{ report.summary.lowest_sla_service || '无明显短板' }}
              </strong>
              <small class="kpi-hint">
                最低可用性 SLA: <strong>{{ report.summary.lowest_sla_percent }}%</strong>
              </small>
            </div>

            <div class="kpi-mini" style="margin-top: 10px;">
              <span class="kpi-lbl">评估受损微服务节点总数</span>
              <strong class="kpi-val">
                {{ report.summary.total_services_evaluated }} 个微服务
              </strong>
            </div>
          </div>

          <!-- 右侧：云原生架构加固建议 -->
          <div class="recommendation-box">
            <span class="rec-lbl">云原生韧性加固与容灾建议:</span>
            <div class="rec-text-card">
              <p class="rec-text">{{ report.summary.recommendation }}</p>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 四维加权细分指标 -->
      <div class="dimension-row">
        <div class="dim-card">
          <span class="dim-label">可用性 SLA 达成度 (40% 权重)</span>
          <div class="dim-val-box">
            <strong>{{ avgSlaPct }}%</strong>
            <small class="dim-hint">各服务平均成功率</small>
          </div>
        </div>

        <div class="dim-card">
          <span class="dim-label">故障自愈 RTO 时效 (30% 权重)</span>
          <div class="dim-val-box">
            <strong>{{ avgRtoSec }} 秒</strong>
            <small class="dim-hint">平均自愈恢复用时</small>
          </div>
        </div>

        <div class="dim-card">
          <span class="dim-label">爆炸半径约束控制力 (20% 权重)</span>
          <div class="dim-val-box">
            <strong :class="report.summary.blast_radius_breached ? 'text-danger' : 'text-success'">
              {{ report.summary.blast_radius_breached ? '已越界 (扣分)' : '安全受控 (满分)' }}
            </strong>
            <small class="dim-hint">级联传导扩散约束</small>
          </div>
        </div>

        <div class="dim-card">
          <span class="dim-label">峰值错误容忍度 (10% 权重)</span>
          <div class="dim-val-box">
            <strong>{{ maxDropPct }}%</strong>
            <small class="dim-hint">最大 SLA 下跌幅度</small>
          </div>
        </div>
      </div>

      <!-- 微服务级可用性与跌幅明细表格 -->
      <a-card size="small" title="微服务级可用性 SLA 达成度与自愈明细" class="services-table-card">
        <a-table
          :data-source="report.services"
          :columns="serviceColumns"
          row-key="service_name"
          size="small"
          :pagination="{ pageSize: 8 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'service_name'">
              <strong>{{ record.service_name }}</strong>
            </template>

            <template v-if="column.key === 'requests'">
              <span>{{ record.total_requests - record.failed_requests }} / {{ record.total_requests }}</span>
            </template>

            <template v-if="column.key === 'sla'">
              <a-space>
                <strong :class="record.availability_sla_pct >= record.sla_baseline_target ? 'text-success' : 'text-danger'">
                  {{ record.availability_sla_pct }}%
                </strong>
                <a-tag :color="getStatusTagColor(record.degradation_status)">
                  {{ getStatusLabel(record.degradation_status) }}
                </a-tag>
              </a-space>
            </template>

            <template v-if="column.key === 'drop'">
              <span :class="record.sla_drop_pct > 0 ? 'text-danger' : 'text-muted'">
                {{ record.sla_drop_pct > 0 ? `-${record.sla_drop_pct}%` : '0%' }}
              </span>
            </template>

            <template v-if="column.key === 'latency'">
              <span>P95: {{ record.p95_latency_ms }} ms</span>
            </template>

            <template v-if="column.key === 'rto'">
              <a-tag color="blue">{{ record.recovery_time_seconds }} 秒自愈</a-tag>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <a-empty v-else description="暂未生成报告，请在上方输入实验 ID 并点击「生成韧性报告」" class="empty-holder" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { meshChaosApi } from '@/api/meshChaos'

const experimentIdInput = ref('exp_mesh_resilience_01')
const slaBaselineInput = ref(99.9)
const compiling = ref(false)

const sampleServicesData = [
  {
    service_name: 'api-gateway',
    total_requests: 2500,
    failed_requests: 5,
    avg_latency_ms: 35.0,
    p95_latency_ms: 80.0,
    recovery_time_seconds: 1.2,
  },
  {
    service_name: 'order-service',
    total_requests: 2000,
    failed_requests: 12,
    avg_latency_ms: 45.0,
    p95_latency_ms: 110.0,
    recovery_time_seconds: 2.5,
  },
  {
    service_name: 'pay-service',
    total_requests: 1500,
    failed_requests: 95,
    avg_latency_ms: 120.0,
    p95_latency_ms: 380.0,
    recovery_time_seconds: 6.8,
  },
  {
    service_name: 'inventory-service',
    total_requests: 1800,
    failed_requests: 2,
    avg_latency_ms: 30.0,
    p95_latency_ms: 65.0,
    recovery_time_seconds: 1.0,
  },
]

const report = ref<any | null>(null)

const serviceColumns = [
  { title: '微服务名称', key: 'service_name', width: 170 },
  { title: '成功 / 总请求数', key: 'requests', width: 150 },
  { title: '可用性 SLA 与状态', key: 'sla', width: 190 },
  { title: '基线跌幅', key: 'drop', width: 110 },
  { title: '耗时百分位 (P95)', key: 'latency', width: 140 },
  { title: '故障自愈耗时 (RTO)', key: 'rto', width: 140 },
]

const avgSlaPct = computed(() => {
  if (!report.value?.services?.length) return 100
  const total = report.value.services.reduce((acc: number, s: any) => acc + s.availability_sla_pct, 0)
  return (total / report.value.services.length).toFixed(2)
})

const avgRtoSec = computed(() => {
  if (!report.value?.services?.length) return 0
  const total = report.value.services.reduce((acc: number, s: any) => acc + s.recovery_time_seconds, 0)
  return (total / report.value.services.length).toFixed(1)
})

const maxDropPct = computed(() => {
  if (!report.value?.services?.length) return 0
  const max = Math.max(...report.value.services.map((s: any) => s.sla_drop_pct))
  return max.toFixed(2)
})

function getScoreColorClass(score: number): string {
  if (score >= 90) return 'text-success'
  if (score >= 80) return 'text-blue'
  if (score >= 65) return 'text-amber'
  return 'text-danger'
}

function getGradeColor(grade: string): string {
  switch (grade) {
    case 'A':
      return 'green'
    case 'B':
      return 'blue'
    case 'C':
      return 'orange'
    default:
      return 'red'
  }
}

function getStatusTagColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'green'
    case 'minor_degraded':
      return 'orange'
    case 'severely_degraded':
      return 'red'
    case 'outage':
      return 'purple'
    default:
      return 'default'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'healthy':
      return '健康稳定'
    case 'minor_degraded':
      return '轻度受损'
    case 'severely_degraded':
      return '严重降级'
    case 'outage':
      return '宕机熔断'
    default:
      return status
  }
}

function loadSampleServices() {
  message.success('已载入 4 组微服务混沌演练样本数据！')
  handleCompileReport()
}

async function handleCompileReport() {
  compiling.value = true
  try {
    const res = await meshChaosApi.compileResilienceReport({
      experiment_id: experimentIdInput.value.trim() || 'exp_mesh_resilience_01',
      services_data: sampleServicesData,
      sla_baseline_target: slaBaselineInput.value,
      blast_radius_breached: false,
      emergency_aborted: false,
    })
    report.value = res
    message.success('全链路微服务高可用 SLA 韧性评分报告已生成！')
  } catch (err: any) {
    message.error(err.message || '生成韧性报告失败')
  } finally {
    compiling.value = false
  }
}

onMounted(() => {
  handleCompileReport()
})
</script>

<style scoped>
.mesh-resilience-report-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.page-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  max-width: 650px;
}

.score-card,
.services-table-card {
  border-radius: 8px;
}

.score-grid {
  display: grid;
  grid-template-columns: 280px 300px 1fr;
  gap: 20px;
  align-items: center;
}

.main-score-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-right: 1px solid var(--c-border, #f1f5f9);
  padding-right: 16px;
}

.score-lbl {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.score-number-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.big-score {
  font-size: 38px;
  font-weight: 700;
  line-height: 1;
}

.score-max {
  font-size: 14px;
  color: #94a3b8;
}

.grade-tag {
  font-size: 13px;
  padding: 2px 8px;
  font-weight: 600;
}

.status-tags {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.weakest-box {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--c-border, #f1f5f9);
  padding-right: 16px;
}

.kpi-mini {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-lbl {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-val {
  font-size: 15px;
}

.kpi-hint {
  font-size: 11px;
  color: #64748b;
}

.recommendation-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rec-lbl {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #64748b);
}

.rec-text-card {
  padding: 10px 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.rec-text {
  margin: 0;
  font-size: 12px;
  color: #334155;
  line-height: 1.6;
}

.dimension-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.dim-card {
  padding: 12px 14px;
  background: var(--c-bg-surface, #fff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.dim-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  display: block;
  margin-bottom: 4px;
}

.dim-val-box {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.dim-val-box strong {
  font-size: 18px;
  color: var(--c-text, #0f172a);
}

.dim-hint {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.text-success {
  color: #16a34a;
}

.text-blue {
  color: #2563eb;
}

.text-amber {
  color: #d97706;
}

.text-danger {
  color: #dc2626;
}

.text-muted {
  color: #94a3b8;
}

.empty-holder {
  margin-top: 40px;
}
</style>
