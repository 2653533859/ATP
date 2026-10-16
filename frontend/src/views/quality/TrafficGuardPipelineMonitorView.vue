<template>
  <div class="page-shell pipeline-monitor-view">
    <!-- 头部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <CheckCircleOutlined class="hero-icon" />
          <h2 class="page-title">生产流量防线 Checkpoint 检查点端到端全景监控看板</h2>
        </div>
        <p class="page-subtitle">
          编排执行端到端四阶段卡点流水线（流量捕获与脱敏 → 影子回放与基线差分 → 契约破坏逆向阻断 → 混沌韧性自愈 RTO），统一裁决 Exit Code 0/1/2 门禁状态，输出专业高对比度 ANSI 终端控制台日志。
        </p>
      </div>
      <div class="hero-actions">
        <a-space>
          <a-button :loading="loadingHistory" @click="fetchHistoryReports">
            <HistoryOutlined /> 历史执行
          </a-button>
          <a-button
            type="primary"
            :loading="runningPipeline"
            @click="handleRunPipeline"
          >
            <PlayCircleOutlined /> 触发全量防线流水线执行
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 参数配置与快速演练预设 -->
    <a-card size="small" class="control-card">
      <div class="control-inner">
        <div class="config-row">
          <span class="cfg-label">接口端点:</span>
          <a-input
            v-model:value="configForm.endpoint"
            placeholder="POST /api/v1/orders/checkout"
            style="width: 260px"
            size="small"
          />

          <span class="cfg-label">写防护模式:</span>
          <a-select v-model:value="configForm.write_guard_mode" style="width: 150px" size="small">
            <a-select-option value="BLOCK_WRITES">BLOCK_WRITES (安全阻断)</a-select-option>
            <a-select-option value="DRY_RUN">DRY_RUN (沙箱试跑)</a-select-option>
            <a-select-option value="ALLOW_ALL">ALLOW_ALL (全量放行)</a-select-option>
          </a-select>

          <span class="cfg-label">容差阈值:</span>
          <a-input-number
            v-model:value="configForm.tolerance_threshold_pct"
            :min="50"
            :max="100"
            style="width: 80px"
            size="small"
          />
          <span class="unit-text">%</span>

          <span class="cfg-label">混沌韧性验证:</span>
          <a-switch v-model:checked="configForm.simulate_chaos_resilience" size="small" />
        </div>

        <div class="preset-row">
          <span class="preset-label">快捷门禁演练预设:</span>
          <a-space :size="8">
            <a-button
              size="small"
              :type="presetKey === 'pass' ? 'primary' : 'default'"
              @click="applyPreset('pass')"
            >
              🟢 场景 1: 四阶段全量通过 (Exit Code 0: PASS 放行)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'block' ? 'primary' : 'default'"
              danger
              @click="applyPreset('block')"
            >
              🔴 场景 2: 契约破坏硬拦截 (Exit Code 1: BLOCK 阻断)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'warn' ? 'primary' : 'default'"
              @click="applyPreset('warn')"
            >
              🟠 场景 3: 容错风险告警 (Exit Code 2: WARN 提示)
            </a-button>
          </a-space>
        </div>
      </div>
    </a-card>

    <!-- 最终裁决大横幅 (Exit Code Verdict Banner) -->
    <div v-if="report" class="verdict-banner" :class="`banner-code-${report.exit_code}`">
      <div class="banner-top">
        <div class="verdict-status-row">
          <span class="exit-badge" :class="`badge-code-${report.exit_code}`">
            EXIT CODE {{ report.exit_code }} ({{ report.overall_status }})
          </span>
          <span class="verdict-title-text">{{ getVerdictTitle(report.exit_code) }}</span>
        </div>
        <div class="pipeline-meta">
          <span>批次: <code>{{ report.pipeline_run_id }}</code></span>
          <span class="meta-sep">|</span>
          <span>端点: <strong>{{ report.endpoint }}</strong></span>
          <span class="meta-sep">|</span>
          <span>耗时: <strong>{{ totalPipelineDuration }} ms</strong></span>
        </div>
      </div>
    </div>

    <!-- 四阶段检查点卡点流看板 (4 Checkpoint Stages) -->
    <div v-if="report" class="stages-grid">
      <div
        v-for="st in report.stages"
        :key="st.stage_index"
        class="stage-card"
        :class="`stage-status-${st.status.toLowerCase()}`"
      >
        <div class="stage-header">
          <div class="stage-index-badge">Stage {{ st.stage_index }}</div>
          <a-tag :color="getStageTagColor(st.status)">
            {{ st.status }}
          </a-tag>
        </div>

        <div class="stage-name">{{ st.stage_name }}</div>
        <div class="stage-summary">{{ st.summary }}</div>

        <!-- 指标微列表 -->
        <div class="stage-metrics">
          <div v-for="(val, k) in st.metrics" :key="k" class="metric-row">
            <span class="m-key">{{ formatMetricKey(k) }}:</span>
            <span class="m-val">{{ val }}</span>
          </div>
        </div>

        <div class="stage-footer">
          <ClockCircleOutlined /> {{ st.duration_ms }} ms
        </div>
      </div>
    </div>

    <!-- 双栏工作台：左侧 ANSI 终端输出 + 右侧阻断行动项与报告历史 -->
    <div v-if="report" class="bottom-layout">
      <!-- 左侧：ANSI 高对比度控制台 -->
      <div class="terminal-panel">
        <div class="panel-header">
          <div class="panel-title">
            <CodeOutlined />
            <span>流水线执行终端控制台日志 (ANSI Terminal Log)</span>
          </div>
          <a-button size="small" @click="copyTerminalLog">
            <CopyOutlined /> 复制控制台日志
          </a-button>
        </div>
        <div class="terminal-body" v-html="parsedAnsiHtml"></div>
      </div>

      <!-- 右侧：行动建议与往期报告 -->
      <div class="side-panel">
        <!-- 阻断修复行动指引 -->
        <div class="side-card">
          <div class="card-title">🚨 流水线卡点阻断与处置指引 (Remediation Actions)</div>
          <div v-if="!report.remediation_actions.length" class="empty-remed">
            <CheckCircleOutlined style="color: #16a34a; font-size: 18px" />
            <span style="color: #16a34a">当前流水线全阶段通过，无违规卡点行动项。</span>
          </div>
          <ul v-else class="remed-list">
            <li v-for="(action, idx) in report.remediation_actions" :key="idx">
              {{ action }}
            </li>
          </ul>
        </div>

        <!-- 历史流水线执行流水 -->
        <div class="side-card">
          <div class="card-title">🕒 历史流水线执行记录</div>
          <div v-if="!historyReports.length" class="empty-sub">
            暂无历史流水线记录
          </div>
          <div v-else class="history-list">
            <div
              v-for="h in historyReports"
              :key="h.pipeline_run_id"
              class="history-item"
              :class="{ 'item-selected': h.pipeline_run_id === report?.pipeline_run_id }"
              @click="loadHistoryReport(h)"
            >
              <div class="h-top">
                <span class="h-name">{{ h.pipeline_name }}</span>
                <span class="h-code" :class="`code-${h.exit_code}`">Exit {{ h.exit_code }}</span>
              </div>
              <div class="h-sub">
                <span>{{ h.endpoint }}</span>
                <small>{{ formatTime(h.executed_at) }}</small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  PlayCircleOutlined,
  HistoryOutlined,
  CodeOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue'
