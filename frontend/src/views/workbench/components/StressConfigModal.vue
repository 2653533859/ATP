<template>
  <a-modal
    :open="open"
    title="生产全链路影子压测负载模型与过载熔断策略配置"
    width="860px"
    :destroy-on-close="true"
    class="stress-config-modal"
    @cancel="handleCancel"
  >
    <div class="modal-container">
      <!-- 1. 顶部配置概览横幅 -->
      <div class="config-summary-banner">
        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ targetService || 'payment-service' }}
          </div>
          <div class="stat-label">目标压测服务</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-success font-bold font-mono">
            {{ calculatedPeakVu }} VU
          </div>
          <div class="stat-label">规划峰值并发</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-warning font-bold font-mono">
            {{ requiredWorkers }} 节点
          </div>
          <div class="stat-label">所需发压 Worker</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            <a-tag :color="formState.auto_circuit_break_enabled ? 'green' : 'orange'">
              {{ formState.auto_circuit_break_enabled ? '秒级断路已激活' : '仅报警不断流' }}
            </a-tag>
          </div>
          <div class="stat-label">过载熔断保护</div>
        </div>
      </div>

      <!-- 2. 多 Tab 配置表单面板 -->
      <a-tabs v-model:activeKey="activeTab" class="config-tabs">
        <!-- Tab 1: 负载模型与发压梯度 -->
        <a-tab-pane key="load" tab="负载模型与阶梯爬坡 (Load Profile)">
          <a-form layout="vertical" class="config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="发压负载加压模型">
                  <a-select v-model:value="formState.profile_type" class="font-mono">
                    <a-select-option value="STEP_RAMP_UP">阶梯递进爬坡 (Step Ramp-Up)</a-select-option>
                    <a-select-option value="SPIKE_SURGE">瞬时突发脉冲 (Spike Surge)</a-select-option>
                    <a-select-option value="CONSTANT_STEADY">恒定稳态并发 (Constant Steady)</a-select-option>
                    <a-select-option value="SOAK_LONGEVITY">长时浸泡耐久度 (Soak Longevity)</a-select-option>
                  </a-select>
                  <div class="form-tip text-xs text-secondary mt-1">
                    推荐阶梯递进爬坡，以平稳加压自动推导 USL 容量拐点
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="初始并发虚拟用户数 (Initial VU)">
                  <a-input-number
                    v-model:value="formState.initial_vu"
                    :min="50"
                    :max="10000"
                    :step="100"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    第 1 阶梯发压起始并发基数（默认 500 VU）
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item label="单阶段递增并发 (Step VU)">
                  <a-input-number
                    v-model:value="formState.step_vu"
                    :min="100"
                    :max="5000"
                    :step="100"
                    style="width: 100%"
                    class="font-mono"
                  />
                </a-form-item>
              </a-col>

              <a-col :span="8">
                <a-form-item label="爬坡阶梯总级数 (Steps)">
                  <a-input-number
                    v-model:value="formState.steps_count"
                    :min="1"
                    :max="10"
                    :step="1"
                    style="width: 100%"
                    class="font-mono"
                  />
                </a-form-item>
              </a-col>

              <a-col :span="8">
                <a-form-item label="单阶段稳态时长 (秒)">
                  <a-input-number
                    v-model:value="formState.stage_duration_seconds"
                    :min="10"
                    :max="1800"
                    :step="10"
                    style="width: 100%"
                    class="font-mono"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-tab-pane>

        <!-- Tab 2: 生产防击穿熔断围栏 -->
        <a-tab-pane key="guard" tab="生产防击穿过载熔断 (Circuit Breaker)">
          <a-form layout="vertical" class="config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="请求错误率熔断红线 (%)">
                  <a-input-number
                    v-model:value="formState.max_error_rate_pct"
                    :min="0.1"
                    :max="10.0"
                    :step="0.1"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    生产服务错误率突破此红线即刻断路切流（默认 1.0%）
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="生产 Pod 核心 CPU 保护上限 (%)">
                  <a-input-number
                    v-model:value="formState.max_cpu_utilization_pct"
                    :min="50"
                    :max="95"
                    :step="5"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    生产 CPU 占用超标毫秒级紧急泄压（默认 85%）
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="P99 响应耗时上限 (ms)">
                  <a-input-number
                    v-model:value="formState.max_p99_latency_ms"
                    :min="100"
                    :max="5000"
                    :step="50"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    P99 时延突破此阈值触发过载保护（默认 500ms）
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="毫秒级自动断路切流泄压">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.auto_circuit_break_enabled" />
                    <span class="text-sm font-mono">
                      {{ formState.auto_circuit_break_enabled ? '触碰红线瞬间清零并发并切断流量' : '仅触发安全告警，不断流' }}
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-tab-pane>

        <!-- Tab 3: 影子存储隔离与清理规则 -->
        <a-tab-pane key="isolation" tab="影子存储隔离与清理 (Shadow Storage)">
          <a-form layout="vertical" class="config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="影子库表识别后缀">
                  <a-input
                    v-model:value="formState.shadow_table_suffix"
                    placeholder="如 _shadow 或 _stress"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    压测流量写操作必须命中的影子存储后缀
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="压测结束自动预演清理">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.auto_purge_on_finish" />
                    <span class="text-sm font-mono">
                      {{ formState.auto_purge_on_finish ? '压测达标后自动生成清理报告' : '仅手动触发归档清理' }}
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="24">
                <a-form-item label="生产核心主库防穿透强制锁">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.block_master_writes" />
                    <span class="text-sm font-mono text-danger font-bold">
                      严禁压测写操作穿透写入生产真实主表（t_order, t_account_balance, t_users）
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 弹窗底部操作按钮 -->
    <template #footer>
      <div class="modal-footer-actions">
        <a-button @click="handleResetDefaults">重置为推荐默认值</a-button>
        <a-space>
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">
            保存配置并生成发压作业
          </a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'

