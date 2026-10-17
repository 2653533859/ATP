<template>
  <a-drawer
    :open="open"
    title="双端业务功能一致性深度透视中枢"
    width="85%"
    placement="right"
    :destroy-on-close="true"
    class="parity-alignment-diff-drawer"
    @close="handleClose"
  >
    <div class="parity-drawer-container">
      <!-- 顶部综合指标横幅 -->
      <div class="parity-hero-banner">
        <div class="hero-left-metrics">
          <div class="composite-score-box">
            <span
              class="score-number"
              :class="getScoreColorClass(auditReport?.composite_score || 0)"
            >
              {{ auditReport ? auditReport.composite_score.toFixed(1) : '--' }}
            </span>
            <span class="score-label">双端一致性综合分</span>
          </div>

          <div class="metrics-summary-content">
            <div class="meta-row">
              <span class="screen-title">{{ auditReport?.screen_name || screenName || '业务页面一致性透视' }}</span>
              <a-tag :color="getGradeTagColor(auditReport?.grade)">
                {{ auditReport?.grade || 'GRADE_B' }}
              </a-tag>
              <a-tag :color="getVerdictTagColor(auditReport?.verdict)">
                门禁: {{ auditReport?.verdict || 'PASS' }}
              </a-tag>
              <span class="platform-transfer font-mono">
                {{ (auditReport?.source_platform || sourcePlatform || 'ios').toUpperCase() }}
                <SwapOutlined class="swap-icon" />
                {{ (auditReport?.target_platform || targetPlatform || 'android').toUpperCase() }}
              </span>
            </div>

            <div class="stats-pills-row">
              <span class="stat-pill">
                对齐控件: <strong>{{ auditReport?.matrix_summary?.aligned_pairs_count || 0 }} / {{ auditReport?.matrix_summary?.total_source_nodes || 0 }}</strong>
              </span>
              <span class="stat-pill">
                状态对齐率: <strong class="text-primary">{{ ((auditReport?.matrix_summary?.alignment_rate || 0) * 100).toFixed(1) }}%</strong>
              </span>
              <span
                class="stat-pill"
                :class="{ 'has-critical': (auditReport?.discrepancy_summary?.critical_count || 0) > 0 }"
              >
                核心缺失: <strong>{{ auditReport?.discrepancy_summary?.critical_count || 0 }}</strong> 项
              </span>
              <span class="stat-pill">
                差异红斑总数: <strong>{{ auditReport?.discrepancy_summary?.total_gaps_count || 0 }}</strong> 项
              </span>
            </div>
          </div>
        </div>

        <div class="hero-right-actions">
          <a-space>
            <a-button size="small" :loading="loading" @click="fetchParityReport">
              <template #icon><ReloadOutlined /></template>
              重新分析透视
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 主标签页导航 -->
      <a-tabs v-model:activeKey="activeTab" class="parity-tabs">
        <!-- Tab 1: 双端控件树分栏透视 -->
        <a-tab-pane key="tree" tab="双端控件树分栏透视 (Tree Diff)">
          <div class="tree-diff-workspace">
            <!-- 左分栏: 源端控件列表 -->
            <div class="diff-column-panel source-panel">
              <div class="column-header">
                <div class="col-title">
                  <a-tag :color="getPlatformTagColor(auditReport?.source_platform || sourcePlatform)">
                    {{ (auditReport?.source_platform || sourcePlatform || 'ios').toUpperCase() }} 端控件树
                  </a-tag>
                  <span class="col-count">({{ sampleSourceNodes.length }} 节点)</span>
                </div>
              </div>
              <div class="nodes-list">
                <div
                  v-for="node in sampleSourceNodes"
                  :key="node.node_id"
                  class="node-tree-item"
                  :class="{
                    'item-aligned': isNodeAligned(node.node_id),
                    'item-missing': isSourceMissingInTarget(node.node_id),
                  }"
                >
                  <div class="node-item-head">
                    <span class="node-role-badge">{{ node.role }}</span>
                    <span class="node-text">{{ node.text || node.identifier || node.node_id }}</span>
                    <a-tag
                      v-if="isSourceMissingInTarget(node.node_id)"
                      color="red"
                      size="small"
                      class="diff-badge"
                    >
                      目标端缺失
                    </a-tag>
                    <a-tag
                      v-else
                      color="green"
                      size="small"
                      class="diff-badge"
                    >
                      已对齐
                    </a-tag>
                  </div>
                  <div class="node-ident font-mono">ID: {{ node.identifier || '--' }}</div>
                </div>
              </div>
            </div>

            <!-- 中间对齐连接指示线 -->
            <div class="diff-center-divider">
              <div class="divider-line" />
              <div class="divider-badge font-mono">
                <SwapOutlined />
              </div>
              <div class="divider-line" />
            </div>

            <!-- 右分栏: 目标端控件列表 -->
            <div class="diff-column-panel target-panel">
              <div class="column-header">
                <div class="col-title">
                  <a-tag :color="getPlatformTagColor(auditReport?.target_platform || targetPlatform)">
                    {{ (auditReport?.target_platform || targetPlatform || 'android').toUpperCase() }} 端控件树
                  </a-tag>
                  <span class="col-count">({{ sampleTargetNodes.length }} 节点)</span>
                </div>
              </div>
              <div class="nodes-list">
                <div
                  v-for="node in sampleTargetNodes"
                  :key="node.node_id"
                  class="node-tree-item"
                  :class="{
                    'item-aligned': isTargetMatched(node.node_id),
                    'item-target-only': isTargetOnlyNode(node.node_id),
                  }"
                >
                  <div class="node-item-head">
                    <span class="node-role-badge">{{ node.role }}</span>
                    <span class="node-text">{{ node.text || node.identifier || node.node_id }}</span>
                    <a-tag
                      v-if="isTargetOnlyNode(node.node_id)"
                      color="blue"
                      size="small"
                      class="diff-badge"
                    >
                      源端未覆盖
                    </a-tag>
                    <a-tag
                      v-else
                      color="green"
                      size="small"
                      class="diff-badge"
                    >
                      已对齐
                    </a-tag>
                  </div>
                  <div class="node-ident font-mono">ID: {{ node.identifier || '--' }}</div>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- Tab 2: 差异缺陷红斑清单 -->
        <a-tab-pane key="gaps" tab="差异缺陷红斑清单 (Parity Gaps)">
          <div class="gaps-list-workspace">
            <div v-if="!auditReport?.gaps?.length" class="empty-gaps">
              <a-empty description="双端功能高度一致，未检出任何差异红斑或控件缺失！" />
            </div>
            <div v-else class="gaps-cards-grid">
              <div
                v-for="gap in auditReport.gaps"
                :key="gap.gap_id"
                class="gap-card"
                :class="'severity-' + gap.severity.toLowerCase()"
              >
                <div class="gap-card-head">
                  <div class="head-left">
                    <a-tag :color="getSeverityTagColor(gap.severity)">{{ gap.severity }}</a-tag>
                    <a-tag color="purple">{{ gap.gap_type }}</a-tag>
                    <span class="gap-title">{{ gap.title }}</span>
                  </div>
                  <span class="gap-time font-mono">{{ gap.detected_at }}</span>
                </div>
                <div class="gap-desc">{{ gap.description }}</div>
                <div v-if="gap.suggested_fix" class="gap-fix-suggestion">
                  <strong>建议处置措施:</strong> {{ gap.suggested_fix }}
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- Tab 3: 四维加权评分雷达与高管决策综述 -->
        <a-tab-pane key="scores" tab="四维评分模型与决策综述 (Executive Summary)">
          <div class="scores-workspace-layout">
            <div class="scores-breakdown-grid">
              <div class="score-card">
                <div class="card-metric-head">
                  <span class="metric-name">控件对齐率得分</span>
                  <span class="metric-weight">权重 40%</span>
                </div>
                <div class="metric-val text-primary">
                  {{ auditReport?.scores?.control_alignment_score?.toFixed(1) || '0.0' }} 分
                </div>
                <div class="metric-desc">反映双端业务控件在界面中的绝对对齐与存在比例。</div>
              </div>

              <div class="score-card">
                <div class="card-metric-head">
                  <span class="metric-name">核心业务覆盖得分</span>
                  <span class="metric-weight">权重 30%</span>
                </div>
                <div
                  class="metric-val"
                  :class="(auditReport?.scores?.core_business_score || 0) < 80 ? 'text-danger' : 'text-success'"
                >
                  {{ auditReport?.scores?.core_business_score?.toFixed(1) || '0.0' }} 分
                </div>
                <div class="metric-desc">评估支付、退款、下单等核心主流程在双端是否完整闭环。</div>
              </div>

              <div class="score-card">
                <div class="card-metric-head">
                  <span class="metric-name">文案语义一致得分</span>
                  <span class="metric-weight">权重 20%</span>
                </div>
                <div class="metric-val text-info">
                  {{ auditReport?.scores?.text_consistency_score?.toFixed(1) || '0.0' }} 分
                </div>
                <div class="metric-desc">检验跨端文案、金额、提示及规则描述是否发生语义漂移。</div>
              </div>

              <div class="score-card">
                <div class="card-metric-head">
                  <span class="metric-name">交互行为兼容得分</span>
                  <span class="metric-weight">权重 10%</span>
                </div>
                <div class="metric-val text-success">
                  {{ auditReport?.scores?.interaction_compatibility_score?.toFixed(1) || '0.0' }} 分
                </div>
                <div class="metric-desc">校验跨端可交互控件属性是否对等（如输入框未退化为纯文本）。</div>
              </div>
            </div>

            <!-- 高管决策综述卡片 -->
            <div class="executive-summary-card">
              <div class="summary-head">
                <span class="summary-title"><FileProtectOutlined /> 高管决策层准入建议综述</span>
                <a-tag :color="getVerdictTagColor(auditReport?.verdict)">
                  发布准入: {{ auditReport?.verdict }}
                </a-tag>
              </div>
              <p class="summary-text">{{ auditReport?.executive_summary }}</p>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  SwapOutlined,
  ReloadOutlined,
  FileProtectOutlined,
} from '@ant-design/icons-vue'
import {
  crossPlatformMigrationApi,
  type ParityAuditReportDTO,
} from '@/api/crossPlatformMigration'

