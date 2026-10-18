<template>
  <a-drawer
    :open="open"
    title="RAG 知识检索召回与上下文溯源透视抽屉"
    width="86%"
    placement="right"
    :destroy-on-close="true"
    class="llm-rag-inspection-drawer"
    @close="handleClose"
  >
    <div class="drawer-container">
      <!-- 1. 顶部 RAG 三元组概览横幅 -->
      <div class="rag-hero-bar">
        <div class="hero-left">
          <div class="title-row">
            <DeploymentUnitOutlined class="hero-icon text-primary" />
            <span class="query-title font-bold">{{ query || 'ATP 全链路压测如何保障数据隔离与防穿透？' }}</span>
            <a-tag :color="getGradeColor(grade)" class="font-mono font-bold">
              评级: {{ grade }}
            </a-tag>
            <a-tag color="blue" class="font-mono">
              模型: {{ targetModel || 'Qwen-2.5-72B-Instruct' }}
            </a-tag>
          </div>

          <div class="hero-summary-pills font-mono">
            <span class="metric-pill">
              三元组综合分: <strong :class="getScoreClass(compositeScore)">{{ compositeScore.toFixed(1) }}</strong>
            </span>
            <span class="metric-pill">
              上下文相关度: <strong class="text-primary">{{ (contextRelevance * 100).toFixed(1) }}%</strong>
            </span>
            <span class="metric-pill">
              知识忠实度: <strong :class="groundedness >= 0.8 ? 'text-success' : 'text-danger'">{{ (groundedness * 100).toFixed(1) }}%</strong>
            </span>
            <span class="metric-pill">
              回答准确度: <strong class="text-primary">{{ (answerRelevance * 100).toFixed(1) }}%</strong>
            </span>
            <span class="metric-pill">
              命中 Chunk: <strong>{{ chunks.length }} 块</strong>
            </span>
          </div>
        </div>

        <div class="hero-actions">
          <a-space>
            <a-button :loading="refreshing" @click="handleRefresh">
              <template #icon><ReloadOutlined /></template>
              刷新评测
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 2. 中部核心三栏/标签页透视 -->
      <a-tabs v-model:activeKey="activeTabKey" class="rag-inspection-tabs" type="card">
        <!-- 标签页 1: 检索 Chunk 相关度热力透视 -->
        <a-tab-pane key="chunks" tab="检索 Chunk 相关度热力透视">
          <div class="chunks-tab-content">
            <div class="query-display-box">
              <span class="box-label"><SearchOutlined /> 原始评测 Query：</span>
              <p class="box-text font-mono">{{ query || 'ATP 全链路压测如何保障数据隔离与防穿透？' }}</p>
            </div>

            <div class="chunk-list-container">
              <div
                v-for="(chunk, idx) in chunks"
                :key="chunk.chunk_id"
                class="chunk-card"
                :class="{ 'highlighted-chunk': selectedChunkId === chunk.chunk_id }"
              >
                <div class="chunk-card-header">
                  <div class="chunk-id-tag">
                    <span class="chunk-badge font-mono">#{{ chunk.chunk_id }}</span>
                    <span class="chunk-source-doc font-mono">{{ chunk.source_doc }}</span>
                  </div>
                  <div class="chunk-score-meter">
                    <span class="meter-label font-mono">相关度 {{ (chunk.relevance_score * 100).toFixed(1) }}%</span>
                    <a-progress
                      :percent="Math.round(chunk.relevance_score * 100)"
                      :stroke-color="getRelevanceColor(chunk.relevance_score)"
                      size="small"
                      :show-info="false"
                      class="chunk-progress"
                    />
                  </div>
                </div>

                <div class="chunk-content-body font-mono">
                  {{ chunk.content }}
                </div>

                <div class="chunk-card-footer">
                  <span class="footer-tip">检索序位: 第 {{ idx + 1 }} 位</span>
                  <a-button type="link" size="small" @click="handleFocusChunk(chunk.chunk_id)">
                    定位引用断言
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- 标签页 2: 断言事实依据引用溯源 -->
        <a-tab-pane key="attributions" tab="模型回答事实引用溯源">
          <div class="attributions-tab-content">
            <div class="answer-display-card">
              <div class="answer-header font-bold">
                <RobotOutlined /> 模型生成完整回答：
              </div>
              <div class="answer-body font-mono">
                {{ answer || 'ATP 平台通过自动识别 X-Stress-Test 请求头注入影子上下文，所有写操作路由至 t_order_shadow 影子表进行物理隔离，并由 ShadowDataCleaner 服务实现一键清理。' }}
              </div>
            </div>

            <div class="claims-table-wrapper">
              <div class="table-title-row">
                <span class="title font-bold">断言事实句溯源细分 (共 {{ claimAttributions.length }} 处判定)：</span>
              </div>

              <a-table
                :columns="claimColumns"
                :data-source="claimAttributions"
                :pagination="false"
                row-key="claim_text"
                size="middle"
                class="claims-table"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'claim_text'">
                    <span class="font-mono text-primary font-bold">{{ record.claim_text }}</span>
                  </template>

                  <template v-else-if="column.key === 'is_grounded'">
                    <a-tag :color="record.is_grounded ? 'success' : 'error'">
                      {{ record.is_grounded ? '已溯源支撑' : '无根幻觉' }}
                    </a-tag>
                  </template>

                  <template v-else-if="column.key === 'supporting_chunk_id'">
                    <a-tag
                      v-if="record.supporting_chunk_id"
                      color="purple"
                      class="font-mono cursor-pointer"
                      @click="handleJumpToChunk(record.supporting_chunk_id)"
                    >
                      #{{ record.supporting_chunk_id }}
                    </a-tag>
                    <span v-else class="text-muted font-mono">-</span>
                  </template>

                  <template v-else-if="column.key === 'evidence_snippet'">
                    <span class="font-mono text-secondary">{{ record.evidence_snippet }}</span>
                  </template>
                </template>
              </a-table>
            </div>
          </div>
        </a-tab-pane>

        <!-- 标签页 3: 幻觉率与事实一致性详情 -->
        <a-tab-pane key="hallucination" tab="事实一致性与冲突检出">
          <div class="hallucination-tab-content">
            <a-alert
              v-if="hallucinationRatePct === 0.0"
              message="未检出任何矛盾断言或无根实体，事实一致性表现优秀！"
              type="success"
              show-icon
              class="mb-4"
            />
            <a-alert
              v-else
              :message="`检出 ${hallucinationRatePct.toFixed(1)}% 幻觉断言，请重点关注以下事实偏差！`"
              type="warning"
              show-icon
              class="mb-4"
            />

            <div class="kpi-row">
              <div class="kpi-mini-card">
                <span class="kpi-label">事实一致性得分</span>
                <span class="kpi-value font-mono text-success">{{ (100 - hallucinationRatePct).toFixed(1) }}</span>
              </div>
              <div class="kpi-mini-card">
                <span class="kpi-label">幻觉偏离率</span>
                <span class="kpi-value font-mono text-warning">{{ hallucinationRatePct.toFixed(1) }}%</span>
              </div>
              <div class="kpi-mini-card">
                <span class="kpi-label">极性矛盾检出</span>
                <span class="kpi-value font-mono text-danger">{{ polarityConflictsCount }} 处</span>
              </div>
              <div class="kpi-mini-card">
                <span class="kpi-label">虚构实体检出</span>
                <span class="kpi-value font-mono text-warning">{{ fabricatedEntitiesCount }} 个</span>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  DeploymentUnitOutlined,
  ReloadOutlined,
  SearchOutlined,
  RobotOutlined,
} from '@ant-design/icons-vue'

