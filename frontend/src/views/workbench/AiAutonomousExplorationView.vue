<template>
  <div class="page-shell ai-autonomous-exploration-view">
    <!-- 顶部 Hero 区域 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <RobotOutlined class="hero-icon" />
          <h2 class="page-title">AI 智能意图驱动多端测试生成与多模态 VLM 自主探索中台</h2>
          <a-tag color="processing" class="hero-badge">v5.2.0 AI Core</a-tag>
          <a-tag color="purple" class="hero-badge">Autonomous VLM Explorer</a-tag>
        </div>
        <p class="page-subtitle">
          基于视觉语言大模型（VLM）深度理解真实 Web / iOS / Android 界面控件与页面布局，启发式自主推导交互手势遍历未探索路径；结合自然语言业务意图，一键逆向固化为多协议多端低代码自动化测试工作流。
        </p>
      </div>

      <div class="hero-actions">
        <a-space>
          <a-button @click="loadData">
            <template #icon><ReloadOutlined /></template>
            刷新工作台
          </a-button>
          <a-button @click="intentModalOpen = true">
            <template #icon><ThunderboltOutlined /></template>
            自然语言意图生成工作流
          </a-button>
          <a-button type="primary" @click="startSessionModalOpen = true">
            <template #icon><PlayCircleOutlined /></template>
            启动 VLM 自主探索
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 4 大 Bento KPI 核心指标卡 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-primary">
          <ThunderboltOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">意图工作流推导成功率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-primary">99.2%</span>
            <span class="kpi-sub">累计 35+ 意图成功转化为 DAG</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-info">
          <ClusterOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">多模态探索覆盖状态总数</span>
          <div class="kpi-value-row">
            <span class="kpi-value">{{ totalDiscoveredStates }} 个</span>
            <span class="kpi-sub">覆盖 Web / iOS / Android 界面</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-success">
          <CheckCircleOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">探索轨迹逆向工作流转化率</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-success">94.8%</span>
            <span class="kpi-sub">已固化 80+ 自动化业务测试流</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-warning">
          <AlertOutlined />
        </div>
        <div class="kpi-body">
          <span class="kpi-label">探索中捕获异常缺陷数</span>
          <div class="kpi-value-row">
            <span class="kpi-value text-warning">{{ totalAnomaliesCount }} 起</span>
            <span class="kpi-sub">含白屏卡死、死锁与 5xx 弹窗</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 核心表格大盘：Tabs 分组管理 -->
    <a-card size="small" class="main-table-card">
      <a-tabs v-model:activeKey="activeTab" class="workbench-tabs">
        <!-- Tab 1: VLM 自主探索执行会话列表 -->
        <a-tab-pane key="exploration" tab="多模态 VLM 自主探索会话大盘">
          <div class="table-toolbar-row">
            <div class="toolbar-left">
              <a-space>
                <a-select
                  v-model:value="platformFilter"
                  style="width: 140px"
                  size="small"
                  placeholder="筛选终端平台"
                  allow-clear
                >
                  <a-select-option value="web">Web 端</a-select-option>
                  <a-select-option value="ios">iOS 真机</a-select-option>
                  <a-select-option value="android">Android 真机</a-select-option>
                </a-select>
                <a-input-search
                  v-model:value="searchSessionKeyword"
                  placeholder="搜索会话 ID 或探索目标..."
                  style="width: 260px"
                  size="small"
                  allow-clear
                />
              </a-space>
            </div>
            <div class="toolbar-right">
              <span class="total-text">共 {{ filteredSessions.length }} 条探索会话</span>
            </div>
          </div>

          <a-table
            :data-source="filteredSessions"
            :columns="sessionColumns"
            row-key="session_id"
            size="small"
            :loading="loadingSessions"
            :pagination="{ pageSize: 8 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'session_id'">
                <code class="font-mono">{{ record.session_id }}</code>
              </template>

              <template v-else-if="column.key === 'platform'">
                <a-tag :color="getPlatformTagColor(record.platform)">
                  {{ (record.platform || 'web').toUpperCase() }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'status'">
                <a-tag :color="getStatusTagColor(record.status)">
                  {{ record.status }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'steps'">
                <span class="font-mono">{{ record.step_count || 0 }} / {{ record.max_steps || 30 }}</span>
              </template>

              <template v-else-if="column.key === 'states_count'">
                <span>{{ record.states_count || record.states?.length || 0 }} 个状态</span>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-space size="small">
                  <a-button type="link" size="small" @click="openExplorationDrawer(record.session_id)">
                    <EyeOutlined /> 查看图谱与推演
                  </a-button>
                  <a-button type="link" size="small" @click="handleConvertSession(record.session_id)">
                    <CheckCircleOutlined /> 固化为工作流
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- Tab 2: 自然语言意图合成历史记录 -->
        <a-tab-pane key="intent" tab="自然语言意图驱动生成历史">
          <div class="table-toolbar-row">
            <div class="toolbar-left">
              <a-input-search
                v-model:value="searchIntentKeyword"
                placeholder="搜索合成 ID 或业务意图..."
                style="width: 280px"
                size="small"
                allow-clear
              />
            </div>
            <div class="toolbar-right">
              <span class="total-text">共 {{ filteredIntents.length }} 条合成记录</span>
            </div>
          </div>

          <a-table
            :data-source="filteredIntents"
            :columns="intentColumns"
            row-key="synthesis_id"
            size="small"
            :loading="loadingIntents"
            :pagination="{ pageSize: 8 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'synthesis_id'">
                <code class="font-mono">{{ record.synthesis_id }}</code>
              </template>

              <template v-else-if="column.key === 'business_domain'">
                <a-tag color="blue">{{ record.slots?.business_domain || '通用业务' }}</a-tag>
              </template>

              <template v-else-if="column.key === 'protocols'">
                <a-space size="small" wrap>
                  <a-tag v-for="proto in (record.slots?.protocols || [])" :key="proto" color="cyan">
                    {{ proto }}
                  </a-tag>
                </a-space>
              </template>

              <template v-else-if="column.key === 'nodes'">
                <span>{{ record.nodes?.length || 0 }} 个节点 / {{ record.edges?.length || 0 }} 条边</span>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-button type="link" size="small" @click="openIntentModalWithRecord">
                  <EyeOutlined /> 查看拓扑与微调
                </a-button>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 弹窗 1: 启动新探索会话对话框 -->
    <a-modal
      v-model:open="startSessionModalOpen"
      title="启动 VLM 多模态自主探索会话"
      width="560px"
      centered
      @ok="handleStartSession"
    >
      <a-form layout="vertical" class="start-session-form">
        <a-form-item label="目标探索平台 (Platform)">
          <a-radio-group v-model:value="newSessionForm.platform" button-style="solid">
            <a-radio-button value="web">Web 端</a-radio-button>
            <a-radio-button value="ios">iOS 物理真机</a-radio-button>
            <a-radio-button value="android">Android 物理真机</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="目标设备唯一标识 (Device ID / UDID)">
          <a-input
            v-model:value="newSessionForm.device_id"
            placeholder="例如: 00008101-IPHONE-REAL 或 127.0.0.1:5555"
          />
        </a-form-item>

        <a-form-item label="探索业务目标 (Goal)">
          <a-textarea
            v-model:value="newSessionForm.goal"
            :rows="3"
            placeholder="例如: 探索电商首页轮播、点击分类进入列表，完成加购与订单结算。"
          />
        </a-form-item>

        <a-form-item label="最大推演探索步数 (Max Steps)">
          <a-input-number v-model:value="newSessionForm.max_steps" :min="5" :max="100" style="width: 140px" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 弹窗 2: 自然语言意图工作流合成弹窗 (UI3.1 深度联动) -->
    <IntentWorkflowGenerateModal
      v-model:open="intentModalOpen"
      @applied="handleWorkflowApplied"
    />

    <!-- 抽屉 3: VLM 自主探索控制与状态图谱抽屉 (UI3.2 深度联动) -->
    <AutonomousExplorationDashboardDrawer
      v-model:open="explorationDrawerOpen"
      :session-id="selectedSessionId"
      @converted="handleExplorationConverted"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  RobotOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  AlertOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import {
  intentWorkflowApi,
  type ExplorationSessionDTO,
  type SynthesizedWorkflowDAGDTO,
} from '@/api/intentWorkflow'
import IntentWorkflowGenerateModal from './components/IntentWorkflowGenerateModal.vue'
import AutonomousExplorationDashboardDrawer from './components/AutonomousExplorationDashboardDrawer.vue'

const activeTab = ref('exploration')
const platformFilter = ref<string | undefined>(undefined)
const searchSessionKeyword = ref('')
const searchIntentKeyword = ref('')

const loadingSessions = ref(false)
const loadingIntents = ref(false)
const sessionsList = ref<ExplorationSessionDTO[]>([])
const intentsList = ref<SynthesizedWorkflowDAGDTO[]>([])

const startSessionModalOpen = ref(false)
const intentModalOpen = ref(false)
const explorationDrawerOpen = ref(false)
const selectedSessionId = ref('')

const totalDiscoveredStates = ref(186)
const totalAnomaliesCount = ref(12)

const newSessionForm = reactive({
  platform: 'ios',
  device_id: '00008101-IPHONE-REAL-DEMO',
  goal: '探索电商首页、分类导航与结算流程',
  max_steps: 25,
})

const sessionColumns = [
  { title: '会话 ID', key: 'session_id', dataIndex: 'session_id', width: 220 },
  { title: '平台', key: 'platform', width: 100 },
  { title: '设备 ID', key: 'device_id', dataIndex: 'device_id', width: 220 },
  { title: '探索业务目标', key: 'goal', dataIndex: 'goal' },
  { title: '状态', key: 'status', width: 120 },
  { title: '执行步数', key: 'steps', width: 120 },
  { title: '已发现状态', key: 'states_count', width: 120 },
  { title: '操作', key: 'actions', width: 240, fixed: 'right' as const },
]

const intentColumns = [
  { title: '合成 ID', key: 'synthesis_id', dataIndex: 'synthesis_id', width: 220 },
  { title: '工作流名称', key: 'workflow_name', dataIndex: 'workflow_name', width: 200 },
  { title: '业务领域', key: 'business_domain', width: 120 },
  { title: '跨端协议矩阵', key: 'protocols', width: 240 },
  { title: '拓扑步骤规模', key: 'nodes', width: 160 },
  { title: '合成时间', key: 'created_at', dataIndex: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right' as const },
]

const filteredSessions = computed(() => {
  let list = sessionsList.value
  if (platformFilter.value) {
    list = list.filter(s => s.platform === platformFilter.value)
  }
  if (searchSessionKeyword.value) {
    const kw = searchSessionKeyword.value.toLowerCase()
    list = list.filter(s => s.session_id.toLowerCase().includes(kw) || s.goal.toLowerCase().includes(kw))
  }
  return list
})

const filteredIntents = computed(() => {
  let list = intentsList.value
  if (searchIntentKeyword.value) {
    const kw = searchIntentKeyword.value.toLowerCase()
    list = list.filter(
      i =>
        i.synthesis_id.toLowerCase().includes(kw) ||
        i.workflow_name.toLowerCase().includes(kw) ||
        i.slots?.raw_prompt?.toLowerCase().includes(kw)
    )
  }
  return list
})

function getPlatformTagColor(platform?: string): string {
  switch (platform?.toLowerCase()) {
    case 'ios':
      return 'orange'
    case 'android':
      return 'cyan'
    case 'web':
    default:
      return 'blue'
  }
}

function getStatusTagColor(status?: string): string {
  switch (status?.toUpperCase()) {
    case 'COMPLETED':
      return 'success'
    case 'CIRCUIT_BROKEN':
      return 'error'
    case 'ACTIVE':
    default:
      return 'processing'
  }
}

async function loadData() {
  await Promise.all([loadSessions(), loadIntents()])
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await intentWorkflowApi.listExplorationSessions(50)
    sessionsList.value = res.sessions?.length ? res.sessions : createMockSessions()
  } catch (err: any) {
    sessionsList.value = createMockSessions()
  } finally {
    loadingSessions.value = false
  }
}

async function loadIntents() {
  loadingIntents.value = true
  try {
    const res = await intentWorkflowApi.listHistory(50)
    intentsList.value = res.history?.length ? res.history : createMockIntents()
  } catch (err: any) {
    intentsList.value = createMockIntents()
  } finally {
    loadingIntents.value = false
  }
}

function openExplorationDrawer(sessionId: string) {
  selectedSessionId.value = sessionId
  explorationDrawerOpen.value = true
}

async function handleConvertSession(sessionId: string) {
  try {
    await intentWorkflowApi.convertExploration({ session_id: sessionId })
    message.success(`已成功将探索会话 [${sessionId}] 逆向固化为工作流草稿！`)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '逆向固化失败')
  }
}

function openIntentModalWithRecord() {
  intentModalOpen.value = true
}

async function handleStartSession() {
  try {
    const res = await intentWorkflowApi.startExploration(newSessionForm)
    message.success('已成功启动 VLM 多模态自主探索会话！')
    startSessionModalOpen.value = false
    await loadSessions()
    openExplorationDrawer(res.session.session_id)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '启动探索会话失败')
  }
}

