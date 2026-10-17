<template>
  <a-modal
    :open="open"
    title="演练爆炸半径安全围栏配置与紧急熔断看门狗"
    width="840px"
    :destroy-on-close="true"
    class="blast-radius-config-modal"
    @cancel="handleCancel"
  >
    <div class="modal-container">
      <!-- 1. 顶部安全围栏核心防线指标横幅 -->
      <div class="guardrail-metrics-banner">
        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ formState.max_impacted_services }} <span class="text-xs">节点</span>
          </div>
          <div class="stat-label">允许波及服务上限</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-danger font-bold font-mono">
            {{ formState.max_error_rate_pct }}%
          </div>
          <div class="stat-label">全局错误率熔断红线</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-warning font-bold font-mono">
            {{ formState.latency_ceiling_ms }}ms
          </div>
          <div class="stat-label">P99 延迟绝对天花板</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            <a-tag :color="formState.auto_abort_enabled ? 'green' : 'orange'">
              {{ formState.auto_abort_enabled ? '看门狗实时熔断' : '仅边界报警' }}
            </a-tag>
          </div>
          <div class="stat-label">越界保护动作</div>
        </div>
      </div>

      <!-- 2. 表单配置区域 -->
      <a-form layout="vertical" class="blast-form">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="演练关联实验 ID">
              <a-input v-model:value="formState.experiment_id" disabled class="font-mono" />
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="安全围栏策略唯一编码">
              <a-input v-model:value="formState.policy_id" disabled class="font-mono text-secondary" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="允许受影响最大微服务节点数 (Max Impacted Services)">
          <div class="slider-input-group">
            <a-slider
              v-model:value="formState.max_impacted_services"
              :min="1"
              :max="10"
              class="flex-1"
            />
            <a-input-number
              v-model:value="formState.max_impacted_services"
              :min="1"
              :max="10"
              style="width: 80px;"
            />
          </div>
          <div class="form-help-text">
            一旦故障扩散超出此服务数量，看门狗将认定爆炸半径失控并触发熔断。
          </div>
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="全局业务错误率熔断红线 (%)">
              <div class="slider-input-group">
                <a-slider
                  v-model:value="formState.max_error_rate_pct"
                  :min="1.0"
                  :max="20.0"
                  :step="0.5"
                  class="flex-1"
                />
                <a-input-number
                  v-model:value="formState.max_error_rate_pct"
                  :min="1.0"
                  :max="20.0"
                  :step="0.5"
                  style="width: 80px;"
                />
              </div>
              <div class="form-help-text text-danger">
                推荐不超过 5.0%，超过即刻判定为生产级击穿风险。
              </div>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="P99 延迟绝对天花板 (ms)">
              <a-input-number
                v-model:value="formState.latency_ceiling_ms"
                :min="300"
                :max="10000"
                :step="100"
                style="width: 100%;"
              />
              <div class="form-help-text">
                接口响应延迟触顶时自动启动熔断切流。
              </div>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="核心 VIP 租户与金丝雀流量豁免白名单 (Exempt Tenants)">
          <a-select
            v-model:value="formState.exempt_tenant_ids"
            mode="tags"
            placeholder="输入受保护的 VIP 租户编码并回车，如 vip_tenant_alipay"
            class="font-mono"
            style="width: 100%;"
          />
          <div class="form-help-text">
            任何带有白名单租户标识的流量，均受到零破坏阻断保护，不予注入故障。
          </div>
        </a-form-item>

        <a-form-item label="自动看门狗毫秒级紧急熔断回滚 (Auto-Abort & Teardown)">
          <div class="switch-row">
            <a-switch v-model:checked="formState.auto_abort_enabled" />
            <span class="switch-desc">
              {{ formState.auto_abort_enabled ? '已开启看门狗自动防御：指标触碰红线时毫秒级强行拔除所有算子并重置演练。' : '仅做边界超标报警通知，不自动剥离故障算子（需人工干预）。' }}
            </span>
          </div>
        </a-form-item>
      </a-form>

      <!-- 3. 安全等级评定与测试看门狗 -->
      <div class="safety-evaluation-card">
        <div class="eval-left">
          <span class="eval-title font-bold">围栏防御严密度评定:</span>
          <a-tag :color="protectionLevelColor">
            {{ protectionLevelLabel }}
          </a-tag>
          <span class="eval-desc text-secondary text-xs">
            {{ protectionLevelDescription }}
          </span>
        </div>

        <div class="eval-right">
          <a-button size="small" type="dashed" danger @click="handleTestWatchdog">
            <template #icon><AlertOutlined /></template>
            测试越界看门狗回滚
          </a-button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="modal-footer">
        <a-button @click="resetToDefaults">恢复默认推荐值</a-button>
        <a-space>
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">
            <template #icon><CheckOutlined /></template>
            保存并应用安全围栏
          </a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { AlertOutlined, CheckOutlined } from '@ant-design/icons-vue'

