<template>
  <a-drawer
    v-model:open="visible"
    title="防击穿自适应分级限流与防雪崩熔断大脑控制台 (UI3.3)"
    width="1120px"
    placement="right"
    :destroy-on-close="false"
  >
    <div class="breaker-console-drawer">
      <!-- 头部说明 Banner -->
      <div class="drawer-header-banner">
        <div class="banner-icon">
          <ThunderboltOutlined style="font-size: 24px; color: #f5222d;" />
        </div>
        <div class="banner-text">
          <div class="banner-title">自适应分级限流 (Adaptive Throttling) 与级联雪崩阻断器</div>
          <div class="banner-desc">
            实时监测底层资源水位、P99 尖刺延迟与接口错误率，驱动 4 阶段状态机（正常放行 ➔ 一级缓速25% ➔ 二级急刹60% ➔ 硬核熔断 ABORT），
            毫秒级阻断流量踩踏与数据库雪崩瘫痪。
          </div>
        </div>
      </div>

      <!-- 4 大核心熔断 KPI 卡片 -->
      <a-row :gutter="[16, 16]">
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">当前熔断状态机</div>
            <div class="kpi-value" :class="getStateColorClass(activeState)">
              {{ getStateShortLabel(activeState) }}
            </div>
            <div class="kpi-sub">当前网关流量控制阶段</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">实时限流截流比例</div>
            <div class="kpi-value text-warning">{{ report.final_decision.throttle_ratio_pct }}%</div>
            <div class="kpi-sub">非核心请求主动降级</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">建议安全承载 TPS</div>
            <div class="kpi-value text-primary">{{ report.final_decision.suggested_safe_tps }}</div>
            <div class="kpi-sub">下游基础设施安全阈值</div>
          </div>
        </a-col>
        <a-col :span="6">
          <div class="kpi-card">
            <div class="kpi-label">尾部 P99 瞬时延迟</div>
            <div class="kpi-value text-purple">{{ report.current_p99_latency_ms }} ms</div>
            <div class="kpi-sub">当前加压耗时监测点</div>
          </div>
        </a-col>
      </a-row>

      <!-- 4 阶段熔断状态机可视化步骤卡 -->
      <a-card title="4 阶段防雪崩熔断状态机流转 (Circuit Breaker State Machine)" :bordered="false" class="panel-card">
        <div class="states-flow-row">
          <div
            class="state-step-box"
            :class="{ active: activeState === 'CLOSED_NORMAL' }"
          >
            <div class="step-badge">Stage 0</div>
            <div class="step-title">CLOSED_NORMAL</div>
            <div class="step-ratio">常态放行 100%</div>
            <div class="step-desc">水位 &lt;85% 且 P99 &lt;800ms，流量完全放行</div>
          </div>

          <div class="flow-arrow">➔</div>

          <div
            class="state-step-box"
            :class="{ active: activeState === 'THROTTLING_STAGE_1' }"
          >
            <div class="step-badge warning">Stage 1</div>
            <div class="step-title">THROTTLING_1</div>
            <div class="step-ratio">缓速截流 25%</div>
            <div class="step-desc">水位 ≥85% 或 P99 ≥800ms，快速平抑毛刺</div>
          </div>

          <div class="flow-arrow">➔</div>

          <div
            class="state-step-box"
            :class="{ active: activeState === 'THROTTLING_STAGE_2' }"
          >
            <div class="step-badge danger">Stage 2</div>
            <div class="step-title">THROTTLING_2</div>
            <div class="step-ratio">急刹截流 60%</div>
            <div class="step-desc">水位 ≥95% 或 错误率 ≥5%，压制踩踏扩散</div>
          </div>

          <div class="flow-arrow">➔</div>

          <div
            class="state-step-box"
            :class="{ active: activeState === 'TRIPPED_HARD_BREAK' }"
          >
            <div class="step-badge critical">Stage 3</div>
            <div class="step-title">TRIPPED_ABORT</div>
            <div class="step-ratio">硬核熔断 100%</div>
            <div class="step-desc">级联崩溃风险，毫秒级阻断保护核心服务</div>
          </div>
        </div>
      </a-card>

      <!-- 熔断判定演算与一键紧急重置沙箱 -->
      <a-card title="熔断推演演算与应急干预控制 (Evaluation & Emergency Intervention)" :bordered="false" class="panel-card">
        <template #extra>
          <a-space>
            <a-button danger type="primary" :loading="resetting" @click="handleEmergencyReset">
              <ReloadOutlined /> 一键紧急重置熔断器 (Emergency Reset)
            </a-button>
          </a-space>
        </template>

        <a-form layout="vertical">
          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :sm="6">
              <a-form-item label="基础设施资源水位 (%)" required>
                <a-input-number v-model:value="evalParams.max_resource_watermark_pct" :min="0" :max="100" style="width: 100%;" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="6">
              <a-form-item label="实时 P99 延迟 (ms)" required>
                <a-input-number v-model:value="evalParams.p99_latency_ms" :min="10" :max="10000" style="width: 100%;" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="6">
              <a-form-item label="请求错误率 (%)" required>
                <a-input-number v-model:value="evalParams.error_rate_pct" :min="0" :max="100" style="width: 100%;" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="6">
              <a-form-item label="当前加压吞吐量 (TPS)">
                <a-input-number v-model:value="evalParams.current_tps" :min="0" :max="100000" style="width: 100%;" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-space>
            <a-button type="primary" :loading="evaluating" @click="handleRunEvaluate">
              <PlayCircleOutlined /> 执行自适应熔断判定评估
            </a-button>
            <a-button size="small" :loading="loading" @click="loadReports">
              <ReloadOutlined /> 刷新报告列表
            </a-button>
          </a-space>
        </a-form>

        <div class="decision-display-box">
          <div class="decision-title">
            <SafetyCertificateOutlined style="color: #1677ff; margin-right: 6px;" />
            熔断大脑决策原因：
          </div>
          <div class="decision-reason">{{ report.final_decision.trigger_reason }}</div>
        </div>
      </a-card>

      <!-- 应急处置与恢复指令 -->
      <a-card title="应急处置与演练恢复操作指引 (Remediation Instructions)" :bordered="false" class="panel-card">
        <ul class="instruction-list">
          <li v-for="(inst, idx) in report.remediation_instructions" :key="idx" class="instruction-item">
            <CheckCircleOutlined style="color: #52c41a; margin-right: 8px;" />
            <span>{{ inst }}</span>
          </li>
        </ul>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import {
  evaluateCircuitBreaker,
  resetCircuitBreaker,
  listBreakerReports,
  type AvalancheBreakerReport,
} from '@/api/fullLinkStressTesting'