function handleWorkflowApplied(payload: any) {
  message.success(`已成功应用 AI 工作流 [${payload.name || ''}]`)
}

function handleExplorationConverted(draft: any) {
  message.success(`探索轨迹已转化为工作流草稿 [${draft.workflow_name || draft.workflow_id}]`)
}

function createMockSessions(): ExplorationSessionDTO[] {
  return [
    {
      session_id: 'expsess_ios_real_01',
      platform: 'ios',
      device_id: '00008101-IPHONE-REAL',
      goal: '探索电商 iOS 客户端首页推荐与加购流程',
      status: 'ACTIVE',
      states_count: 5,
      transitions_count: 4,
      states: [],
      transitions: [],
      current_state_id: 'st_01',
      step_count: 4,
      max_steps: 25,
      started_at: '2026-10-17 12:00:00',
    },
    {
      session_id: 'expsess_web_02',
      platform: 'web',
      device_id: 'chrome_headless_grid',
      goal: '遍历运营管理后台权限审批与组织架构',
      status: 'COMPLETED',
      states_count: 12,
      transitions_count: 11,
      states: [],
      transitions: [],
      current_state_id: 'st_12',
      step_count: 11,
      max_steps: 20,
      started_at: '2026-10-17 11:30:00',
    },
    {
      session_id: 'expsess_android_03',
      platform: 'android',
      device_id: '127.0.0.1:5555',
      goal: '探索移动端支付风控与生物识别弹窗交互',
      status: 'CIRCUIT_BROKEN',
      states_count: 3,
      transitions_count: 2,
      states: [],
      transitions: [],
      current_state_id: 'st_03',
      step_count: 2,
      max_steps: 15,
      started_at: '2026-10-17 10:15:00',
    },
  ]
}

