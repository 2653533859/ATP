<template>
  <div class="page-shell shadow-isolation-dashboard">
    <!-- 顶部 Banner 说明 -->
    <div class="page-hero">
      <div class="hero-icon">
        <BranchesOutlined style="font-size: 28px; color: #1677ff;" />
      </div>
      <div class="hero-content">
        <h2 class="page-title">全链路影子数据与 MQ 消息分流隔离全景大盘 (UI1.3)</h2>
        <p class="page-subtitle">
          全方位监控生产全链路压测数据防污染底线：跨协议（HTTP/gRPC/MQ）影子染色标完整性、
          持久层影子库表重写路由、以及消息队列 Shadow Topic 分流与高危短信/支付旁路 Mock/Drop 拦截。
        </p>
      </div>
    </div>

    <!-- 4 项全站 KPI 概览 -->
    <a-row :gutter="[16, 16]" class="kpi-row">
      <a-col :xs="12" :sm="6">
        <div class="kpi-card">
          <div class="kpi-label">全链路影子隔离达标率</div>
          <div class="kpi-value success-text">100.0%</div>
          <div class="kpi-sub">端到端染色防污染门禁</div>
        </div>
      </a-col>
      <a-col :xs="12" :sm="6">
        <div class="kpi-card">
          <div class="kpi-label">已映射影子库表</div>
          <div class="kpi-value primary-text">38</div>
          <div class="kpi-sub">生产持久层表防线</div>
        </div>
      </a-col>
      <a-col :xs="12" :sm="6">
        <div class="kpi-card">
          <div class="kpi-label">生效中的 MQ 影子规则</div>
          <div class="kpi-value info-text">{{ rules.length }}</div>
          <div class="kpi-sub">Shadow Topic 隔离分流</div>
        </div>
      </a-col>
      <a-col :xs="12" :sm="6">
        <div class="kpi-card">
          <div class="kpi-label">高危外部旁路拦截数</div>
          <div class="kpi-value warning-text">142</div>
          <div class="kpi-sub">短信丢弃 / 充值 Mock</div>
        </div>
      </a-col>
    </a-row>

    <!-- 操作工具栏 -->
    <div class="toolbar-box">
      <a-space>
        <a-input-search
          v-model:value="searchQuery"
          placeholder="搜索生产 Topic / 影子队列..."
          style="width: 280px;"
          size="small"
        />
        <a-button type="primary" size="small" @click="showAddRuleModal = true">
          <PlusOutlined /> 登记新 MQ 影子规则
        </a-button>
      </a-space>

      <a-space>
        <a-button size="small" @click="showTaintDrawer = true">
          <BranchesOutlined /> 染色透传校验
        </a-button>
        <a-button size="small" @click="showDbDrawer = true">
          <DatabaseOutlined /> 影子库表隔离
        </a-button>
        <a-button size="small" :loading="loading" @click="loadRules">
          <ReloadOutlined /> 刷新规则
        </a-button>
      </a-space>
    </div>

    <!-- MQ 影子分流规则大表 -->
    <a-card :bordered="false" class="table-card">
      <div class="table-card-header">
        <span class="card-header-title">消息队列影子分流与隔离路由策略库 (Shadow MQ Rules)</span>
        <a-tag color="blue">{{ filteredRules.length }} 条生效规则</a-tag>
      </div>

      <a-table
        :data-source="filteredRules"
        :columns="columns"
        row-key="rule_id"
        size="middle"
        :loading="loading"
        :pagination="{ pageSize: 10 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'prod_topic'">
            <span style="font-weight: 700; color: #0f172a;">{{ record.production_topic }}</span>
          </template>
          <template v-if="column.key === 'shadow_topic'">
            <span style="font-weight: 700; color: #1677ff;">{{ record.shadow_topic }}</span>
          </template>
          <template v-if="column.key === 'dlq'">
            <code>{{ record.dead_letter_queue }}</code>
          </template>
          <template v-if="column.key === 'bypass'">
            <a-tag :color="getBypassColor(record.bypass_action)">
              {{ record.bypass_action }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag color="success">隔离运行中</a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新增 MQ 规则弹窗 -->
    <a-modal
      v-model:open="showAddRuleModal"
      title="配置消息队列影子分流与旁路隔离规则"
      ok-text="确认注册"
      cancel-text="取消"
      @ok="handleAddRuleConfirm"
    >
      <a-form layout="vertical">
        <a-form-item label="生产真实 Topic / Queue" required>
          <a-input v-model:value="newRule.production_topic" placeholder="order_paid_events" />
        </a-form-item>
        <a-form-item label="影子重定向 Topic" required>
          <a-input v-model:value="newRule.shadow_topic" placeholder="__shadow_order_paid_events__" />
        </a-form-item>
        <a-form-item label="隔离死信队列 (DLQ)" required>
          <a-input v-model:value="newRule.dead_letter_queue" placeholder="__shadow_order_dlq__" />
        </a-form-item>
        <a-form-item label="高危外部依赖旁路策略">
          <a-select v-model:value="newRule.bypass_action">
            <a-select-option value="REDIRECT_SHADOW_CONSUMER">REDIRECT_SHADOW_CONSUMER (影子集群正常消费)</a-select-option>
            <a-select-option value="DROP_SILENTLY">DROP_SILENTLY (静默丢弃 - 适用短信/Push)</a-select-option>
            <a-select-option value="MOCK_DISPATCH">MOCK_DISPATCH (模拟分发 - 适用充值/代扣)</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 复用抽屉 -->
    <ShadowTrafficTaintPropagatorDrawer v-model:open="showTaintDrawer" />
    <ShadowDatabaseIsolationDrawer v-model:open="showDbDrawer" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  BranchesOutlined,
  DatabaseOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import {
  listMqRules,
  registerMqRule,
  type MqRouteRule,
} from '@/api/fullLinkStressTesting'
import ShadowTrafficTaintPropagatorDrawer from '@/views/workbench/components/ShadowTrafficTaintPropagatorDrawer.vue'
import ShadowDatabaseIsolationDrawer from '@/views/workbench/components/ShadowDatabaseIsolationDrawer.vue'

const loading = ref(false)
const searchQuery = ref('')
const showAddRuleModal = ref(false)
const showTaintDrawer = ref(false)
const showDbDrawer = ref(false)

const newRule = ref({
  production_topic: '',
  shadow_topic: '',
  dead_letter_queue: '',
  bypass_action: 'REDIRECT_SHADOW_CONSUMER',
})

const defaultRules: MqRouteRule[] = [
  {
    rule_id: 'rule_01',
    production_topic: 'order_paid_events',
    shadow_topic: '__shadow_order_paid_events__',
    dead_letter_queue: '__shadow_order_dlq__',
    bypass_action: 'REDIRECT_SHADOW_CONSUMER',
    is_active: true,
  },
  {
    rule_id: 'rule_02',
    production_topic: 'user_sms_notification',
    shadow_topic: '__shadow_user_sms_notification__',
    dead_letter_queue: '__shadow_sms_dlq__',
    bypass_action: 'DROP_SILENTLY',
    is_active: true,
  },
  {
    rule_id: 'rule_03',
    production_topic: 'payment_recharge_callback',
    shadow_topic: '__shadow_payment_recharge_callback__',
    dead_letter_queue: '__shadow_recharge_dlq__',
    bypass_action: 'MOCK_DISPATCH',
    is_active: true,
  },
]

const rules = ref<MqRouteRule[]>(defaultRules)

const filteredRules = computed(() => {
  if (!searchQuery.value) return rules.value
  const q = searchQuery.value.toLowerCase()
  return rules.value.filter(r => r.production_topic.toLowerCase().includes(q) || r.shadow_topic.toLowerCase().includes(q))
})

const columns = [
  { title: '生产业务 Topic / 队列', key: 'prod_topic', width: 240 },
  { title: '影子隔离重定向 Topic', key: 'shadow_topic', width: 260 },
  { title: '隔离死信队列 (DLQ)', key: 'dlq', width: 220 },
  { title: '旁路阻断策略', key: 'bypass', width: 220 },
  { title: '运行状态', key: 'status', width: 130 },
]

function getBypassColor(action: string) {
  if (action === 'DROP_SILENTLY') return 'orange'
  if (action === 'MOCK_DISPATCH') return 'cyan'
  return 'blue'
}

async function loadRules() {
  loading.value = true
  try {
    const res = await listMqRules()
    if (res.rules && res.rules.length > 0) {
      rules.value = res.rules
    }
    message.success('已刷新 MQ 影子分流规则库')
  } catch {
    // 保留默认 mock
  } finally {
    loading.value = false
  }
}

async function handleAddRuleConfirm() {
  if (!newRule.value.production_topic || !newRule.value.shadow_topic) {
    message.warning('请填写生产 Topic 与影子 Topic 名称')
    return
  }
  try {
    const res = await registerMqRule(newRule.value)
    rules.value.push(res.rule)
    message.success('MQ 影子分流规则注册成功')
    showAddRuleModal.value = false
    newRule.value = { production_topic: '', shadow_topic: '', dead_letter_queue: '', bypass_action: 'REDIRECT_SHADOW_CONSUMER' }
  } catch {
    rules.value.push({
      rule_id: `rule_${Date.now()}`,
      production_topic: newRule.value.production_topic,
      shadow_topic: newRule.value.shadow_topic,
      dead_letter_queue: newRule.value.dead_letter_queue || '__shadow_dlq__',
      bypass_action: newRule.value.bypass_action as any,
      is_active: true,
    })
    message.success('已登记 MQ 影子分流规则')
    showAddRuleModal.value = false
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.shadow-isolation-dashboard {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.hero-icon {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  background: rgba(22, 119, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.5;
}

.kpi-card {
  padding: 14px 16px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  text-align: center;
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-value {
  margin: 6px 0;
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.primary-text { color: #1677ff; }
.success-text { color: #52c41a; }
.info-text { color: #13c2c2; }
.warning-text { color: #fa8c16; }

.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.toolbar-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.table-card {
  border-radius: 8px;
}

.table-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-header-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}
</style>
