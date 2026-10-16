<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="流量驱动的应用层混沌故障注入编排控制台"
    destroy-on-close
    class="chaos-fault-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <ThunderboltOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">基于流量特征匹配的应用层微服务故障注入防线 (T4.1)</div>
            <div class="banner-desc">
              针对目标接口流量特征（端点正则、HTTP 方法、Header 灰度标签、Body 属性）进行精准匹配，支持 <strong>四大故障模式</strong>：时延延迟（LATENCY）、错误响应（ERROR_RESPONSE）、载荷损坏（CORRUPTION）与连接断开（ABRUPT_DROP）。内置最大触发次数（Max Trigger Limit）自动熔断保护，杜绝演练故障失控扩散！
            </div>
          </div>
        </div>

        <!-- 4 大模式特性卡片 -->
        <div class="mode-cards">
          <div class="mode-card mode-latency">
            <div class="mode-name">⏳ 网络慢调用 (LATENCY)</div>
            <div class="mode-desc">注入基准毫秒延迟与正态随机抖动 (Jitter)</div>
          </div>
          <div class="mode-card mode-error">
            <div class="mode-name">🚫 协议错误码 (ERROR_RESPONSE)</div>
            <div class="mode-desc">强制返回 500/502/503/504 状态码与异常体</div>
          </div>
          <div class="mode-card mode-corrupt">
            <div class="mode-name">💥 载荷损坏 (CORRUPTION)</div>
            <div class="mode-desc">JSON 截断 (TRUNCATE) 或乱码扰乱 (GARBLE)</div>
          </div>
          <div class="mode-card mode-drop">
            <div class="mode-name">🔌 中途断开 (ABRUPT_DROP)</div>
            <div class="mode-desc">模拟网络连接突然 Reset 或高丢包</div>
          </div>
        </div>
      </div>

      <!-- 全局演练会话状态栏 -->
      <div class="session-bar">
        <div class="session-left">
          <span class="session-label">全局演练状态:</span>
          <a-tag :color="activeSession?.is_active ? 'red' : 'default'">
            {{ activeSession?.is_active ? '🔴 演练注入中 (ACTIVE)' : '⚪ 演练未激活 (IDLE)' }}
          </a-tag>
          <span v-if="activeSession" class="session-stats">
            拦截请求: <strong>{{ activeSession.total_requests_intercepted }}</strong> 次 |
            注入故障: <strong>{{ activeSession.total_faults_injected }}</strong> 次
          </span>
        </div>
        <div class="session-right">
          <a-button
            v-if="!activeSession?.is_active"
            type="primary"
            danger
            size="small"
            @click="handleStartSession"
          >
            <PlayCircleOutlined /> 启动混沌演练批次
          </a-button>
          <a-button
            v-else
            danger
            size="small"
            @click="handleStopSession"
          >
            <StopOutlined /> 停止演练 (恢复正常)
          </a-button>
          <a-button size="small" @click="fetchRules">
            <ReloadOutlined /> 刷新规则
          </a-button>
        </div>
      </div>

      <!-- 核心工作区：左侧规则列表 + 右侧创建/沙箱模拟 -->
      <div class="main-layout">
        <!-- 左侧：故障规则列表 -->
        <div class="rules-section">
          <div class="section-title">
            <span>已编排故障注入规则清单</span>
            <a-tag color="blue">共 {{ rules.length }} 条生效规则</a-tag>
          </div>

          <a-table
            :data-source="rules"
            :columns="ruleColumns"
            row-key="rule_id"
            size="small"
            :pagination="false"
            bordered
            class="rules-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rule_name'">
                <div class="rule-name-cell">
                  <strong>{{ record.rule_name }}</strong>
                  <code class="rule-id">{{ record.rule_id }}</code>
                </div>
              </template>

              <template v-if="column.key === 'fault_type'">
                <a-tag :color="getFaultTagColor(record.fault_type)">
                  {{ record.fault_type }}
                </a-tag>
              </template>

              <template v-if="column.key === 'match_criteria'">
                <div class="match-info">
                  <div v-if="record.match_criteria?.endpoint_pattern">
                    路径正则: <code>{{ record.match_criteria.endpoint_pattern }}</code>
                  </div>
                  <div v-if="record.match_criteria?.methods?.length">
                    方法: {{ record.match_criteria.methods.join(', ') }}
                  </div>
                  <div v-if="Object.keys(record.match_criteria?.header_match || {}).length">
                    Header: {{ JSON.stringify(record.match_criteria.header_match) }}
                  </div>
                  <div>概率: <strong>{{ Math.round((record.match_criteria?.traffic_ratio || 1) * 100) }}%</strong></div>
                </div>
              </template>

              <template v-if="column.key === 'fault_params'">
                <div class="fault-params-cell">
                  <span v-if="record.fault_type === 'LATENCY'">
                    延时: {{ record.latency_ms }}ms (抖动 +{{ record.latency_jitter_max_ms }}ms)
                  </span>
                  <span v-else-if="record.fault_type === 'ERROR_RESPONSE'">
                    状态码: <a-tag color="red">{{ record.error_status_code }}</a-tag>
                  </span>
                  <span v-else-if="record.fault_type === 'CORRUPTION'">
                    模式: {{ record.corruption_mode }}
                  </span>
                  <span v-else-if="record.fault_type === 'ABRUPT_DROP'">
                    模拟网络连接强制丢包重置
                  </span>
                </div>
              </template>

              <template v-if="column.key === 'triggers'">
                <div class="trigger-cell">
                  <span>{{ record.current_triggers_count }} / {{ record.max_triggers_limit }}</span>
                  <a-progress
                    :percent="Math.min(100, Math.round((record.current_triggers_count / record.max_triggers_limit) * 100))"
                    size="small"
                    :status="record.current_triggers_count >= record.max_triggers_limit ? 'exception' : 'active'"
                  />
                </div>
              </template>

              <template v-if="column.key === 'action'">
                <a-space size="small">
                  <a-button size="small" type="link" @click="fillSimulator(record as any)">
                    演练
                  </a-button>
                  <a-popconfirm
                    title="确定删除此故障规则吗？"
                    ok-text="删除"
                    cancel-text="取消"
                    @confirm="handleDeleteRule(record.rule_id)"
                  >
                    <a-button size="small" type="link" danger>
                      删除
                    </a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </div>

        <!-- 右侧：创建规则 / 在线模拟演练 Tabs -->
        <div class="side-workbench">
          <a-tabs v-model:activeKey="activeTab" size="small">
            <!-- Tab 1: 编排新建故障规则 -->
            <a-tab-pane key="create" tab="编排新建故障规则">
              <div class="form-container">
                <a-form layout="vertical" size="small">
                  <a-form-item label="故障规则名称">
                    <a-input v-model:value="newRuleForm.rule_name" placeholder="如: 订单结算网关高时延压测" />
                  </a-form-item>

                  <a-form-item label="故障类型模式">
                    <a-select v-model:value="newRuleForm.fault_type">
                      <a-select-option value="LATENCY">⏳ LATENCY (网络慢调用延时)</a-select-option>
                      <a-select-option value="ERROR_RESPONSE">🚫 ERROR_RESPONSE (HTTP 错误码)</a-select-option>
                      <a-select-option value="CORRUPTION">💥 CORRUPTION (载荷截断或乱码)</a-select-option>
                      <a-select-option value="ABRUPT_DROP">🔌 ABRUPT_DROP (网络中断断开)</a-select-option>
                    </a-select>
                  </a-form-item>

                  <!-- 针对模式的参数配置 -->
                  <div v-if="newRuleForm.fault_type === 'LATENCY'" class="mode-inputs">
                    <a-form-item label="基准延时 (ms)">
                      <a-input-number v-model:value="newRuleForm.latency_ms" :min="0" :max="10000" style="width: 100%" />
                    </a-form-item>
                    <a-form-item label="最大随机抖动 (ms)">
                      <a-input-number v-model:value="newRuleForm.latency_jitter_max_ms" :min="0" :max="5000" style="width: 100%" />
                    </a-form-item>
                  </div>

                  <div v-else-if="newRuleForm.fault_type === 'ERROR_RESPONSE'" class="mode-inputs">
                    <a-form-item label="HTTP/gRPC 响应状态码">
                      <a-select v-model:value="newRuleForm.error_status_code">
                        <a-select-option :value="500">500 Internal Server Error</a-select-option>
                        <a-select-option :value="502">502 Bad Gateway</a-select-option>
                        <a-select-option :value="503">503 Service Unavailable</a-select-option>
                        <a-select-option :value="504">504 Gateway Timeout</a-select-option>
                      </a-select>
                    </a-form-item>
                    <a-form-item label="错误响应体 (JSON)">
                      <a-textarea v-model:value="newRuleForm.error_response_body" :rows="2" />
                    </a-form-item>
                  </div>

                  <div v-else-if="newRuleForm.fault_type === 'CORRUPTION'" class="mode-inputs">
                    <a-form-item label="载荷破坏模式">
                      <a-select v-model:value="newRuleForm.corruption_mode">
                        <a-select-option value="TRUNCATE">TRUNCATE (半包截断)</a-select-option>
                        <a-select-option value="GARBLE">GARBLE (随机乱码篡改)</a-select-option>
                      </a-select>
                    </a-form-item>
                  </div>

                  <!-- 流量匹配特征 -->
                  <a-form-item label="接口路径匹配正则">
                    <a-input v-model:value="newRuleForm.endpoint_pattern" placeholder="如: .*/orders/checkout.*" />
                  </a-form-item>

                  <a-form-item label="注入概率比例 (0~100%)">
                    <a-slider v-model:value="trafficRatioPercent" :min="1" :max="100" />
                  </a-form-item>

                  <a-form-item label="最大触发上限 (防失控安全熔断)">
                    <a-input-number v-model:value="newRuleForm.max_triggers_limit" :min="1" :max="10000" style="width: 100%" />
                  </a-form-item>

                  <a-button type="primary" block :loading="savingRule" @click="handleCreateRule">
                    <PlusOutlined /> 保存并加载故障注入规则
                  </a-button>
                </a-form>
              </div>
            </a-tab-pane>

            <!-- Tab 2: 在线沙箱演练模拟器 -->
            <a-tab-pane key="simulate" tab="在线沙箱流量演练">
              <div class="simulator-box">
                <a-form layout="vertical" size="small">
                  <a-form-item label="请求路径 / 端点">
                    <a-input v-model:value="simForm.path_or_endpoint" placeholder="例如: /api/v1/orders/checkout" />
                  </a-form-item>

                  <a-form-item label="请求方法">
                    <a-select v-model:value="simForm.method">
                      <a-select-option value="GET">GET</a-select-option>
                      <a-select-option value="POST">POST</a-select-option>
                      <a-select-option value="PUT">PUT</a-select-option>
                      <a-select-option value="DELETE">DELETE</a-select-option>
                    </a-select>
                  </a-form-item>

                  <a-form-item label="请求 Header (JSON)">
                    <a-input v-model:value="simHeadersJson" placeholder='例如: {"X-Canary": "beta"}' />
                  </a-form-item>

                  <a-button type="primary" block :loading="simulating" @click="handleSimulate">
                    <ThunderboltOutlined /> 发送测试流量并评估故障拦截
                  </a-button>
                </a-form>

                <!-- 演练拦截结果反馈 -->
                <div v-if="simResult" class="sim-feedback">
                  <div class="feedback-title">
                    <span>拦截结果评估</span>
                    <a-tag :color="simResult.fault_triggered ? 'red' : 'green'">
                      {{ simResult.fault_triggered ? '🚨 故障已成功注入' : '✅ 正常放行 (无故障)' }}
                    </a-tag>
                  </div>

                  <div v-if="simResult.fault_triggered" class="feedback-details">
                    <div>触发模式: <strong>{{ simResult.fault_type }}</strong></div>
                    <div>注入时延: <strong>{{ simResult.injected_latency_ms }} ms</strong></div>
                    <div>最终生效状态码: <strong>{{ simResult.effective_status_code }}</strong></div>
                    <div class="feedback-msg">{{ simResult.log_message }}</div>
                    <div class="feedback-body">
                      <div class="body-label">返回响应体:</div>
                      <pre class="body-code">{{ simResult.effective_response_body }}</pre>
                    </div>
                  </div>
                </div>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  PlusOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons-vue'