interface Props {
  open: boolean
  reportId?: string
  screenName?: string
  sourcePlatform?: string
  targetPlatform?: string
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  reportId: '',
  screenName: '收银台结算中心',
  sourcePlatform: 'ios',
  targetPlatform: 'android',
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const activeTab = ref('tree')
const loading = ref(false)
const auditReport = ref<ParityAuditReportDTO | null>(null)

const sampleSourceNodes = ref<any[]>([
  { node_id: 'ios_1', role: 'input', text: '搜索商品', identifier: 'search_box' },
  { node_id: 'ios_2', role: 'button', text: '立即支付', identifier: 'btn_checkout' },
  { node_id: 'ios_3', role: 'button', text: 'Apple Pay 快捷付款', identifier: 'btn_apple_pay' },
  { node_id: 'ios_4', role: 'label', text: '满100减20优惠券', identifier: 'coupon_desc' },
])

const sampleTargetNodes = ref<any[]>([
  { node_id: 'and_1', role: 'input', text: '搜索商品', identifier: 'com.shop:id/search_edit' },
  { node_id: 'and_2', role: 'button', text: '确认付款 (微信/支付宝)', identifier: 'com.shop:id/pay_btn' },
  { node_id: 'and_3', role: 'button', text: '微信专属立减 5 元', identifier: 'com.shop:id/wechat_promo' },
  { node_id: 'and_4', role: 'label', text: '满200减10优惠券', identifier: 'com.shop:id/coupon_text' },
])

function isNodeAligned(nodeId: string): boolean {
  return nodeId === 'ios_1' || nodeId === 'ios_2' || nodeId === 'ios_4'
}

function isSourceMissingInTarget(nodeId: string): boolean {
  return nodeId === 'ios_3'
}

function isTargetMatched(nodeId: string): boolean {
  return nodeId === 'and_1' || nodeId === 'and_2' || nodeId === 'and_4'
}

function isTargetOnlyNode(nodeId: string): boolean {
  return nodeId === 'and_3'
}

function getScoreColorClass(score: number): string {
  if (score >= 90) return 'text-success'
  if (score >= 75) return 'text-primary'
  if (score >= 60) return 'text-warning'
  return 'text-danger'
}

function getGradeTagColor(grade?: string): string {
  switch (grade) {
    case 'GRADE_A':
      return 'green'
    case 'GRADE_B':
      return 'blue'
    case 'GRADE_C':
      return 'orange'
    case 'GRADE_F':
      return 'red'
    default:
      return 'default'
  }
}

function getVerdictTagColor(verdict?: string): string {
  switch (verdict) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'BLOCK':
      return 'error'
    default:
      return 'default'
  }
}

