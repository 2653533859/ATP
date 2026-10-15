<template>
  <div class="exploration-trace-synthesizer">
    <!-- 头部摘要与去噪折叠比例 -->
    <div class="synthesis-header-bar">
      <div class="header-left">
        <h4 class="title">探索事件流实时轨迹与自动化用例合成</h4>
        <p class="subtitle">
          将移动/Web 探索遍历中捕获的连击、渐进打字等高噪事件流，自动折叠提炼为包含终态断言的规范 TestCase 资产。
        </p>
      </div>
      <div class="header-stats">
        <div class="stat-pill">
          <span class="stat-lbl">原始捕获事件:</span>
          <strong>{{ rawEvents.length }} 条</strong>
        </div>
        <div class="stat-arrow">→</div>
        <div class="stat-pill highlight">
          <span class="stat-lbl">提炼提纯步骤:</span>
          <strong>{{ synthesizedResult?.steps?.length ?? estimatedStepsCount }} 步</strong>
        </div>
        <a-tag color="green" class="compression-tag">
          压缩率 {{ compressionRate }}%
        </a-tag>
      </div>
    </div>

    <a-row :gutter="20" class="main-content-row">
      <!-- 左侧：事件流轨迹与用例配置 -->
      <a-col :span="12">
        <a-card title="事件流轨迹与用例参数" size="small" class="form-card">
          <a-form layout="vertical">
            <a-form-item label="生成用例名称" required>
              <a-input v-model:value="caseForm.name" placeholder="例如: 探索自动化冒烟 - 订单结算链路" />
            </a-form-item>

            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="目标归属模块 ID" required>
                  <a-input-number v-model:value="caseForm.moduleId" :min="1" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="用例类型与终端">
                  <a-select v-model:value="caseForm.caseType" style="width: 100%">
                    <a-select-option value="android">Android 移动端</a-select-option>
                    <a-select-option value="web">Web 浏览器</a-select-option>
                    <a-select-option value="ios">iOS 移动端</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="直接持久化落库至用例资产管理">
              <a-switch v-model:checked="caseForm.persist" checked-children="落库保存" un-checked-children="仅预演" />
              <span class="switch-tip">{{ caseForm.persist ? '将自动创建 TestCase 记录并可在用例库中持续运行' : '仅在当前页面预演去噪与断言结果' }}</span>
            </a-form-item>

            <div class="action-buttons">
              <a-button type="primary" :loading="synthesizing" @click="runSynthesis">
                一键合成规范 TestCase
              </a-button>
              <a-button @click="resetToSampleEvents">
                载入典型高噪事件流
              </a-button>
            </div>
          </a-form>

          <a-divider style="margin: 16px 0" />

          <!-- 原始捕获事件流缩略清单 -->
          <div class="stream-title">捕获原始事件流 (Raw Stream: {{ rawEvents.length }} items)</div>
          <div class="raw-stream-list">
            <div v-for="(evt, idx) in rawEvents" :key="idx" class="raw-stream-item">
              <span class="idx">#{{ idx + 1 }}</span>
              <a-tag :color="getEventTagColor(String(evt.action_type || 'click'))" class="evt-tag">
                {{ evt.action_type || 'click' }}
              </a-tag>
              <span class="evt-desc">
                {{ formatEventDescription(evt) }}
              </span>
            </div>
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：合成后规范用例与步骤断言预览 -->
      <a-col :span="12">
        <a-card title="规范化 TestCase 步骤与断言预览" size="small" class="preview-card">
          <div v-if="synthesizedResult" class="synthesized-panel">
            <div class="case-meta-header">
              <div class="meta-title">
                <strong>{{ synthesizedResult.name }}</strong>
                <a-tag color="blue">{{ synthesizedResult.case_type }}</a-tag>
                <a-tag v-if="synthesizedResult.id" color="purple">ID: {{ synthesizedResult.id }} (已落库)</a-tag>
              </div>
              <div v-if="synthesizedResult.description" class="meta-desc">
                {{ synthesizedResult.description }}
              </div>
            </div>

            <div class="step-list-header">
              <span>提炼步骤列表 ({{ synthesizedResult.steps?.length ?? 0 }} 步)</span>
              <a-tag color="cyan">含终态断言</a-tag>
            </div>

            <div class="synthesized-step-list">
              <div
                v-for="(st, sIdx) in (synthesizedResult.steps || [])"
                :key="sIdx"
                class="synthesized-step-row"
                :class="{ 'assertion-step': st.action.startsWith('assert') }"
              >
                <div class="step-num">{{ sIdx + 1 }}</div>
                <div class="step-content">
                  <div class="step-topline">
                    <span class="step-name">{{ st.name }}</span>
                    <a-tag :color="st.action.startsWith('assert') ? 'gold' : 'blue'" class="action-tag">
                      {{ st.action }}
                    </a-tag>
                    <a-tag v-if="st.is_key_step" color="green">关键交互</a-tag>
                  </div>
                  <div class="step-params">
                    <code>{{ JSON.stringify(st.params) }}</code>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="synthesizedResult.id" class="case-success-banner">
              <span>用例已成功落库，可在自动化用例库中执行或编排到测试套件中！</span>
            </div>
          </div>

          <a-empty
            v-else
            description="点击左侧「一键合成规范 TestCase」即可查看提纯后的用例步骤与断言"
            style="margin: 80px 0"
          />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  explorationApi,
  type SynthesizeCaseResponse,
} from '@/api/exploration'

