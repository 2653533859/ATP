<template>
  <div class="trace-anomaly-card">
    <!-- 头部机制与说明 Banner -->
    <div class="intro-banner">
      <div class="banner-top">
        <SlidersOutlined class="banner-icon" />
        <div class="banner-texts">
          <div class="banner-title">分布式调用链异常波动与高频慢调用智能聚类诊断引擎 (T1.3)</div>
          <div class="banner-desc">
            从全网海量分布式 Trace 中智能识别分散的慢调用与错误，基于微服务签名与 <strong>5 大异常模式</strong>（慢数据库查询、网络超时熔断、下游 5xx 故障、断路器跳闸与耗时偏离）自动聚合归簇。引入 <strong>Z-Score 标准差偏离度 (σ)</strong> 与危害度加权模型，定位系统首要瓶颈并出具专家加固建议。
          </div>
        </div>
      </div>

      <!-- 快速演练场景 -->
      <div class="preset-row">
        <span class="preset-label">智能聚类演练场景:</span>
        <a-space :size="8" wrap>
          <a-button
            size="small"
            :type="presetKey === 'mixed' ? 'primary' : 'default'"
            danger
            @click="applyPreset('mixed')"
          >
            场景 1: 多维混合异常 (慢SQL 2次 + 超时 1次 + 正常过滤)
          </a-button>
          <a-button
            size="small"
            :type="presetKey === 'db_heavy' ? 'primary' : 'default'"
            @click="applyPreset('db_heavy')"
          >
            场景 2: 数据库高频慢查簇 (订单查询高频慢查, 偏离度 &gt;3.5σ)
          </a-button>
          <a-button
            size="small"
            :type="presetKey === 'healthy' ? 'primary' : 'default'"
            @click="applyPreset('healthy')"
          >
            场景 3: 全链路健康基线 (零异常)
          </a-button>
        </a-space>
      </div>

      <!-- 控制参数栏 -->
      <div class="action-row">
        <a-space :size="12" align="center" wrap>
          <span class="input-label">慢调用判定阈值:</span>
          <a-input-number
            v-model:value="slowThresholdMs"
            :min="10"
            :max="5000"
            style="width: 100px"
            size="small"
          />
          <span class="unit-text">ms</span>

          <a-button
            type="primary"
            size="small"
            :loading="analyzing"
            @click="runClusteringAnalysis"
          >
            <ThunderboltOutlined /> 执行场景聚类诊断
          </a-button>
          <a-button
            size="small"
            :loading="analyzingTelemetry"
            @click="runTelemetryDiagnosis"
          >
            <ReloadOutlined /> 全网已采集链路诊断
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 聚类态势大横幅 (Verdict Banner) -->
    <div v-if="report" class="verdict-banner" :class="report.clusters_count > 0 ? 'banner-has-clusters' : 'banner-clean'">
      <div class="verdict-head">
        <div class="verdict-status-box">
          <span class="status-badge" :class="report.clusters_count > 0 ? 'badge-alert' : 'badge-ok'">
            {{ report.clusters_count > 0 ? `🚨 检出 ${report.clusters_count} 个异常慢调用聚类簇` : '✅ 全链路表现健康' }}
          </span>
          <span class="verdict-summary">{{ report.verdict_summary }}</span>
        </div>
        <div class="meta-time">
          分析时间: {{ formatTime(report.analyzed_at) }}
        </div>
      </div>

      <!-- 3 项概览统计 KPI -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-val text-blue">{{ report.total_spans_analyzed }}</div>
          <div class="kpi-lbl">全量分析 Span 节点数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-red">{{ report.total_anomalies_detected }}</div>
          <div class="kpi-lbl">检出异常/慢调用频次</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-val text-purple">{{ report.clusters_count }}</div>
          <div class="kpi-lbl">收敛归属异常聚类簇</div>
        </div>
      </div>
    </div>

    <!-- 聚类簇明细表格 (Clusters Table) -->
    <div v-if="report" class="clusters-section">
      <div class="section-title">
        <span>慢调用特征聚类与危害度排行矩阵</span>
        <a-tag color="blue">按危害度得分 (Impact Score) 降序排列</a-tag>
      </div>

      <a-table
        :data-source="report.clusters"
        :columns="tableColumns"
        row-key="cluster_id"
        size="small"
        :pagination="false"
        bordered
        class="clusters-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'pattern'">
            <a-tag :color="getPatternColor(record.pattern)">
              {{ record.pattern }}
            </a-tag>
          </template>

          <template v-if="column.key === 'service_op'">
            <div class="svc-cell">
              <a-tag :color="getServiceTagColor(record.service_name)">{{ record.service_name }}</a-tag>
              <strong class="op-title">{{ record.operation_name }}</strong>
            </div>
          </template>

          <template v-if="column.key === 'duration_stats'">
            <div class="dur-stats-cell">
              <div>均值: <strong>{{ record.avg_duration_ms }} ms</strong> (P95: {{ record.p95_duration_ms }}ms)</div>
              <small class="max-dur">峰值: {{ record.max_duration_ms }} ms</small>
            </div>
          </template>

          <template v-if="column.key === 'deviation'">
            <a-tag :color="record.deviation_sigma >= 3.0 ? 'red' : record.deviation_sigma >= 1.5 ? 'orange' : 'default'">
              +{{ record.deviation_sigma }} σ 偏离
            </a-tag>
          </template>

          <template v-if="column.key === 'impact'">
            <div class="impact-cell">
              <span class="impact-num">{{ record.impact_score }}</span>
              <span class="occurrences">({{ record.occurrences_count }} 次)</span>
            </div>
          </template>

          <template v-if="column.key === 'recommendations'">
            <div class="remed-cell">
              <div class="cause-text">{{ record.root_cause_explanation }}</div>
              <ul v-if="record.actionable_recommendations.length" class="remed-list">
                <li v-for="(rec, idx) in record.actionable_recommendations" :key="idx">
                  {{ rec }}
                </li>
              </ul>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SlidersOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  traceAnomalyApi,
  type TraceAnomalyClusterReport,
} from '@/api/traceObservability'