export interface RagChunk {
  chunk_id: string
  content: string
  relevance_score: number
  source_doc: string
}

export interface ClaimItem {
  claim_text: string
  is_grounded: boolean
  supporting_chunk_id?: string
  evidence_snippet: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    query?: string
    answer?: string
    targetModel?: string
    compositeScore?: number
    contextRelevance?: number
    groundedness?: number
    answerRelevance?: number
    grade?: string
    chunks?: RagChunk[]
    claimAttributions?: ClaimItem[]
    hallucinationRatePct?: number
    polarityConflictsCount?: number
    fabricatedEntitiesCount?: number
  }>(),
  {
    open: false,
    query: 'ATP 全链路压测如何保障数据隔离与防穿透？',
    answer:
      'ATP 平台通过自动识别 X-Stress-Test 请求头注入影子上下文，所有写操作路由至 t_order_shadow 影子表进行物理隔离，并由 ShadowDataCleaner 服务实现一键清理。',
    targetModel: 'Qwen-2.5-72B-Instruct',
    compositeScore: 92.5,
    contextRelevance: 0.88,
    groundedness: 1.0,
    answerRelevance: 0.91,
    grade: 'EXCELLENT',
    chunks: () => [
      {
        chunk_id: 'chk_01',
        content:
          'ATP 平台支持全链路压测标透传，通过 X-Stress-Test 头在微服务之间自动传递，并在持久层自动将流量路由到影子库表。',
        relevance_score: 0.92,
        source_doc: 'atp-stress-isolation-arch.md',
      },
      {
        chunk_id: 'chk_02',
        content:
          '影子数据清理服务 ShadowDataCleaner 负责在压测完成后自动清理 t_order_shadow 等影子表数据，保障主库清洁。',
        relevance_score: 0.85,
        source_doc: 'atp-shadow-cleaner.md',
      },
    ],
    claimAttributions: () => [
      {
        claim_text: 'ATP 平台通过自动识别 X-Stress-Test 请求头注入影子上下文',
        is_grounded: true,
        supporting_chunk_id: 'chk_01',
        evidence_snippet: '匹配片段 chk_01 (重合度 91%)',
      },
      {
        claim_text: '所有写操作路由至 t_order_shadow 影子表进行物理隔离',
        is_grounded: true,
        supporting_chunk_id: 'chk_01',
        evidence_snippet: '匹配片段 chk_01 (重合度 88%)',
      },
      {
        claim_text: '由 ShadowDataCleaner 服务实现一键清理',
        is_grounded: true,
        supporting_chunk_id: 'chk_02',
        evidence_snippet: '匹配片段 chk_02 (重合度 85%)',
      },
    ],
    hallucinationRatePct: 0.0,
    polarityConflictsCount: 0,
    fabricatedEntitiesCount: 0,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
  (e: 'refresh'): void
  (e: 'locate-chunk', chunkId: string): void
}>()

