<template>
  <a-drawer
    :open="open"
    :width="1120"
    placement="right"
    title="多模态测试失败智能根因推导与因果链路下钻控制台"
    destroy-on-close
    class="root-cause-drawer"
    @close="handleClose"
  >
    <div class="drawer-content">
      <!-- 头部介绍 Banner -->
      <div class="intro-banner">
        <div class="banner-top">
          <AimOutlined class="banner-icon" />
          <div class="banner-texts">
            <div class="banner-title">测试失败多模态证据融合与首发根因推导引擎 (T3.1)</div>
            <div class="banner-desc">
              当自动化测试用例执行失败时，融合控制台堆栈输出、HTTP 报文状态、分布式追踪 Span 与系统环境参数。智能剔除层层级联报错误导，定位首发源头微服务与最深物理代码位置（Culprit Location），还原完整的 <strong>因果失效传播链条 (Causal Chain)</strong>。
            </div>
          </div>
        </div>
      </div>

      <!-- 快速演练场景栏 -->
      <div class="action-card">
        <div class="preset-row">
          <span class="preset-label">故障根因推导演练场景:</span>
          <a-space :size="8" wrap>
            <a-button
              size="small"
              :type="presetKey === 'database' ? 'primary' : 'default'"
              danger
              @click="applyPreset('database')"
            >
              场景 1: MySQL 行锁争用死锁 (DATABASE_EXECUTION_FAILURE)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'gateway_timeout' ? 'primary' : 'default'"
              @click="applyPreset('gateway_timeout')"
            >
              场景 2: 外部接口网络超时 (NETWORK_GATEWAY_TIMEOUT 504)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'crash_500' ? 'primary' : 'default'"
              @click="applyPreset('crash_500')"
            >
              场景 3: 下游服务空指针崩溃 (DOWNSTREAM_SERVICE_CRASH 500)
            </a-button>
            <a-button
              size="small"
              :type="presetKey === 'ui_locator' ? 'primary' : 'default'"
              @click="applyPreset('ui_locator')"
            >
              场景 4: 前端结账按钮 DOM 漂移 (UI_DOM_LOCATOR_DRIFT)
            </a-button>
          </a-space>
        </div>

        <div class="ctrl-row">
          <a-space :size="12" align="center" wrap>
            <span class="ctrl-lbl">用例 ID:</span>
            <a-input v-model:value="caseIdInput" style="width: 160px" size="small" />

            <span class="ctrl-lbl">用例名称:</span>
            <a-input v-model:value="caseNameInput" style="width: 240px" size="small" />

            <a-button type="primary" size="small" :loading="diagnosing" @click="handleRunDiagnosis">
              <ThunderboltOutlined /> 触发多模态根因推导
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 根因归因裁决大横幅 (Verdict Banner) -->
      <div v-if="report" class="verdict-banner" :class="`banner-${report.category.toLowerCase()}`">
        <div class="verdict-head">
          <div class="verdict-title-box">
            <span class="cat-tag" :class="`tag-${report.category.toLowerCase()}`">
              {{ report.category }}
            </span>
            <span class="confidence-badge">置信度: {{ Math.round(report.confidence_score * 100) }}%</span>
            <span class="verdict-summary">{{ report.primary_root_cause_summary }}</span>
          </div>
          <div class="meta-box">
            <span>责任微服务: <strong>{{ report.culprit_service }}</strong></span>
            <span class="sep">|</span>
            <span>首发位置: <code>{{ report.culprit_location }}</code></span>
          </div>
        </div>
      </div>

      <!-- 因果失效传播链条 (Causal Chain) -->
      <div v-if="report && report.causal_chain.length > 0" class="causal-section">
        <div class="section-title">
          <span>因果失效传播链条 (Causal Failure Chain)</span>
          <small class="title-sub">由内到外还原从首发底层异常到顶层测试断言失败的扩散全过程</small>
        </div>

        <div class="chain-timeline">
          <div
            v-for="(step, idx) in report.causal_chain"
            :key="idx"
            class="chain-step"
            :class="{ 'step-root': idx === 0, 'step-leaf': idx === report.causal_chain.length - 1 }"
          >
            <div class="step-badge">Step {{ idx + 1 }}</div>
            <div class="step-text">{{ step }}</div>
          </div>
        </div>
      </div>

      <!-- 多模态诊断证据库 (Multi-Modal Evidence Snippets) -->
      <div v-if="report" class="evidence-section">
        <div class="section-title">
          <span>多模态诊断证据汇编 (Multi-Modal Diagnostic Evidence)</span>
          <a-tag color="blue">共 {{ report.evidence_snippets.length }} 项证据源</a-tag>
        </div>

        <div class="evidence-grid">
          <div
            v-for="(ev, idx) in report.evidence_snippets"
            :key="idx"
            class="evidence-card"
            :class="{ 'card-key-evidence': ev.is_key_evidence }"
          >
            <div class="ev-head">
              <div class="ev-title">
                <a-tag :color="getEvidenceTagColor(ev.evidence_type)">{{ ev.evidence_type }}</a-tag>
                <strong>{{ ev.title }}</strong>
              </div>
              <a-tag v-if="ev.is_key_evidence" color="red">关键定性证据</a-tag>
            </div>
            <pre class="ev-content">{{ ev.content }}</pre>
          </div>
        </div>
      </div>

      <!-- 专家排查与修复行动指引 -->
      <div v-if="report" class="action-recommendation">
        <div class="rec-title">🛠️ 专家排查与修复行动建议 (Actionable Remediation Guide)</div>
        <div class="rec-body">{{ report.suggested_action }}</div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  AimOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  rootCauseDiagnosisApi,
  type RootCauseAttributionReport,
} from '@/api/rootCauseDiagnosis'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