const synthesizing = ref(false)
const synthesizedResult = ref<SynthesizeCaseResponse | null>(null)

const caseForm = ref({
  name: '自动探索冒烟用例 - 商品结算流',
  moduleId: 1,
  caseType: 'android' as 'android' | 'web' | 'ios',
  persist: false,
})

const rawEvents = ref<Array<Record<string, unknown>>>([])

const resetToSampleEvents = () => {
  rawEvents.value = [
    { action_type: 'click', element: { text: '加入购物车', resource_id: 'btn_cart', bounds: '[100,500][300,550]' } },
    { action_type: 'click', element: { text: '加入购物车', resource_id: 'btn_cart', bounds: '[100,500][300,550]' } }, // 连击噪声
    { action_type: 'input', text: 'u', element: { resource_id: 'txt_coupon' } },
    { action_type: 'input', text: 'us', element: { resource_id: 'txt_coupon' } },
    { action_type: 'input', text: 'user888', element: { resource_id: 'txt_coupon' } }, // 连续输入
    { action_type: 'click', element: { text: '去结算', resource_id: 'btn_checkout', bounds: '[400,900][700,950]' } },
    { action_type: 'back' },
    { action_type: 'click', element: { text: '去结算', resource_id: 'btn_checkout', bounds: '[400,900][700,950]' } },
    { action_type: 'click', element: { text: '提交订单', resource_id: 'btn_submit', bounds: '[200,800][500,850]' } },
    {
      action_type: 'screen_state',
      screen_name: 'PaymentSuccessScreen',
      elements: [{ text: '支付成功，等待商家发货' }, { text: '订单号: ATP20261016' }],
    },
  ]
}

const estimatedStepsCount = computed(() => {
  return Math.max(1, Math.round(rawEvents.value.length * 0.45))
})

const compressionRate = computed(() => {
  const initial = rawEvents.value.length
  if (initial <= 1) return 0
  const finalCount = synthesizedResult.value?.steps?.length ?? estimatedStepsCount.value
  return Math.max(0, Math.round(((initial - finalCount) / initial) * 100))
})

const getEventTagColor = (action: string): string => {
  switch (action) {
    case 'click':
      return 'blue'
    case 'input':
      return 'orange'
    case 'back':
      return 'purple'
    case 'screen_state':
      return 'green'
    default:
      return 'default'
  }
}

const formatEventDescription = (evt: Record<string, unknown>): string => {
  const action = String(evt.action_type || 'click')
  if (action === 'screen_state') {
    return `到达终态页面: ${String(evt.screen_name || 'SuccessScreen')}`
  }
  const el = evt.element as Record<string, unknown> | undefined
  if (el) {
    const text = el.text ? `"${String(el.text)}"` : ''
    const id = el.resource_id ? `#${String(el.resource_id)}` : ''
    return `${action} -> ${text} ${id}`.trim()
  }
  return `${action} (全局或返回)`
}