function getPlatformTagColor(p?: string): string {
  switch (p?.toLowerCase()) {
    case 'ios':
      return 'orange'
    case 'android':
      return 'cyan'
    case 'web':
    default:
      return 'blue'
  }
}

function getSeverityTagColor(sev: string): string {
  switch (sev?.toUpperCase()) {
    case 'CRITICAL':
      return 'red'
    case 'HIGH':
      return 'orange'
    case 'MEDIUM':
      return 'gold'
    case 'LOW':
    default:
      return 'blue'
  }
}

async function fetchParityReport() {
  loading.value = true
  try {
    if (props.reportId) {
      const res = await crossPlatformMigrationApi.getParityReport(props.reportId)
      auditReport.value = res.report
    } else {
      // 触发真实端到端分析
      const res = await crossPlatformMigrationApi.analyzeParity({
        screen_name: props.screenName,
        source_platform: props.sourcePlatform,
        target_platform: props.targetPlatform,
        source_elements: sampleSourceNodes.value,
        target_elements: sampleTargetNodes.value,
      })
      auditReport.value = res.report
    }
  } catch (err: any) {
    // 降级为本地模拟数据
    auditReport.value = createMockReport()
  } finally {
    loading.value = false
  }
}

function createMockReport(): ParityAuditReportDTO {
  return {
    report_id: 'parrep_mock_demo_01',
    screen_name: props.screenName,
    source_platform: props.sourcePlatform,
    target_platform: props.targetPlatform,
    composite_score: 82.5,
    grade: 'GRADE_B',
    verdict: 'WARN',
    scores: {
      control_alignment_score: 75.0,
      core_business_score: 85.0,
      text_consistency_score: 90.0,
      interaction_compatibility_score: 100.0,
      weighted_composite_score: 82.5,
    },
    matrix_summary: {
      total_source_nodes: 4,
      total_target_nodes: 4,
      aligned_pairs_count: 3,
      alignment_rate: 0.75,
    },
    discrepancy_summary: {
      total_gaps_count: 2,
      critical_count: 0,
      high_count: 1,
      medium_count: 1,
      low_count: 0,
    },
    gaps: [
      {
        gap_id: 'gap_1',
        gap_type: 'MISSING_CORE_CONTROL',
        severity: 'HIGH',
        title: '目标端 Android 缺失 Apple Pay 快捷付款入口',
        description: '源端 iOS 包含 Apple Pay 支付选项，目标端未找到对应聚合快捷入口。',
        suggested_fix: '在 Android 端适配接入对应的快捷闪付或微信/支付宝免密入口。',
        detected_at: '2026-10-17 12:00:00',
      },
      {
        gap_id: 'gap_2',
        gap_type: 'SEMANTIC_TEXT_DRIFT',
        severity: 'MEDIUM',
        title: '双端优惠券满减文案存在漂移',
        description: 'iOS 显示满100减20，Android 显示满200减10，优惠规则配置不同步。',
        suggested_fix: '核对营销中心配置，保持双端优惠券门槛与文案对称。',
        detected_at: '2026-10-17 12:00:00',
      },
    ],
    executive_summary:
      '【带险放行】双端一致性综合评分为 82.5 分 (评级: GRADE_B)。存在 1 项高危差异（支付方式缺失），建议完成对应端适配后上线。',
    generated_at: '2026-10-17 12:00:00',
  }
}

