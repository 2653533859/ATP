<template>
  <a-drawer
    :open="open"
    title="多模态 VLM 自主探索控制与状态图谱中枢"
    width="85%"
    placement="right"
    :destroy-on-close="true"
    class="autonomous-exploration-drawer"
    @close="handleClose"
  >
    <div class="exploration-drawer-container">
      <!-- 顶部会话信息横幅与指标 -->
      <div class="exploration-hero-banner">
        <div class="hero-left-info">
          <div class="session-meta-row">
            <span class="session-title"><RobotOutlined class="hero-robot-icon" /> 自主探索会话:</span>
            <code class="session-id-badge">{{ currentSession?.session_id || sessionId || '未初始化' }}</code>
            <a-tag :color="getPlatformTagColor(currentSession?.platform)">
              {{ (currentSession?.platform || 'web').toUpperCase() }} 端
            </a-tag>
            <a-tag :color="getStatusTagColor(currentSession?.status)">
              {{ currentSession?.status || 'ACTIVE' }}
            </a-tag>
          </div>
          <div class="session-goal-text">
            <strong>探索目标:</strong> {{ currentSession?.goal || '自主遍历与交互验证端侧业务链路' }}
          </div>
          <div class="session-stats-row">
            <span class="stat-pill">
              已发现状态: <strong>{{ currentSession?.states_count || currentSession?.states.length || 0 }}</strong>
            </span>
            <span class="stat-pill">
              迁移动作: <strong>{{ currentSession?.transitions_count || currentSession?.transitions.length || 0 }}</strong>
            </span>
            <span class="stat-pill">
              执行步数: <strong>{{ currentSession?.step_count || 0 }} / {{ currentSession?.max_steps || 30 }}</strong>
            </span>
            <span class="stat-pill" :class="{ 'has-anomalies': anomaliesList.length > 0 }">
              检出异常: <strong>{{ anomaliesList.length }}</strong>
            </span>
          </div>
        </div>

        <div class="hero-right-actions">
          <a-space>
            <a-button size="small" :loading="loading" @click="fetchSessionDetail">
              <template #icon><ReloadOutlined /></template>
              刷新会话
            </a-button>
            <a-button
              size="small"
              :loading="stepping"
              :disabled="currentSession?.status === 'COMPLETED'"
              @click="handleStepExploration"
            >
              <template #icon><ThunderboltOutlined /></template>
              单步推进探索
            </a-button>
            <a-button
              size="small"
              type="primary"
              :loading="converting"
              :disabled="!currentSession || (currentSession.transitions.length === 0 && currentSession.states.length === 0)"
              @click="handleConvertWorkflow"
            >
              <template #icon><CheckCircleOutlined /></template>
              一键固化为工作流草稿
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 主标签页导航 -->
      <a-tabs v-model:activeKey="activeTab" class="exploration-tabs">
        <!-- 标签 1: 状态迁移图谱与交互链路 -->
        <a-tab-pane key="graph" tab="状态迁移图谱 (State Graph)">
          <div class="graph-workspace-layout">
            <!-- 左侧: 状态节点清单 -->
            <div class="states-column-card">
              <div class="column-header">
                <span class="col-title"><ClusterOutlined /> 界面状态节点 ({{ currentSession?.states.length || 0 }})</span>
              </div>
              <div class="states-list">
                <div
                  v-for="st in currentSession?.states || []"
                  :key="st.state_id"
                  class="state-item-card"
                  :class="{ active: selectedStateId === st.state_id }"
                  @click="selectState(st.state_id)"
                >
                  <div class="state-card-header">
                    <span class="state-name">{{ st.screen_name }}</span>
                    <a-tag size="small" color="blue">{{ st.visit_count }} 次访问</a-tag>
                  </div>
                  <div class="state-sig font-mono">指纹: {{ st.ui_signature }}</div>
                  <div class="state-meta">包含控件: {{ st.elements.length }} 个</div>
                </div>
              </div>
            </div>

            <!-- 右侧: 迁移动作流序列 -->
            <div class="transitions-column-card">
              <div class="column-header">
                <span class="col-title"><ApartmentOutlined /> 探索手势与迁移动作流</span>
              </div>
              <div v-if="(currentSession?.transitions || []).length === 0" class="empty-transitions">
                <a-empty description="暂无状态迁移动作，点击上方「单步推进探索」启动执行" />
              </div>
              <div v-else class="transitions-timeline">
                <div
                  v-for="(tr, idx) in currentSession?.transitions || []"
                  :key="tr.transition_id"
                  class="transition-step-row"
                >
                  <div class="step-num">#{{ idx + 1 }}</div>
                  <div class="step-card">
                    <div class="step-card-head">
                      <a-tag :color="getActionTagColor(tr.action_type)">{{ tr.action_type }}</a-tag>
                      <span class="target-label">目标: <strong>{{ tr.target_element_label }}</strong></span>
                    </div>
                    <div class="step-transfer font-mono">
                      <span>{{ tr.from_state_id }}</span>
                      <ArrowRightOutlined class="transfer-arrow" />
                      <span>{{ tr.to_state_id }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- 标签 2: 界面视觉感知与控件清单 -->
        <a-tab-pane key="perception" tab="视觉语义感知 (Screen Perception)">
          <div class="perception-workspace-layout">
            <div class="screen-wireframe-panel">
              <div class="panel-header-sub">
                <span>当前探索屏幕视口 (模拟渲染)</span>
                <span v-if="selectedState" class="font-mono">{{ selectedState.screen_name }}</span>
              </div>
              <div class="simulated-screen">
                <div class="screen-status-bar">
                  <span>9:41</span>
                  <span>5G • 100%</span>
                </div>
                <div class="screen-content-area">
                  <div
                    v-for="el in selectedState?.elements || []"
                    :key="el.element_id"
                    class="simulated-element-box"
                    :class="'el-type-' + el.element_type"
                  >
                    <span class="el-badge">{{ el.element_type }}</span>
                    <span class="el-text">{{ el.label }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="elements-table-panel">
              <div class="panel-header-sub">
                <span>感知到的可交互 UI 控件列表 ({{ selectedState?.elements.length || 0 }})</span>
              </div>
              <a-table
                :data-source="selectedState?.elements || []"
                :columns="elementTableColumns"
                row-key="element_id"
                size="small"
                :pagination="{ pageSize: 6 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'element_type'">
                    <a-tag color="cyan">{{ record.element_type }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'clickable'">
                    <a-tag :color="record.clickable ? 'green' : 'default'">
                      {{ record.clickable ? '可交互' : '纯展示' }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.key === 'confidence'">
                    <span>{{ (record.confidence * 100).toFixed(0) }}%</span>
                  </template>
                </template>
              </a-table>
            </div>
          </div>
        </a-tab-pane>

        <!-- 标签 3: 异常风险与缺陷监控 -->
        <a-tab-pane key="anomalies" tab="异常与缺陷看板 (Anomalies)">
          <div class="anomalies-workspace-layout">
            <div v-if="anomaliesList.length === 0" class="empty-anomalies">
              <a-empty description="本次探索暂未检出任何白屏、死锁或报错弹窗异常，运行平稳。" />
            </div>
            <div v-else class="anomalies-grid">
              <div
                v-for="anom in anomaliesList"
                :key="anom.anomaly_id"
                class="anomaly-card"
                :class="'severity-' + anom.severity.toLowerCase()"
              >
                <div class="anomaly-card-header">
                  <div class="header-left">
                    <a-tag :color="getSeverityColor(anom.severity)">{{ anom.severity }}</a-tag>
                    <a-tag color="red">{{ anom.anomaly_type }}</a-tag>
                    <span class="anomaly-title">{{ anom.title }}</span>
                  </div>
                  <span class="anomaly-time font-mono">{{ anom.detected_at }}</span>
                </div>
                <div class="anomaly-desc">{{ anom.description }}</div>
                <div class="anomaly-suggestion">
                  <strong>建议处置:</strong> {{ anom.suggested_action }}
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  RobotOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ClusterOutlined,
  ApartmentOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons-vue'
import {
  intentWorkflowApi,
  type ExplorationSessionDTO,
  type ExplorationAnomalyDTO,
} from '@/api/intentWorkflow'

interface Props {
  open: boolean
  sessionId?: string
  projectId?: string
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  sessionId: '',
  projectId: '',
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'converted', workflowDraft: any): void
}>()

const activeTab = ref('graph')
const loading = ref(false)
const stepping = ref(false)
const converting = ref(false)
const currentSession = ref<ExplorationSessionDTO | null>(null)
const anomaliesList = ref<ExplorationAnomalyDTO[]>([])
const selectedStateId = ref<string>('')

const elementTableColumns = [
  { title: '控件 ID', dataIndex: 'element_id', key: 'element_id', width: 140 },
  { title: '类型', dataIndex: 'element_type', key: 'element_type', width: 110 },
  { title: '控件文本 / 描述', dataIndex: 'label', key: 'label' },
  { title: '交互属性', dataIndex: 'clickable', key: 'clickable', width: 90 },
  { title: 'VLM 置信度', dataIndex: 'confidence', key: 'confidence', width: 100 },
]

const selectedState = computed(() => {
  if (!currentSession.value?.states) return null
  return (
    currentSession.value.states.find(s => s.state_id === selectedStateId.value) ||
    currentSession.value.states[0] ||
    null
  )
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

function getActionTagColor(action?: string): string {
  switch (action?.toUpperCase()) {
    case 'TAP':
      return 'blue'
    case 'INPUT':
      return 'green'
    case 'SWIPE':
      return 'purple'
    case 'BACK':
      return 'default'
    default:
      return 'cyan'
  }
}

function getSeverityColor(sev: string): string {
  switch (sev?.toUpperCase()) {
    case 'CRITICAL':
      return 'red'
    case 'HIGH':
      return 'orange'
    case 'MEDIUM':
      return 'gold'
    default:
      return 'blue'
  }
}

function selectState(sid: string) {
  selectedStateId.value = sid
}

async function fetchSessionDetail() {
  loading.value = true
  try {
    if (props.sessionId) {
      const res = await intentWorkflowApi.getExploration(props.sessionId)
      currentSession.value = res.session
    } else {
      // 载入默认展示示例会话
      currentSession.value = createMockSession()
    }

    if (currentSession.value?.states?.length && !selectedStateId.value) {
      selectedStateId.value = currentSession.value.states[0].state_id
    }

    // 载入异常列表
    const anomRes = await intentWorkflowApi.listAnomalies(props.sessionId || undefined)
    anomaliesList.value = anomRes.anomalies || []
  } catch (err: any) {
    // 降级为本地 mock 模式
    currentSession.value = createMockSession()
    if (currentSession.value?.states?.length) {
      selectedStateId.value = currentSession.value.states[0].state_id
    }
  } finally {
    loading.value = false
  }
}

async function handleStepExploration() {
  if (!currentSession.value) return
  stepping.value = true
  try {
    const dummyB64 =
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    const res = await intentWorkflowApi.stepExploration({
      session_id: currentSession.value.session_id,
      screenshot_base64: dummyB64,
    })

    message.success(`已推进一步: [${res.action.action_type}] ${res.action.target_label || ''}`)
    // 重新获取会话刷新图谱
    await fetchSessionDetail()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '单步探索推演失败')
  } finally {
    stepping.value = false
  }
}

async function handleConvertWorkflow() {
  if (!currentSession.value) return
  converting.value = true
  try {
    const res = await intentWorkflowApi.convertExploration({
      session_id: currentSession.value.session_id,
      workflow_name: `工作流_${currentSession.value.goal || '自主探索逆向'}`,
    })

    message.success('已成功将探索手势与路径固化为工作流草稿！')
    emit('converted', res.workflow_draft)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '固化工作流草稿失败')
  } finally {
    converting.value = false
  }
}

function createMockSession(): ExplorationSessionDTO {
  return {
    session_id: 'expsess_mock_ios_01',
    platform: 'ios',
    device_id: '00008101-IPHONE-REAL-DEMO',
    goal: '探索电商 App 首页轮播、加购与结算路径',
    status: 'ACTIVE',
    states_count: 3,
    transitions_count: 2,
    states: [
      {
        state_id: 'state_home',
        screen_name: '首页主推荐视口',
        ui_signature: 'sig_a1b2c3d4e5f6',
        elements: [
          {
            element_id: 'el_search',
            element_type: 'input',
            label: '搜索心仪好物',
            bounding_box: [20, 40, 350, 40],
            center_coords: [195, 60],
            clickable: true,
            confidence: 0.98,
          },
          {
            element_id: 'el_banner_promo',
            element_type: 'button',
            label: '双十一特惠主会场',
            bounding_box: [20, 100, 350, 160],
            center_coords: [195, 180],
            clickable: true,
            confidence: 0.95,
          },
          {
            element_id: 'el_add_cart_quick',
            element_type: 'button',
            label: '立即加购',
            bounding_box: [280, 300, 90, 36],
            center_coords: [325, 318],
            clickable: true,
            confidence: 0.96,
          },
        ],
        visit_count: 2,
        first_seen_at: '2026-10-17T12:00:00Z',
      },
      {
        state_id: 'state_cart',
        screen_name: '购物车与优惠明细',
        ui_signature: 'sig_b2c3d4e5f6a1',
        elements: [
          {
            element_id: 'el_checkout_btn',
            element_type: 'button',
            label: '去结算 (1 件商品)',
            bounding_box: [240, 600, 130, 45],
            center_coords: [305, 622],
            clickable: true,
            confidence: 0.99,
          },
        ],
        visit_count: 1,
        first_seen_at: '2026-10-17T12:01:00Z',
      },
    ],
    transitions: [
      {
        transition_id: 'trans_01',
        from_state_id: 'state_home',
        to_state_id: 'state_cart',
        action_type: 'TAP',
        target_element_label: '立即加购',
        performed_at: '2026-10-17T12:00:30Z',
      },
    ],
    current_state_id: 'state_cart',
    step_count: 1,
    max_steps: 25,
    started_at: '2026-10-17T12:00:00Z',
  }
}

function handleClose() {
  emit('update:open', false)
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      fetchSessionDetail()
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (props.open) {
    fetchSessionDetail()
  }
})
</script>

<style scoped>
.exploration-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.exploration-hero-banner {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hero-left-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.hero-robot-icon {
  color: #1677ff;
}

.session-id-badge {
  font-size: 11px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  color: #475569;
}

.session-goal-text {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.session-stats-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}

.stat-pill {
  font-size: 11px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  padding: 2px 8px;
  border-radius: 10px;
  color: var(--c-text-secondary, #475569);
}

.stat-pill.has-anomalies {
  border-color: #fca5a5;
  background: #fef2f2;
  color: #b91c1c;
}

.exploration-tabs {
  margin-top: 4px;
}

.graph-workspace-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  min-height: 480px;
}

.states-column-card,
.transitions-column-card {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
}

.column-header {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.states-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 520px;
  overflow-y: auto;
}

.state-item-card {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.2s;
}

.state-item-card:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.state-item-card.active {
  border-color: #3b82f6;
  background: #eff6ff;
  box-shadow: 0 0 0 1px #3b82f6;
}

.state-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.state-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
}

.state-sig {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 2px;
}

.state-meta {
  font-size: 11px;
  color: #94a3b8;
}

.transitions-timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 520px;
  overflow-y: auto;
}

.transition-step-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-num {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  width: 32px;
}

.step-card {
  flex: 1;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
  background: #f8fafc;
}

.step-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.target-label {
  font-size: 12px;
  color: #1e293b;
}

.step-transfer {
  font-size: 11px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.transfer-arrow {
  color: #94a3b8;
  font-size: 12px;
}

.empty-transitions,
.empty-anomalies {
  padding: 40px 0;
}

.perception-workspace-layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 16px;
  min-height: 480px;
}

.screen-wireframe-panel,
.elements-table-panel {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
}

.panel-header-sub {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 12px;
}

.simulated-screen {
  width: 100%;
  max-width: 300px;
  height: 480px;
  margin: 0 auto;
  border: 4px solid #334155;
  border-radius: 20px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.screen-status-bar {
  display: flex;
  justify-content: space-between;
  padding: 4px 12px;
  font-size: 10px;
  color: #64748b;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}

.screen-content-area {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.simulated-element-box {
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px dashed #93c5fd;
  background: #eff6ff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.el-badge {
  font-size: 9px;
  background: #dbeafe;
  color: #1e40af;
  padding: 1px 4px;
  border-radius: 3px;
}

.el-text {
  font-size: 11px;
  font-weight: 500;
  color: #1e3a8a;
}

.anomalies-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.anomaly-card {
  border: 1px solid #e2e8f0;
  border-left: 4px solid #ef4444;
  border-radius: 8px;
  padding: 12px 16px;
  background: #ffffff;
}

.anomaly-card.severity-critical {
  border-left-color: #ef4444;
  background: #fff5f5;
}
.anomaly-card.severity-high {
  border-left-color: #f97316;
  background: #fffaf0;
}
.anomaly-card.severity-medium {
  border-left-color: #eab308;
  background: #fefce8;
}

.anomaly-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.anomaly-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.anomaly-time {
  font-size: 11px;
  color: #94a3b8;
}

.anomaly-desc {
  font-size: 12px;
  color: #475569;
  margin-bottom: 6px;
  line-height: 1.5;
}

.anomaly-suggestion {
  font-size: 11px;
  color: #15803d;
  background: #f0fdf4;
  padding: 4px 8px;
  border-radius: 4px;
}
</style>