const slowThresholdMs = ref(200)
const analyzing = ref(false)
const analyzingTelemetry = ref(false)
const report = ref<TraceAnomalyClusterReport | null>(null)
const presetKey = ref<'mixed' | 'db_heavy' | 'healthy'>('mixed')

const tableColumns = [
  { title: '异常模式', key: 'pattern', width: 180 },
  { title: '微服务与操作动作', key: 'service_op', width: 280 },
  { title: '耗时统计分布', key: 'duration_stats', width: 180 },
  { title: '统计偏离度 (Z-Score)', key: 'deviation', width: 150 },
  { title: '危害度得分', key: 'impact', width: 120 },
  { title: '根因推导与加固建议', key: 'recommendations' },
]

function getPatternColor(p: string): string {
  switch (p) {
    case 'TIMEOUT_BREACH': return 'red'
    case 'DOWNSTREAM_SERVICE_5XX': return 'volcano'
    case 'SLOW_DATABASE_QUERY': return 'purple'
    case 'CIRCUIT_BREAKER_OPEN': return 'orange'
    case 'HIGH_LATENCY_DEVIATION': return 'gold'
    default: return 'blue'
  }
}

function getServiceTagColor(svc: string): string {
  switch (svc) {
    case 'order-service': return 'orange'
    case 'pay-service': return 'red'
    case 'auth-service': return 'cyan'
    case 'inventory-service': return 'purple'
    default: return 'blue'
  }
}

function formatTime(t: string): string {
  if (!t) return ''
  return t.replace('T', ' ').substring(0, 19)
}

