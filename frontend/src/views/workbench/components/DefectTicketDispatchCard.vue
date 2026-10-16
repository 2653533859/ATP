<template>
  <div class="defect-dispatch-card">
    <!-- 头部机制介绍 Banner -->
    <div class="intro-banner">
      <div class="banner-top">
        <BugOutlined class="banner-icon" />
        <div class="banner-texts">
          <div class="banner-title">缺陷严重度智能评级与第三方工单自动指派网关 (T3.3)</div>
          <div class="banner-desc">
            根据测试失败根因属性自动定级四级严重度：<strong>CRITICAL (P0)</strong>、<strong>MAJOR (P1)</strong>、<strong>NORMAL (P2)</strong> 与 <strong>MINOR (P3)</strong>。自动匹配责任微服务技术团队（Assignee Routing），无缝对接 Jira、GitHub Issues 与 企业微信/钉钉 Webhook 机器人自动建单。
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷演练预设与建单操作栏 -->
    <div class="action-card">
      <div class="preset-row">
        <span class="preset-label">缺陷建单演练场景:</span>
        <a-space :size="8" wrap>
          <a-button
            size="small"
            :type="presetKey === 'critical_jira' ? 'primary' : 'default'"
            danger
            @click="applyPreset('critical_jira')"
          >
            场景 1: P0 级支付死锁缺陷 (Jira 建单 -> FinancePay-OnCall)
          </a-button>
          <a-button
            size="small"
            :type="presetKey === 'major_gh' ? 'primary' : 'default'"
            @click="applyPreset('major_gh')"
          >
            场景 2: P1 级微服务 500 崩溃 (GitHub Issue -> OrderTeam-DevLead)
          </a-button>
          <a-button
            size="small"
            :type="presetKey === 'minor_robot' ? 'primary' : 'default'"
            @click="applyPreset('minor_robot')"
          >
            场景 3: P3 级样式定位漂移 (Webhook 机器人 -> Frontend-QA)
          </a-button>
        </a-space>
      </div>

      <div class="form-row">
        <a-space :size="12" align="center" wrap>
          <span class="f-lbl">目标工单平台:</span>
          <a-select v-model:value="ticketForm.platform" style="width: 150px" size="small">
            <a-select-option value="JIRA">Jira (企业缺陷系统)</a-select-option>
            <a-select-option value="GITHUB_ISSUE">GitHub Issues</a-select-option>
            <a-select-option value="WEBHOOK_ROBOT">Webhook 群机器人</a-select-option>
          </a-select>

          <span class="f-lbl">责任微服务:</span>
          <a-input v-model:value="ticketForm.culprit_service" style="width: 140px" size="small" />

          <span class="f-lbl">覆盖指派人:</span>
          <a-input v-model:value="ticketForm.override_assignee" placeholder="可选，留空按服务映射" style="width: 160px" size="small" />

          <a-button type="primary" size="small" :loading="dispatching" @click="handleDispatchTicket">
            <ThunderboltOutlined /> 智能评级并自动创建工单
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 最新创建工单反馈横幅 (Latest Ticket Feedback Banner) -->
    <div v-if="lastDispatchedTicket" class="ticket-feedback-banner" :class="`banner-sev-${lastDispatchedTicket.severity.toLowerCase()}`">
      <div class="feedback-top">
        <div class="feedback-badge-box">
          <span class="sev-tag" :class="`tag-${lastDispatchedTicket.severity.toLowerCase()}`">
            {{ lastDispatchedTicket.severity }} P0/P1
          </span>
          <a-tag color="blue">{{ lastDispatchedTicket.platform }}</a-tag>
          <strong class="ext-id">{{ lastDispatchedTicket.external_issue_id }}</strong>
          <span class="assignee-text">已自动指派至: <strong>{{ lastDispatchedTicket.assignee }}</strong></span>
        </div>
        <a-button size="small" type="link" @click="copyTicketDesc(lastDispatchedTicket.description)">
          <CopyOutlined /> 复制 Markdown 报告
        </a-button>
      </div>

      <div class="feedback-title">
        {{ lastDispatchedTicket.title }}
      </div>

      <!-- Markdown 预览折叠框 -->
      <div class="desc-preview">
        <pre class="desc-code">{{ lastDispatchedTicket.description }}</pre>
      </div>
    </div>

    <!-- 已派发缺陷工单管理表格 (Tickets Table) -->
    <div class="tickets-section">
      <div class="section-header">
        <div class="sec-title">
          <span>全网自动化测试缺陷工单流转台账</span>
          <a-tag color="blue">共 {{ tickets.length }} 笔已派发工单</a-tag>
        </div>
        <div class="table-filters">
          <a-space :size="8">
            <a-select v-model:value="filterPlatform" style="width: 130px" size="small" allow-clear placeholder="全部平台" @change="fetchTickets">
              <a-select-option value="all">全部平台</a-select-option>
              <a-select-option value="JIRA">Jira</a-select-option>
              <a-select-option value="GITHUB_ISSUE">GitHub</a-select-option>
              <a-select-option value="WEBHOOK_ROBOT">Webhook</a-select-option>
            </a-select>

            <a-button size="small" :loading="loadingTickets" @click="fetchTickets">
              <ReloadOutlined /> 刷新工单
            </a-button>
          </a-space>
        </div>
      </div>

      <a-table
        :data-source="tickets"
        :columns="tableColumns"
        row-key="ticket_id"
        size="small"
        :pagination="false"
        bordered
        class="tickets-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'ext_id'">
            <code class="ext-code">{{ record.external_issue_id }}</code>
          </template>

          <template v-if="column.key === 'title'">
            <div class="ticket-title-cell">
              <strong>{{ record.title }}</strong>
              <div class="label-chips">
                <a-tag v-for="l in record.labels" :key="l" size="small">{{ l }}</a-tag>
              </div>
            </div>
          </template>

          <template v-if="column.key === 'severity'">
            <a-tag :color="getSeverityColor(record.severity)">
              {{ record.severity }}
            </a-tag>
          </template>

          <template v-if="column.key === 'platform'">
            <a-tag color="cyan">{{ record.platform }}</a-tag>
          </template>

          <template v-if="column.key === 'assignee'">
            <span class="assignee-val">👤 {{ record.assignee }}</span>
          </template>

          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'RESOLVED' ? 'green' : 'blue'">
              {{ record.status }}
            </a-tag>
          </template>

          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a-button
                v-if="record.status !== 'RESOLVED'"
                size="small"
                type="link"
                @click="handleResolveTicket(record.ticket_id)"
              >
                标记已解决
              </a-button>
              <span v-else class="text-green text-xs">已闭环</span>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  BugOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  defectTicketDispatchApi,
  type DefectTicketItem,
} from '@/api/rootCauseDiagnosis'

