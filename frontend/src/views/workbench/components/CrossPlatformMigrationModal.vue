<template>
  <a-modal
    :open="open"
    :width="1120"
    title="多模态测试用例跨端智能迁移中枢"
    :footer="null"
    destroy-on-close
    class="cross-platform-migration-modal"
    @cancel="handleClose"
  >
    <div class="migration-modal-body">
      <!-- 头部说明横幅 -->
      <div class="modal-banner">
        <div class="banner-title">
          <SwapOutlined class="banner-icon" />
          <span>Cross-Platform Test Migration Engine</span>
          <a-tag color="processing">v5.3.0 Migration</a-tag>
        </div>
        <p class="banner-desc">
          基于统一跨端语义动作协议（Unified Semantic Action）与多维特征模糊推导，自动将已有测试脚本在 Web、iOS 真机与 Android 真机间进行无损/低损转译，避免多端脚本割裂与重复开发。
        </p>
      </div>

      <!-- 迁移配置卡片 -->
      <div class="config-panel">
        <div class="platform-selector-row">
          <div class="selector-item">
            <span class="selector-label">源端平台 (Source):</span>
            <a-radio-group v-model:value="sourcePlatform" button-style="solid" size="small">
              <a-radio-button value="web">Web 端</a-radio-button>
              <a-radio-button value="ios">iOS 真机</a-radio-button>
              <a-radio-button value="android">Android 真机</a-radio-button>
            </a-radio-group>
          </div>

          <div class="direction-arrow">
            <ArrowRightOutlined class="arrow-icon" />
          </div>

          <div class="selector-item">
            <span class="selector-label">目标端平台 (Target):</span>
            <a-radio-group v-model:value="targetPlatform" button-style="solid" size="small">
              <a-radio-button value="android">Android 真机</a-radio-button>
              <a-radio-button value="ios">iOS 真机</a-radio-button>
              <a-radio-button value="web">Web 端</a-radio-button>
            </a-radio-group>
          </div>
        </div>

        <div class="preset-templates-row">
          <span class="preset-label">快捷测试场景示例:</span>
          <a-button
            v-for="tpl in presetScenarios"
            :key="tpl.label"
            size="small"
            class="preset-btn"
            @click="loadPresetScenario(tpl)"
          >
            {{ tpl.label }}
          </a-button>
        </div>
      </div>

      <!-- 源用例步骤概览与转译触发 -->
      <div class="steps-preview-section">
        <div class="section-header">
          <div class="header-left">
            <span class="section-title"><UnorderedListOutlined /> 待迁移测试步骤序列 ({{ sourceSteps.length }})</span>
            <span class="case-tag">用例名称: {{ customCaseName }}</span>
          </div>
          <div class="header-right">
            <a-button
              type="primary"
              size="small"
              :loading="translating"
              :disabled="sourceSteps.length === 0"
              @click="handleTranslate"
            >
              <ThunderboltOutlined /> 开始跨端智能转译
            </a-button>
          </div>
        </div>

        <!-- 转译结果对比展示 -->
        <div v-if="migrationResult" class="translation-result-summary">
          <div class="summary-pill">
            <span>转译步骤: <strong>{{ migrationResult.mapped_steps_count }} / {{ migrationResult.total_steps }}</strong></span>
          </div>
          <div class="summary-pill">
            <span>平均置信度: <strong class="text-primary">{{ (migrationResult.average_confidence * 100).toFixed(1) }}%</strong></span>
          </div>
          <div class="summary-pill" :class="{ 'has-unresolved': migrationResult.unresolved_count > 0 }">
            <span>未校准控件: <strong>{{ migrationResult.unresolved_count }}</strong></span>
          </div>
        </div>

        <div class="steps-comparison-list">
          <div
            v-for="(step, idx) in displayedSteps"
            :key="step.step_id || idx"
            class="step-compare-row"
          >
            <div class="step-idx">#{{ idx + 1 }}</div>

            <!-- 源端步骤卡片 -->
            <div class="step-card source-card">
              <div class="card-head">
                <a-tag :color="getPlatformColor(sourcePlatform)">{{ sourcePlatform.toUpperCase() }}</a-tag>
                <span class="action-type-badge">{{ step.action_type }}</span>
              </div>
              <div class="locator-info font-mono">
                <code>{{ formatLocator(step.source_locator || step.locator) }}</code>
              </div>
              <div v-if="step.parameters?.text || step.input_text" class="param-info">
                输入文本: <span class="param-val">"{{ step.parameters?.text || step.input_text }}"</span>
              </div>
            </div>

            <!-- 转换指示与置信度 -->
            <div class="compare-middle">
              <ArrowRightOutlined class="middle-arrow" />
              <a-tag
                v-if="step.confidence !== undefined"
                :color="step.confidence >= 0.85 ? 'green' : 'orange'"
                class="confidence-tag"
              >
                {{ (step.confidence * 100).toFixed(0) }}% 置信
              </a-tag>
            </div>

            <!-- 目标端映射后步骤卡片 -->
            <div class="step-card target-card">
              <div class="card-head">
                <a-tag :color="getPlatformColor(targetPlatform)">{{ targetPlatform.toUpperCase() }}</a-tag>
                <span class="action-type-badge">{{ step.action_type }}</span>
              </div>
              <div class="locator-info font-mono">
                <code>{{ formatLocator(step.target_locator) || '等待转译推导...' }}</code>
              </div>
              <div v-if="step.notes" class="notes-info">
                {{ step.notes }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作控制条 -->
      <div class="modal-footer-bar">
        <a-button @click="handleClose">关闭</a-button>
        <a-button
          v-if="migrationResult"
          type="primary"
          @click="handleSaveNewCase"
        >
          <CheckOutlined /> 保存并生成目标端新用例
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SwapOutlined,
  ArrowRightOutlined,
  UnorderedListOutlined,
  ThunderboltOutlined,
  CheckOutlined,
} from '@ant-design/icons-vue'
import {
  crossPlatformMigrationApi,
  type ActionMappingResultDTO,
} from '@/api/crossPlatformMigration'