const runSynthesis = async () => {
  if (!caseForm.value.name.trim()) {
    message.warning('请输入用例名称')
    return
  }
  synthesizing.value = true
  try {
    const res = await explorationApi.synthesizeCase({
      name: caseForm.value.name,
      module_id: caseForm.value.moduleId,
      case_type: caseForm.value.caseType,
      events: rawEvents.value,
      description: '由 ATP AI 智能探索引擎自动去噪提炼合成',
      persist: caseForm.value.persist,
    })
    synthesizedResult.value = res as SynthesizeCaseResponse
    if (caseForm.value.persist && res.id) {
      message.success(`用例成功落库保存！用例 ID: ${res.id}`)
    } else {
      message.success(`成功提纯去噪 ${res.steps?.length ?? 0} 个可执行用例步骤`)
    }
  } catch (err: unknown) {
    const msg = (err && typeof err === 'object' && 'message' in err) ? String(err.message) : '用例合成失败'
    message.error(msg)
  } finally {
    synthesizing.value = false
  }
}

onMounted(() => {
  resetToSampleEvents()
})
</script>

<style scoped>
.exploration-trace-synthesizer {
  padding: 4px 0;
}
.synthesis-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 20px;
}
.header-left .title {
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: var(--c-text-primary, #111827);
}
.header-left .subtitle {
  font-size: 12px;
  color: var(--c-text-secondary, #6b7280);
  margin: 0;
}
.header-stats {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stat-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--c-bg-page, #f3f4f6);
  border-radius: 20px;
  font-size: 12px;
}
.stat-pill.highlight {
  background: rgba(24, 144, 255, 0.1);
  color: #1890ff;
}
.stat-arrow {
  color: #9ca3af;
  font-weight: 700;
}
.compression-tag {
  font-weight: 600;
}
.main-content-row {
  margin-top: 4px;
}
.form-card,
.preview-card {
  border-radius: 8px;
  min-height: 520px;
}
.switch-tip {
  font-size: 11px;
  color: var(--c-text-tertiary, #9ca3af);
  margin-left: 10px;
}
.action-buttons {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}
.stream-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text-secondary, #374151);
  margin-bottom: 8px;
}
.raw-stream-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}
.raw-stream-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--c-bg-page, #f9fafb);
  border-radius: 4px;
  font-size: 12px;
}
.raw-stream-item .idx {
  color: #9ca3af;
  font-family: monospace;
  width: 28px;
}
.evt-tag {
  margin-right: 0;
}
.evt-desc {
  font-family: monospace;
  font-size: 11px;
  color: var(--c-text-secondary, #4b5563);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.case-meta-header {
  padding: 10px 14px;
  background: rgba(24, 144, 255, 0.05);
  border: 1px solid rgba(24, 144, 255, 0.15);
  border-radius: 6px;
  margin-bottom: 14px;
}
.meta-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.meta-desc {
  font-size: 11px;
  color: var(--c-text-tertiary, #6b7280);
  margin-top: 4px;
}
.step-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}
.synthesized-step-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 340px;
  overflow-y: auto;
}
.synthesized-step-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  background: var(--c-bg-page, #f9fafb);
  border: 1px solid var(--c-border-subtle, #e5e7eb);
  border-radius: 6px;
}
.synthesized-step-row.assertion-step {
  border-left: 3px solid #faad14;
  background: rgba(250, 173, 20, 0.04);
}
.step-num {
  font-size: 12px;
  font-weight: 700;
  color: #1890ff;
  width: 20px;
  margin-top: 2px;
}
.step-content {
  flex: 1;
  min-width: 0;
}
.step-topline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.step-name {
  font-size: 13px;
  font-weight: 600;
}
.step-params code {
  font-size: 11px;
  background: var(--c-bg-surface, #ffffff);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--c-text-secondary, #4b5563);
}
.case-success-banner {
  margin-top: 14px;
  padding: 8px 12px;
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid rgba(82, 196, 26, 0.2);
  border-radius: 6px;
  color: #52c41a;
  font-size: 12px;
  font-weight: 600;
}
</style>