import {
  trafficGuardPipelineApi,
  type TrafficGuardPipelineReport,
  type TrafficPipelineStageStatus,
} from '@/api/trafficGateway'

const runningPipeline = ref(false)
const loadingHistory = ref(false)
const report = ref<TrafficGuardPipelineReport | null>(null)
const historyReports = ref<TrafficGuardPipelineReport[]>([])
const presetKey = ref<'pass' | 'block' | 'warn'>('pass')

const configForm = reactive({
  endpoint: 'POST /api/v1/orders/checkout',
  write_guard_mode: 'BLOCK_WRITES',
  tolerance_threshold_pct: 95.0,
  simulate_chaos_resilience: true,
})

const PRESETS = {
  pass: {
    endpoint: 'POST /api/v1/orders/checkout',
    write_guard_mode: 'BLOCK_WRITES',
    tolerance_threshold_pct: 95.0,
    design_contract: {
      type: 'object',
      properties: {
        order_id: { type: 'integer' },
        amount: { type: 'number' },
      },
      required: ['order_id'],
      response_schemas: {
        '200': {
          type: 'object',
          properties: { code: { type: 'integer' }, status: { type: 'string' } },
        },
      },
    },
  },
  block: {
    endpoint: 'POST /api/v1/orders/checkout',
    write_guard_mode: 'BLOCK_WRITES',
    tolerance_threshold_pct: 95.0,
    design_contract: {
      type: 'object',
      properties: {
        order_id: { type: 'integer' },
      },
      required: ['order_id'],
      response_schemas: {
        '200': {
          type: 'object',
          properties: {
            code: { type: 'integer' },
            pay_token: { type: 'string' }, // 设计期有，生产响应删除 -> BREAKING!
          },
          required: ['code', 'pay_token'],
        },
      },
    },
  },
  warn: {
    endpoint: 'POST /api/v1/orders/checkout',
    write_guard_mode: 'DRY_RUN',
    tolerance_threshold_pct: 99.0, // 苛刻容差阈值 -> 触发 Warning
    design_contract: null,
  },
}

