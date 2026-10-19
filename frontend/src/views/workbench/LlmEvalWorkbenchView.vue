<template>
  <div class="page-shell llm-eval-workbench-view">
    <!-- 1. 顶部页头 -->
    <header class="page-hero">
      <div class="hero-left">
        <div class="hero-title-row">
          <ExperimentOutlined class="hero-icon text-primary" />
          <h2 class="page-title">企业级大模型与 RAG 智能体综合评测工作台中枢</h2>
          <span class="live-dot" />
          <a-tag color="processing">v6.3.0 大模型质效评测中台</a-tag>
        </div>
        <p class="page-subtitle">
          覆盖 RAG 检索三元组质量评测、自然语言事实一致性与幻觉消除、Prompt 越狱红蓝攻防对抗与全域推理成本效益推演
        </p>
      </div>

      <div class="hero-right">
        <a-space>
          <a-button type="primary" @click="handleOpenRagDrawer(selectedModelItem)">
            <template #icon><DeploymentUnitOutlined /></template>
            RAG 三元组透视
          </a-button>

          <a-button @click="handleOpenRedTeamModal(selectedModelItem)">
            <template #icon><SecurityScanOutlined /></template>
            红蓝对抗与护栏
          </a-button>

          <a-button :loading="loading" @click="fetchData">
            <template #icon><ReloadOutlined /></template>
            刷新评测大盘
          </a-button>
        </a-space>
      </div>
    </header>

    <!-- 2. 4 大 Bento KPI 卡片 -->
    <div class="bento-kpi-grid">
      <!-- KPI 1 -->
      <div class="bento-card kpi-primary">
        <div class="kpi-header">
          <span class="kpi-title">全域模型综合质效基准分</span>
          <ExperimentOutlined class="kpi-icon text-primary" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-primary font-mono">92.4</span>
          <span class="kpi-trend text-primary font-mono">评级 EXCELLENT</span>
        </div>
        <div class="kpi-footer font-mono">
          涵盖 5 大主流工业模型深度评测
        </div>
      </div>

      <!-- KPI 2 -->
      <div class="bento-card kpi-success">
        <div class="kpi-header">
          <span class="kpi-title">RAG 检索三元组平均分</span>
          <DeploymentUnitOutlined class="kpi-icon text-success" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-success font-mono">93.2</span>
          <span class="kpi-sub font-mono text-success">忠实度 98.5%</span>
        </div>
        <div class="kpi-footer font-mono">
          上下文相关度 91.8%，无根幻觉有效归零
        </div>
      </div>

      <!-- KPI 3 -->
      <div class="bento-card kpi-warning">
        <div class="kpi-header">
          <span class="kpi-title">Prompt 越狱红蓝对抗防御率</span>
          <SecurityScanOutlined class="kpi-icon text-warning" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-warning font-mono">97.5%</span>
          <span class="kpi-sub font-mono text-warning">护栏 &lt; 5ms</span>
        </div>
        <div class="kpi-footer font-mono">
          防御 6 类高危渗透变异，自动脱敏 PII
        </div>
      </div>

      <!-- KPI 4 -->
      <div class="bento-card kpi-info">
        <div class="kpi-header">
          <span class="kpi-title">持续生成速率与经济性</span>
          <ThunderboltOutlined class="kpi-icon text-info" />
        </div>
        <div class="kpi-value-row">
          <span class="kpi-number text-info font-mono">118.5</span>
          <span class="kpi-trend text-info font-mono">TPS 均值</span>
        </div>
        <div class="kpi-footer font-mono">
          最低调用成本 $0.14/1M，性价比 5.2M/USD
        </div>
      </div>
    </div>

    <!-- 3. 主体区域: 全模型基准大盘表格与快速评测 -->
    <div class="workbench-main-content">
      <!-- 3.1 模型基准大盘表格 -->
      <div class="benchmark-table-card">
        <div class="table-toolbar">
          <div class="toolbar-left">
            <span class="section-title font-bold">全域大模型工业评测矩阵基准榜单 (Benchmark Leaderboard)</span>
            <span class="text-secondary text-xs font-mono ml-2">已完成 5 项模型全维度打分</span>
          </div>

          <div class="toolbar-right">
            <a-space>
              <a-radio-group v-model:value="filterProvider" size="small" button-style="solid">
                <a-radio-button value="ALL">全部提供方</a-radio-button>
                <a-radio-button value="DeepSeek">DeepSeek</a-radio-button>
                <a-radio-button value="Alibaba Cloud">通义千问</a-radio-button>
                <a-radio-button value="Meta / Cloud Hub">Meta</a-radio-button>
                <a-radio-button value="OpenAI">OpenAI</a-radio-button>
              </a-radio-group>
            </a-space>
          </div>
        </div>

        <a-table
          :columns="modelColumns"
          :data-source="filteredModels"
          :pagination="false"
          row-key="model_name"
          size="middle"
          class="models-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'model_name'">
              <div class="model-cell">
                <span class="font-bold font-mono text-primary">{{ record.model_name }}</span>
                <span class="text-secondary text-xs">{{ record.provider }}</span>
              </div>
            </template>

            <template v-else-if="column.key === 'rag_score'">
              <div class="score-progress-cell font-mono">
                <span class="score-text" :class="getScoreClass(record.rag_score)">{{ record.rag_score.toFixed(1) }}</span>
                <a-progress
                  :percent="Math.round(record.rag_score)"
                  :stroke-color="record.rag_score >= 90 ? 'var(--c-success)' : 'var(--c-primary)'"
                  size="small"
                  :show-info="false"
                  class="progress-bar"
                />
              </div>
            </template>

            <template v-else-if="column.key === 'hallucination_defense_rate'">
              <a-tag :color="record.hallucination_defense_rate >= 95 ? 'success' : 'warning'" class="font-mono">
                {{ record.hallucination_defense_rate.toFixed(1) }}% 事实合规
              </a-tag>
            </template>

            <template v-else-if="column.key === 'red_team_robustness'">
              <a-tag :color="record.red_team_robustness >= 90 ? 'blue' : 'purple'" class="font-mono">
                {{ record.red_team_robustness.toFixed(1) }} 分
              </a-tag>
            </template>

            <template v-else-if="column.key === 'tps'">
              <span class="font-mono font-bold">{{ record.tps.toFixed(1) }} Token/s</span>
            </template>

            <template v-else-if="column.key === 'monthly_projection_usd'">
              <span class="font-mono">${{ record.monthly_projection_usd.toFixed(2) }}</span>
            </template>

            <template v-else-if="column.key === 'efficiency_tier'">
              <a-tag :color="getTierColor(record.efficiency_tier)" class="font-mono font-bold">
                {{ record.efficiency_tier }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'actions'">
              <a-space size="small">
                <a-button type="link" size="small" @click="handleOpenRagDrawer(record)">
                  三元组透视
                </a-button>
                <a-button type="link" size="small" @click="handleOpenRedTeamModal(record)">
                  攻防配置
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 3.2 快捷交互评测操作台 -->
      <div class="quick-eval-card">
        <div class="card-header font-bold">
          <EditOutlined class="text-primary mr-1" /> 在线 RAG 三元组即时评测验证台
        </div>

        <div class="quick-eval-body">
          <a-form layout="vertical">
            <a-form-item label="测试用户提问 (Query)">
              <a-input
                v-model:value="evalQuery"
                placeholder="输入待评测的业务提问..."
                class="font-mono"
              />
            </a-form-item>

            <a-form-item label="检索上下文片段 (Context Chunk)">
              <a-textarea
                v-model:value="evalContext"
                placeholder="输入从向量数据库/知识库检索出的上下文..."
                :rows="2"
                class="font-mono"
              />
            </a-form-item>

            <a-form-item label="模型生成回答 (Answer)">
              <a-textarea
                v-model:value="evalAnswer"
                placeholder="输入待审查的大模型回答内容..."
                :rows="2"
                class="font-mono"
              />
            </a-form-item>

            <div class="eval-btn-row">
              <a-button type="primary" :loading="evaluating" @click="handleTriggerLiveEvaluation">
                <template #icon><ThunderboltOutlined /></template>
                立即执行在线评测并查看透视
              </a-button>
            </div>
          </a-form>
        </div>
      </div>
    </div>

    <!-- 4. RAG 三元组透视抽屉 -->
    <LlmRagInspectionDrawer
      v-model:open="ragDrawerVisible"
      :query="currentDrawerQuery"
      :target-model="currentDrawerModel"
      :composite-score="currentDrawerScore"
      @refresh="handleRefreshDrawer"
    />

    <!-- 5. 红蓝对抗策略配置弹窗 -->
    <LlmRedTeamConfigModal
      v-model:open="redTeamModalVisible"
      :initial-config="currentConfig"
      @confirm="handleSaveConfig"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ExperimentOutlined,
  DeploymentUnitOutlined,
  SecurityScanOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'
import LlmRagInspectionDrawer from './components/LlmRagInspectionDrawer.vue'
import LlmRedTeamConfigModal, { type RedTeamConfig } from './components/LlmRedTeamConfigModal.vue'

export interface ModelBenchmarkItem {
  model_name: string
  provider: string
  rag_score: number
  hallucination_defense_rate: number
  red_team_robustness: number
  ttft_ms: number
  tps: number
  monthly_projection_usd: number
  efficiency_tier: 'ULTRA_HIGH_VALUE' | 'HIGH_EFFICIENCY' | 'BALANCED' | 'PREMIUM_COSTLY'
}

const loading = ref(false)
const evaluating = ref(false)
const filterProvider = ref('ALL')

const ragDrawerVisible = ref(false)
const redTeamModalVisible = ref(false)

const currentDrawerQuery = ref('ATP 全链路压测如何保障数据隔离与防穿透？')
const currentDrawerModel = ref('qwen-2.5-72b')
const currentDrawerScore = ref(93.5)

const currentConfig = ref<Partial<RedTeamConfig>>({
  target_model: 'qwen-2.5-72b',
})

// 在线快速评测响应式表单
const evalQuery = ref('ATP 全链路压测如何保障数据隔离与防穿透？')
const evalContext = ref(
  'ATP 具备全链路影子流量隔离机制，所有压测写请求自动路由至 t_order_shadow 影子表，并通过 ShadowDataCleaner 自动清理。'
)
const evalAnswer = ref(
  'ATP 平台通过自动识别 X-Stress-Test 请求头注入影子上下文，所有写操作路由至 t_order_shadow 影子表进行物理隔离，并由 ShadowDataCleaner 服务实现一键清理。'
)

const benchmarkModels = ref<ModelBenchmarkItem[]>([
  {
    model_name: 'deepseek-v3',
    provider: 'DeepSeek',
    rag_score: 95.8,
    hallucination_defense_rate: 98.2,
    red_team_robustness: 94.5,
    ttft_ms: 165.0,
    tps: 145.0,
    monthly_projection_usd: 378.0,
    efficiency_tier: 'ULTRA_HIGH_VALUE',
  },
  {
    model_name: 'qwen-2.5-72b',
    provider: 'Alibaba Cloud',
    rag_score: 94.2,
    hallucination_defense_rate: 97.5,
    red_team_robustness: 92.0,
    ttft_ms: 210.0,
    tps: 110.0,
    monthly_projection_usd: 1200.0,
    efficiency_tier: 'ULTRA_HIGH_VALUE',
  },
  {
    model_name: 'deepseek-r1',
    provider: 'DeepSeek',
    rag_score: 96.5,
    hallucination_defense_rate: 99.0,
    red_team_robustness: 95.0,
    ttft_ms: 320.0,
    tps: 85.0,
    monthly_projection_usd: 2190.0,
    efficiency_tier: 'HIGH_EFFICIENCY',
  },
  {
    model_name: 'llama-3.3-70b',
    provider: 'Meta / Cloud Hub',
    rag_score: 91.5,
    hallucination_defense_rate: 96.0,
    red_team_robustness: 89.5,
    ttft_ms: 220.0,
    tps: 105.0,
    monthly_projection_usd: 900.0,
    efficiency_tier: 'HIGH_EFFICIENCY',
  },
  {
    model_name: 'gpt-4o',
    provider: 'OpenAI',
    rag_score: 94.0,
    hallucination_defense_rate: 98.0,
    red_team_robustness: 96.5,
    ttft_ms: 350.0,
    tps: 90.0,
    monthly_projection_usd: 7500.0,
    efficiency_tier: 'PREMIUM_COSTLY',
  },
])

const selectedModelItem = computed(() => benchmarkModels.value[0])

const filteredModels = computed(() => {
  if (filterProvider.value === 'ALL') return benchmarkModels.value
  return benchmarkModels.value.filter((m) => m.provider === filterProvider.value)
})

const modelColumns = [
  { title: '模型代号 / 提供商', dataIndex: 'model_name', key: 'model_name', width: '22%' },
  { title: 'RAG 三元组综合得分', dataIndex: 'rag_score', key: 'rag_score', width: '18%' },
  { title: '事实一致性防护', dataIndex: 'hallucination_defense_rate', key: 'hallucination_defense_rate', width: '14%' },
  { title: '红蓝鲁棒性评分', dataIndex: 'red_team_robustness', key: 'red_team_robustness', width: '12%' },
  { title: '生成速率 (TPS)', dataIndex: 'tps', key: 'tps', width: '12%' },
  { title: '月度预估开销', dataIndex: 'monthly_projection_usd', key: 'monthly_projection_usd', width: '11%' },
  { title: '性价比评级', dataIndex: 'efficiency_tier', key: 'efficiency_tier', width: '13%' },
  { title: '快捷操作', key: 'actions', width: '12%' },
]

function fetchData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
  }, 300)
}

