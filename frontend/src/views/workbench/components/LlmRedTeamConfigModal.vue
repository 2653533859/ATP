<template>
  <a-modal
    :open="open"
    title="大模型红蓝对抗渗透策略与安全护栏配置"
    width="880px"
    :destroy-on-close="true"
    class="llm-red-team-config-modal"
    @cancel="handleCancel"
  >
    <div class="modal-container">
      <!-- 1. 顶部配置概览横幅 -->
      <div class="config-summary-banner">
        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ formState.target_model || 'qwen-2.5-72b' }}
          </div>
          <div class="stat-label">被测目标模型</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-success font-bold font-mono">
            {{ enabledVectorsCount }} / 6 种
          </div>
          <div class="stat-label">已激活攻击算子</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            <a-tag :color="getStrictnessColor(formState.guardrail_strictness)">
              {{ getStrictnessLabel(formState.guardrail_strictness) }}
            </a-tag>
          </div>
          <div class="stat-label">护栏防御模式</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-warning font-bold font-mono">
            {{ formState.attack_rounds }} 轮 / 算子
          </div>
          <div class="stat-label">渗透加压轮次</div>
        </div>
      </div>

      <!-- 2. 多 Tab 配置面板 -->
      <a-tabs v-model:activeKey="activeTab" class="config-tabs">
        <!-- Tab 1: 红蓝攻防算子策略 -->
        <a-tab-pane key="operators" tab="红蓝攻防算子库 (Attack Vectors)">
          <div class="tab-pane-content">
            <div class="section-title font-bold mb-3">
              <SecurityScanOutlined class="text-primary mr-1" />
              选择参与对抗渗透的攻击算子与越狱模式：
            </div>

            <div class="operators-grid">
              <div
                v-for="op in attackOperatorCatalog"
                :key="op.key"
                class="operator-card"
                :class="{ 'card-active': formState.enabled_operators.includes(op.key) }"
                @click="toggleOperator(op.key)"
              >
                <div class="operator-header">
                  <a-checkbox
                    :checked="formState.enabled_operators.includes(op.key)"
                    @click.stop
                    @change="toggleOperator(op.key)"
                  />
                  <span class="operator-name font-bold font-mono">{{ op.name }}</span>
                  <a-tag :color="getSeverityColor(op.severity)" class="severity-tag font-mono">
                    {{ op.severity }}
                  </a-tag>
                </div>
                <div class="operator-desc text-secondary">
                  {{ op.desc }}
                </div>
              </div>
            </div>

            <a-divider class="my-4" />

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="单算子渗透变异轮次 (Attack Rounds)">
                  <a-input-number
                    v-model:value="formState.attack_rounds"
                    :min="1"
                    :max="20"
                    class="w-full font-mono"
                  />
                  <div class="form-tip text-secondary mt-1">
                    每种激活的攻击算子自动生成的变异 Prompts 采样轮次 (推荐 3~5 轮)
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="测试违规意图主域">
                  <a-select v-model:value="formState.intent_domain" class="font-mono">
                    <a-select-option value="DATA_EXFILTRATION">支付中台数据窃取与越权</a-select-option>
                    <a-select-option value="PRIVILEGE_OVERRIDE">生产系统删库与特权提权</a-select-option>
                    <a-select-option value="CYBER_RANSOMWARE">勒索病毒与免杀恶意脚本</a-select-option>
                    <a-select-option value="ETHICAL_BYPASS">通用道德准则与合规边界</a-select-option>
                  </a-select>
                  <div class="form-tip text-secondary mt-1">
                    指定变异器生成底层违规攻击指令的核心场景
                  </div>
                </a-form-item>
              </a-col>
            </a-row>
          </div>
        </a-tab-pane>

        <!-- Tab 2: 双向安全护栏看门狗设置 -->
        <a-tab-pane key="guardrails" tab="双向安全护栏看门狗 (Guardrails)">
          <div class="tab-pane-content">
            <a-form layout="vertical">
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item label="护栏审查防御模式">
                    <a-radio-group v-model:value="formState.guardrail_strictness" button-style="solid">
                      <a-radio-button value="PERMISSIVE">宽松模式</a-radio-button>
                      <a-radio-button value="STANDARD">标准模式 (推荐)</a-radio-button>
                      <a-radio-button value="STRICT">严苛模式</a-radio-button>
                    </a-radio-group>
                    <div class="form-tip text-secondary mt-1">
                      标准模式自动脱敏 PII 并阻断高危指令；严苛模式任何 PII 均直接阻断
                    </div>
                  </a-form-item>
                </a-col>

                <a-col :span="12">
                  <a-form-item label="个人隐私 PII 自动脱敏">
                    <a-switch v-model:checked="formState.pii_redaction_enabled" />
                    <span class="ml-2 font-mono">
                      {{ formState.pii_redaction_enabled ? '已启用自动掩码替换' : '关闭脱敏' }}
                    </span>
                    <div class="form-tip text-secondary mt-1">
                      自动将手机号、身份证、银行卡及 API 凭据替换为 [REDACTED_*]
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item label="双向流向控制">
                    <div class="flex gap-4">
                      <a-checkbox v-model:checked="formState.input_inspection">输入 Prompt 审查</a-checkbox>
                      <a-checkbox v-model:checked="formState.output_inspection">模型响应审查</a-checkbox>
                    </div>
                  </a-form-item>
                </a-col>

                <a-col :span="12">
                  <a-form-item label="毫秒级阻断拦截阈值 (SLA)">
                    <a-input-number
                      v-model:value="formState.guardrail_latency_sla_ms"
                      :min="1"
                      :max="50"
                      suffix="ms"
                      class="w-full font-mono"
                    />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item label="自定义敏感词黑名单 (逗号分隔)">
                <a-textarea
                  v-model:value="formState.custom_blocked_keywords_raw"
                  placeholder="如: Project-Titan-Secret, 财务核心密钥, 内部代号..."
                  :rows="2"
                  class="font-mono"
                />
              </a-form-item>
            </a-form>
          </div>
        </a-tab-pane>

        <!-- Tab 3: 模型推理与采样参数 -->
        <a-tab-pane key="inference" tab="模型推理参数 (Inference Specs)">
          <div class="tab-pane-content">
            <a-form layout="vertical">
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item label="被测大模型选型">
                    <a-select v-model:value="formState.target_model" class="font-mono">
                      <a-select-option value="qwen-2.5-72b">Qwen-2.5-72B-Instruct (通义千问)</a-select-option>
                      <a-select-option value="deepseek-v3">DeepSeek-V3-671B (深度求索)</a-select-option>
                      <a-select-option value="deepseek-r1">DeepSeek-R1 (深度推理)</a-select-option>
                      <a-select-option value="llama-3.3-70b">Llama-3.3-70B-Instruct (Meta)</a-select-option>
                      <a-select-option value="gpt-4o">GPT-4o (OpenAI)</a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>

                <a-col :span="12">
                  <a-form-item label="最大生成 Token 数 (Max Tokens)">
                    <a-input-number
                      v-model:value="formState.max_tokens"
                      :min="128"
                      :max="4096"
                      :step="128"
                      class="w-full font-mono"
                    />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item label="采样随机度 (Temperature)">
                    <div class="slider-wrapper">
                      <a-slider
                        v-model:value="formState.temperature"
                        :min="0.0"
                        :max="1.5"
                        :step="0.05"
                        class="flex-1"
                      />
                      <span class="font-mono font-bold ml-2 w-12">{{ formState.temperature.toFixed(2) }}</span>
                    </div>
                  </a-form-item>
                </a-col>

                <a-col :span="12">
                  <a-form-item label="核采样概率 (Top-P)">
                    <div class="slider-wrapper">
                      <a-slider
                        v-model:value="formState.top_p"
                        :min="0.1"
                        :max="1.0"
                        :step="0.05"
                        class="flex-1"
                      />
                      <span class="font-mono font-bold ml-2 w-12">{{ formState.top_p.toFixed(2) }}</span>
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>
            </a-form>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 底部操作按钮 -->
    <template #footer>
      <div class="modal-footer-wrapper">
        <a-button @click="handleReset">
          恢复企业默认策略
        </a-button>

        <a-space>
          <a-button @click="handleCancel">
            取消
          </a-button>
          <a-button type="primary" :loading="saving" @click="handleConfirm">
            保存并触发红蓝对抗评测
          </a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { SecurityScanOutlined } from '@ant-design/icons-vue'