const dispatching = ref(false)
const loadingTickets = ref(false)
const lastDispatchedTicket = ref<DefectTicketItem | null>(null)
const tickets = ref<DefectTicketItem[]>([])
const filterPlatform = ref('all')
const presetKey = ref<'critical_jira' | 'major_gh' | 'minor_robot'>('critical_jira')

const ticketForm = reactive({
  platform: 'JIRA',
  culprit_service: 'pay-service',
  override_assignee: '',
})

const tableColumns = [
  { title: '外部工单号', key: 'ext_id', width: 140 },
  { title: '工单标题与标签', key: 'title', width: 340 },
  { title: '严重度', key: 'severity', width: 110 },
  { title: '目标平台', key: 'platform', width: 120 },
  { title: '责任人/团队', key: 'assignee', width: 170 },
  { title: '流转状态', key: 'status', width: 110 },
  { title: '操作', key: 'action', width: 100 },
]

function getSeverityColor(sev: string): string {
  switch (sev) {
    case 'CRITICAL': return 'red'
    case 'MAJOR': return 'orange'
    case 'NORMAL': return 'blue'
    case 'MINOR': return 'default'
    default: return 'default'
  }
}

// 演练预设
const PRESETS = {
  critical_jira: {
    case_id: 'case_pay_deadlock_101',
    case_name: '支付扣款并发事务用例',
    category: 'DATABASE_EXECUTION_FAILURE',
    primary_summary: 'MySQL 订单行锁争用死锁，导致支付事务异常中断',
    culprit_service: 'pay-service',
    culprit_location: 'pay_processor.py:110 in deduct_balance()',
    causal_chain: ['[1] 事务行锁争用', '[2] 抛出 Deadlock 异常', '[3] 接口返回 500'],
    suggested_action: '为订单更新增加升序主键排序加锁，调小 lock_wait_timeout',
    platform: 'JIRA',
    is_critical_asset: true,
  },
  major_gh: {
    case_id: 'case_order_crash_202',
    case_name: '用户结账下单全流程',
    category: 'DOWNSTREAM_SERVICE_CRASH',
    primary_summary: 'order-service 发生空指针/KeyError 崩溃',
    culprit_service: 'order-service',
    culprit_location: 'order_service.py:88 in checkout()',
    causal_chain: ['[1] 下游微服务抛出未捕获异常', '[2] 返回 HTTP 500'],
    suggested_action: '增加参数空值判断与默认值兜底',
    platform: 'GITHUB_ISSUE',
    is_critical_asset: false,
  },
  minor_robot: {
    case_id: 'case_ui_303',
    case_name: '购物车结算按钮点击流',
    category: 'UI_DOM_LOCATOR_DRIFT',
    primary_summary: '按钮 DOM 选择器失效漂移',
    culprit_service: 'frontend-web',
    culprit_location: 'cart_view.vue:42',
    causal_chain: ['[1] 前端页面样式重命名', '[2] 定位器超时未找到'],
    suggested_action: '采用 Smart Locator 自愈定位器修正',
    platform: 'WEBHOOK_ROBOT',
    is_critical_asset: false,
  },
}

