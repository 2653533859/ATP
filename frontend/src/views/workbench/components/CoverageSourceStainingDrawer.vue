<template>
  <a-drawer
    :open="open"
    title="源码逐行代码覆盖率动态染色与分支透视抽屉"
    width="88%"
    placement="right"
    :destroy-on-close="true"
    class="coverage-source-staining-drawer"
    @close="handleClose"
  >
    <div class="staining-drawer-container">
      <!-- 1. 顶部文件覆盖率指标与状态概览横幅 -->
      <div class="staining-hero-bar">
        <div class="hero-left">
          <div class="file-badge-row">
            <FileTextOutlined class="file-icon text-primary" />
            <span class="file-path-title font-mono font-bold">{{ displayFilePath }}</span>
            <a-tag :color="getCoverageTagColor(displayCoveragePct)">
              增量行覆盖率: {{ displayCoveragePct.toFixed(1) }}%
            </a-tag>
          </div>

          <div class="hero-stats font-mono">
            <span class="stat-pill text-success">
              <CheckCircleOutlined /> 已覆盖行: <strong>{{ coveredCount }}</strong>
            </span>
            <span class="stat-pill text-warning">
              <ExclamationCircleOutlined /> 部分分支: <strong>{{ partialCount }}</strong>
            </span>
            <span class="stat-pill text-danger">
              <CloseCircleOutlined /> 未覆盖红行: <strong>{{ uncoveredCount }}</strong>
            </span>
            <span class="stat-pill text-secondary">
              变更总行: <strong>{{ totalChangedCount }}</strong>
            </span>
          </div>
        </div>

        <div class="hero-right">
          <a-space>
            <!-- 视图过滤单选 -->
            <a-radio-group v-model:value="filterMode" size="small" button-style="solid">
              <a-radio-button value="all">全部行 (All)</a-radio-button>
              <a-radio-button value="changed">仅变更行 (Diff)</a-radio-button>
              <a-radio-button value="uncovered">仅红黄未覆盖行</a-radio-button>
            </a-radio-group>

            <a-button @click="handleClose">关闭</a-button>
          </a-space>
        </div>
      </div>

      <!-- 2. 未覆盖红行快捷定位导航条 -->
      <div v-if="uncoveredLinesList.length > 0" class="quick-jump-bar">
        <span class="jump-title text-xs font-bold text-danger">
          未覆盖红线定位 ({{ uncoveredLinesList.length }} 处):
        </span>
        <a-space wrap size="small">
          <a-tag
            v-for="ln in uncoveredLinesList"
            :key="ln"
            color="red"
            class="cursor-pointer font-mono"
            @click="jumpToTargetLine(ln)"
          >
            Line {{ ln }}
          </a-tag>
        </a-space>
      </div>

      <!-- 3. 源码行级红黄绿动态染色视窗 -->
      <a-card class="source-view-card" :body-style="{ padding: '0' }">
        <div class="staining-editor-container font-mono">
          <div
            v-for="line in visibleLines"
            :key="line.line_number"
            :id="`source-line-${line.line_number}`"
            class="code-line-row"
            :class="getLineRowClass(line)"
          >
            <!-- 行号与 Diff 标记 -->
            <div class="line-gutter">
              <span class="diff-indicator font-bold">
                {{ line.is_changed_in_diff ? '+' : ' ' }}
              </span>
              <span class="line-num">{{ line.line_number }}</span>
              <span
                class="hits-badge text-xs"
                :class="line.hits > 0 ? 'text-success' : 'text-secondary'"
              >
                {{ line.hits > 0 ? `${line.hits}x` : '-' }}
              </span>
            </div>

            <!-- 行级染色指示竖条 -->
            <div class="staining-strip" :class="`strip-${line.status.toLowerCase()}`"></div>

            <!-- 源码内容文本 -->
            <div class="code-content">
              <pre class="code-pre">{{ line.content || ' ' }}</pre>
            </div>

            <!-- 分支状态与行末动作 -->
            <div class="line-actions">
              <template v-if="line.status === 'PARTIAL'">
                <a-tag color="orange" class="action-tag text-xs">
                  分支: {{ line.branches_covered }}/{{ line.branches_total }}
                </a-tag>
              </template>
              <template v-else-if="line.status === 'UNCOVERED' && line.is_changed_in_diff">
                <a-button
                  size="small"
                  type="link"
                  danger
                  class="action-btn text-xs"
                  @click="handleRequestSynthesize(line.line_number)"
                >
                  <template #icon><ThunderboltOutlined /></template>
                  生成补测用例
                </a-button>
              </template>
            </div>
          </div>
        </div>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  FileTextOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