const PRESET_DATA = {
  mixed: [
    {
      trace_id: 't_m_1',
      span_id: 's_m_1',
      service_name: 'order-service',
      name: 'SELECT * FROM orders WHERE user_id = ?',
      duration_ms: 280.0,
      attributes: { 'db.system': 'mysql', 'db.statement': 'SELECT * FROM orders' },
    },
    {
      trace_id: 't_m_2',
      span_id: 's_m_2',
      service_name: 'order-service',
      name: 'SELECT * FROM orders WHERE user_id = ?',
      duration_ms: 360.0,
      attributes: { 'db.system': 'mysql', 'db.statement': 'SELECT * FROM orders' },
    },
    {
      trace_id: 't_m_3',
      span_id: 's_m_3',
      service_name: 'pay-service',
      name: 'call_alipay_gateway',
      duration_ms: 3500.0,
      status_code: 'ERROR',
      status_message: 'Gateway Timeout (504)',
      attributes: { 'http.status_code': 504 },
    },
    {
      trace_id: 't_m_4',
      span_id: 's_m_4',
      service_name: 'auth-service',
      name: 'verify_token',
      duration_ms: 18.0,
      status_code: 'OK',
      attributes: { 'http.status_code': 200 },
    },
  ],
  db_heavy: [
    {
      trace_id: 't_db_1',
      span_id: 's_db_1',
      service_name: 'order-service',
      name: 'SELECT * FROM orders JOIN items',
      duration_ms: 650.0,
      attributes: { 'db.system': 'mysql' },
    },
    {
      trace_id: 't_db_2',
      span_id: 's_db_2',
      service_name: 'order-service',
      name: 'SELECT * FROM orders JOIN items',
      duration_ms: 820.0,
      attributes: { 'db.system': 'mysql' },
    },
    {
      trace_id: 't_db_3',
      span_id: 's_db_3',
      service_name: 'order-service',
      name: 'SELECT * FROM orders JOIN items',
      duration_ms: 590.0,
      attributes: { 'db.system': 'mysql' },
    },
  ],
  healthy: [
    {
      trace_id: 't_h_1',
      span_id: 's_h_1',
      service_name: 'order-service',
      name: 'get_order_status',
      duration_ms: 22.0,
      status_code: 'OK',
    },
    {
      trace_id: 't_h_2',
      span_id: 's_h_2',
      service_name: 'pay-service',
      name: 'get_balance',
      duration_ms: 30.0,
      status_code: 'OK',
    },
  ],
}

function applyPreset(key: 'mixed' | 'db_heavy' | 'healthy') {
  presetKey.value = key
  runClusteringAnalysis()
}

async function runClusteringAnalysis() {
  analyzing.value = true
  try {
    const spans = PRESET_DATA[presetKey.value]
    const res = await traceAnomalyApi.analyze({
      spans,
      slow_threshold_ms: slowThresholdMs.value,
    })
    report.value = res
    message.success('慢调用智能聚类诊断完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

async function runTelemetryDiagnosis() {
  analyzingTelemetry.value = true
  try {
    const res = await traceAnomalyApi.telemetryDiagnose({
      slow_threshold_ms: slowThresholdMs.value,
    })
    report.value = res
    message.success('全网链路聚类诊断完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '全网链路诊断失败')
  } finally {
    analyzingTelemetry.value = false
  }
}

onMounted(() => {
  runClusteringAnalysis()
})
</script>

<style scoped>
.trace-anomaly-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.intro-banner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.preset-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.action-row {
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.input-label {
  font-size: 12px;
  color: #64748b;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
  margin-left: -6px;
}

/* 裁决横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.banner-has-clusters {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-clean {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.verdict-status-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  font-size: 13px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.badge-alert {
  background: #ef4444;
  color: #ffffff;
}

.badge-ok {
  background: #16a34a;
  color: #ffffff;
}

.verdict-summary {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.meta-time {
  font-size: 11px;
  color: #64748b;
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
  padding: 10px 14px;
  text-align: center;
}

.kpi-val {
  font-size: 20px;
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

.text-red {
  color: #dc2626;
}

.text-purple {
  color: #9333ea;
}

.clusters-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.clusters-table {
  background: #ffffff;
}

.svc-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.op-title {
  font-size: 12px;
  color: #0f172a;
}

.dur-stats-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.max-dur {
  color: #64748b;
  font-size: 10px;
}

.impact-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.impact-num {
  font-size: 14px;
  font-weight: 800;
  color: #dc2626;
}

.occurrences {
  font-size: 11px;
  color: #64748b;
}

.remed-cell {
  font-size: 11px;
  line-height: 1.5;
}

.cause-text {
  color: #0f172a;
  font-weight: 600;
  margin-bottom: 4px;
}

.remed-list {
  margin: 0;
  padding-left: 16px;
  color: #475569;
}
</style>