function applyPreset(key: 'critical_jira' | 'major_gh' | 'minor_robot') {
  presetKey.value = key
  const p = PRESETS[key]
  ticketForm.platform = p.platform
  ticketForm.culprit_service = p.culprit_service
  ticketForm.override_assignee = ''
  handleDispatchTicket()
}

async function handleDispatchTicket() {
  dispatching.value = true
  try {
    const p = PRESETS[presetKey.value]
    const res = await defectTicketDispatchApi.dispatch({
      case_id: p.case_id,
      case_name: p.case_name,
      category: p.category,
      primary_summary: p.primary_summary,
      culprit_service: ticketForm.culprit_service || p.culprit_service,
      culprit_location: p.culprit_location,
      causal_chain: p.causal_chain,
      suggested_action: p.suggested_action,
      platform: ticketForm.platform,
      override_assignee: ticketForm.override_assignee || undefined,
      is_critical_asset: p.is_critical_asset,
    })
    lastDispatchedTicket.value = res.ticket
    message.success(res.message || '工单已自动创建并派发')
    await fetchTickets()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '建单失败')
  } finally {
    dispatching.value = false
  }
}

async function fetchTickets() {
  loadingTickets.value = true
  try {
    const params: any = {}
    if (filterPlatform.value && filterPlatform.value !== 'all') {
      params.platform = filterPlatform.value
    }
    const res = await defectTicketDispatchApi.listTickets(params)
    tickets.value = res.tickets
  } catch {
    // ignore
  } finally {
    loadingTickets.value = false
  }
}

async function handleResolveTicket(ticketId: string) {
  try {
    await defectTicketDispatchApi.updateStatus(ticketId, 'RESOLVED')
    message.success('工单已标记为 RESOLVED 已解决')
    await fetchTickets()
    if (lastDispatchedTicket.value?.ticket_id === ticketId) {
      lastDispatchedTicket.value.status = 'RESOLVED'
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '更新状态失败')
  }
}

function copyTicketDesc(desc: string) {
  void navigator.clipboard.writeText(desc)
  message.success('已复制 Markdown 工单描述')
}

onMounted(() => {
  handleDispatchTicket()
})
</script>

<style scoped>
.defect-dispatch-card {
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

.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.f-lbl {
  font-size: 12px;
  color: #64748b;
}

/* 建单反馈横幅 */
.ticket-feedback-banner {
  border-radius: 8px;
  padding: 14px 18px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.banner-sev-critical {
  background: #fef2f2;
  border-color: #fecaca;
}

.banner-sev-major {
  background: #fff7ed;
  border-color: #fed7aa;
}

.banner-sev-minor {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.feedback-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feedback-badge-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sev-tag {
  font-size: 12px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 4px;
}

.tag-critical {
  background: #dc2626;
  color: #ffffff;
}

.tag-major {
  background: #ea580c;
  color: #ffffff;
}

.tag-minor {
  background: #64748b;
  color: #ffffff;
}

.ext-id {
  font-size: 13px;
  color: #0369a1;
  font-family: Consolas, monospace;
}

.assignee-text {
  font-size: 12px;
  color: #334155;
}

.feedback-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.desc-preview {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
  max-height: 120px;
  overflow-y: auto;
}

.desc-code {
  font-family: Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  margin: 0;
  color: #334155;
  white-space: pre-wrap;
}

/* 工单列表区 */
.tickets-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sec-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.tickets-table {
  background: #ffffff;
}

.ext-code {
  font-size: 11px;
  color: #0284c7;
  font-family: Consolas, monospace;
}

.ticket-title-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label-chips {
  display: flex;
  gap: 4px;
}

.assignee-val {
  font-size: 11px;
  color: #334155;
}

.text-green {
  color: #16a34a;
}

.text-xs {
  font-size: 11px;
}
</style>