import {
  trafficChaosApi,
  type FaultInjectionRuleItem,
  type FaultExecutionResultItem,
  type ChaosExperimentSessionItem,
  type FaultType,
} from '@/api/trafficGateway'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

function handleClose() {
  emit('update:open', false)
}

const rules = ref<FaultInjectionRuleItem[]>([])
const activeSession = ref<ChaosExperimentSessionItem | null>(null)
const activeTab = ref<'create' | 'simulate'>('create')
const savingRule = ref(false)
const simulating = ref(false)
const simResult = ref<FaultExecutionResultItem | null>(null)

const trafficRatioPercent = ref(100)

const newRuleForm = reactive({
  rule_name: '订单结算网关高时延注入',
  fault_type: 'LATENCY' as FaultType,
  endpoint_pattern: '.*/orders/checkout.*',
  latency_ms: 1200,
  latency_jitter_max_ms: 300,
  error_status_code: 503,
  error_response_body: '{"code": 503, "error": "Chaos Injected: Service Unavailable"}',
  corruption_mode: 'TRUNCATE' as 'TRUNCATE' | 'GARBLE',
  max_triggers_limit: 50,
})

const simForm = reactive({
  path_or_endpoint: '/api/v1/orders/checkout',
  method: 'POST',
})
const simHeadersJson = ref('{"X-Canary": "beta"}')