export interface StainedLineItem {
  line_number: number
  content: string
  is_changed_in_diff: boolean
  status: 'COVERED' | 'PARTIAL' | 'UNCOVERED' | 'NOT_EXECUTABLE'
  hits: number
  branches_covered?: number
  branches_total?: number
}

const props = withDefaults(
  defineProps<{
    open: boolean
    filePath?: string
    diffLineCoveragePct?: number
    stainedLines?: StainedLineItem[]
  }>(),
  {
    open: false,
    filePath: 'backend/app/services/payment.py',
    diffLineCoveragePct: 80.0,
    stainedLines: () => [],
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
  (e: 'jumpToLine', line: number): void
  (e: 'requestSynthesizeTest', line: number): void
}>()

const filterMode = ref<'all' | 'changed' | 'uncovered'>('all')

const defaultLines: StainedLineItem[] = [
  { line_number: 1, content: 'from __future__ import annotations', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 2, content: 'import uuid', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 3, content: '', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 4, content: 'def execute_checkout_payment(user_id: str, amount: float) -> bool:', is_changed_in_diff: false, status: 'COVERED', hits: 6 },
  { line_number: 5, content: '    # 校验支付金额合法性', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 6, content: '    if amount <= 0:', is_changed_in_diff: true, status: 'PARTIAL', hits: 2, branches_covered: 1, branches_total: 2 },
  { line_number: 7, content: '        raise InvalidAmountException("支付金额必须大于零")', is_changed_in_diff: true, status: 'COVERED', hits: 2 },
  { line_number: 8, content: '', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 9, content: '    wallet = query_user_wallet(user_id)', is_changed_in_diff: true, status: 'COVERED', hits: 4 },
  { line_number: 10, content: '    if wallet.balance < amount:', is_changed_in_diff: true, status: 'COVERED', hits: 4, branches_covered: 2, branches_total: 2 },
  { line_number: 11, content: '        return False', is_changed_in_diff: true, status: 'COVERED', hits: 1 },
  { line_number: 12, content: '', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 13, content: '    # 未测高危分支: 优惠券抵扣与退款安全审计', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 14, content: '    if user_id.startswith("vip_"):', is_changed_in_diff: true, status: 'UNCOVERED', hits: 0 },
  { line_number: 15, content: '        apply_vip_charge_discount(wallet, amount)', is_changed_in_diff: true, status: 'UNCOVERED', hits: 0 },
  { line_number: 16, content: '', is_changed_in_diff: false, status: 'NOT_EXECUTABLE', hits: 0 },
  { line_number: 17, content: '    return deduct_wallet_balance(wallet, amount)', is_changed_in_diff: true, status: 'COVERED', hits: 3 },
]

const displayFilePath = computed(() => props.filePath || 'backend/app/services/payment.py')
const displayCoveragePct = computed(() => (props.diffLineCoveragePct !== undefined ? props.diffLineCoveragePct : 80.0))
const linesData = computed(() => (props.stainedLines && props.stainedLines.length > 0 ? props.stainedLines : defaultLines))

const coveredCount = computed(() => linesData.value.filter(l => l.is_changed_in_diff && l.status === 'COVERED').length)
const partialCount = computed(() => linesData.value.filter(l => l.is_changed_in_diff && l.status === 'PARTIAL').length)
const uncoveredCount = computed(() => linesData.value.filter(l => l.is_changed_in_diff && l.status === 'UNCOVERED').length)
const totalChangedCount = computed(() => linesData.value.filter(l => l.is_changed_in_diff && l.status !== 'NOT_EXECUTABLE').length)

const uncoveredLinesList = computed(() =>
  linesData.value
    .filter(l => l.is_changed_in_diff && (l.status === 'UNCOVERED' || l.status === 'PARTIAL'))
    .map(l => l.line_number)
)

const visibleLines = computed(() => {
  if (filterMode.value === 'changed') {
    return linesData.value.filter(l => l.is_changed_in_diff)
  }
  if (filterMode.value === 'uncovered') {
    return linesData.value.filter(l => l.is_changed_in_diff && (l.status === 'UNCOVERED' || l.status === 'PARTIAL'))
  }
  return linesData.value
})

function getCoverageTagColor(pct: number): string {
  if (pct >= 85.0) return 'green'
  if (pct >= 70.0) return 'orange'
  return 'red'
}

function getLineRowClass(line: StainedLineItem): string {
  const classes = [`status-${line.status.toLowerCase()}`]
  if (line.is_changed_in_diff) {
    classes.push('diff-changed-line')
  }
  return classes.join(' ')
}

function handleClose() {
  emit('update:open', false)
  emit('close')
}

function jumpToTargetLine(ln: number) {
  emit('jumpToLine', ln)
  const el = document.getElementById(`source-line-${ln}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function handleRequestSynthesize(ln: number) {
  emit('requestSynthesizeTest', ln)
}
</script>

<style scoped>
.staining-drawer-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.staining-hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 14px 18px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.file-icon {
  font-size: 16px;
}

.hero-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
}

.stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.quick-jump-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: var(--c-error-soft);
  border: 1px solid var(--c-error);
  border-radius: var(--radius-sm, 6px);
}

.source-view-card {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm, 6px);
  background: var(--c-bg-elevated, var(--c-surface));
  overflow: hidden;
}

.staining-editor-container {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  line-height: 20px;
  max-height: 620px;
  overflow-y: auto;
  font-family: var(--font-mono, monospace);
}

.code-line-row {
  display: flex;
  align-items: center;
  min-height: 24px;
  transition: background 0.15s ease;
}

.code-line-row:hover {
  background: var(--c-primary-soft) !important;
}

/* 行级染色背景 */
.status-covered {
  background: var(--c-success-soft);
}

.status-partial {
  background: var(--c-warning-soft);
}

.status-uncovered {
  background: var(--c-error-soft);
}

.status-not_executable {
  background: transparent;
}

.diff-changed-line {
  font-weight: 500;
}

.line-gutter {
  display: flex;
  align-items: center;
  width: 110px;
  padding: 0 8px;
  background: var(--c-bg-subtle);
  border-right: 1px solid var(--c-border-subtle);
  user-select: none;
}

.diff-indicator {
  width: 14px;
  color: var(--c-primary);
}

.line-num {
  width: 44px;
  text-align: right;
  color: var(--c-text-tertiary);
  padding-right: 8px;
  font-variant-numeric: tabular-nums;
}

.hits-badge {
  width: 32px;
  text-align: right;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.staining-strip {
  width: 4px;
  height: 24px;
  margin-right: 8px;
}

.strip-covered {
  background: var(--c-success);
}

.strip-partial {
  background: var(--c-warning);
}

.strip-uncovered {
  background: var(--c-error);
}

.strip-not_executable {
  background: transparent;
}

.code-content {
  flex: 1;
  overflow-x: auto;
  padding: 0 4px;
}

.code-pre {
  margin: 0;
  font-family: inherit;
  white-space: pre;
  color: var(--c-text);
}

.line-actions {
  display: flex;
  align-items: center;
  padding: 0 12px;
}

.text-danger {
  color: var(--c-error);
}

.text-success {
  color: var(--c-success);
}

.text-warning {
  color: var(--c-warning);
}

.text-primary {
  color: var(--c-primary);
}

.text-secondary {
  color: var(--c-text-secondary);
}
.cursor-pointer {
  cursor: pointer;
}
</style>