interface Props {
  open: boolean
  sourceCaseId?: string
  sourceCaseName?: string
  defaultSourcePlatform?: string
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  sourceCaseId: '',
  sourceCaseName: '电商加购与结算全链路用例',
  defaultSourcePlatform: 'web',
})

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'migrated', result: ActionMappingResultDTO): void
}>()

const sourcePlatform = ref('web')
const targetPlatform = ref('android')
const customCaseName = ref('电商加购与结算全链路用例')
const translating = ref(false)
const migrationResult = ref<ActionMappingResultDTO | null>(null)

const sourceSteps = ref<any[]>([
  {
    step_id: 'step_1',
    action_type: 'TAP',
    locator: { type: 'css', value: '#login-btn', text: '登录' },
  },
  {
    step_id: 'step_2',
    action_type: 'FILL_TEXT',
    locator: { type: 'id', value: 'username-input', text: '手机号/账号' },
    input_text: '13800138000',
  },
  {
    step_id: 'step_3',
    action_type: 'TAP',
    locator: { type: 'css', value: '#add-cart-btn', text: '立即加购' },
  },
  {
    step_id: 'step_4',
    action_type: 'TAP',
    locator: { type: 'id', value: 'checkout-button', text: '去结算' },
  },
])

const targetCandidates = ref<any[]>([
  {
    element_id: 'c_1',
    element_type: 'button',
    text: '立即登录',
    identifier: 'com.shop.app:id/btn_login_submit',
  },
  {
    element_id: 'c_2',
    element_type: 'input',
    text: '请输入手机号',
    identifier: 'com.shop.app:id/edit_account_field',
  },
  {
    element_id: 'c_3',
    element_type: 'button',
    text: '加入购物车',
    identifier: 'com.shop.app:id/add_cart_action',
  },
  {
    element_id: 'c_4',
    element_type: 'button',
    text: '去结算 (1件商品)',
    identifier: 'com.shop.app:id/checkout_main_btn',
  },
])

const presetScenarios = [
  {
    label: 'Web 登录加购 ➔ Android 真机',
    src: 'web',
    tgt: 'android',
    name: 'Web 加购结算用例 ➔ Android 迁移',
  },
  {
    label: 'iOS 极速支付 ➔ Web H5 端',
    src: 'ios',
    tgt: 'web',
    name: 'iOS 快捷支付用例 ➔ Web 迁移',
  },
  {
    label: 'Android 生物认证 ➔ iOS FaceID',
    src: 'android',
    tgt: 'ios',
    name: 'Android 生物认证用例 ➔ iOS 迁移',
  },
]