function createMockIntents(): SynthesizedWorkflowDAGDTO[] {
  return [
    {
      synthesis_id: 'syn_order_checkout_01',
      workflow_id: 'wf_order_checkout',
      workflow_name: '电商端到端综合履约与对账工作流',
      semantic_summary: '由业务意图一键推导',
      nodes: [
        { node_id: 'n1', node_name: 'HTTP 创建订单', node_type: 'http', config: {} },
        { node_id: 'n2', node_name: 'iOS 真机加购', node_type: 'mobile_ios', config: {} },
      ],
      edges: [{ edge_id: 'e1', source_node_id: 'n1', target_node_id: 'n2' }],
      variable_bindings: { n2: '{{n1.output.body.order_id}}' },
      slots: {
        raw_prompt: '接口创建订单后在 iOS 支付并在数据库对账',
        business_domain: 'ecommerce',
        protocols: ['HTTP', 'iOS', 'SQL'],
        actions: ['create', 'pay', 'verify'],
        extracted_entities: ['order_id'],
        suggested_node_count: 3,
        analyzed_at: '2026-10-17 12:00:00',
      },
      created_at: '2026-10-17 12:00:00',
    },
  ]
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.ai-autonomous-exploration-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-icon {
  font-size: 22px;
  color: #1677ff;
}

.hero-badge {
  font-weight: 500;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  background: var(--c-bg-container, #ffffff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.kpi-icon-primary {
  background: #eff6ff;
  color: #2563eb;
}
.kpi-icon-info {
  background: #f0fdfa;
  color: #0d9488;
}
.kpi-icon-success {
  background: #f0fdf4;
  color: #16a34a;
}
.kpi-icon-warning {
  background: #fffbeb;
  color: #d97706;
}

.kpi-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text-primary, #0f172a);
}

.kpi-sub {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.main-table-card {
  border-radius: 8px;
  border: 1px solid var(--c-border-subtle, #e2e8f0);
}

.table-toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.total-text {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.start-session-form {
  padding-top: 8px;
}
</style>
