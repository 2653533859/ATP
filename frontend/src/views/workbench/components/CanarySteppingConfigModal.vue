<template>
  <a-modal
    :open="open"
    title="全链路金丝雀灰度步进调度与自动熔断围栏策略配置"
    width="860px"
    :destroy-on-close="true"
    class="canary-stepping-config-modal"
    @cancel="handleCancel"
  >
    <div class="modal-container">
      <!-- 1. 顶部当前策略概览横幅 -->
      <div class="config-summary-banner">
        <div class="banner-stat">
          <div class="stat-num text-primary font-bold font-mono">
            {{ targetService || 'payment-service' }}
          </div>
          <div class="stat-label">目标灰度微服务</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-success font-bold font-mono">
            {{ formState.initial_probe_weight_pct }}% 探针
          </div>
          <div class="stat-label">初始分流权重</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num text-danger font-bold font-mono">
            +{{ formState.max_error_rate_diff_pct }}%
          </div>
          <div class="stat-label">熔断错误率红线</div>
        </div>

        <div class="banner-stat">
          <div class="stat-num font-mono">
            <a-tag :color="formState.auto_rollback_enabled ? 'green' : 'orange'">
              {{ formState.auto_rollback_enabled ? '秒级熔断已激活' : '仅告警不切流' }}
            </a-tag>
          </div>
          <div class="stat-label">看门狗回滚状态</div>
        </div>
      </div>

      <!-- 2. 多 Tab 策略配置面板 -->
      <a-tabs v-model:activeKey="activeTab" class="config-tabs">
        <!-- Tab 1: 阶梯放量与自适应步进 -->
        <a-tab-pane key="stepping" tab="阶梯放量与自适应调度 (Stepping Plan)">
          <a-form layout="vertical" class="config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="初始探针分流比例 (%)">
                  <a-input-number
                    v-model:value="formState.initial_probe_weight_pct"
                    :min="1"
                    :max="30"
                    :step="1"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    推荐 5% 作为探针期流量，低风险验证生产稳定性
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="单阶梯最小观察请求数 (requests)">
                  <a-input-number
                    v-model:value="formState.min_observation_requests"
                    :min="100"
                    :max="10000"
                    :step="100"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    放量晋级前必须累积达到的样本基数（默认 500 次）
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="健康度晋级门槛分数 (0~100)">
                  <a-input-number
                    v-model:value="formState.health_score_threshold"
                    :min="60"
                    :max="100"
                    :step="1"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    五维健康度评分 ≥ 此分数时准予晋级（默认 90 分）
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="自适应自动放量晋级">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.auto_promote_enabled" />
                    <span class="text-sm font-mono">
                      {{ formState.auto_promote_enabled ? '健康度达标后自动步进下一阶梯' : '必须由运维人工审核后放量' }}
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-tab-pane>

        <!-- Tab 2: 击穿熔断与看门狗围栏 -->
        <a-tab-pane key="guard" tab="击穿熔断与回滚看门狗 (Rollback Guard)">
          <a-form layout="vertical" class="config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="错误率最大容忍偏离差值 (% points)">
                  <a-input-number
                    v-model:value="formState.max_error_rate_diff_pct"
                    :min="0.1"
                    :max="10.0"
                    :step="0.1"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    金丝雀相对基线错误率增量超过此红线即刻熔断（默认 2.0%）
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="P99 响应延迟倍率上限 (x)">
                  <a-input-number
                    v-model:value="formState.max_latency_ratio"
                    :min="1.1"
                    :max="3.0"
                    :step="0.05"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    P99 时延达到基线的多少倍触发严重警告或熔断（默认 1.50x）
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="业务交易成功率硬性底线 (%)">
                  <a-input-number
                    v-model:value="formState.min_success_rate_floor_pct"
                    :min="80.0"
                    :max="99.9"
                    :step="0.5"
                    style="width: 100%"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    核心业务成功率跌破此底线立即触发紧急避险（默认 95.0%）
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="毫秒级自动切流回滚联动">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.auto_rollback_enabled" />
                    <span class="text-sm font-mono">
                      {{ formState.auto_rollback_enabled ? '触碰红线毫秒级清空权重(0%)' : '仅生成报警事件，不自动切流' }}
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-tab-pane>

        <!-- Tab 3: 影子数据隔离与防污染策略 -->
        <a-tab-pane key="isolation" tab="影子存储隔离与防污染 (Data Isolation)">
          <a-form layout="vertical" class="config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="影子表识别后缀 / 前缀正则">
                  <a-input
                    v-model:value="formState.shadow_table_suffix"
                    placeholder="如 _shadow 或 _canary"
                    class="font-mono"
                  />
                  <div class="form-tip text-xs text-secondary mt-1">
                    写入操作必须命中的影子表命名匹配后缀
                  </div>
                </a-form-item>
              </a-col>

              <a-col :span="12">
                <a-form-item label="强制影子表路由校验">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.enforce_shadow_routing" />
                    <span class="text-sm font-mono">
                      {{ formState.enforce_shadow_routing ? '染色写操作全量走影子存储' : '允许部分无状态写操作' }}
                    </span>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="24">
                <a-form-item label="生产核心主库穿透保护">
                  <div class="flex items-center gap-2 pt-1">
                    <a-switch v-model:checked="formState.block_production_master_writes" />
                    <span class="text-sm font-mono text-danger font-bold">
                      严禁金丝雀染色写操作穿透写入生产核心主表（t_order, t_account_balance, t_payment）
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
        <a-button @click="handleResetDefaults">重置为企业推荐默认值</a-button>
        <a-space>
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" :loading="saving" @click="handleSave">
            保存配置并立即下发生效
          </a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'

export interface CanarySteppingConfig {
  initial_probe_weight_pct: number
  min_observation_requests: number
  health_score_threshold: number
  auto_promote_enabled: boolean
  max_error_rate_diff_pct: number
  max_latency_ratio: number
  min_success_rate_floor_pct: number
  auto_rollback_enabled: boolean
  shadow_table_suffix: string
  enforce_shadow_routing: boolean
  block_production_master_writes: boolean
}

const DEFAULT_CONFIG: CanarySteppingConfig = {
  initial_probe_weight_pct: 5.0,
  min_observation_requests: 500,
  health_score_threshold: 90.0,
  auto_promote_enabled: true,
  max_error_rate_diff_pct: 2.0,
  max_latency_ratio: 1.50,
  min_success_rate_floor_pct: 95.0,
  auto_rollback_enabled: true,
  shadow_table_suffix: '_shadow',
  enforce_shadow_routing: true,
  block_production_master_writes: true,
}

const props = withDefaults(
  defineProps<{
    open: boolean
    targetService?: string
    initialConfig?: Partial<CanarySteppingConfig> | null
  }>(),
  {
    open: false,
    targetService: 'payment-service',
    initialConfig: null,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'save', config: CanarySteppingConfig): void
  (e: 'reset'): void
}>()

const activeTab = ref('stepping')
const saving = ref(false)

const formState = reactive<CanarySteppingConfig>({
  ...DEFAULT_CONFIG,
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

.text-danger {
  color: var(--c-error);
}

.font-mono {
  font-family: var(--font-mono, monospace);
  font-variant-numeric: tabular-nums;
}
</style>