const activeTabKey = ref('chunks')
const refreshing = ref(false)
const selectedChunkId = ref<string | null>(null)

const claimColumns = [
  { title: '断言事实语句', dataIndex: 'claim_text', key: 'claim_text', width: '38%' },
  { title: '忠实度判定', dataIndex: 'is_grounded', key: 'is_grounded', width: '15%' },
  { title: '支撑 Chunk', dataIndex: 'supporting_chunk_id', key: 'supporting_chunk_id', width: '15%' },
  { title: '匹配证据线索', dataIndex: 'evidence_snippet', key: 'evidence_snippet', width: '32%' },
]

function handleClose() {
  emit('update:open', false)
  emit('close')
}

function handleRefresh() {
  refreshing.value = true
  emit('refresh')
  setTimeout(() => {
    refreshing.value = false
  }, 300)
}

function handleFocusChunk(chunkId: string) {
  selectedChunkId.value = chunkId
  activeTabKey.value = 'attributions'
}

function handleJumpToChunk(chunkId: string) {
  selectedChunkId.value = chunkId
  activeTabKey.value = 'chunks'
  emit('locate-chunk', chunkId)
}

function getGradeColor(grade: string) {
  switch (grade) {
    case 'EXCELLENT':
      return 'success'
    case 'GOOD':
      return 'processing'
    case 'MARGINAL':
      return 'warning'
    default:
      return 'error'
  }
}

function getScoreClass(score: number) {
  if (score >= 90.0) return 'text-success'
  if (score >= 75.0) return 'text-primary'
  if (score >= 60.0) return 'text-warning'
  return 'text-danger'
}

function getRelevanceColor(relevance: number) {
  if (relevance >= 0.8) return 'var(--c-success)'
  if (relevance >= 0.5) return 'var(--c-primary)'
  return 'var(--c-warning)'
}
defineExpose({
  handleClose,
  handleRefresh,
  handleJumpToChunk,
  handleFocusChunk,
})
</script>

<style scoped>
.llm-rag-inspection-drawer {
  font-family: var(--font-mono, monospace);
}

.drawer-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}

.rag-hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4, 16px);
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: var(--border-radius, 8px);
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  font-size: 20px;
}

.query-title {
  font-size: 16px;
  color: var(--c-text-primary, #0f172a);
}

.hero-summary-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--c-text-secondary, #475569);
}

.metric-pill strong {
  margin-left: 4px;
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
.text-danger {
  color: var(--c-error, #f5222d);
}

.chunks-tab-content,
.attributions-tab-content,
.hallucination-tab-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 8px;
}

.query-display-box {
  padding: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border-left: 4px solid var(--c-primary, #1677ff);
  border-radius: 4px;
}

.box-label {
  font-weight: 600;
  color: var(--c-text-secondary, #475569);
  font-size: 13px;
}

.box-text {
  margin: 6px 0 0 0;
  font-size: 14px;
  color: var(--c-text-primary, #0f172a);
}

.chunk-list-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-card {
  padding: 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.chunk-card:hover {
  border-color: var(--c-primary, #1677ff);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.highlighted-chunk {
  border-color: var(--c-primary, #1677ff);
  background: rgba(22, 119, 255, 0.03);
}

.chunk-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.chunk-badge {
  background: var(--c-primary-glow, rgba(22, 119, 255, 0.1));
  color: var(--c-primary, #1677ff);
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 12px;
}

.chunk-source-doc {
  margin-left: 8px;
  color: var(--c-text-secondary, #475569);
  font-size: 12px;
}

.chunk-score-meter {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 220px;
}

.meter-label {
  font-size: 12px;
  color: var(--c-text-secondary, #475569);
  white-space: nowrap;
}

.chunk-progress {
  flex: 1;
}

.chunk-content-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--c-text-primary, #0f172a);
  background: var(--c-bg-subtle, #f8fafc);
  padding: 10px;
  border-radius: 4px;
}

.chunk-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.answer-display-card {
  padding: 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.answer-header {
  margin-bottom: 8px;
  color: var(--c-text-primary, #0f172a);
}

.answer-body {
  font-size: 14px;
  line-height: 1.6;
  color: var(--c-text-primary, #0f172a);
  background: var(--c-bg-subtle, #f8fafc);
  padding: 12px;
  border-radius: 4px;
}

.claims-table-wrapper {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  padding: 14px;
}

.table-title-row {
  margin-bottom: 10px;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.kpi-mini-card {
  display: flex;
  flex-direction: column;
  padding: 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.kpi-label {
  font-size: 12px;
  color: var(--c-text-secondary, #475569);
  margin-bottom: 6px;
}

.kpi-value {
  font-size: 20px;
  font-weight: bold;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>