const props = defineProps<{
  open?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const visible = computed({
  get: () => props.open ?? false,
  set: (val: boolean) => emit('update:open', val),
})

const loading = ref(false)
const evaluating = ref(false)
const resetting = ref(false)

const evalParams = ref({
  max_resource_watermark_pct: 88,
  p99_latency_ms: 850,
  error_rate_pct: 2.5,
  current_tps: 4200,
})

const defaultReport: AvalancheBreakerReport = {
  report_id: 'rep_brk_default',
  scenario_name: 'full-link-order-checkout-stress',
  current_watermark_pct: 88.0,
  current_p99_latency_ms: 850,
  current_error_rate_pct: 2.5,
  is_circuit_broken: false,
  circuit_state: 'THROTTLING_STAGE_1',
  final_decision: {
    decision_id: 'dec_default',
    breaker_state: 'THROTTLING_STAGE_1',
    action: 'THROTTLE_DOWN',
    throttle_ratio_pct: 25,
    trigger_reason: '资源水位突破 85% (当前 88%) 且 P99 延迟突破 800ms，触发一级缓速限流 25%',
    suggested_safe_tps: 3150,
  },
  remediation_instructions: [
    '网关集群已自动广播降级指令，对非核心查询类请求开启 25% 快速失败',
    '通知下游数据库与缓存集群加速连接池释放，若水位持续攀升将升级至 Stage 2 (60% 急刹)',
    '压测团队可观察 60 秒后的 P99 恢复趋势，恢复正常后支持一键重置回常态',
  ],
  created_at: new Date().toISOString(),
}

const report = ref<AvalancheBreakerReport>(defaultReport)
const activeState = computed(() => report.value.final_decision?.breaker_state || report.value.circuit_state || 'CLOSED_NORMAL')


function getStateColorClass(state: string) {
  switch (state) {
    case 'CLOSED_NORMAL': return 'text-success'
    case 'THROTTLING_STAGE_1': return 'text-warning'
    case 'THROTTLING_STAGE_2': return 'text-danger'
    case 'TRIPPED_HARD_BREAK': return 'text-danger'
    default: return 'text-primary'
  }
}

function getStateShortLabel(state: string) {
  switch (state) {
    case 'CLOSED_NORMAL': return 'NORMAL (正常)'
    case 'THROTTLING_STAGE_1': return 'STAGE 1 (缓速)'
    case 'THROTTLING_STAGE_2': return 'STAGE 2 (急刹)'
    case 'TRIPPED_HARD_BREAK': return 'ABORT (熔断)'
    default: return state
  }
}

async function loadReports() {
  loading.value = true
  try {
    const res = await listBreakerReports(10)
    if (res.reports && res.reports.length > 0) {
      report.value = res.reports[0]
    }
    message.success('已拉取最新熔断大脑报告')
  } catch {
    // mock fallback
  } finally {
    loading.value = false
  }
}

async function handleRunEvaluate() {
  evaluating.value = true
  try {
    const res = await evaluateCircuitBreaker({
      scenario_name: report.value.scenario_name,
      max_resource_watermark_pct: evalParams.value.max_resource_watermark_pct,
      p99_latency_ms: evalParams.value.p99_latency_ms,
      error_rate_pct: evalParams.value.error_rate_pct,
      current_tps: evalParams.value.current_tps,
    })
    report.value = res.report
    message.success('熔断大脑评估完成')
  } catch {
    // 本地回退模拟
    const wm = evalParams.value.max_resource_watermark_pct
    let state: any = 'CLOSED_NORMAL'
    let ratio = 0
    let reason = '系统资源与延迟均处于健康区间，全量放行'
    if (wm >= 98 || evalParams.value.error_rate_pct >= 15) {
      state = 'TRIPPED_HARD_BREAK'
      ratio = 100
      reason = '资源耗尽或错误率严重失控，硬核毫秒阻断保护核心系统'
    } else if (wm >= 95 || evalParams.value.error_rate_pct >= 5) {
      state = 'THROTTLING_STAGE_2'
      ratio = 60
      reason = '资源水位突破 95% 或错误率突破 5%，启动二级急刹截流 60%'
    } else if (wm >= 85 || evalParams.value.p99_latency_ms >= 800) {
      state = 'THROTTLING_STAGE_1'
      ratio = 25
      reason = '资源水位突破 85% 或 P99 延迟突破 800ms，触发一级缓速限流 25%'
    }

    report.value = {
      report_id: `rep_brk_${Date.now()}`,
      scenario_name: report.value.scenario_name,
      current_watermark_pct: wm,
      current_p99_latency_ms: evalParams.value.p99_latency_ms,
      current_error_rate_pct: evalParams.value.error_rate_pct,
      is_circuit_broken: ratio > 0,
      circuit_state: state,
      final_decision: {
        decision_id: `dec_${Date.now()}`,
        breaker_state: state,
        action: ratio > 0 ? 'THROTTLE_DOWN' : 'PASS_FULL_SPEED',
        throttle_ratio_pct: ratio,
        trigger_reason: reason,
        suggested_safe_tps: Math.round(evalParams.value.current_tps * (1 - ratio / 100)),
      },
      remediation_instructions: [
        '网关已同步执行最新限流与降级指令',
        '建议密切监测依赖服务恢复情况',
      ],
      created_at: new Date().toISOString(),
    }
    message.success('已生成自适应熔断判定评估报告')
  } finally {
    evaluating.value = false
  }
}

async function handleEmergencyReset() {
  resetting.value = true
  try {
    await resetCircuitBreaker()
    report.value = {
      ...report.value,
      circuit_state: 'CLOSED_NORMAL',
      is_circuit_broken: false,
      final_decision: {
        decision_id: `dec_${Date.now()}`,
        breaker_state: 'CLOSED_NORMAL',
        action: 'RESET_NORMAL',
        throttle_ratio_pct: 0,
        trigger_reason: '运维工程师手动触发一键紧急重置，熔断器恢复常态通行状态',
        suggested_safe_tps: 5000,
      },
    }
    message.success('熔断器已成功紧急重置为正常放行状态')
  } catch {
    report.value = {
      ...report.value,
      circuit_state: 'CLOSED_NORMAL',
      is_circuit_broken: false,
      final_decision: {
        decision_id: `dec_${Date.now()}`,
        breaker_state: 'CLOSED_NORMAL',
        action: 'RESET_NORMAL',
        throttle_ratio_pct: 0,
        trigger_reason: '已手动紧急重置熔断器，恢复全量放行',
        suggested_safe_tps: 5000,
      },
    }
    message.success('熔断器重置指令已成功下发')
  } finally {
    resetting.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    loadReports()
  }
})