const ruleColumns = [
  { title: '规则名称与 ID', key: 'rule_name', width: 180 },
  { title: '故障模式', key: 'fault_type', width: 130 },
  { title: '流量特征匹配', key: 'match_criteria' },
  { title: '注入参数', key: 'fault_params', width: 190 },
  { title: '触发熔断进度', key: 'triggers', width: 140 },
  { title: '操作', key: 'action', width: 110 },
]

function getFaultTagColor(t: FaultType): string {
  switch (t) {
    case 'LATENCY': return 'orange'
    case 'ERROR_RESPONSE': return 'red'
    case 'CORRUPTION': return 'purple'
    case 'ABRUPT_DROP': return 'volcano'
    default: return 'blue'
  }
}

async function fetchRules() {
  try {
    const res = await trafficChaosApi.listRules()
    rules.value = res.rules
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '获取规则失败')
  }
}

async function fetchSessions() {
  try {
    const res = await trafficChaosApi.listSessions()
    const active = res.sessions.find((s) => s.is_active)
    activeSession.value = active || res.sessions[0] || null
  } catch {
    // ignore
  }
}

async function handleCreateRule() {
  savingRule.value = true
  try {
    const res = await trafficChaosApi.createRule({
      rule_name: newRuleForm.rule_name,
      fault_type: newRuleForm.fault_type,
      endpoint_pattern: newRuleForm.endpoint_pattern,
      traffic_ratio: trafficRatioPercent.value / 100,
      latency_ms: newRuleForm.latency_ms,
      latency_jitter_max_ms: newRuleForm.latency_jitter_max_ms,
      error_status_code: newRuleForm.error_status_code,
      error_response_body: newRuleForm.error_response_body,
      corruption_mode: newRuleForm.corruption_mode,
      max_triggers_limit: newRuleForm.max_triggers_limit,
      enabled: true,
    })
    message.success(res.message || '故障规则保存成功')
    await fetchRules()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '规则保存失败')
  } finally {
    savingRule.value = false
  }
}