export interface BlastRadiusPolicy {
  policy_id: string
  experiment_id: string
  max_impacted_services: number
  max_error_rate_pct: number
  latency_ceiling_ms: number
  auto_abort_enabled: boolean
  exempt_tenant_ids: string[]
}

const props = withDefaults(
  defineProps<{
    open: boolean
    experimentId?: string
    initialPolicy?: Partial<BlastRadiusPolicy> | null
  }>(),
  {
    open: false,
    experimentId: 'exp_payment_circuit_breaker',
    initialPolicy: null,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'cancel'): void
  (e: 'save', policy: BlastRadiusPolicy): void
  (e: 'testTriggerAbort', experimentId: string): void
}>()

const saving = ref(false)

const formState = reactive<BlastRadiusPolicy>({
  policy_id: `pol_${Math.random().toString(16).slice(2, 10)}`,
  experiment_id: props.experimentId || 'exp_payment_circuit_breaker',
  max_impacted_services: 2,
  max_error_rate_pct: 5.0,
  latency_ceiling_ms: 1200.0,
  auto_abort_enabled: true,
  exempt_tenant_ids: ['vip_alipay_corp', 'vip_wechat_ent'],
})

watch(
  () => props.initialPolicy,
  (newVal) => {
    if (newVal) {
      if (newVal.policy_id) formState.policy_id = newVal.policy_id
      if (newVal.experiment_id) formState.experiment_id = newVal.experiment_id
      if (newVal.max_impacted_services !== undefined) formState.max_impacted_services = newVal.max_impacted_services
      if (newVal.max_error_rate_pct !== undefined) formState.max_error_rate_pct = newVal.max_error_rate_pct
      if (newVal.latency_ceiling_ms !== undefined) formState.latency_ceiling_ms = newVal.latency_ceiling_ms
      if (newVal.auto_abort_enabled !== undefined) formState.auto_abort_enabled = newVal.auto_abort_enabled
      if (newVal.exempt_tenant_ids) formState.exempt_tenant_ids = [...newVal.exempt_tenant_ids]
    }
  },
  { immediate: true }
)

const protectionLevelLabel = computed(() => {
  if (formState.max_error_rate_pct <= 5.0 && formState.max_impacted_services <= 2 && formState.auto_abort_enabled) {
    return '卓越强安全级 (Tier-1 Enterprise Protection)'
  }
  if (formState.max_error_rate_pct <= 10.0 && formState.auto_abort_enabled) {
    return '标准可用级 (Tier-2 Standard Quarantine)'
  }
  return '放宽探索级 (Tier-3 Permissive Sandbox)'
})

const protectionLevelColor = computed(() => {
  if (protectionLevelLabel.value.includes('Tier-1')) return 'green'
  if (protectionLevelLabel.value.includes('Tier-2')) return 'blue'
  return 'orange'
})

const protectionLevelDescription = computed(() => {
  if (protectionLevelLabel.value.includes('Tier-1')) {
    return '爆炸半径被严格限定在 2 个服务与 5% 错误率内，看门狗自动秒级熔断。'
  }
  return '策略相对放宽，请密切留意稳态破损指标与系统报警。'
})

function resetToDefaults() {
  formState.max_impacted_services = 2
  formState.max_error_rate_pct = 5.0
  formState.latency_ceiling_ms = 1200.0
  formState.auto_abort_enabled = true
  formState.exempt_tenant_ids = ['vip_alipay_corp', 'vip_wechat_ent']
}

function handleCancel() {
  emit('update:open', false)
  emit('cancel')
}

function handleSave() {
  saving.value = true
  emit('save', { ...formState, exempt_tenant_ids: [...formState.exempt_tenant_ids] })
  setTimeout(() => {
    saving.value = false
    emit('update:open', false)
  }, 300)
}

function handleTestWatchdog() {
  emit('testTriggerAbort', formState.experiment_id)
}
</script>

<style scoped>
.modal-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.guardrail-metrics-banner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #fafafa);
  border: 1px solid var(--c-border, #f0f0f0);
  border-radius: 8px;
  text-align: center;
}

.banner-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.stat-num {
  font-size: 18px;
}

.stat-label {
  font-size: 11px;
  color: var(--c-text-secondary, #666);
  margin-top: 2px;
}

.slider-input-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.flex-1 {
  flex: 1;
}

.form-help-text {
  font-size: 11px;
  color: var(--c-text-secondary, #888);
  margin-top: 4px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.switch-desc {
  font-size: 12px;
  color: var(--c-text-secondary, #666);
}

.safety-evaluation-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-surface, #ffffff);
  border: 1px dashed var(--c-border-strong, #d9d9d9);
  border-radius: 6px;
}

.eval-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.eval-title {
  font-size: 13px;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.text-danger {
  color: #ff4d4f;
}

.text-warning {
  color: #faad14;
}

.text-primary {
  color: #1677ff;
}

.text-secondary {
  color: var(--c-text-secondary, #666);
}
</style>
