<template>
  <a-drawer
    :open="open"
    title="低代码可视化漏测血缘与测试间隙分析中枢"
    width="85%"
    placement="right"
    :destroy-on-close="true"
    @close="handleClose"
  >
    <div class="coverage-gap-inspector-container">
      <!-- 顶部血缘分析指标横幅 -->
      <div class="coverage-hero-banner">
        <div class="hero-left-metrics">
          <div class="overall-rate-box">
            <span class="rate-num" :class="overallCoverageRate >= 0.85 ? 'text-success' : 'text-warning'">
              {{ (overallCoverageRate * 100).toFixed(1) }}%
            </span>
            <span class="rate-lbl">全链路综合覆盖率</span>
          </div>

          <div class="metrics-summary-text">
            <div class="summary-line">
              <span>总业务与契约节点: <strong>{{ totalNodesCount }}</strong></span>
              <span class="gap-highlight">
                <AlertOutlined class="gap-icon" /> 漏测盲区节点: <strong>{{ gapNodesCount }}</strong>
              </span>
              <a-tag v-if="highRiskCount > 0" color="red">
                {{ highRiskCount }} 个高危漏测红斑
              </a-tag>
            </div>
            <p class="summary-desc">
              自动反向贯通「业务需求 ➔ 接口契约 ➔ 业务逻辑分支 ➔ 落地测试用例」四层血缘，排查未被测试覆盖的盲区分支与异常逻辑。
            </p>
          </div>
        </div>

        <div class="hero-right-actions">
          <a-space>
            <a-button size="small" :loading="analyzing" @click="fetchAnalysisReport">
              <template #icon><ReloadOutlined /></template>
              重新分析血缘
            </a-button>
            <a-button
              size="small"
              type="primary"
              :loading="synthesizing"
              :disabled="gapNodesCount === 0"
              @click="handleSynthesizeAllGaps"
            >
              <template #icon><ThunderboltOutlined /></template>
              一键逆向合成补测用例
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 主视图: 左侧血缘层级树 + 右侧节点详情与补测草稿 -->
      <div class="inspector-workspace-grid">
        <!-- 左侧四层血缘树状拓扑 -->
        <div class="tree-topology-panel">
          <div class="panel-header-row">
            <span class="panel-title">
              <ApartmentOutlined /> 全链路四层血缘依赖树 (4-Tier Lineage)
            </span>
            <a-space size="small">
              <a-switch
                v-model:checked="gapOnly"
                size="small"
                checked-children="仅看漏测盲区"
                un-checked-children="全量血缘"
              />
            </a-space>
          </div>

          <a-spin :spinning="analyzing">
            <div class="lineage-tree-nodes-wrap">
              <div
                v-for="node in flattenedTreeNodes"
                :key="node.node_id"
                class="lineage-tree-row"
                :class="{
                  'row-gap': node.is_gap,
                  'row-selected': selectedNode?.node_id === node.node_id,
                  'row-high-risk': node.risk_level === 'HIGH',
                }"
                :style="{ paddingLeft: `${((node.depth || 1) - 1) * 24 + 10}px` }"
                @click="selectNode(node)"
              >
                <!-- 折叠图标 -->
                <span
                  v-if="node.children && node.children.length > 0"
                  class="toggle-arrow-btn"
                  @click.stop="toggleCollapse(node.node_id)"
                >
                  {{ collapsedIds.has(node.node_id) ? '▶' : '▼' }}
                </span>
                <span v-else class="toggle-arrow-spacer" />

                <!-- 节点类型标签 -->
                <a-tag :color="getCategoryColor(node.category)" class="mini-cat-tag">
                  {{ node.category.toUpperCase() }}
                </a-tag>

                <!-- 节点名称 -->
                <span class="node-name-label" :title="node.node_name">
                  {{ node.node_name }}
                </span>

                <!-- 覆盖率与漏测红斑徽标 -->
                <div class="node-gap-badges">
                  <a-tag v-if="node.is_gap" color="red" class="gap-tag">
                    漏测 {{ node.missing_branches.length }} 分支
                  </a-tag>
                  <span v-else class="text-success text-xs font-semibold">100% 覆盖</span>
                  <a-tag v-if="node.risk_level === 'HIGH'" color="error" class="risk-tag">高危</a-tag>
                </div>
              </div>
            </div>
          </a-spin>
        </div>

        <!-- 右侧选中的节点详情与补测草稿列表 -->
        <div class="node-detail-panel">
          <div class="panel-header-row">
            <span class="panel-title">
              <EyeOutlined /> 节点分支透视图与补测用例
            </span>
          </div>

          <div v-if="selectedNode" class="node-detail-content">
            <!-- 基础属性描述 -->
            <a-descriptions bordered size="small" :column="2">
              <a-descriptions-item label="节点名称" :span="2">
                <strong>{{ selectedNode.node_name }}</strong>
              </a-descriptions-item>
              <a-descriptions-item label="血缘层级">
                <a-tag :color="getCategoryColor(selectedNode.category)">
                  {{ selectedNode.category }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="风险等级">
                <a-tag :color="getRiskColor(selectedNode.risk_level)">
                  {{ selectedNode.risk_level }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="分支覆盖率">
                <span class="font-mono" :class="selectedNode.is_gap ? 'text-warning' : 'text-success'">
                  {{ (selectedNode.coverage_rate * 100).toFixed(0) }}% ({{ selectedNode.covered_branches.length }}/{{ selectedNode.expected_branches.length }})
                </span>
              </a-descriptions-item>
              <a-descriptions-item label="已关联用例数">
                {{ selectedNode.linked_case_ids.length }} 条
              </a-descriptions-item>
            </a-descriptions>

            <!-- 缺失漏测分支高亮框 (Coverage Gaps) -->
            <div v-if="selectedNode.is_gap" class="gaps-alert-box">
              <div class="gaps-box-head">
                <span class="gaps-box-title">
                  <ExclamationCircleOutlined class="alert-red-icon" /> 检出未被覆盖的业务/异常分支 (Coverage Gaps)
                </span>
                <a-button
                  size="small"
                  type="primary"
                  ghost
                  :loading="synthesizingNode"
                  @click="handleSynthesizeSingleNode(selectedNode)"
                >
                  针对该节点合成用例
                </a-button>
              </div>

              <div class="missing-branches-chips">
                <div
                  v-for="branch in selectedNode.missing_branches"
                  :key="branch"
                  class="missing-branch-chip"
                >
                  <span class="missing-dot" />
                  <span class="branch-name">{{ branch }}</span>
                  <span class="branch-tip">(未编写反例或异常测试)</span>
                </div>
              </div>
            </div>

            <!-- 已覆盖的分支 -->
            <div class="covered-section">
              <div class="section-sub-title">已覆盖正常分支:</div>
              <div class="covered-chips">
                <span
                  v-for="b in selectedNode.covered_branches"
                  :key="b"
                  class="covered-chip"
                >
                  ✓ {{ b }}
                </span>
              </div>
            </div>

            <!-- 已合成的用例草稿展示 (若有) -->
            <div v-if="activeDrafts.length > 0" class="synthesized-drafts-section">
              <div class="drafts-section-title">
                <ThunderboltOutlined /> 已自动推导补测用例草稿 ({{ activeDrafts.length }} 条):
              </div>
              <div
                v-for="draft in activeDrafts"
                :key="draft.draft_id"
                class="draft-case-card"
              >
                <div class="draft-card-head">
                  <span class="draft-title-text">{{ draft.title }}</span>
                  <a-space size="small">
                    <a-tag color="purple">{{ draft.case_type.toUpperCase() }}</a-tag>
                    <a-tag :color="draft.priority === 'P0' ? 'red' : 'blue'">{{ draft.priority }}</a-tag>
                  </a-space>
                </div>
                <div class="draft-steps-summary">
                  <div class="draft-step-line" v-for="step in draft.steps" :key="step.step_number">
                    <span class="step-num">步骤 {{ step.step_number }}:</span>
                    <span class="step-desc">{{ step.step_name }}</span>
                    <span class="step-action-tag">({{ step.action_type }})</span>
                  </div>
                </div>
                <div class="draft-outcome">
                  <strong>预期结果:</strong> {{ draft.expected_outcome }}
                </div>
              </div>
            </div>
          </div>

          <div v-else class="detail-empty-wrap">
            <a-empty description="点击左侧血缘树中任意节点查看分支覆盖透视与补测用例" />
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  AlertOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  ApartmentOutlined,
  EyeOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons-vue'
import {
  coverageLineageApi,
  type CoverageLineageNodeItem,
  type CoverageLineageReportItem,
  type SynthesizedTestCaseDraftItem,
} from '@/api/coverageLineage'

const props = defineProps<{
  open: boolean
  projectId?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const analyzing = ref(false)
const synthesizing = ref(false)
const synthesizingNode = ref(false)
const gapOnly = ref(false)
const collapsedIds = ref<Set<string>>(new Set())
const selectedNode = ref<CoverageLineageNodeItem | null>(null)
const report = ref<CoverageLineageReportItem | null>(null)
const activeDrafts = ref<SynthesizedTestCaseDraftItem[]>([])

const overallCoverageRate = computed(() => report.value?.overall_coverage_rate ?? 0.72)
const totalNodesCount = computed(() => report.value?.total_nodes_count ?? 4)
const gapNodesCount = computed(() => report.value?.gap_nodes_count ?? 2)
const highRiskCount = computed(() => report.value?.high_risk_gaps_count ?? 1)

// 扁平化展示树结构
const flattenedTreeNodes = computed<CoverageLineageNodeItem[]>(() => {
  if (!report.value?.tree_hierarchy) return []
  const result: CoverageLineageNodeItem[] = []

  function traverse(nodes: CoverageLineageNodeItem[]) {
    for (const node of nodes) {
      if (!gapOnly.value || node.is_gap || hasGapDescendant(node)) {
        result.push(node)
      }
      if (!collapsedIds.value.has(node.node_id) && node.children && node.children.length > 0) {
        traverse(node.children)
      }
    }
  }

  traverse(report.value.tree_hierarchy)
  return result
})

function hasGapDescendant(node: CoverageLineageNodeItem): boolean {
  if (node.children) {
    for (const c of node.children) {
      if (c.is_gap || hasGapDescendant(c)) return true
    }
  }
  return false
}

function selectNode(node: CoverageLineageNodeItem) {
  selectedNode.value = node
  activeDrafts.value = []
}

function toggleCollapse(nodeId: string) {
  if (collapsedIds.value.has(nodeId)) {
    collapsedIds.value.delete(nodeId)
  } else {
    collapsedIds.value.add(nodeId)
  }
}

function getCategoryColor(category: string): string {
  switch (category) {
    case 'requirement':
      return 'blue'
    case 'api_endpoint':
      return 'purple'
    case 'ui_interaction':
      return 'cyan'
    case 'business_branch':
    default:
      return 'orange'
  }
}

function getRiskColor(risk: string): string {
  switch (risk) {
    case 'HIGH':
      return 'red'
    case 'MEDIUM':
      return 'orange'
    case 'LOW':
      return 'blue'
    default:
      return 'default'
  }
}

async function fetchAnalysisReport() {
  analyzing.value = true
  try {
    const defaultData = generateSampleLineage()
    const res = await coverageLineageApi.analyzeLineage({
      project_id: props.projectId || 'ecommerce_prod',
      nodes: defaultData.nodes,
      edges: defaultData.edges,
    })
    report.value = res.report
    if (res.report.nodes.length > 0 && !selectedNode.value) {
      // 默认选中第一个漏测节点
      selectedNode.value = res.report.nodes.find(n => n.is_gap) || res.report.nodes[0]
    }
  } catch {
    // 优雅降级
  } finally {
    analyzing.value = false
  }
}

async function handleSynthesizeSingleNode(node: CoverageLineageNodeItem) {
  synthesizingNode.value = true
  try {
    const res = await coverageLineageApi.synthesizeCases({
      gap_nodes: [node],
    })
    activeDrafts.value = res.drafts
    message.success(`已为节点 [${node.node_name}] 合成 ${res.total_synthesized} 条补测用例草稿`)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '合成用例失败')
  } finally {
    synthesizingNode.value = false
  }
}

async function handleSynthesizeAllGaps() {
  if (!report.value) return
  synthesizing.value = true
  try {
    const gapNodes = report.value.nodes.filter(n => n.is_gap)
    const res = await coverageLineageApi.synthesizeCases({
      gap_nodes: gapNodes,
    })
    activeDrafts.value = res.drafts
    message.success(`全量漏测盲区智能合成完成！共生成 ${res.total_synthesized} 条用例草稿`)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '全量合成用例失败')
  } finally {
    synthesizing.value = false
  }
}

function generateSampleLineage() {
  return {
    nodes: [
      {
        node_id: 'req_01',
        node_name: '用户全流程结算与支付需求',
        category: 'requirement',
        expected_branches: ['正常购买', '账户余额不足', '优惠券抵扣异常'],
        covered_branches: ['正常购买'],
        linked_case_ids: ['case_001'],
      },
      {
        node_id: 'api_02',
        node_name: 'POST /api/v1/orders/checkout 接口',
        category: 'api_endpoint',
        expected_branches: ['200_SUCCESS', '400_BAD_PARAM', '504_PAYMENT_TIMEOUT'],
        covered_branches: ['200_SUCCESS'],
        linked_case_ids: ['case_002'],
      },
      {
        node_id: 'ui_03',
        node_name: 'iOS 客户端结账页点击支付手势',
        category: 'ui_interaction',
        expected_branches: ['单次点击支付', '网络超时快速连续点击防重'],
        covered_branches: ['单次点击支付'],
        linked_case_ids: ['case_003'],
      },
      {
        node_id: 'branch_04',
        node_name: '库存扣减失败回滚与告警',
        category: 'business_branch',
        expected_branches: ['回滚成功', '库存死锁异常重试'],
        covered_branches: [],
        linked_case_ids: [],
      },
    ],
    edges: [
      { edge_id: 'e1', source_id: 'req_01', target_id: 'api_02', relationship: 'implements' },
      { edge_id: 'e2', source_id: 'api_02', target_id: 'ui_03', relationship: 'triggers' },
      { edge_id: 'e3', source_id: 'api_02', target_id: 'branch_04', relationship: 'validates' },
    ],
  }
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      fetchAnalysisReport()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.coverage-gap-inspector-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

/* 顶部指标横幅 */
.coverage-hero-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  flex-wrap: wrap;
  gap: 12px;
}

.hero-left-metrics {
  display: flex;
  align-items: center;
  gap: 20px;
}

.overall-rate-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  background: #ffffff;
  border: 1px solid var(--c-border, #cbd5e1);
  border-radius: 8px;
  min-width: 110px;
}

.rate-num {
  font-size: 26px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.rate-lbl {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  margin-top: 2px;
}

.summary-line {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 13px;
  color: var(--c-text, #1e293b);
}

.gap-highlight {
  color: #ff4d4f;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 4px;
}

.gap-icon {
  font-size: 14px;
}

.summary-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  max-width: 600px;
}

.text-success { color: #52c41a !important; }
.text-warning { color: #faad14 !important; }

/* 主工作区分割网格 */
.inspector-workspace-grid {
  display: grid;
  grid-template-columns: 1fr 440px;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

@media (max-width: 1200px) {
  .inspector-workspace-grid {
    grid-template-columns: 1fr;
  }
}

.tree-topology-panel,
.node-detail-panel {
  display: flex;
  flex-direction: column;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
}

.panel-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--c-bg-subtle, #f1f5f9);
  border-bottom: 1px solid var(--c-border, #cbd5e1);
}

.panel-title {
  font-weight: 700;
  font-size: 13px;
  color: var(--c-text, #1e293b);
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 血缘树行 */
.lineage-tree-nodes-wrap {
  overflow-y: auto;
  max-height: 560px;
}

.lineage-tree-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--c-border-subtle, #f1f5f9);
  cursor: pointer;
  transition: all 0.15s ease;
}

.lineage-tree-row:hover {
  background: var(--c-bg-subtle, #f8fafc);
}

.lineage-tree-row.row-selected {
  background: #e6f4ff !important;
}

.lineage-tree-row.row-gap {
  border-left: 3px solid #fa8c16;
}

.lineage-tree-row.row-high-risk {
  border-left: 3px solid #ff4d4f;
  background: #fff9f9;
}

.toggle-arrow-btn {
  font-size: 10px;
  width: 16px;
  cursor: pointer;
  color: #94a3b8;
}

.toggle-arrow-spacer {
  width: 16px;
}

.mini-cat-tag {
  font-size: 10px;
  line-height: 16px;
  padding: 0 4px;
  margin-right: 0;
}

.node-name-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-gap-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}

.gap-tag {
  font-size: 11px;
}

.risk-tag {
  font-size: 10px;
}

/* 详情抽屉部分 */
.node-detail-content {
  padding: 14px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.gaps-alert-box {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gaps-box-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.gaps-box-title {
  font-weight: 700;
  color: #cf1322;
  font-size: 12px;
}

.alert-red-icon {
  color: #ff4d4f;
}

.missing-branches-chips {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.missing-branch-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #ffffff;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #ffa39e;
  font-size: 12px;
}

.missing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ff4d4f;
}

.branch-name {
  font-weight: 600;
  color: #cf1322;
}

.branch-tip {
  font-size: 11px;
  color: #8c8c8c;
}

.covered-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-sub-title {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  font-weight: 600;
}

.covered-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.covered-chip {
  font-size: 11px;
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
  padding: 2px 8px;
  border-radius: 4px;
}

/* 补全草稿卡片 */
.synthesized-drafts-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.drafts-section-title {
  font-weight: 700;
  font-size: 13px;
  color: #0958d9;
}

.draft-case-card {
  background: #f8fafc;
  border: 1px solid var(--c-border, #cbd5e1);
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.draft-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.draft-title-text {
  font-weight: 700;
  font-size: 12px;
  color: #0f172a;
}

.draft-steps-summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: #475569;
}

.step-num {
  font-weight: 600;
  margin-right: 4px;
}

.step-action-tag {
  color: #94a3b8;
  margin-left: 4px;
}

.draft-outcome {
  font-size: 11px;
  color: #334155;
  background: #ffffff;
  padding: 4px 6px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

.detail-empty-wrap {
  padding: 60px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