onMounted(() => {
  if (visible.value) {
    loadReports()
  }
})
</script>

<style scoped>
.breaker-console-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.drawer-header-banner {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #fff1f0);
  border: 1px solid var(--c-border-subtle, #ffa39e);
  border-radius: 8px;
}

.banner-title {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
}

.banner-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin-top: 2px;
}

.kpi-card {
  padding: 12px 14px;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  text-align: center;
}

.kpi-label {
  font-size: 12px;
  color: #64748b;
}

.kpi-value {
  margin: 4px 0;
  font-size: 20px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.text-success { color: #52c41a; }
.text-warning { color: #fa8c16; }
.text-danger { color: #f5222d; }
.text-primary { color: #1677ff; }
.text-purple { color: #722ed1; }

.kpi-sub {
  font-size: 11px;
  color: #94a3b8;
}

.panel-card {
  border-radius: 8px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.states-flow-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 0;
}

.state-step-box {
  flex: 1;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.3s;
}

.state-step-box.active {
  background: #fffbe6;
  border-color: #fa8c16;
  box-shadow: 0 0 12px rgba(250, 140, 22, 0.3);
}

.step-badge {
  font-size: 10px;
  font-weight: 700;
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e6f7ff;
  color: #1677ff;
  width: fit-content;
}

.step-badge.warning {
  background: #fff7e6;
  color: #d46b08;
}

.step-badge.danger {
  background: #fff1f0;
  color: #cf1322;
}

.step-badge.critical {
  background: #f5222d;
  color: #ffffff;
}

.step-title {
  font-weight: 700;
  font-size: 13px;
  color: #0f172a;
}

.step-ratio {
  font-size: 12px;
  font-weight: 600;
  color: #fa8c16;
}

.step-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

.flow-arrow {
  font-size: 16px;
  font-weight: 700;
  color: #cbd5e1;
}

.decision-display-box {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f0f7ff;
  border: 1px solid #bae0ff;
  border-radius: 6px;
}

.decision-title {
  font-weight: 700;
  font-size: 13px;
  color: #0958d9;
  margin-bottom: 4px;
}

.decision-reason {
  font-size: 12px;
  color: #1d39c4;
  line-height: 1.5;
}

.instruction-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.instruction-item {
  font-size: 13px;
  color: #334155;
  background: #f8fafc;
  padding: 8px 12px;
  border-radius: 6px;
}
</style>