export interface RedTeamConfig {
  target_model: string
  enabled_operators: string[]
  attack_rounds: number
  intent_domain: string
  guardrail_strictness: 'PERMISSIVE' | 'STANDARD' | 'STRICT'
  pii_redaction_enabled: boolean
  input_inspection: boolean
  output_inspection: boolean
  guardrail_latency_sla_ms: number
  custom_blocked_keywords_raw: string
  max_tokens: number
  temperature: number
  top_p: number
}

const props = withDefaults(
  defineProps<{
    open: boolean
    initialConfig?: Partial<RedTeamConfig>
  }>(),
  {
    open: false,
    initialConfig: () => ({}),
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'cancel'): void
  (e: 'confirm', config: RedTeamConfig): void
  (e: 'reset'): void
}>()

const activeTab = ref('operators')
const saving = ref(false)

const attackOperatorCatalog = [
  {
    key: 'JAILBREAK_DAN',
    name: 'DAN 11.0 道德解锁',
    severity: 'HIGH',
    desc: 'Do Anything Now 越狱解除模型所有规则限制',
  },
  {
    key: 'INSTRUCTION_OVERRIDE',
    name: '内核特权指令覆盖',
    severity: 'CRITICAL',
    desc: '伪造最高管理员指令覆盖前置安全系统设定',
  },
  {
    key: 'LEAK_SYSTEM_PROMPT',
    name: '底座提示词窃取探测',
    severity: 'CRITICAL',
    desc: '以合规审计名义探测并诱导打印内部隐藏指令',
  },
  {
    key: 'ENCODING_EVASION',
    name: 'Base64/ROT13 密文混淆',
    severity: 'HIGH',
    desc: '通过多重编码混淆绕过模型静态安全词匹配',
  },
  {
    key: 'ROLE_PLAY_HYPNOSIS',
    name: '剧本角色扮演催眠',
    severity: 'MEDIUM',
    desc: '在小说虚构反恐情节中催眠模型输出有害脚本',
  },
  {
    key: 'PREFIX_INJECTION',
    name: '响应前缀强迫诱导',
    severity: 'HIGH',
    desc: '强制模型无条件以肯定式前缀开头消除拒答意图',
  },
]

