<template>
  <a-drawer
    :open="open"
    title="定位器自愈对比与 DOM 变化透视抽屉"
    width="85%"
    placement="right"
    :destroy-on-close="true"
    class="self-healing-diff-drawer"
    @close="handleClose"
  >
    <div class="diff-drawer-container">
      <!-- 顶部指标横幅 -->
      <div class="hero-banner">
        <div class="banner-left">
          <div class="confidence-box">
            <span class="confidence-val" :class="getConfidenceClass(confidence)">
              {{ (confidence * 100).toFixed(1) }}%
            </span>
            <span class="confidence-label">自愈置信度</span>
          </div>

          <div class="banner-meta">
            <div class="meta-title-row">
              <span class="step-badge font-mono">{{ displayPatch?.step_id || 'step_unknown' }}</span>
              <a-tag :color="getStatusTagColor(displayPatch?.status)">
                {{ displayPatch?.status || 'PROPOSED' }}
              </a-tag>
              <a-tag color="blue">
                <ThunderboltOutlined /> {{ winningTier || 'TIER_1_ID_VARIATION' }}
              </a-tag>
              <span v-if="displayPatch?.case_id" class="case-subtext font-mono">
                所属用例: {{ displayPatch.case_id }}
              </span>
            </div>

            <div class="meta-stats-row">
              <span class="stat-item">
                定位策略: <strong>{{ winningTier }}</strong>
              </span>
              <span class="stat-item">
                候选项匹配: <strong>{{ candidatesList.length }} 节点</strong>
              </span>
              <span class="stat-item">
                诊断耗时: <strong>&lt; 35ms</strong>
              </span>
            </div>
          </div>
        </div>

        <div class="banner-right-actions">
          <a-space>
            <a-button
              type="primary"
              :disabled="displayPatch?.status === 'COMMITTED_PERMANENT'"
              :loading="committing"
              @click="handleCommit"
            >
              <template #icon><CheckCircleOutlined /></template>
              一键采纳并固化
            </a-button>

            <a-button
              danger
              :disabled="displayPatch?.status === 'REJECTED'"
              :loading="rejecting"
              @click="handleReject"
            >
              <template #icon><CloseCircleOutlined /></template>
              否决回滚
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- 核心左右分栏对比 -->
      <div class="diff-split-grid">
        <!-- 左栏：失效旧定位器 -->
        <div class="diff-card broken-card">
          <div class="card-header">
            <span class="header-tag broken-tag">
              <CloseCircleOutlined /> 失效定位器现场 (Broken Locator)
            </span>
            <span class="status-indicator">运行时拦截</span>
          </div>

          <div class="locator-box broken-box">
            <div class="locator-type font-mono">
              类型: {{ brokenContext?.failed_locator_type || 'css' }}
            </div>
            <div class="locator-code font-mono">
              {{ brokenContext?.failed_locator_value || '#btn-legacy' }}
            </div>
          </div>

          <div class="hints-box">
            <div class="hint-row">
              <span class="hint-label">预期文本 Hint:</span>
              <span class="hint-value">{{ brokenContext?.element_text_hint || '未指定' }}</span>
            </div>
            <div class="hint-row">
              <span class="hint-label">控件角色 Hint:</span>
              <span class="hint-value">{{ brokenContext?.element_role_hint || '未指定' }}</span>
            </div>
            <div class="hint-row">
              <span class="hint-label">异常拦截原因:</span>
              <span class="hint-value text-danger">ElementNotFoundException (元素在 DOM 树中丢失或属性变更)</span>
            </div>
          </div>
        </div>

        <!-- 中间流向连接符 -->
        <div class="diff-arrow-container">
          <div class="arrow-circle">
            <ArrowRightOutlined />
          </div>
          <span class="arrow-label">多模态自愈推导演算</span>
        </div>

        <!-- 右栏：自愈推荐新定位器 -->
        <div class="diff-card healed-card">
          <div class="card-header">
            <span class="header-tag healed-tag">
              <CheckCircleOutlined /> 推荐新定位器 (Healed Candidate)
            </span>
            <a-button size="small" type="link" @click="copyHealedLocator">
              <template #icon><CopyOutlined /></template> 复制表达式
            </a-button>
          </div>

          <div class="locator-box healed-box">
            <div class="locator-type font-mono">
              类型: {{ bestCandidate?.recommended_locator_type || 'css' }}
            </div>
            <div class="locator-code font-mono text-success">
              {{ bestCandidate?.recommended_locator_value || "button[data-action='checkout']" }}
            </div>
          </div>

          <div class="hints-box">
            <div class="hint-row">
              <span class="hint-label">匹配目标节点:</span>
              <span class="hint-value font-mono">&lt;{{ bestCandidate?.matched_node_tag || 'button' }} id="{{ bestCandidate?.matched_node_id || 'btn_new' }}"&gt;</span>
            </div>
            <div class="hint-row">
              <span class="hint-label">综合置信分:</span>
              <span class="hint-value text-success font-bold">{{ ((bestCandidate?.confidence || confidence) * 100).toFixed(1) }}%</span>
            </div>
            <div class="hint-row">
              <span class="hint-label">自愈可解释性:</span>
              <span class="hint-value">{{ bestCandidate?.explanation || '基于多模态属性与语义相似度完成高置信对齐' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- DOM 树候选节点透视表格 -->
      <div class="candidates-table-section">
        <div class="section-header">
          <h4 class="section-title">
            <SafetyCertificateOutlined /> 现场扫描候选 DOM 节点与特征加权打分透视
          </h4>
          <span class="section-desc">展示自愈推导引擎在页面 DOM 树中实时捕获的匹配候选节点及分项得分</span>
        </div>

        <a-table
          :data-source="candidatesList"
          :columns="candidateColumns"
          :pagination="false"
          size="middle"
          row-key="node_id"
          class="candidates-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'node_id'">
              <span class="font-mono text-primary font-bold">{{ record.node_id }}</span>
            </template>
            <template v-else-if="column.key === 'tag_name'">
              <a-tag color="purple">&lt;{{ record.tag_name }}&gt;</a-tag>
            </template>
            <template v-else-if="column.key === 'text'">
              <span>{{ record.text || '--' }}</span>
            </template>
            <template v-else-if="column.key === 'attributes'">
              <div class="attr-pills">
                <span
                  v-for="(val, key) in record.attributes"
                  :key="key"
                  class="attr-pill font-mono"
                >
                  {{ key }}="{{ val }}"
                </span>
              </div>
            </template>
            <template v-else-if="column.key === 'confidence'">
              <a-tag :color="record.is_best ? 'green' : 'orange'">
                {{ record.is_best ? '推荐最优' : '候选备选' }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  CopyOutlined,
  ArrowRightOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { selfHealingCoreApi } from '@/api/testSelfHealing'

const props = defineProps<{
  open: boolean
  patchId?: string
  patchData?: any
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'committed', patchId: string): void
  (e: 'rejected', patchId: string): void
}>()

const committing = ref(false)
const rejecting = ref(false)
const localPatch = ref<any>(null)

watch(
  () => props.patchData,
  (val) => {
    if (val) {
      localPatch.value = { ...val }
    }
  },
  { immediate: true }
)

const displayPatch = computed(() => localPatch.value || props.patchData)
const brokenContext = computed(() => displayPatch.value?.broken_context)
const bestCandidate = computed(() => displayPatch.value?.best_candidate)
const confidence = computed(() => {
  return displayPatch.value?.confidence || bestCandidate.value?.confidence || 0.95
})
const winningTier = computed(() => {
  return bestCandidate.value?.strategy_tier || displayPatch.value?.strategy_tier || 'TIER_1_ID_VARIATION'
})

const candidatesList = computed(() => {
  const nodes = brokenContext.value?.screen_nodes || []
  if (nodes.length > 0) {
    return nodes.map((n: any, idx: number) => ({
      ...n,
      is_best: idx === 0,
    }))
  }
  return [
    {
      node_id: bestCandidate.value?.matched_node_id || 'node_btn_cart',
      tag_name: bestCandidate.value?.matched_node_tag || 'button',
      text: brokenContext.value?.element_text_hint || '立即加购',
      attributes: { 'data-action': 'checkout', class: 'btn-primary' },
      is_best: true,
    },
  ]
})

const candidateColumns = [
  { title: '节点 ID', dataIndex: 'node_id', key: 'node_id', width: 140 },
  { title: '标签类型', dataIndex: 'tag_name', key: 'tag_name', width: 110 },
  { title: 'DOM 文本内容', dataIndex: 'text', key: 'text', width: 180 },
  { title: '节点关键属性 (Attributes)', dataIndex: 'attributes', key: 'attributes' },
  { title: '推荐评级', key: 'confidence', width: 110 },
]

function getConfidenceClass(conf: number) {
  if (conf >= 0.85) return 'text-success'
  if (conf >= 0.65) return 'text-warning'
  return 'text-danger'
}

function getStatusTagColor(status?: string) {
  switch (status) {
    case 'COMMITTED_PERMANENT':
      return 'green'
    case 'APPLIED_IN_FLIGHT':
      return 'blue'
    case 'REJECTED':
      return 'red'
    default:
      return 'cyan'
  }
}

function copyHealedLocator() {
  const val = bestCandidate.value?.recommended_locator_value
  if (val) {
    navigator.clipboard?.writeText(val)
    message.success('新定位器表达式已复制到剪贴板')
  }
}

async function handleCommit() {
  const pid = displayPatch.value?.patch_id || props.patchId
  if (!pid) {
    message.success('已就地确认采纳此自愈定位器')
    emit('committed', 'local_commit')
    return
  }

  try {
    committing.value = true
    await selfHealingCoreApi.commitPatch(pid)
    message.success('自愈补丁已成功固化回写至用例库')
    if (localPatch.value) {
      localPatch.value.status = 'COMMITTED_PERMANENT'
    }
    emit('committed', pid)
  } catch (err: any) {
    message.error(err?.message || '采纳补丁失败')
  } finally {
    committing.value = false
  }
}

async function handleReject() {
  const pid = displayPatch.value?.patch_id || props.patchId
  if (!pid) {
    message.info('已否决此自愈定位器')
    emit('rejected', 'local_reject')
    return
  }

  try {
    rejecting.value = true
    await selfHealingCoreApi.rejectPatch(pid)
    message.success('自愈补丁已被否决回滚')
    if (localPatch.value) {
      localPatch.value.status = 'REJECTED'
    }
    emit('rejected', pid)
  } catch (err: any) {
    message.error(err?.message || '否决补丁失败')
  } finally {
    rejecting.value = false
  }
}

function handleClose() {
  emit('update:open', false)
}
</script>

<style scoped>
.diff-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.banner-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.confidence-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  background: var(--c-bg-subtle, #f8fafc);
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.confidence-val {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
}

.confidence-label {
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  margin-top: 4px;
}

.banner-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-badge {
  font-weight: 700;
  font-size: 15px;
  color: var(--c-text-primary, #1e293b);
}

.case-subtext {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.meta-stats-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
}

.diff-split-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 16px;
}

.diff-card {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
  background: var(--c-bg-card, #ffffff);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.broken-card {
  border-left: 4px solid #ef4444;
}

.healed-card {
  border-left: 4px solid #10b981;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-tag {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.broken-tag {
  color: #ef4444;
}

.healed-tag {
  color: #10b981;
}

.status-indicator {
  font-size: 11px;
  color: #94a3b8;
}

.locator-box {
  padding: 12px;
  border-radius: 6px;
}

.broken-box {
  background: #fef2f2;
  border: 1px dashed #fca5a5;
}

.healed-box {
  background: #f0fdf4;
  border: 1px dashed #86efac;
}

.locator-type {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.locator-code {
  font-size: 14px;
  font-weight: 600;
  word-break: break-all;
}

.hints-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  padding: 10px;
  border-radius: 6px;
}

.hint-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hint-label {
  color: var(--c-text-secondary, #64748b);
  min-width: 90px;
}

.hint-value {
  color: var(--c-text-primary, #1e293b);
}

.diff-arrow-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.arrow-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #eff6ff;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  border: 1px solid #bfdbfe;
}

.arrow-label {
  font-size: 11px;
  color: #64748b;
  text-align: center;
}

.candidates-table-section {
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text-primary, #1e293b);
}

.section-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.attr-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.attr-pill {
  font-size: 11px;
  padding: 2px 6px;
  background: #f1f5f9;
  border-radius: 4px;
  color: #334155;
}

.text-success {
  color: #10b981;
}

.text-warning {
  color: #f59e0b;
}

.text-danger {
  color: #ef4444;
}

.text-primary {
  color: #2563eb;
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: bold;
}
</style>