function applyPreset(key: 'pass' | 'block' | 'warn') {
  presetKey.value = key
  const p = PRESETS[key]
  configForm.endpoint = p.endpoint
  configForm.write_guard_mode = p.write_guard_mode
  configForm.tolerance_threshold_pct = p.tolerance_threshold_pct
  handleRunPipeline()
}

const totalPipelineDuration = computed(() => {
  if (!report.value?.stages) return 0
  return Math.round(report.value.stages.reduce((acc, st) => acc + st.duration_ms, 0))
})

function getVerdictTitle(exitCode: number): string {
  switch (exitCode) {
    case 0: return '端到端流量防线四阶段全量通过，生产发布质量绿灯放行！'
    case 1: return '检出硬性契约破坏变更或安全阻断违规，发布流水线被原子熔断拦截！'
    case 2: return '系统可用但存在非阻断轻微偏离或次要告警，建议进行人工确认。'
    default: return '流水线执行完成'
  }
}

function getStageTagColor(s: TrafficPipelineStageStatus): string {
  switch (s) {
    case 'PASSED': return 'green'
    case 'BLOCKED': return 'red'
    case 'WARNING': return 'orange'
    default: return 'blue'
  }
}

function formatMetricKey(k: string): string {
  return k.replace(/_/g, ' ')
}

function formatTime(t: string): string {
  if (!t) return ''
  return t.replace('T', ' ').substring(0, 19)
}