function handleOpenRagDrawer(model?: ModelBenchmarkItem | Record<string, any>) {
  if (model) {
    currentDrawerModel.value = model.model_name
    currentDrawerScore.value = model.rag_score
  }
  currentDrawerQuery.value = evalQuery.value
  ragDrawerVisible.value = true
}

function handleOpenRedTeamModal(model?: ModelBenchmarkItem | Record<string, any>) {
  if (model) {
    currentConfig.value = {
      target_model: model.model_name,
    }
  }
  redTeamModalVisible.value = true
}

function handleRefreshDrawer() {
  fetchData()
}

function handleSaveConfig(config: RedTeamConfig) {
  currentConfig.value = config
}

function handleTriggerLiveEvaluation() {
  evaluating.value = true
  setTimeout(() => {
    evaluating.value = false
    handleOpenRagDrawer()
  }, 200)
}

function getScoreClass(score: number) {
  if (score >= 95.0) return 'text-success'
  if (score >= 90.0) return 'text-primary'
  if (score >= 80.0) return 'text-warning'
  return 'text-danger'
}

function getTierColor(tier: string) {
  switch (tier) {
    case 'ULTRA_HIGH_VALUE':
      return 'success'
    case 'HIGH_EFFICIENCY':
      return 'processing'
    case 'BALANCED':
      return 'warning'
    default:
      return 'default'
  }
}