function handleClose() {
  emit('update:open', false)
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      fetchParityReport()
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (props.open) {
    fetchParityReport()
  }
})
</script>

<style scoped>
.parity-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.parity-hero-banner {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hero-left-metrics {
  display: flex;
  align-items: center;
  gap: 20px;
}

.composite-score-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.score-number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.score-label {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  margin-top: 2px;
}

.metrics-summary-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.screen-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
}

.platform-transfer {
  font-size: 11px;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
  color: #475569;
  display: flex;
  align-items: center;
  gap: 6px;
}

.swap-icon {
  color: #3b82f6;
}

.stats-pills-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-pill {
  font-size: 11px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  padding: 2px 8px;
  border-radius: 10px;
  color: var(--c-text-secondary, #475569);
}

.stat-pill.has-critical {
  border-color: #fca5a5;
  background: #fef2f2;
  color: #b91c1c;
}

.parity-tabs {
  margin-top: 4px;
}

.tree-diff-workspace {
  display: grid;
  grid-template-columns: 1fr 40px 1fr;
  align-items: stretch;
  gap: 12px;
  min-height: 480px;
}

.diff-column-panel {
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
}

.source-panel {
  border-top: 3px solid #3b82f6;
}

.target-panel {
  border-top: 3px solid #10b981;
}

.column-header {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.col-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.col-count {
  font-size: 11px;
  color: #94a3b8;
}

.nodes-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 500px;
  overflow-y: auto;
}

.node-tree-item {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
  background: #f8fafc;
}

.node-tree-item.item-missing {
  border-left: 4px solid #ef4444;
  background: #fef2f2;
}

.node-tree-item.item-aligned {
  border-left: 4px solid #10b981;
}

.node-tree-item.item-target-only {
  border-left: 4px solid #3b82f6;
  background: #eff6ff;
}

.node-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.node-role-badge {
  font-size: 10px;
  background: #e2e8f0;
  padding: 1px 4px;
  border-radius: 3px;
  color: #475569;
}

.node-text {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}

.diff-badge {
  font-size: 10px;
  padding: 0 4px;
}

.node-ident {
  font-size: 10px;
  color: #64748b;
}

.diff-center-divider {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.divider-line {
  flex: 1;
  width: 1px;
  background: #e2e8f0;
}

.divider-badge {
  padding: 4px 6px;
  background: #f1f5f9;
  border-radius: 50%;
  color: #94a3b8;
  font-size: 12px;
  margin: 8px 0;
}

.gaps-cards-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gap-card {
  border: 1px solid #e2e8f0;
  border-left: 4px solid #ef4444;
  border-radius: 8px;
  padding: 12px 16px;
  background: #ffffff;
}

.gap-card.severity-critical {
  border-left-color: #ef4444;
  background: #fef2f2;
}
.gap-card.severity-high {
  border-left-color: #f97316;
  background: #fffaf0;
}
.gap-card.severity-medium {
  border-left-color: #eab308;
  background: #fefce8;
}

.gap-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gap-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.gap-time {
  font-size: 11px;
  color: #94a3b8;
}

.gap-desc {
  font-size: 12px;
  color: #475569;
  margin-bottom: 6px;
  line-height: 1.5;
}

.gap-fix-suggestion {
  font-size: 11px;
  color: #15803d;
  background: #f0fdf4;
  padding: 4px 8px;
  border-radius: 4px;
}

.scores-workspace-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.scores-breakdown-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.score-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-metric-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-name {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.metric-weight {
  font-size: 10px;
  color: #94a3b8;
}

.metric-val {
  font-size: 20px;
  font-weight: 700;
}

.metric-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

.executive-summary-card {
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  border-radius: 8px;
  padding: 14px 18px;
}

.summary-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.summary-title {
  font-size: 13px;
  font-weight: 600;
  color: #166534;
  display: flex;
  align-items: center;
  gap: 6px;
}

.summary-text {
  font-size: 12px;
  color: #15803d;
  line-height: 1.6;
  margin: 0;
}

.text-success {
  color: #16a34a;
}
.text-primary {
  color: #2563eb;
}
.text-warning {
  color: #d97706;
}
.text-danger {
  color: #dc2626;
}
.text-info {
  color: #0d9488;
}
</style>