async function handleDeleteRule(ruleId: string) {
  try {
    await trafficChaosApi.deleteRule(ruleId)
    message.success('规则已删除')
    await fetchRules()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '删除规则失败')
  }
}

async function handleStartSession() {
  try {
    const res = await trafficChaosApi.startSession({
      name: '生产微服务全网混沌故障注入演练',
      description: '针对高频核心链路开展时延与错误容灾注入',
    })
    activeSession.value = res.session
    message.success('混沌演练批次已启动')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '启动演练失败')
  }
}

async function handleStopSession() {
  if (!activeSession.value) return
  try {
    const res = await trafficChaosApi.stopSession(activeSession.value.experiment_id)
    activeSession.value = res.session
    message.success('混沌演练已停止，流量已恢复正常')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '停止演练失败')
  }
}

function fillSimulator(record: FaultInjectionRuleItem) {
  activeTab.value = 'simulate'
  simForm.path_or_endpoint = record.match_criteria?.endpoint_pattern?.replace(/[\^$.*+?]/g, '') || '/api/v1/orders/checkout'
  if (record.match_criteria?.methods?.length) {
    simForm.method = record.match_criteria.methods[0]
  }
}

async function handleSimulate() {
  simulating.value = true
  try {
    let headers: Record<string, string> = {}
    try {
      headers = JSON.parse(simHeadersJson.value || '{}')
    } catch {
      // ignore
    }

    const res = await trafficChaosApi.evaluateFault({
      path_or_endpoint: simForm.path_or_endpoint,
      method: simForm.method,
      headers,
    })
    simResult.value = res.result
    message.success(res.message || '在线演练评估完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '演练模拟失败')
  } finally {
    simulating.value = false
  }
}

onMounted(async () => {
  await fetchRules()
  await fetchSessions()
})
</script>

<style scoped>
.drawer-content {
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
  color: #ea580c;
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

.mode-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.mode-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
}

.mode-name {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.mode-desc {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

/* 会话状态条 */
.session-bar {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.session-label {
  font-size: 12px;
  color: #475569;
  font-weight: 500;
}

.session-stats {
  font-size: 12px;
  color: #334155;
  margin-left: 8px;
}

.session-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 主布局 */
.main-layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 16px;
  align-items: start;
}

.rules-section {
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

.rules-table {
  background: #ffffff;
}

.rule-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rule-id {
  font-size: 10px;
  color: #64748b;
}

.match-info {
  font-size: 11px;
  color: #475569;
  line-height: 1.4;
}

.match-info code {
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 3px;
}

.fault-params-cell {
  font-size: 11px;
  color: #334155;
}

.trigger-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}

.side-workbench {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
}

.form-container {
  padding-top: 6px;
}

.mode-inputs {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 12px;
}

.simulator-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 6px;
}

.sim-feedback {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
}

.feedback-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.feedback-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: #334155;
}

.feedback-msg {
  color: #0284c7;
  font-style: italic;
  margin-top: 2px;
}

.feedback-body {
  margin-top: 6px;
}

.body-label {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 2px;
}

.body-code {
  font-family: Consolas, monospace;
  font-size: 10px;
  background: #1e293b;
  color: #38bdf8;
  padding: 6px;
  border-radius: 4px;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
