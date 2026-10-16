<template>
  <a-drawer
    :open="open"
    :width="980"
    placement="right"
    title="企微 / 钉钉 / 飞书富文本交互式卡片 Webhook 智能广播"
    destroy-on-close
    @close="handleClose"
  >
    <div class="notification-broadcast-drawer">
      <!-- 头部介绍与脱敏安全说明 -->
      <div class="drawer-banner">
        <div class="banner-left">
          <SendOutlined class="banner-icon" />
          <div>
            <div class="banner-title-row">
              <span class="banner-title">全渠道交互式告警通知中枢 (Notification Hub)</span>
              <a-tag color="processing">多渠道并发适配</a-tag>
              <a-tag color="success">Token 自动脱敏</a-tag>
            </div>
            <p class="banner-desc">
              适配主流协同工作台的富文本卡片协议（企微 template_card、钉钉 actionCard、飞书 interactive），支持所见即所得实时预览与全网广播。
            </p>
          </div>
        </div>
      </div>

      <!-- 投递统计 KPI 卡片 -->
      <div class="stats-grid">
        <div class="kpi-mini-card">
          <span class="kpi-label">累计广播流水</span>
          <span class="kpi-num">{{ stats.total_dispatched_count }}</span>
          <span class="kpi-sub">多通道审计留痕</span>
        </div>
        <div class="kpi-mini-card">
          <span class="kpi-label">全域投递成功率</span>
          <span class="kpi-num text-success">{{ (stats.overall_success_rate_pct || 0).toFixed(1) }}%</span>
          <span class="kpi-sub">端到端网络交付率</span>
        </div>
        <div class="kpi-mini-card">
          <span class="kpi-label">企微分发占比</span>
          <span class="kpi-num text-blue">{{ stats.channel_distribution?.wechat || 0 }} 次</span>
          <span class="kpi-sub">企业微信机器人</span>
        </div>
        <div class="kpi-mini-card">
          <span class="kpi-label">钉钉 / 飞书占比</span>
          <span class="kpi-num text-purple">
            {{ (stats.channel_distribution?.dingtalk || 0) + (stats.channel_distribution?.feishu || 0) }} 次
          </span>
          <span class="kpi-sub">协同卡片与行动点</span>
        </div>
      </div>

      <!-- 双栏编辑与预览区 -->
      <div class="editor-preview-grid">
        <!-- 左栏：目标路由与卡片参数配置 -->
        <div class="config-col">
          <a-card size="small" title="1. 广播目标通道配置 (Webhook Targets)" class="sub-panel">
            <template #extra>
              <a-button size="small" type="dashed" @click="addTarget">
                <PlusOutlined /> 增加通道
              </a-button>
            </template>

            <div class="targets-list">
              <div v-for="(tgt, index) in targets" :key="index" class="target-row-card">
                <div class="target-top-line">
                  <a-select v-model:value="tgt.channel" size="small" style="width: 110px">
                    <a-select-option value="wechat">企业微信</a-select-option>
                    <a-select-option value="dingtalk">钉钉群</a-select-option>
                    <a-select-option value="feishu">飞书机器人</a-select-option>
                    <a-select-option value="slack">Slack</a-select-option>
                  </a-select>
                  <a-switch v-model:checked="tgt.enabled" size="small" checked-children="开" un-checked-children="关" />
                  <a-button
                    v-if="targets.length > 1"
                    type="link"
                    size="small"
                    danger
                    @click="removeTarget(index)"
                  >
                    删除
                  </a-button>
                </div>
                <div class="target-inputs">
                  <a-input
                    v-model:value="tgt.webhook_url"
                    size="small"
                    placeholder="Webhook 回调完整 URL"
                  />
                  <a-input
                    v-model:value="tgt.secret"
                    size="small"
                    placeholder="加签 Secret (可选)"
                    style="margin-top: 4px"
                  />
                </div>
              </div>
            </div>
          </a-card>

          <a-card size="small" title="2. 卡片消息参数配置 (Payload)" class="sub-panel" style="margin-top: 12px">
            <a-form layout="vertical">
              <a-form-item label="卡片主标题" required>
                <a-input v-model:value="cardForm.title" />
              </a-form-item>

              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="状态类型">
                    <a-select v-model:value="cardForm.status">
                      <a-select-option value="passed">全部通过 (passed)</a-select-option>
                      <a-select-option value="failed">用例失败 (failed)</a-select-option>
                      <a-select-option value="blocked">告警阻断 (blocked)</a-select-option>
                      <a-select-option value="approved">审批准入 (approved)</a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="投递优先级">
                    <a-select v-model:value="priority">
                      <a-select-option value="P0">P0 (紧急阻断)</a-select-option>
                      <a-select-option value="P1">P1 (高优先级)</a-select-option>
                      <a-select-option value="P2">P2 (普通通报)</a-select-option>
                      <a-select-option value="P3">P3 (定期摘要)</a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="业务项目名称">
                    <a-input v-model:value="cardForm.project_name" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="执行批次 Run ID">
                    <a-input v-model:value="cardForm.run_id" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="通过率 (%)">
                    <a-input-number v-model:value="cardForm.pass_rate_pct" :min="0" :max="100" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="执行总耗时 (秒)">
                    <a-input-number v-model:value="cardForm.duration_sec" :min="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item label="报告跳转链接 URL">
                <a-input v-model:value="cardForm.report_url" placeholder="https://app.atp.io/runs/101" />
              </a-form-item>

              <a-form-item label="详细摘要描述 (Markdown)">
                <a-textarea v-model:value="cardForm.summary" :rows="3" />
              </a-form-item>
            </a-form>
          </a-card>
        </div>

        <!-- 右栏：多平台所见即所得卡片预览 -->
        <div class="preview-col">
          <a-card size="small" title="3. 交互式卡片效果实时预览 (Live WYSIWYG)" class="sub-panel">
            <a-tabs v-model:activeKey="previewTab">
              <!-- 企业微信 template_card 效果预览 -->
              <a-tab-pane key="wechat" tab="企业微信 (template_card)">
                <div class="mock-device wechat-preview-shell">
                  <div class="wechat-card" :class="`wechat-status-${cardForm.status}`">
                    <div class="wechat-header">
                      <span class="wechat-badge">{{ getStatusLabel(cardForm.status) }}</span>
                      <span class="wechat-title">{{ cardForm.title }}</span>
                    </div>
                    <div class="wechat-desc">{{ cardForm.summary }}</div>
                    <div class="wechat-kv-list">
                      <div class="wechat-kv-row">
                        <span class="kv-k">项目名称:</span>
                        <span class="kv-v">{{ cardForm.project_name }}</span>
                      </div>
                      <div class="wechat-kv-row">
                        <span class="kv-k">执行批次:</span>
                        <span class="kv-v font-mono">Run #{{ cardForm.run_id }}</span>
                      </div>
                      <div class="wechat-kv-row">
                        <span class="kv-k">通过率:</span>
                        <span class="kv-v font-bold" :class="cardForm.pass_rate_pct >= 90 ? 'text-green' : 'text-red'">
                          {{ cardForm.pass_rate_pct }}%
                        </span>
                      </div>
                      <div class="wechat-kv-row">
                        <span class="kv-k">总耗时:</span>
                        <span class="kv-v">{{ cardForm.duration_sec }}s</span>
                      </div>
                    </div>
                    <div class="wechat-footer-action">
                      <a class="wechat-btn" :href="cardForm.report_url || '#'" target="_blank">查看全量测试报告 &gt;</a>
                    </div>
                  </div>
                </div>
              </a-tab-pane>

              <!-- 钉钉 actionCard 效果预览 -->
              <a-tab-pane key="dingtalk" tab="钉钉 (actionCard)">
                <div class="mock-device dingtalk-preview-shell">
                  <div class="dingtalk-card">
                    <div class="dingtalk-header-banner" :class="`dt-banner-${cardForm.status}`">
                      <span class="dt-tag">钉钉自动化通报</span>
                      <span class="dt-status">{{ getStatusLabel(cardForm.status) }}</span>
                    </div>
                    <div class="dingtalk-body">
                      <h4 class="dt-title">{{ cardForm.title }}</h4>
                      <p class="dt-summary">{{ cardForm.summary }}</p>
                      <div class="dt-info-box">
                        <div><strong>项目:</strong> {{ cardForm.project_name }}</div>
                        <div><strong>批次:</strong> #{{ cardForm.run_id }}</div>
                        <div><strong>通过率:</strong> {{ cardForm.pass_rate_pct }}% (耗时 {{ cardForm.duration_sec }}s)</div>
                      </div>
                    </div>
                    <div class="dingtalk-action-btn">
                      <a :href="cardForm.report_url || '#'" target="_blank">查看测试报告详情</a>
                    </div>
                  </div>
                </div>
              </a-tab-pane>

              <!-- 飞书 interactive 效果预览 -->
              <a-tab-pane key="feishu" tab="飞书 (interactive)">
                <div class="mock-device feishu-preview-shell">
                  <div class="feishu-card">
                    <div class="feishu-header" :class="`fs-header-${cardForm.status}`">
                      <span class="fs-title">{{ cardForm.title }}</span>
                    </div>
                    <div class="feishu-body">
                      <div class="fs-summary">{{ cardForm.summary }}</div>
                      <div class="fs-fields-grid">
                        <div class="fs-field">
                          <span class="fs-k">项目</span>
                          <span class="fs-v">{{ cardForm.project_name }}</span>
                        </div>
                        <div class="fs-field">
                          <span class="fs-k">批次</span>
                          <span class="fs-v">#{{ cardForm.run_id }}</span>
                        </div>
                        <div class="fs-field">
                          <span class="fs-k">通过率</span>
                          <span class="fs-v font-bold">{{ cardForm.pass_rate_pct }}%</span>
                        </div>
                        <div class="fs-field">
                          <span class="fs-k">耗时</span>
                          <span class="fs-v">{{ cardForm.duration_sec }}s</span>
                        </div>
                      </div>
                      <div class="fs-action-row">
                        <button class="fs-btn">查看详情报告</button>
                      </div>
                    </div>
                  </div>
                </div>
              </a-tab-pane>
            </a-tabs>

            <!-- 广播投递触发按钮 -->
            <div class="broadcast-action-bar">
              <a-button type="primary" size="large" :loading="broadcasting" block @click="handleBroadcast">
                <SendOutlined /> 一键全渠道并发广播
              </a-button>
            </div>
          </a-card>
        </div>
      </div>

      <!-- 底部投递审计流水表格 -->
      <a-card size="small" title="近期 Webhook 消息投递审计流水 (Delivery Audits)" class="audit-history-panel" style="margin-top: 16px">
        <template #extra>
          <a-space>
            <a-button size="small" @click="loadData">刷新审计</a-button>
          </a-space>
        </template>
        <a-table
          :data-source="audits"
          :columns="auditColumns"
          row-key="delivery_id"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'channel'">
              <a-tag :color="getChannelColor(record.channel)">
                {{ record.channel.toUpperCase() }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'target_webhook_masked'">
              <span class="mono-text" :title="record.target_webhook_masked">{{ record.target_webhook_masked }}</span>
            </template>
            <template v-else-if="column.key === 'priority'">
              <a-tag :color="record.priority === 'P0' ? 'error' : 'default'">{{ record.priority }}</a-tag>
            </template>
            <template v-else-if="column.key === 'success'">
              <a-tag :color="record.success ? 'success' : 'error'">
                {{ record.success ? '投递成功' : '投递失败' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'duration_ms'">
              <span class="mono-text">{{ record.duration_ms }} ms</span>
            </template>
            <template v-else-if="column.key === 'dispatched_at'">
              <small class="mono-text">{{ formatTime(record.dispatched_at) }}</small>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  SendOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'
import {
  notificationHubApi,
  type NotificationRouteTarget,
  type DeliveryAuditRecordItem,
  type DispatcherStats,
  type DeliveryPriority,
} from '@/api/notificationHub'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const broadcasting = ref(false)
const previewTab = ref<'wechat' | 'dingtalk' | 'feishu'>('wechat')
const priority = ref<DeliveryPriority>('P2')

const targets = ref<NotificationRouteTarget[]>([
  {
    channel: 'wechat',
    webhook_url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=wx_mock_token_key_123',
    secret: '',
    enabled: true,
  },
  {
    channel: 'dingtalk',
    webhook_url: 'https://oapi.dingtalk.com/robot/send?access_token=dt_mock_access_token_456',
    secret: '',
    enabled: true,
  },
  {
    channel: 'feishu',
    webhook_url: 'https://open.feishu.cn/open-apis/bot/v2/hook/fs_mock_token_789',
    secret: '',
    enabled: true,
  },
])

const cardForm = reactive({
  title: '[ATP自动化测试通报] 核心链路用例全量回归完成',
  summary: '本次执行已自动化通过所有 P0/P1 用例，发现 2 处非破坏性 Schema 漂移并由 AI 自动自愈放行。',
  status: 'passed',
  project_name: 'ATP-Platform',
  run_id: '501',
  pass_rate_pct: 98.5,
  duration_sec: 145.2,
  report_url: 'https://app.atp.io/runs/501',
})

const stats = reactive<DispatcherStats>({
  total_dispatched_count: 0,
  overall_success_rate_pct: 100,
  channel_distribution: {},
})

const audits = ref<DeliveryAuditRecordItem[]>([])

const auditColumns = [
  { title: '渠道', key: 'channel', width: 110 },
  { title: '脱敏 Webhook 目标', key: 'target_webhook_masked', width: 320 },
  { title: '优先级', key: 'priority', width: 80 },
  { title: '状态', key: 'success', width: 100 },
  { title: '耗时', key: 'duration_ms', width: 90 },
  { title: '投递时间', key: 'dispatched_at', width: 150 },
]

function getStatusLabel(s: string): string {
  switch (s) {
    case 'passed':
      return '测试通过'
    case 'failed':
      return '测试失败'
    case 'blocked':
      return '告警阻断'
    case 'approved':
      return '准入批准'
    default:
      return s
  }
}

function getChannelColor(channel: string): string {
  switch (channel) {
    case 'wechat':
      return 'green'
    case 'dingtalk':
      return 'blue'
    case 'feishu':
      return 'purple'
    case 'slack':
      return 'orange'
    default:
      return 'default'
  }
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return isoStr
  }
}

function addTarget() {
  targets.value.push({
    channel: 'wechat',
    webhook_url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=new_token_key',
    secret: '',
    enabled: true,
  })
}

function removeTarget(index: number) {
  targets.value.splice(index, 1)
}

async function loadData() {
  try {
    const [statsRes, auditsRes] = await Promise.all([
      notificationHubApi.getStats(),
      notificationHubApi.listAudits(),
    ])
    Object.assign(stats, statsRes)
    audits.value = auditsRes.records || []
  } catch {
    // 忽略加载错误
  }
}

async function handleBroadcast() {
  broadcasting.value = true
  try {
    const res = await notificationHubApi.broadcast({
      targets: targets.value,
      card: cardForm,
      priority: priority.value,
    })
    message.success(res.message || '全渠道广播投递成功')
    await loadData()
  } catch (err: any) {
    message.error(`广播失败: ${err.message || err}`)
  } finally {
    broadcasting.value = false
  }
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.notification-broadcast-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.banner-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.banner-icon {
  font-size: 24px;
  color: #2563eb;
  margin-top: 2px;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.banner-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-mini-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
}

.kpi-label {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.kpi-num {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
}

.kpi-sub {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
}

.text-success {
  color: #10b981;
}

.text-blue {
  color: #2563eb;
}

.text-purple {
  color: #8b5cf6;
}

/* 编辑与预览双栏 */
.editor-preview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.sub-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.targets-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 240px;
  overflow-y: auto;
}

.target-row-card {
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.target-top-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

/* 所见即所得手机卡片样式 */
.mock-device {
  background: #f1f5f9;
  border-radius: 8px;
  padding: 16px;
  min-height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 企业微信卡片 */
.wechat-card {
  width: 100%;
  max-width: 380px;
  background: #ffffff;
  border-radius: 6px;
  padding: 14px 16px;
  border-top: 4px solid #10b981;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.wechat-status-failed {
  border-top-color: #ef4444;
}

.wechat-status-blocked {
  border-top-color: #f59e0b;
}

.wechat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.wechat-badge {
  background: #ecfdf5;
  color: #059669;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
}

.wechat-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.wechat-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 10px;
}

.wechat-kv-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-top: 1px solid #f1f5f9;
  padding-top: 8px;
  margin-bottom: 12px;
}

.wechat-kv-row {
  display: flex;
  font-size: 12px;
}

.kv-k {
  color: #94a3b8;
  width: 70px;
}

.kv-v {
  color: #1e293b;
}

.wechat-footer-action {
  border-top: 1px solid #f1f5f9;
  padding-top: 8px;
}

.wechat-btn {
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
}

/* 钉钉卡片 */
.dingtalk-card {
  width: 100%;
  max-width: 380px;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.dingtalk-header-banner {
  background: #2563eb;
  color: #ffffff;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 700;
}

.dt-banner-failed {
  background: #dc2626;
}

.dingtalk-body {
  padding: 12px 14px;
}

.dt-title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.dt-summary {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 8px;
}

.dt-info-box {
  background: #f8fafc;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  color: #334155;
  line-height: 1.6;
}

.dingtalk-action-btn {
  border-top: 1px solid #f1f5f9;
  padding: 8px;
  text-align: center;
}

.dingtalk-action-btn a {
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
}

/* 飞书卡片 */
.feishu-card {
  width: 100%;
  max-width: 380px;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.feishu-header {
  background: #00d6b9;
  color: #ffffff;
  padding: 10px 14px;
}

.fs-header-failed {
  background: #f54a45;
}

.fs-title {
  font-size: 13px;
  font-weight: 700;
}

.feishu-body {
  padding: 12px 14px;
}

.fs-summary {
  font-size: 12px;
  color: #475569;
  margin-bottom: 10px;
}

.fs-fields-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: #f8fafc;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 12px;
}

.fs-field {
  display: flex;
  flex-direction: column;
}

.fs-k {
  font-size: 10px;
  color: #94a3b8;
}

.fs-v {
  font-size: 12px;
  color: #1e293b;
}

.fs-action-row {
  display: flex;
}

.fs-btn {
  width: 100%;
  background: #3370ff;
  color: #ffffff;
  border: none;
  padding: 6px 0;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.broadcast-action-bar {
  margin-top: 16px;
}

.mono-text {
  font-family: monospace;
  font-size: 11px;
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: 700;
}

.text-green {
  color: #10b981;
}

.text-red {
  color: #ef4444;
}
</style>