export interface StressConfigState {
  profile_type: string
  initial_vu: number
  step_vu: number
  steps_count: number
  stage_duration_seconds: number
  max_error_rate_pct: number
  max_cpu_utilization_pct: number
  max_p99_latency_ms: number
  auto_circuit_break_enabled: boolean
  shadow_table_suffix: string
  auto_purge_on_finish: boolean
  block_master_writes: boolean
}

const DEFAULT_CONFIG: StressConfigState = {
  profile_type: 'STEP_RAMP_UP',
  initial_vu: 500,
  step_vu: 1000,
  steps_count: 5,
  stage_duration_seconds: 60,
  max_error_rate_pct: 1.0,
  max_cpu_utilization_pct: 85.0,
  max_p99_latency_ms: 500.0,
  auto_circuit_break_enabled: true,
  shadow_table_suffix: '_shadow',
  auto_purge_on_finish: true,
  block_master_writes: true,
}

const props = withDefaults(
  defineProps<{
    open: boolean
    targetService?: string
    initialConfig?: Partial<StressConfigState> | null
  }>(),
  {
    open: false,
    targetService: 'payment-service',
    initialConfig: null,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'save', config: StressConfigState): void
  (e: 'reset'): void
}>()

const activeTab = ref('load')
const saving = ref(false)

const formState = reactive<StressConfigState>({
  ...DEFAULT_CONFIG,
})

const calculatedPeakVu = computed(() => {
  return formState.initial_vu + (formState.steps_count - 1) * formState.step_vu
})

const requiredWorkers = computed(() => {
  return Math.max(1, Math.ceil(calculatedPeakVu.value / 2000))
})

watch(
  () => props.initialConfig,
  (cfg) => {
    if (cfg) {
      Object.assign(formState, DEFAULT_CONFIG, cfg)
    } else {
      Object.assign(formState, DEFAULT_CONFIG)
    }
  },
  { immediate: true }
)

function handleCancel() {
  emit('update:open', false)
}

function handleResetDefaults() {
  Object.assign(formState, DEFAULT_CONFIG)
  emit('reset')
}

function handleSave() {
  saving.value = true
  emit('save', { ...formState })
  setTimeout(() => {
    saving.value = false
    emit('update:open', false)
  }, 300)
}
</script>

<style scoped>
.modal-container {
  padding: 6px 0;
}

.config-summary-banner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 14px 16px;
  background: var(--c-surface, var(--c-bg-elevated));
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-xs);
  margin-bottom: 18px;
}

.banner-stat {
  text-align: center;
}

.stat-num {
  font-size: 16px;
  font-weight: 700;
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
  margin-bottom: 2px;
}

.stat-label {
  font-size: 12px;
  color: var(--c-text-secondary);
}

.config-tabs {
  margin-top: 4px;
}

.config-form {
  padding-top: 10px;
}

.form-tip {
  color: var(--c-text-secondary);
}

.modal-footer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.text-primary {
  color: var(--c-primary);
}

.text-secondary {
  color: var(--c-text-secondary);
}

.text-success {
  color: var(--c-success);
}

.text-warning {
  color: var(--c-warning);
}

.text-danger {
  color: var(--c-error);
}

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}
</style>
