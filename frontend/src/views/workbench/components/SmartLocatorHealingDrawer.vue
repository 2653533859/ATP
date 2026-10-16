<template>
  <a-drawer
    :open="open"
    :width="960"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <div class="drawer-title-box">
        <span>AI 失效选择器 DOM/UI 树多模态自愈恢复</span>
        <a-tag v-if="healingResult?.success" color="green">自愈推导成功</a-tag>
        <a-tag v-else-if="healingResult" color="red">未达置信度</a-tag>
      </div>
    </template>

    <div class="smart-locator-drawer-body">
      <!-- 头部控制栏：选择器输入与预设 -->
      <a-card size="small" class="control-card">
        <div class="control-header">
          <h4 class="title">失效元素选择器与多模态特征差分输入</h4>
          <p class="subtitle">
            当 Web / 移动端前端由于代码重构导致 XPath、CSS 选择器或 ID 失效时，引擎自动对当前活动 DOM 快照进行加权相似度比对（精准标识 35%、文本语义 25%、标签拓扑 20%、业务属性 20%），自动推导出高置信度的稳固定位器。
          </p>
        </div>

        <div class="locator-input-row">
          <a-select v-model:value="locatorType" size="small" style="width: 130px">
            <a-select-option value="xpath">XPath</a-select-option>
            <a-select-option value="css_selector">CSS Selector</a-select-option>
            <a-select-option value="id">ID</a-select-option>
            <a-select-option value="test_id">Test ID</a-select-option>
            <a-select-option value="text">Text 内容</a-select-option>
          </a-select>

          <a-input
            v-model:value="originalLocator"
            placeholder="输入失效的定位表达式，如 //button[@id='btn-old-submit']"
            size="small"
            style="flex: 1"
          />

          <a-space size="small">
            <a-button size="small" @click="loadButtonRefactorPreset">
              载入重构示例
            </a-button>
            <a-button
              type="primary"
              size="small"
              :loading="healing"
              @click="handleHealLocator"
            >
              多模态智能自愈
            </a-button>
          </a-space>
        </div>
      </a-card>

      <!-- 双栏输入：历史特征指纹 vs 当前实时 DOM 树快照 -->
      <a-row :gutter="12" class="editors-row">
        <a-col :span="10">
          <div class="editor-pane">
            <div class="pane-header">
              <span class="pane-title">历史已知元素指纹 (Last Known Fingerprint)</span>
              <a-tag color="blue">参考特征</a-tag>
            </div>
            <a-textarea
              v-model:value="fingerprintJsonText"
              :rows="7"
              class="json-textarea"
              placeholder="历史标签名、文本、属性 JSON..."
            />
          </div>
        </a-col>

        <a-col :span="14">
          <div class="editor-pane">
            <div class="pane-header">
              <span class="pane-title">当前活动页面 DOM 快照列表 (Live DOM Snapshot)</span>
              <a-tag color="purple">实时候选池</a-tag>
            </div>
            <a-textarea
              v-model:value="domSnapshotJsonText"
              :rows="7"
              class="json-textarea"
              placeholder="当前页面抓取的元素指纹数组 JSON..."
            />
          </div>
        </a-col>
      </a-row>

      <!-- 自愈成功推荐最佳定位器卡片 -->
      <a-card v-if="healingResult?.best_proposal" size="small" class="best-proposal-card">
        <div class="best-box">
          <div class="best-header">
            <span class="best-badge">⭐ AI 最优推荐自愈表达式</span>
            <span class="best-score">
              置信度: <strong class="text-green">{{ Math.round(healingResult.best_proposal.confidence_score * 100) }}%</strong>
            </span>
          </div>

          <div class="locator-result-bar">
            <code class="healed-code">{{ healingResult.best_proposal.healed_locator }}</code>
            <a-button size="small" type="primary" ghost @click="copyToClipboard(healingResult.best_proposal.healed_locator)">
              复制自愈选择器
            </a-button>
          </div>

          <div class="best-reason">
            <span class="reason-label">自愈归因分析:</span>
            <span class="reason-text">{{ healingResult.best_proposal.reason }}</span>
          </div>
        </div>
      </a-card>

      <!-- 未达到置信度告警 -->
      <a-alert
        v-if="healingResult && !healingResult.success"
        type="error"
        show-icon
        class="failure-alert"
        message="[自愈未达置信度] 当前页面未发现与历史特征吻合度达到阈值的候选元素"
        description="可能页面已完全跳转至其他视图或核心业务容器已被移除，建议人工核验当前测试用例执行上下文。"
      />

      <!-- 全部候选自愈方案列表表格 -->
      <a-card
        v-if="healingResult && healingResult.all_proposals.length > 0"
        size="small"
        :title="`自愈候选定位器矩阵 (${healingResult.all_proposals.length} 项可选)`"
        class="proposals-table-card"
      >
        <a-table
          :data-source="healingResult.all_proposals"
          :columns="proposalColumns"
          row-key="proposal_id"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'healed_locator'">
              <code class="table-loc-code">{{ record.healed_locator }}</code>
            </template>

            <template v-if="column.key === 'locator_type'">
              <a-tag color="blue">{{ record.locator_type.toUpperCase() }}</a-tag>
            </template>

            <template v-if="column.key === 'confidence'">
              <div class="confidence-cell">
                <span :class="record.confidence_score >= 0.8 ? 'text-green' : 'text-orange'">
                  {{ Math.round(record.confidence_score * 100) }}%
                </span>
                <a-progress
                  :percent="Math.round(record.confidence_score * 100)"
                  :stroke-color="record.confidence_score >= 0.8 ? '#16a34a' : '#ea580c'"
                  size="small"
                  :show-info="false"
                  style="width: 60px"
                />
              </div>
            </template>

            <template v-if="column.key === 'actions'">
              <a-button size="small" type="link" @click="copyToClipboard(record.healed_locator)">
                采纳复制
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  aiHealingLocatorsApi,
  type LocatorHealingResultItem,
  type LocatorType,
} from '@/api/aiHealing'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const healing = ref(false)
const locatorType = ref<LocatorType>('xpath')
const originalLocator = ref("//button[@id='btn-old-submit']")