const defaultFormState: RedTeamConfig = {
  target_model: 'qwen-2.5-72b',
  enabled_operators: [
    'JAILBREAK_DAN',
    'INSTRUCTION_OVERRIDE',
    'LEAK_SYSTEM_PROMPT',
    'ENCODING_EVASION',
    'ROLE_PLAY_HYPNOSIS',
    'PREFIX_INJECTION',
  ],
  attack_rounds: 3,
  intent_domain: 'DATA_EXFILTRATION',
  guardrail_strictness: 'STANDARD',
  pii_redaction_enabled: true,
  input_inspection: true,
  output_inspection: true,
  guardrail_latency_sla_ms: 5,
  custom_blocked_keywords_raw: '',
  max_tokens: 1024,
  temperature: 0.7,
  top_p: 0.9,
}

const formState = reactive<RedTeamConfig>({
  ...defaultFormState,
  ...props.initialConfig,
})

const enabledVectorsCount = computed(() => formState.enabled_operators.length)

function toggleOperator(key: string) {
  const idx = formState.enabled_operators.indexOf(key)
  if (idx > -1) {
    formState.enabled_operators.splice(idx, 1)
  } else {
    formState.enabled_operators.push(key)
  }
}

function getStrictnessLabel(strictness: string) {
  switch (strictness) {
    case 'STRICT':
      return '严苛模式 (阻断全部 PII)'
    case 'PERMISSIVE':
      return '宽松模式'
    default:
      return '标准模式 (脱敏 PII)'
  }
}

function getStrictnessColor(strictness: string) {
  switch (strictness) {
    case 'STRICT':
      return 'red'
    case 'PERMISSIVE':
      return 'orange'
    default:
      return 'green'
  }
}

function getSeverityColor(sev: string) {
  switch (sev) {
    case 'CRITICAL':
      return 'red'
    case 'HIGH':
      return 'orange'
    default:
      return 'blue'
  }
}

function handleCancel() {
  emit('update:open', false)
  emit('cancel')
}

function handleReset() {
  Object.assign(formState, defaultFormState)
  emit('reset')
}

function handleConfirm() {
  saving.value = true
  emit('confirm', { ...formState })
  setTimeout(() => {
    saving.value = false
    emit('update:open', false)
  }, 200)
}

defineExpose({
  formState,
  handleReset,
  handleConfirm,
})
</script>

<style scoped>
.llm-red-team-config-modal {
  font-family: var(--font-mono, monospace);
}

.modal-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}

.config-summary-banner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: var(--border-radius, 8px);
}

.banner-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.stat-num {
  font-size: 16px;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.tab-pane-content {
  padding: 8px 0;
}

.section-title {
  font-size: 14px;
  color: var(--c-text-primary, #0f172a);
}

.operators-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.operator-card {
  padding: 12px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.operator-card:hover {
  border-color: var(--c-primary, #1677ff);
}

.card-active {
  border-color: var(--c-primary, #1677ff);
  background: rgba(22, 119, 255, 0.03);
}

.operator-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.operator-name {
  font-size: 13px;
  color: var(--c-text-primary, #0f172a);
  flex: 1;
}

.operator-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.5;
  padding-left: 24px;
}

.slider-wrapper {
  display: flex;
  align-items: center;
}

.modal-footer-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
.text-secondary {
  color: var(--c-text-secondary, #64748b);
}

.w-full {
  width: 100%;
}
.mr-1 {
  margin-right: 4px;
}
.ml-2 {
  margin-left: 8px;
}
.mb-3 {
  margin-bottom: 12px;
}
.my-4 {
  margin: 16px 0;
}
.mt-1 {
  margin-top: 4px;
}
.flex {
  display: flex;
}
.flex-1 {
  flex: 1;
}
.gap-4 {
  gap: 16px;
}
</style>