defineExpose({
  benchmarkModels,
  filteredModels,
  ragDrawerVisible,
  redTeamModalVisible,
  fetchData,
  handleOpenRagDrawer,
  handleOpenRedTeamModal,
})
</script>

<style scoped>
.llm-eval-workbench-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4, 16px) var(--space-5, 20px);
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: var(--border-radius, 8px);
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 20px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: bold;
  color: var(--c-text-primary, #0f172a);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-success, #52c41a);
  display: inline-block;
}

.bento-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.bento-card {
  padding: 16px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s ease;
}

.bento-card:hover {
  border-color: var(--c-primary, #1677ff);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kpi-title {
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  font-weight: 500;
}

.kpi-icon {
  font-size: 18px;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.kpi-number {
  font-size: 28px;
  font-weight: bold;
  line-height: 1;
}

.kpi-trend,
.kpi-sub {
  font-size: 12px;
  font-weight: 600;
}

.kpi-footer {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.workbench-main-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.benchmark-table-card,
.quick-eval-card {
  padding: 16px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title {
  font-size: 15px;
  color: var(--c-text-primary, #0f172a);
}

.model-cell {
  display: flex;
  flex-direction: column;
}

.score-progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-text {
  font-weight: bold;
  width: 32px;
}

.progress-bar {
  flex: 1;
}

.card-header {
  font-size: 14px;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 12px;
}

.eval-btn-row {
  display: flex;
  justify-content: flex-end;
}

.text-primary {
  color: var(--c-primary, #1677ff);
}
.text-success {
  color: var(--c-success, #52c41a);
}
.text-warning {
  color: var(--c-warning, #faad14);
}
.text-info {
  color: #13c2c2;
}
.text-danger {
  color: var(--c-error, #f5222d);
}
.text-secondary {
  color: var(--c-text-secondary, #64748b);
}
.text-xs {
  font-size: 12px;
}
.mr-1 {
  margin-right: 4px;
}
.ml-2 {
  margin-left: 8px;
}
</style>