const defaultFingerprint = {
  tag_name: 'button',
  text_content: '确认支付并提交订单',
  element_id: 'btn-old-submit',
  attributes: {
    'data-testid': 'submit-order-btn',
    role: 'button',
  },
}

const defaultDomSnapshot = [
  {
    tag_name: 'div',
    text_content: '订单结算中心',
    class_names: ['page-title'],
    attributes: {},
  },
  {
    tag_name: 'button',
    text_content: '确认支付并提交订单',
    element_id: 'btn-v2-dynamic-888',
    attributes: {
      'data-testid': 'submit-order-btn',
      role: 'button',
    },
    class_names: ['ant-btn', 'ant-btn-primary'],
  },
]

const fingerprintJsonText = ref(JSON.stringify(defaultFingerprint, null, 2))
const domSnapshotJsonText = ref(JSON.stringify(defaultDomSnapshot, null, 2))
const healingResult = ref<LocatorHealingResultItem | null>(null)

const proposalColumns = [
  { title: '自愈候选定位器', key: 'healed_locator' },
  { title: '类型', key: 'locator_type', width: 110 },
  { title: '置信度', key: 'confidence', width: 130 },
  { title: '生成策略', dataIndex: 'match_strategy', key: 'match_strategy', width: 220 },
  { title: '操作', key: 'actions', width: 90 },
]

function handleClose() {
  emit('update:open', false)
}

function loadButtonRefactorPreset() {
  originalLocator.value = "//button[@id='btn-old-submit']"
  locatorType.value = 'xpath'
  fingerprintJsonText.value = JSON.stringify(defaultFingerprint, null, 2)
  domSnapshotJsonText.value = JSON.stringify(defaultDomSnapshot, null, 2)
  message.info('已载入前端按钮重构重命名示例！')
}

async function handleHealLocator() {
  healing.value = true
  try {
    let fp: any = null
    let domList: any[] = []
    try {
      if (fingerprintJsonText.value.trim()) {
        fp = JSON.parse(fingerprintJsonText.value)
      }
    } catch {
      throw new Error('历史特征指纹 JSON 格式不合法')
    }
    try {
      domList = JSON.parse(domSnapshotJsonText.value)
    } catch {
      throw new Error('DOM 元素快照列表 JSON 格式不合法')
    }

    const res = await aiHealingLocatorsApi.healLocator({
      original_locator: originalLocator.value,
      locator_type: locatorType.value,
      last_known_fingerprint: fp,
      live_dom_elements: domList,
      min_confidence: 0.50,
    })

    healingResult.value = res
    if (res.success && res.best_proposal) {
      message.success(`自愈成功！最优自愈定位器: ${res.best_proposal.healed_locator}`)
    } else {
      message.warning('当前页面未发现置信度达标的自愈定位器')
    }
  } catch (err: any) {
    message.error(err.message || '多模态自愈计算失败')
  } finally {
    healing.value = false
  }
}

function copyToClipboard(text: string) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text)
  }
  message.success('选择器已复制到剪贴板！')
}
</script>

<style scoped>
.smart-locator-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.control-card,
.best-proposal-card,
.proposals-table-card {
  border-radius: 8px;
}

.control-header {
  margin-bottom: 10px;
}

.title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.locator-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.editors-row {
  margin-top: 2px;
}

.editor-pane {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pane-title {
  font-size: 11px;
  font-weight: 600;
  color: #334155;
}

.json-textarea {
  font-family: monospace;
  font-size: 11px;
  background: #ffffff;
}

.best-proposal-card {
  background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
  border: 1px solid #86efac;
}

.best-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.best-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.best-badge {
  font-size: 13px;
  font-weight: 700;
  color: #16a34a;
}

.best-score {
  font-size: 12px;
  color: #64748b;
}

.locator-result-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px dashed #22c55e;
}

.healed-code {
  font-family: monospace;
  font-size: 13px;
  color: #0f172a;
  font-weight: 700;
}

.best-reason {
  font-size: 11px;
  color: #475569;
  line-height: 1.5;
}

.reason-label {
  font-weight: 600;
  color: #1e293b;
  margin-right: 4px;
}

.failure-alert {
  border-radius: 6px;
}

.table-loc-code {
  font-family: monospace;
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
}

.confidence-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
}

.text-green {
  color: #16a34a;
}

.text-orange {
  color: #ea580c;
}
</style>