const displayedSteps = computed(() => {
  if (migrationResult.value?.mapped_steps?.length) {
    return migrationResult.value.mapped_steps
  }
  return sourceSteps.value
})

function loadPresetScenario(tpl: any) {
  sourcePlatform.value = tpl.src
  targetPlatform.value = tpl.tgt
  customCaseName.value = tpl.name
  migrationResult.value = null
}

function getPlatformColor(p: string): string {
  switch (p.toLowerCase()) {
    case 'ios':
      return 'orange'
    case 'android':
      return 'cyan'
    case 'web':
    default:
      return 'blue'
  }
}

function formatLocator(loc?: any): string {
  if (!loc) return ''
  if (typeof loc === 'string') return loc
  const t = loc.locator_type || loc.type || ''
  const v = loc.locator_value || loc.value || ''
  const txt = loc.element_text || loc.text || ''
  if (txt) {
    return `[${t}] ${v} ('${txt}')`
  }
  return `[${t}] ${v}`
}

async function handleTranslate() {
  if (sourcePlatform.value === targetPlatform.value) {
    message.warning('源端平台与目标端平台相同，无需迁移转译')
    return
  }
  translating.value = true
  try {
    const res = await crossPlatformMigrationApi.translateCase({
      case_id: props.sourceCaseId || undefined,
      case_name: customCaseName.value,
      source_platform: sourcePlatform.value,
      target_platform: targetPlatform.value,
      steps: sourceSteps.value,
      target_candidates: targetCandidates.value,
    })
    migrationResult.value = res.result
    message.success(res.message || '跨端动作智能转译完成！')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || err?.message || '跨端用例转译失败')
  } finally {
    translating.value = false
  }
}

function handleSaveNewCase() {
  if (!migrationResult.value) return
  emit('migrated', migrationResult.value)
  message.success(`已成功在目标端 [${targetPlatform.value.toUpperCase()}] 生成新用例！`)
  handleClose()
}

function handleClose() {
  emit('update:open', false)
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (props.defaultSourcePlatform) {
        sourcePlatform.value = props.defaultSourcePlatform
      }
      if (props.sourceCaseName) {
        customCaseName.value = props.sourceCaseName
      }
    }
  }
)
</script>

<style scoped>
.migration-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-banner {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
}

.banner-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  margin-bottom: 4px;
}

.banner-icon {
  color: #1677ff;
  font-size: 16px;
}

.banner-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  margin: 0;
  line-height: 1.6;
}

.config-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}

.platform-selector-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.selector-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selector-label {
  font-size: 12px;
  color: var(--c-text-secondary, #475569);
  font-weight: 500;
}

.direction-arrow {
  color: #94a3b8;
  font-size: 16px;
}

.preset-templates-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preset-label {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.preset-btn {
  font-size: 12px;
  border-radius: 12px;
}

.steps-preview-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-primary, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}

.case-tag {
  font-size: 12px;
  color: #64748b;
  margin-left: 12px;
}

.translation-result-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
}

.summary-pill {
  font-size: 12px;
  color: #1e40af;
}

.summary-pill.has-unresolved {
  color: #b91c1c;
}

.steps-comparison-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 440px;
  overflow-y: auto;
  padding: 2px 4px;
}

.step-compare-row {
  display: grid;
  grid-template-columns: 36px 1fr 90px 1fr;
  align-items: center;
  gap: 10px;
}

.step-idx {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  text-align: center;
}

.step-card {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 12px;
  background: #f8fafc;
}

.source-card {
  border-left: 4px solid #3b82f6;
}

.target-card {
  border-left: 4px solid #10b981;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.action-type-badge {
  font-size: 11px;
  font-weight: 600;
  color: #1e293b;
}

.locator-info {
  font-size: 11px;
  color: #334155;
  margin-bottom: 2px;
}

.param-info {
  font-size: 11px;
  color: #64748b;
}

.param-val {
  color: #2563eb;
  font-weight: 500;
}

.notes-info {
  font-size: 10px;
  color: #059669;
}

.compare-middle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.middle-arrow {
  color: #94a3b8;
  font-size: 14px;
}

.confidence-tag {
  font-size: 10px;
  padding: 0 4px;
  margin: 0;
}

.modal-footer-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--c-border-subtle, #e2e8f0);
}
</style>