// 终端 ANSI 颜色解析器
const parsedAnsiHtml = computed(() => {
  if (!report.value?.console_log_output) return ''
  const text = report.value.console_log_output

  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 基础 ANSI 颜色转换
  html = html
    .replace(/\x1b\[1;32m(.*?)\x1b\[0m/g, '<span style="color:#4ade80;font-weight:bold">$1</span>')
    .replace(/\x1b\[1;31m(.*?)\x1b\[0m/g, '<span style="color:#f87171;font-weight:bold">$1</span>')
    .replace(/\x1b\[1;33m(.*?)\x1b\[0m/g, '<span style="color:#fbbf24;font-weight:bold">$1</span>')
    .replace(/\x1b\[1;36m(.*?)\x1b\[0m/g, '<span style="color:#38bdf8;font-weight:bold">$1</span>')
    .replace(/\x1b\[1;35m(.*?)\x1b\[0m/g, '<span style="color:#c084fc;font-weight:bold">$1</span>')
    .replace(/\x1b\[0;32m(.*?)\x1b\[0m/g, '<span style="color:#22c55e">$1</span>')
    .replace(/\x1b\[0;31m(.*?)\x1b\[0m/g, '<span style="color:#ef4444">$1</span>')
    .replace(/\x1b\[0;33m(.*?)\x1b\[0m/g, '<span style="color:#eab308">$1</span>')
    .replace(/\x1b\[0;36m(.*?)\x1b\[0m/g, '<span style="color:#0ea5e9">$1</span>')
    .replace(/\x1b\[\d+m/g, '')

  return html
})

async function handleRunPipeline() {
  runningPipeline.value = true
  try {
    const p = PRESETS[presetKey.value]
    const res = await trafficGuardPipelineApi.run({
      endpoint: configForm.endpoint,
      write_guard_mode: configForm.write_guard_mode,
      tolerance_threshold_pct: configForm.tolerance_threshold_pct,
      simulate_chaos_resilience: configForm.simulate_chaos_resilience,
      design_contract: p.design_contract || undefined,
    })
    report.value = res.report
    message.success(res.message || '流水线执行完成')
    await fetchHistoryReports()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '流水线触发失败')
  } finally {
    runningPipeline.value = false
  }
}

async function fetchHistoryReports() {
  loadingHistory.value = true
  try {
    const res = await trafficGuardPipelineApi.listReports()
    historyReports.value = res.reports
  } catch {
    // ignore
  } finally {
    loadingHistory.value = false
  }
}

function loadHistoryReport(h: TrafficGuardPipelineReport) {
  report.value = h
  message.info(`已切换查看批次: ${h.pipeline_run_id}`)
}

function copyTerminalLog() {
  if (!report.value?.console_log_output) return
  void navigator.clipboard.writeText(report.value.console_log_output)
  message.success('已复制完整终端日志')
}

onMounted(async () => {
  await handleRunPipeline()
})
</script>

<style scoped>
.pipeline-monitor-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
}

.hero-icon {
  font-size: 20px;
  color: #16a34a;
}

.control-card {
  border-radius: 8px;
}

.control-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.cfg-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.unit-text {
  font-size: 12px;
  color: #64748b;
  margin-left: -6px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

/* 最终裁决横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.banner-code-0 {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.banner-code-1 {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-code-2 {
  background: #fffbeb;
  border-color: #fde68a;
}

.banner-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.verdict-status-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.exit-badge {
  font-size: 13px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.badge-code-0 {
  background: #16a34a;
  color: #ffffff;
}

.badge-code-1 {
  background: #dc2626;
  color: #ffffff;
}

.badge-code-2 {
  background: #d97706;
  color: #ffffff;
}

.verdict-title-text {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.pipeline-meta {
  font-size: 11px;
  color: #64748b;
}

.meta-sep {
  margin: 0 6px;
  color: #cbd5e1;
}

/* 四阶段栅格 */
.stages-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stage-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
}

.stage-status-passed {
  border-top: 3px solid #16a34a;
}

.stage-status-blocked {
  border-top: 3px solid #dc2626;
}

.stage-status-warning {
  border-top: 3px solid #d97706;
}

.stage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.stage-index-badge {
  font-size: 11px;
  font-weight: 700;
  color: #0284c7;
  background: #e0f2fe;
  padding: 2px 6px;
  border-radius: 4px;
}

.stage-name {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.4;
  margin-bottom: 6px;
}

.stage-summary {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
  flex: 1;
  margin-bottom: 10px;
}

.stage-metrics {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 10px;
  margin-bottom: 8px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
}

.m-key {
  color: #64748b;
}

.m-val {
  font-weight: 600;
  color: #0f172a;
}

.stage-footer {
  font-size: 11px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 底部双栏 */
.bottom-layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 16px;
  align-items: start;
}

.terminal-panel {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  background: #1e293b;
  padding: 8px 14px;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #38bdf8;
}

.terminal-body {
  padding: 14px;
  font-family: Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
  color: #f8fafc;
  max-height: 480px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.side-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}

.card-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 10px;
}

.empty-remed {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 8px 0;
}

.remed-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #dc2626;
  line-height: 1.6;
}

.empty-sub {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
  padding: 12px 0;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.history-item {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  background: #f8fafc;
  border-color: #0284c7;
}

.item-selected {
  background: #f0f9ff;
  border-color: #0284c7;
}

.h-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.h-code {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
}

.code-0 {
  background: #dcfce7;
  color: #16a34a;
}

.code-1 {
  background: #fee2e2;
  color: #dc2626;
}

.code-2 {
  background: #fef3c7;
  color: #d97706;
}

.h-sub {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}
</style>