function handleClose() {
  emit('update:open', false)
}

const diagnosing = ref(false)
const report = ref<RootCauseAttributionReport | null>(null)
const caseIdInput = ref('case_order_101')
const caseNameInput = ref('提交订单并发支付用例')
const presetKey = ref<'database' | 'gateway_timeout' | 'crash_500' | 'ui_locator'>('database')

function getEvidenceTagColor(t: string): string {
  switch (t) {
    case 'CONSOLE_LOG': return 'orange'
    case 'HTTP_RESPONSE': return 'blue'
    case 'SPAN_TRACE': return 'purple'
    case 'ENV_FACTOR': return 'cyan'
    default: return 'default'
  }
}

// 演练预设
const PRESETS = {
  database: {
    case_id: 'case_order_101',
    case_name: '提交订单并发支付用例',
    console_logs: `
    Traceback (most recent call last):
      File "/app/services/order_service.py", line 155, in checkout
        db.session.commit()
    sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (1213, 'Deadlock found when trying to get lock; try restarting transaction')
    `,
    http_status_code: 500,
    http_response_body: '{"code": 500, "error": "Internal database operational error"}',
  },
  gateway_timeout: {
    case_id: 'case_credit_202',
    case_name: '外部征信风控接口调用',
    console_logs: 'requests.exceptions.ReadTimeout: HTTPSConnectionPool(host="api.credit.com"): Read timed out. (read timeout=5.0)',
    http_status_code: 504,
    http_response_body: '<html><body><h1>504 Gateway Time-out</h1></body></html>',
  },
  crash_500: {
    case_id: 'case_pay_303',
    case_name: '第三方支付异步通知回调',
    console_logs: `
    File "/workspace/backend/payment_processor.py", line 88, in handle_callback
      user_id = payload['data']['user_info']['id']
    KeyError: 'user_info'
    `,
    http_status_code: 500,
    http_response_body: '{"status": 500, "message": "KeyError: user_info"}',
    spans: [
      {
        service_name: 'pay-callback-service',
        name: 'handle_callback',
        status: 'ERROR',
        error_message: "KeyError: 'user_info'",
      },
    ],
  },
  ui_locator: {
    case_id: 'case_ui_404',
    case_name: '购物车结账下单 UI 流程',
    console_logs: 'selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element: {"method":"xpath","selector":"//button[@id="confirm-order"]"}',
    http_status_code: undefined,
    http_response_body: '',
  },
}

function applyPreset(key: 'database' | 'gateway_timeout' | 'crash_500' | 'ui_locator') {
  presetKey.value = key
  const p = PRESETS[key]
  caseIdInput.value = p.case_id
  caseNameInput.value = p.case_name
  handleRunDiagnosis()
}

async function handleRunDiagnosis() {
  diagnosing.value = true
  try {
    const p = PRESETS[presetKey.value]
    const res = await rootCauseDiagnosisApi.analyze({
      case_id: caseIdInput.value,
      case_name: caseNameInput.value,
      console_logs: p.console_logs,
      http_status_code: p.http_status_code,
      http_response_body: p.http_response_body,
      spans: (p as any).spans,
    })
    report.value = res.report
    message.success(res.message || '多模态根因推导完成')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '推导失败')
  } finally {
    diagnosing.value = false
  }
}

onMounted(() => {
  applyPreset('database')
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

.action-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.ctrl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.ctrl-lbl {
  font-size: 12px;
  color: #64748b;
}

/* 裁决大横幅 */
.verdict-banner {
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid transparent;
}

.banner-database_execution_failure {
  background: #faf5ff;
  border-color: #e9d5ff;
}

.banner-network_gateway_timeout {
  background: #fff7ed;
  border-color: #fed7aa;
}

.banner-downstream_service_crash {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-ui_dom_locator_drift {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.verdict-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cat-tag {
  font-size: 13px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
}

.tag-database_execution_failure {
  background: #9333ea;
  color: #ffffff;
}

.tag-network_gateway_timeout {
  background: #ea580c;
  color: #ffffff;
}

.tag-downstream_service_crash {
  background: #dc2626;
  color: #ffffff;
}

.tag-ui_dom_locator_drift {
  background: #16a34a;
  color: #ffffff;
}

.confidence-badge {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  font-size: 11px;
  font-weight: 700;
  color: #0f172a;
  padding: 2px 6px;
  border-radius: 4px;
}

.verdict-summary {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.meta-box {
  font-size: 11px;
  color: #64748b;
}

.sep {
  margin: 0 6px;
  color: #cbd5e1;
}

/* 因果链条 */
.causal-section {
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

.title-sub {
  font-size: 11px;
  color: #64748b;
  font-weight: normal;
}

.chain-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 18px;
}

.chain-step {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.step-badge {
  background: #f1f5f9;
  color: #475569;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.step-root .step-badge {
  background: #fee2e2;
  color: #dc2626;
}

.step-leaf .step-badge {
  background: #fef3c7;
  color: #d97706;
}

.step-text {
  color: #1e293b;
}

/* 证据库 */
.evidence-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
}

.card-key-evidence {
  border-left: 3px solid #dc2626;
}

.ev-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.ev-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #0f172a;
}

.ev-content {
  font-family: Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  background: #0f172a;
  color: #38bdf8;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 0;
  max-height: 140px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 建议卡片 */
.action-recommendation {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  padding: 12px 16px;
}

.rec-title {
  font-size: 13px;
  font-weight: 700;
  color: #166534;
  margin-bottom: 4px;
}

.rec-body {
  font-size: 12px;
  color: #14532d;
  line-height: 1.6;
}
</style>
