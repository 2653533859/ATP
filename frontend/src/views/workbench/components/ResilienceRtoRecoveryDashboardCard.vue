<template>
  <div class="rto-dashboard-card">
    <!-- 头部机制与核心指标说明 Banner -->
    <div class="intro-banner">
      <div class="banner-top">
        <SlidersOutlined class="banner-icon" />
        <div class="banner-texts">
          <div class="banner-title">服务断路器生效时延与 RTO 自愈量化评估看板 (T4.2)</div>
          <div class="banner-desc">
            在微服务应用层注入混沌故障全周期中，高频采样时序数据流，量化三维核心韧性指标：<strong>断路器跳闸生效时延 (Trip Latency)</strong>、<strong>故障期降级成功率 (Fallback Ratio)</strong> 与 <strong>RTO 自愈恢复时长 (Recovery Time Objective)</strong>，自动化出具四级系统韧性评级（EXCELLENT / ADEQUATE / INSUFFICIENT / FRAGILE）。
          </div>
        </div>
      </div>

      <!-- 四级韧性标准预设快捷切换 -->
      <div class="preset-row">
        <span class="preset-label">韧性基线演练预设:</span>
        <a-space :size="8" wrap>
          <a-button
            size="small"
            :type="currentTier === 'EXCELLENT' ? 'primary' : 'default'"
            @click="applyTierPreset('EXCELLENT')"
          >
            🌟 EXCELLENT (卓越: 极速熔断 &lt;150ms, RTO &lt;800ms)
          </a-button>
          <a-button
            size="small"
            :type="currentTier === 'ADEQUATE' ? 'primary' : 'default'"
            @click="applyTierPreset('ADEQUATE')"
          >
            🛡️ ADEQUATE (合格: 熔断 &lt;500ms, RTO &lt;2.5s)
          </a-button>
          <a-button
            size="small"
            :type="currentTier === 'INSUFFICIENT' ? 'primary' : 'default'"
            @click="applyTierPreset('INSUFFICIENT')"
          >
            ⚠️ INSUFFICIENT (欠缺: 熔断迟钝, 自愈延缓)
          </a-button>
          <a-button
            size="small"
            :type="currentTier === 'FRAGILE' ? 'primary' : 'default'"
            danger
            @click="applyTierPreset('FRAGILE')"
          >
            🚨 FRAGILE (脆弱: 未跳闸雪崩, RTO &gt;5s)
          </a-button>
        </a-space>
      </div>

      <!-- 控制参数栏 -->
      <div class="action-row">
        <a-space :size="12" align="center" wrap>
          <span class="input-label">演练目标服务:</span>
          <a-input
            v-model:value="targetServiceId"
            placeholder="例如: order-service"
            style="width: 170px"
            size="small"
          />

          <span class="input-label">接口端点:</span>
          <a-input
            v-model:value="endpointInput"
            placeholder="例如: POST /api/v1/orders/checkout"
            style="width: 260px"
            size="small"
          />

          <a-button
            type="primary"
            size="small"
            :loading="evaluating"
            @click="runSimulation"
          >
            <ThunderboltOutlined /> 执行断路器与 RTO 仿真评估
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 韧性评估大横幅 (Verdict Banner) -->
    <div v-if="report" class="verdict-banner" :class="`verdict-${report.resilience_tier.toLowerCase()}`">
      <div class="verdict-head">
        <div class="verdict-badge-box">
          <span class="tier-tag" :class="`tag-${report.resilience_tier.toLowerCase()}`">
            {{ report.resilience_tier }} RESILIENCE
          </span>
          <span class="verdict-summary">{{ report.verdict_summary }}</span>
        </div>
        <div class="report-meta">
          报告 ID: <code>{{ report.report_id }}</code>
        </div>
      </div>

      <!-- 3 大核心指标 KPI 仪表卡片 -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-icon-wrapper icon-latency">
            <ClockCircleOutlined />
          </div>
          <div class="kpi-content">
            <div class="kpi-title">断路器跳闸生效时延</div>
            <div class="kpi-val" :class="getLatencyColorClass(report.breaker_trip_latency_ms)">
              {{ report.breaker_trip_latency_ms }} ms
            </div>
            <div class="kpi-standard">基准标准: ≤150ms 卓越，≤500ms 达标</div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-icon-wrapper icon-fallback">
            <SafetyCertificateOutlined />
          </div>
          <div class="kpi-content">
            <div class="kpi-title">故障期降级成功率</div>
            <div class="kpi-val" :class="getFallbackColorClass(report.fallback_success_ratio_pct)">
              {{ report.fallback_success_ratio_pct }}%
            </div>
            <div class="kpi-standard">基准标准: ≥98% 卓越，≥90% 达标</div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-icon-wrapper icon-rto">
            <CheckCircleOutlined />
          </div>
          <div class="kpi-content">
            <div class="kpi-title">RTO 自愈恢复时长</div>
            <div class="kpi-val" :class="getRtoColorClass(report.rto_recovery_duration_ms)">
              {{ report.rto_recovery_duration_ms }} ms
            </div>
            <div class="kpi-standard">基准标准: ≤800ms 卓越，≤2500ms 达标</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 演练时序流与断路器状态演变表格 -->
    <div v-if="report" class="timeline-section">
      <div class="section-title">
        <span>演练高频时序采样流与断路器状态演进 (Time-Series Samples Stream)</span>
        <a-tag color="blue">共分析 {{ report.total_samples_analyzed }} 个时序采样点</a-tag>
      </div>

      <div class="state-stage-bar">
        <div class="stage-item stage-closed">
          <span class="stage-dot dot-closed"></span>
          <span>正常常态 (CLOSED)</span>
        </div>
        <div class="stage-arrow">→</div>
        <div class="stage-item stage-open">
          <span class="stage-dot dot-open"></span>
          <span>故障熔断跳闸 (OPEN - 快速降级)</span>
        </div>
        <div class="stage-arrow">→</div>
        <div class="stage-item stage-half">
          <span class="stage-dot dot-half"></span>
          <span>自愈探测阶段 (HALF_OPEN)</span>
        </div>
        <div class="stage-arrow">→</div>
        <div class="stage-item stage-closed">
          <span class="stage-dot dot-closed"></span>
          <span>完全自愈闭合 (CLOSED)</span>
        </div>
      </div>

      <a-table
        :data-source="report.sample_stream"
        :columns="sampleColumns"
        row-key="seq"
        size="small"
        :pagination="{ pageSize: 8 }"
        bordered
        class="sample-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'seq'">
            <code>#{{ record.seq }}</code>
          </template>

          <template v-if="column.key === 'offset_ms'">
            <span>+{{ record.offset_ms }} ms</span>
          </template>

          <template v-if="column.key === 'duration_ms'">
            <span :class="record.duration_ms > 500 ? 'text-red' : 'text-green'">
              {{ record.duration_ms }} ms
            </span>
          </template>

          <template v-if="column.key === 'status_code'">
            <a-tag :color="record.status_code >= 400 ? 'red' : 'green'">
              {{ record.status_code }}
            </a-tag>
          </template>

          <template v-if="column.key === 'is_fault_active'">
            <a-tag :color="record.is_fault_active ? 'volcano' : 'default'">
              {{ record.is_fault_active ? '注入中' : '正常' }}
            </a-tag>
          </template>

          <template v-if="column.key === 'is_fallback'">
            <a-tag :color="record.is_fallback ? 'blue' : 'default'">
              {{ record.is_fallback ? '已降级' : '直接响应' }}
            </a-tag>
          </template>

          <template v-if="column.key === 'breaker_state'">
            <a-tag :color="getBreakerStateColor(record.breaker_state)">
              {{ record.breaker_state }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 加固与调优建议 (Remediation Suggestions) -->
    <div v-if="report && report.remediation_suggestions.length > 0" class="suggestions-card">
      <div class="sugg-title">🛠️ 微服务韧性加固与断路器调优建议 (Resilience Hardening Guide)</div>
      <ul class="sugg-list">
        <li v-for="(sugg, idx) in report.remediation_suggestions" :key="idx">
          {{ sugg }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SlidersOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  resilienceRtoApi,
  type ResilienceRtoReport,
  type ResilienceTier,
  type BreakerState,
} from '@/api/trafficGateway'

const targetServiceId = ref('order-service')
const endpointInput = ref('POST /api/v1/orders/checkout')
const currentTier = ref<ResilienceTier>('EXCELLENT')
const evaluating = ref(false)
const report = ref<ResilienceRtoReport | null>(null)

const sampleColumns = [
  { title: '时序序号', key: 'seq', width: 90 },
  { title: '时间偏移', key: 'offset_ms', width: 120 },
  { title: '响应耗时', key: 'duration_ms', width: 120 },
  { title: 'HTTP 状态码', key: 'status_code', width: 110 },
  { title: '故障活跃状态', key: 'is_fault_active', width: 120 },
  { title: '降级生效', key: 'is_fallback', width: 110 },
  { title: '断路器状态', key: 'breaker_state', width: 130 },
]

function getLatencyColorClass(latency: number): string {
  if (latency <= 150) return 'val-excellent'
  if (latency <= 500) return 'val-adequate'
  return 'val-fragile'
}

function getFallbackColorClass(ratio: number): string {
  if (ratio >= 98) return 'val-excellent'
  if (ratio >= 90) return 'val-adequate'
  return 'val-fragile'
}

function getRtoColorClass(rto: number): string {
  if (rto <= 800) return 'val-excellent'
  if (rto <= 2500) return 'val-adequate'
  return 'val-fragile'
}

function getBreakerStateColor(s: BreakerState): string {
  switch (s) {
    case 'CLOSED': return 'green'
    case 'OPEN': return 'red'
    case 'HALF_OPEN': return 'orange'
    default: return 'blue'
  }
}

function applyTierPreset(tier: ResilienceTier) {
  currentTier.value = tier
  runSimulation()
}

async function runSimulation() {
  evaluating.value = true
  try {
    const res = await resilienceRtoApi.simulate({
      target_service_id: targetServiceId.value,
      endpoint: endpointInput.value,
      tier_preset: currentTier.value,
    })
    report.value = res.report
    message.success(res.message || '断路器与 RTO 韧性评估完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '仿真计算失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(() => {
  runSimulation()
})
</script>

<style scoped>
.rto-dashboard-card {
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

/* 裁决横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.verdict-excellent {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.verdict-adequate {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.verdict-insufficient {
  background: #fffbeb;
  border-color: #fde68a;
}

.verdict-fragile {
  background: #fef2f2;
  border-color: #fecaca;
}

.verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.verdict-badge-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tier-tag {
  font-size: 13px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.tag-excellent {
  background: #16a34a;
  color: #ffffff;
}

.tag-adequate {
  background: #0284c7;
  color: #ffffff;
}

.tag-insufficient {
  background: #d97706;
  color: #ffffff;
}

.tag-fragile {
  background: #dc2626;
  color: #ffffff;
}

.verdict-summary {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.report-meta {
  font-size: 11px;
  color: #64748b;
}

/* 3大 KPI 仪表卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.kpi-icon-wrapper {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.icon-latency {
  background: #e0f2fe;
  color: #0284c7;
}

.icon-fallback {
  background: #dcfce7;
  color: #16a34a;
}

.icon-rto {
  background: #fef3c7;
  color: #d97706;
}

.kpi-content {
  display: flex;
  flex-direction: column;
}

.kpi-title {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.kpi-val {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
  margin: 2px 0;
}

.val-excellent {
  color: #16a34a;
}

.val-adequate {
  color: #0284c7;
}

.val-fragile {
  color: #dc2626;
}

.kpi-standard {
  font-size: 10px;
  color: #94a3b8;
}

/* 时序流与阶段演进 */
.timeline-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.state-stage-bar {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #334155;
}

.stage-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-closed {
  background: #16a34a;
}

.dot-open {
  background: #dc2626;
}

.dot-half {
  background: #f59e0b;
}

.stage-arrow {
  color: #94a3b8;
  font-weight: bold;
}

.sample-table {
  background: #ffffff;
}

.text-red {
  color: #dc2626;
  font-weight: 600;
}

.text-green {
  color: #16a34a;
}

.suggestions-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px 16px;
}

.sugg-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
}

.sugg-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #334155;
  line-height: 1.6;
}
</style>
